"""
Specific recovery strategies for different types of errors.

This module provides concrete recovery strategies for PAC validation,
network errors, proxy failures, and configuration issues.
"""

import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from .error_manager import ErrorHandler, ErrorInfo, ErrorCategory, ErrorSeverity
from .retry_manager import RetryManager, RetryPolicy, ExponentialBackoff
from .fallback_manager import FallbackManager


class PACRecoveryStrategy(ErrorHandler):
    """Recovery strategy for PAC-related errors."""
    
    def __init__(self):
        """Initialize PAC recovery strategy."""
        self.logger = logging.getLogger(__name__)
        self.retry_manager = RetryManager()
        self.fallback_manager = FallbackManager()
        self._cached_pac_content: Optional[str] = None
        self._last_working_pac_source: Optional[str] = None
        self._lock = threading.RLock()
    
    def can_handle(self, error: ErrorInfo) -> bool:
        """Check if this handler can handle PAC-related errors."""
        return error.category in [ErrorCategory.PAC_VALIDATION, ErrorCategory.PAC_LOADING]
    
    def handle(self, error: ErrorInfo) -> bool:
        """Handle PAC-related errors with recovery strategies."""
        try:
            self.logger.info(f"Attempting PAC recovery for error: {error.message}")
            
            if error.category == ErrorCategory.PAC_LOADING:
                return self._handle_pac_loading_error(error)
            elif error.category == ErrorCategory.PAC_VALIDATION:
                return self._handle_pac_validation_error(error)
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error in PAC recovery strategy: {e}")
            return False
    
    def _handle_pac_loading_error(self, error: ErrorInfo) -> bool:
        """Handle PAC loading errors."""
        pac_source = error.context.get('pac_source', '')
        
        # Strategy 1: Retry loading with exponential backoff
        if pac_source.startswith(('http://', 'https://')):
            try:
                self.logger.info(f"Retrying PAC download from {pac_source}")
                pac_content = self._retry_pac_download(pac_source)
                if pac_content:
                    self._cache_working_pac(pac_content, pac_source)
                    return True
            except Exception as e:
                self.logger.warning(f"PAC download retry failed: {e}")
        
        # Strategy 2: Use cached PAC content if available
        if self._cached_pac_content:
            self.logger.info("Using cached PAC content as fallback")
            return True
        
        # Strategy 3: Use last working PAC source
        if self._last_working_pac_source and self._last_working_pac_source != pac_source:
            try:
                self.logger.info(f"Trying last working PAC source: {self._last_working_pac_source}")
                pac_content = self._retry_pac_download(self._last_working_pac_source)
                if pac_content:
                    return True
            except Exception as e:
                self.logger.warning(f"Last working PAC source failed: {e}")
        
        # Strategy 4: Fallback to default PAC
        try:
            fallback_result = self.fallback_manager.execute_fallback({
                'operation_type': 'pac_loading',
                'original_source': pac_source
            })
            self.logger.info("Using default PAC fallback")
            return True
        except Exception as e:
            self.logger.error(f"PAC fallback failed: {e}")
        
        return False
    
    def _handle_pac_validation_error(self, error: ErrorInfo) -> bool:
        """Handle PAC validation errors."""
        pac_content = error.context.get('pac_content', '')
        
        # Strategy 1: Try to fix common PAC syntax errors
        try:
            fixed_pac = self._attempt_pac_fix(pac_content)
            if fixed_pac and fixed_pac != pac_content:
                self.logger.info("Attempted to fix PAC syntax errors")
                # Validate the fixed PAC
                if self._validate_pac_content(fixed_pac):
                    return True
        except Exception as e:
            self.logger.warning(f"PAC fix attempt failed: {e}")
        
        # Strategy 2: Use cached working PAC
        if self._cached_pac_content:
            self.logger.info("Using cached working PAC due to validation error")
            return True
        
        # Strategy 3: Fallback to minimal working PAC
        try:
            fallback_result = self.fallback_manager.execute_fallback({
                'operation_type': 'pac_loading',
                'validation_error': error.message
            })
            self.logger.info("Using minimal PAC fallback due to validation error")
            return True
        except Exception as e:
            self.logger.error(f"PAC validation fallback failed: {e}")
        
        return False
    
    def _retry_pac_download(self, url: str) -> Optional[str]:
        """Retry PAC download with exponential backoff."""
        def download_pac():
            request = Request(url, headers={'User-Agent': 'px-ui-client/1.0'})
            with urlopen(request, timeout=10) as response:
                content = response.read()
                if isinstance(content, bytes):
                    # Try to decode with common encodings
                    for encoding in ['utf-8', 'latin-1', 'cp1252']:
                        try:
                            return content.decode(encoding)
                        except UnicodeDecodeError:
                            continue
                    # If all encodings fail, use utf-8 with error handling
                    return content.decode('utf-8', errors='replace')
                return content
        
        policy = RetryPolicy(
            max_attempts=3,
            base_delay=1.0,
            backoff_strategy=ExponentialBackoff(multiplier=2.0, max_delay=10.0),
            retry_on_exceptions=[URLError, HTTPError, TimeoutError]
        )
        
        try:
            return self.retry_manager.retry(download_pac, policy, "pac_download")
        except Exception:
            return None
    
    def _attempt_pac_fix(self, pac_content: str) -> Optional[str]:
        """Attempt to fix common PAC syntax errors."""
        if not pac_content:
            return None
        
        fixed_content = pac_content
        
        # Fix common issues
        fixes = [
            # Fix missing semicolons
            (r'return\s+"([^"]+)"\s*\n', r'return "\1";\n'),
            # Fix missing function declaration
            (r'^(?!.*function\s+FindProxyForURL)', 'function FindProxyForURL(url, host) {\n'),
            # Ensure function ends properly
            (r'(?<!})\s*$', '\n}'),
            # Fix common variable name issues
            (r'\bURL\b', 'url'),
            (r'\bHOST\b', 'host'),
        ]
        
        import re
        for pattern, replacement in fixes:
            try:
                fixed_content = re.sub(pattern, replacement, fixed_content, flags=re.MULTILINE)
            except Exception as e:
                self.logger.debug(f"PAC fix pattern failed: {e}")
        
        return fixed_content if fixed_content != pac_content else None
    
    def _validate_pac_content(self, pac_content: str) -> bool:
        """Basic validation of PAC content."""
        if not pac_content or not pac_content.strip():
            return False
        
        # Check for required function
        if 'FindProxyForURL' not in pac_content:
            return False
        
        # Basic syntax checks
        if pac_content.count('(') != pac_content.count(')'):
            return False
        
        if pac_content.count('{') != pac_content.count('}'):
            return False
        
        return True
    
    def _cache_working_pac(self, pac_content: str, pac_source: str):
        """Cache working PAC content and source."""
        with self._lock:
            self._cached_pac_content = pac_content
            self._last_working_pac_source = pac_source
            self.logger.debug(f"Cached working PAC from {pac_source}")


