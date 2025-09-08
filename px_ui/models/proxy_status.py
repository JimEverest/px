"""
Proxy status model for tracking proxy service state.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ProxyStatus:
    """
    Represents the current status of the proxy service.
    
    Attributes:
        is_running: Whether the proxy service is currently running
        listen_address: IP address the proxy is listening on
        port: Port number the proxy is listening on
        mode: Proxy mode ("manual", "pac", "auto")
        active_connections: Number of currently active connections
        total_requests: Total number of requests processed since start
    """
    is_running: bool
    listen_address: str
    port: int
    mode: str
    active_connections: int = 0
    total_requests: int = 0
    
    def __post_init__(self):
        """Validate the proxy status after initialization."""
        self._validate()
    
    def _validate(self):
        """Validate proxy status fields."""
        if not (1 <= self.port <= 65535):
            raise ValueError(f"Invalid port number: {self.port}. Must be between 1 and 65535")
        
        valid_modes = {'manual', 'pac', 'auto'}
        if self.mode not in valid_modes:
            raise ValueError(f"Invalid mode: {self.mode}. Must be one of {valid_modes}")
        
        if self.active_connections < 0:
            raise ValueError("Active connections cannot be negative")
        
        if self.total_requests < 0:
            raise ValueError("Total requests cannot be negative")
        
        # Basic IP address validation
        if not self._is_valid_ip_address(self.listen_address):
            raise ValueError(f"Invalid IP address: {self.listen_address}")
    
    def _is_valid_ip_address(self, ip: str) -> bool:
        """Basic IP address validation."""
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
    
    def get_listen_url(self) -> str:
        """Get the full URL where the proxy is listening."""
        return f"http://{self.listen_address}:{self.port}"
    
    def get_status_text(self) -> str:
        """Get human-readable status text."""
        if self.is_running:
            return f"Running on {self.listen_address}:{self.port}"
        else:
            return "Stopped"
    
    def get_mode_display_name(self) -> str:
        """Get display-friendly mode name."""
        mode_names = {
            'manual': 'Manual Configuration',
            'pac': 'PAC File',
            'auto': 'Auto-detect'
        }
        return mode_names.get(self.mode, self.mode.title())
    
    def is_localhost(self) -> bool:
        """Check if proxy is listening on localhost."""
        return self.listen_address in ('127.0.0.1', 'localhost')
    
    def is_using_pac(self) -> bool:
        """Check if proxy is using PAC configuration."""
        return self.mode == 'pac'
    
    def increment_request_count(self):
        """Increment the total request counter."""
        self.total_requests += 1
    
    def update_active_connections(self, count: int):
        """Update the active connections count."""
        if count < 0:
            raise ValueError("Active connections cannot be negative")
        self.active_connections = count
    
    def get_connection_info(self) -> str:
        """Get formatted connection information."""
        return f"{self.active_connections} active, {self.total_requests} total"