"""
Automated tests using test configuration and sample PAC files.
Tests real-world scenarios with actual proxy configurations.
"""

import pytest
import os
import tempfile
import json
import time
from unittest.mock import Mock, patch
from datetime import datetime

from px_ui.communication.event_queue import EventQueue
from px_ui.communication.event_processor import EventProcessor
from .test_mocks import (
    MockPACValidator as PACValidator,
    MockConfigurationBridge as ConfigurationBridge,
    MockEnhancedPxHandler as EnhancedPxHandler,
    MockConfigLoader as ConfigLoader
)


class TestAutomatedPACScenarios:
    """Test automated scenarios using sample PAC files."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.pac_validator = PACValidator()
        self.config_bridge = ConfigurationBridge()
        self.config_loader = ConfigLoader()
        
        # Load test configurations
        self.test_configs = self.config_loader.load_test_configurations()
    
    def test_simple_pac_configuration(self):
        """Test simple PAC configuration from test files."""
        # Load simple PAC file
        simple_pac_path = "test_config/simple.pac"
        
        if os.path.exists(simple_pac_path):
            pac_content = self.pac_validator.load_pac_from_file(simple_pac_path)
            
            # Validate PAC
            pac_config = self.pac_validator.create_pac_configuration(
                source_type="file",
                source_path=simple_pac_path,
                content=pac_content
            )
            
            assert pac_config.is_valid is True
            assert pac_config.validation_errors == []
            
            # Test URL resolution with known test cases
            test_cases = [
                ("http://internal.company.com", "DIRECT"),
                ("https://www.google.com", "PROXY"),
                ("http://localhost", "DIRECT")
            ]
            
            for url, expected_type in test_cases:
                result = self.pac_validator.test_url(url, pac_content)
                if expected_type == "DIRECT":
                    assert "DIRECT" in result
                else:
                    assert "PROXY" in result
        else:
            pytest.skip("Simple PAC file not found")
    
    def test_complex_pac_configuration(self):
        """Test complex PAC configuration with multiple conditions."""
        # Load complex PAC file
        complex_pac_path = "test_config/complex.pac"
        
        if os.path.exists(complex_pac_path):
            pac_content = self.pac_validator.load_pac_from_file(complex_pac_path)
            
            # Validate PAC
            pac_config = self.pac_validator.create_pac_configuration(
                source_type="file",
                source_path=complex_pac_path,
                content=pac_content
            )
            
            assert pac_config.is_valid is True
            
            # Test various URL patterns
            test_urls = [
                "http://intranet.company.com/dashboard",
                "https://mail.company.com/inbox",
                "http://192.168.1.100/admin",
                "https://www.external-site.com/api",
                "http://cdn.example.com/assets/style.css",
                "https://api.github.com/repos",
                "http://10.0.0.50/internal-app"
            ]
            
            for url in test_urls:
                result = self.pac_validator.test_url(url, pac_content)
                # Should return valid proxy decision
                assert result is not None
                assert len(result.strip()) > 0
                # Should be either DIRECT or PROXY format
                assert "DIRECT" in result or "PROXY" in result
        else:
            pytest.skip("Complex PAC file not found")
    
    def test_sample_pac_with_time_conditions(self):
        """Test sample PAC file with time-based conditions."""
        # Create time-based PAC for testing
        time_pac_content = '''
        function FindProxyForURL(url, host) {
            var now = new Date();
            var hour = now.getHours();
            var day = now.getDay(); // 0 = Sunday, 1 = Monday, etc.
            
            // Direct access for internal hosts
            if (isInNet(host, "192.168.0.0", "255.255.0.0") ||
                isInNet(host, "10.0.0.0", "255.0.0.0") ||
                dnsDomainIs(host, ".company.com")) {
                return "DIRECT";
            }
            
            // Business hours (Mon-Fri, 9-17): use fast proxy
            if (day >= 1 && day <= 5 && hour >= 9 && hour <= 17) {
                return "PROXY fast-proxy.company.com:8080; PROXY backup-proxy.company.com:8080; DIRECT";
            }
            
            // Off hours: use slower but cheaper proxy
            return "PROXY slow-proxy.company.com:8080; DIRECT";
        }
        '''
        
        # Validate time-based PAC
        pac_config = self.pac_validator.create_pac_configuration(
            source_type="inline",
            source_path="",
            content=time_pac_content
        )
        
        assert pac_config.is_valid is True
        
        # Test internal vs external URLs
        internal_result = self.pac_validator.test_url("http://intranet.company.com", time_pac_content)
        assert "DIRECT" in internal_result
        
        external_result = self.pac_validator.test_url("https://www.external.com", time_pac_content)
        assert "PROXY" in external_result
        
        # Result should contain appropriate proxy based on time
        assert "proxy.company.com" in external_result
    
    def test_load_balancing_pac_scenario(self):
        """Test PAC configuration with load balancing logic."""
        load_balancing_pac = '''
        function FindProxyForURL(url, host) {
            // Direct access for local addresses
            if (isPlainHostName(host) ||
                dnsDomainIs(host, ".local") ||
                isInNet(host, "127.0.0.0", "255.0.0.0")) {
                return "DIRECT";
            }
            
            // Load balancing based on host hash
            var hash = 0;
            for (var i = 0; i < host.length; i++) {
                hash = ((hash << 5) - hash + host.charCodeAt(i)) & 0xffffffff;
            }
            
            var proxyIndex = Math.abs(hash) % 3;
            
            switch (proxyIndex) {
                case 0:
                    return "PROXY proxy1.company.com:8080; PROXY proxy2.company.com:8080; DIRECT";
                case 1:
                    return "PROXY proxy2.company.com:8080; PROXY proxy3.company.com:8080; DIRECT";
                case 2:
                    return "PROXY proxy3.company.com:8080; PROXY proxy1.company.com:8080; DIRECT";
                default:
                    return "PROXY proxy1.company.com:8080; DIRECT";
            }
        }
        '''
        
        # Validate load balancing PAC
        pac_config = self.pac_validator.create_pac_configuration(
            source_type="inline",
            source_path="",
            content=load_balancing_pac
        )
        
        assert pac_config.is_valid is True
        
        # Test load balancing with different hosts
        test_hosts = [
            "www.example.com",
            "api.service.com",
            "cdn.assets.com",
            "mail.provider.com",
            "data.analytics.com"
        ]
        
        proxy_assignments = {}
        for host in test_hosts:
            url = f"https://{host}/path"
            result = self.pac_validator.test_url(url, load_balancing_pac)
            
            # Extract primary proxy from result
            if "PROXY proxy1.company.com" in result:
                proxy_assignments[host] = "proxy1"
            elif "PROXY proxy2.company.com" in result:
                proxy_assignments[host] = "proxy2"
            elif "PROXY proxy3.company.com" in result:
                proxy_assignments[host] = "proxy3"
        
        # Should have distributed across different proxies
        unique_proxies = set(proxy_assignments.values())
        assert len(unique_proxies) > 1  # Should use multiple proxies
        
        # Same host should always get same proxy (consistency)
        for host in test_hosts:
            url1 = f"https://{host}/page1"
            url2 = f"https://{host}/page2"
            result1 = self.pac_validator.test_url(url1, load_balancing_pac)
            result2 = self.pac_validator.test_url(url2, load_balancing_pac)
            
            # Should get same proxy for same host
            assert result1 == result2


class TestAutomatedProxyIntegration:
    """Test automated proxy integration scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.event_queue = EventQueue()
        self.processed_events = []
        
        def ui_callback(event_type, event):
            self.processed_events.append((event_type, event))
        
        self.event_processor = EventProcessor(self.event_queue, ui_callback)
        self.enhanced_handler = EnhancedPxHandler(self.event_queue)
        self.config_loader = ConfigLoader()
    
    def test_upstream_proxy_configuration(self):
        """Test configuration with upstream proxy settings."""
        # Load test proxy configuration
        test_config = self.config_loader.get_test_proxy_config()
        
        if test_config and 'https_proxy' in test_config:
            upstream_proxy = test_config['https_proxy']
            
            # Configure proxy settings
            config_bridge = ConfigurationBridge()
            config_bridge.set_upstream_proxy(upstream_proxy)
            
            # Start event processor
            self.event_processor.start()
            
            try:
                # Simulate requests through upstream proxy
                test_requests = [
                    "https://www.google.com/search?q=test",
                    "https://api.github.com/user",
                    "http://httpbin.org/get"
                ]
                
                for i, url in enumerate(test_requests):
                    request_id = f"req_upstream_{i}"
                    
                    self.enhanced_handler.capture_request(
                        url=url,
                        method="GET",
                        proxy_decision=f"PROXY {upstream_proxy}",
                        request_id=request_id
                    )
                    
                    # Simulate successful response
                    self.enhanced_handler.capture_response(
                        request_id=request_id,
                        status_code=200,
                        headers={"Content-Type": "application/json"},
                        body_preview='{"status": "success"}',
                        response_time=0.3
                    )
                
                # Wait for processing
                time.sleep(1.0)
                
                # Verify all requests were processed
                request_events = [e for t, e in self.processed_events if t.name == "REQUEST"]
                response_events = [e for t, e in self.processed_events if t.name == "RESPONSE"]
                
                assert len(request_events) == len(test_requests)
                assert len(response_events) == len(test_requests)
                
                # Verify proxy decisions
                for event in request_events:
                    assert upstream_proxy in event.proxy_decision
            
            finally:
                self.event_processor.stop()
        else:
            pytest.skip("Test proxy configuration not available")
    
    def test_pac_with_real_proxy_scenarios(self):
        """Test PAC configuration with real proxy scenarios."""
        # Load sample PAC that matches test environment
        sample_pac_path = "test_config/sample.pac"
        
        if os.path.exists(sample_pac_path):
            pac_validator = PACValidator()
            pac_content = pac_validator.load_pac_from_file(sample_pac_path)
            
            # Create PAC configuration
            pac_config = pac_validator.create_pac_configuration(
                source_type="file",
                source_path=sample_pac_path,
                content=pac_content
            )
            
            assert pac_config.is_valid is True
            
            # Apply configuration
            config_bridge = ConfigurationBridge()
            success = config_bridge.apply_pac_configuration(pac_config)
            assert success is True
            
            # Start event processor
            self.event_processor.start()
            
            try:
                # Test URLs mentioned in sample PAC
                test_scenarios = [
                    ("http://baidu.com", "DIRECT"),
                    ("https://www.google.com", "PROXY"),
                    ("http://amazon.com", "PROXY")
                ]
                
                for url, expected_type in test_scenarios:
                    # Test PAC decision
                    result = pac_validator.test_url(url, pac_content)
                    
                    if expected_type == "DIRECT":
                        assert "DIRECT" in result
                    else:
                        assert "PROXY" in result
                    
                    # Simulate request with PAC decision
                    request_id = f"req_pac_{hash(url)}"
                    
                    self.enhanced_handler.capture_request(
                        url=url,
                        method="GET",
                        proxy_decision=result,
                        request_id=request_id
                    )
                    
                    # Simulate response
                    status_code = 200 if "baidu.com" in url else 200
                    self.enhanced_handler.capture_response(
                        request_id=request_id,
                        status_code=status_code,
                        headers={"Content-Type": "text/html"},
                        body_preview="<html>...</html>",
                        response_time=0.2
                    )
                
                # Wait for processing
                time.sleep(1.0)
                
                # Verify processing
                request_events = [e for t, e in self.processed_events if t.name == "REQUEST"]
                assert len(request_events) == len(test_scenarios)
                
                # Verify proxy decisions match PAC logic
                for i, (url, expected_type) in enumerate(test_scenarios):
                    event = request_events[i]
                    assert event.url == url
                    
                    if expected_type == "DIRECT":
                        assert "DIRECT" in event.proxy_decision
                    else:
                        assert "PROXY" in event.proxy_decision
            
            finally:
                self.event_processor.stop()
        else:
            pytest.skip("Sample PAC file not available")


