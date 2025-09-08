"""
Error dialog components for user-friendly error display and recovery options.

This module provides various error dialog types with recovery options,
error details display, and user-friendly error messages.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import logging
from datetime import datetime
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass

from px_ui.error_handling.error_manager import ErrorInfo, ErrorSeverity, ErrorCategory


@dataclass
class RecoveryOption:
    """Represents a recovery option for an error."""
    label: str
    callback: Callable[[], bool]
    description: Optional[str] = None
    is_default: bool = False


class ErrorDialog:
    """Base class for error dialogs with common functionality."""
    
    def __init__(self, parent: tk.Widget, title: str = "Error"):
        """
        Initialize error dialog.
        
        Args:
            parent: Parent widget
            title: Dialog title
        """
        self.parent = parent
        self.title = title
        self.logger = logging.getLogger(__name__)
        self.result = None
        self.dialog = None
    
    def show(self) -> Optional[str]:
        """Show the dialog and return the result."""
        self._create_dialog()
        self._center_dialog()
        
        # Make dialog modal
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Wait for dialog to close
        self.parent.wait_window(self.dialog)
        
        return self.result
    
    def _create_dialog(self):
        """Create the dialog window. Override in subclasses."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(self.title)
        self.dialog.resizable(False, False)
        
        # Handle window close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
    
    def _center_dialog(self):
        """Center the dialog on the parent window."""
        self.dialog.update_idletasks()
        
        # Get dialog size
        dialog_width = self.dialog.winfo_reqwidth()
        dialog_height = self.dialog.winfo_reqheight()
        
        # Get parent position and size
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_width = self.parent.winfo_width()
        parent_height = self.parent.winfo_height()
        
        # Calculate center position
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
    
    def _on_cancel(self):
        """Handle dialog cancellation."""
        self.result = None
        self.dialog.destroy()


class SimpleErrorDialog(ErrorDialog):
    """Simple error dialog with message and OK button."""
    
    def __init__(self, parent: tk.Widget, message: str, title: str = "Error", 
                 details: Optional[str] = None):
        """
        Initialize simple error dialog.
        
        Args:
            parent: Parent widget
            message: Error message
            title: Dialog title
            details: Optional detailed error information
        """
        super().__init__(parent, title)
        self.message = message
        self.details = details
    
    def _create_dialog(self):
        """Create the simple error dialog."""
        super()._create_dialog()
        
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill="both", expand=True)
        
        # Error icon and message
        message_frame = ttk.Frame(main_frame)
        message_frame.pack(fill="x", pady=(0, 15))
        
        # Error icon (using Unicode symbol)
        icon_label = ttk.Label(message_frame, text="⚠", font=("Arial", 24), foreground="red")
        icon_label.pack(side="left", padx=(0, 10))
        
        # Message text
        message_label = ttk.Label(
            message_frame, 
            text=self.message, 
            wraplength=400,
            justify="left"
        )
        message_label.pack(side="left", fill="x", expand=True)
        
        # Details section (if provided)
        if self.details:
            details_frame = ttk.LabelFrame(main_frame, text="Details", padding=10)
            details_frame.pack(fill="both", expand=True, pady=(0, 15))
            
            details_text = scrolledtext.ScrolledText(
                details_frame,
                height=6,
                width=60,
                wrap="word",
                state="disabled"
            )
            details_text.pack(fill="both", expand=True)
            
            # Insert details text
            details_text.config(state="normal")
            details_text.insert("1.0", self.details)
            details_text.config(state="disabled")
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x")
        
        # OK button
        ok_button = ttk.Button(
            button_frame,
            text="OK",
            command=self._on_ok,
            default="active"
        )
        ok_button.pack(side="right")
        
        # Focus on OK button
        ok_button.focus_set()
        
        # Bind Enter key
        self.dialog.bind("<Return>", lambda e: self._on_ok())
        self.dialog.bind("<Escape>", lambda e: self._on_ok())
    
    def _on_ok(self):
        """Handle OK button click."""
        self.result = "ok"
        self.dialog.destroy()


