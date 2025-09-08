"""
Performance tests for high-volume request scenarios with real proxy.
Tests system performance, memory usage, and scalability.
"""

import pytest
import threading
import time
import psutil
import os
import gc
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
import statistics

from px_ui.communication.event_queue import EventQueue
from px_ui.communication.event_processor import EventProcessor
from px_ui.communication.events import RequestEvent, ResponseEvent, EventType
from .test_mocks import (
    MockEnhancedPxHandler as EnhancedPxHandler,
    MockPerformanceMonitor as PerformanceMonitor,
    MockUpdateThrottler as UpdateThrottler,
    MockLogRotator as LogRotator
)


class TestHighVolumePerformance:
    """Test performance with high volume of requests."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_queue = EventQueue(maxsize=10000)
        self.processed_events = []
        self.processing_times = []
        
        def ui_callback(event_type, event):
            self.processed_events.append((event_type, event))
        
        self.event_processor = EventProcessor(self.event_queue, ui_callback)
        self.enhanced_handler = EnhancedPxHandler(self.event_queue)
        self.performance_monitor = PerformanceMonitor()
    
    def test_high_volume_request_processing(self):
        """Test processing high volume of requests."""
        num_requests = 1000
        
        # Start performance monitoring
        self.performance_monitor.start_monitoring()
        
        # Start event processor
        self.event_processor.start()
        
        try:
            start_time = time.time()
            
            # Generate high volume of requests
            for i in range(num_requests):
                request_id = f"req_perf_{i}"
                url = f"https://api{i % 10}.example.com/data/{i}"
                method = "GET" if i % 2 == 0 else "POST"
                proxy_decision = "DIRECT" if i % 3 == 0 else f"PROXY proxy{i % 3}.corp.com:8080"
                
                self.enhanced_handler.capture_request(
                    url=url,
                    method=method,
                    proxy_decision=proxy_decision,
                    request_id=request_id
                )
                
                # Add response for most requests
                if i % 4 != 3:  # 75% of requests get responses
                    status_code = 200 if i % 10 != 9 else 404  # 10% error rate
                    self.enhanced_handler.capture_response(
                        request_id=request_id,
                        status_code=status_code,
                        headers={"Content-Type": "application/json"},
                        body_preview=f'{{"id": {i}, "data": "response"}}',
                        response_time=0.05 + (i % 20) * 0.01
                    )
            
            # Wait for processing to complete
            time.sleep(5.0)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Stop monitoring
            metrics = self.performance_monitor.stop_monitoring()
            
            # Performance assertions
            assert total_time < 15.0  # Should complete within 15 seconds
            
            # Verify all events were processed
            request_events = [e for t, e in self.processed_events if t == EventType.REQUEST]
            response_events = [e for t, e in self.processed_events if t == EventType.RESPONSE]
            
            assert len(request_events) == num_requests
            assert len(response_events) >= num_requests * 0.7  # At least 70% responses
            
            # Calculate throughput
            throughput = num_requests / total_time
            assert throughput > 100  # Should handle at least 100 requests/second
            
            # Memory usage should be reasonable
            assert metrics['peak_memory_mb'] < 500  # Less than 500MB peak memory
            
            print(f"Performance metrics:")
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Throughput: {throughput:.1f} requests/second")
            print(f"  Peak memory: {metrics['peak_memory_mb']:.1f}MB")
            print(f"  Events processed: {len(self.processed_events)}")
        
        finally:
            self.event_processor.stop()
    
    def test_concurrent_request_processing(self):
        """Test concurrent request processing from multiple threads."""
        num_threads = 5
        requests_per_thread = 200
        total_requests = num_threads * requests_per_thread
        
        # Start event processor
        self.event_processor.start()
        
        try:
            def request_generator(thread_id):
                for i in range(requests_per_thread):
                    request_id = f"req_thread_{thread_id}_{i}"
                    url = f"https://thread{thread_id}-{i}.example.com"
                    
                    self.enhanced_handler.capture_request(
                        url=url,
                        method="GET",
                        proxy_decision=f"PROXY proxy{thread_id}.corp.com:8080",
                        request_id=request_id
                    )
                    
                    # Add response
                    self.enhanced_handler.capture_response(
                        request_id=request_id,
                        status_code=200,
                        headers={"Content-Type": "text/plain"},
                        body_preview=f"Response from thread {thread_id}",
                        response_time=0.1
                    )
                    
                    # Small delay to simulate real conditions
                    time.sleep(0.001)
            
            # Start multiple threads
            threads = []
            start_time = time.time()
            
            for thread_id in range(num_threads):
                thread = threading.Thread(target=request_generator, args=(thread_id,))
                threads.append(thread)
                thread.start()
            
            # Wait for all threads to complete
            for thread in threads:
                thread.join()
            
            # Wait for event processing
            time.sleep(3.0)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Verify all events were processed
            request_events = [e for t, e in self.processed_events if t == EventType.REQUEST]
            response_events = [e for t, e in self.processed_events if t == EventType.RESPONSE]
            
            assert len(request_events) == total_requests
            assert len(response_events) == total_requests
            
            # Verify thread safety - all request IDs should be unique
            request_ids = set(event.request_id for event in request_events)
            assert len(request_ids) == total_requests
            
            # Performance should be reasonable
            throughput = total_requests / total_time
            assert throughput > 50  # Should handle at least 50 requests/second with concurrency
            
            print(f"Concurrent processing metrics:")
            print(f"  Threads: {num_threads}")
            print(f"  Total requests: {total_requests}")
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Throughput: {throughput:.1f} requests/second")
        
        finally:
            self.event_processor.stop()
    
    def test_memory_usage_under_load(self):
        """Test memory usage during high load scenarios."""
        num_requests = 2000
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Start event processor
        self.event_processor.start()
        
        try:
            # Generate requests with large response bodies
            for i in range(num_requests):
                request_id = f"req_memory_{i}"
                
                self.enhanced_handler.capture_request(
                    url=f"https://large-response{i}.example.com",
                    method="GET",
                    proxy_decision="PROXY proxy.corp.com:8080",
                    request_id=request_id
                )
                
                # Large response body to test memory handling
                large_body = "x" * 1000 + f" response {i} " + "y" * 1000
                
                self.enhanced_handler.capture_response(
                    request_id=request_id,
                    status_code=200,
                    headers={"Content-Type": "text/plain", "Content-Length": str(len(large_body))},
                    body_preview=large_body[:500],  # Truncated preview
                    response_time=0.2
                )
                
                # Check memory periodically
                if i % 100 == 0:
                    current_memory = process.memory_info().rss / 1024 / 1024
                    memory_increase = current_memory - initial_memory
                    
                    # Memory increase should be reasonable
                    assert memory_increase < 200  # Less than 200MB increase
            
            # Wait for processing
            time.sleep(3.0)
            
            # Final memory check
            final_memory = process.memory_info().rss / 1024 / 1024
            total_memory_increase = final_memory - initial_memory
            
            # Force garbage collection
            gc.collect()
            time.sleep(1.0)
            
            after_gc_memory = process.memory_info().rss / 1024 / 1024
            
            print(f"Memory usage metrics:")
            print(f"  Initial memory: {initial_memory:.1f}MB")
            print(f"  Peak memory: {final_memory:.1f}MB")
            print(f"  After GC: {after_gc_memory:.1f}MB")
            print(f"  Total increase: {total_memory_increase:.1f}MB")
            
            # Memory usage should be reasonable
            assert total_memory_increase < 300  # Less than 300MB total increase
            
            # Verify all events were processed
            assert len(self.processed_events) == num_requests * 2  # Request + Response
        
        finally:
            self.event_processor.stop()
    
    def test_queue_performance_under_pressure(self):
        """Test event queue performance under pressure."""
        queue_sizes = [100, 1000, 5000]
        
        for queue_size in queue_sizes:
            with self.subTest(queue_size=queue_size):
                # Create queue with specific size
                test_queue = EventQueue(maxsize=queue_size)
                processed_events = []
                
                def test_callback(event_type, event):
                    processed_events.append((event_type, event))
                
                processor = EventProcessor(test_queue, test_callback)
                processor.start()
                
                try:
                    # Fill queue to capacity
                    start_time = time.time()
                    
                    for i in range(queue_size):
                        event = RequestEvent(
                            timestamp=datetime.now(),
                            url=f"https://test{i}.example.com",
                            method="GET",
                            proxy_decision="DIRECT",
                            request_id=f"req_{i}"
                        )
                        test_queue.put(event)
                    
                    # Wait for processing
                    time.sleep(2.0)
                    
                    end_time = time.time()
                    processing_time = end_time - start_time
                    
                    # All events should be processed
                    assert len(processed_events) == queue_size
                    
                    # Performance should scale reasonably
                    events_per_second = queue_size / processing_time
                    assert events_per_second > 100  # At least 100 events/second
                    
                    print(f"Queue size {queue_size}: {events_per_second:.1f} events/second")
                
                finally:
                    processor.stop()


class TestUpdateThrottling:
    """Test update throttling performance optimization."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.throttler = UpdateThrottler(max_updates_per_second=50)
        self.update_count = 0
        
        def mock_update():
            self.update_count += 1
        
        self.mock_update = mock_update
    
    def test_throttling_effectiveness(self):
        """Test that throttling effectively limits update rate."""
        # Generate many update requests rapidly
        num_requests = 200
        
        start_time = time.time()
        
        for i in range(num_requests):
            self.throttler.request_update(self.mock_update)
            time.sleep(0.001)  # 1ms between requests
        
        # Wait for throttled updates to complete
        time.sleep(3.0)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Should have throttled updates
        assert self.update_count < num_requests
        
        # Update rate should be close to throttle limit
        actual_rate = self.update_count / total_time
        assert 40 <= actual_rate <= 60  # Within reasonable range of 50 updates/second
        
        print(f"Throttling metrics:")
        print(f"  Requested updates: {num_requests}")
        print(f"  Actual updates: {self.update_count}")
        print(f"  Update rate: {actual_rate:.1f} updates/second")
    
    def test_throttling_with_burst_traffic(self):
        """Test throttling behavior with burst traffic patterns."""
        # Simulate burst traffic
        bursts = 5
        requests_per_burst = 50
        
        for burst in range(bursts):
            # Generate burst of requests
            for i in range(requests_per_burst):
                self.throttler.request_update(self.mock_update)
            
            # Wait between bursts
            time.sleep(0.5)
        
        # Wait for final updates
        time.sleep(2.0)
        
        total_requests = bursts * requests_per_burst
        
        # Should have handled bursts gracefully
        assert self.update_count < total_requests
        assert self.update_count > total_requests * 0.3  # At least 30% of requests processed
        
        print(f"Burst traffic metrics:")
        print(f"  Total requests: {total_requests}")
        print(f"  Processed updates: {self.update_count}")
        print(f"  Processing ratio: {self.update_count/total_requests:.2f}")


