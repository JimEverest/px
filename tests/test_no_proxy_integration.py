"""
Integration tests for no proxy functionality with proxy controller.
"""

import unittest
import sys
import os
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from px_ui.models.no_proxy_configuration import NoProxyConfiguration
from px_ui.proxy.proxy_controller import ProxyController
from px_ui.proxy.configuration_bridge import PxConfigurationBridge
from px_ui.communication.event_system import EventSystem


class TestNoProxyIntegration(unittest.TestCase):
    """Integration tests for no proxy functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.event_system = EventSystem()
        self.config_bridge = PxConfigurationBridge(self.event_system)
        self.proxy_controller = ProxyController()
    
    def tearDown(self):
        """Clean up test fixtures."""
        if self.event_system.is_running():
            self.event_system.stop()
    
    def test_no_proxy_configuration_bridge(self):
        """Test no proxy configuration through bridge."""
        # Create test configuration
        config = NoProxyConfiguration()
        config.bypass_localhost = True
        config.bypass_private_networks = False
        config.add_pattern("example.com")
        config.add_pattern("*.test.com")
        
        # Set configuration through bridge
        self.config_bridge.set_no_proxy_configuration(config)
        
        # Verify configuration was set
        retrieved_config = self.config_bridge.get_no_proxy_configuration()
        self.assertEqual(retrieved_config.bypass_localhost, True)
        self.assertEqual(retrieved_config.bypass_private_networks, False)
        self.assertIn("example.com", retrieved_config.patterns)
        self.assertIn("*.test.com", retrieved_config.patterns)
    
    def test_no_proxy_environment_variables(self):
        """Test that no proxy configuration sets environment variables."""
        # Create test configuration
        config = NoProxyConfiguration()
        config.bypass_localhost = True
        config.add_pattern("example.com")
        
        # Apply configuration
        self.config_bridge.set_no_proxy_configuration(config)
        self.config_bridge._apply_no_proxy_configuration()
        
        # Check environment variables were set
        self.assertIn('NO_PROXY', os.environ)
        self.assertIn('no_proxy', os.environ)
        
        no_proxy_value = os.environ.get('NO_PROXY', '')
        self.assertIn('localhost', no_proxy_value)
        self.assertIn('example.com', no_proxy_value)
    
    def test_no_proxy_validation_integration(self):
        """Test no proxy validation in configuration validation."""
        # Create configuration with invalid no proxy settings
        config = NoProxyConfiguration()
        config.patterns.append("invalid<pattern")  # Add invalid pattern directly
        config.validate()  # This should mark it as invalid
        
        # Set invalid configuration
        self.config_bridge.set_no_proxy_configuration(config)
        
        # Test proxy configuration validation
        proxy_config = {
            'listen_address': '127.0.0.1',
            'port': 3128,
            'mode': 'manual'
        }
        
        validation_result = self.config_bridge.validate_configuration(proxy_config)
        
        # Should fail due to invalid no proxy configuration
        self.assertFalse(validation_result['is_valid'])
        self.assertTrue(any('No proxy:' in error for error in validation_result['errors']))
    
    def test_proxy_controller_no_proxy_methods(self):
        """Test proxy controller no proxy methods."""
        # Create test configuration
        config = NoProxyConfiguration()
        config.add_pattern("example.com")
        config.add_pattern("*.test.com")
        
        # Set configuration through controller
        self.proxy_controller.set_no_proxy_configuration(config)
        
        # Verify configuration was set
        retrieved_config = self.proxy_controller.get_no_proxy_configuration()
        self.assertIn("example.com", retrieved_config.patterns)
        self.assertIn("*.test.com", retrieved_config.patterns)
    
    def test_no_proxy_px_format_integration(self):
        """Test px format integration."""
        # Create configuration
        config = NoProxyConfiguration()
        config.bypass_localhost = True
        config.bypass_private_networks = True
        config.add_pattern("example.com")
        config.add_pattern("*.internal")
        
        # Convert to px format
        px_format = config.to_px_format()
        
        # Verify px format contains expected patterns
        expected_patterns = [
            'localhost', '127.0.0.1', '::1',  # localhost patterns
            '10.0.0.0/8', '192.168.0.0/16',  # private network patterns
            'example.com', '*.internal'  # custom patterns
        ]
        
        for pattern in expected_patterns:
            self.assertIn(pattern, px_format)
        
        # Test round-trip conversion
        new_config = NoProxyConfiguration.from_px_format(px_format)
        self.assertTrue(new_config.bypass_localhost)
        self.assertTrue(new_config.bypass_private_networks)
        self.assertIn("example.com", new_config.patterns)
        self.assertIn("*.internal", new_config.patterns)
    
    def test_no_proxy_pattern_matching_integration(self):
        """Test pattern matching with various URL formats."""
        # Test 1: With built-in bypass options enabled
        config = NoProxyConfiguration()
        config.bypass_localhost = True
        config.bypass_private_networks = True
        config.add_pattern("example.com")
        config.add_pattern("*.test.com")
        config.add_pattern(".internal")
        
        # Test cases with built-in bypass enabled
        builtin_test_cases = [
            # Localhost patterns (built-in)
            ("localhost", True),
            ("http://localhost:8080", True),
            ("https://127.0.0.1", True),
            
            # Private networks (built-in)
            ("192.168.1.1", True),
            ("http://10.0.0.1:3000", True),
            ("server.local", True),
            
            # Custom patterns
            ("example.com", True),
            ("http://example.com/path", True),
            ("sub.test.com", True),
            ("https://deep.sub.test.com", True),
            ("app.internal", True),
            
            # Should not bypass
            ("google.com", False),
            ("test.com", False),  # Wildcard requires subdomain
        ]
        
        for url, expected_bypass in builtin_test_cases:
            actual_bypass = config.should_bypass_proxy(url)
            self.assertEqual(actual_bypass, expected_bypass, 
                           f"Built-in test - URL: {url}, Expected: {expected_bypass}, Got: {actual_bypass}")
        
        # Test 2: With built-in bypass options disabled (test only custom patterns)
        config2 = NoProxyConfiguration()
        config2.bypass_localhost = False
        config2.bypass_private_networks = False
        config2.add_pattern("example.com")
        config2.add_pattern("*.test.com")
        config2.add_pattern("192.168.100.0/24")
        config2.add_pattern("10.0.1.1-10.0.1.100")
        config2.add_pattern(".internal")
        
        custom_test_cases = [
            # Should bypass (custom patterns only)
            ("example.com", True),
            ("sub.test.com", True),
            ("192.168.100.50", True),
            ("10.0.1.50", True),
            ("app.internal", True),
            
            # Should not bypass
            ("localhost", False),      # Built-in disabled
            ("127.0.0.1", False),      # Built-in disabled
            ("192.168.1.1", False),    # Different subnet
            ("10.0.2.1", False),       # Outside range
            ("google.com", False),
            ("test.com", False),
        ]
        
        for url, expected_bypass in custom_test_cases:
            actual_bypass = config2.should_bypass_proxy(url)
            self.assertEqual(actual_bypass, expected_bypass, 
                           f"Custom test - URL: {url}, Expected: {expected_bypass}, Got: {actual_bypass}")
    
    def test_no_proxy_error_handling(self):
        """Test error handling in no proxy integration."""
        # Test with None configuration
        try:
            self.config_bridge.set_no_proxy_configuration(None)
            # Should handle gracefully or raise appropriate error
        except Exception as e:
            # If it raises an error, it should be a reasonable one
            self.assertIsInstance(e, (TypeError, ValueError))
        
        # Test with malformed patterns
        config = NoProxyConfiguration()
        config.patterns = ["valid.com", None, "", "invalid<pattern"]
        
        # Should handle gracefully during validation
        is_valid = config.validate()
        self.assertFalse(is_valid)
        self.assertGreater(len(config.validation_errors), 0)
    
    def test_no_proxy_performance(self):
        """Test performance with large number of patterns."""
        # Create configuration with many patterns
        config = NoProxyConfiguration()
        
        # Add many patterns
        for i in range(100):
            config.add_pattern(f"server{i}.example.com")
            config.add_pattern(f"192.168.{i}.0/24")
        
        # Test pattern matching performance
        import time
        
        test_urls = [
            "server50.example.com",
            "192.168.50.1",
            "nonexistent.com"
        ]
        
        start_time = time.time()
        for _ in range(100):
            for url in test_urls:
                config.should_bypass_proxy(url)
        end_time = time.time()
        
        # Should complete reasonably quickly (less than 1 second for 300 checks)
        elapsed_time = end_time - start_time
        self.assertLess(elapsed_time, 1.0, f"Pattern matching too slow: {elapsed_time:.3f}s")
    
    def test_no_proxy_configuration_persistence(self):
        """Test configuration persistence through dict conversion."""
        # Create complex configuration
        config = NoProxyConfiguration()
        config.bypass_localhost = False
        config.bypass_private_networks = True
        config.add_pattern("example.com")
        config.add_pattern("*.test.com")
        config.add_pattern("192.168.1.0/24")
        
        # Convert to dict
        config_dict = config.to_dict()
        
        # Verify dict structure
        self.assertIn('patterns', config_dict)
        self.assertIn('bypass_localhost', config_dict)
        self.assertIn('bypass_private_networks', config_dict)
        self.assertIn('is_valid', config_dict)
        self.assertIn('validation_errors', config_dict)
        
        # Create new configuration from dict
        new_config = NoProxyConfiguration.from_dict(config_dict)
        
        # Verify configurations match
        self.assertEqual(new_config.bypass_localhost, config.bypass_localhost)
        self.assertEqual(new_config.bypass_private_networks, config.bypass_private_networks)
        self.assertEqual(new_config.patterns, config.patterns)
        self.assertEqual(new_config.is_valid, config.is_valid)


if __name__ == '__main__':
    unittest.main()