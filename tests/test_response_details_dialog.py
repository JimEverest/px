"""
Tests for response details dialog functionality.

This module tests the ResponseDetailsDialog class and its integration
with the monitoring view for displaying detailed response information.
"""

import unittest
from unittest.mock import Mock, patch
import tkinter as tk
from datetime import datetime
import json

from px_ui.ui.response_details_dialog import ResponseDetailsDialog
from px_ui.ui.monitoring_view import RequestEntry
from px_ui.communication.events import RequestEvent, ResponseEvent


class MockRequestEntry:
    """Mock request entry for testing."""
    
    def __init__(self):
        self.request_id = "test-123"
        self.timestamp = datetime.now()
        self.url = "https://example.com/api/test"
        self.method = "GET"
        self.proxy_decision = "PROXY proxy.example.com:8080"
        self.headers = {"User-Agent": "Test Agent", "Accept": "application/json"}
        
        # Response data
        self.status_code = 200
        self.response_headers = {
            "Content-Type": "application/json",
            "Content-Length": "150",
            "Server": "nginx/1.18.0"
        }
        self.body_preview = '{"message": "Hello World", "status": "success", "data": {"id": 123, "name": "Test"}}'
        self.content_length = 150
        self.response_time = 245.5
        self.error_message = None
        
    def is_error(self):
        return self.error_message is not None or (self.status_code is not None and self.status_code >= 400)


class MockErrorRequestEntry(MockRequestEntry):
    """Mock request entry with error for testing."""
    
    def __init__(self):
        super().__init__()
        self.status_code = 404
        self.error_message = "Not Found"
        self.body_preview = '{"error": "Resource not found", "code": 404}'


