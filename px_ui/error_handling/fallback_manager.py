"""
Fallback management system for graceful degradation.

This module provides fallback strategies for when primary operations fail,
ensuring the application continues to function with reduced capabilities.
"""

import logging
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union


class FallbackResult(Enum):
    """Result of a fallback attempt."""
    SUCCESS = "success"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


@dataclass
class FallbackAttempt:
    """Information about a fallback attempt."""
    strategy_name: str
    timestamp: datetime
    result: FallbackResult
    details: Optional[str] = None
    error: Optional[Exception] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class FallbackStrategy(ABC):
    """Base class for fallback strategies."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the fallback strategy."""
        pass
    
    @abstractmethod
    def can_fallback(self, context: Dict[str, Any]) -> bool:
        """Check if this strategy can be used for the given context."""
        pass
    
    @abstractmethod
    def execute_fallback(self, context: Dict[str, Any]) -> Any:
        """Execute the fallback strategy."""
        pass
    
    def get_priority(self) -> int:
        """Get priority of this strategy (lower number = higher priority)."""
        return 100


class DirectConnectionFallback(FallbackStrategy):
    """Fallback to direct connection when proxy fails."""
    
    @property
    def name(self) -> str:
        return "direct_connection"
    
    def can_fallback(self, context: Dict[str, Any]) -> bool:
        """Check if direct connection fallback is applicable."""
        return context.get('operation_type') == 'proxy_connection'
    
    def execute_fallback(self, context: Dict[str, Any]) -> Any:
        """Execute direct connection fallback."""
        # This would typically involve reconfiguring the proxy to use DIRECT
        # For now, we'll return a configuration that indicates direct connection
        return {
            'proxy_mode': 'direct',
            'proxy_decision': 'DIRECT',
            'fallback_reason': 'Proxy connection failed, falling back to direct connection'
        }
    
    def get_priority(self) -> int:
        return 10  # High priority for proxy failures


class DefaultPACFallback(FallbackStrategy):
    """Fallback to default PAC configuration when PAC loading fails."""
    
    def __init__(self, default_pac_content: Optional[str] = None):
        """
        Initialize with default PAC content.
        
        Args:
            default_pac_content: Default PAC content to use
        """
        self.default_pac_content = default_pac_content or self._get_minimal_pac()
    
    @property
    def name(self) -> str:
        return "default_pac"
    
    def can_fallback(self, context: Dict[str, Any]) -> bool:
        """Check if default PAC fallback is applicable."""
        return context.get('operation_type') == 'pac_loading'
    
    def execute_fallback(self, context: Dict[str, Any]) -> Any:
        """Execute default PAC fallback."""
        return {
            'pac_content': self.default_pac_content,
            'pac_source': 'fallback_default',
            'fallback_reason': 'PAC loading failed, using default configuration'
        }
    
    def get_priority(self) -> int:
        return 20  # Medium priority
    
    def _get_minimal_pac(self) -> str:
        """Get minimal PAC configuration that works."""
        return """
function FindProxyForURL(url, host) {
    // Fallback PAC: Direct connection for all requests
    return "DIRECT";
}
"""