class RecoveryErrorDialog(ErrorDialog):
    """Error dialog with recovery options."""
    
    def __init__(self, parent: tk.Widget, error_info: ErrorInfo, 
                 recovery_options: List[RecoveryOption]):
        """
        Initialize recovery error dialog.
        
        Args:
            parent: Parent widget
            error_info: Error information
            recovery_options: Available recovery options
        """
        super().__init__(parent, self._get_title_for_error(error_info))
        self.error_info = error_info
        self.recovery_options = recovery_options
    
    def _get_title_for_error(self, error_info: ErrorInfo) -> str:
        """Get appropriate title for error severity."""
        if error_info.severity == ErrorSeverity.CRITICAL:
            return "Critical Error"
        elif error_info.severity == ErrorSeverity.HIGH:
            return "Error"
        elif error_info.severity == ErrorSeverity.MEDIUM:
            return "Warning"
        else:
            return "Information"
    
    def _create_dialog(self):
        """Create the recovery error dialog."""
        super()._create_dialog()
        self.dialog.minsize(500, 300)
        
        # Main frame
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill="both", expand=True)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Header with error info
        self._create_header(main_frame)
        
        # Details section
        self._create_details_section(main_frame)
        
        # Recovery options
        self._create_recovery_section(main_frame)
        
        # Button frame
        self._create_button_frame(main_frame)
    
    def _create_header(self, parent: ttk.Frame):
        """Create the header section with error summary."""
        header_frame = ttk.Frame(parent)
        header_frame.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        header_frame.grid_columnconfigure(1, weight=1)
        
        # Severity icon
        icon_text = self._get_icon_for_severity(self.error_info.severity)
        icon_color = self._get_color_for_severity(self.error_info.severity)
        
        icon_label = ttk.Label(
            header_frame, 
            text=icon_text, 
            font=("Arial", 20),
            foreground=icon_color
        )
        icon_label.grid(row=0, column=0, padx=(0, 10), sticky="nw")
        
        # Error message
        message_label = ttk.Label(
            header_frame,
            text=self.error_info.message,
            wraplength=400,
            justify="left",
            font=("Arial", 10, "bold")
        )
        message_label.grid(row=0, column=1, sticky="ew")
        
        # Error category and time
        info_text = f"Category: {self.error_info.category.value.replace('_', ' ').title()}\n"
        info_text += f"Time: {self.error_info.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        
        info_label = ttk.Label(
            header_frame,
            text=info_text,
            font=("Arial", 8),
            foreground="gray"
        )
        info_label.grid(row=1, column=1, sticky="ew", pady=(5, 0))
    
    def _create_details_section(self, parent: ttk.Frame):
        """Create the details section."""
        if self.error_info.details or self.error_info.exception:
            details_frame = ttk.LabelFrame(parent, text="Error Details", padding=10)
            details_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 15))
            details_frame.grid_rowconfigure(0, weight=1)
            details_frame.grid_columnconfigure(0, weight=1)
            
            details_text = scrolledtext.ScrolledText(
                details_frame,
                height=8,
                wrap="word",
                state="disabled",
                font=("Consolas", 9)
            )
            details_text.grid(row=0, column=0, sticky="nsew")
            
            # Build details content
            details_content = ""
            if self.error_info.details:
                details_content += f"Details: {self.error_info.details}\n\n"
            
            if self.error_info.exception:
                details_content += f"Exception: {type(self.error_info.exception).__name__}\n"
                details_content += f"Message: {str(self.error_info.exception)}\n"
                
                # Add context if available
                if self.error_info.context:
                    details_content += "\nContext:\n"
                    for key, value in self.error_info.context.items():
                        details_content += f"  {key}: {value}\n"
            
            # Insert details
            details_text.config(state="normal")
            details_text.insert("1.0", details_content.strip())
            details_text.config(state="disabled")
    
    def _create_recovery_section(self, parent: ttk.Frame):
        """Create the recovery options section."""
        if self.recovery_options:
            recovery_frame = ttk.LabelFrame(parent, text="Recovery Options", padding=10)
            recovery_frame.grid(row=2, column=0, sticky="ew", pady=(0, 15))
            
            for i, option in enumerate(self.recovery_options):
                option_frame = ttk.Frame(recovery_frame)
                option_frame.pack(fill="x", pady=2)
                
                # Recovery button
                button = ttk.Button(
                    option_frame,
                    text=option.label,
                    command=lambda opt=option: self._execute_recovery(opt)
                )
                button.pack(side="left", padx=(0, 10))
                
                # Description
                if option.description:
                    desc_label = ttk.Label(
                        option_frame,
                        text=option.description,
                        font=("Arial", 8),
                        foreground="gray"
                    )
                    desc_label.pack(side="left", fill="x", expand=True)
                
                # Set default button
                if option.is_default:
                    button.config(default="active")
                    button.focus_set()
    
    def _create_button_frame(self, parent: ttk.Frame):
        """Create the button frame."""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=3, column=0, sticky="ew")
        
        # Close button
        close_button = ttk.Button(
            button_frame,
            text="Close",
            command=self._on_cancel
        )
        close_button.pack(side="right")
        
        # Copy details button
        copy_button = ttk.Button(
            button_frame,
            text="Copy Details",
            command=self._copy_details
        )
        copy_button.pack(side="right", padx=(0, 10))
        
        # Bind Escape key
        self.dialog.bind("<Escape>", lambda e: self._on_cancel())
    
    def _execute_recovery(self, option: RecoveryOption):
        """Execute a recovery option."""
        try:
            self.logger.info(f"Executing recovery option: {option.label}")
            success = option.callback()
            
            if success:
                self.result = f"recovery:{option.label}"
                self.dialog.destroy()
                messagebox.showinfo(
                    "Recovery Successful",
                    f"Recovery action '{option.label}' completed successfully."
                )
            else:
                messagebox.showerror(
                    "Recovery Failed",
                    f"Recovery action '{option.label}' failed. Please try another option."
                )
        
        except Exception as e:
            self.logger.error(f"Error executing recovery option {option.label}: {e}")
            messagebox.showerror(
                "Recovery Error",
                f"An error occurred while executing recovery action:\n{str(e)}"
            )
    
    def _copy_details(self):
        """Copy error details to clipboard."""
        try:
            details_text = f"Error: {self.error_info.message}\n"
            details_text += f"Category: {self.error_info.category.value}\n"
            details_text += f"Severity: {self.error_info.severity.value}\n"
            details_text += f"Time: {self.error_info.timestamp}\n"
            
            if self.error_info.details:
                details_text += f"\nDetails: {self.error_info.details}\n"
            
            if self.error_info.exception:
                details_text += f"\nException: {type(self.error_info.exception).__name__}\n"
                details_text += f"Message: {str(self.error_info.exception)}\n"
            
            # Copy to clipboard
            self.dialog.clipboard_clear()
            self.dialog.clipboard_append(details_text)
            
            messagebox.showinfo("Copied", "Error details copied to clipboard.")
        
        except Exception as e:
            self.logger.error(f"Failed to copy details: {e}")
            messagebox.showerror("Error", "Failed to copy details to clipboard.")
    
    def _get_icon_for_severity(self, severity: ErrorSeverity) -> str:
        """Get icon character for error severity."""
        icons = {
            ErrorSeverity.CRITICAL: "🛑",
            ErrorSeverity.HIGH: "⚠",
            ErrorSeverity.MEDIUM: "⚠",
            ErrorSeverity.LOW: "ℹ"
        }
        return icons.get(severity, "⚠")
    
    def _get_color_for_severity(self, severity: ErrorSeverity) -> str:
        """Get color for error severity."""
        colors = {
            ErrorSeverity.CRITICAL: "red",
            ErrorSeverity.HIGH: "red",
            ErrorSeverity.MEDIUM: "orange",
            ErrorSeverity.LOW: "blue"
        }
        return colors.get(severity, "red")


