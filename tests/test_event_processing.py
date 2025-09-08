"""
Unit tests for event processing system.
Tests event queue operations, event processing, and UI update mechanisms.
"""

import pytest
import threading
import time
import queue
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from px_ui.communication.event_queue import EventQueue
from px_ui.communication.event_processor import EventProcessor
from px_ui.communication.events import (
    RequestEvent, ResponseEvent, ErrorEvent, StatusEvent, EventType
)


class TestEventQueue:
    """Test EventQueue functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_queue = EventQueue(maxsize=100)
    
    def test_event_queue_creation(self):
        """Test EventQueue creation with default and custom sizes."""
        # Default size
        default_queue = EventQueue()
        assert default_queue.maxsize == 1000
        
        # Custom size
        custom_queue = EventQueue(maxsize=50)
        assert custom_queue.maxsize == 50
    
    def test_put_and_get_event(self):
        """Test putting and getting events from queue."""
        event = RequestEvent(
            timestamp=datetime.now(),
            url="https://example.com",
            method="GET",
            proxy_decision="DIRECT",
            request_id="req_123"
        )
        
        self.event_queue.put(event)
        retrieved_event = self.event_queue.get(timeout=1.0)
        
        assert retrieved_event == event
        assert retrieved_event.url == "https://example.com"
        assert retrieved_event.method == "GET"
    
    def test_queue_empty_timeout(self):
        """Test getting from empty queue with timeout."""
        with pytest.raises(queue.Empty):
            self.event_queue.get(timeout=0.1)
    
    def test_queue_full_behavior(self):
        """Test queue behavior when full."""
        small_queue = EventQueue(maxsize=2)
        
        # Fill the queue
        event1 = RequestEvent(datetime.now(), "http://test1.com", "GET", "DIRECT", "req_1")
        event2 = RequestEvent(datetime.now(), "http://test2.com", "GET", "DIRECT", "req_2")
        
        small_queue.put(event1)
        small_queue.put(event2)
        
        # Queue should be full
        assert small_queue.qsize() == 2
        
        # Adding another event should either block or raise exception
        event3 = RequestEvent(datetime.now(), "http://test3.com", "GET", "DIRECT", "req_3")
        with pytest.raises(queue.Full):
            small_queue.put(event3, timeout=0.1)
    
    def test_queue_thread_safety(self):
        """Test queue thread safety with concurrent access."""
        events_to_send = 50
        received_events = []
        
        def producer():
            for i in range(events_to_send):
                event = RequestEvent(
                    timestamp=datetime.now(),
                    url=f"https://example{i}.com",
                    method="GET",
                    proxy_decision="DIRECT",
                    request_id=f"req_{i}"
                )
                self.event_queue.put(event)
                time.sleep(0.001)  # Small delay to simulate real conditions
        
        def consumer():
            while len(received_events) < events_to_send:
                try:
                    event = self.event_queue.get(timeout=1.0)
                    received_events.append(event)
                except queue.Empty:
                    break
        
        # Start producer and consumer threads
        producer_thread = threading.Thread(target=producer)
        consumer_thread = threading.Thread(target=consumer)
        
        producer_thread.start()
        consumer_thread.start()
        
        producer_thread.join()
        consumer_thread.join()
        
        # All events should be received
        assert len(received_events) == events_to_send
        
        # Verify event order and content
        for i, event in enumerate(received_events):
            assert event.request_id == f"req_{i}"
            assert event.url == f"https://example{i}.com"
    
    def test_queue_size_monitoring(self):
        """Test queue size monitoring."""
        assert self.event_queue.qsize() == 0
        assert self.event_queue.empty() is True
        assert self.event_queue.full() is False
        
        # Add some events
        for i in range(5):
            event = RequestEvent(datetime.now(), f"http://test{i}.com", "GET", "DIRECT", f"req_{i}")
            self.event_queue.put(event)
        
        assert self.event_queue.qsize() == 5
        assert self.event_queue.empty() is False
        assert self.event_queue.full() is False
        
        # Remove events
        for i in range(5):
            self.event_queue.get()
        
        assert self.event_queue.qsize() == 0
        assert self.event_queue.empty() is True


class TestEventProcessor:
    """Test EventProcessor functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_queue = EventQueue()
        self.mock_ui_callback = Mock()
        self.processor = EventProcessor(self.event_queue, self.mock_ui_callback)
    
    def test_event_processor_creation(self):
        """Test EventProcessor creation."""
        assert self.processor.event_queue == self.event_queue
        assert self.processor.ui_callback == self.mock_ui_callback
        assert self.processor.running is False
    
    def test_process_request_event(self):
        """Test processing RequestEvent."""
        event = RequestEvent(
            timestamp=datetime.now(),
            url="https://api.example.com",
            method="POST",
            proxy_decision="PROXY proxy.corp.com:8080",
            request_id="req_456"
        )
        
        self.event_queue.put(event)
        self.processor.process_events()
        
        # Verify UI callback was called
        self.mock_ui_callback.assert_called_once()
        call_args = self.mock_ui_callback.call_args[0]
        assert call_args[0] == EventType.REQUEST
        assert call_args[1] == event
    
    def test_process_response_event(self):
        """Test processing ResponseEvent."""
        event = ResponseEvent(
            timestamp=datetime.now(),
            request_id="req_456",
            status_code=200,
            headers={"Content-Type": "application/json"},
            body_preview='{"status": "success"}',
            response_time=0.25
        )
        
        self.event_queue.put(event)
        self.processor.process_events()
        
        self.mock_ui_callback.assert_called_once()
        call_args = self.mock_ui_callback.call_args[0]
        assert call_args[0] == EventType.RESPONSE
        assert call_args[1] == event
    
    def test_process_error_event(self):
        """Test processing ErrorEvent."""
        event = ErrorEvent(
            timestamp=datetime.now(),
            error_type="NetworkError",
            message="Connection timeout",
            details={"timeout": 30, "host": "example.com"},
            request_id="req_789"
        )
        
        self.event_queue.put(event)
        self.processor.process_events()
        
        self.mock_ui_callback.assert_called_once()
        call_args = self.mock_ui_callback.call_args[0]
        assert call_args[0] == EventType.ERROR
        assert call_args[1] == event
    
    def test_process_status_event(self):
        """Test processing StatusEvent."""
        event = StatusEvent(
            timestamp=datetime.now(),
            status="proxy_started",
            message="Proxy server started on port 3128",
            details={"port": 3128, "address": "127.0.0.1"}
        )
        
        self.event_queue.put(event)
        self.processor.process_events()
        
        self.mock_ui_callback.assert_called_once()
        call_args = self.mock_ui_callback.call_args[0]
        assert call_args[0] == EventType.STATUS
        assert call_args[1] == event
    
    def test_process_multiple_events(self):
        """Test processing multiple events in sequence."""
        events = [
            RequestEvent(datetime.now(), "http://test1.com", "GET", "DIRECT", "req_1"),
            ResponseEvent(datetime.now(), "req_1", 200, {}, "OK", 0.1),
            RequestEvent(datetime.now(), "http://test2.com", "POST", "PROXY proxy:8080", "req_2"),
            ErrorEvent(datetime.now(), "AuthError", "401 Unauthorized", {}, "req_2")
        ]
        
        for event in events:
            self.event_queue.put(event)
        
        self.processor.process_events()
        
        # Should have called UI callback for each event
        assert self.mock_ui_callback.call_count == 4
    
    def test_continuous_processing(self):
        """Test continuous event processing in background thread."""
        processed_events = []
        
        def mock_callback(event_type, event):
            processed_events.append((event_type, event))
        
        processor = EventProcessor(self.event_queue, mock_callback)
        
        # Start continuous processing
        processor.start()
        
        try:
            # Add events while processor is running
            events = [
                RequestEvent(datetime.now(), f"http://test{i}.com", "GET", "DIRECT", f"req_{i}")
                for i in range(10)
            ]
            
            for event in events:
                self.event_queue.put(event)
                time.sleep(0.01)  # Small delay
            
            # Wait for processing
            time.sleep(0.5)
            
            # All events should be processed
            assert len(processed_events) == 10
            
            for i, (event_type, event) in enumerate(processed_events):
                assert event_type == EventType.REQUEST
                assert event.request_id == f"req_{i}"
        
        finally:
            processor.stop()
    
    def test_processor_error_handling(self):
        """Test processor error handling when UI callback fails."""
        def failing_callback(event_type, event):
            raise Exception("UI callback failed")
        
        processor = EventProcessor(self.event_queue, failing_callback)
        
        event = RequestEvent(datetime.now(), "http://test.com", "GET", "DIRECT", "req_1")
        self.event_queue.put(event)
        
        # Should not raise exception, should handle gracefully
        processor.process_events()
        
        # Queue should be empty (event was processed despite callback failure)
        assert self.event_queue.empty()
    
    def test_processor_performance(self):
        """Test processor performance with high event volume."""
        processed_count = 0
        
        def counting_callback(event_type, event):
            nonlocal processed_count
            processed_count += 1
        
        processor = EventProcessor(self.event_queue, counting_callback)
        
        # Add many events
        num_events = 1000
        start_time = time.time()
        
        for i in range(num_events):
            event = RequestEvent(datetime.now(), f"http://test{i}.com", "GET", "DIRECT", f"req_{i}")
            self.event_queue.put(event)
        
        # Process all events
        processor.process_events()
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # All events should be processed
        assert processed_count == num_events
        
        # Should process reasonably fast (less than 1 second for 1000 events)
        assert processing_time < 1.0
        
        # Calculate events per second
        events_per_second = num_events / processing_time
        assert events_per_second > 500  # Should handle at least 500 events/second


