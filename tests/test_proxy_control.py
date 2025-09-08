"""
Tests for proxy control functionality.
"""

import pytest
import threading
import time
from unittest.mock import Mock, patch, MagicMock

from px_ui.proxy.proxy_controller import ProxyController
from px_ui.proxy.configuration_bridge import PxConfigurationBridge
from px_ui.models.proxy_status import ProxyStatus


class TestProxyController:
    """Test cases for ProxyController class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.controller = ProxyController()
    
    def teardown_method(self):
        """Clean up after tests."""
        if self.controller:
            self.controller.shutdown()
    
    def test_initialization(self):
        """Test proxy controller initialization."""
        assert self.controller is not None
        assert self.controller.event_system is not None
        assert self.controller.config_bridge is not None
        assert not self.controller.is_proxy_running()
    
    def test_get_proxy_status(self):
        """Test getting proxy status."""
        status = self.controller.get_proxy_status()
        assert isinstance(status, ProxyStatus)
        assert not status.is_running
        assert status.listen_address == "127.0.0.1"
        assert status.port == 3128
    
    def test_validate_configuration_valid(self):
        """Test configuration validation with valid config."""
        config = {
            'listen_address': '127.0.0.1',
            'port': 3128,
            'mode': 'manual'
        }
        
        result = self.controller.validate_configuration(config)
        assert result['is_valid'] is True
        assert len(result['errors']) == 0
    
    def test_validate_configuration_invalid_port(self):
        """Test configuration validation with invalid port."""
        config = {
            'listen_address': '127.0.0.1',
            'port': 70000,  # Invalid port
            'mode': 'manual'
        }
        
        result = self.controller.validate_configuration(config)
        assert result['is_valid'] is False
        assert any('port' in error.lower() for error in result['errors'])
    
    def test_validate_configuration_invalid_mode(self):
        """Test configuration validation with invalid mode."""
        config = {
            'listen_address': '127.0.0.1',
            'port': 3128,
            'mode': 'invalid_mode'
        }
        
        result = self.controller.validate_configuration(config)
        assert result['is_valid'] is False
        assert any('mode' in error.lower() for error in result['errors'])
    
    def test_set_ui_callbacks(self):
        """Test setting UI callbacks."""
        status_callback = Mock()
        error_callback = Mock()
        
        self.controller.set_ui_callbacks(status_callback, error_callback)
        
        assert self.controller._status_update_callback == status_callback
        assert self.controller._error_callback == error_callback
    
    def test_pac_content_management(self):
        """Test PAC content management."""
        pac_content = """
        function FindProxyForURL(url, host) {
            return "DIRECT";
        }
        """
        
        self.controller.set_pac_content(pac_content, "test")
        
        assert self.controller.get_pac_content() == pac_content
        assert self.controller.get_pac_source() == "test"
    
    @patch('px_ui.proxy.configuration_bridge.px.main.main')
    def test_start_proxy_success(self, mock_px_main):
        """Test successful proxy start."""
        # Mock px.main.main to not actually start proxy
        mock_px_main.return_value = None
        
        config = {
            'listen_address': '127.0.0.1',
            'port': 3128,
            'mode': 'manual'
        }
        
        # Mock the configuration bridge to simulate successful start
        with patch.object(self.controller.config_bridge, 'start_proxy', return_value=True):
            result = self.controller.start_proxy(config)
            assert result is True
    
    def test_start_proxy_invalid_config(self):
        """Test proxy start with invalid configuration."""
        config = {
            'listen_address': '127.0.0.1',
            'port': 70000,  # Invalid port
            'mode': 'manual'
        }
        
        result = self.controller.start_proxy(config)
        assert result is False
    
    def test_stop_proxy_when_not_running(self):
        """Test stopping proxy when it's not running."""
        result = self.controller.stop_proxy()
        # Should return False since proxy is not running
        assert result is False


class TestPxConfigurationBridge:
    """Test cases for PxConfigurationBridge class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        from px_ui.communication.event_system import EventSystem
        self.event_system = EventSystem()
        self.bridge = PxConfigurationBridge(self.event_system)
    
    def teardown_method(self):
        """Clean up after tests."""
        if self.bridge and self.bridge.get_proxy_status().is_running:
            self.bridge.stop_proxy()
    
    def test_initialization(self):
        """Test configuration bridge initialization."""
        assert self.bridge is not None
        assert self.bridge.event_system == self.event_system
        assert not self.bridge.get_proxy_status().is_running
    
    def test_validate_configuration_valid(self):
        """Test configuration validation with valid config."""
        config = {
            'listen_address': '127.0.0.1',
            'port': 8080,
            'mode': 'manual'
        }
        
        result = self.bridge.validate_configuration(config)
        assert result['is_valid'] is True
        assert len(result['errors']) == 0
    
    def test_validate_configuration_invalid_ip(self):
        """Test configuration validation with invalid IP."""
        config = {
            'listen_address': '999.999.999.999',
            'port': 3128,
            'mode': 'manual'
        }
        
        result = self.bridge.validate_configuration(config)
        assert result['is_valid'] is False
        assert any('address' in error.lower() for error in result['errors'])
    
    def test_pac_content_validation_empty(self):
        """Test PAC content validation with empty content."""
        result = self.bridge._validate_pac_content("")
        assert result['is_valid'] is False
        assert any('empty' in error.lower() for error in result['errors'])
    
    def test_pac_content_validation_missing_function(self):
        """Test PAC content validation without FindProxyForURL function."""
        pac_content = "var test = 'hello';"
        result = self.bridge._validate_pac_content(pac_content)
        assert result['is_valid'] is False
        assert any('findproxyforurl' in error.lower() for error in result['errors'])
    
    def test_pac_content_validation_valid(self):
        """Test PAC content validation with valid content."""
        pac_content = """
        function FindProxyForURL(url, host) {
            return "DIRECT";
        }
        """
        result = self.bridge._validate_pac_content(pac_content)
        assert result['is_valid'] is True
        assert len(result['errors']) == 0
    
    def test_status_callbacks(self):
        """Test status change callbacks."""
        callback = Mock()
        self.bridge.add_status_callback(callback)
        
        # Simulate status change
        new_status = ProxyStatus(
            is_running=True,
            listen_address="127.0.0.1",
            port=3128,
            mode="manual"
        )
        self.bridge._proxy_status = new_status
        self.bridge._notify_status_change()
        
        callback.assert_called_once_with(new_status)
        
        # Test removing callback
        self.bridge.remove_status_callback(callback)
        callback.reset_mock()
        self.bridge._notify_status_change()
        callback.assert_not_called()
    
    def test_port_in_use_check(self):
        """Test port availability checking."""
        # Test with a port that should be available
        assert not self.bridge._is_port_in_use(0)  # Port 0 should be available
        
        # Test with a commonly used port (may or may not be available)
        # Just ensure the method doesn't crash
        result = self.bridge._is_port_in_use(80)
        assert isinstance(result, bool)


if __name__ == '__main__':
    pytest.main([__file__])