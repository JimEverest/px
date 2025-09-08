"""
Error handling integration for UI components.

This module provides centralized error handling integration across all UI components,
including error highlighting, status indicators, and recovery coordination.
"""

import tkinter as tk
from tkinter import ttk
import logging
import threading
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta

from px_ui.error_handling.error_manager import (
    ErrorManager, ErrorInfo, ErrorSeverity, ErrorCategory, get_error_manager
)
from px_ui.error_handling.retry_manager import RetryManager, RetryPolicy
from px_ui.error_handling.fallback_manager import FallbackManager
from px_ui.ui.error_dialogs import (
    show_error_with_recovery, show_simple_error, RecoveryOption, ErrorStatusIndicator
)


class UIErrorHandler:
    """Handles errors for a specific UI component."""
    
    def __init__(self, component_name: str, parent_widget: tk.Widget):
        """
        Initialize UI error handler.
        
        Args:
            component_name: Name of the UI component
            parent_widget: Parent widget for error dialogs
        """
        self.component_name = component_name
        self.parent_widget = parent_widget
        self.logger = logging.getLogger(f"{__name__}.{component_name}")
        
        # Error state tracking
        self.current_errors: Dict[str, ErrorInfo] = {}
        self.error_indicators: Dict[str, ErrorStatusIndicator] = {}
        self.highlighted_widgets: List[tk.Widget] = []
        
        # Recovery callbacks
        self.recovery_callbacks: Dict[str, Callable[[], bool]] = {}
    
    def handle_error(self, category: ErrorCategory, severity: ErrorSeverity,
                    message: str, details: Optional[str] = None,
                    context: Optional[Dict[str, Any]] = None,
                    show_dialog: bool = True,
                    highlight_widget: Optional[tk.Widget] = None) -> ErrorInfo:
        """
        Handle an error in this UI component.
        
        Args:
            category: Error category
            severity: Error severity
            message: Error message
            details: Additional details
            context: Error context
            show_dialog: Whether to show error dialog
            highlight_widget: Widget to highlight for error
            
        Returns:
            ErrorInfo object
        """
        # Add component context
        if context is None:
            context = {}
        context['component'] = self.component_name
        
        # Handle error through error manager
        error_manager = get_error_manager()
        error_info = error_manager.handle_error(
            category=category,
            severity=severity,
            message=message,
            details=details,
            context=context
        )
        
        # Store current error
        self.current_errors[error_info.error_id] = error_info
        
        # Highlight widget if specified
        if highlight_widget:
            self._highlight_widget_error(highlight_widget, severity)
        
        # Show dialog for high/critical errors or if explicitly requested
        if show_dialog and severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            self._show_error_dialog(error_info)
        
        # Update error indicators
        self._update_error_indicators()
        
        return error_info
    
    def clear_error(self, error_id: str):
        """Clear a specific error."""
        if error_id in self.current_errors:
            del self.current_errors[error_id]
            self._update_error_indicators()
            self.logger.debug(f"Cleared error {error_id}")
    
    def clear_all_errors(self):
        """Clear all errors for this component."""
        self.current_errors.clear()
        self._clear_all_highlights()
        self._update_error_indicators()
        self.logger.debug(f"Cleared all errors for {self.component_name}")
    
    def add_recovery_callback(self, error_type: str, callback: Callable[[], bool]):
        """Add a recovery callback for a specific error type."""
        self.recovery_callbacks[error_type] = callback
    
    def create_status_indicator(self, parent: tk.Widget) -> ErrorStatusIndicator:
        """Create and register a status indicator."""
        indicator = ErrorStatusIndicator(parent)
        indicator_id = f"indicator_{len(self.error_indicators)}"
        self.error_indicators[indicator_id] = indicator
        self._update_error_indicators()
        return indicator
    
    def _highlight_widget_error(self, widget: tk.Widget, severity: ErrorSeverity):
        """Highlight a widget to indicate error state."""
        try:
            # Store original style
            if not hasattr(widget, '_original_style'):
                if isinstance(widget, ttk.Widget):
                    widget._original_style = widget.cget('style') if widget.cget('style') else None
                else:
                    widget._original_style = {
                        'bg': widget.cget('bg') if 'bg' in widget.keys() else None,
                        'fg': widget.cget('fg') if 'fg' in widget.keys() else None
                    }
            
            # Apply error highlighting
            if isinstance(widget, ttk.Widget):
                # For ttk widgets, we'll use a custom style
                style_name = f"Error.{widget.winfo_class()}"
                style = ttk.Style()
                
                if severity == ErrorSeverity.CRITICAL:
                    style.configure(style_name, fieldbackground='#ffebee', bordercolor='red')
                elif severity == ErrorSeverity.HIGH:
                    style.configure(style_name, fieldbackground='#fff3e0', bordercolor='orange')
                else:
                    style.configure(style_name, fieldbackground='#f3e5f5', bordercolor='purple')
                
                widget.configure(style=style_name)
            else:
                # For tk widgets, change background directly
                if severity == ErrorSeverity.CRITICAL:
                    widget.configure(bg='#ffebee')
                elif severity == ErrorSeverity.HIGH:
                    widget.configure(bg='#fff3e0')
                else:
                    widget.configure(bg='#f3e5f5')
            
            # Track highlighted widget
            if widget not in self.highlighted_widgets:
                self.highlighted_widgets.append(widget)
            
            # Schedule highlight removal
            self.parent_widget.after(5000, lambda: self._remove_widget_highlight(widget))
            
        except Exception as e:
            self.logger.error(f"Failed to highlight widget: {e}")
    
    def _remove_widget_highlight(self, widget: tk.Widget):
        """Remove error highlighting from a widget."""
        try:
            if hasattr(widget, '_original_style'):
                if isinstance(widget, ttk.Widget):
                    original_style = widget._original_style
                    if original_style:
                        widget.configure(style=original_style)
                    else:
                        widget.configure(style='')
                else:
                    original_style = widget._original_style
                    if original_style.get('bg'):
                        widget.configure(bg=original_style['bg'])
                    if original_style.get('fg'):
                        widget.configure(fg=original_style['fg'])
                
                delattr(widget, '_original_style')
            
            # Remove from tracked widgets
            if widget in self.highlighted_widgets:
                self.highlighted_widgets.remove(widget)
                
        except Exception as e:
            self.logger.error(f"Failed to remove widget highlight: {e}")
    
    def _clear_all_highlights(self):
        """Clear all widget highlights."""
        for widget in self.highlighted_widgets.copy():
            self._remove_widget_highlight(widget)
    
    def _show_error_dialog(self, error_info: ErrorInfo):
        """Show error dialog with recovery options."""
        try:
            # Create recovery options based on error category
            recovery_options = self._create_recovery_options(error_info)
            
            if recovery_options:
                # Show dialog with recovery options
                result = show_error_with_recovery(
                    self.parent_widget,
                    error_info,
                    recovery_options
                )
                
                if result and result.startswith("recovery:"):
                    self.logger.info(f"User selected recovery: {result}")
            else:
                # Show simple error dialog
                show_simple_error(
                    self.parent_widget,
                    error_info.message,
                    self._get_dialog_title(error_info),
                    error_info.details
                )
        
        except Exception as e:
            self.logger.error(f"Failed to show error dialog: {e}")
    
    def _create_recovery_options(self, error_info: ErrorInfo) -> List[RecoveryOption]:
        """Create recovery options for an error."""
        options = []
        
        # Add component-specific recovery options
        error_key = f"{error_info.category.value}_{self.component_name}"
        if error_key in self.recovery_callbacks:
            options.append(RecoveryOption(
                label="Retry Operation",
                callback=self.recovery_callbacks[error_key],
                description="Retry the failed operation",
                is_default=True
            ))
        
        # Add category-specific recovery options
        if error_info.category == ErrorCategory.PAC_VALIDATION:
            options.extend([
                RecoveryOption(
                    label="Use Default PAC",
                    callback=lambda: self._trigger_fallback("default_pac"),
                    description="Fall back to default PAC configuration"
                ),
                RecoveryOption(
                    label="Clear PAC Configuration",
                    callback=lambda: self._clear_pac_config(),
                    description="Clear current PAC and use direct connection"
                )
            ])
        
        elif error_info.category == ErrorCategory.NETWORK:
            options.extend([
                RecoveryOption(
                    label="Use Direct Connection",
                    callback=lambda: self._trigger_fallback("direct_connection"),
                    description="Bypass proxy for this connection",
                    is_default=True
                ),
                RecoveryOption(
                    label="Retry with Proxy",
                    callback=lambda: self._retry_network_operation(error_info),
                    description="Retry the network operation"
                )
            ])
        
        elif error_info.category == ErrorCategory.PROXY:
            options.extend([
                RecoveryOption(
                    label="Restart Proxy Service",
                    callback=lambda: self._restart_proxy(),
                    description="Stop and restart the proxy service",
                    is_default=True
                ),
                RecoveryOption(
                    label="Check Configuration",
                    callback=lambda: self._open_configuration(),
                    description="Open configuration for review"
                )
            ])
        
        return options
    
    def _get_dialog_title(self, error_info: ErrorInfo) -> str:
        """Get appropriate dialog title for error."""
        if error_info.severity == ErrorSeverity.CRITICAL:
            return f"Critical Error - {self.component_name}"
        elif error_info.severity == ErrorSeverity.HIGH:
            return f"Error - {self.component_name}"
        elif error_info.severity == ErrorSeverity.MEDIUM:
            return f"Warning - {self.component_name}"
        else:
            return f"Information - {self.component_name}"
    
    def _update_error_indicators(self):
        """Update all error status indicators."""
        # Determine overall status
        if not self.current_errors:
            status = "ok"
            message = "No errors"
        else:
            # Find highest severity error
            max_severity = max(error.severity for error in self.current_errors.values())
            error_count = len(self.current_errors)
            
            if max_severity == ErrorSeverity.CRITICAL:
                status = "critical"
                message = f"{error_count} critical error(s)"
            elif max_severity == ErrorSeverity.HIGH:
                status = "error"
                message = f"{error_count} error(s)"
            elif max_severity == ErrorSeverity.MEDIUM:
                status = "warning"
                message = f"{error_count} warning(s)"
            else:
                status = "ok"
                message = f"{error_count} info message(s)"
        
        # Update all indicators
        for indicator in self.error_indicators.values():
            try:
                indicator.set_status(status, message)
            except Exception as e:
                self.logger.error(f"Failed to update error indicator: {e}")
    
    def _trigger_fallback(self, fallback_type: str) -> bool:
        """Trigger a fallback strategy."""
        try:
            fallback_manager = FallbackManager()
            context = {
                'operation_type': fallback_type,
                'component': self.component_name
            }
            
            result = fallback_manager.try_fallback(context)
            return result is not None
        
        except Exception as e:
            self.logger.error(f"Fallback {fallback_type} failed: {e}")
            return False
    
    def _clear_pac_config(self) -> bool:
        """Clear PAC configuration (placeholder)."""
        # This would be implemented by the specific component
        self.logger.info("PAC configuration cleared (placeholder)")
        return True
    
    def _retry_network_operation(self, error_info: ErrorInfo) -> bool:
        """Retry network operation (placeholder)."""
        # This would be implemented by the specific component
        self.logger.info("Network operation retried (placeholder)")
        return True
    
    def _restart_proxy(self) -> bool:
        """Restart proxy service (placeholder)."""
        # This would be implemented by the main window
        self.logger.info("Proxy service restart requested (placeholder)")
        return True
    
    def _open_configuration(self) -> bool:
        """Open configuration dialog (placeholder)."""
        # This would be implemented by the main window
        self.logger.info("Configuration dialog opened (placeholder)")
        return True


