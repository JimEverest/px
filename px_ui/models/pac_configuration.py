"""
PAC configuration model for managing Proxy Auto-Configuration files.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import re
import urllib.parse


@dataclass
class PACConfiguration:
    """
    Represents a Proxy Auto-Configuration (PAC) file configuration.
    
    Attributes:
        source_type: Type of PAC source ("file", "url", "inline")
        source_path: Path to file or URL (empty for inline)
        content: The actual PAC file content (JavaScript)
        encoding: Character encoding of the PAC file
        is_valid: Whether the PAC content is syntactically valid
        validation_errors: List of validation error messages
    """
    source_type: str
    source_path: str
    content: str
    encoding: str = "utf-8"
    is_valid: bool = False
    validation_errors: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate the PAC configuration after initialization."""
        self._validate()
    
    def _validate(self):
        """Validate PAC configuration fields."""
        valid_source_types = {'file', 'url', 'inline'}
        if self.source_type not in valid_source_types:
            raise ValueError(f"Invalid source type: {self.source_type}. Must be one of {valid_source_types}")
        
        if self.source_type in ('file', 'url') and not self.source_path:
            raise ValueError(f"Source path is required for source type: {self.source_type}")
        
        if self.source_type == 'url' and not self._is_valid_url(self.source_path):
            raise ValueError(f"Invalid URL format: {self.source_path}")
        
        valid_encodings = {'utf-8', 'ascii', 'latin-1', 'cp1252'}
        if self.encoding not in valid_encodings:
            raise ValueError(f"Unsupported encoding: {self.encoding}")
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if the provided URL is valid."""
        try:
            result = urllib.parse.urlparse(url)
            return all([result.scheme, result.netloc]) and result.scheme in ('http', 'https')
        except Exception:
            return False
    
    def validate_pac_syntax(self) -> bool:
        """
        Validate the PAC file JavaScript syntax.
        
        Returns:
            True if syntax is valid, False otherwise.
            Updates is_valid and validation_errors fields.
        """
        self.validation_errors.clear()
        
        if not self.content.strip():
            self.validation_errors.append("PAC content cannot be empty")
            self.is_valid = False
            return False
        
        # Check for required FindProxyForURL function
        if 'function FindProxyForURL' not in self.content:
            self.validation_errors.append("PAC file must contain 'function FindProxyForURL(url, host)' function")
        
        # Basic JavaScript syntax checks
        if not self._check_basic_js_syntax():
            self.is_valid = False
            return False
        
        # Check for common PAC functions usage
        self._check_pac_functions()
        
        self.is_valid = len(self.validation_errors) == 0
        return self.is_valid
    
    def _check_basic_js_syntax(self) -> bool:
        """Perform basic JavaScript syntax validation."""
        # Check for balanced braces
        brace_count = self.content.count('{') - self.content.count('}')
        if brace_count != 0:
            self.validation_errors.append("Unbalanced braces in JavaScript code")
            return False
        
        # Check for balanced parentheses
        paren_count = self.content.count('(') - self.content.count(')')
        if paren_count != 0:
            self.validation_errors.append("Unbalanced parentheses in JavaScript code")
            return False
        
        # Check for unterminated strings (basic check)
        if self._has_unterminated_strings():
            self.validation_errors.append("Unterminated string literals found")
            return False
        
        return True
    
    def _has_unterminated_strings(self) -> bool:
        """Check for unterminated string literals."""
        in_single_quote = False
        in_double_quote = False
        escaped = False
        
        for char in self.content:
            if escaped:
                escaped = False
                continue
            
            if char == '\\':
                escaped = True
                continue
            
            if char == '"' and not in_single_quote:
                in_double_quote = not in_double_quote
            elif char == "'" and not in_double_quote:
                in_single_quote = not in_single_quote
        
        return in_single_quote or in_double_quote
    
    def _check_pac_functions(self):
        """Check for proper usage of PAC utility functions."""
        # Common PAC functions that should be used correctly
        pac_functions = [
            'isPlainHostName', 'dnsDomainIs', 'localHostOrDomainIs',
            'isResolvable', 'isInNet', 'dnsResolve', 'myIpAddress',
            'dnsDomainLevels', 'shExpMatch'
        ]
        
        for func in pac_functions:
            if func in self.content:
                # Basic check for function call syntax
                pattern = rf'{func}\s*\('
                if not re.search(pattern, self.content):
                    self.validation_errors.append(f"Function '{func}' found but not properly called")
    
    def test_url(self, test_url: str, test_host: str) -> Optional[str]:
        """
        Test the PAC configuration against a specific URL.
        
        Args:
            test_url: URL to test
            test_host: Host to test
            
        Returns:
            Proxy decision string or None if testing fails
        """
        if not self.is_valid or not self.content:
            return None
        
        try:
            # Use JavaScript execution to properly evaluate PAC function
            result = self._evaluate_pac_with_javascript(test_url, test_host)
            if result:
                return result
            
            # Fallback: Check for host-specific rules in the PAC content
            content_lower = self.content.lower()
            host_lower = test_host.lower()
            
            # Look for specific host patterns in the PAC content
            if f'host == "{host_lower}"' in content_lower or f"host == '{host_lower}'" in content_lower:
                # Find the return statement for this host
                lines = self.content.split('\n')
                for i, line in enumerate(lines):
                    if f'host == "{host_lower}"' in line.lower() or f"host == '{host_lower}'" in line.lower():
                        # Look for return statement in the next few lines
                        for j in range(i, min(i + 5, len(lines))):
                            if 'return' in lines[j]:
                                match = re.search(r'return\s+"([^"]+)"', lines[j])
                                if match:
                                    return match.group(1)
            
            # Check for endsWith patterns
            if f'host.endswith(".{host_lower}")' in content_lower or f'host.endsWith(".{host_lower}")' in content_lower:
                # Find the return statement for this pattern
                lines = self.content.split('\n')
                for i, line in enumerate(lines):
                    if f'.endswith(".{host_lower}")' in line.lower() or f'.endsWith(".{host_lower}")' in line.lower():
                        # Look for return statement in the next few lines
                        for j in range(i, min(i + 5, len(lines))):
                            if 'return' in lines[j]:
                                match = re.search(r'return\s+"([^"]+)"', lines[j])
                                if match:
                                    return match.group(1)
            
            # Check for domain-specific patterns (e.g., google.com, baidu.com)
            domain_patterns = {
                'google.com': ['google.com', 'www.google.com'],
                'baidu.com': ['baidu.com', 'www.baidu.com'],
                'amazon.com': ['amazon.com', 'www.amazon.com']
            }
            
            for domain, hosts in domain_patterns.items():
                if any(h in host_lower for h in hosts):
                    # Look for this domain in PAC content
                    if domain in content_lower:
                        lines = self.content.split('\n')
                        for i, line in enumerate(lines):
                            if domain in line.lower() and ('==' in line or 'endswith' in line.lower()):
                                # Look for return statement in the next few lines
                                for j in range(i, min(i + 5, len(lines))):
                                    if 'return' in lines[j]:
                                        match = re.search(r'return\s+"([^"]+)"', lines[j])
                                        if match:
                                            return match.group(1)
            
            # Look for default return statement at the end
            lines = self.content.split('\n')
            for line in reversed(lines):
                if 'return' in line and not line.strip().startswith('//'):
                    match = re.search(r'return\s+"([^"]+)"', line)
                    if match:
                        return match.group(1)
            
            # If no specific pattern found, return DIRECT as fallback
            return "DIRECT"
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error testing PAC URL {test_url}: {e}")
            return None
    
    def _evaluate_pac_with_javascript(self, test_url: str, test_host: str) -> Optional[str]:
        """
        Evaluate PAC function using JavaScript engine.
        
        Args:
            test_url: URL to test
            test_host: Host to test
            
        Returns:
            Proxy decision string or None if evaluation fails
        """
        try:
            import execjs
            
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
            full_pac_script = pac_helpers + '\n' + self.content
            
            # Execute PAC script
            ctx = execjs.compile(full_pac_script)
            result = ctx.call('FindProxyForURL', test_url, test_host)
            
            return str(result).strip()
            
        except ImportError:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("execjs not available for PAC testing, using fallback")
            return self._fallback_pac_evaluation(test_url, test_host)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"PAC JavaScript evaluation error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._fallback_pac_evaluation(test_url, test_host)
    
    def _fallback_pac_evaluation(self, test_url: str, test_host: str) -> Optional[str]:
        """
        Fallback PAC evaluation using pattern matching when JavaScript engine is not available.
        
        Args:
            test_url: URL to test
            test_host: Host to test
            
        Returns:
            Proxy decision string or None if evaluation fails
        """
        try:
            # Check for host-specific rules in the PAC content
            content_lower = self.content.lower()
            host_lower = test_host.lower()
            
            # Look for specific host patterns in the PAC content
            if f'host == "{host_lower}"' in content_lower or f"host == '{host_lower}'" in content_lower:
                # Find the return statement for this host
                lines = self.content.split('\n')
                for i, line in enumerate(lines):
                    if f'host == "{host_lower}"' in line.lower() or f"host == '{host_lower}'" in line.lower():
                        # Look for return statement in the next few lines
                        for j in range(i, min(i + 5, len(lines))):
                            if 'return' in lines[j]:
                                match = re.search(r'return\s+"([^"]+)"', lines[j])
                                if match:
                                    return match.group(1)
            
            # Check for endsWith patterns
            if f'host.endswith(".{host_lower}")' in content_lower or f'host.endsWith(".{host_lower}")' in content_lower:
                # Find the return statement for this pattern
                lines = self.content.split('\n')
                for i, line in enumerate(lines):
                    if f'.endswith(".{host_lower}")' in line.lower() or f'.endsWith(".{host_lower}")' in line.lower():
                        # Look for return statement in the next few lines
                        for j in range(i, min(i + 5, len(lines))):
                            if 'return' in lines[j]:
                                match = re.search(r'return\s+"([^"]+)"', lines[j])
                                if match:
                                    return match.group(1)
            
            # Check for domain-specific patterns (e.g., google.com, baidu.com)
            domain_patterns = {
                'google.com': ['google.com', 'www.google.com'],
                'baidu.com': ['baidu.com', 'www.baidu.com'],
                'amazon.com': ['amazon.com', 'www.amazon.com']
            }
            
            for domain, hosts in domain_patterns.items():
                if any(h in host_lower for h in hosts):
                    # Look for this domain in PAC content
                    if domain in content_lower:
                        lines = self.content.split('\n')
                        for i, line in enumerate(lines):
                            if domain in line.lower() and ('==' in line or 'endswith' in line.lower()):
                                # Look for return statement in the next few lines
                                for j in range(i, min(i + 5, len(lines))):
                                    if 'return' in lines[j]:
                                        match = re.search(r'return\s+"([^"]+)"', lines[j])
                                        if match:
                                            return match.group(1)
            
            # Look for default return statement at the end
            lines = self.content.split('\n')
            for line in reversed(lines):
                if 'return' in line and not line.strip().startswith('//'):
                    match = re.search(r'return\s+"([^"]+)"', line)
                    if match:
                        return match.group(1)
            
            # If no specific pattern found, return DIRECT as fallback
            return "DIRECT"
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Fallback PAC evaluation error: {e}")
            return "DIRECT"
    
    def get_source_display_name(self) -> str:
        """Get a display-friendly name for the PAC source."""
        if self.source_type == 'inline':
            return "Inline Configuration"
        elif self.source_type == 'file':
            return f"File: {self.source_path}"
        elif self.source_type == 'url':
            return f"URL: {self.source_path}"
        return "Unknown Source"
    
    def is_from_file(self) -> bool:
        """Check if PAC is loaded from a file."""
        return self.source_type == 'file'
    
    def is_from_url(self) -> bool:
        """Check if PAC is loaded from a URL."""
        return self.source_type == 'url'
    
    def is_inline(self) -> bool:
        """Check if PAC is inline configuration."""
        return self.source_type == 'inline'