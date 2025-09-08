"""
Event processor for handling queue polling and UI updates.

This module provides the EventProcessor class that polls the event queue
and dispatches events to appropriate UI handlers with throttling and
performance optimizations.
"""

import threading
import time
from typing import Dict, Callable, Optional, List
from datetime import datetime, timedelta

from .events import BaseEvent, EventType, RequestEvent, ResponseEvent, ErrorEvent, StatusEvent
from .event_queue import EventQueue, EventFilter
from px_ui.performance import UpdateThrottler, ThrottleConfig, ThrottleMode, BatchUpdateThrottler


class EventThrottler:
    """Throttles event processing to prevent UI overload."""
    
    def __init__(self, max_events_per_second: int = 50):
        """
        Initialize throttler.
        
        Args:
            max_events_per_second: Maximum events to process per second
        """
        self.max_events_per_second = max_events_per_second
        self.min_interval = 1.0 / max_events_per_second
        self.last_process_time = 0.0
        self.event_count = 0
        self.window_start = time.time()
        
    def should_process(self) -> bool:
        """
        Check if we should process more events based on throttling rules.
        
        Returns:
            True if we can process more events
        """
        current_time = time.time()
        
        # Reset window if more than 1 second has passed
        if current_time - self.window_start >= 1.0:
            self.window_start = current_time
            self.event_count = 0
        
        # Check if we're under the rate limit
        if self.event_count < self.max_events_per_second:
            # Check minimum interval between events
            if current_time - self.last_process_time >= self.min_interval:
                self.last_process_time = current_time
                self.event_count += 1
                return True
        
        return False
    
    def get_sleep_time(self) -> float:
        """Get recommended sleep time before next processing attempt."""
        current_time = time.time()
        time_since_last = current_time - self.last_process_time
        
        if time_since_last < self.min_interval:
            return self.min_interval - time_since_last
        
        return 0.01  # Minimum sleep time