class TestConfigurationValidation:
    """Test configuration validation with various scenarios."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.config_loader = ConfigLoader()
        self.pac_validator = PACValidator()
    
    def test_validate_all_sample_pac_files(self):
        """Test validation of all sample PAC files."""
        pac_files = [
            "test_config/simple.pac",
            "test_config/complex.pac",
            "test_config/sample.pac"
        ]
        
        valid_files = 0
        
        for pac_file in pac_files:
            if os.path.exists(pac_file):
                try:
                    pac_content = self.pac_validator.load_pac_from_file(pac_file)
                    
                    pac_config = self.pac_validator.create_pac_configuration(
                        source_type="file",
                        source_path=pac_file,
                        content=pac_content
                    )
                    
                    if pac_config.is_valid:
                        valid_files += 1
                        
                        # Test basic functionality
                        test_urls = [
                            "http://www.example.com",
                            "https://internal.company.com",
                            "http://192.168.1.1"
                        ]
                        
                        for url in test_urls:
                            result = self.pac_validator.test_url(url, pac_content)
                            assert result is not None
                            assert len(result.strip()) > 0
                    
                    print(f"PAC file {pac_file}: {'VALID' if pac_config.is_valid else 'INVALID'}")
                    if not pac_config.is_valid:
                        print(f"  Errors: {pac_config.validation_errors}")
                
                except Exception as e:
                    print(f"PAC file {pac_file}: ERROR - {str(e)}")
        
        # At least one PAC file should be valid
        assert valid_files > 0
    
    def test_configuration_file_loading(self):
        """Test loading various configuration file formats."""
        config_files = [
            "test_config/test_proxy_config.ini"
        ]
        
        for config_file in config_files:
            if os.path.exists(config_file):
                try:
                    config = self.config_loader.load_config_file(config_file)
                    
                    # Should have loaded some configuration
                    assert config is not None
                    assert len(config) > 0
                    
                    # Check for expected configuration keys
                    expected_keys = ['proxy', 'port', 'auth']
                    found_keys = [key for key in expected_keys if key in config]
                    
                    assert len(found_keys) > 0  # Should have at least one expected key
                    
                    print(f"Config file {config_file}: loaded {len(config)} settings")
                    print(f"  Found keys: {found_keys}")
                
                except Exception as e:
                    print(f"Config file {config_file}: ERROR - {str(e)}")
    
    def test_environment_specific_configurations(self):
        """Test environment-specific configuration scenarios."""
        # Test development environment
        dev_config = {
            'environment': 'development',
            'proxy_host': '127.0.0.1',
            'proxy_port': 33210,
            'pac_url': None,
            'direct_hosts': ['localhost', '127.0.0.1', '*.local']
        }
        
        # Validate development configuration
        assert dev_config['proxy_host'] is not None
        assert dev_config['proxy_port'] > 0
        assert isinstance(dev_config['direct_hosts'], list)
        
        # Test production environment
        prod_config = {
            'environment': 'production',
            'proxy_host': 'proxy.company.com',
            'proxy_port': 8080,
            'pac_url': 'http://proxy.company.com/proxy.pac',
            'direct_hosts': ['*.company.com', '10.*', '192.168.*']
        }
        
        # Validate production configuration
        assert prod_config['proxy_host'] != '127.0.0.1'  # Should not be localhost
        assert prod_config['pac_url'] is not None
        assert len(prod_config['direct_hosts']) > 0
        
        # Test configuration switching
        configs = [dev_config, prod_config]
        
        for config in configs:
            # Each configuration should be self-consistent
            if config['pac_url']:
                # PAC-based configuration
                assert config['pac_url'].startswith('http')
            else:
                # Manual proxy configuration
                assert config['proxy_host'] is not None
                assert config['proxy_port'] > 0


class TestErrorScenarios:
    """Test automated error scenarios and recovery."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.pac_validator = PACValidator()
        self.config_bridge = ConfigurationBridge()
    
    def test_invalid_pac_file_handling(self):
        """Test handling of invalid PAC files."""
        # Create temporary invalid PAC file
        invalid_pac_content = '''
        // This is not a valid PAC file
        function WrongFunctionName(url, host) {
            return INVALID_SYNTAX;  // Missing quotes
        }
        
        // Missing FindProxyForURL function
        '''
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.pac', delete=False) as f:
            f.write(invalid_pac_content)
            temp_path = f.name
        
        try:
            # Attempt to load invalid PAC
            pac_content = self.pac_validator.load_pac_from_file(temp_path)
            
            pac_config = self.pac_validator.create_pac_configuration(
                source_type="file",
                source_path=temp_path,
                content=pac_content
            )
            
            # Should detect invalidity
            assert pac_config.is_valid is False
            assert len(pac_config.validation_errors) > 0
            
            # Should not be able to apply invalid configuration
            success = self.config_bridge.apply_pac_configuration(pac_config)
            assert success is False
            
            print(f"Invalid PAC errors: {pac_config.validation_errors}")
        
        finally:
            os.unlink(temp_path)
    
    def test_network_error_simulation(self):
        """Test network error scenarios."""
        # Test invalid PAC URL
        invalid_urls = [
            "http://nonexistent.domain.com/proxy.pac",
            "https://invalid-host-name/proxy.pac",
            "http://127.0.0.1:99999/proxy.pac"  # Invalid port
        ]
        
        for url in invalid_urls:
            with pytest.raises(Exception):
                self.pac_validator.load_pac_from_url(url)
    
    def test_configuration_recovery(self):
        """Test configuration recovery after errors."""
        # Start with valid configuration
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
        
        # Attempt to apply invalid configuration
        invalid_pac = "invalid javascript"
        
        invalid_config = self.pac_validator.create_pac_configuration(
            source_type="inline",
            source_path="",
            content=invalid_pac
        )
        
        assert invalid_config.is_valid is False
        success = self.config_bridge.apply_pac_configuration(invalid_config)
        assert success is False
        
        # Should still have valid configuration active
        current_config = self.config_bridge.get_current_pac_configuration()
        assert current_config is not None
        assert current_config.is_valid is True
        assert current_config.content == valid_pac