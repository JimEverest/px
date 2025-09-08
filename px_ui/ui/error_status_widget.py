"""
Error status widget for displaying error states and indicators throughout the UI.

This module provides various error status widgets that can be embedded in
different UI components to show error states, warnings, and status information.
"""

import tkinter as tk
from tkinter import ttk
import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from enum import Enum

from px_ui.error_handling.error_manager import ErrorInfo, ErrorSeverity, ErrorCategory, get_error_manager
from px_ui.ui.error_dialogs import show_error_with_recovery, RecoveryOption


class StatusLevel(Enum):
    """Status levels for error indicators."""
    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ErrorStatusWidget(ttk.Frame):
    """
    Comprehensive error status widget with multiple display modes.
    
    Can display error status as:
    - Status indicator with colored dot
    - Status bar with text and icon
    - Detailed status panel with error list
    """
    
    def __init__(self, parent, mode: str = "indicator", **kwargs):
        """
        Initialize error status widget.
        
        Args:
            parent: Parent widget
            mode: Display mode ("indicator", "bar", "panel")
        """
        super().__init__(parent, **kwargs)
        
        self.logger = logging.getLogger(__name__)
        self.mode = mode
        
        # Error tracking
        self.current_errors: List[ErrorInfo] = []
        self.error_counts: Dict[str, int] = {
            'critical': 0,
            'high': 0,
            'medium': 0,
            'low': 0
        }
        
        # UI components
        self.status_canvas = None
        self.status_label = None
        self.error_listbox = None
        self.details_button = None
        
        # Callbacks
        self.on_status_click: Optional[Callable] = None
        self.on_error_select: Optional[Callable[[ErrorInfo], None]] = None
        
        # Create UI based on mode
        self._create_ui()
        
        # Set up error manager callback
        error_manager = get_error_manager()
        error_manager.add_error_callback(self._on_error_occurred)
        
        # Initialize with OK status
        self._update_display()
    
    def _create_ui(self):
        """Create UI components based on display mode."""
        if self.mode == "indicator":
            self._create_indicator_ui()
        elif self.mode == "bar":
            self._create_bar_ui()
        elif self.mode == "panel":
            self._create_panel_ui()
        else:
            raise ValueError(f"Unknown display mode: {self.mode}")
    
    def _create_indicator_ui(self):
        """Create simple status indicator UI."""
        # Status indicator (colored circle)
        self.status_canvas = tk.Canvas(self, width=16, height=16, highlightthickness=0)
        self.status_canvas.pack(side="left", padx=(0, 5))
        
        # Status text
        self.status_label = ttk.Label(self, text="OK")
        self.status_label.pack(side="left")
        
        # Make clickable
        self.status_canvas.bind("<Button-1>", self._on_click)
        self.status_label.bind("<Button-1>", self._on_click)
        
        # Add tooltip
        self._create_tooltip()
    
    def _create_bar_ui(self):
        """Create status bar UI."""
        # Configure frame
        self.grid_columnconfigure(1, weight=1)
        
        # Status icon
        self.status_canvas = tk.Canvas(self, width=20, height=20, highlightthickness=0)
        self.status_canvas.grid(row=0, column=0, padx=(0, 8))
        
        # Status text
        self.status_label = ttk.Label(self, text="System OK - No errors")
        self.status_label.grid(row=0, column=1, sticky="w")
        
        # Details button
        self.details_button = ttk.Button(
            self, 
            text="Details", 
            command=self._show_error_details,
            state="disabled"
        )
        self.details_button.grid(row=0, column=2, padx=(8, 0))
        
        # Make status clickable
        self.status_canvas.bind("<Button-1>", self._on_click)
        self.status_label.bind("<Button-1>", self._on_click)
    
    def _create_panel_ui(self):
        """Create detailed status panel UI."""
        # Configure frame
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Header with status
        header_frame = ttk.Frame(self)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Status icon
        self.status_canvas = tk.Canvas(header_frame, width=24, height=24, highlightthickness=0)
        self.status_canvas.grid(row=0, column=0, padx=(0, 10))
        
        # Status text
        self.status_label = ttk.Label(header_frame, text="System Status: OK", font=("Arial", 10, "bold"))
        self.status_label.grid(row=0, column=1, sticky="w")
        
        # Error counts
        self.counts_label = ttk.Label(header_frame, text="", font=("Arial", 8))
        self.counts_label.grid(row=1, column=1, sticky="w", pady=(2, 0))
        
        # Error list
        list_frame = ttk.LabelFrame(self, text="Recent Errors", padding=5)
        list_frame.grid(row=1, column=0, sticky="nsew")
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Listbox with scrollbar
        list_container = ttk.Frame(list_frame)
        list_container.grid(row=0, column=0, sticky="nsew")
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)
        
        self.error_listbox = tk.Listbox(list_container, height=6)
        self.error_listbox.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.error_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.error_listbox.config(yscrollcommand=scrollbar.set)
        
        # Bind selection
        self.error_listbox.bind("<<ListboxSelect>>", self._on_error_select)
        self.error_listbox.bind("<Double-Button-1>", self._on_error_double_click)
        
        # Action buttons
        button_frame = ttk.Frame(self)
        button_frame.grid(row=2, column=0, sticky="ew", pady=(5, 0))
        
        ttk.Button(button_frame, text="Clear All", command=self._clear_all_errors).pack(side="left")
        ttk.Button(button_frame, text="Export Report", command=self._export_error_report).pack(side="left", padx=(5, 0))
        ttk.Button(button_frame, text="Refresh", command=self._refresh_errors).pack(side="right")
    
    def _on_error_occurred(self, error_info: ErrorInfo):
        """Handle error occurrence from error manager."""
        # Add to current errors (keep last 50)
        self.current_errors.append(error_info)
        if len(self.current_errors) > 50:
            self.current_errors = self.current_errors[-50:]
        
        # Update counts
        severity_key = error_info.severity.value
        if severity_key in self.error_counts:
            self.error_counts[severity_key] += 1
        
        # Update display
        self._update_display()
    
    def _update_display(self):
        """Update the display based on current error state."""
        # Determine overall status
        status_level = self._get_current_status_level()
        status_color = self._get_status_color(status_level)
        status_text = self._get_status_text(status_level)
        
        # Update status indicator
        if self.status_canvas:
            self._draw_status_indicator(status_color)
        
        # Update status text
        if self.status_label:
            self.status_label.config(text=status_text)
        
        # Update mode-specific elements
        if self.mode == "bar":
            self._update_bar_display(status_level)
        elif self.mode == "panel":
            self._update_panel_display(status_level)
    
    def _get_current_status_level(self) -> StatusLevel:
        """Determine current status level based on errors."""
        if self.error_counts['critical'] > 0:
            return StatusLevel.CRITICAL
        elif self.error_counts['high'] > 0:
            return StatusLevel.ERROR
        elif self.error_counts['medium'] > 0:
            return StatusLevel.WARNING
        elif self.error_counts['low'] > 0:
            return StatusLevel.INFO
        else:
            return StatusLevel.OK
    
    def _get_status_color(self, status_level: StatusLevel) -> str:
        """Get color for status level."""
        colors = {
            StatusLevel.OK: "#28a745",      # Green
            StatusLevel.INFO: "#17a2b8",    # Blue
            StatusLevel.WARNING: "#ffc107", # Yellow
            StatusLevel.ERROR: "#dc3545",   # Red
            StatusLevel.CRITICAL: "#6f42c1" # Purple
        }
        return colors.get(status_level, "#6c757d")  # Default gray
    
    def _get_status_text(self, status_level: StatusLevel) -> str:
        """Get status text for status level."""
        if status_level == StatusLevel.OK:
            return "OK"
        elif status_level == StatusLevel.INFO:
            return f"Info ({self.error_counts['low']})"
        elif status_level == StatusLevel.WARNING:
            return f"Warning ({self.error_counts['medium']})"
        elif status_level == StatusLevel.ERROR:
            return f"Error ({self.error_counts['high']})"
        elif status_level == StatusLevel.CRITICAL:
            return f"Critical ({self.error_counts['critical']})"
        else:
            return "Unknown"
    
    def _draw_status_indicator(self, color: str):
        """Draw status indicator on canvas."""
        if not self.status_canvas:
            return
        
        # Clear canvas
        self.status_canvas.delete("all")
        
        # Get canvas size
        width = self.status_canvas.winfo_reqwidth()
        height = self.status_canvas.winfo_reqheight()
        
        # Draw circle
        margin = 2
        self.status_canvas.create_oval(
            margin, margin, 
            width - margin, height - margin,
            fill=color, outline=color
        )
    
    def _update_bar_display(self, status_level: StatusLevel):
        """Update status bar display."""
        # Update details button state
        if self.details_button:
            if status_level != StatusLevel.OK:
                self.details_button.config(state="normal")
            else:
                self.details_button.config(state="disabled")
        
        # Update status text with more detail
        if self.status_label:
            if status_level == StatusLevel.OK:
                text = "System OK - No errors"
            else:
                total_errors = sum(self.error_counts.values())
                text = f"System Status: {status_level.value.title()} - {total_errors} error(s)"
            
            self.status_label.config(text=text)
    
    def _update_panel_display(self, status_level: StatusLevel):
        """Update status panel display."""
        # Update counts label
        if self.counts_label:
            counts_text = f"Critical: {self.error_counts['critical']}, " \
                         f"High: {self.error_counts['high']}, " \
                         f"Medium: {self.error_counts['medium']}, " \
                         f"Low: {self.error_counts['low']}"
            self.counts_label.config(text=counts_text)
        
        # Update error list
        if self.error_listbox:
            self.error_listbox.delete(0, tk.END)
            
            # Show recent errors (last 20)
            recent_errors = sorted(self.current_errors, key=lambda x: x.timestamp, reverse=True)[:20]
            
            for error in recent_errors:
                timestamp = error.timestamp.strftime("%H:%M:%S")
                severity_icon = self._get_severity_icon(error.severity)
                text = f"{timestamp} {severity_icon} {error.message[:60]}{'...' if len(error.message) > 60 else ''}"
                
                self.error_listbox.insert(tk.END, text)
                
                # Color code by severity
                index = self.error_listbox.size() - 1
                if error.severity == ErrorSeverity.CRITICAL:
                    self.error_listbox.itemconfig(index, {'fg': '#dc3545'})
                elif error.severity == ErrorSeverity.HIGH:
                    self.error_listbox.itemconfig(index, {'fg': '#fd7e14'})
                elif error.severity == ErrorSeverity.MEDIUM:
                    self.error_listbox.itemconfig(index, {'fg': '#ffc107'})
    
    def _get_severity_icon(self, severity: ErrorSeverity) -> str:
        """Get icon for error severity."""
        icons = {
            ErrorSeverity.CRITICAL: "🛑",
            ErrorSeverity.HIGH: "⚠",
            ErrorSeverity.MEDIUM: "⚠",
            ErrorSeverity.LOW: "ℹ"
        }
        return icons.get(severity, "•")
    
    def _create_tooltip(self):
        """Create tooltip for status indicator."""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            # Get tooltip text
            status_level = self._get_current_status_level()
            if status_level == StatusLevel.OK:
                tooltip_text = "System OK - No errors"
            else:
                total_errors = sum(self.error_counts.values())
                tooltip_text = f"System Status: {status_level.value.title()}\n"
                tooltip_text += f"Total Errors: {total_errors}\n"
                tooltip_text += f"Critical: {self.error_counts['critical']}\n"
                tooltip_text += f"High: {self.error_counts['high']}\n"
                tooltip_text += f"Medium: {self.error_counts['medium']}\n"
                tooltip_text += f"Low: {self.error_counts['low']}"
            
            label = ttk.Label(
                tooltip,
                text=tooltip_text,
                background="lightyellow",
                relief="solid",
                borderwidth=1,
                font=("Arial", 8)
            )
            label.pack()
            
            # Store tooltip reference
            self.tooltip = tooltip
        
        def on_leave(event):
            if hasattr(self, 'tooltip'):
                self.tooltip.destroy()
                delattr(self, 'tooltip')
        
        # Bind events to all interactive elements
        for widget in [self.status_canvas, self.status_label]:
            if widget:
                widget.bind("<Enter>", on_enter)
                widget.bind("<Leave>", on_leave)
    
    def _on_click(self, event=None):
        """Handle status indicator click."""
        if self.on_status_click:
            self.on_status_click()
        else:
            self._show_error_details()
    
    def _on_error_select(self, event=None):
        """Handle error selection in listbox."""
        if not self.error_listbox:
            return
        
        selection = self.error_listbox.curselection()
        if selection and self.on_error_select:
            index = selection[0]
            if index < len(self.current_errors):
                # Get error (list is in reverse chronological order)
                recent_errors = sorted(self.current_errors, key=lambda x: x.timestamp, reverse=True)
                if index < len(recent_errors):
                    self.on_error_select(recent_errors[index])
    
    def _on_error_double_click(self, event=None):
        """Handle error double-click in listbox."""
        if not self.error_listbox:
            return
        
        selection = self.error_listbox.curselection()
        if selection:
            index = selection[0]
            recent_errors = sorted(self.current_errors, key=lambda x: x.timestamp, reverse=True)
            if index < len(recent_errors):
                error_info = recent_errors[index]
                self._show_error_dialog(error_info)
    
    def _show_error_details(self):
        """Show detailed error information."""
        if not self.current_errors:
            return
        
        # Show most recent critical/high error, or just most recent
        recent_errors = sorted(self.current_errors, key=lambda x: x.timestamp, reverse=True)
        
        # Find most severe recent error
        target_error = None
        for error in recent_errors:
            if error.severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]:
                target_error = error
                break
        
        if not target_error and recent_errors:
            target_error = recent_errors[0]
        
        if target_error:
            self._show_error_dialog(target_error)
    
    def _show_error_dialog(self, error_info: ErrorInfo):
        """Show error dialog for specific error."""
        try:
            # Create recovery options
            recovery_options = [
                RecoveryOption(
                    label="Dismiss",
                    callback=lambda: True,
                    description="Acknowledge this error",
                    is_default=True
                ),
                RecoveryOption(
                    label="Clear All Errors",
                    callback=self._clear_all_errors,
                    description="Clear all current errors"
                )
            ]
            
            show_error_with_recovery(
                self.winfo_toplevel(),
                error_info,
                recovery_options
            )
        
        except Exception as e:
            self.logger.error(f"Failed to show error dialog: {e}")
    
    def _clear_all_errors(self) -> bool:
        """Clear all current errors."""
        try:
            self.current_errors.clear()
            self.error_counts = {key: 0 for key in self.error_counts}
            self._update_display()
            self.logger.info("All errors cleared from status widget")
            return True
        except Exception as e:
            self.logger.error(f"Failed to clear errors: {e}")
            return False
    
    def _export_error_report(self):
        """Export error report."""
        try:
            from px_ui.error_handling.error_reporter import get_error_reporter
            from tkinter import filedialog
            
            # Ask user for file location
            file_path = filedialog.asksaveasfilename(
                title="Export Error Report",
                defaultextension=".html",
                filetypes=[
                    ("HTML files", "*.html"),
                    ("JSON files", "*.json"),
                    ("CSV files", "*.csv")
                ]
            )
            
            if file_path:
                # Determine format from extension
                if file_path.endswith('.json'):
                    format = 'json'
                elif file_path.endswith('.csv'):
                    format = 'csv'
                else:
                    format = 'html'
                
                # Generate report
                reporter = get_error_reporter()
                output_file = reporter.generate_error_report(Path(file_path), format)
                
                from tkinter import messagebox
                messagebox.showinfo("Export Complete", f"Error report exported to:\n{output_file}")
        
        except Exception as e:
            self.logger.error(f"Failed to export error report: {e}")
            from tkinter import messagebox
            messagebox.showerror("Export Error", f"Failed to export error report:\n{str(e)}")
    
    def _refresh_errors(self):
        """Refresh error display."""
        # Get recent errors from error manager
        error_manager = get_error_manager()
        recent_errors = error_manager.get_recent_errors(minutes=60)
        
        # Update current errors
        self.current_errors = recent_errors
        
        # Recalculate counts
        self.error_counts = {key: 0 for key in self.error_counts}
        for error in self.current_errors:
            severity_key = error.severity.value
            if severity_key in self.error_counts:
                self.error_counts[severity_key] += 1
        
        # Update display
        self._update_display()
        self.logger.info("Error status refreshed")
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of current error state."""
        return {
            'total_errors': len(self.current_errors),
            'error_counts': self.error_counts.copy(),
            'status_level': self._get_current_status_level().value,
            'most_recent_error': self.current_errors[-1].timestamp.isoformat() if self.current_errors else None
        }


class ComponentErrorIndicator(ttk.Frame):
    """
    Simple error indicator for individual UI components.
    
    Shows a small colored dot that indicates the error state of a specific component.
    """
    
    def __init__(self, parent, component_name: str, **kwargs):
        """
        Initialize component error indicator.
        
        Args:
            parent: Parent widget
            component_name: Name of the component this indicator represents
        """
        super().__init__(parent, **kwargs)
        
        self.component_name = component_name
        self.current_status = StatusLevel.OK
        
        # Create indicator
        self.indicator = tk.Canvas(self, width=12, height=12, highlightthickness=0)
        self.indicator.pack()
        
        # Draw initial status
        self._update_indicator()
        
        # Add tooltip
        self._create_tooltip()
    
    def set_status(self, status_level: StatusLevel, message: str = ""):
        """Set the status of this component."""
        self.current_status = status_level
        self.status_message = message
        self._update_indicator()
    
    def _update_indicator(self):
        """Update the visual indicator."""
        # Clear canvas
        self.indicator.delete("all")
        
        # Get color for status
        color = {
            StatusLevel.OK: "#28a745",
            StatusLevel.INFO: "#17a2b8",
            StatusLevel.WARNING: "#ffc107",
            StatusLevel.ERROR: "#dc3545",
            StatusLevel.CRITICAL: "#6f42c1"
        }.get(self.current_status, "#6c757d")
        
        # Draw circle
        self.indicator.create_oval(2, 2, 10, 10, fill=color, outline=color)
    
    def _create_tooltip(self):
        """Create tooltip showing component status."""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            tooltip_text = f"Component: {self.component_name}\n"
            tooltip_text += f"Status: {self.current_status.value.title()}"
            
            if hasattr(self, 'status_message') and self.status_message:
                tooltip_text += f"\n{self.status_message}"
            
            label = ttk.Label(
                tooltip,
                text=tooltip_text,
                background="lightyellow",
                relief="solid",
                borderwidth=1,
                font=("Arial", 8)
            )
            label.pack()
            
            self.tooltip = tooltip
        
        def on_leave(event):
            if hasattr(self, 'tooltip'):
                self.tooltip.destroy()
                delattr(self, 'tooltip')
        
        self.indicator.bind("<Enter>", on_enter)
        self.indicator.bind("<Leave>", on_leave)