"""
PAC file validation with comprehensive error handling and recovery.

This module provides PAC file validation capabilities with error handling,
automatic fixes for common issues, and fallback strategies.
"""

import logging
import re
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

from ..error_handling import (
    ErrorManager, ErrorCategory, ErrorSeverity, get_error_manager,
    RetryManager, FallbackManager,
    retry_on_network_error, retry_on_pac_error
)


class PACValidationResult:
    """Result of PAC validation with detailed information."""
    
    def __init__(self, is_valid: bool = False, errors: Optional[List[str]] = None,
                 warnings: Optional[List[str]] = None, fixed_content: Optional[str] = None):
        """
        Initialize validation result.
        
        Args:
            is_valid: Whether PAC content is valid
            errors: List of validation errors
            warnings: List of validation warnings
            fixed_content: Auto-fixed PAC content if applicable
        """
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
        self.fixed_content = fixed_content
        self.original_content: Optional[str] = None
        self.validation_details: Dict[str, Any] = {}


class PACValidator:
    """
    PAC file validator with error handling and recovery capabilities.
    
    Provides comprehensive PAC validation, automatic error fixing,
    and fallback strategies for PAC loading failures.
    """
    
    def __init__(self):
        """Initialize PAC validator."""
        self.logger = logging.getLogger(__name__)
        self.error_manager = get_error_manager()
        self.retry_manager = RetryManager()
        self.fallback_manager = FallbackManager()
        
        # Validation configuration
        self.enable_auto_fix = True
        self.enable_fallback = True
        self.download_timeout = 10
        self.max_pac_size = 1024 * 1024  # 1MB limit
    
    def validate_pac_content(self, pac_content: str, source: str = "inline") -> PACValidationResult:
        """
        Validate PAC content with comprehensive error handling.
        
        Args:
            pac_content: PAC file content to validate
            source: Source description for logging
            
        Returns:
            PACValidationResult with validation details
        """
        result = PACValidationResult()
        result.original_content = pac_content
        
        try:
            self.logger.debug(f"Validating PAC content from {source}")
            
            # Basic validation
            if not pac_content or not pac_content.strip():
                result.errors.append("PAC content is empty")
                self._handle_validation_error("Empty PAC content", source)
                return result
            
            # Size validation
            if len(pac_content) > self.max_pac_size:
                result.warnings.append(f"PAC content is large ({len(pac_content)} bytes)")
            
            # Syntax validation
            syntax_errors = self._validate_syntax(pac_content)
            result.errors.extend(syntax_errors)
            
            # Function validation
            function_errors = self._validate_functions(pac_content)
            result.errors.extend(function_errors)
            
            # Security validation
            security_warnings = self._validate_security(pac_content)
            result.warnings.extend(security_warnings)
            
            # Auto-fix if enabled and there are fixable errors
            if self.enable_auto_fix and result.errors:
                try:
                    fixed_content = self._attempt_auto_fix(pac_content, result.errors)
                    if fixed_content and fixed_content != pac_content:
                        # Re-validate fixed content
                        fixed_result = self._validate_fixed_content(fixed_content)
                        if fixed_result.is_valid:
                            result.fixed_content = fixed_content
                            result.warnings.append("PAC content was automatically fixed")
                            result.is_valid = True
                            self.logger.info(f"Successfully auto-fixed PAC content from {source}")
                        else:
                            result.warnings.append("Auto-fix attempted but validation still failed")
                except Exception as e:
                    result.warnings.append(f"Auto-fix failed: {str(e)}")
                    self.logger.warning(f"PAC auto-fix failed for {source}: {e}")
            
            # Set validation result
            if not result.errors:
                result.is_valid = True
                self.logger.debug(f"PAC validation successful for {source}")
            else:
                self.logger.warning(f"PAC validation failed for {source}: {result.errors}")
                self._handle_validation_error(f"PAC validation failed: {result.errors}", source)
            
            # Store validation details
            result.validation_details = {
                'source': source,
                'content_length': len(pac_content),
                'auto_fix_attempted': self.enable_auto_fix and bool(result.errors),
                'auto_fix_successful': bool(result.fixed_content)
            }
            
            return result
            
        except Exception as e:
            result.errors.append(f"Validation error: {str(e)}")
            self.logger.error(f"PAC validation exception for {source}: {e}")
            self._handle_validation_error(f"PAC validation exception: {str(e)}", source, e)
            return result
    
    def load_and_validate_pac_file(self, file_path: str) -> PACValidationResult:
        """
        Load and validate PAC file from local path.
        
        Args:
            file_path: Path to PAC file
            
        Returns:
            PACValidationResult with validation details
        """
        try:
            self.logger.info(f"Loading PAC file: {file_path}")
            
            # Load file with retry mechanism
            def load_file():
                path = Path(file_path)
                if not path.exists():
                    raise FileNotFoundError(f"PAC file not found: {file_path}")
                
                if path.stat().st_size > self.max_pac_size:
                    raise ValueError(f"PAC file too large: {path.stat().st_size} bytes")
                
                # Try different encodings
                for encoding in ['utf-8', 'latin-1', 'cp1252']:
                    try:
                        return path.read_text(encoding=encoding)
                    except UnicodeDecodeError:
                        continue
                
                # If all encodings fail, use utf-8 with error handling
                return path.read_text(encoding='utf-8', errors='replace')
            
            pac_content = retry_on_pac_error(load_file)
            return self.validate_pac_content(pac_content, f"file:{file_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to load PAC file {file_path}: {e}")
            self._handle_loading_error(f"Failed to load PAC file: {str(e)}", file_path, e)
            
            result = PACValidationResult()
            result.errors.append(f"Failed to load PAC file: {str(e)}")
            return result
    
    def load_and_validate_pac_url(self, url: str) -> PACValidationResult:
        """
        Load and validate PAC file from URL.
        
        Args:
            url: URL to PAC file
            
        Returns:
            PACValidationResult with validation details
        """
        try:
            self.logger.info(f"Loading PAC from URL: {url}")
            
            # Validate URL
            parsed_url = urlparse(url)
            if not parsed_url.scheme or not parsed_url.netloc:
                raise ValueError(f"Invalid PAC URL: {url}")
            
            # Download with retry mechanism
            def download_pac():
                request = Request(url, headers={
                    'User-Agent': 'px-ui-client/1.0',
                    'Accept': 'application/x-ns-proxy-autoconfig, text/plain, */*'
                })
                
                with urlopen(request, timeout=self.download_timeout) as response:
                    content = response.read()
                    
                    # Check content size
                    if len(content) > self.max_pac_size:
                        raise ValueError(f"PAC content too large: {len(content)} bytes")
                    
                    # Decode content
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
            
            pac_content = retry_on_network_error(download_pac)
            return self.validate_pac_content(pac_content, f"url:{url}")
            
        except Exception as e:
            self.logger.error(f"Failed to load PAC from URL {url}: {e}")
            self._handle_loading_error(f"Failed to load PAC from URL: {str(e)}", url, e)
            
            # Try fallback strategies
            if self.enable_fallback:
                try:
                    fallback_result = self.fallback_manager.try_fallback({
                        'operation_type': 'pac_loading',
                        'pac_source': url,
                        'error_type': 'network'
                    })
                    
                    if fallback_result and 'pac_content' in fallback_result:
                        self.logger.info(f"Using fallback PAC content for {url}")
                        return self.validate_pac_content(
                            fallback_result['pac_content'],
                            f"fallback:{url}"
                        )
                except Exception as fallback_error:
                    self.logger.warning(f"PAC fallback failed: {fallback_error}")
            
            result = PACValidationResult()
            result.errors.append(f"Failed to load PAC from URL: {str(e)}")
            return result
    
    def test_pac_function(self, pac_content: str, test_url: str, test_host: Optional[str] = None) -> Dict[str, Any]:
        """
        Test PAC function with a specific URL.
        
        Args:
            pac_content: PAC content to test
            test_url: URL to test
            test_host: Host to test (extracted from URL if not provided)
            
        Returns:
            Dictionary with test results
        """
        try:
            if not test_host:
                parsed_url = urlparse(test_url)
                test_host = parsed_url.netloc or parsed_url.hostname or test_url
            
            self.logger.debug(f"Testing PAC function with URL: {test_url}, Host: {test_host}")
            
            # For now, we'll do basic validation
            # In a full implementation, you might use a JavaScript engine like PyV8 or similar
            result = {
                'success': True,
                'proxy_decision': 'DIRECT',  # Default fallback
                'test_url': test_url,
                'test_host': test_host,
                'error': None,
                'details': 'PAC function test completed (basic validation)'
            }
            
            # Basic pattern matching for common PAC patterns
            if 'return "DIRECT"' in pac_content:
                result['proxy_decision'] = 'DIRECT'
            elif 'return "PROXY' in pac_content:
                # Try to extract proxy information
                proxy_match = re.search(r'return\s+"PROXY\s+([^"]+)"', pac_content)
                if proxy_match:
                    result['proxy_decision'] = f'PROXY {proxy_match.group(1)}'
                else:
                    result['proxy_decision'] = 'PROXY (unknown)'
            
            return result
            
        except Exception as e:
            self.logger.error(f"PAC function test failed: {e}")
            return {
                'success': False,
                'proxy_decision': 'DIRECT',
                'test_url': test_url,
                'test_host': test_host,
                'error': str(e),
                'details': f'PAC function test failed: {str(e)}'
            }
    
    def _validate_syntax(self, pac_content: str) -> List[str]:
        """Validate basic JavaScript syntax."""
        errors = []
        
        # Check for balanced parentheses and braces
        if pac_content.count('(') != pac_content.count(')'):
            errors.append("Mismatched parentheses in PAC content")
        
        if pac_content.count('{') != pac_content.count('}'):
            errors.append("Mismatched braces in PAC content")
        
        if pac_content.count('[') != pac_content.count(']'):
            errors.append("Mismatched brackets in PAC content")
        
        # Check for basic syntax issues
        if pac_content.count('"') % 2 != 0:
            errors.append("Unmatched quotes in PAC content")
        
        return errors
    
    def _validate_functions(self, pac_content: str) -> List[str]:
        """Validate required PAC functions."""
        errors = []
        
        # Check for required FindProxyForURL function
        if 'FindProxyForURL' not in pac_content:
            errors.append("PAC file must contain FindProxyForURL function")
        
        # Check function signature
        if not re.search(r'function\s+FindProxyForURL\s*\(\s*\w+\s*,\s*\w+\s*\)', pac_content):
            errors.append("FindProxyForURL function has invalid signature")
        
        return errors
    
    def _validate_security(self, pac_content: str) -> List[str]:
        """Validate PAC content for security issues."""
        warnings = []
        
        # Check for potentially dangerous functions
        dangerous_patterns = [
            r'eval\s*\(',
            r'Function\s*\(',
            r'setTimeout\s*\(',
            r'setInterval\s*\(',
            r'XMLHttpRequest',
            r'fetch\s*\('
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, pac_content, re.IGNORECASE):
                warnings.append(f"Potentially dangerous function detected: {pattern}")
        
        return warnings
    
    def _attempt_auto_fix(self, pac_content: str, errors: List[str]) -> Optional[str]:
        """Attempt to automatically fix common PAC errors."""
        fixed_content = pac_content
        
        try:
            # Fix missing FindProxyForURL function
            if "PAC file must contain FindProxyForURL function" in errors:
                if 'function FindProxyForURL' not in fixed_content:
                    # Add basic function if missing
                    fixed_content = f"""function FindProxyForURL(url, host) {{
    {fixed_content}
}}"""
            
            # Fix missing return statements
            if 'return' not in fixed_content.lower():
                # Add default return statement
                fixed_content = fixed_content.rstrip() + '\n    return "DIRECT";\n'
            
            # Fix missing semicolons
            fixed_content = re.sub(r'return\s+"([^"]+)"\s*(?!\;)', r'return "\1";', fixed_content)
            
            # Fix common variable name issues
            fixed_content = re.sub(r'\bURL\b', 'url', fixed_content)
            fixed_content = re.sub(r'\bHOST\b', 'host', fixed_content)
            
            return fixed_content if fixed_content != pac_content else None
            
        except Exception as e:
            self.logger.warning(f"Auto-fix attempt failed: {e}")
            return None
    
    def _validate_fixed_content(self, fixed_content: str) -> PACValidationResult:
        """Validate auto-fixed content."""
        result = PACValidationResult()
        
        # Basic validation of fixed content
        syntax_errors = self._validate_syntax(fixed_content)
        function_errors = self._validate_functions(fixed_content)
        
        result.errors.extend(syntax_errors)
        result.errors.extend(function_errors)
        result.is_valid = len(result.errors) == 0
        
        return result
    
    def _handle_validation_error(self, message: str, source: str, exception: Optional[Exception] = None):
        """Handle PAC validation errors."""
        self.error_manager.handle_error(
            category=ErrorCategory.PAC_VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            message=message,
            details=f"PAC source: {source}",
            context={
                'pac_source': source,
                'operation': 'validation'
            },
            exception=exception
        )
    
    def _handle_loading_error(self, message: str, source: str, exception: Optional[Exception] = None):
        """Handle PAC loading errors."""
        self.error_manager.handle_error(
            category=ErrorCategory.PAC_LOADING,
            severity=ErrorSeverity.HIGH,
            message=message,
            details=f"PAC source: {source}",
            context={
                'pac_source': source,
                'operation': 'loading'
            },
            exception=exception
        )