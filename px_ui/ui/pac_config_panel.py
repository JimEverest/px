"""
PAC Configuration Panel for managing Proxy Auto-Configuration files.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import logging
import threading
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Callable
import tempfile
import os

from px_ui.models.pac_configuration import PACConfiguration
from px_ui.error_handling.error_manager import ErrorCategory, ErrorSeverity


class PACConfigPanel(ttk.Frame):
    """
    Panel for configuring and managing PAC (Proxy Auto-Configuration) files.
    
    Provides functionality for:
    - Loading PAC files from local filesystem
    - Loading PAC files from URLs
    - Inline PAC editing with syntax highlighting
    - PAC validation and testing
    - PAC file saving with encoding management
    """
    
    def __init__(self, parent, **kwargs):
        """Initialize the PAC configuration panel."""
        super().__init__(parent, **kwargs)
        
        self.logger = logging.getLogger(__name__)
        self.pac_config: Optional[PACConfiguration] = None
        
        # Callbacks for external integration
        self.on_pac_changed: Optional[Callable[[PACConfiguration], None]] = None
        self.on_restart_proxy: Optional[Callable[[PACConfiguration], None]] = None
        
        # Proxy controller reference
        self.proxy_controller = None
        self.config_manager = None
        
        # Error handling
        self.error_handler = None
        
        # UI state
        self._is_loading = False
        self._auto_validate = True
        
        self._setup_ui()
        self._create_default_pac()
        
        self.logger.info("PAC Configuration Panel initialized")
    
    def set_error_handler(self, error_handler):
        """Set the error handler for this component."""
        self.error_handler = error_handler
    
    def _setup_ui(self):
        """Set up the user interface components."""
        # Configure grid weights
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Create main sections
        self._create_source_section()
        self._create_editor_section()
        self._create_validation_section()
        self._create_test_section()
        self._create_action_buttons()
    
    def _create_source_section(self):
        """Create the PAC source selection section."""
        source_frame = ttk.LabelFrame(self, text="PAC Source", padding=10)
        source_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        source_frame.grid_columnconfigure(1, weight=1)
        
        # Source type selection
        ttk.Label(source_frame, text="Source Type:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        
        self.source_type_var = tk.StringVar(value="inline")
        source_type_frame = ttk.Frame(source_frame)
        source_type_frame.grid(row=0, column=1, sticky="w")
        
        ttk.Radiobutton(
            source_type_frame, text="Inline", variable=self.source_type_var, 
            value="inline", command=self._on_source_type_changed
        ).pack(side="left", padx=(0, 10))
        
        ttk.Radiobutton(
            source_type_frame, text="File", variable=self.source_type_var, 
            value="file", command=self._on_source_type_changed
        ).pack(side="left", padx=(0, 10))
        
        ttk.Radiobutton(
            source_type_frame, text="URL", variable=self.source_type_var, 
            value="url", command=self._on_source_type_changed
        ).pack(side="left")
        
        # File/URL path section
        path_frame = ttk.Frame(source_frame)
        path_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        path_frame.grid_columnconfigure(1, weight=1)
        
        self.path_label = ttk.Label(path_frame, text="Path:")
        self.path_label.grid(row=0, column=0, sticky="w", padx=(0, 5))
        
        self.path_var = tk.StringVar()
        self.path_var.trace('w', self._on_path_changed)
        self.path_entry = ttk.Entry(path_frame, textvariable=self.path_var, state="disabled")
        self.path_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        
        self.browse_button = ttk.Button(path_frame, text="Browse...", command=self._browse_file, state="disabled")
        self.browse_button.grid(row=0, column=2, padx=(0, 5))
        
        self.load_button = ttk.Button(path_frame, text="Load", command=self._load_from_source, state="disabled")
        self.load_button.grid(row=0, column=3)
        
        # Encoding selection
        encoding_frame = ttk.Frame(source_frame)
        encoding_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        
        ttk.Label(encoding_frame, text="Encoding:").pack(side="left", padx=(0, 5))
        
        self.encoding_var = tk.StringVar(value="utf-8")
        encoding_combo = ttk.Combobox(
            encoding_frame, textvariable=self.encoding_var, 
            values=["utf-8", "ascii", "latin-1", "cp1252"],
            state="readonly", width=10
        )
        encoding_combo.pack(side="left")
        encoding_combo.bind("<<ComboboxSelected>>", self._on_encoding_changed)
    
    def _create_editor_section(self):
        """Create the PAC content editor section."""
        editor_frame = ttk.LabelFrame(self, text="PAC Content", padding=10)
        editor_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 5))
        editor_frame.grid_rowconfigure(0, weight=1)
        editor_frame.grid_columnconfigure(0, weight=1)
        
        # Create text editor with scrollbars
        self.editor = scrolledtext.ScrolledText(
            editor_frame,
            wrap=tk.NONE,
            font=("Consolas", 10) if os.name == 'nt' else ("Monaco", 10),
            undo=True,
            maxundo=50
        )
        self.editor.grid(row=0, column=0, sticky="nsew")
        
        # Bind events for auto-validation
        self.editor.bind("<KeyRelease>", self._on_content_changed)
        self.editor.bind("<Button-1>", self._on_content_changed)
        
        # Add context menu
        self._create_editor_context_menu()
    
    def _create_editor_context_menu(self):
        """Create context menu for the editor."""
        self.context_menu = tk.Menu(self.editor, tearoff=0)
        self.context_menu.add_command(label="Cut", command=lambda: self.editor.event_generate("<<Cut>>"))
        self.context_menu.add_command(label="Copy", command=lambda: self.editor.event_generate("<<Copy>>"))
        self.context_menu.add_command(label="Paste", command=lambda: self.editor.event_generate("<<Paste>>"))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Select All", command=lambda: self.editor.event_generate("<<SelectAll>>"))
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Undo", command=lambda: self.editor.event_generate("<<Undo>>"))
        self.context_menu.add_command(label="Redo", command=lambda: self.editor.event_generate("<<Redo>>"))
        
        def show_context_menu(event):
            try:
                self.context_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.context_menu.grab_release()
        
        self.editor.bind("<Button-3>", show_context_menu)  # Right click
    
    def _create_validation_section(self):
        """Create the PAC validation section."""
        validation_frame = ttk.LabelFrame(self, text="Validation", padding=10)
        validation_frame.grid(row=2, column=0, sticky="ew", pady=(0, 5))
        validation_frame.grid_columnconfigure(1, weight=1)
        
        # Validation controls
        controls_frame = ttk.Frame(validation_frame)
        controls_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        
        self.validate_button = ttk.Button(controls_frame, text="Validate PAC", command=self._validate_pac)
        self.validate_button.pack(side="left", padx=(0, 10))
        
        self.auto_validate_var = tk.BooleanVar(value=True)
        auto_validate_check = ttk.Checkbutton(
            controls_frame, text="Auto-validate", variable=self.auto_validate_var,
            command=self._on_auto_validate_changed
        )
        auto_validate_check.pack(side="left")
        
        # Validation status
        self.validation_status = ttk.Label(validation_frame, text="Status: Not validated", foreground="gray")
        self.validation_status.grid(row=1, column=0, columnspan=2, sticky="w")
        
        # Validation errors display
        self.errors_text = scrolledtext.ScrolledText(
            validation_frame, height=4, wrap=tk.WORD, state="disabled"
        )
        self.errors_text.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
    
    def _create_test_section(self):
        """Create the PAC testing section."""
        test_frame = ttk.LabelFrame(self, text="PAC Testing", padding=10)
        test_frame.grid(row=3, column=0, sticky="ew", pady=(0, 5))
        test_frame.grid_columnconfigure(1, weight=1)
        
        # Test URL input
        ttk.Label(test_frame, text="Test URL:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        
        self.test_url_var = tk.StringVar(value="http://www.example.com")
        self.test_url_entry = ttk.Entry(test_frame, textvariable=self.test_url_var)
        self.test_url_entry.grid(row=0, column=1, sticky="ew", padx=(0, 5))
        
        self.test_button = ttk.Button(test_frame, text="Test", command=self._test_pac)
        self.test_button.grid(row=0, column=2)
        
        # Test result display
        ttk.Label(test_frame, text="Result:").grid(row=1, column=0, sticky="nw", padx=(0, 5), pady=(5, 0))
        
        self.test_result = tk.Text(test_frame, height=3, wrap=tk.WORD, state="disabled")
        self.test_result.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(5, 0))
    
    def _create_action_buttons(self):
        """Create action buttons section."""
        button_frame = ttk.Frame(self)
        button_frame.grid(row=4, column=0, sticky="ew", pady=(5, 0))
        
        # Apply button
        self.apply_button = ttk.Button(button_frame, text="Apply Configuration", 
                                     command=self._apply_configuration)
        self.apply_button.pack(side="left", padx=(0, 5))
        
        # Save button
        self.save_button = ttk.Button(button_frame, text="Save PAC File...", command=self._save_pac_file)
        self.save_button.pack(side="left", padx=(0, 5))
        
        # Clear button
        self.clear_button = ttk.Button(button_frame, text="Clear", command=self._clear_editor)
        self.clear_button.pack(side="left", padx=(0, 5))
        
        # Reset button
        self.reset_button = ttk.Button(button_frame, text="Reset to Default", command=self._reset_to_default)
        self.reset_button.pack(side="left")
    
    def _create_default_pac(self):
        """Create a default PAC configuration."""
        default_content = '''function FindProxyForURL(url, host) {
    // Default PAC configuration with example rules
    // Customize this function to define your proxy rules
    
    // Local network and localhost - direct connection
    if (isPlainHostName(host) || isInNet(host, "192.168.0.0", "255.255.0.0") || 
        isInNet(host, "10.0.0.0", "255.0.0.0") || isInNet(host, "127.0.0.0", "255.0.0.0")) {
        return "DIRECT";
    }
    
    // Example: Baidu uses direct connection
    if (host == "baidu.com" || host.endsWith(".baidu.com")) {
        return "DIRECT";
    }
    
    // Example: Google uses proxy server 1
    if (host == "google.com" || host.endsWith(".google.com")) {
        return "PROXY 127.0.0.1:8080";
    }
    
    // Example: Amazon uses proxy server 2
    if (host == "amazon.com" || host.endsWith(".amazon.com")) {
        return "PROXY 127.0.0.1:8081";
    }
    
    // Default: use main proxy server
    return "PROXY 127.0.0.1:33210";
}'''
        
        self.pac_config = PACConfiguration(
            source_type="inline",
            source_path="",
            content=default_content,
            encoding="utf-8"
        )
        
        self._update_editor_content()
        self._validate_pac()
    
    def _on_source_type_changed(self):
        """Handle source type selection change."""
        source_type = self.source_type_var.get()
        
        if source_type == "inline":
            self.path_entry.config(state="disabled")
            self.browse_button.config(state="disabled")
            self.load_button.config(state="disabled")
            self.path_label.config(text="Path:")
        elif source_type == "file":
            self.path_entry.config(state="normal")
            self.browse_button.config(state="normal")
            self.load_button.config(state="normal")
            self.path_label.config(text="File Path:")
        elif source_type == "url":
            self.path_entry.config(state="normal")
            self.browse_button.config(state="disabled")
            self.load_button.config(state="normal")
            self.path_label.config(text="URL:")
        
        # Update PAC configuration with new source type
        if not self._is_loading:
            self._update_pac_config_from_ui()
            self._auto_save_configuration()
        
        self.logger.debug(f"Source type changed to: {source_type}")
    
    def _on_path_changed(self, *args):
        """Handle path variable changes."""
        if not self._is_loading:
            self._update_pac_config_from_ui()
            self._auto_save_configuration()
    
    def _browse_file(self):
        """Browse for a PAC file."""
        file_path = filedialog.askopenfilename(
            title="Select PAC File",
            filetypes=[
                ("PAC files", "*.pac"),
                ("JavaScript files", "*.js"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            self.path_var.set(file_path)
            self.logger.info(f"Selected PAC file: {file_path}")
    
    def _load_from_source(self):
        """Load PAC content from the specified source."""
        source_type = self.source_type_var.get()
        source_path = self.path_var.get().strip()
        
        if not source_path:
            if self.error_handler:
                self.error_handler.handle_error(
                    category=ErrorCategory.PAC_VALIDATION,
                    severity=ErrorSeverity.MEDIUM,
                    message="Please specify a file path or URL",
                    show_dialog=True
                )
            else:
                messagebox.showerror("Error", "Please specify a file path or URL.")
            return
        
        self._set_loading_state(True)
        
        # Load in background thread to avoid blocking UI
        threading.Thread(
            target=self._load_from_source_thread,
            args=(source_type, source_path),
            daemon=True
        ).start()
    
    def _load_from_source_thread(self, source_type: str, source_path: str):
        """Load PAC content in background thread."""
        try:
            if source_type == "file":
                content = self._load_from_file(source_path)
            elif source_type == "url":
                content = self._load_from_url(source_path)
            else:
                raise ValueError(f"Invalid source type: {source_type}")
            
            # Update UI in main thread
            self.after(0, lambda: self._on_load_success(source_type, source_path, content))
            
        except Exception as e:
            self.after(0, lambda: self._on_load_error(str(e)))
    
    def _load_from_file(self, file_path: str) -> str:
        """Load PAC content from a file."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not path.is_file():
            raise ValueError(f"Path is not a file: {file_path}")
        
        encoding = self.encoding_var.get()
        
        try:
            with open(path, 'r', encoding=encoding) as f:
                content = f.read()
        except UnicodeDecodeError as e:
            raise ValueError(f"Failed to decode file with {encoding} encoding: {e}")
        
        self.logger.info(f"Loaded PAC file: {file_path} ({len(content)} characters)")
        return content
    
    def _load_from_url(self, url: str) -> str:
        """Load PAC content from a URL."""
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                raw_content = response.read()
                
                # Try to determine encoding from response headers
                content_type = response.headers.get('content-type', '')
                encoding = self.encoding_var.get()
                
                if 'charset=' in content_type:
                    try:
                        encoding = content_type.split('charset=')[1].split(';')[0].strip()
                    except:
                        pass  # Use default encoding
                
                content = raw_content.decode(encoding)
                
        except urllib.error.URLError as e:
            raise ValueError(f"Failed to load URL: {e}")
        except UnicodeDecodeError as e:
            raise ValueError(f"Failed to decode content with {encoding} encoding: {e}")
        
        self.logger.info(f"Loaded PAC from URL: {url} ({len(content)} characters)")
        return content
    
    def _on_load_success(self, source_type: str, source_path: str, content: str):
        """Handle successful PAC loading."""
        self.pac_config = PACConfiguration(
            source_type=source_type,
            source_path=source_path,
            content=content,
            encoding=self.encoding_var.get()
        )
        
        self._update_editor_content()
        self._validate_pac()
        self._set_loading_state(False)
        
        self.logger.info(f"Successfully loaded PAC from {source_type}: {source_path}")
    
    def _on_load_error(self, error_msg: str):
        """Handle PAC loading error."""
        self._set_loading_state(False)
        
        # Use error handler if available
        if self.error_handler:
            from px_ui.error_handling.error_manager import ErrorCategory, ErrorSeverity
            self.error_handler.handle_error(
                category=ErrorCategory.PAC_LOADING,
                severity=ErrorSeverity.MEDIUM,
                message="Failed to load PAC configuration",
                details=error_msg,
                context={"source": self.path_var.get()},
                highlight_widget=self.path_entry
            )
        else:
            # Fallback to simple dialog
            messagebox.showerror("Load Error", f"Failed to load PAC:\n{error_msg}")
        
        self.logger.error(f"Failed to load PAC: {error_msg}")
    
    def _set_loading_state(self, loading: bool):
        """Set the loading state of the UI."""
        self._is_loading = loading
        
        # Disable/enable controls during loading
        state = "disabled" if loading else "normal"
        self.load_button.config(state=state)
        self.validate_button.config(state=state)
        self.test_button.config(state=state)
        self.save_button.config(state=state)
        
        if loading:
            self.load_button.config(text="Loading...")
        else:
            self.load_button.config(text="Load")
    
    def _update_editor_content(self):
        """Update the editor with current PAC content."""
        if self.pac_config:
            self.editor.delete(1.0, tk.END)
            self.editor.insert(1.0, self.pac_config.content)
    
    def _on_content_changed(self, event=None):
        """Handle editor content changes."""
        if self._is_loading:
            return
        
        # Update PAC configuration with current editor content
        content = self.editor.get(1.0, tk.END).rstrip('\n')
        
        if self.pac_config:
            self.pac_config.content = content
        else:
            self.pac_config = PACConfiguration(
                source_type=self.source_type_var.get(),
                source_path=self.path_var.get(),
                content=content,
                encoding=self.encoding_var.get()
            )
        
        # Auto-save configuration
        self._auto_save_configuration()
        
        # Auto-validate if enabled
        if self._auto_validate and self.auto_validate_var.get():
            self.after_idle(self._validate_pac)
    
    def _on_encoding_changed(self, event=None):
        """Handle encoding selection change."""
        if self.pac_config:
            self.pac_config.encoding = self.encoding_var.get()
            self.logger.debug(f"Encoding changed to: {self.pac_config.encoding}")
    
    def _on_auto_validate_changed(self):
        """Handle auto-validate checkbox change."""
        self._auto_validate = self.auto_validate_var.get()
        if self._auto_validate:
            self._validate_pac()
        self.logger.debug(f"Auto-validate changed to: {self._auto_validate}")
    
    def _validate_pac(self):
        """Validate the current PAC configuration."""
        if not self.pac_config:
            self._update_validation_display(False, ["No PAC configuration to validate"])
            return
        
        # Update content from editor
        self.pac_config.content = self.editor.get(1.0, tk.END).rstrip('\n')
        
        # Perform validation
        is_valid = self.pac_config.validate_pac_syntax()
        
        # Update validation display
        self._update_validation_display(is_valid, self.pac_config.validation_errors)
        
        # Handle validation errors through error handler
        if not is_valid and self.error_handler:
            from px_ui.error_handling.error_manager import ErrorCategory, ErrorSeverity
            error_details = "\n".join(self.pac_config.validation_errors) if self.pac_config.validation_errors else "Unknown validation error"
            
            self.error_handler.handle_error(
                category=ErrorCategory.PAC_VALIDATION,
                severity=ErrorSeverity.MEDIUM,
                message="PAC configuration validation failed",
                details=error_details,
                context={"pac_content": self.editor.get("1.0", tk.END)[:500]},  # First 500 chars
                show_dialog=False,  # Don't show dialog for validation errors
                highlight_widget=self.editor
            )
        
        # Notify external components
        if self.on_pac_changed:
            self.on_pac_changed(self.pac_config)
        
        self.logger.debug(f"PAC validation result: {is_valid}")
    
    def _update_validation_display(self, is_valid: bool, errors: list):
        """Update the validation status display."""
        if is_valid:
            self.validation_status.config(text="Status: Valid ✓", foreground="green")
        else:
            self.validation_status.config(text="Status: Invalid ✗", foreground="red")
        
        # Update errors display
        self.errors_text.config(state="normal")
        self.errors_text.delete(1.0, tk.END)
        
        if errors:
            error_text = "\n".join(f"• {error}" for error in errors)
            self.errors_text.insert(1.0, error_text)
        else:
            self.errors_text.insert(1.0, "No validation errors.")
        
        self.errors_text.config(state="disabled")
    
    def _test_pac(self):
        """Test the PAC configuration with a URL."""
        if not self.pac_config or not self.pac_config.is_valid:
            if self.error_handler:
                self.error_handler.handle_error(
                    category=ErrorCategory.PAC_VALIDATION,
                    severity=ErrorSeverity.MEDIUM,
                    message="PAC configuration is not valid",
                    details="Please ensure PAC configuration is valid before testing",
                    show_dialog=True,
                    highlight_widget=self.editor
                )
            else:
                messagebox.showerror("Error", "Please ensure PAC configuration is valid before testing.")
            return
        
        test_url = self.test_url_var.get().strip()
        if not test_url:
            if self.error_handler:
                self.error_handler.handle_error(
                    category=ErrorCategory.PAC_VALIDATION,
                    severity=ErrorSeverity.LOW,
                    message="Please enter a URL to test",
                    show_dialog=True,
                    highlight_widget=self.test_url_entry
                )
            else:
                messagebox.showerror("Error", "Please enter a URL to test.")
            return
        
        try:
            # Extract host from URL
            from urllib.parse import urlparse
            parsed = urlparse(test_url)
            test_host = parsed.netloc or parsed.path.split('/')[0]
            
            # Test PAC configuration
            result = self.pac_config.test_url(test_url, test_host)
            
            # Display result
            self.test_result.config(state="normal")
            self.test_result.delete(1.0, tk.END)
            
            if result:
                self.test_result.insert(1.0, f"URL: {test_url}\nHost: {test_host}\nProxy Decision: {result}")
            else:
                self.test_result.insert(1.0, f"URL: {test_url}\nHost: {test_host}\nProxy Decision: Failed to evaluate")
            
            self.test_result.config(state="disabled")
            
            self.logger.info(f"PAC test result for {test_url}: {result}")
            
        except Exception as e:
            if self.error_handler:
                self.error_handler.handle_error(
                    category=ErrorCategory.PAC_VALIDATION,
                    severity=ErrorSeverity.MEDIUM,
                    message="Failed to test PAC configuration",
                    details=str(e),
                    exception=e,
                    show_dialog=True,
                    context={"test_url": test_url}
                )
            else:
                messagebox.showerror("Test Error", f"Failed to test PAC:\n{str(e)}")
            self.logger.error(f"PAC test error: {e}")
    
    def _save_pac_file(self):
        """Save the current PAC configuration to a file."""
        if not self.pac_config:
            if self.error_handler:
                self.error_handler.handle_error(
                    category=ErrorCategory.PAC_VALIDATION,
                    severity=ErrorSeverity.MEDIUM,
                    message="No PAC configuration to save",
                    show_dialog=True
                )
            else:
                messagebox.showerror("Error", "No PAC configuration to save.")
            return
        
        file_path = filedialog.asksaveasfilename(
            title="Save PAC File",
            defaultextension=".pac",
            filetypes=[
                ("PAC files", "*.pac"),
                ("JavaScript files", "*.js"),
                ("All files", "*.*")
            ]
        )
        
        if not file_path:
            return
        
        try:
            # Update content from editor
            self.pac_config.content = self.editor.get(1.0, tk.END).rstrip('\n')
            
            # Save to file
            with open(file_path, 'w', encoding=self.pac_config.encoding) as f:
                f.write(self.pac_config.content)
            
            # Update PAC configuration
            self.pac_config.source_type = "file"
            self.pac_config.source_path = file_path
            
            # Update UI
            self.source_type_var.set("file")
            self.path_var.set(file_path)
            self._on_source_type_changed()
            
            messagebox.showinfo("Success", f"PAC file saved successfully:\n{file_path}")
            self.logger.info(f"PAC file saved: {file_path}")
            
        except Exception as e:
            if self.error_handler:
                self.error_handler.handle_error(
                    category=ErrorCategory.SYSTEM,
                    severity=ErrorSeverity.HIGH,
                    message="Failed to save PAC file",
                    details=str(e),
                    exception=e,
                    show_dialog=True,
                    context={"file_path": file_path}
                )
            else:
                messagebox.showerror("Save Error", f"Failed to save PAC file:\n{str(e)}")
            self.logger.error(f"Failed to save PAC file: {e}")
    
    def _clear_editor(self):
        """Clear the editor content."""
        if messagebox.askyesno("Confirm", "Are you sure you want to clear the PAC content?"):
            self.editor.delete(1.0, tk.END)
            self.pac_config = None
            self._update_validation_display(False, ["No PAC content"])
            self.logger.info("PAC editor cleared")
    
    def _reset_to_default(self):
        """Reset to default PAC configuration."""
        if messagebox.askyesno("Confirm", "Are you sure you want to reset to default PAC configuration?"):
            self.source_type_var.set("inline")
            self.path_var.set("")
            self.encoding_var.set("utf-8")
            self._on_source_type_changed()
            self._create_default_pac()
            self.logger.info("PAC configuration reset to default")
    
    def _update_pac_config_from_ui(self):
        """Update PAC configuration from current UI state."""
        content = self.editor.get(1.0, tk.END).rstrip('\n')
        
        if self.pac_config:
            self.pac_config.source_type = self.source_type_var.get()
            self.pac_config.source_path = self.path_var.get()
            self.pac_config.content = content
            self.pac_config.encoding = self.encoding_var.get()
        else:
            self.pac_config = PACConfiguration(
                source_type=self.source_type_var.get(),
                source_path=self.path_var.get(),
                content=content,
                encoding=self.encoding_var.get()
            )
    
    def _auto_save_configuration(self):
        """Auto-save the current PAC configuration."""
        try:
            if self.config_manager and self.pac_config:
                # Update PAC config from UI first
                self._update_pac_config_from_ui()
                
                # Save to persistent storage
                success = self.config_manager.save_pac_configuration(self.pac_config)
                if success:
                    self.logger.debug("PAC configuration auto-saved")
                else:
                    self.logger.warning("Failed to auto-save PAC configuration")
        except Exception as e:
            self.logger.error(f"Error during auto-save: {e}")
    
    def _apply_configuration(self):
        """Apply the current PAC configuration."""
        try:
            config = self.get_pac_configuration()
            if config and config.is_valid:
                # Check if proxy is running
                if hasattr(self, 'proxy_controller') and self.proxy_controller and hasattr(self.proxy_controller, 'is_running') and self.proxy_controller.is_running():
                    # Show warning about restart requirement
                    result = messagebox.askyesno(
                        "Proxy Restart Required",
                        "The proxy is currently running. PAC configuration changes require a proxy restart to take effect.\n\n"
                        "Do you want to restart the proxy now?",
                        icon="warning"
                    )
                    if result:
                        # Restart proxy
                        if hasattr(self, 'on_restart_proxy') and self.on_restart_proxy:
                            self.on_restart_proxy(config)
                        else:
                            messagebox.showerror("Error", "Restart proxy callback is not configured.")
                    else:
                        messagebox.showinfo(
                            "Configuration Saved",
                            "Configuration has been saved but will not take effect until the proxy is restarted."
                        )
                else:
                    # Notify parent about configuration change
                    if hasattr(self, 'on_pac_changed') and self.on_pac_changed:
                        self.on_pac_changed(config)
                    messagebox.showinfo("Configuration Applied", "PAC configuration has been applied successfully.")
                
                self.logger.info(f"PAC configuration applied: {config.source_type}")
            else:
                messagebox.showerror("Invalid Configuration", 
                                    "Please fix the validation errors before applying.")
        except Exception as e:
            self.logger.error(f"Error applying PAC configuration: {e}")
            messagebox.showerror("Error", f"Failed to apply configuration: {str(e)}")
    
    # Public API methods
    
    def get_pac_configuration(self) -> Optional[PACConfiguration]:
        """Get the current PAC configuration."""
        if self.pac_config:
            # Update content from editor
            self.pac_config.content = self.editor.get(1.0, tk.END).rstrip('\n')
        return self.pac_config
    
    def set_pac_configuration(self, pac_config: PACConfiguration):
        """Set the PAC configuration."""
        # Set loading flag to prevent auto-save during initialization
        self._is_loading = True
        
        try:
            self.pac_config = pac_config
            
            # Update UI
            self.source_type_var.set(pac_config.source_type)
            self.path_var.set(pac_config.source_path)
            self.encoding_var.set(pac_config.encoding)
            
            self._on_source_type_changed()
            self._update_editor_content()
            self._validate_pac()
            
            self.logger.info(f"PAC configuration set: {pac_config.get_source_display_name()}")
        finally:
            # Clear loading flag
            self._is_loading = False
    
    def validate_current_pac(self) -> bool:
        """Validate the current PAC configuration and return result."""
        self._validate_pac()
        return self.pac_config.is_valid if self.pac_config else False
    
    def set_pac_changed_callback(self, callback: Callable[[PACConfiguration], None]):
        """Set callback for PAC configuration changes."""
        self.on_pac_changed = callback