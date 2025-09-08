"""
Proxy controller for managing proxy lifecycle and integration with UI.

This module provides the main controller class that coordinates between
the UI components and the proxy engine.
"""

import logging
import threading
from typing import Optional, Dict, Any, Callable

from .configuration_bridge import PxConfigurationBridge
from ..communication.event_system import EventSystem
from ..models.proxy_status import ProxyStatus
from ..models.no_proxy_configuration import NoProxyConfiguration


class ProxyController:
    """
    Main controller for proxy operations and UI integration.
    
    This class coordinates between the UI components and the proxy engine,
    managing the proxy lifecycle and configuration.
    """
    
    def __init__(self, event_system: Optional[EventSystem] = None):
        """Initialize the proxy controller."""
        self.logger = logging.getLogger(__name__)
        
        # Initialize event system
        self.event_system = event_system or EventSystem()
        
        # Initialize configuration bridge
        self.config_bridge = PxConfigurationBridge(self.event_system)
        
        # UI callbacks
        self._status_update_callback: Optional[Callable[[ProxyStatus], None]] = None
        self._error_callback: Optional[Callable[[str, str], None]] = None
        
        # Register for status updates
        self.config_bridge.add_status_callback(self._on_status_change)
        
        self.logger.info("Proxy controller initialized")
    
    def set_ui_callbacks(self, 
                        status_callback: Optional[Callable[[ProxyStatus], None]] = None,
                        error_callback: Optional[Callable[[str, str], None]] = None):
        """
        Set UI callback functions.
        
        Args:
            status_callback: Function to call when proxy status changes
            error_callback: Function to call when errors occur
        """
        self._status_update_callback = status_callback
        self._error_callback = error_callback
        self.logger.info("UI callbacks configured")
    
    def start_proxy(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Start the proxy service.
        
        Args:
            config: Optional configuration dictionary
            
        Returns:
            True if proxy started successfully, False otherwise
        """
        try:
            self.logger.info("Starting proxy service...")
            
            # Use default configuration if none provided
            if config is None:
                config = self._get_default_config()
            
            # Extract and set PAC configuration if provided
            if 'pac_config' in config:
                pac_config = config['pac_config']
                if pac_config and hasattr(pac_config, 'content'):
                    self.config_bridge.set_pac_content(
                        pac_config.content, 
                        pac_config.get_source_display_name()
                    )
                    self.logger.info(f"PAC content set from {pac_config.get_source_display_name()}")
            
            # Validate configuration
            validation_result = self.config_bridge.validate_configuration(config)
            if not validation_result['is_valid']:
                error_msg = "Configuration validation failed:\n" + "\n".join(validation_result['errors'])
                self.logger.error(error_msg)
                self._notify_error("Configuration Error", error_msg)
                return False
            
            # Show warnings if any
            if validation_result['warnings']:
                warning_msg = "Configuration warnings:\n" + "\n".join(validation_result['warnings'])
                self.logger.warning(warning_msg)
            
            # Start the proxy
            success = self.config_bridge.start_proxy(config)
            
            if success:
                self.logger.info("Proxy service started successfully")
            else:
                self.logger.error("Failed to start proxy service")
                self._notify_error("Proxy Error", "Failed to start proxy service")
            
            return success
            
        except Exception as e:
            error_msg = f"Unexpected error starting proxy: {str(e)}"
            self.logger.error(error_msg)
            self._notify_error("Proxy Error", error_msg)
            return False
    
    def stop_proxy(self) -> bool:
        """
        Stop the proxy service.
        
        Returns:
            True if proxy stopped successfully, False otherwise
        """
        try:
            self.logger.info("Stopping proxy service...")
            
            success = self.config_bridge.stop_proxy()
            
            if success:
                self.logger.info("Proxy service stopped successfully")
            else:
                self.logger.error("Failed to stop proxy service")
                self._notify_error("Proxy Error", "Failed to stop proxy service")
            
            return success
            
        except Exception as e:
            error_msg = f"Unexpected error stopping proxy: {str(e)}"
            self.logger.error(error_msg)
            self._notify_error("Proxy Error", error_msg)
            return False
    
    def get_proxy_status(self) -> ProxyStatus:
        """
        Get current proxy status.
        
        Returns:
            Current proxy status
        """
        return self.config_bridge.get_proxy_status()
    
    def is_proxy_running(self) -> bool:
        """
        Check if proxy is currently running.
        
        Returns:
            True if proxy is running, False otherwise
        """
        return self.config_bridge.get_proxy_status().is_running
    
    def validate_configuration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate proxy configuration.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            Dictionary with validation results
        """
        return self.config_bridge.validate_configuration(config)
    
    def set_pac_content(self, content: str, source: str = "inline"):
        """
        Set PAC content for the proxy.
        
        Args:
            content: PAC file content
            source: Source description (file path, URL, or "inline")
        """
        try:
            self.config_bridge.set_pac_content(content, source)
            self.logger.info(f"PAC content updated from {source}")
        except Exception as e:
            error_msg = f"Failed to set PAC content: {str(e)}"
            self.logger.error(error_msg)
            self._notify_error("PAC Error", error_msg)
    
    def get_pac_content(self) -> Optional[str]:
        """Get current PAC content."""
        return self.config_bridge.get_pac_content()
    
    def get_pac_source(self) -> Optional[str]:
        """Get current PAC source."""
        return self.config_bridge.get_pac_source()
    
    def set_no_proxy_configuration(self, config: NoProxyConfiguration):
        """
        Set no proxy configuration.
        
        Args:
            config: No proxy configuration
        """
        try:
            self.config_bridge.set_no_proxy_configuration(config)
            self.logger.info(f"No proxy configuration updated: {config.get_summary()}")
        except Exception as e:
            error_msg = f"Failed to set no proxy configuration: {str(e)}"
            self.logger.error(error_msg)
            self._notify_error("No Proxy Error", error_msg)
    
    def get_no_proxy_configuration(self) -> NoProxyConfiguration:
        """Get current no proxy configuration."""
        return self.config_bridge.get_no_proxy_configuration()
    
    def get_monitoring_stats(self) -> Dict[str, Any]:
        """
        Get monitoring statistics.
        
        Returns:
            Dictionary with monitoring statistics
        """
        return self.config_bridge.get_monitoring_stats()
    
    def shutdown(self):
        """
        Shutdown the proxy controller and cleanup resources.
        """
        try:
            self.logger.info("Shutting down proxy controller...")
            
            # Stop proxy if running
            if self.is_proxy_running():
                self.stop_proxy()
            
            # Stop event system
            if self.event_system.is_running():
                self.event_system.stop()
            
            # Remove status callback
            self.config_bridge.remove_status_callback(self._on_status_change)
            
            self.logger.info("Proxy controller shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during proxy controller shutdown: {e}")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        Get default proxy configuration.
        
        Returns:
            Default configuration dictionary
        """
        return {
            'listen_address': '127.0.0.1',
            'port': 3128,
            'mode': 'manual'
        }
    
    def _on_status_change(self, status: ProxyStatus):
        """
        Handle proxy status changes.
        
        Args:
            status: New proxy status
        """
        self.logger.debug(f"Proxy status changed: {status.get_status_text()}")
        
        if self._status_update_callback:
            try:
                self._status_update_callback(status)
            except Exception as e:
                self.logger.error(f"Error in status update callback: {e}")
    
    def _notify_error(self, title: str, message: str):
        """
        Notify UI of an error.
        
        Args:
            title: Error title
            message: Error message
        """
        if self._error_callback:
            try:
                self._error_callback(title, message)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")