class TestEventTypes:
    """Test event type classes and their functionality."""
    
    def test_request_event_creation(self):
        """Test RequestEvent creation and attributes."""
        timestamp = datetime.now()
        event = RequestEvent(
            timestamp=timestamp,
            url="https://api.example.com/users",
            method="GET",
            proxy_decision="PROXY proxy.corp.com:8080",
            request_id="req_123"
        )
        
        assert event.timestamp == timestamp
        assert event.url == "https://api.example.com/users"
        assert event.method == "GET"
        assert event.proxy_decision == "PROXY proxy.corp.com:8080"
        assert event.request_id == "req_123"
        assert event.event_type == EventType.REQUEST
    
    def test_response_event_creation(self):
        """Test ResponseEvent creation and attributes."""
        timestamp = datetime.now()
        headers = {"Content-Type": "application/json", "Content-Length": "256"}
        
        event = ResponseEvent(
            timestamp=timestamp,
            request_id="req_123",
            status_code=200,
            headers=headers,
            body_preview='{"users": []}',
            response_time=0.5
        )
        
        assert event.timestamp == timestamp
        assert event.request_id == "req_123"
        assert event.status_code == 200
        assert event.headers == headers
        assert event.body_preview == '{"users": []}'
        assert event.response_time == 0.5
        assert event.event_type == EventType.RESPONSE
    
    def test_error_event_creation(self):
        """Test ErrorEvent creation and attributes."""
        timestamp = datetime.now()
        details = {"timeout": 30, "retry_count": 3}
        
        event = ErrorEvent(
            timestamp=timestamp,
            error_type="TimeoutError",
            message="Request timed out after 30 seconds",
            details=details,
            request_id="req_456"
        )
        
        assert event.timestamp == timestamp
        assert event.error_type == "TimeoutError"
        assert event.message == "Request timed out after 30 seconds"
        assert event.details == details
        assert event.request_id == "req_456"
        assert event.event_type == EventType.ERROR
    
    def test_status_event_creation(self):
        """Test StatusEvent creation and attributes."""
        timestamp = datetime.now()
        details = {"port": 3128, "mode": "pac"}
        
        event = StatusEvent(
            timestamp=timestamp,
            status="proxy_started",
            message="Proxy server started successfully",
            details=details
        )
        
        assert event.timestamp == timestamp
        assert event.status == "proxy_started"
        assert event.message == "Proxy server started successfully"
        assert event.details == details
        assert event.event_type == EventType.STATUS
    
    def test_event_equality(self):
        """Test event equality comparison."""
        timestamp = datetime.now()
        
        event1 = RequestEvent(timestamp, "http://test.com", "GET", "DIRECT", "req_1")
        event2 = RequestEvent(timestamp, "http://test.com", "GET", "DIRECT", "req_1")
        event3 = RequestEvent(timestamp, "http://other.com", "GET", "DIRECT", "req_1")
        
        assert event1 == event2
        assert event1 != event3
    
    def test_event_string_representation(self):
        """Test event string representation."""
        event = RequestEvent(
            datetime.now(),
            "https://example.com",
            "POST",
            "PROXY proxy:8080",
            "req_123"
        )
        
        event_str = str(event)
        assert "RequestEvent" in event_str
        assert "https://example.com" in event_str
        assert "POST" in event_str
        assert "req_123" in event_str


