"""
Simple Proxy Handler

A simple HTTP proxy handler that doesn't require authentication
but supports monitoring and PAC configuration.
"""

import socket
import time
import uuid
import urllib.request
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse
import logging

from ..communication.events import RequestEvent, ResponseEvent, ErrorEvent, EventType


class SimpleProxyHandler(BaseHTTPRequestHandler):
    """
    Simple HTTP proxy handler without authentication requirements.
    
    This handler provides basic proxy functionality with monitoring
    support but doesn't require client authentication.
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize the handler."""
        self.logger = logging.getLogger(__name__)
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        self._handle_request()
    
    def do_POST(self):
        """Handle POST requests."""
        self._handle_request()
    
    def do_PUT(self):
        """Handle PUT requests."""
        self._handle_request()
    
    def do_DELETE(self):
        """Handle DELETE requests."""
        self._handle_request()
    
    def do_HEAD(self):
        """Handle HEAD requests."""
        self._handle_request()
    
    def do_CONNECT(self):
        """Handle CONNECT requests for HTTPS tunneling."""
        self._handle_connect()
    
    def _handle_request(self):
        """Handle HTTP requests."""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            # Get URL
            url = self.path
            if not url.startswith('http'):
                # Relative URL, construct full URL
                host = self.headers.get('Host', 'localhost')
                url = f"http://{host}{url}"
            
            self.logger.debug(f"Handling request: {self.command} {url}")
            
            # Determine proxy decision using PAC if available
            proxy_decision = self._get_proxy_decision(url)
            
            # Send request event for monitoring
            self._send_request_event(request_id, url, self.command, proxy_decision)
            
            # Create request
            req = urllib.request.Request(url, method=self.command)
            
            # Copy headers (excluding proxy-specific ones)
            for header, value in self.headers.items():
                if header.lower() not in ['host', 'connection', 'proxy-connection']:
                    req.add_header(header, value)
            
            # Handle request body for POST/PUT
            if self.command in ['POST', 'PUT']:
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    post_data = self.rfile.read(content_length)
                    req.data = post_data
            
            # Make the request through proxy if specified
            try:
                # Parse proxy decision and create proxy handler if needed
                proxy_handler = self._create_proxy_handler(proxy_decision)
                
                if proxy_handler:
                    # Use proxy
                    opener = urllib.request.build_opener(proxy_handler)
                    try:
                        with opener.open(req, timeout=30) as response:
                            self._send_successful_response(response, request_id, start_time)
                    except Exception as e:
                        self.logger.error(f"Proxy connection failed: {e}, falling back to DIRECT")
                        # Send fallback event for monitoring
                        self._send_fallback_event(request_id, proxy_decision, "DIRECT", str(e))
                        # Fallback to direct connection
                        with urllib.request.urlopen(req, timeout=30) as response:
                            self._send_successful_response(response, request_id, start_time)
                else:
                    # Direct connection
                    with urllib.request.urlopen(req, timeout=30) as response:
                        self._send_successful_response(response, request_id, start_time)
            except Exception as e:
                self._send_error_response(str(e), request_id, start_time)
        
        except Exception as e:
            self.logger.error(f"Error handling request: {e}")
            self._send_error_response(str(e), request_id, start_time)
    
    def _handle_connect(self):
        """Handle CONNECT method for HTTPS tunneling."""
        request_id = str(uuid.uuid4())
        start_time = time.time()
        
        try:
            # Parse target host and port
            host, port = self.path.split(':')
            port = int(port)
            
            self.logger.debug(f"CONNECT to {host}:{port}")
            
            # Send request event
            https_url = f"https://{host}:{port}"
            proxy_decision = self._get_proxy_decision(https_url)
            self._send_request_event(request_id, https_url, "CONNECT", proxy_decision)
            
            # Create connection to target server (through proxy if specified)
            try:
                # Check if we should use a proxy for this HTTPS connection
                if proxy_decision and proxy_decision.strip().upper() != "DIRECT":
                    # Parse proxy decision
                    parts = proxy_decision.strip().split()
                    if len(parts) >= 2 and parts[0].upper() == "PROXY":
                        proxy_address = parts[1]
                        proxy_host, proxy_port = proxy_address.split(':')
                        proxy_port = int(proxy_port)
                        
                        self.logger.debug(f"CONNECT through proxy: {proxy_host}:{proxy_port}")
                        
                        # Connect to proxy first
                        try:
                            proxy_socket = socket.create_connection((proxy_host, proxy_port), timeout=30)
                            
                            # Send CONNECT request to proxy
                            connect_request = f"CONNECT {host}:{port} HTTP/1.1\r\nHost: {host}:{port}\r\n\r\n"
                            proxy_socket.send(connect_request.encode())
                            
                            # Read proxy response
                            response = proxy_socket.recv(4096).decode()
                            if "200" not in response.split('\n')[0]:
                                first_line = response.split('\n')[0]
                                raise Exception(f"Proxy CONNECT failed: {first_line}")
                            
                            target_socket = proxy_socket
                            
                        except Exception as e:
                            self.logger.error(f"Proxy connection failed: {e}, falling back to DIRECT")
                            # Send fallback event for monitoring
                            fallback_decision = f"{proxy_decision} --fb--> DIRECT"
                            self._send_fallback_event(request_id, proxy_decision, "DIRECT", str(e))
                            # Fallback to direct connection
                            target_socket = socket.create_connection((host, port), timeout=30)
                    else:
                        # Direct connection if proxy decision is malformed
                        target_socket = socket.create_connection((host, port), timeout=30)
                else:
                    # Direct connection
                    target_socket = socket.create_connection((host, port), timeout=30)
                    
            except Exception as e:
                self.send_error(502, f"Bad Gateway: {str(e)}")
                self._send_error_event(str(e), request_id)
                return
            
            # Send 200 Connection established
            self.send_response(200, 'Connection established')
            self.end_headers()
            
            # Send response event
            self._send_response_event(200, request_id, start_time)
            
            # Start tunneling
            self._tunnel_data(self.connection, target_socket)
            
        except Exception as e:
            self.logger.error(f"Error in CONNECT: {e}")
            self.send_error(500, f"Internal Server Error: {str(e)}")
            self._send_error_event(str(e), request_id)
    
    def _tunnel_data(self, client_socket, target_socket):
        """Tunnel data between client and target for HTTPS."""
        import select
        
        try:
            sockets = [client_socket, target_socket]
            
            while True:
                ready_sockets, _, error_sockets = select.select(sockets, [], sockets, 1.0)
                
                if error_sockets:
                    break
                
                for sock in ready_sockets:
                    try:
                        data = sock.recv(4096)
                        if not data:
                            return
                        
                        if sock is client_socket:
                            target_socket.send(data)
                        else:
                            client_socket.send(data)
                    except:
                        return
        
        except Exception as e:
            self.logger.error(f"Error tunneling data: {e}")
        finally:
            try:
                target_socket.close()
            except:
                pass
    
    def _get_proxy_decision(self, url):
        """Get proxy decision using PAC if available."""
        try:
            # Check if server has PAC configuration
            if hasattr(self.server, 'pac_content') and self.server.pac_content:
                return self._evaluate_pac_function(url, self.server.pac_content)
            
            # Default to DIRECT if no PAC
            return "DIRECT"
            
        except Exception as e:
            self.logger.error(f"Error in proxy decision: {e}")
            return "DIRECT"
    
    def _create_proxy_handler(self, proxy_decision):
        """Create proxy handler based on PAC decision."""
        try:
            if not proxy_decision or proxy_decision.strip().upper() == "DIRECT":
                return None  # Direct connection
            
            # Parse proxy decision (e.g., "PROXY 127.0.0.1:8080")
            parts = proxy_decision.strip().split()
            if len(parts) >= 2 and parts[0].upper() == "PROXY":
                proxy_address = parts[1]
                
                # Create proxy handler
                proxy_handler = urllib.request.ProxyHandler({
                    'http': f'http://{proxy_address}',
                    'https': f'http://{proxy_address}'
                })
                
                self.logger.debug(f"Using proxy: {proxy_address}")
                return proxy_handler
            
            # If we can't parse the proxy decision, fall back to direct
            self.logger.warning(f"Could not parse proxy decision: {proxy_decision}, using DIRECT")
            return None
            
        except Exception as e:
            self.logger.error(f"Error creating proxy handler: {e}")
            return None
    
    def _evaluate_pac_function(self, url, pac_content):
        """Evaluate PAC function using JavaScript engine."""
        try:
            import execjs
            
            # Parse URL to get host
            parsed = urlparse(url)
            host = parsed.netloc.split(':')[0]
            
            # PAC helper functions
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
                return true;
            }
            
            function isInNet(host, pattern, mask) {
                if (host === '127.0.0.1' && pattern.startsWith('127.')) return true;
                if (host.startsWith('192.168.') && pattern.startsWith('192.168.')) return true;
                if (host.startsWith('10.') && pattern.startsWith('10.')) return true;
                if (host.startsWith('172.16.') && pattern.startsWith('172.16.')) return true;
                return false;
            }
            
            function dnsResolve(host) {
                return host;
            }
            
            function myIpAddress() {
                return '127.0.0.1';
            }
            
            function dnsDomainLevels(host) {
                return host.split('.').length - 1;
            }
            
            function shExpMatch(str, shexp) {
                var regex = shexp.replace(/\\*/g, '.*').replace(/\\?/g, '.');
                return new RegExp('^' + regex + '$').test(str);
            }
            '''
            
            # Combine helpers with PAC content
            full_pac_script = pac_helpers + '\n' + pac_content
            
            # Execute PAC script
            ctx = execjs.compile(full_pac_script)
            result = ctx.call('FindProxyForURL', url, host)
            
            return str(result).strip()
            
        except ImportError:
            self.logger.warning("execjs not available, using DIRECT")
            return "DIRECT"
        except Exception as e:
            self.logger.error(f"PAC evaluation error: {e}")
            return "DIRECT"
    
    def _send_request_event(self, request_id, url, method, proxy_decision):
        """Send request event for monitoring."""
        try:
            if hasattr(self.server, 'event_system') and self.server.event_system:
                event = RequestEvent(
                    event_type=EventType.REQUEST,
                    timestamp=datetime.now(),
                    event_id=request_id,
                    url=url,
                    method=method,
                    proxy_decision=proxy_decision,
                    request_id=request_id,
                    headers=dict(self.headers)
                )
                self.server.event_system.send_event(event)
        except Exception as e:
            self.logger.error(f"Error sending request event: {e}")
    
    def _send_response_event(self, status_code, request_id, start_time, headers=None, body_preview=""):
        """Send response event for monitoring."""
        try:
            if hasattr(self.server, 'event_system') and self.server.event_system:
                response_time = time.time() - start_time
                event = ResponseEvent(
                    event_type=EventType.RESPONSE,
                    timestamp=datetime.now(),
                    event_id=str(uuid.uuid4()),
                    request_id=request_id,
                    status_code=status_code,
                    headers=headers or {},
                    body_preview=body_preview,
                    content_length=len(body_preview),
                    response_time=response_time
                )
                self.server.event_system.send_event(event)
        except Exception as e:
            self.logger.error(f"Error sending response event: {e}")
    
    def _send_error_event(self, error_message, request_id):
        """Send error event for monitoring."""
        try:
            if hasattr(self.server, 'event_system') and self.server.event_system:
                event = ErrorEvent(
                    event_type=EventType.ERROR,
                    timestamp=datetime.now(),
                    event_id=str(uuid.uuid4()),
                    error_type="proxy",
                    error_message=error_message,
                    request_id=request_id,
                    url=getattr(self, 'path', 'unknown')
                )
                self.server.event_system.send_event(event)
        except Exception as e:
            self.logger.error(f"Error sending error event: {e}")
    
    def _send_fallback_event(self, request_id, original_proxy, fallback_proxy, error_reason):
        """Send fallback event for monitoring."""
        try:
            if hasattr(self.server, 'event_system') and self.server.event_system:
                # Create a special request event to update the monitoring display
                fallback_decision = f"{original_proxy} --fb--> {fallback_proxy}"
                event = RequestEvent(
                    event_type=EventType.REQUEST,
                    timestamp=datetime.now(),
                    event_id=str(uuid.uuid4()),
                    url=getattr(self, 'path', 'unknown'),
                    method="FALLBACK",
                    proxy_decision=fallback_decision,
                    request_id=request_id,
                    headers={"X-Fallback-Reason": error_reason}
                )
                self.server.event_system.send_event(event)
        except Exception as e:
            self.logger.error(f"Error sending fallback event: {e}")
    
    def _send_successful_response(self, response, request_id, start_time):
        """Send successful response to client."""
        try:
            # Read response body
            response_body = response.read()
            body_preview = response_body[:500].decode('utf-8', errors='ignore') if response_body else ""
            
            # Send response event
            self._send_response_event(
                response.getcode(), 
                request_id, 
                start_time, 
                dict(response.headers), 
                body_preview
            )
            
            # Send response to client
            self.send_response(response.getcode())
            
            # Copy response headers
            for header, value in response.headers.items():
                if header.lower() not in ['connection', 'transfer-encoding']:
                    self.send_header(header, value)
            self.end_headers()
            
            # Send response body
            self.wfile.write(response_body)
            
        except Exception as e:
            self.logger.error(f"Error sending successful response: {e}")
            self._send_error_response(str(e), request_id, start_time)
    
    def _send_error_response(self, error_message, request_id, start_time):
        """Send error response to client."""
        try:
            # Clean error message
            clean_error = str(error_message).encode('ascii', errors='ignore').decode('ascii')
            
            # Send error event
            self._send_error_event(clean_error, request_id)
            
            # Send HTTP error response
            self.send_error(500, f"Proxy error: {clean_error}")
            
        except Exception as e:
            self.logger.error(f"Error sending error response: {e}")
            try:
                self.send_error(500, "Proxy connection failed")
            except:
                pass
    
    def log_message(self, format, *args):
        """Override to use our logger."""
        self.logger.debug(format % args)