class ErrorIntegrationManager:
    """
    Manages error handling integration across all UI components.
    
    Coordinates error handling, recovery, and user notifications
    across the entire application.
    """
    
    def __init__(self, main_window):
        """
        Initialize error integration manager.
        
        Args:
            main_window: Main application window
        """
        self.main_window = main_window
        self.logger = logging.getLogger(__name__)
        
        # Component error handlers
        self.component_handlers: Dict[str, UIErrorHandler] = {}
        
        # Global error tracking
        self.global_error_count = 0
        self.last_error_time = None
        
        # Error suppression (to avoid spam)
        self.error_suppression_window = timedelta(seconds=30)
        self.suppressed_errors: Dict[str, datetime] = {}
        
        # Initialize error manager callback
        self._setup_error_manager_integration()
        
        # Create global status indicator
        self.global_status_indicator = None
        
        self.logger.info("Error integration manager initialized")
    
    def register_component(self, component_name: str, parent_widget: tk.Widget) -> UIErrorHandler:
        """
        Register a UI component for error handling.
        
        Args:
            component_name: Name of the component
            parent_widget: Parent widget for error dialogs
            
        Returns:
            UIErrorHandler for the component
        """
        handler = UIErrorHandler(component_name, parent_widget)
        self.component_handlers[component_name] = handler
        
        self.logger.info(f"Registered error handler for component: {component_name}")
        return handler
    
    def get_component_handler(self, component_name: str) -> Optional[UIErrorHandler]:
        """Get error handler for a component."""
        return self.component_handlers.get(component_name)
    
    def handle_global_error(self, category: ErrorCategory, severity: ErrorSeverity,
                          message: str, details: Optional[str] = None,
                          context: Optional[Dict[str, Any]] = None,
                          component: Optional[str] = None) -> ErrorInfo:
        """
        Handle a global application error.
        
        Args:
            category: Error category
            severity: Error severity
            message: Error message
            details: Additional details
            context: Error context
            component: Component that triggered the error
            
        Returns:
            ErrorInfo object
        """
        # Add global context
        if context is None:
            context = {}
        context['global'] = True
        if component:
            context['source_component'] = component
        
        # Handle through error manager
        error_manager = get_error_manager()
        error_info = error_manager.handle_error(
            category=category,
            severity=severity,
            message=message,
            details=details,
            context=context
        )
        
        # Update global tracking
        self.global_error_count += 1
        self.last_error_time = datetime.now()
        
        # Show global error dialog for critical errors
        if severity == ErrorSeverity.CRITICAL:
            self._show_global_error_dialog(error_info)
        
        # Update global status
        self._update_global_status()
        
        return error_info
    
    def create_global_status_indicator(self, parent: tk.Widget) -> ErrorStatusIndicator:
        """Create global status indicator."""
        self.global_status_indicator = ErrorStatusIndicator(parent)
        self._update_global_status()
        return self.global_status_indicator
    
    def setup_component_recovery_callbacks(self):
        """Set up recovery callbacks for all components."""
        # PAC Configuration recovery
        pac_handler = self.get_component_handler("pac_config")
        if pac_handler:
            pac_handler.add_recovery_callback(
                "pac_validation_pac_config",
                self._recover_pac_configuration
            )
        
        # Monitoring View recovery
        monitoring_handler = self.get_component_handler("monitoring")
        if monitoring_handler:
            monitoring_handler.add_recovery_callback(
                "network_monitoring",
                self._recover_monitoring_connection
            )
        
        # Proxy Controller recovery
        proxy_handler = self.get_component_handler("proxy_controller")
        if proxy_handler:
            proxy_handler.add_recovery_callback(
                "proxy_proxy_controller",
                self._recover_proxy_service
            )
    
    def _setup_error_manager_integration(self):
        """Set up integration with the global error manager."""
        error_manager = get_error_manager()
        error_manager.add_error_callback(self._on_error_manager_callback)
    
    def _on_error_manager_callback(self, error_info: ErrorInfo):
        """Handle callbacks from the error manager."""
        # Check if this is a UI-related error that needs special handling
        component = error_info.context.get('component') if error_info.context else None
        
        if component and component in self.component_handlers:
            # Let the component handler deal with it
            return
        
        # Handle global errors
        if error_info.severity in [ErrorSeverity.HIGH, ErrorSeverity.CRITICAL]:
            # Check for error suppression
            error_key = f"{error_info.category.value}:{error_info.message}"
            if not self._should_suppress_error(error_key):
                self._show_global_error_notification(error_info)
    
    def _should_suppress_error(self, error_key: str) -> bool:
        """Check if error should be suppressed."""
        if error_key in self.suppressed_errors:
            last_time = self.suppressed_errors[error_key]
            if datetime.now() - last_time < self.error_suppression_window:
                return True
        
        self.suppressed_errors[error_key] = datetime.now()
        return False
    
    def _show_global_error_dialog(self, error_info: ErrorInfo):
        """Show global error dialog."""
        try:
            recovery_options = [
                RecoveryOption(
                    label="Continue",
                    callback=lambda: True,
                    description="Continue with current operation",
                    is_default=True
                ),
                RecoveryOption(
                    label="Restart Application",
                    callback=self._restart_application,
                    description="Restart the entire application"
                )
            ]
            
            show_error_with_recovery(
                self.main_window.root,
                error_info,
                recovery_options
            )
        
        except Exception as e:
            self.logger.error(f"Failed to show global error dialog: {e}")
    
    def _show_global_error_notification(self, error_info: ErrorInfo):
        """Show a non-blocking error notification."""
        try:
            # For now, just log the error
            # In a full implementation, this could show a toast notification
            self.logger.warning(f"Global error notification: {error_info.message}")
        
        except Exception as e:
            self.logger.error(f"Failed to show error notification: {e}")
    
    def _update_global_status(self):
        """Update global status indicator."""
        if not self.global_status_indicator:
            return
        
        try:
            # Get error statistics from all components
            total_errors = sum(
                len(handler.current_errors) 
                for handler in self.component_handlers.values()
            )
            
            if total_errors == 0:
                self.global_status_indicator.set_status("ok", "All systems operational")
            else:
                # Find highest severity across all components
                max_severity = ErrorSeverity.LOW
                for handler in self.component_handlers.values():
                    if handler.current_errors:
                        component_max = max(error.severity for error in handler.current_errors.values())
                        if component_max.value > max_severity.value:
                            max_severity = component_max
                
                if max_severity == ErrorSeverity.CRITICAL:
                    status = "critical"
                    message = f"{total_errors} critical error(s)"
                elif max_severity == ErrorSeverity.HIGH:
                    status = "error"
                    message = f"{total_errors} error(s)"
                elif max_severity == ErrorSeverity.MEDIUM:
                    status = "warning"
                    message = f"{total_errors} warning(s)"
                else:
                    status = "ok"
                    message = f"{total_errors} info message(s)"
                
                self.global_status_indicator.set_status(status, message)
        
        except Exception as e:
            self.logger.error(f"Failed to update global status: {e}")
    
    def _recover_pac_configuration(self) -> bool:
        """Recover PAC configuration."""
        try:
            # Get PAC panel and trigger fallback
            pac_panel = getattr(self.main_window, 'pac_config_panel', None)
            if pac_panel:
                # This would trigger a fallback to default PAC
                self.logger.info("Recovering PAC configuration")
                return True
        except Exception as e:
            self.logger.error(f"Failed to recover PAC configuration: {e}")
        return False
    
    def _recover_monitoring_connection(self) -> bool:
        """Recover monitoring connection."""
        try:
            # This would restart the monitoring connection
            self.logger.info("Recovering monitoring connection")
            return True
        except Exception as e:
            self.logger.error(f"Failed to recover monitoring connection: {e}")
        return False
    
    def _recover_proxy_service(self) -> bool:
        """Recover proxy service."""
        try:
            # This would restart the proxy service
            if hasattr(self.main_window, 'stop_proxy_callback') and hasattr(self.main_window, 'start_proxy_callback'):
                self.logger.info("Recovering proxy service")
                # Stop and restart proxy
                if self.main_window.stop_proxy_callback:
                    self.main_window.stop_proxy_callback()
                if self.main_window.start_proxy_callback:
                    # Get current config and restart
                    config = self.main_window._get_proxy_configuration()
                    return self.main_window.start_proxy_callback(config)
        except Exception as e:
            self.logger.error(f"Failed to recover proxy service: {e}")
        return False
    
    def _restart_application(self) -> bool:
        """Restart the entire application."""
        try:
            self.logger.info("Restarting application")
            # This would trigger application restart
            # For now, just close the application
            self.main_window._on_window_close()
            return True
        except Exception as e:
            self.logger.error(f"Failed to restart application: {e}")
        return False
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of all errors across components."""
        summary = {
            'total_errors': 0,
            'by_severity': {severity.value: 0 for severity in ErrorSeverity},
            'by_category': {category.value: 0 for category in ErrorCategory},
            'by_component': {},
            'recent_errors': []
        }
        
        # Collect errors from all components
        all_errors = []
        for component_name, handler in self.component_handlers.items():
            component_errors = list(handler.current_errors.values())
            all_errors.extend(component_errors)
            
            summary['by_component'][component_name] = len(component_errors)
            
            for error in component_errors:
                summary['by_severity'][error.severity.value] += 1
                summary['by_category'][error.category.value] += 1
        
        summary['total_errors'] = len(all_errors)
        
        # Get recent errors (last 10)
        recent_errors = sorted(all_errors, key=lambda x: x.timestamp, reverse=True)[:10]
        summary['recent_errors'] = [
            {
                'message': error.message,
                'severity': error.severity.value,
                'category': error.category.value,
                'timestamp': error.timestamp.isoformat(),
                'component': error.context.get('component', 'unknown') if error.context else 'unknown'
            }
            for error in recent_errors
        ]
        
        return summary