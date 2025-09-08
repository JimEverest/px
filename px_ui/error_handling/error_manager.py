"""
Central error management system for comprehensive error handling.

This module provides the ErrorManager class that coordinates error handling,
recovery attempts, and fallback strategies across the application.
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from enum import Enum, IntEnum
from typing import Dict, List, Optional, Callable, Any, Union
from dataclasses import dataclass


class ErrorSeverity(IntEnum):
    """Error severity levels."""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class ErrorCategory(Enum):
    """Error categories for classification."""
    PAC_VALIDATION = "pac_validation"
    PAC_LOADING = "pac_loading"
    NETWORK = "network"
    PROXY = "proxy"
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    SYSTEM = "system"
    UI = "ui"


@dataclass
class ErrorInfo:
    """Information about an error occurrence."""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    details: Optional[str] = None
    timestamp: datetime = None
    context: Optional[Dict[str, Any]] = None
    exception: Optional[Exception] = None
    recovery_attempted: bool = False
    recovery_successful: bool = False
    retry_count: int = 0
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()
        if self.context is None:
            self.context = {}


class ErrorHandler:
    """Base class for error handlers."""
    
    def can_handle(self, error: ErrorInfo) -> bool:
        """Check if this handler can handle the error."""
        raise NotImplementedError
    
    def handle(self, error: ErrorInfo) -> bool:
        """Handle the error. Returns True if handled successfully."""
        raise NotImplementedError


class ErrorManager:
    """
    Central error management system.
    
    Coordinates error handling, recovery attempts, and fallback strategies
    across the application.
    """
    
    def __init__(self):
        """Initialize the error manager."""
        self.logger = logging.getLogger(__name__)
        self._handlers: List[ErrorHandler] = []
        self._error_history: List[ErrorInfo] = []
        self._error_callbacks: List[Callable[[ErrorInfo], None]] = []
        self._lock = threading.RLock()
        
        # Configuration
        self.max_history_size = 1000
        self.max_retry_attempts = 3
        self.error_suppression_window = timedelta(minutes=5)
        self._suppressed_errors: Dict[str, datetime] = {}
        
        # Statistics
        self._stats = {
            'total_errors': 0,
            'errors_by_category': {},
            'errors_by_severity': {},
            'recovery_attempts': 0,
            'successful_recoveries': 0
        }
    
    def add_handler(self, handler: ErrorHandler):
        """Add an error handler."""
        with self._lock:
            self._handlers.append(handler)
            self.logger.info(f"Added error handler: {handler.__class__.__name__}")
    
    def remove_handler(self, handler: ErrorHandler):
        """Remove an error handler."""
        with self._lock:
            if handler in self._handlers:
                self._handlers.remove(handler)
                self.logger.info(f"Removed error handler: {handler.__class__.__name__}")
    
    def add_error_callback(self, callback: Callable[[ErrorInfo], None]):
        """Add callback to be notified of errors."""
        with self._lock:
            self._error_callbacks.append(callback)
    
    def remove_error_callback(self, callback: Callable[[ErrorInfo], None]):
        """Remove error callback."""
        with self._lock:
            if callback in self._error_callbacks:
                self._error_callbacks.remove(callback)
    
    def handle_error(self, 
                    category: ErrorCategory,
                    severity: ErrorSeverity,
                    message: str,
                    details: Optional[str] = None,
                    context: Optional[Dict[str, Any]] = None,
                    exception: Optional[Exception] = None) -> ErrorInfo:
        """
        Handle an error occurrence.
        
        Args:
            category: Error category
            severity: Error severity
            message: Error message
            details: Additional error details
            context: Error context information
            exception: Associated exception if any
            
        Returns:
            ErrorInfo object with handling results
        """
        import uuid
        
        # Create error info
        error = ErrorInfo(
            error_id=str(uuid.uuid4()),
            category=category,
            severity=severity,
            message=message,
            details=details,
            context=context or {},
            exception=exception
        )
        
        with self._lock:
            # Check for error suppression
            if self._should_suppress_error(error):
                self.logger.debug(f"Suppressing duplicate error: {message}")
                return error
            
            # Add to history
            self._error_history.append(error)
            self._cleanup_history()
            
            # Update statistics
            self._update_stats(error)
            
            # Log the error
            self._log_error(error)
            
            # Try to handle the error
            handled = self._try_handle_error(error)
            
            if not handled and severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
                self.logger.warning(f"Unhandled {severity.value} error: {message}")
            
            # Notify callbacks
            self._notify_callbacks(error)
            
            return error
    
    def handle_pac_error(self, message: str, details: Optional[str] = None, 
                        exception: Optional[Exception] = None) -> ErrorInfo:
        """Handle PAC-related errors."""
        return self.handle_error(
            category=ErrorCategory.PAC_VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            message=message,
            details=details,
            exception=exception
        )
    
    def handle_network_error(self, message: str, details: Optional[str] = None,
                           exception: Optional[Exception] = None) -> ErrorInfo:
        """Handle network-related errors."""
        return self.handle_error(
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            message=message,
            details=details,
            exception=exception
        )
    
    def handle_proxy_error(self, message: str, details: Optional[str] = None,
                          exception: Optional[Exception] = None) -> ErrorInfo:
        """Handle proxy-related errors."""
        return self.handle_error(
            category=ErrorCategory.PROXY,
            severity=ErrorSeverity.HIGH,
            message=message,
            details=details,
            exception=exception
        )
    
    def handle_configuration_error(self, message: str, details: Optional[str] = None,
                                 exception: Optional[Exception] = None) -> ErrorInfo:
        """Handle configuration-related errors."""
        return self.handle_error(
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.MEDIUM,
            message=message,
            details=details,
            exception=exception
        )
    
    def get_error_history(self, 
                         category: Optional[ErrorCategory] = None,
                         severity: Optional[ErrorSeverity] = None,
                         since: Optional[datetime] = None) -> List[ErrorInfo]:
        """Get error history with optional filtering."""
        with self._lock:
            errors = self._error_history.copy()
        
        # Apply filters
        if category:
            errors = [e for e in errors if e.category == category]
        
        if severity:
            errors = [e for e in errors if e.severity == severity]
        
        if since:
            errors = [e for e in errors if e.timestamp >= since]
        
        return errors
    
    def get_recent_errors(self, minutes: int = 60) -> List[ErrorInfo]:
        """Get errors from the last N minutes."""
        since = datetime.now() - timedelta(minutes=minutes)
        return self.get_error_history(since=since)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get error handling statistics."""
        with self._lock:
            return self._stats.copy()
    
    def clear_history(self):
        """Clear error history."""
        with self._lock:
            self._error_history.clear()
            self._suppressed_errors.clear()
            self.logger.info("Error history cleared")
    
    def _should_suppress_error(self, error: ErrorInfo) -> bool:
        """Check if error should be suppressed due to recent occurrence."""
        error_key = f"{error.category.value}:{error.message}"
        
        if error_key in self._suppressed_errors:
            last_occurrence = self._suppressed_errors[error_key]
            if datetime.now() - last_occurrence < self.error_suppression_window:
                return True
        
        self._suppressed_errors[error_key] = datetime.now()
        return False
    
    def _try_handle_error(self, error: ErrorInfo) -> bool:
        """Try to handle error with registered handlers."""
        for handler in self._handlers:
            try:
                if handler.can_handle(error):
                    self.logger.debug(f"Trying handler {handler.__class__.__name__} for error {error.error_id}")
                    
                    if handler.handle(error):
                        error.recovery_attempted = True
                        error.recovery_successful = True
                        self._stats['successful_recoveries'] += 1
                        self.logger.info(f"Error {error.error_id} handled successfully by {handler.__class__.__name__}")
                        return True
                    else:
                        error.recovery_attempted = True
                        self._stats['recovery_attempts'] += 1
                        self.logger.warning(f"Handler {handler.__class__.__name__} failed to handle error {error.error_id}")
            
            except Exception as e:
                self.logger.error(f"Error in handler {handler.__class__.__name__}: {e}")
        
        return False
    
    def _log_error(self, error: ErrorInfo):
        """Log error with appropriate level."""
        log_message = f"[{error.category.value.upper()}] {error.message}"
        if error.details:
            log_message += f" - {error.details}"
        
        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical(log_message, exc_info=error.exception)
        elif error.severity == ErrorSeverity.HIGH:
            self.logger.error(log_message, exc_info=error.exception)
        elif error.severity == ErrorSeverity.MEDIUM:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
    
    def _update_stats(self, error: ErrorInfo):
        """Update error statistics."""
        self._stats['total_errors'] += 1
        
        # Update category stats
        category_key = error.category.value
        if category_key not in self._stats['errors_by_category']:
            self._stats['errors_by_category'][category_key] = 0
        self._stats['errors_by_category'][category_key] += 1
        
        # Update severity stats
        severity_key = error.severity.value
        if severity_key not in self._stats['errors_by_severity']:
            self._stats['errors_by_severity'][severity_key] = 0
        self._stats['errors_by_severity'][severity_key] += 1
    
    def _notify_callbacks(self, error: ErrorInfo):
        """Notify error callbacks."""
        for callback in self._error_callbacks:
            try:
                callback(error)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")
    
    def _cleanup_history(self):
        """Clean up old error history entries."""
        if len(self._error_history) > self.max_history_size:
            # Keep only the most recent entries
            self._error_history = self._error_history[-self.max_history_size:]
        
        # Clean up old suppressed errors
        cutoff_time = datetime.now() - self.error_suppression_window
        self._suppressed_errors = {
            key: timestamp for key, timestamp in self._suppressed_errors.items()
            if timestamp > cutoff_time
        }


# Global error manager instance
_global_error_manager: Optional[ErrorManager] = None


def get_error_manager() -> ErrorManager:
    """Get the global error manager instance."""
    global _global_error_manager
    if _global_error_manager is None:
        _global_error_manager = ErrorManager()
    return _global_error_manager


def handle_error(category: ErrorCategory, severity: ErrorSeverity, message: str,
                details: Optional[str] = None, context: Optional[Dict[str, Any]] = None,
                exception: Optional[Exception] = None) -> ErrorInfo:
    """Convenience function to handle errors using global manager."""
    return get_error_manager().handle_error(
        category=category,
        severity=severity,
        message=message,
        details=details,
        context=context,
        exception=exception
    )