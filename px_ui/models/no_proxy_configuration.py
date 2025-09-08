"""
No proxy configuration data model.

This module defines the data structure for managing no proxy settings,
including support for wildcard patterns, IP ranges, and CIDR notation.
"""

import re
import ipaddress
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Union
from urllib.parse import urlparse


@dataclass
class NoProxyConfiguration:
    """
    Configuration for no proxy settings.
    
    Manages hosts and IP ranges that should bypass proxy settings,
    supporting various pattern formats including wildcards, IP ranges,
    and CIDR notation.
    """
    
    # List of no proxy patterns
    patterns: List[str] = field(default_factory=list)
    
    # Whether to bypass proxy for localhost
    bypass_localhost: bool = True
    
    # Whether to bypass proxy for private networks
    bypass_private_networks: bool = True
    
    # Validation state
    is_valid: bool = True
    validation_errors: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Initialize and validate configuration after creation."""
        self.logger = logging.getLogger(__name__)
        self.validate()
    
    def add_pattern(self, pattern: str) -> bool:
        """
        Add a no proxy pattern.
        
        Args:
            pattern: Pattern to add (hostname, IP, CIDR, wildcard)
            
        Returns:
            True if pattern was added successfully, False if invalid
        """
        pattern = pattern.strip()
        if not pattern:
            return False
        
        # Validate pattern before adding
        if self._validate_pattern(pattern):
            if pattern not in self.patterns:
                self.patterns.append(pattern)
                self.validate()
                return True
        
        return False
    
    def remove_pattern(self, pattern: str) -> bool:
        """
        Remove a no proxy pattern.
        
        Args:
            pattern: Pattern to remove
            
        Returns:
            True if pattern was removed, False if not found
        """
        if pattern in self.patterns:
            self.patterns.remove(pattern)
            self.validate()
            return True
        return False
    
    def clear_patterns(self):
        """Clear all no proxy patterns."""
        self.patterns.clear()
        self.validate()
    
    def should_bypass_proxy(self, url: str) -> bool:
        """
        Check if a URL should bypass the proxy.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL should bypass proxy, False otherwise
        """
        try:
            # Parse URL to extract host
            parsed = urlparse(url if url.startswith(('http://', 'https://')) else f'http://{url}')
            host = parsed.hostname or parsed.netloc
            
            if not host:
                return False
            
            # Check localhost bypass
            if self.bypass_localhost and self._is_localhost(host):
                return True
            
            # Check private network bypass
            if self.bypass_private_networks and self._is_private_network(host):
                return True
            
            # Check against patterns
            return self._matches_patterns(host)
            
        except Exception as e:
            self.logger.error(f"Error checking bypass for {url}: {e}")
            return False
    
    def _matches_patterns(self, host: str) -> bool:
        """Check if host matches any no proxy patterns."""
        for pattern in self.patterns:
            if self._match_pattern(host, pattern):
                return True
        return False
    
    def _match_pattern(self, host: str, pattern: str) -> bool:
        """
        Check if host matches a specific pattern.
        
        Supports:
        - Exact hostname matching
        - Wildcard patterns (*.example.com)
        - IP addresses
        - CIDR notation (192.168.1.0/24)
        - IP ranges (192.168.1.1-192.168.1.100)
        """
        try:
            # Exact match
            if host.lower() == pattern.lower():
                return True
            
            # Wildcard pattern matching
            if '*' in pattern:
                return self._match_wildcard(host, pattern)
            
            # IP address or CIDR matching
            if self._is_ip_pattern(pattern):
                return self._match_ip_pattern(host, pattern)
            
            # Domain suffix matching (implicit wildcard)
            if pattern.startswith('.'):
                return host.lower().endswith(pattern.lower())
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error matching {host} against {pattern}: {e}")
            return False
    
    def _match_wildcard(self, host: str, pattern: str) -> bool:
        """Match host against wildcard pattern."""
        # Convert wildcard pattern to regex
        regex_pattern = pattern.replace('.', r'\.').replace('*', '.*')
        regex_pattern = f'^{regex_pattern}$'
        
        try:
            return bool(re.match(regex_pattern, host, re.IGNORECASE))
        except re.error:
            return False
    
    def _is_ip_pattern(self, pattern: str) -> bool:
        """Check if pattern is an IP-related pattern."""
        # Check for CIDR notation
        if '/' in pattern:
            return True
        
        # Check for IP range
        if '-' in pattern:
            return True
        
        # Check for single IP address
        try:
            ipaddress.ip_address(pattern)
            return True
        except ValueError:
            return False
    
    def _match_ip_pattern(self, host: str, pattern: str) -> bool:
        """Match host against IP pattern (CIDR, range, or single IP)."""
        try:
            # Convert host to IP if possible
            host_ip = ipaddress.ip_address(host)
        except ValueError:
            # Host is not an IP address
            return False
        
        try:
            # CIDR notation
            if '/' in pattern:
                network = ipaddress.ip_network(pattern, strict=False)
                return host_ip in network
            
            # IP range (e.g., 192.168.1.1-192.168.1.100)
            if '-' in pattern:
                start_ip, end_ip = pattern.split('-', 1)
                start_ip = ipaddress.ip_address(start_ip.strip())
                end_ip = ipaddress.ip_address(end_ip.strip())
                return start_ip <= host_ip <= end_ip
            
            # Single IP address
            pattern_ip = ipaddress.ip_address(pattern)
            return host_ip == pattern_ip
            
        except ValueError as e:
            self.logger.error(f"Invalid IP pattern {pattern}: {e}")
            return False
    
    def _is_localhost(self, host: str) -> bool:
        """Check if host is localhost."""
        localhost_patterns = [
            'localhost',
            '127.0.0.1',
            '::1',
            '0.0.0.0'
        ]
        
        return host.lower() in localhost_patterns
    
    def _is_private_network(self, host: str) -> bool:
        """Check if host is in a private network."""
        try:
            ip = ipaddress.ip_address(host)
            # Exclude localhost addresses from private network check
            if ip.is_loopback:
                return False
            return ip.is_private
        except ValueError:
            # Not an IP address, check for private domain patterns
            private_domains = ['.local', '.internal', '.corp', '.lan']
            return any(host.lower().endswith(domain) for domain in private_domains)
    
    def validate(self) -> bool:
        """
        Validate the no proxy configuration.
        
        Returns:
            True if configuration is valid, False otherwise
        """
        self.validation_errors.clear()
        
        try:
            # Validate each pattern
            for pattern in self.patterns:
                if not self._validate_pattern(pattern):
                    self.validation_errors.append(f"Invalid pattern: {pattern}")
            
            # Check for duplicate patterns
            if len(self.patterns) != len(set(self.patterns)):
                self.validation_errors.append("Duplicate patterns found")
            
            self.is_valid = len(self.validation_errors) == 0
            return self.is_valid
            
        except Exception as e:
            self.validation_errors.append(f"Validation error: {str(e)}")
            self.is_valid = False
            return False
    
    def _validate_pattern(self, pattern: str) -> bool:
        """Validate a single no proxy pattern."""
        if not pattern or not pattern.strip():
            return False
        
        pattern = pattern.strip()
        
        try:
            # Check for invalid characters
            invalid_chars = ['<', '>', '"', '|', '\\', '^', '`', '{', '}']
            if any(char in pattern for char in invalid_chars):
                return False
            
            # Validate wildcard patterns
            if '*' in pattern:
                return self._validate_wildcard_pattern(pattern)
            
            # Validate IP patterns
            if self._is_ip_pattern(pattern):
                return self._validate_ip_pattern(pattern)
            
            # Validate hostname patterns
            return self._validate_hostname_pattern(pattern)
            
        except Exception:
            return False
    
    def _validate_wildcard_pattern(self, pattern: str) -> bool:
        """Validate wildcard pattern."""
        # Basic wildcard validation
        if pattern.count('*') > 3:  # Reasonable limit
            return False
        
        # Check for valid wildcard placement
        if pattern.startswith('*.'):
            return self._validate_hostname_pattern(pattern[2:])
        
        if pattern.endswith('.*'):
            return self._validate_hostname_pattern(pattern[:-2])
        
        # Allow patterns like *.example.*
        return True
    
    def _validate_ip_pattern(self, pattern: str) -> bool:
        """Validate IP-related pattern."""
        try:
            # CIDR notation
            if '/' in pattern:
                ipaddress.ip_network(pattern, strict=False)
                return True
            
            # IP range
            if '-' in pattern:
                start_ip, end_ip = pattern.split('-', 1)
                start = ipaddress.ip_address(start_ip.strip())
                end = ipaddress.ip_address(end_ip.strip())
                return start <= end
            
            # Single IP
            ipaddress.ip_address(pattern)
            return True
            
        except ValueError:
            return False
    
    def _validate_hostname_pattern(self, pattern: str) -> bool:
        """Validate hostname pattern."""
        if not pattern:
            return False
        
        # Remove leading dot for domain suffix patterns
        original_pattern = pattern
        if pattern.startswith('.'):
            pattern = pattern[1:]
        
        # Check if this looks like an invalid IP address
        # If it has 4 numeric parts separated by dots, treat it as an IP
        if not original_pattern.startswith('.'):
            parts = pattern.split('.')
            if len(parts) == 4 and all(part.isdigit() for part in parts):
                # This looks like an IP address, validate it as such
                try:
                    ipaddress.ip_address(pattern)
                    return True  # Valid IP
                except ValueError:
                    return False  # Invalid IP
        
        # Basic hostname validation
        if len(pattern) > 253:
            return False
        
        # Check each label
        labels = pattern.split('.')
        for label in labels:
            if not label or len(label) > 63:
                return False
            
            # Check for valid characters
            if not re.match(r'^[a-zA-Z0-9-]+$', label):
                return False
            
            # Cannot start or end with hyphen
            if label.startswith('-') or label.endswith('-'):
                return False
        
        return True
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            'patterns': self.patterns.copy(),
            'bypass_localhost': self.bypass_localhost,
            'bypass_private_networks': self.bypass_private_networks,
            'is_valid': self.is_valid,
            'validation_errors': self.validation_errors.copy()
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'NoProxyConfiguration':
        """Create configuration from dictionary."""
        config = cls(
            patterns=data.get('patterns', []),
            bypass_localhost=data.get('bypass_localhost', True),
            bypass_private_networks=data.get('bypass_private_networks', True)
        )
        return config
    
    def to_px_format(self) -> str:
        """
        Convert configuration to px-compatible format.
        
        Returns:
            Comma-separated string of no proxy patterns
        """
        all_patterns = []
        
        # Add localhost patterns if enabled
        if self.bypass_localhost:
            all_patterns.extend(['localhost', '127.0.0.1', '::1'])
        
        # Add private network patterns if enabled
        if self.bypass_private_networks:
            all_patterns.extend([
                '10.0.0.0/8',
                '172.16.0.0/12', 
                '192.168.0.0/16',
                '169.254.0.0/16',  # Link-local
                'fc00::/7'  # IPv6 private
            ])
        
        # Add custom patterns
        all_patterns.extend(self.patterns)
        
        return ','.join(all_patterns)
    
    @classmethod
    def from_px_format(cls, no_proxy_string: str) -> 'NoProxyConfiguration':
        """
        Create configuration from px-compatible format.
        
        Args:
            no_proxy_string: Comma-separated string of patterns
            
        Returns:
            NoProxyConfiguration instance
        """
        if not no_proxy_string:
            return cls()
        
        patterns = [p.strip() for p in no_proxy_string.split(',') if p.strip()]
        
        # Separate built-in patterns from custom ones
        localhost_patterns = {'localhost', '127.0.0.1', '::1'}
        private_patterns = {
            '10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16',
            '169.254.0.0/16', 'fc00::/7'
        }
        
        custom_patterns = []
        bypass_localhost = False
        bypass_private_networks = False
        
        for pattern in patterns:
            if pattern in localhost_patterns:
                bypass_localhost = True
            elif pattern in private_patterns:
                bypass_private_networks = True
            else:
                custom_patterns.append(pattern)
        
        return cls(
            patterns=custom_patterns,
            bypass_localhost=bypass_localhost,
            bypass_private_networks=bypass_private_networks
        )
    
    def get_pattern_count(self) -> int:
        """Get total number of effective patterns."""
        count = len(self.patterns)
        
        if self.bypass_localhost:
            count += 3  # localhost, 127.0.0.1, ::1
        
        if self.bypass_private_networks:
            count += 5  # Private network ranges
        
        return count
    
    def get_summary(self) -> str:
        """Get a summary description of the configuration."""
        parts = []
        
        if self.bypass_localhost:
            parts.append("localhost")
        
        if self.bypass_private_networks:
            parts.append("private networks")
        
        if self.patterns:
            parts.append(f"{len(self.patterns)} custom pattern(s)")
        
        if not parts:
            return "No bypass patterns configured"
        
        return f"Bypass: {', '.join(parts)}"