class CachedConfigurationFallback(FallbackStrategy):
    """Fallback to cached/previous configuration when current config fails."""
    
    def __init__(self):
        """Initialize cached configuration fallback."""
        self._cached_configs: Dict[str, Any] = {}
        self._lock = threading.RLock()
    
    @property
    def name(self) -> str:
        return "cached_configuration"
    
    def can_fallback(self, context: Dict[str, Any]) -> bool:
        """Check if cached configuration fallback is applicable."""
        config_type = context.get('config_type')
        return config_type and self._has_cached_config(config_type)
    
    def execute_fallback(self, context: Dict[str, Any]) -> Any:
        """Execute cached configuration fallback."""
        config_type = context.get('config_type')
        cached_config = self._get_cached_config(config_type)
        
        if cached_config:
            return {
                'configuration': cached_config,
                'fallback_reason': f'Using cached {config_type} configuration'
            }
        else:
            raise RuntimeError(f"No cached configuration available for {config_type}")
    
    def get_priority(self) -> int:
        return 30  # Lower priority than direct fallbacks
    
    def cache_configuration(self, config_type: str, configuration: Any):
        """Cache a working configuration for future fallback."""
        with self._lock:
            self._cached_configs[config_type] = configuration
    
    def _has_cached_config(self, config_type: str) -> bool:
        """Check if we have a cached configuration of the given type."""
        with self._lock:
            return config_type in self._cached_configs
    
    def _get_cached_config(self, config_type: str) -> Optional[Any]:
        """Get cached configuration of the given type."""
        with self._lock:
            return self._cached_configs.get(config_type)


class NoProxyFallback(FallbackStrategy):
    """Fallback to no-proxy configuration when proxy fails."""
    
    @property
    def name(self) -> str:
        return "no_proxy"
    
    def can_fallback(self, context: Dict[str, Any]) -> bool:
        """Check if no-proxy fallback is applicable."""
        return context.get('operation_type') in ['proxy_connection', 'network_request']
    
    def execute_fallback(self, context: Dict[str, Any]) -> Any:
        """Execute no-proxy fallback."""
        # Get the target URL/host from context
        url = context.get('url', '')
        host = context.get('host', '')
        
        return {
            'proxy_decision': 'DIRECT',
            'no_proxy_hosts': [host] if host else [],
            'fallback_reason': f'Adding {host or url} to no-proxy list due to connection failure'
        }
    
    def get_priority(self) -> int:
        return 15  # High priority for network failures


