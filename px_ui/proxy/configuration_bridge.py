"""
Configuration bridge for integrating enhanced handler with px engine.

This module provides utilities to configure px to use the enhanced handler
with monitoring capabilities and control proxy lifecycle.
"""

import sys
import threading
import time
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from pathlib import Path

# Import px components
import px.config
import px.main
import px.handler

from .enhanced_handler import EnhancedPxHandler, create_enhanced_handler_class
from ..communication.event_system import EventSystem
from ..models.proxy_status import ProxyStatus
from ..models.no_proxy_configuration import NoProxyConfiguration
from ..error_handling import (
    ErrorManager, ErrorCategory, ErrorSeverity, get_error_manager,
    RetryManager, FallbackManager, 
    PACRecoveryStrategy, NetworkRecoveryStrategy, ProxyRecoveryStrategy, ConfigurationRecoveryStrategy
)


class PxConfigurationBridge:
    """
    Bridge class for configuring px with enhanced monitoring and proxy control.
    
    This class handles the integration between the px proxy engine
    and our enhanced handler with monitoring capabilities, as well as
    proxy lifecycle management.
    """
    
    def __init__(self, event_system: EventSystem):
        """
        Initialize the configuration bridge.
        
        Args:
            event_system: Event system for monitoring events
        """
        self.logger = logging.getLogger(__name__)
        self.event_system = event_system
        self.enhanced_handler_class = None
        self._original_handler_class = None
        
        # Error handling and recovery
        self.error_manager = get_error_manager()
        self.retry_manager = RetryManager()
        self.fallback_manager = FallbackManager()
        
        # Register recovery strategies
        self._setup_recovery_strategies()
        
        # Proxy control state
        self._proxy_thread: Optional[threading.Thread] = None
        self._proxy_status = ProxyStatus(
            is_running=False,
            listen_address="127.0.0.1",
            port=3128,
            mode="manual"
        )
        self._shutdown_event = threading.Event()
        self._status_callbacks: list[Callable[[ProxyStatus], None]] = []
        
        # Configuration state
        self._current_config: Dict[str, Any] = {}
        self._pac_content: Optional[str] = None
        self._pac_source: Optional[str] = None
        self._no_proxy_config: NoProxyConfiguration = NoProxyConfiguration()
    
    def configure_px_monitoring(self):
        """
        Configure px to use enhanced handler with monitoring.
        
        This method modifies px configuration to use our enhanced
        handler class instead of the default one.
        """
        # Create enhanced handler class
        self.enhanced_handler_class = create_enhanced_handler_class(self.event_system)
        
        # Store original handler class for restoration
        self._original_handler_class = px.handler.PxHandler
        
        # Replace px handler with our enhanced version
        px.handler.PxHandler = self.enhanced_handler_class
        
        # Also update any other references that might exist
        if hasattr(px.main, 'handler'):
            px.main.handler.PxHandler = self.enhanced_handler_class
    
    def restore_original_handler(self):
        """
        Restore the original px handler.
        
        This method restores the original px handler class,
        effectively disabling monitoring.
        """
        if self._original_handler_class:
            px.handler.PxHandler = self._original_handler_class
            if hasattr(px.main, 'handler'):
                px.main.handler.PxHandler = self._original_handler_class
    
    def is_monitoring_enabled(self) -> bool:
        """
        Check if monitoring is currently enabled.
        
        Returns:
            True if enhanced handler is active
        """
        current_handler = px.handler.PxHandler
        return (current_handler is not None and 
                issubclass(current_handler, EnhancedPxHandler))
    
    def get_monitoring_stats(self) -> dict:
        """
        Get monitoring statistics.
        
        Returns:
            Dictionary with monitoring statistics
        """
        stats = {
            'monitoring_enabled': self.is_monitoring_enabled(),
            'event_system_running': self.event_system.is_running(),
            'event_system_stats': self.event_system.get_stats()
        }
        
        return stats
    
    def start_proxy(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Start the proxy service with optional configuration.
        
        Args:
            config: Optional configuration dictionary
            
        Returns:
            True if proxy started successfully, False otherwise
        """
        if self._proxy_status.is_running:
            self.logger.warning("Proxy is already running")
            return False
        
        try:
            # Validate configuration before starting
            if config:
                validation_result = self.validate_configuration(config)
                if not validation_result['is_valid']:
                    error_msg = f"Configuration validation failed: {validation_result['errors']}"
                    self.logger.error(error_msg)
                    self.error_manager.handle_configuration_error(
                        message=error_msg,
                        details=str(validation_result['errors'])
                    )
                    return False
                self._current_config = config.copy()
                
                # Extract PAC content from configuration
                if 'pac_config' in config and config['pac_config']:
                    pac_config = config['pac_config']
                    if hasattr(pac_config, 'content') and pac_config.content:
                        self.set_pac_content(pac_config.content, pac_config.get_source_display_name())
                        self.logger.info(f"PAC content extracted from config: {len(pac_config.content)} characters")
                    else:
                        self.logger.warning("PAC config present but no content available")
                        self._pac_content = None
                else:
                    self.logger.info("No PAC configuration in config")
                    self._pac_content = None
                
                self.logger.info(f"Configuration received: {config}")
                self.logger.info(f"NTLM enabled: {config.get('enable_ntlm', False)}")
                self.logger.info(f"Upstream proxy: {config.get('upstream_proxy', 'None')}")
                self.logger.info(f"Mode: {config.get('mode', 'manual')}")
                self.logger.info(f"PAC content available: {bool(self._pac_content)}")
            
            # Configure monitoring
            self.configure_px_monitoring()
            
            # Start event system if not running
            if not self.event_system.is_running():
                self.event_system.start()
            
            # Reset shutdown event
            self._shutdown_event.clear()
            
            # Start proxy with retry mechanism
            def start_proxy_with_retry():
                self._proxy_thread = threading.Thread(
                    target=self._run_proxy_thread,
                    daemon=True,
                    name="px-proxy-thread"
                )
                self._proxy_thread.start()
                
                # Wait a moment for proxy to start
                time.sleep(0.5)
                
                # Check if proxy actually started
                if not self._proxy_thread.is_alive():
                    raise RuntimeError("Proxy thread failed to start")
                
                return True
            
            # Use retry manager for proxy startup
            from ..error_handling.retry_manager import RetryPolicy, ExponentialBackoff
            retry_policy = RetryPolicy(
                max_attempts=3,
                base_delay=1.0,
                backoff_strategy=ExponentialBackoff(multiplier=1.5, max_delay=5.0),
                retry_on_exceptions=[RuntimeError, OSError]
            )
            
            success = self.retry_manager.retry(
                start_proxy_with_retry,
                policy=retry_policy,
                operation_name="proxy_startup"
            )
            
            if success:
                # Update status
                self._proxy_status.is_running = True
                self._notify_status_change()
                self.logger.info(f"Proxy started on {self._proxy_status.get_listen_url()}")
                return True
            else:
                return False
            
        except Exception as e:
            self.logger.error(f"Failed to start proxy: {e}")
            self.error_manager.handle_proxy_error(
                message=f"Failed to start proxy: {str(e)}",
                details=f"Port: {self._proxy_status.port}, Address: {self._proxy_status.listen_address}",
                exception=e
            )
            self._proxy_status.is_running = False
            self._notify_status_change()
            
            # Try fallback strategies
            try:
                fallback_result = self.fallback_manager.try_fallback({
                    'operation_type': 'proxy_connection',
                    'error_type': 'startup_failure',
                    'config': config
                })
                if fallback_result:
                    self.logger.info("Proxy startup fallback successful")
                    return True
            except Exception as fallback_error:
                self.logger.error(f"Proxy startup fallback failed: {fallback_error}")
            
            return False
    
    def stop_proxy(self) -> bool:
        """
        Stop the proxy service.
        
        Returns:
            True if proxy stopped successfully, False otherwise
        """
        if not self._proxy_status.is_running:
            self.logger.warning("Proxy is not running")
            return False
        
        try:
            self.logger.info("Stopping proxy service...")
            
            # Signal shutdown
            self._shutdown_event.set()
            
            # Wait for proxy thread to finish (with timeout)
            if self._proxy_thread and self._proxy_thread.is_alive():
                self._proxy_thread.join(timeout=5.0)
                
                if self._proxy_thread.is_alive():
                    self.logger.warning("Proxy thread did not stop gracefully")
            
            # Update status
            self._proxy_status.is_running = False
            self._proxy_status.active_connections = 0
            self._notify_status_change()
            
            # Restore original handler
            self.restore_original_handler()
            
            self.logger.info("Proxy stopped successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to stop proxy: {e}")
            return False
    
    def _run_proxy_thread(self):
        """Run the px proxy in a background thread with full NTLM support."""
        try:
            self.logger.info("Starting px proxy with NTLM authentication support...")
            
            # Configure px state for NTLM authentication
            self._configure_px_state()
            
            # Use real px library functionality instead of simple proxy
            self._run_px_proxy_server()
            
        except Exception as e:
            self.logger.error(f"Proxy thread error: {e}")
        finally:
            self.logger.info("Proxy thread finished")
            self._proxy_status.is_running = False
            self._notify_status_change()
    
    def _configure_px_state(self):
        """Configure px library state for NTLM authentication."""
        try:
            from px.config import STATE
            import px.config
            import configparser
            import tempfile
            import os
            
            # Initialize px configuration if not already done
            if STATE.config is None:
                self.logger.info("Initializing px configuration...")
                
                # Create a temporary config file for px
                config = configparser.ConfigParser()
                
                # Basic proxy settings
                config.add_section('proxy')
                config.set('proxy', 'listen', self._current_config.get('listen_address', '127.0.0.1'))
                config.set('proxy', 'port', str(self._current_config.get('port', 3128)))
                config.set('proxy', 'auth', self._current_config.get('auth_method', 'ANY'))
                config.set('proxy', 'pac_encoding', 'utf-8')  # Add missing pac_encoding option
                
                # Settings section
                config.add_section('settings')
                config.set('settings', 'workers', str(self._current_config.get('threads', 5)))
                
                # Save to temporary file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
                    config.write(f)
                    temp_config_file = f.name
                
                # Initialize px state with config
                STATE.ini = temp_config_file
                STATE.config = config
                
                # Initialize px curl multi-handle (if available)
                try:
                    import mcurl
                    if STATE.mcurl is None:
                        STATE.mcurl = mcurl.MCurl()
                        self.logger.info("px mcurl initialized successfully")
                except ImportError:
                    # px.mcurl module doesn't exist, this is normal for some px versions
                    self.logger.debug("px.mcurl module not available, using default initialization")
                except Exception as mcurl_error:
                    self.logger.warning(f"Failed to initialize px mcurl: {mcurl_error}")
                
                self.logger.info(f"px configuration initialized with temp file: {temp_config_file}")
            
            # Configure px state for NTLM
            listen_address = self._current_config.get('listen_address', '127.0.0.1')
            if isinstance(listen_address, str):
                STATE.listen = [listen_address]  # px expects a list
            else:
                STATE.listen = listen_address
            
            # Set port in config
            port = self._current_config.get('port', 3128)
            STATE.config.set('proxy', 'port', str(port))
            
            # Ensure pac_encoding is set (required by px)
            if not STATE.config.has_option('proxy', 'pac_encoding'):
                STATE.config.set('proxy', 'pac_encoding', 'utf-8')
            
            # NTLM authentication configuration
            auth_method = self._current_config.get('auth_method', 'ANY')
            upstream_proxy = self._current_config.get('upstream_proxy', '')
            mode = self._current_config.get('mode', 'manual')
            
            # Always clear proxy.server to ensure PAC file controls proxy decisions
            STATE.config.set('proxy', 'server', '')
            
            # Configure authentication based on mode and NTLM settings
            if mode == 'pac' and self._pac_content:
                # PAC mode: authentication is enabled but proxy selection is controlled by PAC
                if self._current_config.get('enable_ntlm', False) and upstream_proxy:
                    STATE.auth = auth_method  # Enable NTLM authentication
                    STATE.config.set('proxy', 'auth', auth_method)
                    
                    # Store NTLM proxy info for authentication reference only
                    STATE.ntlm_proxy = upstream_proxy
                    
                    self.logger.info(f"PAC mode with NTLM authentication enabled (auth={auth_method})")
                    self.logger.info(f"NTLM proxy for authentication: {upstream_proxy}")
                    self.logger.info("Proxy selection controlled by PAC file")
                else:
                    # PAC mode without NTLM authentication
                    STATE.auth = "NONE"
                    STATE.config.set('proxy', 'auth', 'NONE')
                    if hasattr(STATE, 'ntlm_proxy'):
                        delattr(STATE, 'ntlm_proxy')
                    
                    self.logger.info("PAC mode without authentication")
                    self.logger.info("Proxy selection controlled by PAC file")
            else:
                # Manual mode: use NTLM settings if available
                if self._current_config.get('enable_ntlm', False) and upstream_proxy:
                    STATE.auth = auth_method
                    STATE.config.set('proxy', 'auth', auth_method)
                    STATE.config.set('proxy', 'server', upstream_proxy)  # Use NTLM proxy for all connections
                    
                    self.logger.info(f"Manual mode with NTLM authentication (auth={auth_method})")
                    self.logger.info(f"All connections via NTLM proxy: {upstream_proxy}")
                else:
                    # Manual mode without NTLM
                    STATE.auth = "NONE"
                    STATE.config.set('proxy', 'auth', 'NONE')
                    if hasattr(STATE, 'ntlm_proxy'):
                        delattr(STATE, 'ntlm_proxy')
                    
                    self.logger.info("Manual mode without authentication - direct connections")
            
            # Username configuration (for NTLM)
            username = self._current_config.get('username', '')
            if username:
                STATE.username = username
                self.logger.info(f"Username configured: {username}")
            
            # PAC configuration
            if self._pac_content:
                pac_file = self._save_pac_to_temp_file()
                STATE.set_pac(pac_file)  # Use the proper setter method
                self.logger.info(f"PAC file configured: {pac_file}")
            else:
                STATE.pac = ""
            
            # Client authentication (usually NONE for UI clients)
            client_auth = self._current_config.get('client_auth', ['NONE'])
            STATE.client_auth = client_auth
            
            # Ensure no client authentication is required
            if 'NONE' in client_auth:
                # Disable all client authentication mechanisms
                STATE.client_auth = []
                self.logger.info("Client authentication disabled - no authentication required from clients")
            
            # No proxy configuration
            if hasattr(self, '_no_proxy_config') and self._no_proxy_config:
                noproxy_str = self._no_proxy_config.to_px_format()
                if noproxy_str:
                    STATE.set_noproxy(noproxy_str)
                    self.logger.info(f"No-proxy configuration: {noproxy_str}")
            
            self.logger.info("px state configured successfully for NTLM support")
            
        except Exception as e:
            self.logger.error(f"Failed to configure px state: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise
    
    def _run_px_proxy_server(self):
        """Run the real px proxy server with NTLM support and monitoring."""
        try:
            import px.handler
            from px.config import STATE
            import socketserver
            import concurrent.futures
            import socket
            
            # Configure enhanced handler for monitoring
            self.configure_px_monitoring()
            
            # Get configuration
            listen_address = self._current_config.get('listen_address', '127.0.0.1')
            port = self._current_config.get('port', 3128)
            
            self.logger.info(f"Starting px proxy server on {listen_address}:{port} with NTLM support")
            
            # Create custom ThreadedTCPServer class with pool support
            class PxThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
                daemon_threads = True
                allow_reuse_address = True
                
                def __init__(self, server_address, RequestHandlerClass, max_workers=5):
                    super().__init__(server_address, RequestHandlerClass)
                    self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
                    
                def process_request(self, request, client_address):
                    """Process request using thread pool."""
                    self.pool.submit(self.process_request_thread, request, client_address)
                
                def server_close(self):
                    """Close server and shutdown thread pool."""
                    super().server_close()
                    if hasattr(self, 'pool'):
                        self.pool.shutdown(wait=True)
            
            # Create proxy server
            max_workers = self._current_config.get('threads', 5)
            
            # Choose handler based on configuration
            if self._current_config.get('enable_ntlm', False) and self._current_config.get('upstream_proxy'):
                # Use px handler for NTLM authentication
                from .enhanced_handler import EnhancedPxHandler
                handler_class = EnhancedPxHandler
                self.logger.info("Using px handler with NTLM authentication")
            else:
                # Use simple handler for direct connections
                from .simple_proxy_handler import SimpleProxyHandler
                handler_class = SimpleProxyHandler
                self.logger.info("Using simple handler for direct connections")
            
            httpd = PxThreadedTCPServer((listen_address, port), handler_class, max_workers)
            
            # Set server timeout for graceful shutdown
            httpd.timeout = 1.0
            
            # Attach PAC content and event system to server for handler access
            httpd.pac_content = self._pac_content
            httpd.event_system = self.event_system
            
            self.logger.info(f"px proxy server started successfully on {listen_address}:{port}")
            self.logger.info(f"NTLM authentication: {STATE.auth}")
            self.logger.info(f"PAC configuration: {STATE.pac}")
            
            # Serve requests until shutdown
            while not self._shutdown_event.is_set():
                try:
                    httpd.handle_request()
                except socket.timeout:
                    # Timeout is expected for graceful shutdown
                    continue
                except Exception as e:
                    if not self._shutdown_event.is_set():
                        self.logger.error(f"Error handling request: {e}")
                        # Continue serving unless shutdown requested
            
            self.logger.info("px proxy server shutting down...")
            httpd.server_close()
            
        except Exception as e:
            self.logger.error(f"Failed to start px proxy server: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            raise
    
    def _save_pac_to_temp_file(self) -> str:
        """Save PAC content to a temporary file and return the file path."""
        import tempfile
        import os
        
        try:
            # Create temporary file with .pac extension
            with tempfile.NamedTemporaryFile(mode='w', suffix='.pac', delete=False, encoding='utf-8') as f:
                f.write(self._pac_content)
                temp_pac_file = f.name
            
            self.logger.info(f"PAC content saved to temporary file: {temp_pac_file}")
            return temp_pac_file
            
        except Exception as e:
            self.logger.error(f"Failed to save PAC to temporary file: {e}")
            raise
    
    def _run_simple_proxy_server(self):
        """Run a simple proxy server that can work in a background thread."""
        import socket
        import threading
        import time
        import uuid
        from http.server import HTTPServer, BaseHTTPRequestHandler
        from urllib.parse import urlparse
        import urllib.request
        import urllib.parse
        
        # Import event classes
        from ..communication.events import RequestEvent, ResponseEvent, ErrorEvent, EventType
        
        class SimpleProxyHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                self._handle_request()
            
            def do_POST(self):
                self._handle_request()
            
            def do_CONNECT(self):
                self._handle_connect()
            
            def _handle_request(self):
                request_id = str(uuid.uuid4())
                start_time = time.time()
                
                try:
                    # Simple proxy implementation
                    url = self.path
                    if not url.startswith('http'):
                        url = f"http://{self.headers.get('Host', 'localhost')}{url}"
                    
                    # Determine proxy decision (simplified PAC logic)
                    proxy_decision = self._get_proxy_decision(url)
                    
                    # Send request event (will be updated if fallback occurs)
                    try:
                        self.server.logger.debug(f"Creating request event for {url}")
                        request_event = RequestEvent(
                            event_type=EventType.REQUEST,
                            timestamp=datetime.now(),
                            event_id=request_id,
                            url=url,
                            method=self.command,
                            proxy_decision=proxy_decision,
                            request_id=request_id,
                            headers=dict(self.headers)
                        )
                        self.server.logger.debug(f"Sending request event to event system: {hasattr(self.server, 'event_system')}")
                        if hasattr(self.server, 'event_system') and self.server.event_system:
                            success = self.server.event_system.send_event(request_event)
                            self.server.logger.debug(f"Request event sent: {success}")
                        else:
                            self.server.logger.warning("Event system not available on server")
                    except Exception as event_error:
                        self.server.logger.error(f"Failed to send request event: {event_error}")
                        import traceback
                        self.server.logger.error(traceback.format_exc())
                    
                    # Create request
                    req = urllib.request.Request(url)
                    
                    # Copy headers
                    for header, value in self.headers.items():
                        if header.lower() not in ['host', 'connection']:
                            req.add_header(header, value)
                    
                    # Handle POST data
                    if self.command == 'POST':
                        content_length = int(self.headers.get('Content-Length', 0))
                        if content_length > 0:
                            post_data = self.rfile.read(content_length)
                            req.data = post_data
                    
                    # Handle request based on proxy decision
                    if proxy_decision == "DIRECT":
                        # Direct connection
                        self._make_direct_request(req, request_id, start_time)
                    elif proxy_decision.startswith("PROXY "):
                        # Proxy connection
                        proxy_info = proxy_decision.split(" ", 1)[1]  # Get "127.0.0.1:8080"
                        self._make_proxy_request(req, proxy_info, request_id, start_time)
                    else:
                        # Unknown proxy decision, fallback to direct
                        self.server.logger.warning(f"Unknown proxy decision: {proxy_decision}, using DIRECT")
                        self._make_direct_request(req, request_id, start_time)
                
                except Exception as e:
                    response_time = time.time() - start_time
                    
                    # Send error event
                    try:
                        error_event = ErrorEvent(
                            event_type=EventType.ERROR,
                            timestamp=datetime.now(),
                            event_id=str(uuid.uuid4()),
                            error_type="proxy",
                            error_message=str(e),
                            request_id=request_id,
                            url=url if 'url' in locals() else None
                        )
                        self.server.event_system.send_event(error_event)
                    except Exception as event_error:
                        self.server.logger.error(f"Failed to send error event: {event_error}")
                    
                    self.send_error(500, f"Proxy error: {str(e)}")
            
            def _get_proxy_decision(self, url):
                """Determine proxy decision based on URL using actual PAC logic."""
                try:
                    # Use the actual PAC configuration if available
                    if hasattr(self.server, 'pac_content') and self.server.pac_content:
                        decision = self._evaluate_pac_function(url, self.server.pac_content)
                        self.server.logger.debug(f"PAC decision for {url}: {decision}")
                        return decision
                    
                    # If no PAC content, return DIRECT (no hardcoded proxy decisions)
                    self.server.logger.warning(f"No PAC content available, using DIRECT for {url}")
                    return "DIRECT"
                    
                except Exception as e:
                    self.server.logger.error(f"Error in PAC decision for {url}: {e}")
                    return "DIRECT"
            
            def _evaluate_pac_function(self, url, pac_content):
                """Evaluate PAC function using JavaScript engine."""
                try:
                    import execjs
                    
                    # Parse URL to get host
                    parsed = urlparse(url)
                    host = parsed.netloc.split(':')[0]  # Remove port if present
                    
                    self.server.logger.info(f"Evaluating PAC for {url} -> {host}")
                    
                    # Create JavaScript context with PAC helper functions
                    pac_helpers = '''
                    function isPlainHostName(host) {
                        return host.indexOf('.') === -1;
                    }
                    
                    function dnsDomainIs(host, domain) {
                        return host.toLowerCase().endsWith(domain.toLowerCase());
                    }
                    
                    function localHostOrDomainIs(host, hostdom) {
                        return host === hostdom || host === hostdom.split('.')[0];
                    }
                    
                    function isResolvable(host) {
                        return true; // Simplified
                    }
                    
                    function isInNet(host, pattern, mask) {
                        // Simplified IP range check
                        if (host === '127.0.0.1' && pattern.startsWith('127.')) return true;
                        if (host.startsWith('192.168.') && pattern.startsWith('192.168.')) return true;
                        if (host.startsWith('10.') && pattern.startsWith('10.')) return true;
                        if (host.startsWith('172.16.') && pattern.startsWith('172.16.')) return true;
                        return false;
                    }
                    
                    function dnsResolve(host) {
                        return host; // Simplified
                    }
                    
                    function myIpAddress() {
                        return '127.0.0.1';
                    }
                    
                    function dnsDomainLevels(host) {
                        return host.split('.').length - 1;
                    }
                    
                    function shExpMatch(str, shexp) {
                        // Convert shell expression to regex
                        var regex = shexp.replace(/\\*/g, '.*').replace(/\\?/g, '.');
                        return new RegExp('^' + regex + '$').test(str);
                    }
                    '''
                    
                    # Combine PAC helpers with actual PAC content
                    full_pac_script = pac_helpers + '\n' + pac_content
                    
                    # Create JavaScript context and execute PAC script
                    ctx = execjs.compile(full_pac_script)
                    
                    # Call FindProxyForURL function
                    result = ctx.call('FindProxyForURL', url, host)
                    
                    decision = str(result).strip()
                    self.server.logger.info(f"PAC decision: {url} -> {decision}")
                    return decision
                    
                except ImportError as e:
                    self.server.logger.error(f"execjs not available: {e}")
                    return "DIRECT"
                except Exception as e:
                    self.server.logger.error(f"PAC evaluation error: {e}")
                    import traceback
                    self.server.logger.error(traceback.format_exc())
                    return "DIRECT"
            

            
            def _make_direct_request(self, req, request_id, start_time):
                """Make a direct request to the target server."""
                try:
                    with urllib.request.urlopen(req, timeout=30) as response:
                        self._send_successful_response(response, request_id, start_time)
                except Exception as e:
                    self._send_error_response(str(e), request_id, start_time)
            
            def _make_proxy_request(self, req, proxy_info, request_id, start_time):
                """Make a request through another proxy server."""
                try:
                    # Parse proxy info (e.g., "127.0.0.1:8080")
                    if ':' in proxy_info:
                        proxy_host, proxy_port = proxy_info.split(':', 1)
                        proxy_port = int(proxy_port)
                    else:
                        proxy_host = proxy_info
                        proxy_port = 3128  # Default proxy port
                    
                    # Create proxy handler
                    proxy_handler = urllib.request.ProxyHandler({
                        'http': f'http://{proxy_host}:{proxy_port}',
                        'https': f'http://{proxy_host}:{proxy_port}'
                    })
                    opener = urllib.request.build_opener(proxy_handler)
                    
                    # Make request through proxy
                    with opener.open(req, timeout=30) as response:
                        self._send_successful_response(response, request_id, start_time)
                        
                except Exception as e:
                    self.server.logger.error(f"Proxy request failed to {proxy_info}: {e}")
                    # If proxy fails, try direct connection as fallback
                    self.server.logger.info(f"Falling back to direct connection for {req.full_url}")
                    
                    # Send updated event showing fallback
                    try:
                        fallback_decision = f"PROXY {proxy_info} --fb--> DIRECT"
                        fallback_event = RequestEvent(
                            event_type=EventType.REQUEST,
                            timestamp=datetime.now(),
                            event_id=request_id,
                            url=req.full_url,
                            method="GET",
                            proxy_decision=fallback_decision,
                            request_id=request_id,
                            headers={}
                        )
                        if hasattr(self.server, 'event_system') and self.server.event_system:
                            self.server.event_system.send_event(fallback_event)
                    except Exception as event_error:
                        self.server.logger.error(f"Failed to send fallback event: {event_error}")
                    
                    try:
                        self._make_direct_request(req, request_id, start_time)
                    except Exception as direct_error:
                        self._send_error_response(f"Proxy failed: {e}, Direct failed: {direct_error}", request_id, start_time)
            
            def _send_successful_response(self, response, request_id, start_time):
                """Send a successful response to the client."""
                response_time = time.time() - start_time
                
                # Read response body for preview
                response_body = response.read()
                body_preview = response_body[:500].decode('utf-8', errors='ignore') if response_body else ""
                
                # Send response event
                try:
                    response_event = ResponseEvent(
                        event_type=EventType.RESPONSE,
                        timestamp=datetime.now(),
                        event_id=str(uuid.uuid4()),
                        request_id=request_id,
                        status_code=response.getcode(),
                        headers=dict(response.headers),
                        body_preview=body_preview,
                        content_length=len(response_body),
                        response_time=response_time
                    )
                    if hasattr(self.server, 'event_system') and self.server.event_system:
                        self.server.event_system.send_event(response_event)
                except Exception as event_error:
                    self.server.logger.error(f"Failed to send response event: {event_error}")
                
                # Send response to client
                self.send_response(response.getcode())
                
                # Copy response headers
                for header, value in response.headers.items():
                    if header.lower() not in ['connection', 'transfer-encoding']:
                        self.send_header(header, value)
                self.end_headers()
                
                # Send response body
                self.wfile.write(response_body)
            
            def _send_error_response(self, error_message, request_id, start_time):
                """Send an error response to the client."""
                response_time = time.time() - start_time
                
                # Clean error message to avoid encoding issues
                try:
                    clean_error_message = str(error_message).encode('ascii', errors='ignore').decode('ascii')
                except:
                    clean_error_message = "Proxy connection failed"
                
                # Send error event
                try:
                    error_event = ErrorEvent(
                        event_type=EventType.ERROR,
                        timestamp=datetime.now(),
                        event_id=str(uuid.uuid4()),
                        error_type="proxy",
                        error_message=clean_error_message,
                        request_id=request_id,
                        url=getattr(self, 'path', 'unknown')
                    )
                    if hasattr(self.server, 'event_system') and self.server.event_system:
                        self.server.event_system.send_event(error_event)
                except Exception as event_error:
                    self.server.logger.error(f"Failed to send error event: {event_error}")
                
                # Send HTTP error response with clean message
                try:
                    self.send_error(500, f"Proxy error: {clean_error_message}")
                except Exception as send_error:
                    # Fallback to basic error
                    try:
                        self.send_error(500, "Proxy connection failed")
                    except:
                        pass
            
            def _handle_connect(self):
                # Handle CONNECT method for HTTPS tunneling
                request_id = str(uuid.uuid4())
                start_time = time.time()
                
                try:
                    host, port = self.path.split(':')
                    port = int(port)
                    
                    # Construct HTTPS URL for monitoring
                    https_url = f"https://{host}:{port}"
                    
                    # Determine proxy decision
                    proxy_decision = self._get_proxy_decision(https_url)
                    
                    # Send CONNECT request event
                    try:
                        self.server.logger.debug(f"Creating CONNECT event for {https_url}")
                        connect_event = RequestEvent(
                            event_type=EventType.REQUEST,
                            timestamp=datetime.now(),
                            event_id=request_id,
                            url=https_url,
                            method="CONNECT",
                            proxy_decision=proxy_decision,
                            request_id=request_id,
                            headers=dict(self.headers)
                        )
                        if hasattr(self.server, 'event_system') and self.server.event_system:
                            success = self.server.event_system.send_event(connect_event)
                            self.server.logger.debug(f"CONNECT event sent: {success}")
                        else:
                            self.server.logger.warning("Event system not available for CONNECT")
                    except Exception as event_error:
                        self.server.logger.error(f"Failed to send CONNECT event: {event_error}")
                    
                    # Handle connection based on proxy decision
                    if proxy_decision == "DIRECT":
                        # Direct connection to target
                        target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        target_sock.connect((host, port))
                    elif proxy_decision.startswith("PROXY "):
                        # Connect through proxy server
                        proxy_info = proxy_decision.split(" ", 1)[1]  # Get "127.0.0.1:8081"
                        if ':' in proxy_info:
                            proxy_host, proxy_port = proxy_info.split(':', 1)
                            proxy_port = int(proxy_port)
                        else:
                            proxy_host = proxy_info
                            proxy_port = 3128
                        
                        try:
                            # Connect to proxy server
                            target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            target_sock.connect((proxy_host, proxy_port))
                            
                            # Send CONNECT request to proxy
                            connect_request = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n"
                            target_sock.send(connect_request.encode())
                            
                            # Read proxy response
                            response = target_sock.recv(4096).decode()
                            if "200" not in response:
                                raise Exception(f"Proxy CONNECT failed: {response}")
                                
                        except Exception as proxy_error:
                            self.server.logger.error(f"HTTPS proxy failed to {proxy_info}: {proxy_error}")
                            self.server.logger.info(f"Falling back to direct HTTPS connection for {host}:{port}")
                            
                            # Send updated event showing HTTPS fallback
                            try:
                                fallback_decision = f"PROXY {proxy_info} --fb--> DIRECT"
                                fallback_event = RequestEvent(
                                    event_type=EventType.REQUEST,
                                    timestamp=datetime.now(),
                                    event_id=request_id,
                                    url=https_url,
                                    method="CONNECT",
                                    proxy_decision=fallback_decision,
                                    request_id=request_id,
                                    headers=dict(self.headers)
                                )
                                if hasattr(self.server, 'event_system') and self.server.event_system:
                                    self.server.event_system.send_event(fallback_event)
                            except Exception as event_error:
                                self.server.logger.error(f"Failed to send HTTPS fallback event: {event_error}")
                            
                            # Fallback to direct connection
                            target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            target_sock.connect((host, port))
                    else:
                        # Unknown proxy decision, use direct
                        self.server.logger.warning(f"Unknown proxy decision for HTTPS: {proxy_decision}, using DIRECT")
                        target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        target_sock.connect((host, port))
                    
                    # Send 200 Connection established
                    self.send_response(200, 'Connection established')
                    self.end_headers()
                    
                    # Send successful CONNECT response event
                    try:
                        response_time = time.time() - start_time
                        connect_response_event = ResponseEvent(
                            event_type=EventType.RESPONSE,
                            timestamp=datetime.now(),
                            event_id=str(uuid.uuid4()),
                            request_id=request_id,
                            status_code=200,
                            headers={"Connection": "established"},
                            body_preview="[HTTPS Tunnel Established]",
                            content_length=0,
                            response_time=response_time
                        )
                        if hasattr(self.server, 'event_system') and self.server.event_system:
                            success = self.server.event_system.send_event(connect_response_event)
                            self.server.logger.debug(f"CONNECT response event sent: {success}")
                    except Exception as event_error:
                        self.server.logger.error(f"Failed to send CONNECT response event: {event_error}")
                    
                    # Start tunneling
                    client_sock = self.connection
                    
                    def tunnel(source, destination):
                        try:
                            while True:
                                data = source.recv(4096)
                                if not data:
                                    break
                                destination.send(data)
                        except:
                            pass
                        finally:
                            source.close()
                            destination.close()
                    
                    # Start tunneling in both directions
                    t1 = threading.Thread(target=tunnel, args=(client_sock, target_sock))
                    t2 = threading.Thread(target=tunnel, args=(target_sock, client_sock))
                    t1.daemon = True
                    t2.daemon = True
                    t1.start()
                    t2.start()
                    
                    # Wait for tunneling to complete
                    t1.join()
                    t2.join()
                    
                except Exception as e:
                    response_time = time.time() - start_time
                    
                    # Send error event for failed CONNECT
                    try:
                        error_event = ErrorEvent(
                            event_type=EventType.ERROR,
                            timestamp=datetime.now(),
                            event_id=str(uuid.uuid4()),
                            error_type="connect",
                            error_message=str(e),
                            request_id=request_id,
                            url=f"https://{self.path}" if ':' in self.path else None
                        )
                        if hasattr(self.server, 'event_system') and self.server.event_system:
                            self.server.event_system.send_event(error_event)
                    except Exception as event_error:
                        self.server.logger.error(f"Failed to send CONNECT error event: {event_error}")
                    
                    self.send_error(500, f"CONNECT error: {str(e)}")
            
            def log_message(self, format, *args):
                # Log through our logger instead of stderr
                message = format % args
                self.server.logger.info(f"Proxy request: {message}")
        
        # Create and start the proxy server
        server_address = (self._proxy_status.listen_address, self._proxy_status.port)
        httpd = HTTPServer(server_address, SimpleProxyHandler)
        httpd.logger = self.logger
        httpd.event_system = self.event_system  # Add event system reference
        httpd.pac_content = self._pac_content  # Add PAC content reference
        
        self.logger.info(f"Simple proxy server started on {server_address[0]}:{server_address[1]}")
        
        # Run server until shutdown event is set
        while not self._shutdown_event.is_set():
            httpd.timeout = 1.0  # Check shutdown event every second
            httpd.handle_request()
    
    def _apply_configuration(self):
        """Apply current configuration to px (legacy method, now handled by _configure_px_state)."""
        try:
            # Update proxy status with basic configuration
            if 'listen_address' in self._current_config:
                self._proxy_status.listen_address = self._current_config['listen_address']
            
            if 'port' in self._current_config:
                self._proxy_status.port = self._current_config['port']
            
            if 'mode' in self._current_config:
                self._proxy_status.mode = self._current_config['mode']
            
            # Note: NTLM and PAC configuration is now handled in _configure_px_state()
            # This method is kept for backward compatibility
            
            self.logger.info(f"Applied basic configuration: {self._current_config}")
            
        except Exception as e:
            self.logger.error(f"Failed to apply configuration: {e}")
            raise
    
    def _apply_pac_configuration(self):
        """Apply PAC configuration to px."""
        try:
            if not self._pac_content:
                self.logger.warning("No PAC content available")
                return
            
            # Write PAC content to temporary file for px to use
            pac_file = Path.cwd() / "temp_pac.pac"
            with open(pac_file, 'w', encoding='utf-8') as f:
                f.write(self._pac_content)
            
            # Configure px to use PAC file
            # Note: This would need to be integrated with actual px configuration
            self.logger.info(f"Applied PAC configuration from {self._pac_source}")
            
        except Exception as e:
            self.logger.error(f"Failed to apply PAC configuration: {e}")
            raise
    
    def get_proxy_status(self) -> ProxyStatus:
        """
        Get current proxy status.
        
        Returns:
            Current proxy status
        """
        return self._proxy_status
    
    def add_status_callback(self, callback: Callable[[ProxyStatus], None]):
        """
        Add a callback to be notified of status changes.
        
        Args:
            callback: Function to call when status changes
        """
        self._status_callbacks.append(callback)
    
    def remove_status_callback(self, callback: Callable[[ProxyStatus], None]):
        """
        Remove a status change callback.
        
        Args:
            callback: Function to remove from callbacks
        """
        if callback in self._status_callbacks:
            self._status_callbacks.remove(callback)
    
    def _notify_status_change(self):
        """Notify all registered callbacks of status change."""
        for callback in self._status_callbacks:
            try:
                callback(self._proxy_status)
            except Exception as e:
                self.logger.error(f"Error in status callback: {e}")
    
    def validate_configuration(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate proxy configuration.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            Dictionary with validation results
        """
        errors = []
        warnings = []
        
        try:
            # Validate port
            port = config.get('port', 3128)
            if not isinstance(port, int) or not (1 <= port <= 65535):
                errors.append(f"Invalid port: {port}. Must be between 1 and 65535")
            
            # Validate listen address
            listen_address = config.get('listen_address', '127.0.0.1')
            if not self._is_valid_ip_address(listen_address):
                errors.append(f"Invalid listen address: {listen_address}")
            
            # Validate mode
            mode = config.get('mode', 'manual')
            valid_modes = {'manual', 'pac', 'auto'}
            if mode not in valid_modes:
                errors.append(f"Invalid mode: {mode}. Must be one of {valid_modes}")
            
            # Validate PAC configuration if mode is PAC
            if mode == 'pac':
                pac_config = config.get('pac_config')
                if not pac_config:
                    errors.append("PAC mode selected but no PAC configuration available")
                elif not hasattr(pac_config, 'content') or not pac_config.content:
                    errors.append("PAC mode selected but no PAC content available")
                elif not pac_config.is_valid:
                    errors.append("PAC configuration is not valid")
                    if hasattr(pac_config, 'validation_errors'):
                        errors.extend(pac_config.validation_errors)
                else:
                    # PAC config is valid
                    pac_validation = self._validate_pac_content(pac_config.content)
                    if not pac_validation['is_valid']:
                        errors.extend(pac_validation['errors'])
                    warnings.extend(pac_validation.get('warnings', []))
            
            # Check for port conflicts
            if self._is_port_in_use(port):
                warnings.append(f"Port {port} may already be in use")
            
            # Validate no proxy configuration
            if not self._no_proxy_config.validate():
                errors.extend([f"No proxy: {error}" for error in self._no_proxy_config.validation_errors])
            
        except Exception as e:
            errors.append(f"Configuration validation error: {str(e)}")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def _is_valid_ip_address(self, ip: str) -> bool:
        """Validate IP address format."""
        if ip in ('localhost', '0.0.0.0'):
            return True
        
        try:
            parts = ip.split('.')
            if len(parts) != 4:
                return False
            
            for part in parts:
                num = int(part)
                if not (0 <= num <= 255):
                    return False
            
            return True
        except (ValueError, AttributeError):
            return False
    
    def _is_port_in_use(self, port: int) -> bool:
        """Check if a port is already in use."""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', port))
                return False
        except OSError:
            return True
    
    def _validate_pac_content(self, pac_content: str) -> Dict[str, Any]:
        """
        Validate PAC file content.
        
        Args:
            pac_content: PAC file content to validate
            
        Returns:
            Dictionary with validation results
        """
        errors = []
        warnings = []
        
        try:
            # Basic PAC validation
            if not pac_content.strip():
                errors.append("PAC content is empty")
                return {'is_valid': False, 'errors': errors, 'warnings': warnings}
            
            # Check for required FindProxyForURL function
            if 'FindProxyForURL' not in pac_content:
                errors.append("PAC file must contain FindProxyForURL function")
            
            # Check for basic JavaScript syntax issues
            if pac_content.count('(') != pac_content.count(')'):
                warnings.append("Mismatched parentheses in PAC content")
            
            if pac_content.count('{') != pac_content.count('}'):
                warnings.append("Mismatched braces in PAC content")
            
            # TODO: Add more sophisticated PAC validation using JavaScript engine
            
        except Exception as e:
            errors.append(f"PAC validation error: {str(e)}")
        
        return {
            'is_valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings
        }
    
    def set_pac_content(self, content: str, source: str = "inline"):
        """
        Set PAC content for the proxy.
        
        Args:
            content: PAC file content
            source: Source description (file path, URL, or "inline")
        """
        self._pac_content = content
        self._pac_source = source
        self.logger.info(f"PAC content set from {source}")
    
    def get_pac_content(self) -> Optional[str]:
        """Get current PAC content."""
        return self._pac_content
    
    def get_pac_source(self) -> Optional[str]:
        """Get current PAC source."""
        return self._pac_source
    
    def set_no_proxy_configuration(self, config: NoProxyConfiguration):
        """
        Set no proxy configuration.
        
        Args:
            config: No proxy configuration
        """
        if config is None:
            raise ValueError("No proxy configuration cannot be None")
        
        self._no_proxy_config = config
        self.logger.info(f"No proxy configuration updated: {config.get_summary()}")
    
    def get_no_proxy_configuration(self) -> NoProxyConfiguration:
        """Get current no proxy configuration."""
        return self._no_proxy_config
    
    def _apply_no_proxy_configuration(self):
        """Apply no proxy configuration to px."""
        try:
            if not self._no_proxy_config:
                return
            
            # Convert to px-compatible format
            no_proxy_string = self._no_proxy_config.to_px_format()
            
            if no_proxy_string:
                # Set environment variable for px to use
                import os
                os.environ['NO_PROXY'] = no_proxy_string
                os.environ['no_proxy'] = no_proxy_string  # Some systems use lowercase
                
                self.logger.info(f"Applied no proxy configuration: {no_proxy_string}")
            else:
                # Clear no proxy settings
                import os
                os.environ.pop('NO_PROXY', None)
                os.environ.pop('no_proxy', None)
                self.logger.info("Cleared no proxy configuration")
            
        except Exception as e:
            self.logger.error(f"Failed to apply no proxy configuration: {e}")
            raise
    
    def _setup_recovery_strategies(self):
        """Set up error recovery strategies."""
        try:
            # Add recovery strategies to error manager
            self.error_manager.add_handler(PACRecoveryStrategy())
            self.error_manager.add_handler(NetworkRecoveryStrategy())
            self.error_manager.add_handler(ProxyRecoveryStrategy())
            self.error_manager.add_handler(ConfigurationRecoveryStrategy())
            
            self.logger.info("Error recovery strategies initialized")
        except Exception as e:
            self.logger.error(f"Failed to setup recovery strategies: {e}")


def setup_px_monitoring(event_system: EventSystem) -> PxConfigurationBridge:
    """
    Set up px monitoring with the given event system.
    
    This is a convenience function that creates and configures
    a PxConfigurationBridge.
    
    Args:
        event_system: Event system for monitoring
        
    Returns:
        Configured bridge instance
    """
    bridge = PxConfigurationBridge(event_system)
    bridge.configure_px_monitoring()
    return bridge


def disable_px_monitoring(bridge: PxConfigurationBridge):
    """
    Disable px monitoring.
    
    Args:
        bridge: Bridge instance to disable
    """
    if bridge:
        bridge.restore_original_handler()