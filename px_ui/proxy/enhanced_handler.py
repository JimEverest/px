"""
Enhanced px proxy handler with monitoring hooks.

This module extends the px.handler.PxHandler class to add monitoring capabilities
for real-time request/response tracking in the UI.
"""

import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, Callable
from urllib.parse import urlparse

# Import px components
import px.handler
from px.config import STATE

# Import our event system
from ..communication.events import RequestEvent, ResponseEvent, ErrorEvent, ProxyDecisionUpdateEvent, EventType
from ..communication.event_system import EventSystem

# Import error handling
from ..error_handling import ErrorManager, ErrorCategory, ErrorSeverity, get_error_manager


class MonitoringHooks:
    """
    Callback system for capturing proxy events.
    
    This class provides hooks that are called at various points during
    request processing to capture monitoring data.
    """
    
    def __init__(self, event_system: Optional[EventSystem] = None):
        """
        Initialize monitoring hooks.
        
        Args:
            event_system: Event system to send events to
        """
        self.event_system = event_system
        self._request_start_times: Dict[str, float] = {}
        
    def on_request_start(self, request_id: str, url: str, method: str, headers: Optional[Dict[str, str]] = None):
        """
        Called when a request starts.
        
        Args:
            request_id: Unique identifier for the request
            url: Target URL
            method: HTTP method
            headers: Request headers
        """
        self._request_start_times[request_id] = time.time()
        
        if self.event_system:
            # We'll set proxy_decision later in on_proxy_decision
            event = RequestEvent(
                event_type=None,  # Will be set by __post_init__
                timestamp=datetime.now(),
                event_id=str(uuid.uuid4()),
                url=url,
                method=method,
                proxy_decision="PENDING",
                request_id=request_id,
                headers=headers
            )
            self.event_system.send_event(event)
    
    def on_proxy_decision(self, request_id: str, proxy_decision: str):
        """
        Called when PAC decision is made.
        
        Args:
            request_id: Request identifier
            proxy_decision: "DIRECT" or "PROXY host:port"
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"on_proxy_decision called for request {request_id} with decision {proxy_decision}")

        if self.event_system:
            event = ProxyDecisionUpdateEvent(
                event_type=EventType.PROXY_DECISION_UPDATE,
                timestamp=datetime.now(),
                event_id=str(uuid.uuid4()),
                request_id=request_id,
                proxy_decision=proxy_decision,
            )
            self.event_system.send_event(event)
    
    def on_proxy_fallback(self, request_id: str, original_proxy: str, fallback_proxy: str, error_reason: str):
        """
        Called when proxy fallback occurs.
        
        Args:
            request_id: Request identifier
            original_proxy: Original proxy decision
            fallback_proxy: Fallback proxy decision
            error_reason: Reason for fallback
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"on_proxy_fallback called for request {request_id}")

        if self.event_system:
            fallback_decision = f"{original_proxy} --fb--> {fallback_proxy}"
            event = ProxyDecisionUpdateEvent(
                event_type=EventType.PROXY_DECISION_UPDATE,
                timestamp=datetime.now(),
                event_id=str(uuid.uuid4()),
                request_id=request_id,
                proxy_decision=fallback_decision,
            )
            self.event_system.send_event(event)
    
    def on_response_received(self, request_id: str, status_code: int, headers: Dict[str, str], 
                           body_preview: str, content_length: int):
        """
        Called when a response is received.
        
        Args:
            request_id: Request identifier
            status_code: HTTP status code
            headers: Response headers
            body_preview: First 500 characters of response body
            content_length: Total content length
        """
        # Calculate response time
        start_time = self._request_start_times.get(request_id, time.time())
        response_time = time.time() - start_time
        
        # Clean up start time
        if request_id in self._request_start_times:
            del self._request_start_times[request_id]
        
        if self.event_system:
            event = ResponseEvent(
                event_type=None,  # Will be set by __post_init__
                timestamp=datetime.now(),
                event_id=str(uuid.uuid4()),
                request_id=request_id,
                status_code=status_code,
                headers=headers,
                body_preview=body_preview,
                content_length=content_length,
                response_time=response_time
            )
            self.event_system.send_event(event)
    
    def on_error(self, error_type: str, error_message: str, error_details: Optional[str] = None,
                request_id: Optional[str] = None, url: Optional[str] = None):
        """
        Called when an error occurs.
        
        Args:
            error_type: Type of error (network, auth, pac, config)
            error_message: Error message
            error_details: Additional error details
            request_id: Associated request ID if applicable
            url: Associated URL if applicable
        """
        # Clean up start time if we have a request_id
        if request_id and request_id in self._request_start_times:
            del self._request_start_times[request_id]
        
        # Handle error with error management system
        error_category = self._map_error_type_to_category(error_type)
        error_severity = self._determine_error_severity(error_type, error_message)
        
        error_manager = get_error_manager()
        error_manager.handle_error(
            category=error_category,
            severity=error_severity,
            message=error_message,
            details=error_details,
            context={
                'request_id': request_id,
                'url': url,
                'error_type': error_type,
                'component': 'enhanced_handler'
            }
        )
        
        if self.event_system:
            event = ErrorEvent(
                event_type=None,  # Will be set by __post_init__
                timestamp=datetime.now(),
                event_id=str(uuid.uuid4()),
                error_type=error_type,
                error_message=error_message,
                error_details=error_details,
                request_id=request_id,
                url=url
            )
            self.event_system.send_event(event)


    def _map_error_type_to_category(self, error_type: str) -> ErrorCategory:
        """Map error type string to ErrorCategory enum."""
        mapping = {
            'network': ErrorCategory.NETWORK,
            'auth': ErrorCategory.AUTHENTICATION,
            'proxy': ErrorCategory.PROXY,
            'pac': ErrorCategory.PAC_VALIDATION,
            'config': ErrorCategory.CONFIGURATION
        }
        return mapping.get(error_type, ErrorCategory.SYSTEM)
    
    def _determine_error_severity(self, error_type: str, error_message: str) -> ErrorSeverity:
        """Determine error severity based on type and message."""
        # Critical errors
        if 'fatal' in error_message.lower() or 'critical' in error_message.lower():
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if error_type in ['auth', 'proxy'] or 'connection refused' in error_message:
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        if error_type in ['network', 'pac']:
            return ErrorSeverity.MEDIUM
        
        # Default to low severity
        return ErrorSeverity.LOW


