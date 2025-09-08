"""
Request data model for capturing HTTP request information.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class RequestData:
    """
    Represents an HTTP request being processed by the proxy.
    
    Attributes:
        timestamp: When the request was initiated
        url: The target URL being requested
        method: HTTP method (GET, POST, etc.)
        proxy_decision: Proxy routing decision ("DIRECT" or "PROXY host:port")
        status: Current request status ("pending", "completed", "error")
        request_id: Unique identifier for this request
    """
    timestamp: datetime
    url: str
    method: str
    proxy_decision: str
    status: str = "pending"
    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def __post_init__(self):
        """Validate the request data after initialization."""
        self._validate()
    
    def _validate(self):
        """Validate request data fields."""
        if not self.url:
            raise ValueError("URL cannot be empty")
        
        if not self.url.startswith(('http://', 'https://')):
            raise ValueError("URL must start with http:// or https://")
        
        valid_methods = {'GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'OPTIONS', 'PATCH', 'CONNECT'}
        if self.method.upper() not in valid_methods:
            raise ValueError(f"Invalid HTTP method: {self.method}")
        
        valid_statuses = {'pending', 'completed', 'error'}
        if self.status not in valid_statuses:
            raise ValueError(f"Invalid status: {self.status}. Must be one of {valid_statuses}")
        
        if not (self.proxy_decision == "DIRECT" or self.proxy_decision.startswith("PROXY ")):
            raise ValueError("Proxy decision must be 'DIRECT' or start with 'PROXY '")
    
    def is_completed(self) -> bool:
        """Check if the request has been completed."""
        return self.status == "completed"
    
    def is_error(self) -> bool:
        """Check if the request resulted in an error."""
        return self.status == "error"
    
    def uses_proxy(self) -> bool:
        """Check if the request uses a proxy server."""
        return self.proxy_decision != "DIRECT"
    
    def get_proxy_host_port(self) -> Optional[tuple[str, int]]:
        """Extract proxy host and port from proxy decision."""
        if not self.uses_proxy():
            return None
        
        try:
            # Format: "PROXY host:port"
            proxy_part = self.proxy_decision.split(" ", 1)[1]
            host, port = proxy_part.rsplit(":", 1)
            return (host, int(port))
        except (IndexError, ValueError):
            return None