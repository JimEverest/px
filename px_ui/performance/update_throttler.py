"""
Update throttling to limit UI refresh frequency during high traffic.

This module provides update throttling capabilities to prevent UI overload
during high traffic periods while maintaining responsiveness.
"""

import threading
import time
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from collections import deque


class ThrottleMode(Enum):
    """Throttling modes."""
    FIXED_RATE = "fixed"
    ADAPTIVE = "adaptive"
    BURST_CONTROL = "burst"


@dataclass
class ThrottleConfig:
    """Configuration for update throttling."""
    mode: ThrottleMode = ThrottleMode.ADAPTIVE
    max_updates_per_second: int = 30
    min_update_interval_ms: int = 33  # ~30 FPS
    burst_threshold: int = 100  # Events that trigger burst mode
    burst_cooldown_ms: int = 1000  # Cooldown after burst
    adaptive_factor: float = 0.8  # Factor for adaptive throttling


@dataclass
class ThrottleStats:
    """Throttling statistics."""
    total_requests: int
    throttled_requests: int
    processed_requests: int
    current_rate: float
    average_rate: float
    burst_events: int
    last_update: Optional[datetime]


class UpdateThrottler:
    """
    Throttles UI updates to prevent overload during high traffic.
    
    Supports multiple throttling modes including fixed rate, adaptive,
    and burst control to maintain UI responsiveness.
    """
    
    def __init__(self, config: Optional[ThrottleConfig] = None):
        """
        Initialize update throttler.
        
        Args:
            config: Throttling configuration
        """
        self.config = config or ThrottleConfig()
        
        # Statistics
        self.stats = ThrottleStats(0, 0, 0, 0.0, 0.0, 0, None)
        
        # Throttling state
        self._lock = threading.RLock()
        self._last_update_time = 0.0
        self._update_history = deque(maxlen=100)  # Track recent updates
        self._burst_start_time = 0.0
        self._in_burst_mode = False
        
        # Pending updates queue
        self._pending_updates: List[Callable] = []
        self._update_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Adaptive throttling state
        self._adaptive_interval = self.config.min_update_interval_ms / 1000.0
        self._load_history = deque(maxlen=20)
        
    def start_throttling(self):
        """Start background update processing."""
        if self._update_thread and self._update_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._update_thread = threading.Thread(
            target=self._update_loop,
            name="UpdateThrottler",
            daemon=True
        )
        self._update_thread.start()
    
    def stop_throttling(self):
        """Stop background update processing."""
        self._stop_event.set()
        
        if self._update_thread and self._update_thread.is_alive():
            self._update_thread.join(timeout=1.0)
    
    def request_update(self, update_func: Callable, priority: int = 0) -> bool:
        """
        Request a UI update with throttling.
        
        Args:
            update_func: Function to call for update
            priority: Update priority (higher = more important)
            
        Returns:
            True if update was accepted, False if throttled
        """
        current_time = time.time()
        
        with self._lock:
            self.stats.total_requests += 1
            
            # Check if we should throttle this update
            if self._should_throttle(current_time):
                self.stats.throttled_requests += 1
                return False
            
            # Add to pending updates
            self._pending_updates.append((update_func, priority, current_time))
            
            # Sort by priority (higher priority first)
            self._pending_updates.sort(key=lambda x: x[1], reverse=True)
            
            # Limit pending updates to prevent memory issues
            if len(self._pending_updates) > 50:
                # Remove lowest priority updates
                self._pending_updates = self._pending_updates[:50]
            
            self.stats.processed_requests += 1
            return True
    
    def force_update(self, update_func: Callable):
        """
        Force an immediate update bypassing throttling.
        
        Args:
            update_func: Function to call for update
        """
        try:
            update_func()
            with self._lock:
                self._record_update(time.time())
        except Exception as e:
            print(f"Error in forced update: {e}")
    
    def get_stats(self) -> ThrottleStats:
        """Get current throttling statistics."""
        with self._lock:
            # Calculate current rate
            current_time = time.time()
            recent_updates = [t for t in self._update_history 
                            if current_time - t < 1.0]
            self.stats.current_rate = len(recent_updates)
            
            # Calculate average rate
            if self._update_history:
                time_span = current_time - self._update_history[0]
                if time_span > 0:
                    self.stats.average_rate = len(self._update_history) / time_span
            
            return self.stats
    
    def adjust_throttling(self, load_factor: float):
        """
        Adjust throttling based on system load.
        
        Args:
            load_factor: System load factor (0.0 to 1.0)
        """
        with self._lock:
            self._load_history.append(load_factor)
            
            if self.config.mode == ThrottleMode.ADAPTIVE:
                # Adjust adaptive interval based on load
                avg_load = sum(self._load_history) / len(self._load_history)
                
                if avg_load > 0.8:  # High load
                    self._adaptive_interval = min(
                        self._adaptive_interval * 1.2,
                        0.5  # Max 2 updates per second under high load
                    )
                elif avg_load < 0.3:  # Low load
                    self._adaptive_interval = max(
                        self._adaptive_interval * 0.9,
                        self.config.min_update_interval_ms / 1000.0
                    )
    
    def clear_pending_updates(self):
        """Clear all pending updates."""
        with self._lock:
            self._pending_updates.clear()
    
    def get_pending_count(self) -> int:
        """Get number of pending updates."""
        with self._lock:
            return len(self._pending_updates)
    
    def _should_throttle(self, current_time: float) -> bool:
        """Check if update should be throttled."""
        # Check minimum interval
        time_since_last = current_time - self._last_update_time
        min_interval = self._get_current_min_interval()
        
        if time_since_last < min_interval:
            return True
        
        # Check burst mode
        if self._check_burst_mode(current_time):
            return True
        
        # Check rate limit
        recent_updates = [t for t in self._update_history 
                         if current_time - t < 1.0]
        if len(recent_updates) >= self.config.max_updates_per_second:
            return True
        
        return False
    
    def _get_current_min_interval(self) -> float:
        """Get current minimum interval based on throttling mode."""
        if self.config.mode == ThrottleMode.FIXED_RATE:
            return self.config.min_update_interval_ms / 1000.0
        
        elif self.config.mode == ThrottleMode.ADAPTIVE:
            return self._adaptive_interval
        
        elif self.config.mode == ThrottleMode.BURST_CONTROL:
            if self._in_burst_mode:
                return (self.config.min_update_interval_ms * 2) / 1000.0
            else:
                return self.config.min_update_interval_ms / 1000.0
        
        return self.config.min_update_interval_ms / 1000.0
    
    def _check_burst_mode(self, current_time: float) -> bool:
        """Check and manage burst mode."""
        # Count recent requests
        recent_requests = sum(1 for _, _, t in self._pending_updates 
                            if current_time - t < 1.0)
        
        if recent_requests >= self.config.burst_threshold:
            if not self._in_burst_mode:
                self._in_burst_mode = True
                self._burst_start_time = current_time
                self.stats.burst_events += 1
        
        # Check burst cooldown
        if self._in_burst_mode:
            if current_time - self._burst_start_time > (self.config.burst_cooldown_ms / 1000.0):
                self._in_burst_mode = False
        
        return self._in_burst_mode
    
    def _record_update(self, update_time: float):
        """Record an update in history."""
        self._last_update_time = update_time
        self._update_history.append(update_time)
        self.stats.last_update = datetime.fromtimestamp(update_time)
    
    def _update_loop(self):
        """Background update processing loop."""
        while not self._stop_event.is_set():
            try:
                current_time = time.time()
                updates_to_process = []
                
                with self._lock:
                    if self._pending_updates and not self._should_throttle(current_time):
                        # Get next update to process
                        update_func, priority, request_time = self._pending_updates.pop(0)
                        updates_to_process.append(update_func)
                        self._record_update(current_time)
                
                # Process updates outside of lock
                for update_func in updates_to_process:
                    try:
                        update_func()
                    except Exception as e:
                        print(f"Error processing throttled update: {e}")
                
                # Sleep for minimum interval
                sleep_time = self._get_current_min_interval()
                if self._stop_event.wait(sleep_time):
                    break
                
            except Exception as e:
                print(f"Error in update throttling loop: {e}")
                time.sleep(0.1)
    
    def reset_stats(self):
        """Reset throttling statistics."""
        with self._lock:
            self.stats = ThrottleStats(0, 0, 0, 0.0, 0.0, 0, None)
            self._update_history.clear()
            self._load_history.clear()