class NetworkRecoveryStrategy(ErrorHandler):
    """Recovery strategy for network-related errors."""
    
    def __init__(self):
        """Initialize network recovery strategy."""
        self.logger = logging.getLogger(__name__)
        self.retry_manager = RetryManager()
        self.fallback_manager = FallbackManager()
        self._connection_failures: Dict[str, int] = {}
        self._lock = threading.RLock()
    
    def can_handle(self, error: ErrorInfo) -> bool:
        """Check if this handler can handle network-related errors."""
        return error.category == ErrorCategory.NETWORK
    
    def handle(self, error: ErrorInfo) -> bool:
        """Handle network-related errors with recovery strategies."""
        try:
            self.logger.info(f"Attempting network recovery for error: {error.message}")
            
            url = error.context.get('url', '')
            host = error.context.get('host', '')
            
            # Track connection failures
            self._track_connection_failure(host or url)
            
            # Strategy 1: Retry with exponential backoff
            if self._should_retry_connection(host or url):
                self.logger.info(f"Retrying network connection to {host or url}")
                # The actual retry would be handled by the calling code
                # Here we just indicate that retry is recommended
                return True
            
            # Strategy 2: Fallback to direct connection
            try:
                fallback_result = self.fallback_manager.execute_fallback({
                    'operation_type': 'network_request',
                    'url': url,
                    'host': host,
                    'error_type': 'network'
                })
                self.logger.info(f"Network fallback successful for {host or url}")
                return True
            except Exception as e:
                self.logger.warning(f"Network fallback failed: {e}")
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error in network recovery strategy: {e}")
            return False
    
    def _track_connection_failure(self, target: str):
        """Track connection failures for a target."""
        if not target:
            return
        
        with self._lock:
            self._connection_failures[target] = self._connection_failures.get(target, 0) + 1
    
    def _should_retry_connection(self, target: str) -> bool:
        """Check if we should retry connection to target."""
        if not target:
            return False
        
        with self._lock:
            failure_count = self._connection_failures.get(target, 0)
            return failure_count < 3  # Retry up to 3 times


