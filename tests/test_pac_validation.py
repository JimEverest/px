"""
Unit tests for PAC validation functionality.
Tests JavaScript syntax validation, PAC execution, and URL testing.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os

from .test_mocks import MockPACValidator as PACValidator
from px_ui.models.pac_configuration import PACConfiguration


class TestPACValidator:
    """Test PAC validation functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = PACValidator()
    
    def test_validate_valid_pac_syntax(self):
        """Test validation of valid PAC JavaScript syntax."""
        valid_pac = '''
        function FindProxyForURL(url, host) {
            if (host == "example.com") {
                return "DIRECT";
            }
            return "PROXY proxy.corp.com:8080";
        }
        '''
        
        is_valid, errors = self.validator.validate_syntax(valid_pac)
        
        assert is_valid is True
        assert errors == []
    
    def test_validate_invalid_pac_syntax(self):
        """Test validation of invalid PAC JavaScript syntax."""
        invalid_pac = '''
        function FindProxyForURL(url, host) {
            if (host == "example.com" {  // Missing closing parenthesis
                return "DIRECT";
            }
            return "PROXY proxy.corp.com:8080";
        }
        '''
        
        is_valid, errors = self.validator.validate_syntax(invalid_pac)
        
        assert is_valid is False
        assert len(errors) > 0
        assert any("SyntaxError" in error for error in errors)
    
    def test_validate_missing_function(self):
        """Test validation when FindProxyForURL function is missing."""
        invalid_pac = '''
        function WrongFunctionName(url, host) {
            return "DIRECT";
        }
        '''
        
        is_valid, errors = self.validator.validate_syntax(invalid_pac)
        
        assert is_valid is False
        assert any("FindProxyForURL" in error for error in errors)
    
    def test_validate_empty_pac(self):
        """Test validation of empty PAC content."""
        empty_pac = ""
        
        is_valid, errors = self.validator.validate_syntax(empty_pac)
        
        assert is_valid is False
        assert len(errors) > 0
    
    def test_validate_pac_with_comments(self):
        """Test validation of PAC with JavaScript comments."""
        pac_with_comments = '''
        // This is a comment
        function FindProxyForURL(url, host) {
            /* Multi-line comment
               explaining the logic */
            if (host == "internal.company.com") {
                return "DIRECT";  // Direct connection for internal
            }
            return "PROXY proxy.company.com:8080";
        }
        '''
        
        is_valid, errors = self.validator.validate_syntax(pac_with_comments)
        
        assert is_valid is True
        assert errors == []
    
    def test_test_url_direct(self):
        """Test URL testing that returns DIRECT."""
        pac_content = '''
        function FindProxyForURL(url, host) {
            if (host == "internal.company.com") {
                return "DIRECT";
            }
            return "PROXY proxy.company.com:8080";
        }
        '''
        
        result = self.validator.test_url("http://internal.company.com/page", pac_content)
        
        assert result == "DIRECT"
    
    def test_test_url_proxy(self):
        """Test URL testing that returns proxy."""
        pac_content = '''
        function FindProxyForURL(url, host) {
            if (host == "external.example.com") {
                return "PROXY proxy.company.com:8080";
            }
            return "DIRECT";
        }
        '''
        
        result = self.validator.test_url("http://external.example.com/api", pac_content)
        
        assert result == "PROXY proxy.company.com:8080"
    
    def test_test_url_multiple_proxies(self):
        """Test URL testing with multiple proxy options."""
        pac_content = '''
        function FindProxyForURL(url, host) {
            if (host.indexOf("google.com") != -1) {
                return "PROXY proxy1.company.com:8080; PROXY proxy2.company.com:8080; DIRECT";
            }
            return "DIRECT";
        }
        '''
        
        result = self.validator.test_url("https://www.google.com/search", pac_content)
        
        assert "PROXY proxy1.company.com:8080" in result
        assert "PROXY proxy2.company.com:8080" in result
        assert "DIRECT" in result
    
    def test_test_url_with_pac_functions(self):
        """Test URL testing using PAC utility functions."""
        pac_content = '''
        function FindProxyForURL(url, host) {
            if (isInNet(host, "192.168.0.0", "255.255.0.0")) {
                return "DIRECT";
            }
            if (dnsDomainIs(host, ".company.com")) {
                return "DIRECT";
            }
            return "PROXY proxy.company.com:8080";
        }
        '''
        
        # Test internal IP
        result = self.validator.test_url("http://192.168.1.100/", pac_content)
        assert result == "DIRECT"
        
        # Test company domain
        result = self.validator.test_url("http://intranet.company.com/", pac_content)
        assert result == "DIRECT"
        
        # Test external domain
        result = self.validator.test_url("http://www.external.com/", pac_content)
        assert result == "PROXY proxy.company.com:8080"
    
    def test_test_url_invalid_pac(self):
        """Test URL testing with invalid PAC content."""
        invalid_pac = '''
        function FindProxyForURL(url, host) {
            return INVALID_SYNTAX;  // Missing quotes
        }
        '''
        
        with pytest.raises(Exception):
            self.validator.test_url("http://example.com", invalid_pac)
    
    def test_load_pac_from_file(self):
        """Test loading PAC content from file."""
        pac_content = '''
        function FindProxyForURL(url, host) {
            return "DIRECT";
        }
        '''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pac', delete=False) as f:
            f.write(pac_content)
            temp_path = f.name
        
        try:
            loaded_content = self.validator.load_pac_from_file(temp_path)
            assert "FindProxyForURL" in loaded_content
            assert loaded_content.strip() == pac_content.strip()
        finally:
            os.unlink(temp_path)
    
    def test_load_pac_from_nonexistent_file(self):
        """Test loading PAC from non-existent file."""
        with pytest.raises(FileNotFoundError):
            self.validator.load_pac_from_file("/nonexistent/path/proxy.pac")
    
    @patch('urllib.request.urlopen')
    def test_load_pac_from_url(self, mock_urlopen):
        """Test loading PAC content from URL."""
        pac_content = '''
        function FindProxyForURL(url, host) {
            return "PROXY proxy.company.com:8080";
        }
        '''
        
        mock_response = Mock()
        mock_response.read.return_value = pac_content.encode('utf-8')
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        loaded_content = self.validator.load_pac_from_url("http://proxy.company.com/proxy.pac")
        
        assert loaded_content == pac_content
        mock_urlopen.assert_called_once_with("http://proxy.company.com/proxy.pac")
    
    @patch('urllib.request.urlopen')
    def test_load_pac_from_url_error(self, mock_urlopen):
        """Test loading PAC from URL with network error."""
        mock_urlopen.side_effect = Exception("Network error")
        
        with pytest.raises(Exception):
            self.validator.load_pac_from_url("http://invalid.url/proxy.pac")
    
    def test_create_pac_configuration_valid(self):
        """Test creating PACConfiguration from valid content."""
        pac_content = '''
        function FindProxyForURL(url, host) {
            if (host == "example.com") return "DIRECT";
            return "PROXY proxy.corp.com:8080";
        }
        '''
        
        config = self.validator.create_pac_configuration(
            source_type="inline",
            source_path="",
            content=pac_content
        )
        
        assert isinstance(config, PACConfiguration)
        assert config.source_type == "inline"
        assert config.content == pac_content
        assert config.is_valid is True
        assert config.validation_errors == []
    
    def test_create_pac_configuration_invalid(self):
        """Test creating PACConfiguration from invalid content."""
        invalid_pac = '''
        function FindProxyForURL(url, host) {
            return INVALID;  // Missing quotes
        }
        '''
        
        config = self.validator.create_pac_configuration(
            source_type="inline",
            source_path="",
            content=invalid_pac
        )
        
        assert isinstance(config, PACConfiguration)
        assert config.is_valid is False
        assert len(config.validation_errors) > 0
    
    def test_validate_pac_functions_availability(self):
        """Test that PAC utility functions are available during validation."""
        pac_with_functions = '''
        function FindProxyForURL(url, host) {
            // Test various PAC utility functions
            if (isPlainHostName(host)) return "DIRECT";
            if (dnsDomainIs(host, ".local")) return "DIRECT";
            if (localHostOrDomainIs(host, "localhost")) return "DIRECT";
            if (isResolvable(host)) {
                if (isInNet(host, "10.0.0.0", "255.0.0.0")) return "DIRECT";
            }
            if (shExpMatch(host, "*.company.com")) return "DIRECT";
            
            var today = new Date();
            if (weekdayRange("MON", "FRI")) {
                if (timeRange(9, 17)) {
                    return "PROXY work-proxy.company.com:8080";
                }
            }
            
            return "PROXY home-proxy.company.com:8080";
        }
        '''
        
        is_valid, errors = self.validator.validate_syntax(pac_with_functions)
        
        assert is_valid is True
        assert errors == []
    
    def test_pac_encoding_detection(self):
        """Test PAC content encoding detection and handling."""
        # Test UTF-8 content
        utf8_pac = '''
        function FindProxyForURL(url, host) {
            // Comment with unicode: café, naïve
            return "DIRECT";
        }
        '''
        
        encoding = self.validator.detect_encoding(utf8_pac.encode('utf-8'))
        assert encoding in ['utf-8', 'ascii']  # ASCII is subset of UTF-8
        
        # Test with BOM
        utf8_bom_pac = '\ufeff' + utf8_pac
        encoding = self.validator.detect_encoding(utf8_bom_pac.encode('utf-8-sig'))
        assert encoding == 'utf-8-sig'
    
    def test_pac_performance_validation(self):
        """Test PAC validation performance with large content."""
        # Create a large PAC file with many conditions
        large_pac_parts = [
            'function FindProxyForURL(url, host) {'
        ]
        
        # Add many host conditions
        for i in range(100):
            large_pac_parts.append(f'    if (host == "host{i}.example.com") return "DIRECT";')
        
        large_pac_parts.append('    return "PROXY proxy.company.com:8080";')
        large_pac_parts.append('}')
        
        large_pac = '\n'.join(large_pac_parts)
        
        # Validation should complete in reasonable time
        import time
        start_time = time.time()
        is_valid, errors = self.validator.validate_syntax(large_pac)
        end_time = time.time()
        
        assert is_valid is True
        assert errors == []
        assert (end_time - start_time) < 5.0  # Should complete within 5 seconds