class TestEventSystemIntegration:
    """Test integration between event system components."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_queue = EventQueue()
        self.processed_events = []
        
        def ui_callback(event_type, event):
            self.processed_events.append((event_type, event))
        
        self.processor = EventProcessor(self.event_queue, ui_callback)
    
    def test_full_request_response_cycle(self):
        """Test complete request-response event cycle."""
        request_id = "req_integration_test"
        
        # Create request event
        request_event = RequestEvent(
            timestamp=datetime.now(),
            url="https://api.example.com/data",
            method="GET",
            proxy_decision="PROXY proxy.corp.com:8080",
            request_id=request_id
        )
        
        # Create response event
        response_event = ResponseEvent(
            timestamp=datetime.now(),
            request_id=request_id,
            status_code=200,
            headers={"Content-Type": "application/json"},
            body_preview='{"data": "success"}',
            response_time=0.3
        )
        
        # Add events to queue
        self.event_queue.put(request_event)
        self.event_queue.put(response_event)
        
        # Process events
        self.processor.process_events()
        
        # Verify both events were processed
        assert len(self.processed_events) == 2
        
        # Verify request event
        req_type, req_event = self.processed_events[0]
        assert req_type == EventType.REQUEST
        assert req_event.request_id == request_id
        assert req_event.url == "https://api.example.com/data"
        
        # Verify response event
        resp_type, resp_event = self.processed_events[1]
        assert resp_type == EventType.RESPONSE
        assert resp_event.request_id == request_id
        assert resp_event.status_code == 200
    
    def test_error_handling_in_request_cycle(self):
        """Test error handling during request processing."""
        request_id = "req_error_test"
        
        # Create request event
        request_event = RequestEvent(
            timestamp=datetime.now(),
            url="https://timeout.example.com",
            method="GET",
            proxy_decision="PROXY proxy.corp.com:8080",
            request_id=request_id
        )
        
        # Create error event instead of response
        error_event = ErrorEvent(
            timestamp=datetime.now(),
            error_type="TimeoutError",
            message="Connection timed out",
            details={"timeout": 30},
            request_id=request_id
        )
        
        # Add events to queue
        self.event_queue.put(request_event)
        self.event_queue.put(error_event)
        
        # Process events
        self.processor.process_events()
        
        # Verify both events were processed
        assert len(self.processed_events) == 2
        
        # Verify error event
        error_type, error_evt = self.processed_events[1]
        assert error_type == EventType.ERROR
        assert error_evt.request_id == request_id
        assert error_evt.error_type == "TimeoutError"
    
    def test_concurrent_event_processing(self):
        """Test concurrent event processing from multiple sources."""
        num_producers = 3
        events_per_producer = 20
        
        def producer(producer_id):
            for i in range(events_per_producer):
                event = RequestEvent(
                    timestamp=datetime.now(),
                    url=f"https://producer{producer_id}-{i}.com",
                    method="GET",
                    proxy_decision="DIRECT",
                    request_id=f"req_{producer_id}_{i}"
                )
                self.event_queue.put(event)
                time.sleep(0.001)  # Small delay
        
        # Start multiple producer threads
        threads = []
        for i in range(num_producers):
            thread = threading.Thread(target=producer, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Start processor
        self.processor.start()
        
        try:
            # Wait for all producers to finish
            for thread in threads:
                thread.join()
            
            # Wait for processing to complete
            time.sleep(0.5)
            
            # All events should be processed
            expected_events = num_producers * events_per_producer
            assert len(self.processed_events) == expected_events
            
            # Verify all request IDs are unique and present
            request_ids = set()
            for event_type, event in self.processed_events:
                assert event_type == EventType.REQUEST
                request_ids.add(event.request_id)
            
            assert len(request_ids) == expected_events
        
        finally:
            self.processor.stop()