class ErrorStatusIndicator:
    """Status indicator widget for showing error states."""
    
    def __init__(self, parent: tk.Widget):
        """
        Initialize error status indicator.
        
        Args:
            parent: Parent widget
        """
        self.parent = parent
        self.logger = logging.getLogger(__name__)
        
        # Create indicator frame
        self.frame = ttk.Frame(parent)
        
        # Status indicator (colored circle)
        self.status_canvas = tk.Canvas(self.frame, width=16, height=16, highlightthickness=0)
        self.status_canvas.pack(side="left", padx=(0, 5))
        
        # Status text
        self.status_label = ttk.Label(self.frame, text="OK")
        self.status_label.pack(side="left")
        
        # Initialize with OK status
        self.set_status("ok", "System OK")
    
    def set_status(self, status: str, message: str):
        """
        Set the status indicator.
        
        Args:
            status: Status type ("ok", "warning", "error", "critical")
            message: Status message
        """
        # Clear canvas
        self.status_canvas.delete("all")
        
        # Color mapping
        colors = {
            "ok": "#28a745",      # Green
            "warning": "#ffc107", # Yellow
            "error": "#dc3545",   # Red
            "critical": "#6f42c1" # Purple
        }
        
        color = colors.get(status, "#6c757d")  # Default gray
        
        # Draw status circle
        self.status_canvas.create_oval(2, 2, 14, 14, fill=color, outline=color)
        
        # Update text
        self.status_label.config(text=message)
        
        # Add tooltip with full message
        self._create_tooltip(message)
    
    def _create_tooltip(self, text: str):
        """Create tooltip for the status indicator."""
        def on_enter(event):
            tooltip = tk.Toplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            
            label = ttk.Label(
                tooltip,
                text=text,
                background="lightyellow",
                relief="solid",
                borderwidth=1,
                font=("Arial", 8)
            )
            label.pack()
            
            # Store tooltip reference
            self.frame.tooltip = tooltip
        
        def on_leave(event):
            if hasattr(self.frame, 'tooltip'):
                self.frame.tooltip.destroy()
                delattr(self.frame, 'tooltip')
        
        # Bind events
        self.frame.bind("<Enter>", on_enter)
        self.frame.bind("<Leave>", on_leave)
    
    def pack(self, **kwargs):
        """Pack the indicator frame."""
        self.frame.pack(**kwargs)
    
    def grid(self, **kwargs):
        """Grid the indicator frame."""
        self.frame.grid(**kwargs)


