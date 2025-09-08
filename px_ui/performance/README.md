# Performance Optimizations and Memory Management

This module provides comprehensive performance optimizations for the px UI client, including memory management, log rotation, update throttling, and resource cleanup. These optimizations ensure the application remains responsive even under high traffic conditions.

## Overview

The performance optimization system consists of several interconnected components:

1. **Memory Manager** - Manages memory usage and automatic cleanup
2. **Log Rotator** - Handles log rotation and cleanup of old data
3. **Update Throttler** - Limits UI refresh frequency during high traffic
4. **Resource Cleaner** - Manages cleanup of threads and connections
5. **Performance Monitor** - Coordinates all optimizations with unified monitoring

## Components

### Memory Manager (`memory_manager.py`)

Manages memory usage for monitoring data and response bodies with automatic cleanup.

**Key Features:**
- Response body truncation to configurable size limits
- Automatic cleanup of old monitoring entries
- Memory usage monitoring with configurable thresholds
- Adaptive cleanup based on memory pressure
- Statistics tracking for memory usage

**Usage:**
```python
from px_ui.performance import MemoryManager

memory_manager = MemoryManager(
    max_entries=1000,
    max_memory_mb=500,
    max_body_size=10240,  # 10KB
    cleanup_interval=60
)

# Start monitoring
memory_manager.start_monitoring()

# Add cleanup callback
memory_manager.add_cleanup_callback(lambda count: print(f"Cleaned {count} entries"))

# Truncate response body
truncated = memory_manager.truncate_response_body(large_response_body)
```

### Log Rotator (`log_rotator.py`)

Handles log rotation and automatic cleanup of old monitoring data.

**Key Features:**
- Multiple rotation policies: count-based, size-based, time-based
- Automatic compression of rotated files
- Configurable retention policies
- Background cleanup of old log files
- Statistics tracking for log operations

**Usage:**
```python
from px_ui.performance import LogRotator, RotationConfig, RotationPolicy

config = RotationConfig(
    policy=RotationPolicy.COUNT_BASED,
    max_count=1000,
    max_files=5,
    compress_old=True
)

log_rotator = LogRotator("logs", config)
log_rotator.start_rotation()

# Add entries
log_rotator.add_entry({
    'timestamp': datetime.now(),
    'url': 'http://example.com',
    'status': 200
})
```

### Update Throttler (`update_throttler.py`)

Limits UI refresh frequency during high traffic to prevent overload.

**Key Features:**
- Multiple throttling modes: fixed rate, adaptive, burst control
- Configurable update rate limits
- Priority-based update queuing
- Batch update processing for improved performance
- Statistics tracking for throttling operations

**Usage:**
```python
from px_ui.performance import UpdateThrottler, ThrottleConfig, ThrottleMode

config = ThrottleConfig(
    mode=ThrottleMode.ADAPTIVE,
    max_updates_per_second=30,
    min_update_interval_ms=33
)

throttler = UpdateThrottler(config)
throttler.start_throttling()

# Request throttled update
success = throttler.request_update(update_function, priority=1)

# Force immediate update
throttler.force_update(critical_update_function)
```

### Resource Cleaner (`resource_cleaner.py`)

Manages cleanup of threads, connections, and other system resources.

**Key Features:**
- Automatic cleanup of expired resources
- Support for multiple resource types (threads, connections, queues, files)
- Configurable timeout policies
- Custom cleanup functions
- Weak reference tracking to prevent memory leaks

**Usage:**
```python
from px_ui.performance import ResourceCleaner, ResourceType

cleaner = ResourceCleaner(
    cleanup_interval=300,  # 5 minutes
    resource_timeout=3600,  # 1 hour
    max_resources=100
)

cleaner.start_cleanup()

# Register resources
cleaner.register_resource(
    "my_thread",
    ResourceType.THREAD,
    thread_object,
    cleanup_func=custom_cleanup
)

# Manual cleanup
cleaner.cleanup_by_type(ResourceType.CONNECTION)
```

### Performance Monitor (`performance_monitor.py`)

Central coordinator for all performance optimizations with unified monitoring.

**Key Features:**
- Integrated management of all performance components
- Performance scoring and alerting
- Automatic optimization based on system load
- Comprehensive performance reporting
- Configurable alert thresholds

**Usage:**
```python
from px_ui.performance import PerformanceMonitor, PerformanceConfig

config = PerformanceConfig(
    enable_memory_management=True,
    enable_log_rotation=True,
    enable_update_throttling=True,
    enable_resource_cleanup=True,
    max_entries=1000,
    max_memory_mb=500
)

monitor = PerformanceMonitor(config)
monitor.start_monitoring()

# Add alert callback
monitor.add_alert_callback(lambda alert_type, data: print(f"Alert: {alert_type}"))

# Get performance stats
stats = monitor.get_performance_stats()
print(f"Performance score: {stats.performance_score}")

# Force optimization
monitor.force_optimization()
```

## Integration with UI Components

### Monitoring View Integration

The monitoring view has been enhanced with performance optimizations:

