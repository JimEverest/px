"""
Comprehensive integration tests for proxy-UI communication and configuration management.
Tests end-to-end workflows and component interactions.
"""

import pytest
import threading
import time
import tempfile
import os
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from px_ui.communication.event_queue import EventQueue
from px_ui.communication.event_processor import EventProcessor
from px_ui.communication.events import RequestEvent, ResponseEvent, EventType
from px_ui.models.pac_configuration import PACConfiguration
from px_ui.models.proxy_status import ProxyStatus
from .test_mocks import (
    MockEnhancedPxHandler as EnhancedPxHandler,
    MockConfigurationBridge as ConfigurationBridge,
    MockPACValidator as PACValidator
)


class TestProxyUIIntegration:
    """Test integration between proxy engine and UI components."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_queue = EventQueue()
        self.processed_events = []
        
        def ui_callback(event_type, event):
            self.processed_events.append((event_type, event))
        
        self.event_processor = EventProcessor(self.event_queue, ui_callback)
        self.enhanced_handler = EnhancedPxHandler(self.event_queue)
    
    def test_request_capture_and_ui_update(self):
        """Test request capture by proxy and UI update."""
        # Mock a request being processed
        test_url = "https://api.example.com/users"
        test_method = "GET"
        proxy_decision = "PROXY proxy.corp.com:8080"
        
        # Simulate request capture
        self.enhanced_handler.capture_request(
            url=test_url,
            method=test_method,
            proxy_decision=proxy_decision
        )
        
        # Process events
        self.event_processor.process_events()
        
        # Verify UI was updated
        assert len(self.processed_events) == 1
        event_type, event = self.processed_events[0]
        
        assert event_type == EventType.REQUEST
        assert event.url == test_url
        assert event.method == test_method
        assert event.proxy_decision == proxy_decision
    
    def test_response_capture_and_ui_update(self):
        """Test response capture by proxy and UI update."""
        request_id = "req_integration_123"
        
        # First capture request
        self.enhanced_handler.capture_request(
            url="https://api.example.com/data",
            method="POST",
            proxy_decision="DIRECT",
            request_id=request_id
        )
        
        # Then capture response
        self.enhanced_handler.capture_response(
            request_id=request_id,
            status_code=201,
            headers={"Content-Type": "application/json", "Location": "/data/123"},
            body_preview='{"id": 123, "status": "created"}',
            response_time=0.45
        )
        
        # Process events
        self.event_processor.process_events()
        
        # Verify both request and response events
        assert len(self.processed_events) == 2
        
        # Check request event
        req_type, req_event = self.processed_events[0]
        assert req_type == EventType.REQUEST
        assert req_event.request_id == request_id
        
        # Check response event
        resp_type, resp_event = self.processed_events[1]
        assert resp_type == EventType.RESPONSE
        assert resp_event.request_id == request_id
        assert resp_event.status_code == 201
        assert resp_event.headers["Content-Type"] == "application/json"
    
    def test_error_capture_and_ui_update(self):
        """Test error capture by proxy and UI update."""
        request_id = "req_error_123"
        
        # Capture request
        self.enhanced_handler.capture_request(
            url="https://timeout.example.com",
            method="GET",
            proxy_decision="PROXY slow-proxy.corp.com:8080",
            request_id=request_id
        )
        
        # Capture error
        self.enhanced_handler.capture_error(
            request_id=request_id,
            error_type="TimeoutError",
            message="Connection timed out after 30 seconds",
            details={"timeout": 30, "proxy": "slow-proxy.corp.com:8080"}
        )
        
        # Process events
        self.event_processor.process_events()
        
        # Verify request and error events
        assert len(self.processed_events) == 2
        
        # Check error event
        error_type, error_event = self.processed_events[1]
        assert error_type == EventType.ERROR
        assert error_event.request_id == request_id
        assert error_event.error_type == "TimeoutError"
        assert "timed out" in error_event.message
    
    def test_high_volume_request_processing(self):
        """Test handling high volume of requests."""
        num_requests = 100
        
        # Start event processor
        self.event_processor.start()
        
        try:
            # Generate many requests
            for i in range(num_requests):
                self.enhanced_handler.capture_request(
                    url=f"https://api{i}.example.com/data",
                    method="GET" if i % 2 == 0 else "POST",
                    proxy_decision="DIRECT" if i % 3 == 0 else f"PROXY proxy{i%3}.corp.com:8080",
                    request_id=f"req_{i}"
                )
                
                # Simulate some responses
                if i % 2 == 0:
                    self.enhanced_handler.capture_response(
                        request_id=f"req_{i}",
                        status_code=200,
                        headers={"Content-Type": "application/json"},
                        body_preview=f'{{"data": "response_{i}"}}',
                        response_time=0.1 + (i % 10) * 0.05
                    )
            
            # Wait for processing
            time.sleep(2.0)
            
            # Should have processed all events
            assert len(self.processed_events) >= num_requests
            
            # Verify request IDs are unique
            request_ids = set()
            for event_type, event in self.processed_events:
                if event_type == EventType.REQUEST:
                    request_ids.add(event.request_id)
            
            assert len(request_ids) == num_requests
        
        finally:
            self.event_processor.stop()


class TestConfigurationManagement:
    """Test configuration management and bridge functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config_bridge = ConfigurationBridge()
        self.pac_validator = PACValidator()
    
    def test_pac_configuration_validation_and_application(self):
        """Test PAC configuration validation and application to proxy."""
        pac_content = '''
        function FindProxyForURL(url, host) {
            if (dnsDomainIs(host, ".company.com")) {
                return "DIRECT";
            }
            if (shExpMatch(host, "*.google.com")) {
                return "PROXY proxy1.company.com:8080; PROXY proxy2.company.com:8080";
            }
            return "PROXY default-proxy.company.com:8080";
        }
        '''
        
        # Validate PAC configuration
        pac_config = self.pac_validator.create_pac_configuration(
            source_type="inline",
            source_path="",
            content=pac_content
        )
        
        assert pac_config.is_valid is True
        assert pac_config.validation_errors == []
        
        # Apply configuration through bridge
        success = self.config_bridge.apply_pac_configuration(pac_config)
        assert success is True
        
        # Test URL resolution
        test_cases = [
            ("http://intranet.company.com", "DIRECT"),
            ("https://www.google.com", "PROXY proxy1.company.com:8080"),
            ("http://external.example.com", "PROXY default-proxy.company.com:8080")
        ]
        
        for url, expected_proxy in test_cases:
            result = self.pac_validator.test_url(url, pac_content)
            assert expected_proxy in result
    
    def test_invalid_pac_configuration_handling(self):
        """Test handling of invalid PAC configuration."""
        invalid_pac = '''
        function FindProxyForURL(url, host) {
            return INVALID_SYNTAX;  // Missing quotes
        }
        '''
        
        # Validate PAC configuration
        pac_config = self.pac_validator.create_pac_configuration(
            source_type="inline",
            source_path="",
            content=invalid_pac
        )
        
        assert pac_config.is_valid is False
        assert len(pac_config.validation_errors) > 0
        
        # Attempt to apply invalid configuration
        success = self.config_bridge.apply_pac_configuration(pac_config)
        assert success is False
    
    def test_pac_file_loading_and_validation(self):
        """Test loading PAC from file and validation."""
        pac_content = '''
        function FindProxyForURL(url, host) {
            // Corporate proxy configuration
            if (isInNet(host, "10.0.0.0", "255.0.0.0") ||
                isInNet(host, "192.168.0.0", "255.255.0.0")) {
                return "DIRECT";
            }
            return "PROXY corporate-proxy.company.com:8080; DIRECT";
        }
        '''
        
        # Create temporary PAC file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pac', delete=False) as f:
            f.write(pac_content)
            temp_path = f.name
        
        try:
            # Load PAC from file
            loaded_content = self.pac_validator.load_pac_from_file(temp_path)
            assert "FindProxyForURL" in loaded_content
            
            # Create configuration
            pac_config = self.pac_validator.create_pac_configuration(
                source_type="file",
                source_path=temp_path,
                content=loaded_content
            )
            
            assert pac_config.is_valid is True
            assert pac_config.source_type == "file"
            assert pac_config.source_path == temp_path
            
            # Test URL resolution
            result = self.pac_validator.test_url("http://192.168.1.100", loaded_content)
            assert result == "DIRECT"
            
            result = self.pac_validator.test_url("http://www.external.com", loaded_content)
            assert "PROXY corporate-proxy.company.com:8080" in result
        
        finally:
            os.unlink(temp_path)
    
    @patch('urllib.request.urlopen')
    def test_pac_url_loading_and_validation(self, mock_urlopen):
        """Test loading PAC from URL and validation."""
        pac_content = '''
        function FindProxyForURL(url, host) {
            if (weekdayRange("MON", "FRI") && timeRange(9, 17)) {
                return "PROXY work-proxy.company.com:8080";
            }
            return "PROXY home-proxy.company.com:8080";
        }
        '''
        
        # Mock URL response
        mock_response = Mock()
        mock_response.read.return_value = pac_content.encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        # Load PAC from URL
        pac_url = "http://proxy.company.com/proxy.pac"
        loaded_content = self.pac_validator.load_pac_from_url(pac_url)
        
        assert loaded_content == pac_content
        
        # Create configuration
        pac_config = self.pac_validator.create_pac_configuration(
            source_type="url",
            source_path=pac_url,
            content=loaded_content
        )
        
        assert pac_config.is_valid is True
        assert pac_config.source_type == "url"
        assert pac_config.source_path == pac_url
        
        # Verify URL was called
        mock_urlopen.assert_called_once_with(pac_url)
    
    def test_proxy_status_monitoring(self):
        """Test proxy status monitoring and updates."""
        # Initial status - stopped
        status = self.config_bridge.get_proxy_status()
        assert isinstance(status, ProxyStatus)
        assert status.is_running is False
        
        # Simulate starting proxy
        self.config_bridge.start_proxy(port=3128, address="127.0.0.1")
        
        # Check updated status
        status = self.config_bridge.get_proxy_status()
        assert status.is_running is True
        assert status.port == 3128
        assert status.listen_address == "127.0.0.1"
        
        # Simulate stopping proxy
        self.config_bridge.stop_proxy()
        
        # Check final status
        status = self.config_bridge.get_proxy_status()
        assert status.is_running is False


