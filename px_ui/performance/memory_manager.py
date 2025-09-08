"""
Memory management for monitoring data and response bodies.

This module provides memory management capabilities including automatic cleanup
of old monitoring data, response body truncation, and memory usage monitoring.
"""

import threading
import time
import gc
import psutil
import os
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from collections import deque


@dataclass
class MemoryStats:
    """Memory usage statistics."""
    total_memory_mb: float
    used_memory_mb: float
    available_memory_mb: float
    memory_percent: float
    process_memory_mb: float
    entries_count: int
    truncated_bodies: int


class MemoryManager:
    """
    Manages memory usage for monitoring data and response bodies.
    
    Provides automatic cleanup of old data, response body truncation,
    and memory usage monitoring with configurable limits.
    """
    
    def __init__(self, 
                 max_entries: int = 1000,
                 max_memory_mb: int = 500,
                 max_body_size: int = 10240,  # 10KB
                 cleanup_interval: int = 60,  # seconds
                 memory_check_interval: int = 30):  # seconds
        """
        Initialize memory manager.
        
        Args:
            max_entries: Maximum number of monitoring entries to keep
            max_memory_mb: Maximum memory usage in MB before cleanup
            max_body_size: Maximum response body size to store (bytes)
            cleanup_interval: Interval between cleanup operations (seconds)
            memory_check_interval: Interval between memory checks (seconds)
        """
        self.max_entries = max_entries
        self.max_memory_mb = max_memory_mb
        self.max_body_size = max_body_size
        self.cleanup_interval = cleanup_interval
        self.memory_check_interval = memory_check_interval
        
        # Statistics
        self.stats = MemoryStats(0, 0, 0, 0, 0, 0, 0)
        self.truncated_bodies = 0
        
        # Cleanup control
        self._cleanup_thread: Optional[threading.Thread] = None
        self._memory_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        
        # Callbacks for cleanup operations
        self._cleanup_callbacks: List[Callable[[int], None]] = []
        self._memory_warning_callbacks: List[Callable[[MemoryStats], None]] = []
        
        # Recent cleanup history for adaptive behavior
        self._cleanup_history = deque(maxlen=10)
        
    def start_monitoring(self):
        """Start background memory monitoring and cleanup."""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        
        self._stop_event.clear()
        
        # Start cleanup thread
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name="MemoryManager-Cleanup",
            daemon=True
        )
        self._cleanup_thread.start()
        
        # Start memory monitoring thread
        self._memory_thread = threading.Thread(
            target=self._memory_monitor_loop,
            name="MemoryManager-Monitor", 
            daemon=True
        )
        self._memory_thread.start()
    
    def stop_monitoring(self):
        """Stop background monitoring."""
        self._stop_event.set()
        
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=2.0)
        
        if self._memory_thread and self._memory_thread.is_alive():
            self._memory_thread.join(timeout=2.0)
    
    def add_cleanup_callback(self, callback: Callable[[int], None]):
        """
        Add callback for cleanup operations.
        
        Args:
            callback: Function called with number of entries to remove
        """
        with self._lock:
            self._cleanup_callbacks.append(callback)
    
    def add_memory_warning_callback(self, callback: Callable[[MemoryStats], None]):
        """
        Add callback for memory warnings.
        
        Args:
            callback: Function called when memory usage is high
        """
        with self._lock:
            self._memory_warning_callbacks.append(callback)
    
    def truncate_response_body(self, body: str, content_type: str = "") -> str:
        """
        Truncate response body to manageable size.
        
        Args:
            body: Original response body
            content_type: Content type of response
            
        Returns:
            Truncated body with truncation indicator if needed
        """
        if not body:
            return body
        
        # Convert to bytes to get accurate size
        body_bytes = body.encode('utf-8', errors='ignore')
        
        if len(body_bytes) <= self.max_body_size:
            return body
        
        # Truncate and add indicator
        truncated_bytes = body_bytes[:self.max_body_size]
        truncated_text = truncated_bytes.decode('utf-8', errors='ignore')
        
        # Add truncation indicator
        truncation_msg = f"\n\n[TRUNCATED: Original size {len(body_bytes)} bytes, showing first {len(truncated_bytes)} bytes]"
        
        with self._lock:
            self.truncated_bodies += 1
        
        return truncated_text + truncation_msg
    
    def should_cleanup(self, current_entries: int) -> bool:
        """
        Check if cleanup should be performed based on current state.
        
        Args:
            current_entries: Current number of entries
            
        Returns:
            True if cleanup should be performed
        """
        # Check entry count limit
        if current_entries > self.max_entries:
            return True
        
        # Check memory usage
        memory_stats = self._get_memory_stats(current_entries)
        if memory_stats.process_memory_mb > self.max_memory_mb:
            return True
        
        # Check system memory pressure
        if memory_stats.memory_percent > 85:  # System memory usage > 85%
            return True
        
        return False
    
    def calculate_cleanup_amount(self, current_entries: int) -> int:
        """
        Calculate how many entries should be removed during cleanup.
        
        Args:
            current_entries: Current number of entries
            
        Returns:
            Number of entries to remove
        """
        if current_entries <= self.max_entries:
            return 0
        
        # Base cleanup: remove excess entries plus buffer
        base_cleanup = current_entries - self.max_entries
        buffer_cleanup = max(50, int(self.max_entries * 0.1))  # 10% buffer
        
        # Adaptive cleanup based on memory pressure
        memory_stats = self._get_memory_stats(current_entries)
        
        if memory_stats.process_memory_mb > self.max_memory_mb * 1.5:
            # High memory pressure - aggressive cleanup
            return min(current_entries // 2, base_cleanup + buffer_cleanup * 3)
        elif memory_stats.process_memory_mb > self.max_memory_mb:
            # Medium memory pressure - moderate cleanup
            return base_cleanup + buffer_cleanup * 2
        else:
            # Normal cleanup
            return base_cleanup + buffer_cleanup
    
    def force_cleanup(self, entries_to_remove: int):
        """
        Force immediate cleanup operation.
        
        Args:
            entries_to_remove: Number of entries to remove
        """
        with self._lock:
            for callback in self._cleanup_callbacks:
                try:
                    callback(entries_to_remove)
                except Exception as e:
                    print(f"Error in cleanup callback: {e}")
            
            # Record cleanup operation
            self._cleanup_history.append({
                'timestamp': datetime.now(),
                'entries_removed': entries_to_remove,
                'memory_before': self._get_process_memory_mb()
            })
        
        # Force garbage collection after cleanup
        gc.collect()
    
    def get_memory_stats(self, current_entries: int = 0) -> MemoryStats:
        """Get current memory statistics."""
        return self._get_memory_stats(current_entries)
    
    def _cleanup_loop(self):
        """Background cleanup loop."""
        while not self._stop_event.wait(self.cleanup_interval):
            try:
                # Check if cleanup is needed
                current_entries = self._get_current_entries_count()
                
                if self.should_cleanup(current_entries):
                    cleanup_amount = self.calculate_cleanup_amount(current_entries)
                    if cleanup_amount > 0:
                        self.force_cleanup(cleanup_amount)
                
            except Exception as e:
                print(f"Error in cleanup loop: {e}")
    
    def _memory_monitor_loop(self):
        """Background memory monitoring loop."""
        while not self._stop_event.wait(self.memory_check_interval):
            try:
                current_entries = self._get_current_entries_count()
                memory_stats = self._get_memory_stats(current_entries)
                
                # Update stored stats
                with self._lock:
                    self.stats = memory_stats
                
                # Check for memory warnings
                if (memory_stats.process_memory_mb > self.max_memory_mb * 0.8 or
                    memory_stats.memory_percent > 80):
                    
                    with self._lock:
                        for callback in self._memory_warning_callbacks:
                            try:
                                callback(memory_stats)
                            except Exception as e:
                                print(f"Error in memory warning callback: {e}")
                
            except Exception as e:
                print(f"Error in memory monitor loop: {e}")
    
    def _get_memory_stats(self, current_entries: int) -> MemoryStats:
        """Get current memory statistics."""
        try:
            # System memory
            memory = psutil.virtual_memory()
            
            # Process memory
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info()
            
            return MemoryStats(
                total_memory_mb=memory.total / (1024 * 1024),
                used_memory_mb=memory.used / (1024 * 1024),
                available_memory_mb=memory.available / (1024 * 1024),
                memory_percent=memory.percent,
                process_memory_mb=process_memory.rss / (1024 * 1024),
                entries_count=current_entries,
                truncated_bodies=self.truncated_bodies
            )
        except Exception:
            # Fallback if psutil fails
            return MemoryStats(0, 0, 0, 0, 0, current_entries, self.truncated_bodies)
    
    def _get_process_memory_mb(self) -> float:
        """Get current process memory usage in MB."""
        try:
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / (1024 * 1024)
        except Exception:
            return 0.0
    
    def _get_current_entries_count(self) -> int:
        """Get current entries count from callbacks."""
        # This will be set by the monitoring view or other components
        with self._lock:
            return self.stats.entries_count
    
    def update_entries_count(self, count: int):
        """Update the current entries count."""
        with self._lock:
            self.stats.entries_count = count
    
    def get_cleanup_history(self) -> List[Dict]:
        """Get recent cleanup history."""
        with self._lock:
            return list(self._cleanup_history)
    
    def reset_stats(self):
        """Reset statistics counters."""
        with self._lock:
            self.truncated_bodies = 0
            self._cleanup_history.clear()