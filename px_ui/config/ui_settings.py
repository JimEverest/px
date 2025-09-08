"""
UI settings data model for storing user preferences.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import json


@dataclass
class UISettings:
    """
    Represents user interface settings and preferences.
    
    Attributes:
        window_geometry: Window size and position (width, height, x, y)
        monitoring_filters: Default filters for request monitoring
        pac_editor_font_size: Font size for PAC editor
        auto_scroll_monitoring: Whether to auto-scroll monitoring view
        max_log_entries: Maximum number of log entries to keep
        theme: UI theme preference
        proxy_port: Default proxy port
        proxy_address: Default proxy listen address
        enable_logging: Whether to enable request logging
        log_response_bodies: Whether to log response body content
    """
    window_geometry: tuple[int, int, int, int] = (800, 600, 100, 100)  # width, height, x, y
    monitoring_filters: Dict[str, Any] = field(default_factory=dict)
    pac_editor_font_size: int = 12
    auto_scroll_monitoring: bool = True
    max_log_entries: int = 1000
    theme: str = "default"
    proxy_port: int = 3128
    proxy_address: str = "127.0.0.1"
    enable_logging: bool = True
    log_response_bodies: bool = True
    
    def __post_init__(self):
        """Validate settings after initialization."""
        self._validate()
    
    def _validate(self):
        """Validate UI settings."""
        # Validate window geometry
        width, height, x, y = self.window_geometry
        if width < 400 or height < 300:
            raise ValueError("Window size too small (minimum 400x300)")
        
        if width > 3840 or height > 2160:
            raise ValueError("Window size too large (maximum 3840x2160)")
        
        # Validate font size
        if not (8 <= self.pac_editor_font_size <= 24):
            raise ValueError("Font size must be between 8 and 24")
        
        # Validate max log entries
        if not (100 <= self.max_log_entries <= 10000):
            raise ValueError("Max log entries must be between 100 and 10000")
        
        # Validate proxy port
        if not (1 <= self.proxy_port <= 65535):
            raise ValueError("Proxy port must be between 1 and 65535")
        
        # Validate theme
        valid_themes = {"default", "dark", "light"}
        if self.theme not in valid_themes:
            raise ValueError(f"Invalid theme: {self.theme}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary for serialization."""
        return {
            'window_geometry': list(self.window_geometry),
            'monitoring_filters': self.monitoring_filters,
            'pac_editor_font_size': self.pac_editor_font_size,
            'auto_scroll_monitoring': self.auto_scroll_monitoring,
            'max_log_entries': self.max_log_entries,
            'theme': self.theme,
            'proxy_port': self.proxy_port,
            'proxy_address': self.proxy_address,
            'enable_logging': self.enable_logging,
            'log_response_bodies': self.log_response_bodies
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UISettings':
        """Create settings from dictionary."""
        # Convert window geometry back to tuple
        if 'window_geometry' in data and isinstance(data['window_geometry'], list):
            data['window_geometry'] = tuple(data['window_geometry'])
        
        # Filter out unknown keys
        known_keys = {
            'window_geometry', 'monitoring_filters', 'pac_editor_font_size',
            'auto_scroll_monitoring', 'max_log_entries', 'theme',
            'proxy_port', 'proxy_address', 'enable_logging', 'log_response_bodies'
        }
        filtered_data = {k: v for k, v in data.items() if k in known_keys}
        
        return cls(**filtered_data)
    
    def to_json(self) -> str:
        """Convert settings to JSON string."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'UISettings':
        """Create settings from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def update_window_geometry(self, width: int, height: int, x: int, y: int):
        """Update window geometry settings."""
        self.window_geometry = (width, height, x, y)
        self._validate()
    
    def set_monitoring_filter(self, filter_name: str, filter_value: Any):
        """Set a monitoring filter value."""
        self.monitoring_filters[filter_name] = filter_value
    
    def get_monitoring_filter(self, filter_name: str, default: Any = None) -> Any:
        """Get a monitoring filter value."""
        return self.monitoring_filters.get(filter_name, default)
    
    def clear_monitoring_filters(self):
        """Clear all monitoring filters."""
        self.monitoring_filters.clear()
    
    def get_proxy_url(self) -> str:
        """Get the proxy URL based on current settings."""
        return f"http://{self.proxy_address}:{self.proxy_port}"