class TestEndToEndWorkflows:
    """Test complete end-to-end workflows."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_queue = EventQueue()
        self.processed_events = []
        
        def ui_callback(event_type, event):
            self.processed_events.append((event_type, event))
        
        self.event_processor = EventProcessor(self.event_queue, ui_callback)
        self.enhanced_handler = EnhancedPxHandler(self.event_queue)
        self.config_bridge = ConfigurationBridge()
        self.pac_validator = PACValidator()
    
    def test_complete_pac_configuration_workflow(self):
        """Test complete PAC configuration workflow from UI to proxy."""
        # Step 1: User creates PAC configuration
        pac_content = '''
        function FindProxyForURL(url, host) {
            if (host == "internal.company.com") return "DIRECT";
            if (host.indexOf("google.com") != -1) return "PROXY proxy1.company.com:8080";
            return "PROXY proxy2.company.com:8080; DIRECT";
        }
        '''
        
        # Step 2: Validate PAC
        pac_config = self.pac_validator.create_pac_configuration(
            source_type="inline",
            source_path="",
            content=pac_content
        )
        
        assert pac_config.is_valid is True
        
        # Step 3: Apply configuration
        success = self.config_bridge.apply_pac_configuration(pac_config)
        assert success is True
        
        # Step 4: Start proxy
        self.config_bridge.start_proxy(port=3128, address="127.0.0.1")
        
        # Step 5: Simulate requests and verify proxy decisions
        test_requests = [
            ("http://internal.company.com/page", "DIRECT"),
            ("https://www.google.com/search", "PROXY proxy1.company.com:8080"),
            ("http://external.example.com/api", "PROXY proxy2.company.com:8080")
        ]
        
        self.event_processor.start()
        
        try:
            for url, expected_proxy in test_requests:
                # Test PAC decision
                result = self.pac_validator.test_url(url, pac_content)
                assert expected_proxy in result
                
                # Simulate request processing
                request_id = f"req_{hash(url)}"
                self.enhanced_handler.capture_request(
                    url=url,
                    method="GET",
                    proxy_decision=result,
                    request_id=request_id
                )
                
                # Simulate response
                self.enhanced_handler.capture_response(
                    request_id=request_id,
                    status_code=200,
                    headers={"Content-Type": "text/html"},
                    body_preview="<html>...</html>",
                    response_time=0.2
                )
            
            # Wait for processing
            time.sleep(1.0)
            
            # Verify all requests were processed
            request_events = [e for t, e in self.processed_events if t == EventType.REQUEST]
            response_events = [e for t, e in self.processed_events if t == EventType.RESPONSE]
            
            assert len(request_events) == len(test_requests)
            assert len(response_events) == len(test_requests)
            
            # Verify proxy decisions
            for i, (url, expected_proxy) in enumerate(test_requests):
                request_event = request_events[i]
                assert request_event.url == url
                assert expected_proxy in request_event.proxy_decision
        
        finally:
            self.event_processor.stop()
            self.config_bridge.stop_proxy()
    
    def test_error_handling_workflow(self):
        """Test error handling throughout the system."""
        # Step 1: Invalid PAC configuration
        invalid_pac = "invalid javascript content"
        
        pac_config = self.pac_validator.create_pac_configuration(
            source_type="inline",
            source_path="",
            content=invalid_pac
        )
        
        assert pac_config.is_valid is False
        
        # Step 2: Attempt to apply invalid configuration
        success = self.config_bridge.apply_pac_configuration(pac_config)
        assert success is False
        
        # Step 3: Use valid configuration
        valid_pac = '''
        function FindProxyForURL(url, host) {
            return "PROXY proxy.company.com:8080";
        }
        '''
        
        valid_config = self.pac_validator.create_pac_configuration(
            source_type="inline",
            source_path="",
            content=valid_pac
        )
        
        assert valid_config.is_valid is True
        success = self.config_bridge.apply_pac_configuration(valid_config)
        assert success is True
        
        # Step 4: Simulate network errors
        self.event_processor.start()
        
        try:
            # Simulate request that results in error
            request_id = "req_error_test"
            self.enhanced_handler.capture_request(
                url="https://unreachable.example.com",
                method="GET",
                proxy_decision="PROXY proxy.company.com:8080",
                request_id=request_id
            )
            
            # Simulate network error
            self.enhanced_handler.capture_error(
                request_id=request_id,
                error_type="NetworkError",
                message="Connection refused",
                details={"errno": 61, "proxy": "proxy.company.com:8080"}
            )
            
            # Wait for processing
            time.sleep(0.5)
            
            # Verify error was captured and processed
            error_events = [e for t, e in self.processed_events if t == EventType.ERROR]
            assert len(error_events) == 1
            
            error_event = error_events[0]
            assert error_event.request_id == request_id
            assert error_event.error_type == "NetworkError"
            assert "Connection refused" in error_event.message
        
        finally:
            self.event_processor.stop()
    
    def test_performance_under_load(self):
        """Test system performance under high load."""
        # Configure simple PAC
        pac_content = '''
        function FindProxyForURL(url, host) {
            if (host.indexOf("direct") != -1) return "DIRECT";
            return "PROXY proxy.company.com:8080";
        }
        '''
        
        pac_config = self.pac_validator.create_pac_configuration(
            source_type="inline",
            source_path="",
            content=pac_content
        )
        
        self.config_bridge.apply_pac_configuration(pac_config)
        self.config_bridge.start_proxy(port=3128, address="127.0.0.1")
        
        # Start event processor
        self.event_processor.start()
        
        try:
            # Generate high volume of requests
            num_requests = 500
            start_time = time.time()
            
            for i in range(num_requests):
                request_id = f"req_load_{i}"
                url = f"https://test{i}.example.com" if i % 2 == 0 else f"https://direct{i}.example.com"
                
                self.enhanced_handler.capture_request(
                    url=url,
                    method="GET",
                    proxy_decision="DIRECT" if "direct" in url else "PROXY proxy.company.com:8080",
                    request_id=request_id
                )
                
                # Simulate response for every other request
                if i % 2 == 0:
                    self.enhanced_handler.capture_response(
                        request_id=request_id,
                        status_code=200,
                        headers={"Content-Type": "application/json"},
                        body_preview='{"status": "ok"}',
                        response_time=0.1
                    )
            
            # Wait for processing
            time.sleep(3.0)
            
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Verify performance
            assert processing_time < 10.0  # Should complete within 10 seconds
            
            # Verify all events were processed
            request_events = [e for t, e in self.processed_events if t == EventType.REQUEST]
            response_events = [e for t, e in self.processed_events if t == EventType.RESPONSE]
            
            assert len(request_events) == num_requests
            assert len(response_events) == num_requests // 2  # Only every other request had response
            
            # Calculate throughput
            requests_per_second = num_requests / processing_time
            assert requests_per_second > 50  # Should handle at least 50 requests/second
        
        finally:
            self.event_processor.stop()
            self.config_bridge.stop_proxy()