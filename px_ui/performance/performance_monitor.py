"""
Performance monitoring and optimization coordinator.

This module provides a central coordinator for all performance optimizations
including memory management, log rotation, update throttling, and resource cleanup.
"""

import threading
import time
import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from .memory_manager import MemoryManager, MemoryStats
from .log_rotator import LogRotator, RotationConfig, LogStats
from .update_throttler import UpdateThrottler, ThrottleConfig, ThrottleStats
from .resource_cleaner import ResourceCleaner, CleanupStats


@dataclass
class PerformanceConfig:
    """Configuration for performance monitoring."""
    enable_memory_management: bool = True
    enable_log_rotation: bool = True
    enable_update_throttling: bool = True
    enable_resource_cleanup: bool = True
    
    # Memory management
    max_entries: int = 1000
    max_memory_mb: int = 500
    max_body_size: int = 10240
    
    # Log rotation
    log_directory: str = "logs"
    rotation_policy: str = "count"  # "count", "size", "time"
    max_log_files: int = 5
    
    # Update throttling
    max_updates_per_second: int = 30
    throttle_mode: str = "adaptive"  # "fixed", "adaptive", "burst"
    
    # Resource cleanup
    cleanup_interval: int = 300
    resource_timeout: int = 3600
    
    # Monitoring
    stats_update_interval: int = 60
    performance_alerts: bool = True


@dataclass
class PerformanceStats:
    """Combined performance statistics."""
    memory_stats: Optional[MemoryStats] = None
    log_stats: Optional[LogStats] = None
    throttle_stats: Optional[ThrottleStats] = None
    cleanup_stats: Optional[CleanupStats] = None
    
    # Overall stats
    uptime_seconds: float = 0
    total_optimizations: int = 0
    performance_score: float = 100.0  # 0-100 scale
    last_update: Optional[datetime] = None