class EnhancedPxHandler(px.handler.PxHandler):
    """
    Enhanced proxy handler with monitoring capabilities.
    
    This class extends px.handler.PxHandler to add request/response monitoring
    hooks for real-time UI updates.
    """
    
    # Class-level monitoring hooks instance
    monitoring_hooks: Optional[MonitoringHooks] = None
    
    @classmethod
    def set_monitoring_hooks(cls, hooks: MonitoringHooks):
        """Set the monitoring hooks for all handler instances."""
        cls.monitoring_hooks = hooks
    
    def __init__(self, *args, **kwargs):
        """Initialize the enhanced handler."""
        super().__init__(*args, **kwargs)
        self._current_request_id: Optional[str] = None
        self._current_url: Optional[str] = None
        self._current_method: Optional[str] = None
        
        # Initialize logger
        import logging
        self.logger = logging.getLogger(__name__)
    
    def do_curl(self):
        """
        Handle incoming request using libcurl with monitoring hooks.
        
        This method overrides the parent do_curl() to add request/response
        monitoring capabilities.
        """
        # Generate unique request ID
        self._current_request_id = str(uuid.uuid4())
        self._current_url = self.path
        self._current_method = self.command
        
        # Capture request headers
        request_headers = {}
        if self.headers:
            for key, value in self.headers.items():
                request_headers[key] = value
        
        # Call monitoring hook for request start
        if self.monitoring_hooks:
            try:
                self.monitoring_hooks.on_request_start(
                    request_id=self._current_request_id,
                    url=self._current_url,
                    method=self._current_method,
                    headers=request_headers
                )
            except Exception as e:
                # Don't let monitoring errors break the proxy
                print(f"Monitoring hook error (request_start): {e}")
        
        # Call parent implementation with error handling
        try:
            # Check if px mcurl is properly initialized
            from px.config import STATE
            if hasattr(STATE, 'mcurl') and STATE.mcurl is None:
                import logging
                self.logger = logging.getLogger(__name__)
                self.logger.warning("px mcurl is not initialized, attempting to initialize...")
                try:
                    import px.mcurl
                    STATE.mcurl = px.mcurl.Mcurl()
                    self.logger.info("px mcurl initialized successfully")
                except ImportError:
                    # px.mcurl module doesn't exist, continue without it
                    self.logger.debug("px.mcurl module not available, continuing with default behavior")
                except Exception as mcurl_error:
                    self.logger.warning(f"Failed to initialize px mcurl: {mcurl_error}, continuing anyway")
            
            # Store original curl object if it exists
            original_curl = self.curl
            
            # Call parent do_curl
            super().do_curl()
            
            # If we have a curl object, try to capture response information
            if self.curl and hasattr(self.curl, 'resp') and hasattr(self.curl, 'headers'):
                self._capture_response_data()
            
        except Exception as e:
            # Capture error information
            if self.monitoring_hooks:
                try:
                    error_type = "network"
                    if "auth" in str(e).lower():
                        error_type = "auth"
                    elif "proxy" in str(e).lower():
                        error_type = "proxy"
                    
                    # Check if this is a proxy connection failure that might trigger fallback
                    if "connection refused" in str(e).lower() or "timeout" in str(e).lower():
                        # This might be a proxy connection failure
                        # Check if we have a proxy configured
                        if hasattr(self, 'proxy_servers') and self.proxy_servers:
                            server_info = self.proxy_servers[0]
                            if len(server_info) >= 2:
                                original_proxy = f"PROXY {server_info[0]}:{server_info[1]}"
                                self.monitoring_hooks.on_proxy_fallback(
                                    request_id=self._current_request_id,
                                    original_proxy=original_proxy,
                                    fallback_proxy="DIRECT",
                                    error_reason=str(e)
                                )
                    
                    self.monitoring_hooks.on_error(
                        error_type=error_type,
                        error_message=str(e),
                        error_details=None,
                        request_id=self._current_request_id,
                        url=self._current_url
                    )
                except Exception as hook_error:
                    print(f"Monitoring hook error (error): {hook_error}")
            
            # Handle with error management system
            error_manager = get_error_manager()
            error_manager.handle_error(
                category=ErrorCategory.NETWORK,
                severity=ErrorSeverity.HIGH,
                message=str(e),
                context={
                    'request_id': self._current_request_id,
                    'url': self._current_url,
                    'method': self._current_method,
                    'component': 'enhanced_handler'
                },
                exception=e
            )
            
            # Re-raise the original exception
            raise
    
    def _capture_response_data(self):
        """
        Capture response data from curl object. 
        
        This method extracts response information from the curl object
        and sends it to monitoring hooks.
        """
        if not self.curl or not self.monitoring_hooks:
            return
        
        try:
            # Get status code
            status_code = getattr(self.curl, 'resp', 0)
            
            # Get response headers
            response_headers = {}
            if hasattr(self.curl, 'headers') and self.curl.headers:
                # Parse headers from curl object
                # Note: The actual header format depends on mcurl implementation
                headers_data = getattr(self.curl, 'headers', {})
                if isinstance(headers_data, dict):
                    response_headers = headers_data
                elif isinstance(headers_data, str):
                    # Parse header string if needed
                    response_headers = self._parse_header_string(headers_data)
            
            # Get content length
            content_length = 0
            if 'content-length' in response_headers:
                try:
                    content_length = int(response_headers['content-length'])
                except (ValueError, TypeError):
                    content_length = 0
            
            # Get body preview (first 500 chars)
            body_preview = ""
            if hasattr(self.curl, 'body') and self.curl.body:
                body_data = getattr(self.curl, 'body', '')
                if isinstance(body_data, bytes):
                    try:
                        body_preview = body_data.decode('utf-8', errors='ignore')[:500]
                    except Exception:
                        body_preview = str(body_data)[:500]
                elif isinstance(body_data, str):
                    body_preview = body_data[:500]
            
            # Send response event
            self.monitoring_hooks.on_response_received(
                request_id=self._current_request_id,
                status_code=status_code,
                headers=response_headers,
                body_preview=body_preview,
                content_length=content_length
            )
            
        except Exception as e:
            # Don't let monitoring errors break the proxy
            print(f"Error capturing response data: {e}")
    
    def _parse_header_string(self, header_string: str) -> Dict[str, str]:
        """
        Parse header string into dictionary.
        
        Args:
            header_string: Raw header string
            
        Returns:
            Dictionary of headers
        """
        headers = {}
        try:
            lines = header_string.strip().split('\n')
            for line in lines:
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip().lower()] = value.strip()
        except Exception as e:
            print(f"Error parsing headers: {e}")
        
        return headers
    
    def get_destination(self):
        """
        Override get_destination to capture proxy decision.
        
        This method calls the parent implementation and captures the
        proxy decision for monitoring.
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"get_destination called for request {self._current_request_id}")

        # Call parent implementation
        result = super().get_destination()
        
        # Determine proxy decision
        proxy_decision = "DIRECT" if result else "PROXY"
        if not result and self.proxy_servers:
            # Format proxy decision with server info
            server_info = self.proxy_servers[0]
            if len(server_info) >= 2:
                proxy_decision = f"PROXY {server_info[0]}:{server_info[1]}"
        
        # Call monitoring hook
        if self.monitoring_hooks and self._current_request_id:
            try:
                self.monitoring_hooks.on_proxy_decision(
                    request_id=self._current_request_id,
                    proxy_decision=proxy_decision
                )
            except Exception as e:
                print(f"Monitoring hook error (proxy_decision): {e}")
        
        return result
    
    def send_error(self, code, message=None):
        """
        Override send_error to capture error responses.
        
        Args:
            code: HTTP error code
            message: Error message
        """
        # Capture error information
        if self.monitoring_hooks and self._current_request_id:
            try:
                error_type = "network"
                if code in [401, 407]:
                    error_type = "auth"
                elif code >= 500:
                    error_type = "server"
                
                self.monitoring_hooks.on_error(
                    error_type=error_type,
                    error_message=f"HTTP {code}: {message or 'Unknown error'}",
                    error_details=None,
                    request_id=self._current_request_id,
                    url=self._current_url
                )
            except Exception as e:
                print(f"Monitoring hook error (send_error): {e}")
        
        # Call parent implementation
        super().send_error(code, message)
    
    def _map_error_type_to_category(self, error_type: str) -> ErrorCategory:
        """Map error type string to ErrorCategory enum."""
        mapping = {
            'network': ErrorCategory.NETWORK,
            'auth': ErrorCategory.AUTHENTICATION,
            'proxy': ErrorCategory.PROXY,
            'pac': ErrorCategory.PAC_VALIDATION,
            'config': ErrorCategory.CONFIGURATION
        }
        return mapping.get(error_type.lower(), ErrorCategory.SYSTEM)
    
    def _determine_error_severity(self, error_type: str, error_message: str) -> ErrorSeverity:
        """Determine error severity based on type and message."""
        error_type = error_type.lower()
        error_message = error_message.lower()
        
        # Critical errors
        if 'critical' in error_message or 'fatal' in error_message:
            return ErrorSeverity.CRITICAL
        
        # High severity errors
        if error_type in ['auth', 'proxy'] or 'connection refused' in error_message:
            return ErrorSeverity.HIGH
        
        # Medium severity errors
        if error_type in ['network', 'pac'] or 'timeout' in error_message:
            return ErrorSeverity.MEDIUM
        
        # Default to low severity
        return ErrorSeverity.LOW


def create_enhanced_handler_class(event_system: EventSystem) -> type:
    """
    Create an enhanced handler class with monitoring hooks.
    
    This function creates a new handler class with monitoring hooks
    configured for the given event system.
    
    Args:
        event_system: Event system to send monitoring events to
        
    Returns:
        Enhanced handler class ready for use with px
    """
    # Create monitoring hooks
    hooks = MonitoringHooks(event_system)
    
    # Set hooks on the class
    EnhancedPxHandler.set_monitoring_hooks(hooks)
    
    return EnhancedPxHandler
