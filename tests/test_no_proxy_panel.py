"""
Tests for no proxy panel UI functionality.
"""

import unittest
import tkinter as tk
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from px_ui.ui.no_proxy_panel import NoProxyPanel
from px_ui.models.no_proxy_configuration import NoProxyConfiguration


class TestNoProxyPanel(unittest.TestCase):
    """Test cases for NoProxyPanel class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the window during tests
        self.panel = NoProxyPanel(self.root)
        
        # Mock callback
        self.config_changed_mock = Mock()
        self.panel.on_config_changed = self.config_changed_mock
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.root.destroy()
    
    def test_panel_initialization(self):
        """Test panel initialization."""
        self.assertIsInstance(self.panel.no_proxy_config, NoProxyConfiguration)
        self.assertTrue(self.panel.bypass_localhost_var.get())
        self.assertTrue(self.panel.bypass_private_var.get())
    
    def test_built_in_options(self):
        """Test built-in bypass options."""
        # Test localhost option
        self.panel.bypass_localhost_var.set(False)
        self.panel._on_built_in_option_changed()
        self.assertFalse(self.panel.no_proxy_config.bypass_localhost)
        self.config_changed_mock.assert_called()
        
        # Test private networks option
        self.panel.bypass_private_var.set(False)
        self.panel._on_built_in_option_changed()
        self.assertFalse(self.panel.no_proxy_config.bypass_private_networks)
    
    def test_add_pattern(self):
        """Test adding patterns through UI."""
        # Set pattern in entry
        self.panel.pattern_entry.insert(0, "example.com")
        
        # Trigger add pattern
        self.panel._on_add_pattern()
        
        # Verify pattern was added
        self.assertIn("example.com", self.panel.no_proxy_config.patterns)
        self.assertEqual(self.panel.pattern_entry.get(), "")  # Entry should be cleared
        self.config_changed_mock.assert_called()
    
    def test_add_invalid_pattern(self):
        """Test adding invalid pattern."""
        with patch('tkinter.messagebox.showerror') as mock_error:
            # Set invalid pattern
            self.panel.pattern_entry.insert(0, "invalid<pattern")
            
            # Trigger add pattern
            self.panel._on_add_pattern()
            
            # Verify error was shown and pattern not added
            mock_error.assert_called()
            self.assertNotIn("invalid<pattern", self.panel.no_proxy_config.patterns)
    
    def test_remove_pattern(self):
        """Test removing patterns."""
        # Add a pattern first
        self.panel.no_proxy_config.add_pattern("example.com")
        self.panel._update_pattern_list()
        
        # Select the pattern in the tree
        items = self.panel.pattern_tree.get_children()
        self.assertGreater(len(items), 0)
        self.panel.pattern_tree.selection_set(items[0])
        
        # Remove pattern
        self.panel._on_remove_pattern()
        
        # Verify pattern was removed
        self.assertNotIn("example.com", self.panel.no_proxy_config.patterns)
        self.config_changed_mock.assert_called()
    
    def test_remove_pattern_no_selection(self):
        """Test removing pattern with no selection."""
        with patch('tkinter.messagebox.showwarning') as mock_warning:
            # Try to remove without selection
            self.panel._on_remove_pattern()
            
            # Verify warning was shown
            mock_warning.assert_called()
    
    def test_clear_patterns(self):
        """Test clearing all patterns."""
        # Add some patterns
        self.panel.no_proxy_config.add_pattern("example.com")
        self.panel.no_proxy_config.add_pattern("test.com")
        
        with patch('tkinter.messagebox.askyesno', return_value=True) as mock_confirm:
            # Clear patterns
            self.panel._on_clear_patterns()
            
            # Verify confirmation was asked and patterns cleared
            mock_confirm.assert_called()
            self.assertEqual(len(self.panel.no_proxy_config.patterns), 0)
            self.config_changed_mock.assert_called()
    
    def test_validate_patterns(self):
        """Test pattern validation."""
        # Add valid and invalid patterns manually
        self.panel.no_proxy_config.patterns = ["example.com", "invalid<pattern"]
        
        # Trigger validation
        self.panel._on_validate_patterns()
        
        # Check validation results
        self.assertFalse(self.panel.no_proxy_config.is_valid)
        self.assertGreater(len(self.panel.no_proxy_config.validation_errors), 0)
    
    def test_url_testing(self):
        """Test URL testing functionality."""
        # Add test pattern
        self.panel.no_proxy_config.add_pattern("example.com")
        
        # Set test URL
        self.panel.test_url_entry.insert(0, "http://example.com")
        
        # Trigger test
        self.panel._on_test_url()
        
        # Check result label was updated
        result_text = self.panel.test_result_label.cget("text")
        self.assertIn("BYPASS PROXY", result_text)
    
    def test_url_testing_invalid_url(self):
        """Test URL testing with invalid URL."""
        # Set invalid URL
        self.panel.test_url_entry.insert(0, "not-a-url")
        
        # Trigger test
        self.panel._on_test_url()
        
        # Should handle gracefully (no exception)
        result_text = self.panel.test_result_label.cget("text")
        self.assertTrue(len(result_text) > 0)  # Some result should be shown
    
    def test_pattern_list_update(self):
        """Test pattern list display update."""
        # Add patterns
        self.panel.no_proxy_config.add_pattern("example.com")
        self.panel.no_proxy_config.add_pattern("*.test.com")
        self.panel.no_proxy_config.add_pattern("192.168.1.0/24")
        
        # Update display
        self.panel._update_pattern_list()
        
        # Check tree items
        items = self.panel.pattern_tree.get_children()
        self.assertEqual(len(items), 3)
        
        # Check pattern types are displayed
        for item in items:
            values = self.panel.pattern_tree.item(item)["values"]
            self.assertEqual(len(values), 3)  # pattern, type, status
            self.assertIn(values[1], ["Hostname", "Wildcard", "CIDR"])  # Type
            self.assertIn(values[2], ["Valid", "Invalid"])  # Status
    
    def test_get_pattern_type(self):
        """Test pattern type detection."""
        # Test different pattern types
        self.assertEqual(self.panel._get_pattern_type("example.com"), "Hostname")
        self.assertEqual(self.panel._get_pattern_type("*.example.com"), "Wildcard")
        self.assertEqual(self.panel._get_pattern_type("192.168.1.1"), "IP Address")
        self.assertEqual(self.panel._get_pattern_type("192.168.1.0/24"), "CIDR")
        self.assertEqual(self.panel._get_pattern_type("192.168.1.1-192.168.1.100"), "IP Range")
        self.assertEqual(self.panel._get_pattern_type(".local"), "Domain")
    
    def test_validation_display(self):
        """Test validation status display."""
        # Valid configuration
        self.panel.no_proxy_config.add_pattern("example.com")
        self.panel._update_validation_display()
        
        validation_text = self.panel.validation_label.cget("text")
        self.assertIn("valid", validation_text.lower())
        
        # Invalid configuration
        self.panel.no_proxy_config.patterns.append("invalid<pattern")
        self.panel.no_proxy_config.validate()
        self.panel._update_validation_display()
        
        validation_text = self.panel.validation_label.cget("text")
        self.assertIn("error", validation_text.lower())
    
    def test_configuration_methods(self):
        """Test configuration getter/setter methods."""
        # Create test configuration
        test_config = NoProxyConfiguration()
        test_config.bypass_localhost = False
        test_config.add_pattern("test.com")
        
        # Set configuration
        self.panel.set_configuration(test_config)
        
        # Verify UI was updated
        self.assertFalse(self.panel.bypass_localhost_var.get())
        self.assertIn("test.com", self.panel.no_proxy_config.patterns)
        
        # Get configuration
        retrieved_config = self.panel.get_configuration()
        self.assertEqual(retrieved_config.bypass_localhost, False)
        self.assertIn("test.com", retrieved_config.patterns)
    
    def test_px_format_methods(self):
        """Test px format conversion methods."""
        # Set up configuration
        self.panel.no_proxy_config.add_pattern("example.com")
        
        # Get px format
        px_format = self.panel.get_px_format()
        self.assertIsInstance(px_format, str)
        self.assertIn("example.com", px_format)
        
        # Load from px format
        test_px_format = "localhost,127.0.0.1,test.com,*.example.com"
        self.panel.load_from_px_format(test_px_format)
        
        # Verify configuration was updated
        self.assertTrue(self.panel.no_proxy_config.bypass_localhost)
        self.assertIn("test.com", self.panel.no_proxy_config.patterns)
        self.assertIn("*.example.com", self.panel.no_proxy_config.patterns)
    
    def test_summary_method(self):
        """Test configuration summary method."""
        # Empty configuration
        self.panel.no_proxy_config.bypass_localhost = False
        self.panel.no_proxy_config.bypass_private_networks = False
        summary = self.panel.get_summary()
        self.assertIn("No bypass", summary)
        
        # With patterns
        self.panel.no_proxy_config.add_pattern("example.com")
        summary = self.panel.get_summary()
        self.assertIn("custom pattern", summary)


class TestNoProxyPanelIntegration(unittest.TestCase):
    """Integration tests for no proxy panel."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()
        self.panel = NoProxyPanel(self.root)
    
    def tearDown(self):
        """Clean up test fixtures."""
        self.root.destroy()
    
    def test_full_workflow(self):
        """Test complete workflow of adding, testing, and removing patterns."""
        # Start with clean configuration
        self.panel.no_proxy_config.clear_patterns()
        self.panel.no_proxy_config.bypass_localhost = False
        self.panel.no_proxy_config.bypass_private_networks = False
        
        # Add patterns through UI
        patterns_to_add = [
            "example.com",
            "*.test.com", 
            "192.168.1.0/24",
            "10.0.0.1-10.0.0.100"
        ]
        
        for pattern in patterns_to_add:
            self.panel.pattern_entry.delete(0, tk.END)
            self.panel.pattern_entry.insert(0, pattern)
            self.panel._on_add_pattern()
        
        # Verify all patterns were added
        for pattern in patterns_to_add:
            self.assertIn(pattern, self.panel.no_proxy_config.patterns)
        
        # Test URL matching
        test_cases = [
            ("http://example.com", True),
            ("http://sub.test.com", True),
            ("http://192.168.1.50", True),
            ("http://10.0.0.50", True),
            ("http://google.com", False)
        ]
        
        for url, should_bypass in test_cases:
            result = self.panel.no_proxy_config.should_bypass_proxy(url)
            self.assertEqual(result, should_bypass, f"Failed for URL: {url}")
        
        # Clear all patterns
        with patch('tkinter.messagebox.askyesno', return_value=True):
            self.panel._on_clear_patterns()
        
        # Verify patterns were cleared
        self.assertEqual(len(self.panel.no_proxy_config.patterns), 0)
    
    def test_error_handling(self):
        """Test error handling in various scenarios."""
        # Test adding empty pattern
        self.panel.pattern_entry.delete(0, tk.END)
        self.panel._on_add_pattern()  # Should handle gracefully
        
        # Test removing with no selection
        with patch('tkinter.messagebox.showwarning'):
            self.panel._on_remove_pattern()  # Should show warning
        
        # Test URL testing with empty URL
        self.panel.test_url_entry.delete(0, tk.END)
        self.panel._on_test_url()  # Should handle gracefully


if __name__ == '__main__':
    # Run tests with minimal GUI interaction
    unittest.main()