"""
Resource cleanup for threads and connections.

This module provides resource cleanup capabilities for proper management
of threads, connections, and other system resources.
"""

import threading
import time
import weakref
import gc
from typing import Dict, List, Optional, Set, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
import socket
import queue


class ResourceType(Enum):
    """Types of resources to manage."""
    THREAD = "thread"
    CONNECTION = "connection"
    QUEUE = "queue"
    FILE_HANDLE = "file_handle"
    TIMER = "timer"
    CALLBACK = "callback"


@dataclass
class ResourceInfo:
    """Information about a managed resource."""
    resource_id: str
    resource_type: ResourceType
    resource: Any
    created_at: datetime
    last_accessed: datetime
    cleanup_func: Optional[Callable] = None
    metadata: Dict[str, Any] = None


@dataclass
class CleanupStats:
    """Resource cleanup statistics."""
    total_resources: int
    active_resources: int
    cleaned_resources: int
    failed_cleanups: int
    threads_cleaned: int
    connections_cleaned: int
    memory_freed_mb: float
    last_cleanup: Optional[datetime]


class ResourceCleaner:
    """
    Manages cleanup of threads, connections, and other system resources.
    
    Provides automatic cleanup of resources with configurable policies
    and manual cleanup capabilities.
    """
    
    def __init__(self, 
                 cleanup_interval: int = 300,  # 5 minutes
                 resource_timeout: int = 3600,  # 1 hour
                 max_resources: int = 100):
        """
        Initialize resource cleaner.
        
        Args:
            cleanup_interval: Interval between cleanup runs (seconds)
            resource_timeout: Timeout for unused resources (seconds)
            max_resources: Maximum number of resources to track
        """
        self.cleanup_interval = cleanup_interval
        self.resource_timeout = resource_timeout
        self.max_resources = max_resources
        
        # Resource tracking
        self._resources: Dict[str, ResourceInfo] = {}
        self._lock = threading.RLock()
        
        # Statistics
        self.stats = CleanupStats(0, 0, 0, 0, 0, 0, 0.0, None)
        
        # Cleanup control
        self._cleanup_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        
        # Cleanup callbacks
        self._cleanup_callbacks: List[Callable[[ResourceInfo], None]] = []
        
        # Weak references to avoid circular references
        self._weak_refs: Set[weakref.ref] = set()
    
    def start_cleanup(self):
        """Start background resource cleanup."""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        
        self._stop_event.clear()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name="ResourceCleaner",
            daemon=True
        )
        self._cleanup_thread.start()
    
    def stop_cleanup(self):
        """Stop background resource cleanup."""
        self._stop_event.set()
        
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=2.0)
        
        # Perform final cleanup
        self.cleanup_all_resources()
    
    def register_resource(self, 
                         resource_id: str,
                         resource_type: ResourceType,
                         resource: Any,
                         cleanup_func: Optional[Callable] = None,
                         metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Register a resource for cleanup management.
        
        Args:
            resource_id: Unique identifier for the resource
            resource_type: Type of resource
            resource: The actual resource object
            cleanup_func: Custom cleanup function
            metadata: Additional metadata about the resource
            
        Returns:
            True if resource was registered successfully
        """
        with self._lock:
            # Check resource limit
            if len(self._resources) >= self.max_resources:
                # Remove oldest resource
                oldest_id = min(self._resources.keys(), 
                              key=lambda k: self._resources[k].created_at)
                self.unregister_resource(oldest_id)
            
            # Create resource info
            resource_info = ResourceInfo(
                resource_id=resource_id,
                resource_type=resource_type,
                resource=resource,
                created_at=datetime.now(),
                last_accessed=datetime.now(),
                cleanup_func=cleanup_func,
                metadata=metadata or {}
            )
            
            self._resources[resource_id] = resource_info
            self.stats.total_resources += 1
            self.stats.active_resources += 1
            
            # Create weak reference if possible
            try:
                weak_ref = weakref.ref(resource, self._on_resource_deleted)
                self._weak_refs.add(weak_ref)
            except TypeError:
                # Some objects don't support weak references
                pass
            
            return True
    
    def unregister_resource(self, resource_id: str) -> bool:
        """
        Unregister and cleanup a resource.
        
        Args:
            resource_id: ID of resource to unregister
            
        Returns:
            True if resource was found and cleaned up
        """
        with self._lock:
            if resource_id not in self._resources:
                return False
            
            resource_info = self._resources[resource_id]
            success = self._cleanup_resource(resource_info)
            
            del self._resources[resource_id]
            self.stats.active_resources -= 1
            
            if success:
                self.stats.cleaned_resources += 1
            else:
                self.stats.failed_cleanups += 1
            
            return success
    
    def access_resource(self, resource_id: str):
        """
        Mark a resource as accessed (updates last_accessed time).
        
        Args:
            resource_id: ID of resource that was accessed
        """
        with self._lock:
            if resource_id in self._resources:
                self._resources[resource_id].last_accessed = datetime.now()
    
    def cleanup_expired_resources(self) -> int:
        """
        Clean up resources that have expired.
        
        Returns:
            Number of resources cleaned up
        """
        cleaned_count = 0
        current_time = datetime.now()
        timeout_delta = timedelta(seconds=self.resource_timeout)
        
        with self._lock:
            expired_ids = []
            
            for resource_id, resource_info in self._resources.items():
                if current_time - resource_info.last_accessed > timeout_delta:
                    expired_ids.append(resource_id)
            
            for resource_id in expired_ids:
                if self.unregister_resource(resource_id):
                    cleaned_count += 1
        
        return cleaned_count
    
    def cleanup_all_resources(self) -> int:
        """
        Clean up all registered resources.
        
        Returns:
            Number of resources cleaned up
        """
        cleaned_count = 0
        
        with self._lock:
            resource_ids = list(self._resources.keys())
            
            for resource_id in resource_ids:
                if self.unregister_resource(resource_id):
                    cleaned_count += 1
        
        return cleaned_count
    
    def cleanup_by_type(self, resource_type: ResourceType) -> int:
        """
        Clean up all resources of a specific type.
        
        Args:
            resource_type: Type of resources to clean up
            
        Returns:
            Number of resources cleaned up
        """
        cleaned_count = 0
        
        with self._lock:
            resource_ids = [
                rid for rid, info in self._resources.items()
                if info.resource_type == resource_type
            ]
            
            for resource_id in resource_ids:
                if self.unregister_resource(resource_id):
                    cleaned_count += 1
        
        return cleaned_count
    
    def get_resource_info(self, resource_id: str) -> Optional[ResourceInfo]:
        """Get information about a specific resource."""
        with self._lock:
            return self._resources.get(resource_id)
    
    def get_resources_by_type(self, resource_type: ResourceType) -> List[ResourceInfo]:
        """Get all resources of a specific type."""
        with self._lock:
            return [
                info for info in self._resources.values()
                if info.resource_type == resource_type
            ]
    
    def get_stats(self) -> CleanupStats:
        """Get current cleanup statistics."""
        with self._lock:
            self.stats.active_resources = len(self._resources)
            return self.stats
    
    def add_cleanup_callback(self, callback: Callable[[ResourceInfo], None]):
        """Add callback for cleanup events."""
        with self._lock:
            self._cleanup_callbacks.append(callback)
    
    def force_garbage_collection(self):
        """Force garbage collection and update memory stats."""
        import psutil
        import os
        
        # Get memory before GC
        try:
            process = psutil.Process(os.getpid())
            memory_before = process.memory_info().rss / (1024 * 1024)
        except:
            memory_before = 0
        
        # Force garbage collection
        collected = gc.collect()
        
        # Get memory after GC
        try:
            memory_after = process.memory_info().rss / (1024 * 1024)
            memory_freed = max(0, memory_before - memory_after)
            self.stats.memory_freed_mb += memory_freed
        except:
            pass
        
        return collected
    
    def _cleanup_resource(self, resource_info: ResourceInfo) -> bool:
        """
        Clean up a specific resource.
        
        Args:
            resource_info: Information about resource to clean up
            
        Returns:
            True if cleanup was successful
        """
        try:
            # Call custom cleanup function if provided
            if resource_info.cleanup_func:
                resource_info.cleanup_func()
                return True
            
            # Default cleanup based on resource type
            if resource_info.resource_type == ResourceType.THREAD:
                return self._cleanup_thread_resource(resource_info.resource)
            
            elif resource_info.resource_type == ResourceType.CONNECTION:
                return self._cleanup_connection_resource(resource_info.resource)
            
            elif resource_info.resource_type == ResourceType.QUEUE:
                return self._cleanup_queue_resource(resource_info.resource)
            
            elif resource_info.resource_type == ResourceType.FILE_HANDLE:
                return self._cleanup_file_resource(resource_info.resource)
            
            elif resource_info.resource_type == ResourceType.TIMER:
                return self._cleanup_timer_resource(resource_info.resource)
            
            # Notify callbacks
            for callback in self._cleanup_callbacks:
                try:
                    callback(resource_info)
                except Exception as e:
                    print(f"Error in cleanup callback: {e}")
            
            return True
            
        except Exception as e:
            print(f"Error cleaning up resource {resource_info.resource_id}: {e}")
            return False
    
    def _cleanup_thread_resource(self, thread: threading.Thread) -> bool:
        """Clean up a thread resource."""
        try:
            if thread.is_alive():
                # For daemon threads, we can't force stop them
                # Just mark for cleanup and let them finish naturally
                if not thread.daemon:
                    # Non-daemon threads should be joined with timeout
                    thread.join(timeout=1.0)
            
            self.stats.threads_cleaned += 1
            return True
            
        except Exception as e:
            print(f"Error cleaning up thread: {e}")
            return False
    
    def _cleanup_connection_resource(self, connection) -> bool:
        """Clean up a connection resource."""
        try:
            if hasattr(connection, 'close'):
                connection.close()
            elif hasattr(connection, 'shutdown'):
                if isinstance(connection, socket.socket):
                    connection.shutdown(socket.SHUT_RDWR)
                connection.close()
            
            self.stats.connections_cleaned += 1
            return True
            
        except Exception as e:
            print(f"Error cleaning up connection: {e}")
            return False
    
    def _cleanup_queue_resource(self, queue_obj) -> bool:
        """Clean up a queue resource."""
        try:
            if hasattr(queue_obj, 'empty'):
                # Clear the queue
                while not queue_obj.empty():
                    try:
                        queue_obj.get_nowait()
                    except queue.Empty:
                        break
            
            return True
            
        except Exception as e:
            print(f"Error cleaning up queue: {e}")
            return False
    
    def _cleanup_file_resource(self, file_handle) -> bool:
        """Clean up a file handle resource."""
        try:
            if hasattr(file_handle, 'close') and not file_handle.closed:
                file_handle.close()
            
            return True
            
        except Exception as e:
            print(f"Error cleaning up file handle: {e}")
            return False
    
    def _cleanup_timer_resource(self, timer) -> bool:
        """Clean up a timer resource."""
        try:
            if hasattr(timer, 'cancel'):
                timer.cancel()
            elif hasattr(timer, 'stop'):
                timer.stop()
            
            return True
            
        except Exception as e:
            print(f"Error cleaning up timer: {e}")
            return False
    
    def _cleanup_loop(self):
        """Background cleanup loop."""
        while not self._stop_event.wait(self.cleanup_interval):
            try:
                # Clean up expired resources
                cleaned = self.cleanup_expired_resources()
                
                if cleaned > 0:
                    self.stats.last_cleanup = datetime.now()
                
                # Force garbage collection periodically
                if self.stats.cleaned_resources % 10 == 0:
                    self.force_garbage_collection()
                
                # Clean up dead weak references
                self._cleanup_weak_refs()
                
            except Exception as e:
                print(f"Error in resource cleanup loop: {e}")
    
    def _cleanup_weak_refs(self):
        """Clean up dead weak references."""
        dead_refs = set()
        for weak_ref in self._weak_refs:
            if weak_ref() is None:
                dead_refs.add(weak_ref)
        
        self._weak_refs -= dead_refs
    
    def _on_resource_deleted(self, weak_ref):
        """Callback when a resource is deleted."""
        # Remove the weak reference
        self._weak_refs.discard(weak_ref)
    
    def get_resource_summary(self) -> Dict[str, Any]:
        """Get summary of all resources."""
        with self._lock:
            summary = {
                'total_resources': len(self._resources),
                'by_type': {},
                'oldest_resource': None,
                'newest_resource': None
            }
            
            # Count by type
            for resource_info in self._resources.values():
                resource_type = resource_info.resource_type.value
                summary['by_type'][resource_type] = summary['by_type'].get(resource_type, 0) + 1
            
            # Find oldest and newest
            if self._resources:
                oldest = min(self._resources.values(), key=lambda r: r.created_at)
                newest = max(self._resources.values(), key=lambda r: r.created_at)
                
                summary['oldest_resource'] = {
                    'id': oldest.resource_id,
                    'type': oldest.resource_type.value,
                    'age_seconds': (datetime.now() - oldest.created_at).total_seconds()
                }
                
                summary['newest_resource'] = {
                    'id': newest.resource_id,
                    'type': newest.resource_type.value,
                    'age_seconds': (datetime.now() - newest.created_at).total_seconds()
                }
            
            return summary