class EventProcessor:
    """Processes events from queue and dispatches to UI handlers."""
    
    def __init__(self, event_queue: EventQueue, max_events_per_second: int = 50):
        """
        Initialize event processor.
        
        Args:
            event_queue: Queue to process events from
            max_events_per_second: Maximum events to process per second
        """
        self.event_queue = event_queue
        self.throttler = EventThrottler(max_events_per_second)
        self.event_filter = EventFilter()
        
        # Performance optimizations
        self.update_throttler = UpdateThrottler(ThrottleConfig(
            max_updates_per_second=max_events_per_second,
            mode=ThrottleMode.ADAPTIVE
        ))
        
        self.batch_throttler = BatchUpdateThrottler(
            batch_size=10,
            batch_timeout_ms=50,
            max_batch_size=25
        )
        
        # Event handlers
        self._handlers: Dict[EventType, List[Callable[[BaseEvent], None]]] = {
            EventType.REQUEST: [],
            EventType.RESPONSE: [],
            EventType.ERROR: [],
            EventType.STATUS: [],
            EventType.PROXY_DECISION_UPDATE: []
        }
        
        # Processing control
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Batch processing setup
        self.batch_throttler.set_batch_processor(self._process_event_batch)
        
        # Statistics
        self._stats = {
            'events_processed': 0,
            'events_filtered': 0,
            'events_throttled': 0,
            'processing_errors': 0,
            'last_process_time': None
        }
    
    def add_handler(self, event_type: EventType, handler: Callable[[BaseEvent], None]):
        """
        Add event handler for specific event type.
        
        Args:
            event_type: Type of event to handle
            handler: Function to call when event occurs
        """
        if event_type in self._handlers:
            self._handlers[event_type].append(handler)
    
    def remove_handler(self, event_type: EventType, handler: Callable[[BaseEvent], None]):
        """
        Remove event handler.
        
        Args:
            event_type: Type of event
            handler: Handler function to remove
        """
        if event_type in self._handlers and handler in self._handlers[event_type]:
            self._handlers[event_type].remove(handler)
    
    def set_filter(self, event_filter: EventFilter):
        """Set event filter for processing."""
        self.event_filter = event_filter
    
    def start_processing(self):
        """Start event processing in background thread."""
        if self._running:
            return
        
        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._process_events, daemon=True)
        self._thread.start()
        
        # Start performance components
        self.update_throttler.start_throttling()
        self.batch_throttler.start_batching()
    
    def stop_processing(self):
        """Stop event processing."""
        if not self._running:
            return
        
        self._running = False
        self._stop_event.set()
        
        # Stop performance components
        self.update_throttler.stop_throttling()
        self.batch_throttler.stop_batching()
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
    
    def process_single_batch(self, max_events: int = 10) -> int:
        """
        Process a single batch of events (for manual processing).
        
        Args:
            max_events: Maximum events to process in batch
            
        Returns:
            Number of events processed
        """
        events = self.event_queue.get_events_batch(max_events, timeout=0.01)
        processed_count = 0
        
        # For batch processing, we allow processing all events in the batch
        # but still respect the overall rate limit
        for event in events:
            if self._process_single_event(event):
                processed_count += 1
            
            # Only check throttling if we've processed many events
            if processed_count >= self.throttler.max_events_per_second:
                break
        
        return processed_count
    
    def _process_events(self):
        """Main event processing loop (runs in background thread)."""
        while self._running and not self._stop_event.is_set():
            try:
                # Check throttling
                if not self.throttler.should_process():
                    sleep_time = self.throttler.get_sleep_time()
                    if self._stop_event.wait(sleep_time):
                        break
                    continue
                
                # Get events batch
                events = self.event_queue.get_events_batch(max_events=10, timeout=0.1)
                
                if not events:
                    continue
                
                # Process events - use batch processing for better performance
                if len(events) > 5:  # Use batch processing for larger event sets
                    self.batch_throttler.add_to_batch(events)
                else:
                    # Process individually for small sets
                    for event in events:
                        if not self._running:
                            break
                        
                        self._process_single_event(event)
                        
                        # Check throttling between events
                        if not self.throttler.should_process():
                            self._stats['events_throttled'] += 1
                            break
                
            except Exception as e:
                self._stats['processing_errors'] += 1
                # Log error but continue processing
                print(f"Error processing events: {e}")
                time.sleep(0.1)
    
    def _process_single_event(self, event: BaseEvent) -> bool:
        """
        Process a single event.
        
        Args:
            event: Event to process
            
        Returns:
            True if event was processed, False if filtered
        """
        try:
            # Apply filter
            if not self.event_filter.matches(event):
                self._stats['events_filtered'] += 1
                return False
            
            # Dispatch to handlers
            handlers = self._handlers.get(event.event_type, [])
            for handler in handlers:
                try:
                    handler(event)
                except Exception as e:
                    self._stats['processing_errors'] += 1
                    print(f"Error in event handler: {e}")
            
            self._stats['events_processed'] += 1
            self._stats['last_process_time'] = datetime.now()
            return True
            
        except Exception as e:
            self._stats['processing_errors'] += 1
            print(f"Error processing event: {e}")
            return False
    
    def get_stats(self) -> dict:
        """Get processing statistics."""
        queue_stats = self.event_queue.get_stats()
        return {
            **self._stats,
            'queue_stats': queue_stats,
            'is_running': self._running,
            'throttle_rate': self.throttler.max_events_per_second
        }
    
    def reset_stats(self):
        """Reset processing statistics."""
        self._stats = {
            'events_processed': 0,
            'events_filtered': 0,
            'events_throttled': 0,
            'processing_errors': 0,
            'last_process_time': None
        }
    
    def _process_event_batch(self, events: List[BaseEvent]):
        """
        Process a batch of events for improved performance.
        
        Args:
            events: List of events to process
        """
        try:
            # Group events by type for efficient processing
            events_by_type = {}
            for event in events:
                event_type = event.event_type
                if event_type not in events_by_type:
                    events_by_type[event_type] = []
                events_by_type[event_type].append(event)
            
            # Process each type in batch
            for event_type, type_events in events_by_type.items():
                handlers = self._handlers.get(event_type, [])
                
                for handler in handlers:
                    try:
                        # Check if handler supports batch processing
                        if hasattr(handler, 'handle_batch'):
                            handler.handle_batch(type_events)
                        else:
                            # Process individually
                            for event in type_events:
                                handler(event)
                    except Exception as e:
                        self._stats['processing_errors'] += 1
                        print(f"Error in batch event handler: {e}")
            
            self._stats['events_processed'] += len(events)
            self._stats['last_process_time'] = datetime.now()
            
        except Exception as e:
            self._stats['processing_errors'] += 1
            print(f"Error processing event batch: {e}")
    
    def enable_batch_processing(self, enable: bool = True):
        """Enable or disable batch processing for better performance."""
        if enable:
            self.batch_throttler.start_batching()
        else:
            self.batch_throttler.stop_batching()
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics including throttling info."""
        base_stats = self.get_stats()
        
        # Add throttling stats
        throttle_stats = self.update_throttler.get_stats()
        batch_stats = self.batch_throttler.get_batch_stats()
        
        return {
            **base_stats,
            'throttling': {
                'total_requests': throttle_stats.total_requests,
                'throttled_requests': throttle_stats.throttled_requests,
                'current_rate': throttle_stats.current_rate,
                'burst_events': throttle_stats.burst_events
            },
            'batching': batch_stats
        }