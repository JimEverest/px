"""
Response data model for capturing HTTP response information.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ResponseData:
    """
    Represents an HTTP response received from a server or proxy.
    
    Attributes:
        request_id: ID of the associated request
        status_code: HTTP status code (200, 404, etc.)
        headers: Response headers as key-value pairs
        body_preview: First 500 characters of response body
        content_length: Total size of response body in bytes
        response_time: Time taken to receive response in seconds
    """
    request_id: str
    status_code: int
    headers: Dict[str, str]
    body_preview: str
    content_length: int
    response_time: float
    
    def __post_init__(self):
        """Validate the response data after initialization."""
        self._validate()
    
    def _validate(self):
        """Validate response data fields."""
        if not self.request_id:
            raise ValueError("Request ID cannot be empty")
        
        if not (100 <= self.status_code <= 599):
            raise ValueError(f"Invalid HTTP status code: {self.status_code}")
        
        if self.content_length < 0:
            raise ValueError("Content length cannot be negative")
        
        if self.response_time < 0:
            raise ValueError("Response time cannot be negative")
        
        if len(self.body_preview) > 500:
            raise ValueError("Body preview should not exceed 500 characters")
    
    def is_success(self) -> bool:
        """Check if the response indicates success (2xx status)."""
        return 200 <= self.status_code < 300
    
    def is_client_error(self) -> bool:
        """Check if the response indicates client error (4xx status)."""
        return 400 <= self.status_code < 500
    
    def is_server_error(self) -> bool:
        """Check if the response indicates server error (5xx status)."""
        return 500 <= self.status_code < 600
    
    def is_error(self) -> bool:
        """Check if the response indicates any error (4xx or 5xx status)."""
        return self.is_client_error() or self.is_server_error()
    
    def is_auth_error(self) -> bool:
        """Check if the response indicates authentication error."""
        return self.status_code in (401, 407)
    
    def get_content_type(self) -> Optional[str]:
        """Get the content type from response headers."""
        # Check common header variations
        for header_name in ['content-type', 'Content-Type', 'CONTENT-TYPE']:
            if header_name in self.headers:
                return self.headers[header_name].split(';')[0].strip()
        return None
    
    def get_status_text(self) -> str:
        """Get human-readable status text for common status codes."""
        status_texts = {
            200: "OK",
            201: "Created", 
            204: "No Content",
            301: "Moved Permanently",
            302: "Found",
            304: "Not Modified",
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            407: "Proxy Authentication Required",
            408: "Request Timeout",
            500: "Internal Server Error",
            502: "Bad Gateway",
            503: "Service Unavailable",
            504: "Gateway Timeout"
        }
        return status_texts.get(self.status_code, "Unknown")
    
    def should_highlight_error(self) -> bool:
        """Check if this response should be highlighted as an error in UI."""
        return self.is_error()