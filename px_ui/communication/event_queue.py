"""
Thread-safe event queue for proxy-to-UI communication.

This module provides a thread-safe queue implementation for handling events
between the proxy engine and UI components.
"""

import queue
import threading
import time
from typing import Optional, List, Callable
from datetime import datetime, timedelta

from .events import BaseEvent, EventType


class EventQueue:
    """Thread-safe event queue for proxy-to-UI communication."""
    
    def __init__(self, max_size: int = 1000):
        """
        Initialize the event queue.
        
        Args:
            max_size: Maximum number of events to store in queue
        """
        self._queue = queue.Queue(maxsize=max_size)
        self._lock = threading.RLock()
        self._event_count = 0
        self._dropped_events = 0
        self._last_cleanup = datetime.now()
        
    def put_event(self, event: BaseEvent, block: bool = False, timeout: Optional[float] = None) -> bool:
        """
        Put an event into the queue.
        
        Args:
            event: Event to add to queue
            block: Whether to block if queue is full
            timeout: Timeout for blocking operation
            
        Returns:
            True if event was added, False if queue was full
        """
        try:
            with self._lock:
                self._queue.put(event, block=block, timeout=timeout)
                self._event_count += 1
                return True
        except queue.Full:
            with self._lock:
                self._dropped_events += 1
            return False
    
    def get_event(self, block: bool = True, timeout: Optional[float] = None) -> Optional[BaseEvent]:
        """
        Get an event from the queue.
        
        Args:
            block: Whether to block if queue is empty
            timeout: Timeout for blocking operation
            
        Returns:
            Event from queue or None if empty/timeout
        """
        try:
            return self._queue.get(block=block, timeout=timeout)
        except queue.Empty:
            return None
    
    def get_events_batch(self, max_events: int = 10, timeout: float = 0.1) -> List[BaseEvent]:
        """
        Get multiple events from queue in a batch.
        
        Args:
            max_events: Maximum number of events to retrieve
            timeout: Timeout for first event
            
        Returns:
            List of events (may be empty)
        """
        events = []
        
        # Get first event with timeout
        first_event = self.get_event(block=True, timeout=timeout)
        if first_event:
            events.append(first_event)
            
            # Get additional events without blocking
            for _ in range(max_events - 1):
                event = self.get_event(block=False)
                if event:
                    events.append(event)
                else:
                    break
        
        return events
    
    def size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()
    
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return self._queue.empty()
    
    def is_full(self) -> bool:
        """Check if queue is full."""
        return self._queue.full()
    
    def clear(self):
        """Clear all events from queue."""
        with self._lock:
            while not self._queue.empty():
                try:
                    self._queue.get_nowait()
                except queue.Empty:
                    break
    
    def get_stats(self) -> dict:
        """Get queue statistics."""
        with self._lock:
            return {
                'current_size': self.size(),
                'total_events': self._event_count,
                'dropped_events': self._dropped_events,
                'is_full': self.is_full(),
                'is_empty': self.is_empty()
            }


class EventFilter:
    """Filter for events based on various criteria."""
    
    def __init__(self):
        self.event_types: Optional[List[EventType]] = None
        self.url_patterns: Optional[List[str]] = None
        self.status_codes: Optional[List[int]] = None
        self.proxy_types: Optional[List[str]] = None
        self.time_range: Optional[tuple] = None
        
    def set_event_types(self, event_types: List[EventType]):
        """Set event types to filter."""
        self.event_types = event_types
    
    def set_url_patterns(self, patterns: List[str]):
        """Set URL patterns to filter (supports wildcards)."""
        self.url_patterns = patterns
    
    def set_status_codes(self, codes: List[int]):
        """Set HTTP status codes to filter."""
        self.status_codes = codes
    
    def set_proxy_types(self, proxy_types: List[str]):
        """Set proxy types to filter (DIRECT, PROXY)."""
        self.proxy_types = proxy_types
    
    def set_time_range(self, start_time: datetime, end_time: datetime):
        """Set time range to filter events."""
        self.time_range = (start_time, end_time)
    
    def matches(self, event: BaseEvent) -> bool:
        """
        Check if event matches filter criteria.
        
        Args:
            event: Event to check
            
        Returns:
            True if event matches all filter criteria
        """
        # Check event type
        if self.event_types and event.event_type not in self.event_types:
            return False
        
        # Check time range
        if self.time_range:
            start_time, end_time = self.time_range
            if not (start_time <= event.timestamp <= end_time):
                return False
        
        # Check URL patterns for request/response events
        if self.url_patterns:
            if hasattr(event, 'url'):
                url = getattr(event, 'url', '')
                if not any(self._match_pattern(pattern, url) for pattern in self.url_patterns):
                    return False
            else:
                # If event doesn't have URL but we're filtering by URL, exclude it
                return False
        
        # Check status codes for response events
        if self.status_codes:
            if hasattr(event, 'status_code'):
                if event.status_code not in self.status_codes:
                    return False
            else:
                # If event doesn't have status_code but we're filtering by status, exclude it
                return False
        
        # Check proxy types for request events
        if self.proxy_types:
            if hasattr(event, 'proxy_decision'):
                proxy_decision = getattr(event, 'proxy_decision', '')
                proxy_type = 'DIRECT' if proxy_decision == 'DIRECT' else 'PROXY'
                if proxy_type not in self.proxy_types:
                    return False
            else:
                # If event doesn't have proxy_decision but we're filtering by proxy type, exclude it
                return False
        
        return True
    
    def _match_pattern(self, pattern: str, text: str) -> bool:
        """Simple wildcard pattern matching."""
        import fnmatch
        return fnmatch.fnmatch(text.lower(), pattern.lower())
    
    def clear(self):
        """Clear all filter criteria."""
        self.event_types = None
        self.url_patterns = None
        self.status_codes = None
        self.proxy_types = None
        self.time_range = None