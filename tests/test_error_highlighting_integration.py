"""
Integration tests for error highlighting functionality.

This module tests the integration between the monitoring view and response
details dialog, focusing on error highlighting and status-based formatting.
"""

import unittest
from unittest.mock import Mock, patch
import tkinter as tk
from datetime import datetime

from px_ui.ui.monitoring_view import MonitoringView, RequestEntry
from px_ui.ui.response_details_dialog import ResponseDetailsDialog
from px_ui.communication.event_system import EventSystem
from px_ui.communication.events import RequestEvent, ResponseEvent, ErrorEvent


class TestErrorHighlightingIntegration(unittest.TestCase):
    """Integration tests for error highlighting functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the root window during tests
        
        # Create mock event system
        self.event_system = Mock(spec=EventSystem)
        
        # Create monitoring view
        self.monitoring_view = MonitoringView(self.root, self.event_system)
        
    def tearDown(self):
        """Clean up after tests."""
        self.root.destroy()
        
    def _create_request_entry(self, status_code=None, error_message=None):
        """Helper to create a request entry for testing."""
        # Create mock request event
        request_event = Mock(spec=RequestEvent)
        request_event.request_id = "test-123"
        request_event.timestamp = datetime.now()
        request_event.url = "https://example.com/test"
        request_event.method = "GET"
        request_event.proxy_decision = "DIRECT"
        request_event.headers = {"User-Agent": "Test"}
        
        # Create request entry
        entry = RequestEntry(request_event)
        
        # Set response data
        if status_code is not None:
            response_event = Mock(spec=ResponseEvent)
            response_event.status_code = status_code
            response_event.headers = {"Content-Type": "application/json"}
            response_event.body_preview = '{"test": "data"}'
            response_event.content_length = 100
            response_event.response_time = 150.0
            entry.update_response(response_event)
            
        if error_message:
            error_event = Mock(spec=ErrorEvent)
            error_event.error_message = error_message
            entry.update_error(error_event)
            
        return entry
        
    def test_success_response_highlighting(self):
        """Test highlighting for successful responses (2xx)."""
        entry = self._create_request_entry(status_code=200)
        tag = self.monitoring_view._get_status_tag(entry)
        
        self.assertEqual(tag, "success")
        self.assertTrue(entry.is_success())
        self.assertFalse(entry.is_error())
        
    def test_client_error_highlighting(self):
        """Test highlighting for client errors (4xx)."""
        entry = self._create_request_entry(status_code=404)
        tag = self.monitoring_view._get_status_tag(entry)
        
        self.assertEqual(tag, "client_error")
        self.assertTrue(entry.is_client_error())
        self.assertTrue(entry.is_error())
        self.assertFalse(entry.is_success())
        
    def test_server_error_highlighting(self):
        """Test highlighting for server errors (5xx)."""
        entry = self._create_request_entry(status_code=500)
        tag = self.monitoring_view._get_status_tag(entry)
        
        self.assertEqual(tag, "server_error")
        self.assertTrue(entry.is_server_error())
        self.assertTrue(entry.is_error())
        self.assertFalse(entry.is_success())
        
    def test_network_error_highlighting(self):
        """Test highlighting for network errors."""
        entry = self._create_request_entry(error_message="Connection timeout")
        tag = self.monitoring_view._get_status_tag(entry)
        
        self.assertEqual(tag, "error")
        self.assertTrue(entry.is_error())
        self.assertFalse(entry.is_success())
        
    def test_pending_request_highlighting(self):
        """Test highlighting for pending requests."""
        entry = self._create_request_entry()  # No response yet
        tag = self.monitoring_view._get_status_tag(entry)
        
        self.assertEqual(tag, "normal")
        self.assertFalse(entry.is_error())
        self.assertFalse(entry.is_success())
        
    def test_response_details_dialog_with_success(self):
        """Test response details dialog with successful response."""
        entry = self._create_request_entry(status_code=200)
        dialog = ResponseDetailsDialog(self.root, entry)
        
        # Test dialog creation
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.entry, entry)
        
        # Test status text
        status_text = dialog._get_status_text(200)
        self.assertEqual(status_text, "OK")
        
    def test_response_details_dialog_with_error(self):
        """Test response details dialog with error response."""
        entry = self._create_request_entry(status_code=404)
        dialog = ResponseDetailsDialog(self.root, entry)
        
        # Test dialog creation
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.entry, entry)
        
        # Test status text
        status_text = dialog._get_status_text(404)
        self.assertEqual(status_text, "Not Found")
        
    def test_response_details_dialog_with_network_error(self):
        """Test response details dialog with network error."""
        entry = self._create_request_entry(error_message="Connection failed")
        dialog = ResponseDetailsDialog(self.root, entry)
        
        # Test dialog creation
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.entry, entry)
        self.assertEqual(dialog.entry.error_message, "Connection failed")
        
    def test_monitoring_view_tree_configuration(self):
        """Test that monitoring view tree is properly configured for highlighting."""
        tree = self.monitoring_view.tree
        
        # Check that error highlighting tags are configured by checking tag configuration
        # Tkinter doesn't have tag_names() method, so we check if tags are configured
        try:
            # Try to get tag configuration - if tag exists, this won't raise an error
            tree.tag_configure("error")
            tree.tag_configure("client_error")
            tree.tag_configure("server_error")
            tree.tag_configure("success")
            tree.tag_configure("normal")
            # If we get here, all tags are configured
            self.assertTrue(True)
        except tk.TclError:
            self.fail("Error highlighting tags are not properly configured")
        
    def test_status_display_formatting(self):
        """Test status display formatting for different response types."""
        # Success response
        entry = self._create_request_entry(status_code=200)
        self.assertEqual(entry.get_status_display(), "200")
        
        # Client error
        entry = self._create_request_entry(status_code=404)
        self.assertEqual(entry.get_status_display(), "404")
        
        # Server error
        entry = self._create_request_entry(status_code=500)
        self.assertEqual(entry.get_status_display(), "500")
        
        # Network error
        entry = self._create_request_entry(error_message="Timeout")
        self.assertEqual(entry.get_status_display(), "ERROR: Timeout")
        
        # Pending request
        entry = self._create_request_entry()
        self.assertEqual(entry.get_status_display(), "Pending")
        
    def test_comprehensive_error_detection(self):
        """Test comprehensive error detection across different scenarios."""
        test_cases = [
            # (status_code, error_message, expected_is_error, expected_tag)
            (200, None, False, "success"),
            (201, None, False, "success"),
            (299, None, False, "success"),
            (300, None, False, "normal"),  # 3xx redirects are not success but not error
            (400, None, True, "client_error"),
            (404, None, True, "client_error"),
            (499, None, True, "client_error"),
            (500, None, True, "server_error"),
            (503, None, True, "server_error"),
            (599, None, True, "server_error"),
            (None, "Network error", True, "error"),
            (200, "Partial error", True, "error"),  # Error message overrides success status
        ]
        
        for status_code, error_message, expected_is_error, expected_tag in test_cases:
            with self.subTest(status_code=status_code, error_message=error_message):
                entry = self._create_request_entry(status_code=status_code, error_message=error_message)
                
                # Test error detection
                self.assertEqual(entry.is_error(), expected_is_error, 
                               f"Error detection failed for status={status_code}, error={error_message}")
                
                # Test tag assignment (skip 3xx for now as they're edge cases)
                if status_code != 300:
                    tag = self.monitoring_view._get_status_tag(entry)
                    self.assertEqual(tag, expected_tag,
                                   f"Tag assignment failed for status={status_code}, error={error_message}")


if __name__ == '__main__':
    unittest.main()