class TestResponseDetailsDialog(unittest.TestCase):
    """Test cases for ResponseDetailsDialog."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the root window during tests
        
    def tearDown(self):
        """Clean up after tests."""
        self.root.destroy()
        
    def test_dialog_creation(self):
        """Test dialog creation with valid request entry."""
        entry = MockRequestEntry()
        dialog = ResponseDetailsDialog(self.root, entry)
        
        # Test that dialog can be created without errors
        self.assertIsNotNone(dialog)
        self.assertEqual(dialog.entry, entry)
        self.assertIsNone(dialog.dialog)  # Dialog not shown yet
        
    def test_dialog_show(self):
        """Test showing the dialog."""
        entry = MockRequestEntry()
        dialog = ResponseDetailsDialog(self.root, entry)
        
        # Show dialog
        dialog.show()
        
        # Verify dialog is created
        self.assertIsNotNone(dialog.dialog)
        self.assertTrue(dialog.dialog.winfo_exists())
        
        # Clean up
        dialog._on_close()
        
    def test_url_truncation(self):
        """Test URL truncation for long URLs."""
        entry = MockRequestEntry()
        entry.url = "https://very-long-domain-name.example.com/api/v1/very/long/path/with/many/segments/test"
        
        dialog = ResponseDetailsDialog(self.root, entry)
        
        # Test truncation
        truncated = dialog._truncate_url(entry.url, 50)
        self.assertLessEqual(len(truncated), 50)
        self.assertTrue(truncated.endswith("..."))
        
        # Test no truncation needed
        short_url = "https://example.com"
        not_truncated = dialog._truncate_url(short_url, 50)
        self.assertEqual(not_truncated, short_url)
        
    def test_byte_formatting(self):
        """Test byte count formatting."""
        entry = MockRequestEntry()
        dialog = ResponseDetailsDialog(self.root, entry)
        
        # Test different byte sizes
        self.assertEqual(dialog._format_bytes(500), "500 bytes")
        self.assertEqual(dialog._format_bytes(1536), "1.5 KB")
        self.assertEqual(dialog._format_bytes(2097152), "2.0 MB")
        
    def test_status_text_mapping(self):
        """Test HTTP status code to text mapping."""
        entry = MockRequestEntry()
        dialog = ResponseDetailsDialog(self.root, entry)
        
        # Test common status codes
        self.assertEqual(dialog._get_status_text(200), "OK")
        self.assertEqual(dialog._get_status_text(404), "Not Found")
        self.assertEqual(dialog._get_status_text(500), "Internal Server Error")
        self.assertEqual(dialog._get_status_text(999), "Unknown")
        
    def test_error_entry_display(self):
        """Test dialog with error entry."""
        entry = MockErrorRequestEntry()
        dialog = ResponseDetailsDialog(self.root, entry)
        
        # Show dialog
        dialog.show()
        
        # Verify dialog handles error entry
        self.assertIsNotNone(dialog.dialog)
        
        # Clean up
        dialog._on_close()
        
    def test_json_formatting(self):
        """Test JSON content formatting."""
        entry = MockRequestEntry()
        dialog = ResponseDetailsDialog(self.root, entry)
        dialog.show()
        
        # Set format to JSON
        dialog.format_var.set("JSON")
        dialog._update_body_display()
        
        # Verify content is formatted
        content = dialog.body_text.get("1.0", "end-1c")
        self.assertIn("{\n", content)  # Should be formatted with indentation
        
        # Clean up
        dialog._on_close()
        
    @patch('tkinter.messagebox.showinfo')
    def test_copy_url(self, mock_showinfo):
        """Test URL copying functionality."""
        entry = MockRequestEntry()
        dialog = ResponseDetailsDialog(self.root, entry)
        dialog.show()
        
        # Test copy URL
        dialog._copy_url()
        
        # Verify clipboard content
        clipboard_content = dialog.dialog.clipboard_get()
        self.assertEqual(clipboard_content, entry.url)
        
        # Verify info message shown
        mock_showinfo.assert_called_once_with("Copied", "URL copied to clipboard")
        
        # Clean up
        dialog._on_close()
        
    @patch('tkinter.filedialog.asksaveasfilename')
    @patch('builtins.open', create=True)
    def test_export_details_json(self, mock_open, mock_filedialog):
        """Test exporting details to JSON file."""
        entry = MockRequestEntry()
        dialog = ResponseDetailsDialog(self.root, entry)
        dialog.show()
        
        # Mock file dialog
        mock_filedialog.return_value = "test_export.json"
        
        # Mock file writing
        mock_file = Mock()
        mock_open.return_value.__enter__.return_value = mock_file
        
        # Test export
        dialog._export_details()
        
        # Verify file dialog was called
        mock_filedialog.assert_called_once()
        
        # Verify file was opened for writing
        mock_open.assert_called_once_with("test_export.json", 'w', encoding='utf-8')
        
        # Clean up
        dialog._on_close()
        
    def test_full_content_dialog(self):
        """Test full content viewing dialog."""
        entry = MockRequestEntry()
        entry.content_length = 1000  # Simulate truncated content
        
        dialog = ResponseDetailsDialog(self.root, entry)
        dialog.show()
        
        # Set full content
        dialog.full_body_content = "This is the full content that was truncated..."
        
        # Test view full content
        dialog._view_full_content()
        
        # Clean up
        dialog._on_close()


class TestMonitoringViewErrorHighlighting(unittest.TestCase):
    """Test cases for error highlighting in monitoring view."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()
        
    def tearDown(self):
        """Clean up after tests."""
        self.root.destroy()
        
    def test_status_tag_assignment(self):
        """Test status tag assignment for different response types."""
        from px_ui.ui.monitoring_view import MonitoringView
        from px_ui.communication.event_system import EventSystem
        
        event_system = Mock(spec=EventSystem)
        view = MonitoringView(self.root, event_system)
        
        # Test success response
        entry = MockRequestEntry()
        entry.status_code = 200
        entry.error_message = None
        self.assertEqual(view._get_status_tag(entry), "success")
        
        # Test client error
        entry.status_code = 404
        self.assertEqual(view._get_status_tag(entry), "client_error")
        
        # Test server error
        entry.status_code = 500
        self.assertEqual(view._get_status_tag(entry), "server_error")
        
        # Test general error
        entry.status_code = None
        entry.error_message = "Network error"
        self.assertEqual(view._get_status_tag(entry), "error")
        
        # Test pending request
        entry.status_code = None
        entry.error_message = None
        self.assertEqual(view._get_status_tag(entry), "normal")
        
    def test_request_entry_error_methods(self):
        """Test RequestEntry error detection methods."""
        from px_ui.ui.monitoring_view import RequestEntry
        from px_ui.communication.events import RequestEvent
        
        # Create mock request event
        request_event = Mock(spec=RequestEvent)
        request_event.request_id = "test-123"
        request_event.timestamp = datetime.now()
        request_event.url = "https://example.com"
        request_event.method = "GET"
        request_event.proxy_decision = "DIRECT"
        request_event.headers = {}
        
        entry = RequestEntry(request_event)
        
        # Test success response
        entry.status_code = 200
        entry.error_message = None
        self.assertTrue(entry.is_success())
        self.assertFalse(entry.is_error())
        self.assertFalse(entry.is_client_error())
        self.assertFalse(entry.is_server_error())
        
        # Test client error
        entry.status_code = 404
        self.assertFalse(entry.is_success())
        self.assertTrue(entry.is_error())
        self.assertTrue(entry.is_client_error())
        self.assertFalse(entry.is_server_error())
        
        # Test server error
        entry.status_code = 500
        self.assertFalse(entry.is_success())
        self.assertTrue(entry.is_error())
        self.assertFalse(entry.is_client_error())
        self.assertTrue(entry.is_server_error())
        
        # Test general error
        entry.status_code = None
        entry.error_message = "Connection failed"
        self.assertFalse(entry.is_success())
        self.assertTrue(entry.is_error())
        self.assertFalse(entry.is_client_error())
        self.assertFalse(entry.is_server_error())


if __name__ == '__main__':
    unittest.main()