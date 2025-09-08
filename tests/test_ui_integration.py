"""
Integration tests for UI components.
"""

import unittest
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from px_ui.models.proxy_status import ProxyStatus


class TestUIIntegration(unittest.TestCase):
    """Integration tests for UI components."""
    
    def test_proxy_status_model(self):
        """Test ProxyStatus model used by MainWindow."""
        # Test creating a proxy status
        status = ProxyStatus(
            is_running=True,
            listen_address="127.0.0.1",
            port=3128,
            mode="pac",
            active_connections=5,
            total_requests=100
        )
        
        # Test status methods used by MainWindow
        self.assertEqual(status.get_status_text(), "Running on 127.0.0.1:3128")
        self.assertEqual(status.get_connection_info(), "5 active, 100 total")
        self.assertEqual(status.get_listen_url(), "http://127.0.0.1:3128")
        self.assertTrue(status.is_running)
        self.assertTrue(status.is_localhost())
        self.assertTrue(status.is_using_pac())
    
    def test_proxy_status_stopped(self):
        """Test ProxyStatus when stopped."""
        status = ProxyStatus(
            is_running=False,
            listen_address="127.0.0.1",
            port=3128,
            mode="manual"
        )
        
        self.assertEqual(status.get_status_text(), "Stopped")
        self.assertEqual(status.get_connection_info(), "0 active, 0 total")
        self.assertFalse(status.is_running)
        self.assertFalse(status.is_using_pac())
    
    def test_main_window_import(self):
        """Test that MainWindow can be imported successfully."""
        try:
            from px_ui.ui import MainWindow
            self.assertTrue(True, "MainWindow imported successfully")
        except ImportError as e:
            self.fail(f"Failed to import MainWindow: {e}")
    
    def test_main_window_class_exists(self):
        """Test that MainWindow class has required methods."""
        from px_ui.ui import MainWindow
        
        # Check that MainWindow has the required methods
        required_methods = [
            'run',
            'set_proxy_callbacks',
            'update_proxy_status',
            'show_error',
            'show_info'
        ]
        
        for method_name in required_methods:
            self.assertTrue(
                hasattr(MainWindow, method_name),
                f"MainWindow missing required method: {method_name}"
            )


if __name__ == '__main__':
    unittest.main()