"""
Example integration of enhanced px handler with monitoring.

This module demonstrates how to integrate the enhanced px handler
with the event system for real-time monitoring.
"""

import threading
import time
from typing import Optional

from ..communication.event_system import EventSystem
from ..communication.events import RequestEvent, ResponseEvent, ErrorEvent, StatusEvent
from .configuration_bridge import setup_px_monitoring, disable_px_monitoring


class ProxyMonitoringIntegration:
    """
    Complete integration example for proxy monitoring.
    
    This class demonstrates how to set up and use the enhanced px handler
    with real-time event monitoring.
    """
    
    def __init__(self, queue_size: int = 1000, max_events_per_second: int = 50):
        """
        Initialize the monitoring integration.
        
        Args:
            queue_size: Maximum size of event queue
            max_events_per_second: Maximum events to process per second
        """
        self.event_system = EventSystem(queue_size, max_events_per_second)
        self.bridge = None
        self._monitoring_active = False
        self._stats = {
            'total_requests': 0,
            'total_responses': 0,
            'total_errors': 0,
            'active_requests': 0
        }
        self._active_requests = set()
    
    def start_monitoring(self):
        """Start the monitoring system."""
        if self._monitoring_active:
            return
        
        # Set up event handlers
        self.event_system.add_request_handler(self._handle_request_event)
        self.event_system.add_response_handler(self._handle_response_event)
        self.event_system.add_error_handler(self._handle_error_event)
        
        # Start event system
        self.event_system.start()
        
        # Configure px monitoring
        self.bridge = setup_px_monitoring(self.event_system)
        
        self._monitoring_active = True
        print("Proxy monitoring started")
    
    def stop_monitoring(self):
        """Stop the monitoring system."""
        if not self._monitoring_active:
            return
        
        # Disable px monitoring
        if self.bridge:
            disable_px_monitoring(self.bridge)
            self.bridge = None
        
        # Stop event system
        self.event_system.stop()
        
        self._monitoring_active = False
        print("Proxy monitoring stopped")
    
    def _handle_request_event(self, event: RequestEvent):
        """Handle request events."""
        self._stats['total_requests'] += 1
        self._active_requests.add(event.request_id)
        self._stats['active_requests'] = len(self._active_requests)
        
        print(f"Request: {event.method} {event.url} -> {event.proxy_decision}")
    
    def _handle_response_event(self, event: ResponseEvent):
        """Handle response events."""
        self._stats['total_responses'] += 1
        if event.request_id in self._active_requests:
            self._active_requests.remove(event.request_id)
            self._stats['active_requests'] = len(self._active_requests)
        
        print(f"Response: {event.status_code} ({event.response_time:.3f}s) - {event.content_length} bytes")
    
    def _handle_error_event(self, event: ErrorEvent):
        """Handle error events."""
        self._stats['total_errors'] += 1
        if event.request_id and event.request_id in self._active_requests:
            self._active_requests.remove(event.request_id)
            self._stats['active_requests'] = len(self._active_requests)
        
        print(f"Error: {event.error_type} - {event.error_message}")
        if event.url:
            print(f"  URL: {event.url}")
    
    def get_stats(self) -> dict:
        """Get monitoring statistics."""
        stats = self._stats.copy()
        stats['monitoring_active'] = self._monitoring_active
        
        if self.bridge:
            stats.update(self.bridge.get_monitoring_stats())
        
        return stats
    
    def print_stats(self):
        """Print current statistics."""
        stats = self.get_stats()
        print("\n=== Proxy Monitoring Stats ===")
        print(f"Monitoring Active: {stats['monitoring_active']}")
        print(f"Total Requests: {stats['total_requests']}")
        print(f"Total Responses: {stats['total_responses']}")
        print(f"Total Errors: {stats['total_errors']}")
        print(f"Active Requests: {stats['active_requests']}")
        
        if 'event_system_stats' in stats:
            event_stats = stats['event_system_stats']
            print(f"Event Queue Size: {event_stats.get('current_size', 0)}")
            print(f"Events Processed: {event_stats.get('total_processed', 0)}")
        print("==============================\n")


def run_monitoring_example():
    """
    Run a complete monitoring example.
    
    This function demonstrates how to set up and use the proxy monitoring
    system in a real application.
    """
    print("Starting proxy monitoring example...")
    
    # Create monitoring integration
    monitoring = ProxyMonitoringIntegration()
    
    try:
        # Start monitoring
        monitoring.start_monitoring()
        
        # Print initial stats
        monitoring.print_stats()
        
        # Simulate running for a while
        print("Monitoring active. Press Ctrl+C to stop...")
        
        # Print stats every 10 seconds
        while True:
            time.sleep(10)
            monitoring.print_stats()
    
    except KeyboardInterrupt:
        print("\nStopping monitoring...")
    
    finally:
        # Clean up
        monitoring.stop_monitoring()
        print("Monitoring stopped.")


if __name__ == "__main__":
    run_monitoring_example()