"""
Main window implementation for the px UI client.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import logging
import threading
import sys
from typing import Optional, Callable
from pathlib import Path

from px_ui.models.proxy_status import ProxyStatus
from px_ui.config import ConfigManager
from px_ui.ui.pac_config_panel import PACConfigPanel
from px_ui.ui.monitoring_view import MonitoringView
from px_ui.ui.no_proxy_panel import NoProxyPanel
from px_ui.ui.ntlm_config_panel import NTLMConfigPanel
from px_ui.communication.event_system import EventSystem
from px_ui.ui.error_integration import ErrorIntegrationManager
from px_ui.error_handling.error_manager import ErrorCategory, ErrorSeverity
from px_ui.error_handling.error_reporter import get_error_reporter
from px_ui.ui.error_status_widget import ErrorStatusWidget


class MainWindow:
    """
    Main application window providing the primary interface for the px UI client.
    
    This class implements the root window with basic layout, menu system, status bar,
    and application lifecycle management.
    """
    
    def __init__(self):
        """Initialize the main window and its components."""
        self.logger = logging.getLogger(__name__)
        self.config_manager = ConfigManager()
        
        # Application state
        self._proxy_status: Optional[ProxyStatus] = None
        self._is_shutting_down = False
        
        # Callbacks for proxy control (to be set by application controller)
        self.start_proxy_callback: Optional[Callable] = None
        self.stop_proxy_callback: Optional[Callable] = None
        
        # Proxy controller reference (to be set by application controller)
        self.proxy_controller = None
        
        # Event system for communication between components
        self.event_system = EventSystem()
        
        # Error handling integration
        self.error_manager = ErrorIntegrationManager(self)
        
        # UI components
        self.pac_config_panel: Optional[PACConfigPanel] = None
        self.monitoring_view: Optional[MonitoringView] = None
        self.no_proxy_panel: Optional[NoProxyPanel] = None
        self.ntlm_config_panel: Optional[NTLMConfigPanel] = None
        
        # Initialize UI
        self._setup_root_window()
        self._create_menu_system()
        self._create_main_layout()
        self._create_status_bar()
        self._setup_keyboard_shortcuts()
        
        # Initialize with default proxy status
        self._update_proxy_status(ProxyStatus(
            is_running=False,
            listen_address="127.0.0.1",
            port=3128,
            mode="manual"
        ))
        
        # Set up error recovery callbacks
        self.error_manager.setup_component_recovery_callbacks()
        
        self.logger.info("Main window initialized successfully")
    
    def _setup_root_window(self):
        """Set up the root Tkinter window."""
        self.root = tk.Tk()
        self.root.title("px UI Client")
        self.root.geometry("800x600")
        self.root.minsize(600, 400)
        
        # Set window icon if available
        icon_path = Path(__file__).parent.parent.parent / "px.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except tk.TclError:
                self.logger.warning(f"Could not load icon from {icon_path}")
        
        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)
        
        # Configure grid weights for responsive layout
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
    
    def _create_menu_system(self):
        """Create the application menu system."""
        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)
        
        # File menu
        self.file_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.file_menu.add_command(label="Load PAC File...", command=self._load_pac_file, accelerator="Ctrl+O")
        self.file_menu.add_command(label="Save PAC File...", command=self._save_pac_file, accelerator="Ctrl+S")
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Export Logs...", command=self._export_logs, accelerator="Ctrl+E")
        self.file_menu.add_command(label="Export Error Report...", command=self._export_error_report)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Exit", command=self._on_window_close, accelerator="Ctrl+Q")
        
        # Proxy menu
        self.proxy_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Proxy", menu=self.proxy_menu)
        self.proxy_menu.add_command(label="Start Proxy", command=self._start_proxy, accelerator="F5")
        self.proxy_menu.add_command(label="Stop Proxy", command=self._stop_proxy, accelerator="F6")
        self.proxy_menu.add_separator()
        self.proxy_menu.add_command(label="Clear Logs", command=self._clear_logs, accelerator="Ctrl+L")
        
        # View menu
        self.view_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="View", menu=self.view_menu)
        self.view_menu.add_command(label="Refresh", command=self._refresh_view, accelerator="F5")
        self.view_menu.add_separator()
        self.view_menu.add_checkbutton(label="Auto-scroll Logs", command=self._toggle_auto_scroll)
        
        # Help menu
        self.help_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Help", menu=self.help_menu)
        self.help_menu.add_command(label="About", command=self._show_about)
    
    def _create_main_layout(self):
        """Create the main application layout."""
        # Main container frame
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.main_frame.grid_rowconfigure(1, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)
        
        # Control panel frame
        self.control_frame = ttk.LabelFrame(self.main_frame, text="Proxy Control", padding=10)
        self.control_frame.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        self.control_frame.grid_columnconfigure(1, weight=1)
        
        # Proxy control buttons
        self.start_button = ttk.Button(
            self.control_frame, 
            text="Start Proxy", 
            command=self._start_proxy,
            style="Accent.TButton"
        )
        self.start_button.grid(row=0, column=0, padx=(0, 5))
        
        self.stop_button = ttk.Button(
            self.control_frame, 
            text="Stop Proxy", 
            command=self._stop_proxy,
            state="disabled"
        )
        self.stop_button.grid(row=0, column=1, padx=(0, 5))
        
        # Proxy status label
        self.status_label = ttk.Label(self.control_frame, text="Proxy Status: Stopped")
        self.status_label.grid(row=0, column=2, padx=(10, 0), sticky="w")
        
        # Create tabbed interface for main content
        self._create_tabbed_interface()
    
    def _create_tabbed_interface(self):
        """Create the tabbed interface with all UI components."""
        # Create notebook (tabbed interface)
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        
        # Create and add tabs
        self._create_monitoring_tab()
        self._create_pac_config_tab()
        self._create_ntlm_config_tab()
        self._create_no_proxy_tab()
        
        # Bind tab change events
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
    
    def _create_monitoring_tab(self):
        """Create the monitoring view tab."""
        try:
            self.monitoring_view = MonitoringView(self.notebook, self.event_system)
            
            # Register error handler for monitoring view
            monitoring_handler = self.error_manager.register_component("monitoring", self.root)
            if hasattr(self.monitoring_view, 'set_error_handler'):
                self.monitoring_view.set_error_handler(monitoring_handler)
            
            self.notebook.add(self.monitoring_view, text="Request Monitoring")
            self.logger.info("Monitoring view tab created successfully")
        except Exception as e:
            self.logger.error(f"Failed to create monitoring view: {e}")
            
            # Handle error through error manager
            self.error_manager.handle_global_error(
                category=ErrorCategory.UI,
                severity=ErrorSeverity.HIGH,
                message="Failed to create monitoring view",
                details=str(e),
                component="main_window"
            )
            
            # Create placeholder if monitoring view fails
            placeholder_frame = ttk.Frame(self.notebook)
            ttk.Label(
                placeholder_frame, 
                text=f"Monitoring view unavailable:\n{str(e)}",
                justify="center"
            ).pack(expand=True)
            self.notebook.add(placeholder_frame, text="Request Monitoring")
    
    def _create_pac_config_tab(self):
        """Create the PAC configuration tab."""
        try:
            self.pac_config_panel = PACConfigPanel(self.notebook)
            self.pac_config_panel.set_pac_changed_callback(self._on_pac_config_changed)
            
            # Set proxy controller and restart callback
            self.pac_config_panel.proxy_controller = self.proxy_controller
            self.pac_config_panel.on_restart_proxy = self._restart_proxy_with_config
            self.pac_config_panel.config_manager = self.config_manager
            
            # Register error handler for PAC configuration
            pac_handler = self.error_manager.register_component("pac_config", self.root)
            if hasattr(self.pac_config_panel, 'set_error_handler'):
                self.pac_config_panel.set_error_handler(pac_handler)
            
            # Load saved PAC configuration
            self._load_saved_pac_configuration()
            
            self.notebook.add(self.pac_config_panel, text="PAC Configuration")
            self.logger.info("PAC configuration tab created successfully")
        except Exception as e:
            self.logger.error(f"Failed to create PAC configuration panel: {e}")
            
            # Handle error through error manager
            self.error_manager.handle_global_error(
                category=ErrorCategory.UI,
                severity=ErrorSeverity.HIGH,
                message="Failed to create PAC configuration panel",
                details=str(e),
                component="main_window"
            )
            
            # Create placeholder if PAC panel fails
            placeholder_frame = ttk.Frame(self.notebook)
            ttk.Label(
                placeholder_frame, 
                text=f"PAC configuration unavailable:\n{str(e)}",
                justify="center"
            ).pack(expand=True)
            self.notebook.add(placeholder_frame, text="PAC Configuration")
    
    def _create_ntlm_config_tab(self):
        """Create the NTLM authentication configuration tab."""
        try:
            self.ntlm_config_panel = NTLMConfigPanel(self.notebook, self.config_manager)
            self.ntlm_config_panel.set_config_change_callback(self._on_ntlm_config_changed)
            
            # Register error handler for NTLM configuration
            ntlm_handler = self.error_manager.register_component("ntlm_config", self.root)
            if hasattr(self.ntlm_config_panel, 'set_error_handler'):
                self.ntlm_config_panel.set_error_handler(ntlm_handler)
            
            self.notebook.add(self.ntlm_config_panel, text="NTLM Authentication")
            self.logger.info("NTLM configuration tab created successfully")
        except Exception as e:
            self.logger.error(f"Failed to create NTLM configuration panel: {e}")
            
            # Handle error through error manager
            self.error_manager.handle_global_error(
                category=ErrorCategory.UI,
                severity=ErrorSeverity.HIGH,
                message="Failed to create NTLM configuration panel",
                details=str(e),
                component="main_window"
            )
            
            # Create placeholder if NTLM panel fails
            placeholder_frame = ttk.Frame(self.notebook)
            ttk.Label(
                placeholder_frame, 
                text=f"NTLM configuration unavailable:\n{str(e)}",
                justify="center"
            ).pack(expand=True)
            self.notebook.add(placeholder_frame, text="NTLM Authentication")
    
    def _create_no_proxy_tab(self):
        """Create the no proxy configuration tab."""
        try:
            self.no_proxy_panel = NoProxyPanel(self.notebook)
            
            # Register error handler for no proxy panel
            no_proxy_handler = self.error_manager.register_component("no_proxy", self.root)
            if hasattr(self.no_proxy_panel, 'set_error_handler'):
                self.no_proxy_panel.set_error_handler(no_proxy_handler)
            
            self.notebook.add(self.no_proxy_panel, text="No Proxy Settings")
            self.logger.info("No proxy configuration tab created successfully")
        except Exception as e:
            self.logger.error(f"Failed to create no proxy panel: {e}")
            
            # Handle error through error manager
            self.error_manager.handle_global_error(
                category=ErrorCategory.UI,
                severity=ErrorSeverity.MEDIUM,
                message="Failed to create no proxy panel",
                details=str(e),
                component="main_window"
            )
            
            # Create placeholder if no proxy panel fails
            placeholder_frame = ttk.Frame(self.notebook)
            ttk.Label(
                placeholder_frame, 
                text=f"No proxy settings unavailable:\n{str(e)}",
                justify="center"
            ).pack(expand=True)
            self.notebook.add(placeholder_frame, text="No Proxy Settings")
    
    def _on_tab_changed(self, event):
        """Handle tab change events."""
        selected_tab = self.notebook.select()
        tab_text = self.notebook.tab(selected_tab, "text")
        self.logger.debug(f"Switched to tab: {tab_text}")
    
    def _on_pac_config_changed(self, pac_config):
        """Handle PAC configuration changes."""
        self.logger.info(f"PAC configuration changed: {pac_config.get_source_display_name()}")
        # TODO: Apply PAC configuration to proxy when implemented
    
    def _on_ntlm_config_changed(self, ntlm_config):
        """Handle NTLM configuration changes."""
        self.logger.info(f"NTLM configuration changed: {ntlm_config}")
        
        try:
            # Save NTLM configuration
            if self.config_manager:
                current_config = self.config_manager.get_proxy_config()
                current_config.update(ntlm_config)
                self.config_manager.save_proxy_config(current_config)
                self.logger.info("NTLM configuration saved successfully")
            
            # Update status
            if ntlm_config.get('enable_ntlm', False):
                upstream = ntlm_config.get('upstream_proxy', '')
                if upstream:
                    self.status_text.configure(text=f"NTLM enabled for {upstream}")
                else:
                    self.status_text.configure(text="NTLM enabled")
            else:
                self.status_text.configure(text="NTLM disabled")
                
        except Exception as e:
            self.logger.error(f"Failed to handle NTLM configuration change: {e}")
            self.error_manager.handle_global_error(
                category=ErrorCategory.CONFIGURATION,
                severity=ErrorSeverity.MEDIUM,
                message="Failed to save NTLM configuration",
                details=str(e),
                component="main_window"
            )
    
    def _create_status_bar(self):
        """Create the status bar at the bottom of the window."""
        self.status_frame = ttk.Frame(self.root)
        self.status_frame.grid(row=1, column=0, sticky="ew", padx=5, pady=(0, 5))
        self.status_frame.grid_columnconfigure(1, weight=1)
        
        # Status text
        self.status_text = ttk.Label(self.status_frame, text="Ready")
        self.status_text.grid(row=0, column=0, sticky="w")
        
        # Error status indicator
        self.error_status_widget = ErrorStatusWidget(self.status_frame, mode="bar")
        self.error_status_widget.grid(row=0, column=1, padx=5, sticky="ew")
        
        # Connection info
        self.connection_info = ttk.Label(self.status_frame, text="0 active, 0 total")
        self.connection_info.grid(row=0, column=2, sticky="e", padx=(5, 0))
        
        # Separator
        ttk.Separator(self.status_frame, orient="vertical").grid(row=0, column=3, sticky="ns", padx=5)
    
    def _setup_keyboard_shortcuts(self):
        """Set up keyboard shortcuts for the application."""
        # File operations
        self.root.bind("<Control-o>", lambda e: self._load_pac_file())
        self.root.bind("<Control-s>", lambda e: self._save_pac_file())
        self.root.bind("<Control-e>", lambda e: self._export_logs())
        self.root.bind("<Control-q>", lambda e: self._on_window_close())
        
        # Proxy operations
        self.root.bind("<F5>", lambda e: self._start_proxy())
        self.root.bind("<F6>", lambda e: self._stop_proxy())
        
        # View operations
        self.root.bind("<Control-l>", lambda e: self._clear_logs())
        self.root.bind("<F5>", lambda e: self._refresh_view())
    
    def _start_proxy(self):
        """Start the proxy service."""
        try:
            self.logger.info("Starting proxy service...")
            self._update_status("Starting proxy...")
            
            if self.start_proxy_callback:
                # Run proxy start in background thread to avoid blocking UI
                threading.Thread(
                    target=self._start_proxy_thread,
                    daemon=True
                ).start()
            else:
                self.logger.warning("No start proxy callback configured")
                self._update_status("Error: Proxy service not configured")
                messagebox.showerror("Error", "Proxy service is not properly configured.")
        
        except Exception as e:
            self.logger.error(f"Failed to start proxy: {e}")
            self._update_status("Failed to start proxy")
            messagebox.showerror("Error", f"Failed to start proxy service:\n{str(e)}")
    
    def _start_proxy_thread(self):
        """Start proxy in background thread."""
        try:
            if self.start_proxy_callback:
                # Get current configuration
                config = self._get_proxy_configuration()
                
                # Start proxy with configuration
                success = self.start_proxy_callback(config)
                if success:
                    # Update UI in main thread
                    self.root.after(0, self._on_proxy_started)
                else:
                    self.root.after(0, lambda: self._on_proxy_start_failed("Failed to start proxy service"))
        except Exception as e:
            self.root.after(0, lambda: self._on_proxy_start_failed(str(e)))
    
    def _on_proxy_started(self):
        """Handle successful proxy start."""
        self.start_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self._update_status("Proxy started successfully")
        self.logger.info("Proxy service started successfully")
    
    def _on_proxy_start_failed(self, error_msg: str):
        """Handle failed proxy start."""
        self._update_status("Failed to start proxy")
        self.logger.error(f"Failed to start proxy: {error_msg}")
        
        # Handle error through error manager
        self.error_manager.handle_global_error(
            category=ErrorCategory.PROXY,
            severity=ErrorSeverity.HIGH,
            message="Failed to start proxy service",
            details=error_msg,
            component="main_window"
        )
    
    def _stop_proxy(self):
        """Stop the proxy service."""
        try:
            self.logger.info("Stopping proxy service...")
            self._update_status("Stopping proxy...")
            
            if self.stop_proxy_callback:
                # Run proxy stop in background thread
                threading.Thread(
                    target=self._stop_proxy_thread,
                    daemon=True
                ).start()
            else:
                self.logger.warning("No stop proxy callback configured")
                self._update_status("Error: Proxy service not configured")
        
        except Exception as e:
            self.logger.error(f"Failed to stop proxy: {e}")
            self._update_status("Failed to stop proxy")
            messagebox.showerror("Error", f"Failed to stop proxy service:\n{str(e)}")
    
    def _stop_proxy_thread(self):
        """Stop proxy in background thread."""
        try:
            if self.stop_proxy_callback:
                success = self.stop_proxy_callback()
                if success:
                    self.root.after(0, self._on_proxy_stopped)
                else:
                    self.root.after(0, lambda: self._on_proxy_stop_failed("Unknown error"))
        except Exception as e:
            self.root.after(0, lambda: self._on_proxy_stop_failed(str(e)))
    
    def _on_proxy_stopped(self):
        """Handle successful proxy stop."""
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self._update_status("Proxy stopped")
        self.logger.info("Proxy service stopped successfully")
    
    def _on_proxy_stop_failed(self, error_msg: str):
        """Handle failed proxy stop."""
        self._update_status("Failed to stop proxy")
        self.logger.error(f"Failed to stop proxy: {error_msg}")
        
        # Handle error through error manager
        self.error_manager.handle_global_error(
            category=ErrorCategory.PROXY,
            severity=ErrorSeverity.HIGH,
            message="Failed to stop proxy service",
            details=error_msg,
            component="main_window"
        )
    
    def _restart_proxy_with_config(self, pac_config):
        """Restart proxy with new PAC configuration."""
        try:
            self.logger.info("Restarting proxy with new PAC configuration...")
            self._update_status("Restarting proxy...")
            
            # Store the new PAC config
            self._pending_pac_config = pac_config
            
            # Stop proxy first
            if self.proxy_controller and self.proxy_controller.is_running():
                threading.Thread(
                    target=self._restart_proxy_thread,
                    daemon=True
                ).start()
            else:
                # If proxy is not running, just start it with new config
                self._start_proxy_with_pac_config(pac_config)
                
        except Exception as e:
            self.logger.error(f"Failed to restart proxy: {e}")
            self._update_status("Failed to restart proxy")
            messagebox.showerror("Error", f"Failed to restart proxy:\n{str(e)}")
    
    def _restart_proxy_thread(self):
        """Restart proxy in background thread."""
        try:
            # Stop proxy first
            if self.stop_proxy_callback:
                success = self.stop_proxy_callback()
                if success:
                    # Wait a moment for cleanup
                    import time
                    time.sleep(1)
                    
                    # Start proxy with new config
                    self.root.after(0, lambda: self._start_proxy_with_pac_config(self._pending_pac_config))
                else:
                    self.root.after(0, lambda: self._on_restart_failed("Failed to stop proxy"))
            else:
                self.root.after(0, lambda: self._on_restart_failed("No stop callback configured"))
        except Exception as e:
            self.root.after(0, lambda: self._on_restart_failed(str(e)))
    
    def _start_proxy_with_pac_config(self, pac_config):
        """Start proxy with specific PAC configuration."""
        try:
            # Update PAC configuration
            if self.pac_config_panel:
                self.pac_config_panel.pac_config = pac_config
            
            # Start proxy
            self._start_proxy()
            
        except Exception as e:
            self.logger.error(f"Failed to start proxy with PAC config: {e}")
            self._on_restart_failed(str(e))
    
    def _on_restart_failed(self, error_msg: str):
        """Handle failed proxy restart."""
        self._update_status("Failed to restart proxy")
        self.logger.error(f"Proxy restart failed: {error_msg}")
        messagebox.showerror("Restart Failed", f"Failed to restart proxy:\n{error_msg}")
    
    def _load_saved_pac_configuration(self):
        """Load saved PAC configuration from persistent storage."""
        try:
            if self.config_manager and self.pac_config_panel:
                saved_config = self.config_manager.load_pac_configuration()
                if saved_config:
                    self.pac_config_panel.set_pac_configuration(saved_config)
                    self.logger.info(f"Loaded saved PAC configuration: {saved_config.source_type}")
                else:
                    self.logger.info("No saved PAC configuration found, using default")
        except Exception as e:
            self.logger.error(f"Failed to load saved PAC configuration: {e}")
    
    def _load_pac_file(self):
        """Load a PAC file through the PAC configuration panel."""
        if self.pac_config_panel:
            # Switch to PAC configuration tab
            for i in range(self.notebook.index("end")):
                if self.notebook.tab(i, "text") == "PAC Configuration":
                    self.notebook.select(i)
                    break
            
            # Trigger file loading in PAC panel
            file_path = filedialog.askopenfilename(
                title="Load PAC File",
                filetypes=[("PAC files", "*.pac"), ("JavaScript files", "*.js"), ("All files", "*.*")]
            )
            if file_path:
                self.pac_config_panel.path_var.set(file_path)
                self.pac_config_panel.source_type_var.set("file")
                self.pac_config_panel._on_source_type_changed()
                self.pac_config_panel._load_from_source()
                self.logger.info(f"Loading PAC file: {file_path}")
        else:
            messagebox.showerror("Error", "PAC configuration panel is not available.")
    
    def _save_pac_file(self):
        """Save a PAC file through the PAC configuration panel."""
        if self.pac_config_panel:
            # Switch to PAC configuration tab
            for i in range(self.notebook.index("end")):
                if self.notebook.tab(i, "text") == "PAC Configuration":
                    self.notebook.select(i)
                    break
            
            # Trigger file saving in PAC panel
            self.pac_config_panel._save_pac_file()
        else:
            messagebox.showerror("Error", "PAC configuration panel is not available.")
    
    def _export_logs(self):
        """Export monitoring logs through the monitoring view."""
        if self.monitoring_view:
            # Switch to monitoring tab
            for i in range(self.notebook.index("end")):
                if self.notebook.tab(i, "text") == "Request Monitoring":
                    self.notebook.select(i)
                    break
            
            # Export logs
            file_path = filedialog.asksaveasfilename(
                title="Export Logs",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("CSV files", "*.csv"), ("All files", "*.*")]
            )
            if file_path:
                try:
                    self._export_monitoring_logs(file_path)
                    self._update_status(f"Exported logs to: {Path(file_path).name}")
                    messagebox.showinfo("Success", f"Logs exported successfully to:\n{file_path}")
                except Exception as e:
                    self.logger.error(f"Failed to export logs: {e}")
                    
                    # Handle error through error manager
                    self.error_manager.handle_global_error(
                        category=ErrorCategory.SYSTEM,
                        severity=ErrorSeverity.MEDIUM,
                        message="Failed to export logs",
                        details=str(e),
                        context={"file_path": file_path},
                        component="main_window"
                    )
        else:
            messagebox.showerror("Error", "Monitoring view is not available.")
    
    def _export_error_report(self):
        """Export comprehensive error report."""
        try:
            file_path = filedialog.asksaveasfilename(
                title="Export Error Report",
                defaultextension=".html",
                filetypes=[
                    ("HTML files", "*.html"),
                    ("JSON files", "*.json"),
                    ("CSV files", "*.csv"),
                    ("All files", "*.*")
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
                error_reporter = get_error_reporter()
                output_file = error_reporter.generate_error_report(Path(file_path), format)
                
                self._update_status(f"Error report exported: {Path(file_path).name}")
                messagebox.showinfo("Export Complete", f"Error report exported successfully to:\n{output_file}")
        
        except Exception as e:
            self.logger.error(f"Failed to export error report: {e}")
            
            # Handle error through error manager
            self.error_manager.handle_global_error(
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.MEDIUM,
                message="Failed to export error report",
                details=str(e),
                context={"file_path": file_path if 'file_path' in locals() else None},
                component="main_window"
            )
    
    def _clear_logs(self):
        """Clear monitoring logs through the monitoring view."""
        if self.monitoring_view:
            self.monitoring_view.clear_logs()
            self._update_status("Logs cleared")
        else:
            messagebox.showerror("Error", "Monitoring view is not available.")
    
    def _refresh_view(self):
        """Refresh the current view."""
        self.logger.info("Refreshing view")
        self._update_status("View refreshed")
        # TODO: Implement view refresh in future tasks
    
    def _toggle_auto_scroll(self):
        """Toggle auto-scroll for logs (placeholder implementation)."""
        self.logger.info("Toggled auto-scroll")
        # TODO: Implement auto-scroll toggle in future tasks
    
    def _show_about(self):
        """Show the about dialog."""
        about_text = """px UI Client v1.0.0