class ProxyRecoveryStrategy(ErrorHandler):
    """Recovery strategy for proxy-related errors."""
    
    def __init__(self):
        """Initialize proxy recovery strategy."""
        self.logger = logging.getLogger(__name__)
        self.retry_manager = RetryManager()
        self.fallback_manager = FallbackManager()
        self._proxy_failures: Dict[str, int] = {}
        self._lock = threading.RLock()
    
    def can_handle(self, error: ErrorInfo) -> bool:
        """Check if this handler can handle proxy-related errors."""
        return error.category == ErrorCategory.PROXY
    
    def handle(self, error: ErrorInfo) -> bool:
        """Handle proxy-related errors with recovery strategies."""
        try:
            self.logger.info(f"Attempting proxy recovery for error: {error.message}")
            
            proxy_host = error.context.get('proxy_host', '')
            proxy_port = error.context.get('proxy_port', '')
            
            # Track proxy failures
            proxy_key = f"{proxy_host}:{proxy_port}" if proxy_host and proxy_port else "unknown"
            self._track_proxy_failure(proxy_key)
            
            # Strategy 1: Retry proxy connection
            if self._should_retry_proxy(proxy_key):
                self.logger.info(f"Retrying proxy connection to {proxy_key}")
                return True
            
            # Strategy 2: Fallback to direct connection
            try:
                fallback_result = self.fallback_manager.execute_fallback({
                    'operation_type': 'proxy_connection',
                    'proxy_host': proxy_host,
                    'proxy_port': proxy_port,
                    'error_type': 'proxy'
                })
                self.logger.info(f"Proxy fallback successful, using direct connection")
                return True
            except Exception as e:
                self.logger.warning(f"Proxy fallback failed: {e}")
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error in proxy recovery strategy: {e}")
            return False
    
    def _track_proxy_failure(self, proxy_key: str):
        """Track proxy failures."""
        with self._lock:
            self._proxy_failures[proxy_key] = self._proxy_failures.get(proxy_key, 0) + 1
    
    def _should_retry_proxy(self, proxy_key: str) -> bool:
        """Check if we should retry proxy connection."""
        with self._lock:
            failure_count = self._proxy_failures.get(proxy_key, 0)
            return failure_count < 2  # Retry up to 2 times for proxy


class ConfigurationRecoveryStrategy(ErrorHandler):
    """Recovery strategy for configuration-related errors."""
    
    def __init__(self):
        """Initialize configuration recovery strategy."""
        self.logger = logging.getLogger(__name__)
        self.fallback_manager = FallbackManager()
        self._backup_configs: Dict[str, Any] = {}
        self._lock = threading.RLock()
    
    def can_handle(self, error: ErrorInfo) -> bool:
        """Check if this handler can handle configuration-related errors."""
        return error.category == ErrorCategory.CONFIGURATION
    
    def handle(self, error: ErrorInfo) -> bool:
        """Handle configuration-related errors with recovery strategies."""
        try:
            self.logger.info(f"Attempting configuration recovery for error: {error.message}")
            
            config_type = error.context.get('config_type', 'unknown')
            
            # Strategy 1: Use backup configuration
            if self._has_backup_config(config_type):
                backup_config = self._get_backup_config(config_type)
                self.logger.info(f"Using backup configuration for {config_type}")
                return True
            
            # Strategy 2: Use cached configuration fallback
            try:
                fallback_result = self.fallback_manager.execute_fallback({
                    'operation_type': 'configuration',
                    'config_type': config_type,
                    'error_type': 'configuration'
                })
                self.logger.info(f"Configuration fallback successful for {config_type}")
                return True
            except Exception as e:
                self.logger.warning(f"Configuration fallback failed: {e}")
            
            # Strategy 3: Reset to default configuration
            try:
                default_config = self._get_default_config(config_type)
                if default_config:
                    self.logger.info(f"Using default configuration for {config_type}")
                    return True
            except Exception as e:
                self.logger.warning(f"Default configuration failed: {e}")
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error in configuration recovery strategy: {e}")
            return False
    
    def backup_configuration(self, config_type: str, configuration: Any):
        """Backup a working configuration."""
        with self._lock:
            self._backup_configs[config_type] = configuration
            self.logger.debug(f"Backed up configuration for {config_type}")
    
    def _has_backup_config(self, config_type: str) -> bool:
        """Check if we have a backup configuration."""
        with self._lock:
            return config_type in self._backup_configs
    
    def _get_backup_config(self, config_type: str) -> Optional[Any]:
        """Get backup configuration."""
        with self._lock:
            return self._backup_configs.get(config_type)
    
    def _get_default_config(self, config_type: str) -> Optional[Dict[str, Any]]:
        """Get default configuration for the given type."""
        defaults = {
            'proxy': {
                'listen_address': '127.0.0.1',
                'port': 3128,
                'mode': 'manual'
            },
            'pac': {
                'content': 'function FindProxyForURL(url, host) { return "DIRECT"; }',
                'source': 'default'
            },
            'no_proxy': {
                'hosts': ['localhost', '127.0.0.1'],
                'enabled': True
            }
        }
        
        return defaults.get(config_type)