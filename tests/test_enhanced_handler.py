"""
Tests for enhanced px handler with monitoring hooks.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import time
from datetime import datetime

from px_ui.proxy.enhanced_handler import EnhancedPxHandler, MonitoringHooks
from px_ui.communication.event_system import EventSystem
from px_ui.communication.events import RequestEvent, ResponseEvent, ErrorEvent


class TestMonitoringHooks(unittest.TestCase):
    """Test monitoring hooks functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.event_system = Mock(spec=EventSystem)
        self.hooks = MonitoringHooks(self.event_system)
    
    def test_on_request_start(self):
        """Test request start hook."""
        request_id = "test-request-123"
        url = "https://example.com/test"
        method = "GET"
        headers = {"User-Agent": "test-agent"}
        
        self.hooks.on_request_start(request_id, url, method, headers)
        
        # Verify event was sent
        self.event_system.send_event.assert_called_once()
        event = self.event_system.send_event.call_args[0][0]
        
        self.assertIsInstance(event, RequestEvent)
        self.assertEqual(event.url, url)
        self.assertEqual(event.method, method)
        self.assertEqual(event.request_id, request_id)
        self.assertEqual(event.headers, headers)
        self.assertEqual(event.proxy_decision, "PENDING")
    
    def test_on_response_received(self):
        """Test response received hook."""
        request_id = "test-request-123"
        
        # First start a request to set up timing
        self.hooks.on_request_start(request_id, "https://example.com", "GET")
        
        # Small delay to test timing
        time.sleep(0.01)
        
        status_code = 200
        headers = {"Content-Type": "text/html"}
        body_preview = "<html>test</html>"
        content_length = 1024
        
        self.hooks.on_response_received(request_id, status_code, headers, body_preview, content_length)
        
        # Verify response event was sent (second call after request event)
        self.assertEqual(self.event_system.send_event.call_count, 2)
        response_event = self.event_system.send_event.call_args_list[1][0][0]
        
        self.assertIsInstance(response_event, ResponseEvent)
        self.assertEqual(response_event.request_id, request_id)
        self.assertEqual(response_event.status_code, status_code)
        self.assertEqual(response_event.headers, headers)
        self.assertEqual(response_event.body_preview, body_preview)
        self.assertEqual(response_event.content_length, content_length)
        self.assertGreater(response_event.response_time, 0)
    
    def test_on_error(self):
        """Test error hook."""
        error_type = "network"
        error_message = "Connection failed"
        error_details = "Timeout after 30 seconds"
        request_id = "test-request-123"
        url = "https://example.com/test"
        
        self.hooks.on_error(error_type, error_message, error_details, request_id, url)
        
        # Verify error event was sent
        self.event_system.send_event.assert_called_once()
        event = self.event_system.send_event.call_args[0][0]
        
        self.assertIsInstance(event, ErrorEvent)
        self.assertEqual(event.error_type, error_type)
        self.assertEqual(event.error_message, error_message)
        self.assertEqual(event.error_details, error_details)
        self.assertEqual(event.request_id, request_id)
        self.assertEqual(event.url, url)


class TestEnhancedPxHandler(unittest.TestCase):
    """Test enhanced px handler functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.event_system = Mock(spec=EventSystem)
        self.hooks = MonitoringHooks(self.event_system)
        EnhancedPxHandler.set_monitoring_hooks(self.hooks)
        
        # Mock the handler initialization
        with patch('px.handler.PxHandler.__init__'):
            self.handler = EnhancedPxHandler()
            self.handler.path = "https://example.com/test"
            self.handler.command = "GET"
            self.handler.headers = {"User-Agent": "test-agent"}
    
    @patch('px.handler.PxHandler.do_curl')
    def test_do_curl_with_monitoring(self, mock_parent_do_curl):
        """Test do_curl with monitoring hooks."""
        # Mock curl object
        mock_curl = Mock()
        mock_curl.resp = 200
        mock_curl.headers = {"Content-Type": "text/html"}
        mock_curl.body = b"<html>test response</html>"
        self.handler.curl = mock_curl
        
        # Call do_curl
        self.handler.do_curl()
        
        # Verify parent method was called
        mock_parent_do_curl.assert_called_once()
        
        # Verify request event was sent
        self.event_system.send_event.assert_called()
        
        # Check that request ID was generated
        self.assertIsNotNone(self.handler._current_request_id)
        self.assertEqual(self.handler._current_url, "https://example.com/test")
        self.assertEqual(self.handler._current_method, "GET")
    
    @patch('px.handler.PxHandler.do_curl')
    def test_do_curl_error_handling(self, mock_parent_do_curl):
        """Test error handling in do_curl."""
        # Make parent method raise an exception
        mock_parent_do_curl.side_effect = Exception("Network error")
        
        # Call do_curl and expect exception
        with self.assertRaises(Exception):
            self.handler.do_curl()
        
        # Verify error event was sent
        self.event_system.send_event.assert_called()
        
        # Find the error event
        error_event = None
        for call in self.event_system.send_event.call_args_list:
            event = call[0][0]
            if isinstance(event, ErrorEvent):
                error_event = event
                break
        
        self.assertIsNotNone(error_event)
        self.assertEqual(error_event.error_type, "network")
        self.assertIn("Network error", error_event.error_message)
    
    @patch('px.handler.PxHandler.get_destination')
    def test_get_destination_monitoring(self, mock_parent_get_destination):
        """Test proxy decision monitoring."""
        # Set up handler state
        self.handler._current_request_id = "test-123"
        
        # Test direct connection
        mock_parent_get_destination.return_value = "example.com:80"
        result = self.handler.get_destination()
        
        self.assertEqual(result, "example.com:80")
        
        # Test proxy connection
        mock_parent_get_destination.return_value = None
        self.handler.proxy_servers = [("proxy.example.com", 8080)]
        result = self.handler.get_destination()
        
        self.assertIsNone(result)
    
    @patch('px.handler.PxHandler.send_error')
    def test_send_error_monitoring(self, mock_parent_send_error):
        """Test error response monitoring."""
        self.handler._current_request_id = "test-123"
        self.handler._current_url = "https://example.com/test"
        
        # Call send_error
        self.handler.send_error(401, "Unauthorized")
        
        # Verify parent method was called
        mock_parent_send_error.assert_called_once_with(401, "Unauthorized")
        
        # Verify error event was sent
        self.event_system.send_event.assert_called()
    
    def test_parse_header_string(self):
        """Test header string parsing."""
        header_string = "Content-Type: text/html\nContent-Length: 1024\nServer: nginx"
        
        headers = self.handler._parse_header_string(header_string)
        
        expected = {
            "content-type": "text/html",
            "content-length": "1024",
            "server": "nginx"
        }
        self.assertEqual(headers, expected)


if __name__ == '__main__':
    unittest.main()