A graphical user interface for the px proxy library.

Built with Python and Tkinter.
Based on the px library by genotrance.

© 2024 px-ui-client"""
        
        messagebox.showinfo("About px UI Client", about_text)
    
    def _update_status(self, message: str):
        """Update the status bar message."""
        self.status_text.config(text=message)
        self.root.update_idletasks()
    
    def _update_proxy_status(self, status: ProxyStatus):
        """Update the proxy status display."""
        self._proxy_status = status
        
        # Update status label with color coding
        status_text = f"Proxy Status: {status.get_status_text()}"
        self.status_label.config(text=status_text)
        
        # Color code the status label
        if status.is_running:
            self.status_label.config(foreground="green")
        else:
            self.status_label.config(foreground="red")
        
        # Update connection info in status bar
        self.connection_info.config(text=status.get_connection_info())
        
        # Update button states
        if status.is_running:
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.proxy_menu.entryconfig("Start Proxy", state="disabled")
            self.proxy_menu.entryconfig("Stop Proxy", state="normal")
        else:
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")
            self.proxy_menu.entryconfig("Start Proxy", state="normal")
            self.proxy_menu.entryconfig("Stop Proxy", state="disabled")
        
        # Update status bar with detailed information
        if status.is_running:
            mode_text = status.get_mode_display_name()
            self._update_status(f"Proxy running on {status.get_listen_url()} ({mode_text})")
        else:
            self._update_status("Proxy stopped - Ready to start")
        
        # Update window title to reflect proxy status
        base_title = "px UI Client"
        if status.is_running:
            self.root.title(f"{base_title} - Running on port {status.port}")
        else:
            self.root.title(base_title)
    
    def _on_window_close(self):
        """Handle window close event with proper cleanup."""
        if self._is_shutting_down:
            return
        
        self._is_shutting_down = True
        self.logger.info("Application shutdown initiated")
        
        try:
            # Stop proxy if running
            if self._proxy_status and self._proxy_status.is_running:
                self.logger.info("Stopping proxy before shutdown...")
                if self.stop_proxy_callback:
                    self.stop_proxy_callback()
            
            # Perform cleanup
            self._cleanup()
            
            # Close the window
            self.root.quit()
            self.root.destroy()
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
            # Force close if cleanup fails
            try:
                self.root.destroy()
            except:
                pass
    
    def _get_proxy_configuration(self) -> dict:
        """
        Get current proxy configuration from UI settings.
        
        Returns:
            Configuration dictionary for proxy
        """
        # Load configuration from config manager
        settings = self.config_manager.load_settings()
        
        config = {
            'listen_address': '127.0.0.1',  # Default to localhost for security
            'port': settings.proxy_port if hasattr(settings, 'proxy_port') else 3128,
            'mode': 'manual'  # Default mode
        }
        
        # Add PAC configuration if available and valid
        if self.pac_config_panel:
            pac_config = self.pac_config_panel.get_pac_configuration()
            if pac_config and pac_config.is_valid and pac_config.content and pac_config.content.strip():
                config['mode'] = 'pac'
                config['pac_config'] = pac_config
                self.logger.info(f"Using PAC mode with content length: {len(pac_config.content)}")
            else:
                self.logger.info("PAC config not valid or empty, using manual mode")
                config['mode'] = 'manual'
        
        # Add no proxy configuration if available
        if self.no_proxy_panel:
            no_proxy_config = self.no_proxy_panel.get_configuration()
            if no_proxy_config:
                config['no_proxy'] = no_proxy_config.to_px_format()
        
        # Add NTLM configuration if available
        if self.ntlm_config_panel:
            ntlm_config = self.ntlm_config_panel.get_configuration()
            if ntlm_config:
                # Merge NTLM configuration into main config
                config.update(ntlm_config)
                self.logger.info(f"Using NTLM configuration: {ntlm_config}")
        
        return config
    
    def _export_monitoring_logs(self, file_path: str):
        """Export monitoring logs to a file."""
        if not self.monitoring_view:
            raise ValueError("Monitoring view is not available")
        
        entries = self.monitoring_view.entries
        if not entries:
            raise ValueError("No monitoring data to export")
        
        # Determine file format based on extension
        file_ext = Path(file_path).suffix.lower()
        
        with open(file_path, 'w', encoding='utf-8') as f:
            if file_ext == '.csv':
                # CSV format
                f.write("Timestamp,Method,URL,Proxy Decision,Status Code,Response Time (ms),Error Message\n")
                for entry in entries.values():
                    timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    method = entry.method
                    url = entry.url.replace('"', '""')  # Escape quotes for CSV
                    proxy = entry.proxy_decision.replace('"', '""')
                    status = str(entry.status_code) if entry.status_code is not None else ""
                    response_time = str(entry.response_time) if entry.response_time is not None else ""
                    error = entry.error_message.replace('"', '""') if entry.error_message else ""
                    
                    f.write(f'"{timestamp}","{method}","{url}","{proxy}","{status}","{response_time}","{error}"\n')
            else:
                # Text format
                f.write("px UI Client - Request Monitoring Log\n")
                f.write("=" * 50 + "\n\n")
                
                for entry in sorted(entries.values(), key=lambda x: x.timestamp):
                    f.write(f"Timestamp: {entry.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}\n")
                    f.write(f"Method: {entry.method}\n")
                    f.write(f"URL: {entry.url}\n")
                    f.write(f"Proxy Decision: {entry.proxy_decision}\n")
                    if entry.status_code is not None:
                        f.write(f"Status Code: {entry.status_code}\n")
                    if entry.response_time is not None:
                        f.write(f"Response Time: {entry.response_time:.2f} ms\n")
                    if entry.error_message:
                        f.write(f"Error: {entry.error_message}\n")
                    f.write("-" * 30 + "\n\n")
        
        self.logger.info(f"Exported {len(entries)} log entries to {file_path}")
    
    def _cleanup(self):
        """Perform application cleanup."""
        self.logger.info("Performing application cleanup")
        
        # Cleanup event system
        if hasattr(self, 'event_system') and self.event_system:
            try:
                self.event_system.stop()
            except Exception as e:
                self.logger.error(f"Error stopping event system: {e}")
        
        # Cleanup UI components
        if self.monitoring_view:
            try:
                # Stop any background threads in monitoring view
                if hasattr(self.monitoring_view, 'performance_monitor'):
                    self.monitoring_view.performance_monitor.stop_monitoring()
            except Exception as e:
                self.logger.error(f"Error cleaning up monitoring view: {e}")
    
    def run(self):
        """Start the main application loop."""
        try:
            self.logger.info("Starting main application loop")
            self.root.mainloop()
        except KeyboardInterrupt:
            self.logger.info("Application interrupted by user")
            self._on_window_close()
        except Exception as e:
            self.logger.error(f"Unexpected error in main loop: {e}")
            messagebox.showerror("Fatal Error", f"An unexpected error occurred:\n{str(e)}")
            self._on_window_close()
    
    def set_proxy_callbacks(self, start_callback: Callable, stop_callback: Callable, proxy_controller=None):
        """Set callbacks for proxy control operations."""
        self.start_proxy_callback = start_callback
        self.stop_proxy_callback = stop_callback
        
        # Set proxy controller if provided
        if proxy_controller:
            self.proxy_controller = proxy_controller
            
            # Update PAC config panel with proxy controller reference
            if self.pac_config_panel:
                self.pac_config_panel.proxy_controller = proxy_controller
        
        self.logger.info("Proxy control callbacks configured")
    
    def update_proxy_status(self, status: ProxyStatus):
        """Public method to update proxy status from external components."""
        self.root.after(0, lambda: self._update_proxy_status(status))
    
    def show_error(self, title: str, message: str):
        """Show an error dialog."""
        self.root.after(0, lambda: messagebox.showerror(title, message))
    
    def show_info(self, title: str, message: str):
        """Show an info dialog."""
        self.root.after(0, lambda: messagebox.showinfo(title, message))
    
    # Public API methods for accessing integrated components
    
    def get_event_system(self) -> EventSystem:
        """Get the event system for external components."""
        return self.event_system
    
    def get_pac_configuration(self):
        """Get current PAC configuration from the PAC panel."""
        if self.pac_config_panel:
            return self.pac_config_panel.get_pac_configuration()
        return None
    
    def get_no_proxy_configuration(self):
        """Get current no proxy configuration from the no proxy panel."""
        if self.no_proxy_panel:
            return self.no_proxy_panel.get_configuration()
        return None
    
    def get_monitoring_stats(self) -> dict:
        """Get monitoring statistics."""
        if self.monitoring_view:
            return {
                'total_entries': self.monitoring_view.get_entry_count(),
                'filtered_entries': self.monitoring_view.get_filtered_count()
            }
        return {'total_entries': 0, 'filtered_entries': 0}
    
    def switch_to_tab(self, tab_name: str):
        """Switch to a specific tab by name."""
        if not hasattr(self, 'notebook'):
            return False
        
        for i in range(self.notebook.index("end")):
            if self.notebook.tab(i, "text") == tab_name:
                self.notebook.select(i)
                return True
        return False
    
    def update_connection_info(self, active_connections: int, total_requests: int):
        """Update connection information in the status bar."""
        self.connection_info.config(text=f"{active_connections} active, {total_requests} total")