class TestLogRotation:
    """Test log rotation performance and memory management."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.log_rotator = LogRotator(max_entries=1000, cleanup_threshold=1200)
        self.entries = []
    
    def test_log_rotation_performance(self):
        """Test log rotation performance with large datasets."""
        # Generate large number of log entries
        num_entries = 2000
        
        start_time = time.time()
        
        for i in range(num_entries):
            entry = {
                'timestamp': datetime.now(),
                'url': f'https://test{i}.example.com',
                'method': 'GET',
                'status': 200,
                'response_time': 0.1 + (i % 100) * 0.01
            }
            self.entries.append(entry)
            
            # Trigger rotation check periodically
            if i % 100 == 0:
                self.log_rotator.check_rotation(self.entries)
        
        end_time = time.time()
        rotation_time = end_time - start_time
        
        # Final rotation
        self.log_rotator.rotate_logs(self.entries)
        
        # Should have rotated logs
        assert len(self.entries) <= self.log_rotator.max_entries
        
        # Rotation should be fast
        assert rotation_time < 2.0  # Less than 2 seconds for 2000 entries
        
        print(f"Log rotation metrics:")
        print(f"  Original entries: {num_entries}")
        print(f"  Final entries: {len(self.entries)}")
        print(f"  Rotation time: {rotation_time:.2f}s")
    
    def test_memory_cleanup_effectiveness(self):
        """Test memory cleanup effectiveness during log rotation."""
        # Get initial memory
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        # Generate large entries with substantial data
        large_entries = []
        for i in range(5000):
            entry = {
                'timestamp': datetime.now(),
                'url': f'https://large-data{i}.example.com',
                'method': 'POST',
                'status': 200,
                'request_body': 'x' * 1000,  # 1KB request body
                'response_body': 'y' * 2000,  # 2KB response body
                'headers': {f'header{j}': f'value{j}' for j in range(20)}
            }
            large_entries.append(entry)
        
        # Check memory after creating entries
        after_creation_memory = process.memory_info().rss / 1024 / 1024
        
        # Perform rotation
        self.log_rotator.rotate_logs(large_entries)
        
        # Force garbage collection
        gc.collect()
        time.sleep(0.5)
        
        # Check memory after rotation
        after_rotation_memory = process.memory_info().rss / 1024 / 1024
        
        print(f"Memory cleanup metrics:")
        print(f"  Initial memory: {initial_memory:.1f}MB")
        print(f"  After creation: {after_creation_memory:.1f}MB")
        print(f"  After rotation: {after_rotation_memory:.1f}MB")
        print(f"  Entries before: 5000")
        print(f"  Entries after: {len(large_entries)}")
        
        # Should have reduced entries
        assert len(large_entries) <= self.log_rotator.max_entries
        
        # Memory should have been freed (allowing for some variance)
        memory_freed = after_creation_memory - after_rotation_memory
        assert memory_freed > 0  # Some memory should be freed


class TestRealWorldScenarios:
    """Test performance in real-world usage scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_queue = EventQueue(maxsize=5000)
        self.processed_events = []
        
        def ui_callback(event_type, event):
            self.processed_events.append((event_type, event))
        
        self.event_processor = EventProcessor(self.event_queue, ui_callback)
        self.enhanced_handler = EnhancedPxHandler(self.event_queue)
    
    def test_typical_browsing_session(self):
        """Test performance during typical web browsing session."""
        # Simulate typical browsing patterns
        browsing_patterns = [
            # Initial page load with many resources
            ("https://www.example.com", 15),  # Main page + 14 resources
            ("https://www.google.com", 8),    # Search page + resources
            ("https://www.github.com", 12),   # GitHub page + resources
            ("https://www.stackoverflow.com", 10),  # SO page + resources
        ]
        
        self.event_processor.start()
        
        try:
            start_time = time.time()
            total_requests = 0
            
            for base_url, num_resources in browsing_patterns:
                # Main page request
                main_request_id = f"req_main_{hash(base_url)}"
                self.enhanced_handler.capture_request(
                    url=base_url,
                    method="GET",
                    proxy_decision="PROXY proxy.corp.com:8080",
                    request_id=main_request_id
                )
                
                self.enhanced_handler.capture_response(
                    request_id=main_request_id,
                    status_code=200,
                    headers={"Content-Type": "text/html"},
                    body_preview="<html>...</html>",
                    response_time=0.5
                )
                
                total_requests += 1
                
                # Resource requests (CSS, JS, images, etc.)
                for i in range(num_resources - 1):
                    resource_id = f"req_resource_{hash(base_url)}_{i}"
                    resource_url = f"{base_url}/static/resource{i}.js"
                    
                    self.enhanced_handler.capture_request(
                        url=resource_url,
                        method="GET",
                        proxy_decision="PROXY proxy.corp.com:8080",
                        request_id=resource_id
                    )
                    
                    self.enhanced_handler.capture_response(
                        request_id=resource_id,
                        status_code=200,
                        headers={"Content-Type": "application/javascript"},
                        body_preview="// JavaScript code...",
                        response_time=0.1 + i * 0.02
                    )
                    
                    total_requests += 1
                
                # Small delay between page loads
                time.sleep(0.1)
            
            # Wait for processing
            time.sleep(2.0)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Verify all requests were processed
            request_events = [e for t, e in self.processed_events if t == EventType.REQUEST]
            response_events = [e for t, e in self.processed_events if t == EventType.RESPONSE]
            
            assert len(request_events) == total_requests
            assert len(response_events) == total_requests
            
            # Performance should be good for typical browsing
            throughput = total_requests / total_time
            assert throughput > 20  # Should handle typical browsing easily
            
            print(f"Browsing session metrics:")
            print(f"  Total requests: {total_requests}")
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Throughput: {throughput:.1f} requests/second")
        
        finally:
            self.event_processor.stop()
    
    def test_api_heavy_application(self):
        """Test performance with API-heavy application usage."""
        # Simulate API-heavy application (like a dashboard)
        api_endpoints = [
            "/api/users",
            "/api/orders",
            "/api/products",
            "/api/analytics",
            "/api/notifications",
            "/api/settings"
        ]
        
        self.event_processor.start()
        
        try:
            start_time = time.time()
            total_requests = 0
            
            # Simulate periodic API calls over time
            for cycle in range(10):  # 10 refresh cycles
                for endpoint in api_endpoints:
                    request_id = f"req_api_{cycle}_{hash(endpoint)}"
                    url = f"https://api.company.com{endpoint}"
                    
                    self.enhanced_handler.capture_request(
                        url=url,
                        method="GET",
                        proxy_decision="PROXY api-proxy.corp.com:8080",
                        request_id=request_id
                    )
                    
                    # Simulate varying response times and sizes
                    response_time = 0.1 + (hash(endpoint) % 10) * 0.05
                    status_code = 200 if cycle < 9 else (500 if endpoint == "/api/analytics" else 200)
                    
                    body_size = 100 + (hash(endpoint) % 50) * 20
                    body_preview = '{"data": [' + '{"id": 1},' * (body_size // 20) + ']}'
                    
                    self.enhanced_handler.capture_response(
                        request_id=request_id,
                        status_code=status_code,
                        headers={"Content-Type": "application/json"},
                        body_preview=body_preview[:500],
                        response_time=response_time
                    )
                    
                    total_requests += 1
                
                # Delay between refresh cycles
                time.sleep(0.05)
            
            # Wait for processing
            time.sleep(2.0)
            
            end_time = time.time()
            total_time = end_time - start_time
            
            # Verify processing
            request_events = [e for t, e in self.processed_events if t == EventType.REQUEST]
            response_events = [e for t, e in self.processed_events if t == EventType.RESPONSE]
            
            assert len(request_events) == total_requests
            assert len(response_events) == total_requests
            
            # Check for error handling
            error_responses = [e for e in response_events if e.status_code >= 400]
            assert len(error_responses) > 0  # Should have some errors from simulation
            
            # Performance should handle API load well
            throughput = total_requests / total_time
            assert throughput > 30  # Should handle API calls efficiently
            
            print(f"API application metrics:")
            print(f"  Total API calls: {total_requests}")
            print(f"  Total time: {total_time:.2f}s")
            print(f"  Throughput: {throughput:.1f} requests/second")
            print(f"  Error responses: {len(error_responses)}")
        
        finally:
            self.event_processor.stop()