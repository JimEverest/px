"""
Comprehensive error handling and recovery system for px UI client.

This package provides error handling, recovery mechanisms, and fallback strategies
for various failure scenarios in the proxy client application.
"""

from .error_manager import ErrorManager, ErrorSeverity, ErrorCategory, get_error_manager
from .retry_manager import RetryManager, RetryPolicy, ExponentialBackoff
from .fallback_manager import FallbackManager, FallbackStrategy
from .recovery_strategies import (
    PACRecoveryStrategy,
    NetworkRecoveryStrategy,
    ProxyRecoveryStrategy,
    ConfigurationRecoveryStrategy
)

__all__ = [
    'ErrorManager',
    'ErrorSeverity', 
    'ErrorCategory',
    'get_error_manager',
    'RetryManager',
    'RetryPolicy',
    'ExponentialBackoff',
    'FallbackManager',
    'FallbackStrategy',
    'PACRecoveryStrategy',
    'NetworkRecoveryStrategy',
    'ProxyRecoveryStrategy',
    'ConfigurationRecoveryStrategy'
]