class FallbackManager:
    """
    Manages fallback strategies for graceful degradation.
    
    Coordinates multiple fallback strategies and executes them in priority order
    when primary operations fail.
    """
    
    def __init__(self):
        """Initialize the fallback manager."""
        self.logger = logging.getLogger(__name__)
        self._strategies: List[FallbackStrategy] = []
        self._fallback_history: List[FallbackAttempt] = []
        self._lock = threading.RLock()
        
        # Configuration
        self.max_history_size = 500
        
        # Statistics
        self._stats = {
            'total_fallbacks': 0,
            'successful_fallbacks': 0,
            'fallbacks_by_strategy': {}
        }
        
        # Register default strategies
        self._register_default_strategies()
    
    def add_strategy(self, strategy: FallbackStrategy):
        """Add a fallback strategy."""
        with self._lock:
            self._strategies.append(strategy)
            self._strategies.sort(key=lambda s: s.get_priority())
            self.logger.info(f"Added fallback strategy: {strategy.name}")
    
    def remove_strategy(self, strategy: FallbackStrategy):
        """Remove a fallback strategy."""
        with self._lock:
            if strategy in self._strategies:
                self._strategies.remove(strategy)
                self.logger.info(f"Removed fallback strategy: {strategy.name}")
    
    def execute_fallback(self, context: Dict[str, Any]) -> Any:
        """
        Execute fallback strategies for the given context.
        
        Args:
            context: Context information for fallback decision
            
        Returns:
            Result from successful fallback strategy
            
        Raises:
            RuntimeError: If no fallback strategy succeeds
        """
        with self._lock:
            applicable_strategies = [
                strategy for strategy in self._strategies
                if strategy.can_fallback(context)
            ]
        
        if not applicable_strategies:
            self.logger.warning(f"No applicable fallback strategies for context: {context}")
            raise RuntimeError("No applicable fallback strategies available")
        
        self.logger.info(f"Attempting fallback with {len(applicable_strategies)} strategies")
        
        for strategy in applicable_strategies:
            attempt = FallbackAttempt(
                strategy_name=strategy.name,
                timestamp=datetime.now(),
                result=FallbackResult.FAILED
            )
            
            try:
                self.logger.debug(f"Trying fallback strategy: {strategy.name}")
                result = strategy.execute_fallback(context)
                
                # Success
                attempt.result = FallbackResult.SUCCESS
                attempt.details = f"Fallback successful with strategy {strategy.name}"
                
                with self._lock:
                    self._fallback_history.append(attempt)
                    self._cleanup_history()
                    self._update_stats(attempt)
                
                self.logger.info(f"Fallback successful with strategy: {strategy.name}")
                return result
                
            except Exception as e:
                attempt.result = FallbackResult.FAILED
                attempt.error = e
                attempt.details = f"Fallback failed: {str(e)}"
                
                with self._lock:
                    self._fallback_history.append(attempt)
                    self._update_stats(attempt)
                
                self.logger.warning(f"Fallback strategy {strategy.name} failed: {e}")
        
        # All strategies failed
        self.logger.error("All fallback strategies failed")
        raise RuntimeError("All fallback strategies failed")
    
    def try_fallback(self, context: Dict[str, Any]) -> Optional[Any]:
        """
        Try to execute fallback strategies, returning None if all fail.
        
        Args:
            context: Context information for fallback decision
            
        Returns:
            Result from successful fallback strategy, or None if all fail
        """
        try:
            return self.execute_fallback(context)
        except RuntimeError:
            return None
    
    def get_applicable_strategies(self, context: Dict[str, Any]) -> List[str]:
        """Get names of strategies applicable to the given context."""
        with self._lock:
            return [
                strategy.name for strategy in self._strategies
                if strategy.can_fallback(context)
            ]
    
    def get_fallback_history(self, strategy_name: Optional[str] = None) -> List[FallbackAttempt]:
        """Get fallback history, optionally filtered by strategy name."""
        with self._lock:
            history = self._fallback_history.copy()
        
        if strategy_name:
            history = [attempt for attempt in history if attempt.strategy_name == strategy_name]
        
        return history
    
    def get_stats(self) -> Dict[str, Any]:
        """Get fallback statistics."""
        with self._lock:
            return self._stats.copy()
    
    def clear_history(self):
        """Clear fallback history."""
        with self._lock:
            self._fallback_history.clear()
            self.logger.info("Fallback history cleared")
    
    def _register_default_strategies(self):
        """Register default fallback strategies."""
        self.add_strategy(DirectConnectionFallback())
        self.add_strategy(DefaultPACFallback())
        self.add_strategy(CachedConfigurationFallback())
        self.add_strategy(NoProxyFallback())
    
    def _update_stats(self, attempt: FallbackAttempt):
        """Update fallback statistics."""
        self._stats['total_fallbacks'] += 1
        
        if attempt.result == FallbackResult.SUCCESS:
            self._stats['successful_fallbacks'] += 1
        
        # Update strategy stats
        strategy_name = attempt.strategy_name
        if strategy_name not in self._stats['fallbacks_by_strategy']:
            self._stats['fallbacks_by_strategy'][strategy_name] = {
                'total': 0,
                'successful': 0
            }
        
        self._stats['fallbacks_by_strategy'][strategy_name]['total'] += 1
        if attempt.result == FallbackResult.SUCCESS:
            self._stats['fallbacks_by_strategy'][strategy_name]['successful'] += 1
    
    def _cleanup_history(self):
        """Clean up old fallback history entries."""
        if len(self._fallback_history) > self.max_history_size:
            self._fallback_history = self._fallback_history[-self.max_history_size:]


# Convenience functions for common fallback scenarios

def fallback_to_direct_connection(context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convenience function to fallback to direct connection."""
    manager = FallbackManager()
    fallback_context = context or {'operation_type': 'proxy_connection'}
    return manager.execute_fallback(fallback_context)


def fallback_to_default_pac(context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convenience function to fallback to default PAC."""
    manager = FallbackManager()
    fallback_context = context or {'operation_type': 'pac_loading'}
    return manager.execute_fallback(fallback_context)