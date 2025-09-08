"""
Tests for the event communication system.

This module tests the event queue, processor, and filtering functionality
to ensure proper thread-safe communication between proxy and UI.
"""

import unittest
import time
import threading
from datetime import datetime, timedelta

from px_ui.communication import (
    EventSystem, EventType, RequestEvent, ResponseEvent, ErrorEvent, StatusEvent,
    create_request_event, create_response_event, create_error_event, create_status_event
)


class TestEventCommunication(unittest.TestCase):
    """Test cases for event communication system."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.event_system = EventSystem(queue_size=100, max_events_per_second=1000)  # Higher rate for testing
        self.received_events = []
        
    def tearDown(self):
        """Clean up after tests."""
        self.event_system.stop()
    
    def _event_handler(self, event):
        """Generic event handler for testing."""
        self.received_events.append(event)
    
    def test_event_creation(self):
        """Test event creation functions."""
        # Test request event
        request_event = create_request_event(
            url="http://example.com",
            method="GET",
            proxy_decision="DIRECT",
            request_id="req-123"
        )
        self.assertEqual(request_event.event_type, EventType.REQUEST)
        self.assertEqual(request_event.url, "http://example.com")
        self.assertEqual(request_event.method, "GET")
        self.assertEqual(request_event.proxy_decision, "DIRECT")
        self.assertEqual(request_event.request_id, "req-123")
        
        # Test response event
        response_event = create_response_event(
            request_id="req-123",
            status_code=200,
            headers={"Content-Type": "text/html"},
            body_preview="<html>",
            content_length=1024,
            response_time=0.5
        )
        self.assertEqual(response_event.event_type, EventType.RESPONSE)
        self.assertEqual(response_event.request_id, "req-123")
        self.assertEqual(response_event.status_code, 200)
        
        # Test error event
        error_event = create_error_event(
            error_type="network",
            error_message="Connection timeout",
            request_id="req-123"
        )
        self.assertEqual(error_event.event_type, EventType.ERROR)
        self.assertEqual(error_event.error_type, "network")
        self.assertEqual(error_event.error_message, "Connection timeout")
        
        # Test status event
        status_event = create_status_event(
            is_running=True,
            listen_address="127.0.0.1",
            port=3128,
            mode="pac",
            active_connections=5,
            total_requests=100
        )
        self.assertEqual(status_event.event_type, EventType.STATUS)
        self.assertEqual(status_event.is_running, True)
        self.assertEqual(status_event.port, 3128)
    
    def test_event_queue_basic_operations(self):
        """Test basic event queue operations."""
        queue = self.event_system.queue
        
        # Test empty queue
        self.assertTrue(queue.is_empty())
        self.assertEqual(queue.size(), 0)
        
        # Test adding events
        event1 = create_request_event("http://test1.com", "GET", "DIRECT", "req-1")
        event2 = create_request_event("http://test2.com", "POST", "PROXY proxy:8080", "req-2")
        
        self.assertTrue(queue.put_event(event1))
        self.assertTrue(queue.put_event(event2))
        self.assertEqual(queue.size(), 2)
        self.assertFalse(queue.is_empty())
        
        # Test getting events
        retrieved_event1 = queue.get_event(block=False)
        self.assertEqual(retrieved_event1.url, "http://test1.com")
        
        retrieved_event2 = queue.get_event(block=False)
        self.assertEqual(retrieved_event2.url, "http://test2.com")
        
        # Queue should be empty now
        self.assertTrue(queue.is_empty())
        self.assertIsNone(queue.get_event(block=False))
    
    def test_event_queue_batch_operations(self):
        """Test batch operations on event queue."""
        queue = self.event_system.queue
        
        # Add multiple events
        events = []
        for i in range(5):
            event = create_request_event(f"http://test{i}.com", "GET", "DIRECT", f"req-{i}")
            events.append(event)
            queue.put_event(event)
        
        # Get events in batch
        batch = queue.get_events_batch(max_events=3, timeout=0.1)
        self.assertEqual(len(batch), 3)
        
        # Check remaining events
        self.assertEqual(queue.size(), 2)
        
        # Get remaining events
        remaining = queue.get_events_batch(max_events=5, timeout=0.1)
        self.assertEqual(len(remaining), 2)
        self.assertTrue(queue.is_empty())
    
    def test_event_filtering(self):
        """Test event filtering functionality."""
        # Set up filter for only request events
        self.event_system.set_event_filter(event_types=[EventType.REQUEST])
        
        # Add handler
        self.event_system.add_request_handler(self._event_handler)
        
        # Send different types of events
        request_event = create_request_event("http://test.com", "GET", "DIRECT", "req-1")
        response_event = create_response_event("req-1", 200, {}, "", 0, 0.1)
        error_event = create_error_event("network", "Test error")
        
        self.event_system.send_event(request_event)
        self.event_system.send_event(response_event)
        self.event_system.send_event(error_event)
        
        # Process events
        processed = self.event_system.process_batch(max_events=10)
        
        # Only request event should be processed
        self.assertEqual(len(self.received_events), 1)
        self.assertEqual(self.received_events[0].event_type, EventType.REQUEST)
    
    def test_url_pattern_filtering(self):
        """Test URL pattern filtering."""
        # Set up filter for specific URL patterns
        self.event_system.set_event_filter(url_patterns=["*google.com*", "*github.com*"])
        self.event_system.add_request_handler(self._event_handler)
        
        # Send events with different URLs
        events = [
            create_request_event("http://google.com", "GET", "DIRECT", "req-1"),
            create_request_event("http://github.com/user/repo", "GET", "DIRECT", "req-2"),
            create_request_event("http://example.com", "GET", "DIRECT", "req-3"),
            create_request_event("http://api.google.com", "GET", "DIRECT", "req-4")
        ]
        
        for event in events:
            self.event_system.send_event(event)
        
        # Process events
        self.event_system.process_batch(max_events=10)
        
        # Should only receive events matching patterns
        self.assertEqual(len(self.received_events), 3)  # google.com, github.com, api.google.com
        
        received_urls = [event.url for event in self.received_events]
        
        self.assertIn("http://google.com", received_urls)
        self.assertIn("http://github.com/user/repo", received_urls)
        self.assertIn("http://api.google.com", received_urls)
        self.assertNotIn("http://example.com", received_urls)
    
    def test_status_code_filtering(self):
        """Test status code filtering."""
        # Set up filter for error status codes
        self.event_system.set_event_filter(status_codes=[404, 500, 503])
        self.event_system.add_response_handler(self._event_handler)
        
        # Send response events with different status codes
        events = [
            create_response_event("req-1", 200, {}, "", 0, 0.1),
            create_response_event("req-2", 404, {}, "", 0, 0.1),
            create_response_event("req-3", 301, {}, "", 0, 0.1),
            create_response_event("req-4", 500, {}, "", 0, 0.1)
        ]
        
        for event in events:
            self.event_system.send_event(event)
        
        # Process events
        self.event_system.process_batch(max_events=10)
        
        # Should only receive error status codes
        self.assertEqual(len(self.received_events), 2)
        status_codes = [event.status_code for event in self.received_events]
        self.assertIn(404, status_codes)
        self.assertIn(500, status_codes)
        self.assertNotIn(200, status_codes)
        self.assertNotIn(301, status_codes)
    
    def test_proxy_type_filtering(self):
        """Test proxy type filtering."""
        # Set up filter for DIRECT connections only
        self.event_system.set_event_filter(proxy_types=["DIRECT"])
        self.event_system.add_request_handler(self._event_handler)
        
        # Send events with different proxy decisions
        events = [
            create_request_event("http://test1.com", "GET", "DIRECT", "req-1"),
            create_request_event("http://test2.com", "GET", "PROXY proxy:8080", "req-2"),
            create_request_event("http://test3.com", "GET", "DIRECT", "req-3")
        ]
        
        for event in events:
            self.event_system.send_event(event)
        
        # Process events
        self.event_system.process_batch(max_events=10)
        
        # Should only receive DIRECT connections
        self.assertEqual(len(self.received_events), 2)
        for event in self.received_events:
            self.assertEqual(event.proxy_decision, "DIRECT")
    
    def test_event_system_lifecycle(self):
        """Test event system start/stop lifecycle."""
        # System should not be running initially
        self.assertFalse(self.event_system.is_running())
        
        # Start system
        self.event_system.start()
        self.assertTrue(self.event_system.is_running())
        
        # Add handler and send event
        self.event_system.add_request_handler(self._event_handler)
        event = create_request_event("http://test.com", "GET", "DIRECT", "req-1")
        self.assertTrue(self.event_system.send_event(event))
        
        # Give some time for processing
        time.sleep(0.1)
        
        # Stop system
        self.event_system.stop()
        self.assertFalse(self.event_system.is_running())
    
    def test_event_statistics(self):
        """Test event system statistics."""
        # Add handler
        self.event_system.add_request_handler(self._event_handler)
        
        # Send some events
        for i in range(5):
            event = create_request_event(f"http://test{i}.com", "GET", "DIRECT", f"req-{i}")
            self.event_system.send_event(event)
        
        # Process events
        processed = self.event_system.process_batch(max_events=10)
        self.assertEqual(processed, 5)
        
        # Check statistics
        stats = self.event_system.get_stats()
        self.assertIn('events_processed', stats)
        self.assertIn('queue_stats', stats)
        self.assertEqual(stats['events_processed'], 5)


if __name__ == '__main__':
    unittest.main()