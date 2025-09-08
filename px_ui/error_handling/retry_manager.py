"""
Retry management system with exponential backoff and configurable policies.

This module provides retry mechanisms for handling transient failures
with various backoff strategies and retry policies.
"""

import asyncio
import logging
import random
import time
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Optional, Any, Dict, List, Union


class RetryResult(Enum):
    """Result of a retry attempt."""
    SUCCESS = "success"
    FAILED = "failed"
    EXHAUSTED = "exhausted"
    CANCELLED = "cancelled"


@dataclass
class RetryAttempt:
    """Information about a retry attempt."""
    attempt_number: int
    timestamp: datetime
    delay: float
    result: Optional[RetryResult] = None
    error: Optional[Exception] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class BackoffStrategy(ABC):
    """Base class for backoff strategies."""
    
    @abstractmethod
    def get_delay(self, attempt: int, base_delay: float = 1.0) -> float:
        """Get delay for the given attempt number."""
        pass


class ExponentialBackoff(BackoffStrategy):
    """Exponential backoff strategy with optional jitter."""
    
    def __init__(self, multiplier: float = 2.0, max_delay: float = 60.0, 
                 jitter: bool = True, jitter_factor: float = 0.1):
        """
        Initialize exponential backoff.
        
        Args:
            multiplier: Multiplier for each retry attempt
            max_delay: Maximum delay between attempts
            jitter: Whether to add random jitter
            jitter_factor: Factor for jitter calculation (0.0 to 1.0)
        """
        self.multiplier = multiplier
        self.max_delay = max_delay
        self.jitter = jitter
        self.jitter_factor = jitter_factor
    
    def get_delay(self, attempt: int, base_delay: float = 1.0) -> float:
        """Get exponential delay with optional jitter."""
        delay = base_delay * (self.multiplier ** (attempt - 1))
        delay = min(delay, self.max_delay)
        
        if self.jitter:
            jitter_amount = delay * self.jitter_factor
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(0.1, delay)  # Minimum delay of 0.1 seconds


class LinearBackoff(BackoffStrategy):
    """Linear backoff strategy."""
    
    def __init__(self, increment: float = 1.0, max_delay: float = 30.0):
        """
        Initialize linear backoff.
        
        Args:
            increment: Delay increment for each attempt
            max_delay: Maximum delay between attempts
        """
        self.increment = increment
        self.max_delay = max_delay
    
    def get_delay(self, attempt: int, base_delay: float = 1.0) -> float:
        """Get linear delay."""
        delay = base_delay + (self.increment * (attempt - 1))
        return min(delay, self.max_delay)


class FixedBackoff(BackoffStrategy):
    """Fixed delay backoff strategy."""
    
    def __init__(self, delay: float = 1.0):
        """
        Initialize fixed backoff.
        
        Args:
            delay: Fixed delay between attempts
        """
        self.delay = delay
    
    def get_delay(self, attempt: int, base_delay: float = 1.0) -> float:
        """Get fixed delay."""
        return self.delay


@dataclass
class RetryPolicy:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    backoff_strategy: BackoffStrategy = None
    timeout: Optional[float] = None
    retry_on_exceptions: Optional[List[type]] = None
    stop_on_exceptions: Optional[List[type]] = None
    
    def __post_init__(self):
        if self.backoff_strategy is None:
            self.backoff_strategy = ExponentialBackoff()
        if self.retry_on_exceptions is None:
            self.retry_on_exceptions = [Exception]
        if self.stop_on_exceptions is None:
            self.stop_on_exceptions = []


