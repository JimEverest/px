"""
Example usage of the event communication system.

This script demonstrates how to use the event communication system
for proxy-to-UI communication with filtering and throttling.
"""

import time
import threading
from datetime import datetime

from .event_system import (
    EventSystem, EventType,
    create_request_event, create_response_event, create_error_event, create_status_event
)


def example_request_handler(event):
    """Example handler for request events."""
    print(f"[REQUEST] {event.timestamp.strftime('%H:%M:%S')} - {event.method} {event.url} -> {event.proxy_decision}")


def example_response_handler(event):
    """Example handler for response events."""
    status_color = "🔴" if event.status_code >= 400 else "🟢"
    print(f"[RESPONSE] {event.timestamp.strftime('%H:%M:%S')} - {status_color} {event.status_code} ({event.response_time:.2f}s)")


def example_error_handler(event):
    """Example handler for error events."""
    print(f"[ERROR] {event.timestamp.strftime('%H:%M:%S')} - {event.error_type}: {event.error_message}")


def example_status_handler(event):
    """Example handler for status events."""
    status = "🟢 RUNNING" if event.is_running else "🔴 STOPPED"
    print(f"[STATUS] {event.timestamp.strftime('%H:%M:%S')} - {status} on {event.listen_address}:{event.port}")


def simulate_proxy_activity(event_system):
    """Simulate proxy activity by sending various events."""
    
    # Simulate proxy startup
    status_event = create_status_event(
        is_running=True,
        listen_address="127.0.0.1",
        port=3128,
        mode="pac",
        active_connections=0,
        total_requests=0
    )
    event_system.send_event(status_event)
    
    # Simulate some requests
    requests = [
        ("http://google.com", "GET", "DIRECT"),
        ("http://github.com", "GET", "PROXY proxy:8080"),
        ("http://stackoverflow.com", "GET", "DIRECT"),
        ("http://api.github.com", "POST", "PROXY proxy:8080"),
        ("http://example.com", "GET", "DIRECT")
    ]
    
    for i, (url, method, proxy_decision) in enumerate(requests):
        # Send request event
        request_id = f"req-{i+1}"
        request_event = create_request_event(
            url=url,
            method=method,
            proxy_decision=proxy_decision,
            request_id=request_id
        )
        event_system.send_event(request_event)
        
        # Simulate some processing time
        time.sleep(0.1)
        
        # Send response event
        status_code = 200 if i < 3 else (404 if i == 3 else 500)
        response_event = create_response_event(
            request_id=request_id,
            status_code=status_code,
            headers={"Content-Type": "text/html", "Content-Length": "1024"},
            body_preview="<html><body>Response content...</body></html>",
            content_length=1024,
            response_time=0.15 + (i * 0.05)
        )
        event_system.send_event(response_event)
        
        # Simulate error for last request
        if i == 4:
            error_event = create_error_event(
                error_type="network",
                error_message="Internal server error",
                error_details="Connection timeout after 30 seconds",
                request_id=request_id,
                url=url
            )
            event_system.send_event(error_event)
    
    # Simulate proxy shutdown
    time.sleep(0.5)
    status_event = create_status_event(
        is_running=False,
        listen_address="127.0.0.1",
        port=3128,
        mode="pac",
        active_connections=0,
        total_requests=5
    )
    event_system.send_event(status_event)


def main():
    """Main example function."""
    print("Event Communication System Example")
    print("=" * 50)
    
    # Create event system
    event_system = EventSystem(queue_size=100, max_events_per_second=100)
    
    # Add event handlers
    event_system.add_request_handler(example_request_handler)
    event_system.add_response_handler(example_response_handler)
    event_system.add_error_handler(example_error_handler)
    event_system.add_status_handler(example_status_handler)
    
    # Start the event system
    event_system.start()
    
    print("\n1. Basic Event Processing:")
    print("-" * 30)
    
    # Simulate proxy activity in a separate thread
    simulator_thread = threading.Thread(target=simulate_proxy_activity, args=(event_system,))
    simulator_thread.start()
    
    # Let it run for a bit
    time.sleep(2)
    
    # Wait for simulator to finish
    simulator_thread.join()
    
    print("\n2. Event Filtering Example:")
    print("-" * 30)
    
    # Clear previous events
    event_system.clear_queue()
    
    # Set up filtering for error status codes only
    event_system.set_event_filter(status_codes=[404, 500, 503])
    
    # Send some more events
    for i in range(3):
        status_codes = [200, 404, 500]
        response_event = create_response_event(
            request_id=f"filtered-req-{i}",
            status_code=status_codes[i],
            headers={},
            body_preview="",
            content_length=0,
            response_time=0.1
        )
        event_system.send_event(response_event)
    
    # Process events (should only show 404 and 500)
    time.sleep(0.5)
    
    print("\n3. URL Pattern Filtering Example:")
    print("-" * 30)
    
    # Clear filter and set URL pattern filter
    event_system.clear_filter()
    event_system.set_event_filter(url_patterns=["*github*", "*google*"])
    
    # Send requests with different URLs
    urls = [
        "http://github.com/user/repo",
        "http://example.com",
        "http://api.github.com",
        "http://google.com/search",
        "http://stackoverflow.com"
    ]
    
    for i, url in enumerate(urls):
        request_event = create_request_event(
            url=url,
            method="GET",
            proxy_decision="DIRECT",
            request_id=f"pattern-req-{i}"
        )
        event_system.send_event(request_event)
    
    # Process events (should only show github and google URLs)
    time.sleep(0.5)
    
    # Show statistics
    print("\n4. System Statistics:")
    print("-" * 30)
    stats = event_system.get_stats()
    print(f"Events processed: {stats['events_processed']}")
    print(f"Events filtered: {stats['events_filtered']}")
    print(f"Queue size: {stats['queue_stats']['current_size']}")
    print(f"Total events sent: {stats['queue_stats']['total_events']}")
    
    # Stop the event system
    event_system.stop()
    print("\nEvent system stopped.")


if __name__ == "__main__":
    main()