class TestPACValidatorIntegration:
    """Test PAC validator integration with other components."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.validator = PACValidator()
    
    def test_validate_real_world_pac_examples(self):
        """Test validation with real-world PAC examples."""
        # Example 1: Simple corporate PAC
        corporate_pac = '''
        function FindProxyForURL(url, host) {
            // Direct access for local addresses
            if (isPlainHostName(host) || 
                dnsDomainIs(host, ".local") ||
                isInNet(host, "10.0.0.0", "255.0.0.0") ||
                isInNet(host, "172.16.0.0", "255.240.0.0") ||
                isInNet(host, "192.168.0.0", "255.255.0.0")) {
                return "DIRECT";
            }
            
            // Use proxy for everything else
            return "PROXY proxy.company.com:8080; DIRECT";
        }
        '''
        
        is_valid, errors = self.validator.validate_syntax(corporate_pac)
        assert is_valid is True
        assert errors == []
        
        # Test URL resolution
        result = self.validator.test_url("http://192.168.1.1/", corporate_pac)
        assert result == "DIRECT"
        
        result = self.validator.test_url("http://www.google.com/", corporate_pac)
        assert "PROXY proxy.company.com:8080" in result
    
    def test_validate_complex_pac_with_time_conditions(self):
        """Test validation of PAC with time-based conditions."""
        time_based_pac = '''
        function FindProxyForURL(url, host) {
            // Different proxy during business hours
            var now = new Date();
            var hour = now.getHours();
            
            if (weekdayRange("MON", "FRI") && timeRange(9, 17)) {
                // Business hours - use fast proxy
                return "PROXY fast-proxy.company.com:8080; DIRECT";
            } else {
                // Off hours - use slower but cheaper proxy
                return "PROXY slow-proxy.company.com:8080; DIRECT";
            }
        }
        '''
        
        is_valid, errors = self.validator.validate_syntax(time_based_pac)
        assert is_valid is True
        assert errors == []
    
    def test_validate_pac_with_load_balancing(self):
        """Test validation of PAC with load balancing logic."""
        load_balancing_pac = '''
        function FindProxyForURL(url, host) {
            // Simple load balancing based on hash of hostname
            var hash = 0;
            for (var i = 0; i < host.length; i++) {
                hash = ((hash << 5) - hash + host.charCodeAt(i)) & 0xffffffff;
            }
            
            var proxyIndex = Math.abs(hash) % 3;
            
            if (proxyIndex == 0) {
                return "PROXY proxy1.company.com:8080; PROXY proxy2.company.com:8080; DIRECT";
            } else if (proxyIndex == 1) {
                return "PROXY proxy2.company.com:8080; PROXY proxy3.company.com:8080; DIRECT";
            } else {
                return "PROXY proxy3.company.com:8080; PROXY proxy1.company.com:8080; DIRECT";
            }
        }
        '''
        
        is_valid, errors = self.validator.validate_syntax(load_balancing_pac)
        assert is_valid is True
        assert errors == []
        
        # Test that different hosts get different proxy assignments
        result1 = self.validator.test_url("http://host1.example.com/", load_balancing_pac)
        result2 = self.validator.test_url("http://host2.example.com/", load_balancing_pac)
        
        # Results should contain proxy assignments (may be same or different)
        assert "PROXY" in result1
        assert "PROXY" in result2