class BatchUpdateThrottler:
    """
    Specialized throttler for batch updates.
    
    Collects multiple updates and processes them in batches
    to improve performance during high traffic.
    """
    
    def __init__(self, 
                 batch_size: int = 10,
                 batch_timeout_ms: int = 100,
                 max_batch_size: int = 50):
        """
        Initialize batch update throttler.
        
        Args:
            batch_size: Target batch size
            batch_timeout_ms: Maximum time to wait for batch
            max_batch_size: Maximum batch size
        """
        self.batch_size = batch_size
        self.batch_timeout_ms = batch_timeout_ms
        self.max_batch_size = max_batch_size
        
        self._lock = threading.RLock()
        self._batch_queue: List[Any] = []
        self._batch_processor: Optional[Callable[[List[Any]], None]] = None
        self._last_batch_time = time.time()
        
        self._batch_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    def set_batch_processor(self, processor: Callable[[List[Any]], None]):
        """Set the function to process batches."""
        self._batch_processor = processor
    
    def start_batching(self):
        """Start batch processing."""
        if self._batch_thread and self._batch_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._batch_thread = threading.Thread(
            target=self._batch_loop,
            name="BatchUpdateThrottler",
            daemon=True
        )
        self._batch_thread.start()
    
    def stop_batching(self):
        """Stop batch processing."""
        self._stop_event.set()
        
        if self._batch_thread and self._batch_thread.is_alive():
            self._batch_thread.join(timeout=1.0)
    
    def add_to_batch(self, item: Any):
        """Add item to current batch."""
        with self._lock:
            self._batch_queue.append(item)
            
            # Process batch if it's full
            if len(self._batch_queue) >= self.max_batch_size:
                self._process_current_batch()
    
    def force_batch_processing(self):
        """Force processing of current batch."""
        with self._lock:
            if self._batch_queue:
                self._process_current_batch()
    
    def _batch_loop(self):
        """Background batch processing loop."""
        while not self._stop_event.wait(self.batch_timeout_ms / 1000.0):
            try:
                current_time = time.time()
                should_process = False
                
                with self._lock:
                    # Check if batch should be processed
                    if self._batch_queue:
                        time_since_last = current_time - self._last_batch_time
                        if (len(self._batch_queue) >= self.batch_size or
                            time_since_last >= (self.batch_timeout_ms / 1000.0)):
                            should_process = True
                
                if should_process:
                    self._process_current_batch()
                
            except Exception as e:
                print(f"Error in batch processing loop: {e}")
    
    def _process_current_batch(self):
        """Process the current batch."""
        if not self._batch_processor:
            return
        
        batch_to_process = []
        
        with self._lock:
            if self._batch_queue:
                batch_to_process = self._batch_queue.copy()
                self._batch_queue.clear()
                self._last_batch_time = time.time()
        
        if batch_to_process:
            try:
                self._batch_processor(batch_to_process)
            except Exception as e:
                print(f"Error processing batch: {e}")
    
    def get_batch_stats(self) -> Dict:
        """Get batch processing statistics."""
        with self._lock:
            return {
                'queue_size': len(self._batch_queue),
                'batch_size': self.batch_size,
                'max_batch_size': self.max_batch_size,
                'timeout_ms': self.batch_timeout_ms
            }