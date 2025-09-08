"""
Tests for no proxy configuration functionality.
"""

import unittest
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from px_ui.models.no_proxy_configuration import NoProxyConfiguration


class TestNoProxyConfiguration(unittest.TestCase):
    """Test cases for NoProxyConfiguration class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = NoProxyConfiguration()
    
    def test_initialization(self):
        """Test configuration initialization."""
        self.assertTrue(self.config.bypass_localhost)
        self.assertTrue(self.config.bypass_private_networks)
        self.assertEqual(len(self.config.patterns), 0)
        self.assertTrue(self.config.is_valid)
    
    def test_add_valid_patterns(self):
        """Test adding valid patterns."""
        # Test hostname
        self.assertTrue(self.config.add_pattern("example.com"))
        self.assertIn("example.com", self.config.patterns)
        
        # Test wildcard
        self.assertTrue(self.config.add_pattern("*.example.com"))
        self.assertIn("*.example.com", self.config.patterns)
        
        # Test IP address
        self.assertTrue(self.config.add_pattern("192.168.1.1"))
        self.assertIn("192.168.1.1", self.config.patterns)
        
        # Test CIDR
        self.assertTrue(self.config.add_pattern("192.168.1.0/24"))
        self.assertIn("192.168.1.0/24", self.config.patterns)
        
        # Test IP range
        self.assertTrue(self.config.add_pattern("192.168.1.1-192.168.1.100"))
        self.assertIn("192.168.1.1-192.168.1.100", self.config.patterns)
    
    def test_add_invalid_patterns(self):
        """Test adding invalid patterns."""
        # Empty pattern
        self.assertFalse(self.config.add_pattern(""))
        self.assertFalse(self.config.add_pattern("   "))
        
        # Invalid characters
        self.assertFalse(self.config.add_pattern("example<.com"))
        self.assertFalse(self.config.add_pattern("example>.com"))
        
        # Invalid IP
        self.assertFalse(self.config.add_pattern("999.999.999.999"))
        
        # Invalid CIDR
        self.assertFalse(self.config.add_pattern("192.168.1.0/99"))
    
    def test_remove_pattern(self):
        """Test removing patterns."""
        # Add pattern
        self.config.add_pattern("example.com")
        self.assertIn("example.com", self.config.patterns)
        
        # Remove pattern
        self.assertTrue(self.config.remove_pattern("example.com"))
        self.assertNotIn("example.com", self.config.patterns)
        
        # Try to remove non-existent pattern
        self.assertFalse(self.config.remove_pattern("nonexistent.com"))
    
    def test_clear_patterns(self):
        """Test clearing all patterns."""
        # Add some patterns
        self.config.add_pattern("example.com")
        self.config.add_pattern("*.test.com")
        self.assertEqual(len(self.config.patterns), 2)
        
        # Clear patterns
        self.config.clear_patterns()
        self.assertEqual(len(self.config.patterns), 0)
    
    def test_localhost_bypass(self):
        """Test localhost bypass functionality."""
        # Test localhost patterns
        self.assertTrue(self.config.should_bypass_proxy("localhost"))
        self.assertTrue(self.config.should_bypass_proxy("127.0.0.1"))
        self.assertTrue(self.config.should_bypass_proxy("::1"))
        
        # Disable localhost bypass
        self.config.bypass_localhost = False
        self.assertFalse(self.config.should_bypass_proxy("localhost"))
        self.assertFalse(self.config.should_bypass_proxy("127.0.0.1"))
    
    def test_private_network_bypass(self):
        """Test private network bypass functionality."""
        # Test private IP addresses
        self.assertTrue(self.config.should_bypass_proxy("192.168.1.1"))
        self.assertTrue(self.config.should_bypass_proxy("10.0.0.1"))
        self.assertTrue(self.config.should_bypass_proxy("172.16.0.1"))
        
        # Test private domains
        self.assertTrue(self.config.should_bypass_proxy("server.local"))
        self.assertTrue(self.config.should_bypass_proxy("intranet.internal"))
        
        # Disable private network bypass
        self.config.bypass_private_networks = False
        self.assertFalse(self.config.should_bypass_proxy("192.168.1.1"))
        self.assertFalse(self.config.should_bypass_proxy("server.local"))
    
    def test_pattern_matching(self):
        """Test pattern matching functionality."""
        # Disable built-in bypass options to test only custom patterns
        self.config.bypass_localhost = False
        self.config.bypass_private_networks = False
        
        # Add test patterns
        self.config.add_pattern("example.com")
        self.config.add_pattern("*.test.com")
        self.config.add_pattern("192.168.1.0/24")
        self.config.add_pattern("10.0.0.1-10.0.0.100")
        
        # Test exact hostname match
        self.assertTrue(self.config.should_bypass_proxy("example.com"))
        self.assertFalse(self.config.should_bypass_proxy("other.com"))
        
        # Test wildcard match
        self.assertTrue(self.config.should_bypass_proxy("sub.test.com"))
        self.assertTrue(self.config.should_bypass_proxy("deep.sub.test.com"))
        self.assertFalse(self.config.should_bypass_proxy("test.com"))  # Wildcard requires prefix
        
        # Test CIDR match
        self.assertTrue(self.config.should_bypass_proxy("192.168.1.50"))
        self.assertFalse(self.config.should_bypass_proxy("192.168.2.50"))
        
        # Test IP range match
        self.assertTrue(self.config.should_bypass_proxy("10.0.0.50"))
        self.assertFalse(self.config.should_bypass_proxy("10.0.0.200"))
    
    def test_px_format_conversion(self):
        """Test conversion to/from px format."""
        # Configure test settings
        self.config.bypass_localhost = True
        self.config.bypass_private_networks = True
        self.config.add_pattern("example.com")
        self.config.add_pattern("*.test.com")
        
        # Convert to px format
        px_format = self.config.to_px_format()
        self.assertIsInstance(px_format, str)
        self.assertIn("localhost", px_format)
        self.assertIn("127.0.0.1", px_format)
        self.assertIn("example.com", px_format)
        self.assertIn("*.test.com", px_format)
        
        # Convert back from px format
        new_config = NoProxyConfiguration.from_px_format(px_format)
        self.assertTrue(new_config.bypass_localhost)
        self.assertTrue(new_config.bypass_private_networks)
        self.assertIn("example.com", new_config.patterns)
        self.assertIn("*.test.com", new_config.patterns)
    
    def test_validation(self):
        """Test configuration validation."""
        # Valid configuration
        self.config.add_pattern("example.com")
        self.assertTrue(self.config.validate())
        self.assertTrue(self.config.is_valid)
        self.assertEqual(len(self.config.validation_errors), 0)
        
        # Add invalid pattern manually (bypassing add_pattern validation)
        self.config.patterns.append("invalid<pattern")
        self.assertFalse(self.config.validate())
        self.assertFalse(self.config.is_valid)
        self.assertGreater(len(self.config.validation_errors), 0)
    
    def test_get_summary(self):
        """Test configuration summary."""
        # Empty configuration
        self.config.bypass_localhost = False
        self.config.bypass_private_networks = False
        summary = self.config.get_summary()
        self.assertEqual(summary, "No bypass patterns configured")
        
        # With localhost only
        self.config.bypass_localhost = True
        summary = self.config.get_summary()
        self.assertIn("localhost", summary)
        
        # With custom patterns
        self.config.add_pattern("example.com")
        summary = self.config.get_summary()
        self.assertIn("custom pattern", summary)
    
    def test_pattern_count(self):
        """Test pattern count calculation."""
        # Initial count (localhost + private networks)
        initial_count = self.config.get_pattern_count()
        self.assertGreater(initial_count, 0)
        
        # Add custom pattern
        self.config.add_pattern("example.com")
        new_count = self.config.get_pattern_count()
        self.assertEqual(new_count, initial_count + 1)
        
        # Disable built-in options
        self.config.bypass_localhost = False
        self.config.bypass_private_networks = False
        final_count = self.config.get_pattern_count()
        self.assertEqual(final_count, 1)  # Only custom pattern


class TestNoProxyPatternValidation(unittest.TestCase):
    """Test cases for pattern validation."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.config = NoProxyConfiguration()
    
    def test_hostname_validation(self):
        """Test hostname pattern validation."""
        # Valid hostnames
        valid_hostnames = [
            "example.com",
            "sub.example.com",
            "test-server.local",
            "server123.domain.org"
        ]
        
        for hostname in valid_hostnames:
            self.assertTrue(self.config._validate_hostname_pattern(hostname), 
                          f"Should be valid: {hostname}")
        
        # Invalid hostnames
        invalid_hostnames = [
            "",
            ".",
            "-example.com",
            "example-.com",
            "ex<ample.com",
            "a" * 64 + ".com"  # Label too long
        ]
        
        for hostname in invalid_hostnames:
            self.assertFalse(self.config._validate_hostname_pattern(hostname), 
                           f"Should be invalid: {hostname}")
    
    def test_wildcard_validation(self):
        """Test wildcard pattern validation."""
        # Valid wildcards
        valid_wildcards = [
            "*.example.com",
            "sub.*.example.com",
            "*.local"
        ]
        
        for wildcard in valid_wildcards:
            self.assertTrue(self.config._validate_wildcard_pattern(wildcard), 
                          f"Should be valid: {wildcard}")
        
        # Invalid wildcards (too many wildcards)
        invalid_wildcard = "*.*.*.*"
        self.assertFalse(self.config._validate_wildcard_pattern(invalid_wildcard))
    
    def test_ip_validation(self):
        """Test IP pattern validation."""
        # Valid IP patterns
        valid_ips = [
            "192.168.1.1",
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.1.1-192.168.1.100"
        ]
        
        for ip in valid_ips:
            self.assertTrue(self.config._validate_ip_pattern(ip), 
                          f"Should be valid: {ip}")
        
        # Invalid IP patterns
        invalid_ips = [
            "999.999.999.999",
            "192.168.1.0/99",
            "192.168.1.100-192.168.1.1"  # Invalid range
        ]
        
        for ip in invalid_ips:
            self.assertFalse(self.config._validate_ip_pattern(ip), 
                           f"Should be invalid: {ip}")


if __name__ == '__main__':
    unittest.main()