class RetryManager:
    """
    Manages retry operations with configurable policies and backoff strategies.
    """
    
    def __init__(self, default_policy: Optional[RetryPolicy] = None):
        """
        Initialize retry manager.
        
        Args:
            default_policy: Default retry policy to use
        """
        self.logger = logging.getLogger(__name__)
        self.default_policy = default_policy or RetryPolicy()
        self._active_retries: Dict[str, threading.Event] = {}
        self._retry_stats: Dict[str, List[RetryAttempt]] = {}
        self._lock = threading.RLock()
    
    def retry(self, 
             func: Callable[[], Any],
             policy: Optional[RetryPolicy] = None,
             operation_name: Optional[str] = None,
             context: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute function with retry logic.
        
        Args:
            func: Function to execute
            policy: Retry policy (uses default if None)
            operation_name: Name for logging and tracking
            context: Additional context for logging
            
        Returns:
            Result of successful function execution
            
        Raises:
            Exception: Last exception if all retries exhausted
        """
        policy = policy or self.default_policy
        operation_name = operation_name or func.__name__
        context = context or {}
        
        # Generate unique retry ID
        import uuid
        retry_id = str(uuid.uuid4())
        
        with self._lock:
            self._active_retries[retry_id] = threading.Event()
            self._retry_stats[retry_id] = []
        
        try:
            return self._execute_with_retry(func, policy, operation_name, retry_id, context)
        finally:
            with self._lock:
                self._active_retries.pop(retry_id, None)
                # Keep stats for a while for analysis
                # In production, you might want to clean these up periodically
    
    def retry_async(self,
                   func: Callable[[], Any],
                   callback: Optional[Callable[[Any, Optional[Exception]], None]] = None,
                   policy: Optional[RetryPolicy] = None,
                   operation_name: Optional[str] = None,
                   context: Optional[Dict[str, Any]] = None) -> str:
        """
        Execute function with retry logic asynchronously.
        
        Args:
            func: Function to execute
            callback: Callback to call with result or exception
            policy: Retry policy (uses default if None)
            operation_name: Name for logging and tracking
            context: Additional context for logging
            
        Returns:
            Retry ID for tracking/cancellation
        """
        import uuid
        retry_id = str(uuid.uuid4())
        
        def run_retry():
            try:
                result = self.retry(func, policy, operation_name, context)
                if callback:
                    callback(result, None)
            except Exception as e:
                if callback:
                    callback(None, e)
        
        thread = threading.Thread(target=run_retry, daemon=True)
        thread.start()
        
        return retry_id
    
    def cancel_retry(self, retry_id: str) -> bool:
        """
        Cancel an active retry operation.
        
        Args:
            retry_id: ID of retry to cancel
            
        Returns:
            True if retry was cancelled, False if not found
        """
        with self._lock:
            if retry_id in self._active_retries:
                self._active_retries[retry_id].set()
                return True
        return False
    
    def get_retry_stats(self, retry_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get retry statistics.
        
        Args:
            retry_id: Specific retry ID, or None for all stats
            
        Returns:
            Dictionary with retry statistics
        """
        with self._lock:
            if retry_id:
                attempts = self._retry_stats.get(retry_id, [])
                return {
                    'retry_id': retry_id,
                    'attempts': len(attempts),
                    'total_delay': sum(a.delay for a in attempts),
                    'success': any(a.result == RetryResult.SUCCESS for a in attempts),
                    'attempts_detail': attempts
                }
            else:
                total_retries = len(self._retry_stats)
                total_attempts = sum(len(attempts) for attempts in self._retry_stats.values())
                successful_retries = sum(
                    1 for attempts in self._retry_stats.values()
                    if any(a.result == RetryResult.SUCCESS for a in attempts)
                )
                
                return {
                    'total_retries': total_retries,
                    'total_attempts': total_attempts,
                    'successful_retries': successful_retries,
                    'success_rate': successful_retries / total_retries if total_retries > 0 else 0,
                    'active_retries': len(self._active_retries)
                }
    
    def _execute_with_retry(self, 
                           func: Callable[[], Any],
                           policy: RetryPolicy,
                           operation_name: str,
                           retry_id: str,
                           context: Dict[str, Any]) -> Any:
        """Execute function with retry logic."""
        last_exception = None
        start_time = time.time()
        
        for attempt in range(1, policy.max_attempts + 1):
            # Check for cancellation
            if retry_id in self._active_retries and self._active_retries[retry_id].is_set():
                self.logger.info(f"Retry {operation_name} cancelled at attempt {attempt}")
                raise RuntimeError(f"Retry operation {operation_name} was cancelled")
            
            # Check timeout
            if policy.timeout and (time.time() - start_time) > policy.timeout:
                self.logger.warning(f"Retry {operation_name} timed out after {time.time() - start_time:.2f}s")
                raise TimeoutError(f"Retry operation {operation_name} timed out")
            
            try:
                self.logger.debug(f"Attempting {operation_name} (attempt {attempt}/{policy.max_attempts})")
                
                # Record attempt
                attempt_info = RetryAttempt(
                    attempt_number=attempt,
                    timestamp=datetime.now(),
                    delay=0.0
                )
                
                # Execute function
                result = func()
                
                # Success
                attempt_info.result = RetryResult.SUCCESS
                with self._lock:
                    self._retry_stats[retry_id].append(attempt_info)
                
                if attempt > 1:
                    self.logger.info(f"Retry {operation_name} succeeded on attempt {attempt}")
                
                return result
                
            except Exception as e:
                last_exception = e
                attempt_info.result = RetryResult.FAILED
                attempt_info.error = e
                
                # Check if we should stop on this exception
                if any(isinstance(e, exc_type) for exc_type in policy.stop_on_exceptions):
                    self.logger.info(f"Stopping retry {operation_name} due to stop exception: {e}")
                    attempt_info.result = RetryResult.CANCELLED
                    with self._lock:
                        self._retry_stats[retry_id].append(attempt_info)
                    raise e
                
                # Check if we should retry on this exception
                if not any(isinstance(e, exc_type) for exc_type in policy.retry_on_exceptions):
                    self.logger.info(f"Not retrying {operation_name} due to non-retryable exception: {e}")
                    attempt_info.result = RetryResult.CANCELLED
                    with self._lock:
                        self._retry_stats[retry_id].append(attempt_info)
                    raise e
                
                # Calculate delay for next attempt
                if attempt < policy.max_attempts:
                    delay = policy.backoff_strategy.get_delay(attempt, policy.base_delay)
                    attempt_info.delay = delay
                    
                    self.logger.warning(f"Retry {operation_name} attempt {attempt} failed: {e}. "
                                      f"Retrying in {delay:.2f}s")
                    
                    with self._lock:
                        self._retry_stats[retry_id].append(attempt_info)
                    
                    # Wait with cancellation check
                    if self._wait_with_cancellation(retry_id, delay):
                        raise RuntimeError(f"Retry operation {operation_name} was cancelled")
                else:
                    # Last attempt failed
                    self.logger.error(f"Retry {operation_name} exhausted all {policy.max_attempts} attempts")
                    attempt_info.result = RetryResult.EXHAUSTED
                    with self._lock:
                        self._retry_stats[retry_id].append(attempt_info)
        
        # All attempts exhausted
        raise last_exception
    
    def _wait_with_cancellation(self, retry_id: str, delay: float) -> bool:
        """
        Wait for delay with cancellation support.
        
        Args:
            retry_id: Retry ID to check for cancellation
            delay: Delay in seconds
            
        Returns:
            True if cancelled, False if delay completed
        """
        if retry_id in self._active_retries:
            return self._active_retries[retry_id].wait(delay)
        else:
            time.sleep(delay)
            return False


# Convenience functions for common retry patterns

def retry_on_network_error(func: Callable[[], Any], 
                          max_attempts: int = 3,
                          base_delay: float = 1.0) -> Any:
    """Retry function on network-related errors."""
    import requests
    import urllib.error
    
    policy = RetryPolicy(
        max_attempts=max_attempts,
        base_delay=base_delay,
        backoff_strategy=ExponentialBackoff(multiplier=2.0, max_delay=30.0),
        retry_on_exceptions=[
            ConnectionError,
            TimeoutError,
            requests.exceptions.RequestException,
            urllib.error.URLError
        ]
    )
    
    manager = RetryManager()
    return manager.retry(func, policy, "network_operation")


def retry_on_pac_error(func: Callable[[], Any],
                      max_attempts: int = 2,
                      base_delay: float = 0.5) -> Any:
    """Retry function on PAC-related errors."""
    policy = RetryPolicy(
        max_attempts=max_attempts,
        base_delay=base_delay,
        backoff_strategy=FixedBackoff(delay=base_delay),
        retry_on_exceptions=[ValueError, SyntaxError, RuntimeError]
    )
    
    manager = RetryManager()
    return manager.retry(func, policy, "pac_operation")


def retry_on_proxy_error(func: Callable[[], Any],
                        max_attempts: int = 3,
                        base_delay: float = 2.0) -> Any:
    """Retry function on proxy-related errors."""
    policy = RetryPolicy(
        max_attempts=max_attempts,
        base_delay=base_delay,
        backoff_strategy=ExponentialBackoff(multiplier=1.5, max_delay=15.0),
        retry_on_exceptions=[ConnectionError, TimeoutError, OSError]
    )
    
    manager = RetryManager()
    return manager.retry(func, policy, "proxy_operation")