```python
from px_ui.performance import PerformanceMonitor, PerformanceConfig

class MonitoringView(ttk.Frame):
    def __init__(self, parent, event_system):
        super().__init__(parent)
        
        # Initialize performance monitor
        self.performance_monitor = PerformanceMonitor(PerformanceConfig(
            max_entries=1000,
            max_memory_mb=200,
            max_body_size=5120,
            max_updates_per_second=20,
            throttle_mode="adaptive"
        ))
        
        # Start performance monitoring
        self.performance_monitor.start_monitoring()
        
        # Set up callbacks
        memory_manager = self.performance_monitor.get_memory_manager()
        if memory_manager:
            memory_manager.add_cleanup_callback(self._on_memory_cleanup)
```

### Virtual Scrolling

For large datasets, virtual scrolling is implemented to improve performance:

```python
def _refresh_tree_virtual(self):
    """Refresh tree view with virtual scrolling for large datasets."""
    # Only render visible items
    start_idx, end_idx = self.visible_range
    visible_entries = self.filtered_entries[start_idx:end_idx]
    
    # Clear and repopulate with visible items only
    for item in self.tree.get_children():
        self.tree.delete(item)
    
    for entry_id in visible_entries:
        # Add entry to tree
        self.tree.insert("", "end", values=entry_values)
```

### Event Processing Optimization

The event processor has been enhanced with batch processing and throttling:

```python
from px_ui.performance import UpdateThrottler, BatchUpdateThrottler

class EventProcessor:
    def __init__(self, event_queue, max_events_per_second=50):
        self.update_throttler = UpdateThrottler(ThrottleConfig(
            max_updates_per_second=max_events_per_second,
            throttle_mode="adaptive"
        ))
        
        self.batch_throttler = BatchUpdateThrottler(
            batch_size=10,
            batch_timeout_ms=50
        )
        
        # Set up batch processing
        self.batch_throttler.set_batch_processor(self._process_event_batch)
```

## Configuration

### Performance Configuration

All performance optimizations can be configured through `PerformanceConfig`:

```python
config = PerformanceConfig(
    # Enable/disable components
    enable_memory_management=True,
    enable_log_rotation=True,
    enable_update_throttling=True,
    enable_resource_cleanup=True,
    
    # Memory management
    max_entries=1000,
    max_memory_mb=500,
    max_body_size=10240,
    
    # Log rotation
    log_directory="logs",
    rotation_policy="count",  # "count", "size", "time"
    max_log_files=5,
    
    # Update throttling
    max_updates_per_second=30,
    throttle_mode="adaptive",  # "fixed", "adaptive", "burst"
    
    # Resource cleanup
    cleanup_interval=300,
    resource_timeout=3600,
    
    # Monitoring
    stats_update_interval=60,
    performance_alerts=True
)
```

### Alert Thresholds

Performance alerts can be configured with custom thresholds:

```python
monitor._alert_thresholds = {
    'memory_usage_percent': 80,
    'throttle_rate_percent': 70,
    'cleanup_failures_percent': 20,
    'performance_score_min': 60
}
```

## Performance Metrics

The system tracks various performance metrics:

### Memory Metrics
- Total memory usage (MB)
- Process memory usage (MB)
- Number of entries in memory
- Number of truncated response bodies
- Memory cleanup operations

### Log Metrics
- Total log entries
- Number of rotated files
- Total log size (MB)
- Compression statistics
- Cleanup operations

### Throttling Metrics
- Total update requests
- Throttled requests
- Current update rate
- Average update rate
- Burst events

### Resource Metrics
- Active resources by type
- Cleaned resources
- Failed cleanup operations
- Memory freed through cleanup

### Overall Performance Score

The system calculates an overall performance score (0-100) based on:
- Memory usage efficiency (30 points)
- Update throttling effectiveness (25 points)
- Resource cleanup success rate (25 points)
- Log management efficiency (20 points)

## Best Practices

### Memory Management
1. Set appropriate `max_entries` based on available memory
2. Configure `max_body_size` to limit response body storage
3. Monitor memory usage and adjust thresholds as needed
4. Use cleanup callbacks to handle application-specific cleanup

### Log Rotation
1. Choose appropriate rotation policy based on usage patterns
2. Set reasonable retention policies to balance storage and history
3. Enable compression for long-term storage
4. Monitor log directory size regularly

### Update Throttling
1. Use adaptive throttling for variable load conditions
2. Set update rates based on UI responsiveness requirements
3. Use priority-based updates for critical operations
4. Monitor throttling statistics to optimize settings

### Resource Cleanup
1. Register all long-lived resources for cleanup
2. Provide custom cleanup functions for complex resources
3. Set appropriate timeout values based on resource lifecycle
4. Monitor cleanup statistics for resource leaks

## Troubleshooting

### High Memory Usage
- Check `max_entries` configuration
- Verify cleanup callbacks are working
- Monitor for memory leaks in application code
- Consider reducing `max_body_size`

### Poor UI Responsiveness
- Check update throttling configuration
- Monitor throttling statistics
- Consider using batch processing for high-volume updates
- Verify virtual scrolling is enabled for large datasets

### Resource Leaks
- Check resource cleanup statistics
- Verify all resources are properly registered
- Monitor system resource usage
- Check for failed cleanup operations

### Log Storage Issues
- Verify log rotation is working
- Check retention policies
- Monitor log directory size
- Ensure compression is enabled if needed

## Examples

See `examples/performance_optimization_example.py` for a complete demonstration of all performance optimization features.

## Testing

Run the test suite to verify performance optimizations:

```bash
python test_task11_completion.py
```

This will test all performance components and verify they work correctly together.