# Convenience functions for showing error dialogs

def show_simple_error(parent: tk.Widget, message: str, title: str = "Error",
                     details: Optional[str] = None) -> str:
    """Show a simple error dialog."""
    dialog = SimpleErrorDialog(parent, message, title, details)
    return dialog.show()


def show_error_with_recovery(parent: tk.Widget, error_info: ErrorInfo,
                           recovery_options: List[RecoveryOption]) -> Optional[str]:
    """Show an error dialog with recovery options."""
    dialog = RecoveryErrorDialog(parent, error_info, recovery_options)
    return dialog.show()


def show_pac_error(parent: tk.Widget, message: str, details: Optional[str] = None,
                  pac_content: Optional[str] = None) -> Optional[str]:
    """Show PAC-specific error dialog with recovery options."""
    from px_ui.error_handling.error_manager import ErrorInfo, ErrorSeverity, ErrorCategory
    
    # Create error info
    error_info = ErrorInfo(
        error_id="pac_error",
        category=ErrorCategory.PAC_VALIDATION,
        severity=ErrorSeverity.MEDIUM,
        message=message,
        details=details,
        context={"pac_content": pac_content} if pac_content else None
    )
    
    # Create recovery options
    recovery_options = [
        RecoveryOption(
            label="Use Default PAC",
            callback=lambda: True,  # Placeholder - would trigger fallback
            description="Fall back to a basic PAC configuration",
            is_default=True
        ),
        RecoveryOption(
            label="Retry Loading",
            callback=lambda: True,  # Placeholder - would retry operation
            description="Attempt to reload the PAC configuration"
        )
    ]
    
    return show_error_with_recovery(parent, error_info, recovery_options)


def show_network_error(parent: tk.Widget, message: str, details: Optional[str] = None,
                      url: Optional[str] = None) -> Optional[str]:
    """Show network-specific error dialog with recovery options."""
    from px_ui.error_handling.error_manager import ErrorInfo, ErrorSeverity, ErrorCategory
    
    # Create error info
    error_info = ErrorInfo(
        error_id="network_error",
        category=ErrorCategory.NETWORK,
        severity=ErrorSeverity.HIGH,
        message=message,
        details=details,
        context={"url": url} if url else None
    )
    
    # Create recovery options
    recovery_options = [
        RecoveryOption(
            label="Use Direct Connection",
            callback=lambda: True,  # Placeholder - would bypass proxy
            description="Bypass proxy and connect directly",
            is_default=True
        ),
        RecoveryOption(
            label="Retry Connection",
            callback=lambda: True,  # Placeholder - would retry
            description="Attempt to reconnect through proxy"
        )
    ]
    
    return show_error_with_recovery(parent, error_info, recovery_options)


def show_proxy_error(parent: tk.Widget, message: str, details: Optional[str] = None,
                    proxy_info: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Show proxy-specific error dialog with recovery options."""
    from px_ui.error_handling.error_manager import ErrorInfo, ErrorSeverity, ErrorCategory
    
    # Create error info
    error_info = ErrorInfo(
        error_id="proxy_error",
        category=ErrorCategory.PROXY,
        severity=ErrorSeverity.HIGH,
        message=message,
        details=details,
        context=proxy_info or {}
    )
    
    # Create recovery options
    recovery_options = [
        RecoveryOption(
            label="Restart Proxy",
            callback=lambda: True,  # Placeholder - would restart proxy
            description="Stop and restart the proxy service",
            is_default=True
        ),
        RecoveryOption(
            label="Check Configuration",
            callback=lambda: True,  # Placeholder - would open config
            description="Review proxy configuration settings"
        )
    ]
    
    return show_error_with_recovery(parent, error_info, recovery_options)