class PerformanceMonitor:
    """
    Central coordinator for performance optimizations.
    
    Manages memory, log rotation, update throttling, and resource cleanup
    with unified monitoring and alerting.
    """
    
    def __init__(self, config: Optional[PerformanceConfig] = None):
        """
        Initialize performance monitor.
        
        Args:
            config: Performance configuration
        """
        self.config = config or PerformanceConfig()
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.memory_manager: Optional[MemoryManager] = None
        self.log_rotator: Optional[LogRotator] = None
        self.update_throttler: Optional[UpdateThrottler] = None
        self.resource_cleaner: Optional[ResourceCleaner] = None
        
        # Statistics
        self.stats = PerformanceStats()
        self.start_time = datetime.now()
        
        # Monitoring control
        self._monitoring_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        
        # Alert callbacks
        self._alert_callbacks: List[Callable[[str, Dict], None]] = []
        
        # Performance thresholds for alerts
        self._alert_thresholds = {
            'memory_usage_percent': 80,
            'throttle_rate_percent': 70,
            'cleanup_failures_percent': 20,
            'performance_score_min': 60
        }
        
        self._initialize_components()
    
    def start_monitoring(self):
        """Start all performance monitoring components."""
        try:
            # Start individual components
            if self.memory_manager:
                self.memory_manager.start_monitoring()
            
            if self.log_rotator:
                self.log_rotator.start_rotation()
            
            if self.update_throttler:
                self.update_throttler.start_throttling()
            
            if self.resource_cleaner:
                self.resource_cleaner.start_cleanup()
            
            # Start monitoring thread
            self._stop_event.clear()
            self._monitoring_thread = threading.Thread(
                target=self._monitoring_loop,
                name="PerformanceMonitor",
                daemon=True
            )
            self._monitoring_thread.start()
            
            self.logger.info("Performance monitoring started")
            
        except Exception as e:
            self.logger.error(f"Failed to start performance monitoring: {e}")
            raise
    
    def stop_monitoring(self):
        """Stop all performance monitoring components."""
        try:
            # Stop monitoring thread
            self._stop_event.set()
            
            if self._monitoring_thread and self._monitoring_thread.is_alive():
                self._monitoring_thread.join(timeout=2.0)
            
            # Stop individual components
            if self.memory_manager:
                self.memory_manager.stop_monitoring()
            
            if self.log_rotator:
                self.log_rotator.stop_rotation()
            
            if self.update_throttler:
                self.update_throttler.stop_throttling()
            
            if self.resource_cleaner:
                self.resource_cleaner.stop_cleanup()
            
            self.logger.info("Performance monitoring stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping performance monitoring: {e}")
    
    def get_performance_stats(self) -> PerformanceStats:
        """Get current performance statistics."""
        with self._lock:
            # Update component stats
            if self.memory_manager:
                self.stats.memory_stats = self.memory_manager.get_memory_stats()
            
            if self.log_rotator:
                self.stats.log_stats = self.log_rotator.get_stats()
            
            if self.update_throttler:
                self.stats.throttle_stats = self.update_throttler.get_stats()
            
            if self.resource_cleaner:
                self.stats.cleanup_stats = self.resource_cleaner.get_stats()
            
            # Update overall stats
            self.stats.uptime_seconds = (datetime.now() - self.start_time).total_seconds()
            self.stats.performance_score = self._calculate_performance_score()
            self.stats.last_update = datetime.now()
            
            return self.stats
    
    def add_alert_callback(self, callback: Callable[[str, Dict], None]):
        """Add callback for performance alerts."""
        with self._lock:
            self._alert_callbacks.append(callback)
    
    def force_optimization(self):
        """Force immediate optimization across all components."""
        try:
            optimizations = 0
            
            # Force memory cleanup
            if self.memory_manager:
                entries_count = self.memory_manager.stats.entries_count
                if self.memory_manager.should_cleanup(entries_count):
                    cleanup_amount = self.memory_manager.calculate_cleanup_amount(entries_count)
                    self.memory_manager.force_cleanup(cleanup_amount)
                    optimizations += 1
            
            # Force log rotation
            if self.log_rotator:
                rotated_file = self.log_rotator.force_rotation()
                if rotated_file:
                    optimizations += 1
            
            # Force resource cleanup
            if self.resource_cleaner:
                cleaned = self.resource_cleaner.cleanup_expired_resources()
                if cleaned > 0:
                    optimizations += 1
            
            # Clear throttler pending updates if overloaded
            if self.update_throttler:
                pending = self.update_throttler.get_pending_count()
                if pending > 20:  # Arbitrary threshold
                    self.update_throttler.clear_pending_updates()
                    optimizations += 1
            
            with self._lock:
                self.stats.total_optimizations += optimizations
            
            self.logger.info(f"Forced optimization completed: {optimizations} operations")
            
        except Exception as e:
            self.logger.error(f"Error during forced optimization: {e}")
    
    def get_memory_manager(self) -> Optional[MemoryManager]:
        """Get memory manager instance."""
        return self.memory_manager
    
    def get_log_rotator(self) -> Optional[LogRotator]:
        """Get log rotator instance."""
        return self.log_rotator
    
    def get_update_throttler(self) -> Optional[UpdateThrottler]:
        """Get update throttler instance."""
        return self.update_throttler
    
    def get_resource_cleaner(self) -> Optional[ResourceCleaner]:
        """Get resource cleaner instance."""
        return self.resource_cleaner
    
    def update_config(self, new_config: PerformanceConfig):
        """Update performance configuration."""
        self.config = new_config
        
        # Reinitialize components with new config
        self.stop_monitoring()
        self._initialize_components()
        self.start_monitoring()
        
        self.logger.info("Performance configuration updated")
    
    def _initialize_components(self):
        """Initialize performance components based on configuration."""
        try:
            # Initialize memory manager
            if self.config.enable_memory_management:
                self.memory_manager = MemoryManager(
                    max_entries=self.config.max_entries,
                    max_memory_mb=self.config.max_memory_mb,
                    max_body_size=self.config.max_body_size
                )
            
            # Initialize log rotator
            if self.config.enable_log_rotation:
                from .log_rotator import RotationPolicy
                
                policy_map = {
                    "count": RotationPolicy.COUNT_BASED,
                    "size": RotationPolicy.SIZE_BASED,
                    "time": RotationPolicy.TIME_BASED
                }
                
                rotation_config = RotationConfig(
                    policy=policy_map.get(self.config.rotation_policy, RotationPolicy.COUNT_BASED),
                    max_files=self.config.max_log_files
                )
                
                self.log_rotator = LogRotator(
                    log_directory=self.config.log_directory,
                    config=rotation_config
                )
            
            # Initialize update throttler
            if self.config.enable_update_throttling:
                from .update_throttler import ThrottleMode
                
                mode_map = {
                    "fixed": ThrottleMode.FIXED_RATE,
                    "adaptive": ThrottleMode.ADAPTIVE,
                    "burst": ThrottleMode.BURST_CONTROL
                }
                
                throttle_config = ThrottleConfig(
                    mode=mode_map.get(self.config.throttle_mode, ThrottleMode.ADAPTIVE),
                    max_updates_per_second=self.config.max_updates_per_second
                )
                
                self.update_throttler = UpdateThrottler(throttle_config)
            
            # Initialize resource cleaner
            if self.config.enable_resource_cleanup:
                self.resource_cleaner = ResourceCleaner(
                    cleanup_interval=self.config.cleanup_interval,
                    resource_timeout=self.config.resource_timeout
                )
            
            self.logger.info("Performance components initialized")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize performance components: {e}")
            raise
    
    def _monitoring_loop(self):
        """Background monitoring loop."""
        while not self._stop_event.wait(self.config.stats_update_interval):
            try:
                # Update statistics
                current_stats = self.get_performance_stats()
                
                # Check for performance alerts
                if self.config.performance_alerts:
                    self._check_performance_alerts(current_stats)
                
                # Perform automatic optimizations if needed
                self._auto_optimize(current_stats)
                
            except Exception as e:
                self.logger.error(f"Error in performance monitoring loop: {e}")
    
    def _check_performance_alerts(self, stats: PerformanceStats):
        """Check for performance issues and trigger alerts."""
        alerts = []
        
        # Memory usage alert
        if stats.memory_stats:
            memory_percent = (stats.memory_stats.process_memory_mb / 
                            max(stats.memory_stats.total_memory_mb, 1)) * 100
            
            if memory_percent > self._alert_thresholds['memory_usage_percent']:
                alerts.append({
                    'type': 'memory_usage',
                    'severity': 'warning',
                    'message': f'High memory usage: {memory_percent:.1f}%',
                    'data': {'memory_percent': memory_percent}
                })
        
        # Throttling alert
        if stats.throttle_stats:
            if stats.throttle_stats.total_requests > 0:
                throttle_percent = (stats.throttle_stats.throttled_requests / 
                                  stats.throttle_stats.total_requests) * 100
                
                if throttle_percent > self._alert_thresholds['throttle_rate_percent']:
                    alerts.append({
                        'type': 'high_throttling',
                        'severity': 'warning',
                        'message': f'High throttling rate: {throttle_percent:.1f}%',
                        'data': {'throttle_percent': throttle_percent}
                    })
        
        # Cleanup failures alert
        if stats.cleanup_stats:
            total_cleanups = stats.cleanup_stats.cleaned_resources + stats.cleanup_stats.failed_cleanups
            if total_cleanups > 0:
                failure_percent = (stats.cleanup_stats.failed_cleanups / total_cleanups) * 100
                
                if failure_percent > self._alert_thresholds['cleanup_failures_percent']:
                    alerts.append({
                        'type': 'cleanup_failures',
                        'severity': 'error',
                        'message': f'High cleanup failure rate: {failure_percent:.1f}%',
                        'data': {'failure_percent': failure_percent}
                    })
        
        # Performance score alert
        if stats.performance_score < self._alert_thresholds['performance_score_min']:
            alerts.append({
                'type': 'low_performance',
                'severity': 'warning',
                'message': f'Low performance score: {stats.performance_score:.1f}',
                'data': {'performance_score': stats.performance_score}
            })
        
        # Send alerts
        for alert in alerts:
            self._send_alert(alert['type'], alert)
    
    def _auto_optimize(self, stats: PerformanceStats):
        """Perform automatic optimizations based on current stats."""
        try:
            # Auto memory cleanup if usage is high
            if (stats.memory_stats and 
                stats.memory_stats.process_memory_mb > self.config.max_memory_mb * 0.9):
                
                if self.memory_manager:
                    entries_count = stats.memory_stats.entries_count
                    cleanup_amount = self.memory_manager.calculate_cleanup_amount(entries_count)
                    if cleanup_amount > 0:
                        self.memory_manager.force_cleanup(cleanup_amount)
                        self.logger.info(f"Auto-optimized: cleaned {cleanup_amount} entries")
            
            # Auto log rotation if needed
            if self.log_rotator and self.log_rotator._should_rotate():
                rotated_file = self.log_rotator.force_rotation()
                if rotated_file:
                    self.logger.info(f"Auto-optimized: rotated logs to {rotated_file}")
            
            # Auto resource cleanup if too many resources
            if (stats.cleanup_stats and 
                stats.cleanup_stats.active_resources > 50):  # Arbitrary threshold
                
                if self.resource_cleaner:
                    cleaned = self.resource_cleaner.cleanup_expired_resources()
                    if cleaned > 0:
                        self.logger.info(f"Auto-optimized: cleaned {cleaned} resources")
            
        except Exception as e:
            self.logger.error(f"Error during auto-optimization: {e}")
    
    def _calculate_performance_score(self) -> float:
        """Calculate overall performance score (0-100)."""
        score = 100.0
        
        # Memory score (0-30 points)
        if self.stats.memory_stats:
            memory_usage = min(100, (self.stats.memory_stats.process_memory_mb / 
                                   max(self.config.max_memory_mb, 1)) * 100)
            memory_score = max(0, 30 - (memory_usage * 0.3))
            score = min(score, score - (30 - memory_score))
        
        # Throttling score (0-25 points)
        if self.stats.throttle_stats and self.stats.throttle_stats.total_requests > 0:
            throttle_rate = (self.stats.throttle_stats.throttled_requests / 
                           self.stats.throttle_stats.total_requests) * 100
            throttle_score = max(0, 25 - (throttle_rate * 0.25))
            score = min(score, score - (25 - throttle_score))
        
        # Resource cleanup score (0-25 points)
        if self.stats.cleanup_stats:
            total_cleanups = (self.stats.cleanup_stats.cleaned_resources + 
                            self.stats.cleanup_stats.failed_cleanups)
            if total_cleanups > 0:
                failure_rate = (self.stats.cleanup_stats.failed_cleanups / total_cleanups) * 100
                cleanup_score = max(0, 25 - (failure_rate * 0.25))
                score = min(score, score - (25 - cleanup_score))
        
        # Log management score (0-20 points)
        if self.stats.log_stats:
            # Score based on log file count and size
            log_score = 20.0
            if self.stats.log_stats.rotated_files > self.config.max_log_files:
                log_score *= 0.8
            if self.stats.log_stats.total_size_mb > 100:  # Arbitrary threshold
                log_score *= 0.8
            score = min(score, score - (20 - log_score))
        
        return max(0, min(100, score))
    
    def _send_alert(self, alert_type: str, alert_data: Dict):
        """Send performance alert to registered callbacks."""
        with self._lock:
            for callback in self._alert_callbacks:
                try:
                    callback(alert_type, alert_data)
                except Exception as e:
                    self.logger.error(f"Error in alert callback: {e}")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report."""
        stats = self.get_performance_stats()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'uptime_hours': stats.uptime_seconds / 3600,
            'performance_score': stats.performance_score,
            'total_optimizations': stats.total_optimizations,
            'components': {}
        }
        
        # Memory report
        if stats.memory_stats:
            report['components']['memory'] = {
                'entries_count': stats.memory_stats.entries_count,
                'process_memory_mb': stats.memory_stats.process_memory_mb,
                'memory_percent': stats.memory_stats.memory_percent,
                'truncated_bodies': stats.memory_stats.truncated_bodies
            }
        
        # Log report
        if stats.log_stats:
            report['components']['logs'] = {
                'total_entries': stats.log_stats.total_entries,
                'rotated_files': stats.log_stats.rotated_files,
                'total_size_mb': stats.log_stats.total_size_mb,
                'last_rotation': stats.log_stats.last_rotation.isoformat() if stats.log_stats.last_rotation else None
            }
        
        # Throttling report
        if stats.throttle_stats:
            report['components']['throttling'] = {
                'total_requests': stats.throttle_stats.total_requests,
                'throttled_requests': stats.throttle_stats.throttled_requests,
                'current_rate': stats.throttle_stats.current_rate,
                'burst_events': stats.throttle_stats.burst_events
            }
        
        # Cleanup report
        if stats.cleanup_stats:
            report['components']['cleanup'] = {
                'active_resources': stats.cleanup_stats.active_resources,
                'cleaned_resources': stats.cleanup_stats.cleaned_resources,
                'failed_cleanups': stats.cleanup_stats.failed_cleanups,
                'memory_freed_mb': stats.cleanup_stats.memory_freed_mb
            }
        
        return report