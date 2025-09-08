"""
NTLM Authentication Configuration Panel

This module provides a UI panel for configuring NTLM authentication settings
for the px proxy server.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
from typing import Dict, Any, Callable, Optional


class NTLMConfigPanel(ttk.Frame):
    """
    NTLM Authentication Configuration Panel
    
    Provides UI controls for configuring NTLM authentication settings
    including upstream proxy, authentication methods, and domain settings.
    """
    
    def __init__(self, parent, config_manager=None, **kwargs):
        """
        Initialize NTLM configuration panel.
        
        Args:
            parent: Parent widget
            config_manager: Configuration manager instance
            **kwargs: Additional keyword arguments for Frame
        """
        super().__init__(parent, **kwargs)
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        
        # Configuration change callback
        self._config_change_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        
        # Initialize variables
        self._init_variables()
        
        # Create UI widgets
        self._create_widgets()
        
        # Load current configuration
        self._load_configuration()
    
    def _init_variables(self):
        """Initialize tkinter variables."""
        # NTLM enable/disable
        self.enable_ntlm_var = tk.BooleanVar(value=True)
        
        # Authentication method
        self.auth_method_var = tk.StringVar(value="ANY")
        
        # Upstream proxy settings
        self.upstream_proxy_var = tk.StringVar()
        self.proxy_port_var = tk.StringVar(value="8080")
        
        # Domain and user settings
        self.domain_var = tk.StringVar()
        self.username_var = tk.StringVar()
        
        # Client authentication
        self.client_auth_var = tk.StringVar(value="NONE")
        
        # Auto-detect settings
        self.auto_detect_domain_var = tk.BooleanVar(value=True)
        
        # Bind change events
        self.enable_ntlm_var.trace_add('write', self._on_config_change)
        self.auth_method_var.trace_add('write', self._on_config_change)
        self.upstream_proxy_var.trace_add('write', self._on_config_change)
        self.proxy_port_var.trace_add('write', self._on_config_change)
        self.domain_var.trace_add('write', self._on_config_change)
        self.username_var.trace_add('write', self._on_config_change)
        self.client_auth_var.trace_add('write', self._on_config_change)
        self.auto_detect_domain_var.trace_add('write', self._on_config_change)
    
    def _create_widgets(self):
        """Create and layout UI widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # NTLM Enable Section
        self._create_enable_section(main_frame)
        
        # Authentication Method Section
        self._create_auth_method_section(main_frame)
        
        # Upstream Proxy Section
        self._create_upstream_proxy_section(main_frame)
        
        # Domain Settings Section
        self._create_domain_section(main_frame)
        
        # Client Authentication Section
        self._create_client_auth_section(main_frame)
        
        # Status and Help Section
        self._create_status_section(main_frame)
    
    def _create_enable_section(self, parent):
        """Create NTLM enable/disable section."""
        enable_frame = ttk.LabelFrame(parent, text="NTLM Authentication", padding=10)
        enable_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Checkbutton(
            enable_frame,
            text="Enable NTLM Authentication",
            variable=self.enable_ntlm_var,
            command=self._on_enable_change
        ).pack(anchor="w")
        
        # Help text
        help_text = ttk.Label(
            enable_frame,
            text="Enable automatic NTLM authentication for enterprise proxy servers",
            font=("TkDefaultFont", 8),
            foreground="gray"
        )
        help_text.pack(anchor="w", pady=(5, 0))
    
    def _create_auth_method_section(self, parent):
        """Create authentication method selection section."""
        self.auth_frame = ttk.LabelFrame(parent, text="Authentication Method", padding=10)
        self.auth_frame.pack(fill="x", pady=(0, 10))
        
        # Authentication method selection
        ttk.Label(self.auth_frame, text="Authentication Method:").pack(anchor="w")
        
        auth_combo = ttk.Combobox(
            self.auth_frame,
            textvariable=self.auth_method_var,
            values=["ANY", "NTLM", "NEGOTIATE", "DIGEST", "BASIC", "NONE"],
            state="readonly",
            width=20
        )
        auth_combo.pack(anchor="w", pady=(5, 0))
        
        # Help text for auth methods
        auth_help = ttk.Label(
            self.auth_frame,
            text="ANY: All methods (recommended), NTLM: NTLM only, NONE: No authentication",
            font=("TkDefaultFont", 8),
            foreground="gray",
            wraplength=400
        )
        auth_help.pack(anchor="w", pady=(5, 0))
    
    def _create_upstream_proxy_section(self, parent):
        """Create upstream proxy configuration section."""
        self.proxy_frame = ttk.LabelFrame(parent, text="Upstream Proxy Server", padding=10)
        self.proxy_frame.pack(fill="x", pady=(0, 10))
        
        # Proxy server input
        ttk.Label(self.proxy_frame, text="Proxy Server:").pack(anchor="w")
        proxy_entry = ttk.Entry(self.proxy_frame, textvariable=self.upstream_proxy_var, width=40)
        proxy_entry.pack(fill="x", pady=(5, 0))
        
        # Port input
        port_frame = ttk.Frame(self.proxy_frame)
        port_frame.pack(fill="x", pady=(5, 0))
        
        ttk.Label(port_frame, text="Port:").pack(side="left")
        port_entry = ttk.Entry(port_frame, textvariable=self.proxy_port_var, width=10)
        port_entry.pack(side="left", padx=(5, 0))
        
        # Help text
        proxy_help = ttk.Label(
            self.proxy_frame,
            text="Example: proxy.company.com (Enterprise proxy server that requires NTLM authentication)",
            font=("TkDefaultFont", 8),
            foreground="gray",
            wraplength=400
        )
        proxy_help.pack(anchor="w", pady=(5, 0))
    
    def _create_domain_section(self, parent):
        """Create domain and user settings section."""
        self.domain_frame = ttk.LabelFrame(parent, text="Domain Settings", padding=10)
        self.domain_frame.pack(fill="x", pady=(0, 10))
        
        # Auto-detect domain
        ttk.Checkbutton(
            self.domain_frame,
            text="Auto-detect domain (recommended)",
            variable=self.auto_detect_domain_var,
            command=self._on_auto_detect_change
        ).pack(anchor="w")
        
        # Manual domain input
        self.manual_domain_frame = ttk.Frame(self.domain_frame)
        self.manual_domain_frame.pack(fill="x", pady=(10, 0))
        
        ttk.Label(self.manual_domain_frame, text="Domain:").pack(anchor="w")
        self.domain_entry = ttk.Entry(self.manual_domain_frame, textvariable=self.domain_var, width=30)
        self.domain_entry.pack(anchor="w", pady=(5, 0))
        
        ttk.Label(self.manual_domain_frame, text="Username (optional):").pack(anchor="w", pady=(10, 0))
        self.username_entry = ttk.Entry(self.manual_domain_frame, textvariable=self.username_var, width=30)
        self.username_entry.pack(anchor="w", pady=(5, 0))
        
        # Help text
        domain_help = ttk.Label(
            self.domain_frame,
            text="Leave username empty to use current Windows user credentials",
            font=("TkDefaultFont", 8),
            foreground="gray"
        )
        domain_help.pack(anchor="w", pady=(5, 0))
    
    def _create_client_auth_section(self, parent):
        """Create client authentication section."""
        self.client_frame = ttk.LabelFrame(parent, text="Client Authentication", padding=10)
        self.client_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(self.client_frame, text="Client Authentication:").pack(anchor="w")
        
        client_combo = ttk.Combobox(
            self.client_frame,
            textvariable=self.client_auth_var,
            values=["NONE", "NTLM", "NEGOTIATE", "DIGEST", "BASIC", "ANY"],
            state="readonly",
            width=20
        )
        client_combo.pack(anchor="w", pady=(5, 0))
        
        # Help text
        client_help = ttk.Label(
            self.client_frame,
            text="NONE: No client authentication required (recommended for UI clients)",
            font=("TkDefaultFont", 8),
            foreground="gray"
        )
        client_help.pack(anchor="w", pady=(5, 0))
    
    def _create_status_section(self, parent):
        """Create status and help section."""
        status_frame = ttk.LabelFrame(parent, text="Status & Help", padding=10)
        status_frame.pack(fill="x", pady=(0, 10))
        
        # Status label
        self.status_label = ttk.Label(
            status_frame,
            text="NTLM authentication ready",
            foreground="green"
        )
        self.status_label.pack(anchor="w")
        
        # Help button
        help_button = ttk.Button(
            status_frame,
            text="Help & Troubleshooting",
            command=self._show_help
        )
        help_button.pack(anchor="w", pady=(10, 0))
    
    def _on_enable_change(self):
        """Handle NTLM enable/disable change."""
        enabled = self.enable_ntlm_var.get()
        
        # Enable/disable all child frames
        state = "normal" if enabled else "disabled"
        
        for frame in [self.auth_frame, self.proxy_frame, self.domain_frame, self.client_frame]:
            for child in frame.winfo_children():
                if hasattr(child, 'configure'):
                    try:
                        child.configure(state=state)
                    except tk.TclError:
                        pass  # Some widgets don't support state
        
        # Update status
        if enabled:
            self.status_label.configure(text="NTLM authentication enabled", foreground="green")
        else:
            self.status_label.configure(text="NTLM authentication disabled", foreground="red")
        
        self._on_config_change()
    
    def _on_auto_detect_change(self):
        """Handle auto-detect domain change."""
        auto_detect = self.auto_detect_domain_var.get()
        
        # Enable/disable manual domain inputs
        state = "disabled" if auto_detect else "normal"
        self.domain_entry.configure(state=state)
        self.username_entry.configure(state=state)
        
        if auto_detect:
            # Clear manual inputs when auto-detect is enabled
            self.domain_var.set("")
            self.username_var.set("")
    
    def _on_config_change(self, *args):
        """Handle configuration change."""
        if self._config_change_callback:
            config = self.get_configuration()
            self._config_change_callback(config)
    
    def _load_configuration(self):
        """Load configuration from config manager."""
        if not self.config_manager:
            return
        
        try:
            config = self.config_manager.get_proxy_config()
            
            # Load NTLM settings
            self.enable_ntlm_var.set(config.get('enable_ntlm', True))
            self.auth_method_var.set(config.get('auth_method', 'ANY'))
            
            # Load upstream proxy
            upstream_proxy = config.get('upstream_proxy', '')
            if ':' in upstream_proxy:
                host, port = upstream_proxy.rsplit(':', 1)
                self.upstream_proxy_var.set(host)
                self.proxy_port_var.set(port)
            else:
                self.upstream_proxy_var.set(upstream_proxy)
            
            # Load domain settings
            self.domain_var.set(config.get('domain', ''))
            self.username_var.set(config.get('username', ''))
            self.auto_detect_domain_var.set(config.get('auto_detect_domain', True))
            
            # Load client auth
            client_auth = config.get('client_auth', ['NONE'])
            if isinstance(client_auth, list) and client_auth:
                self.client_auth_var.set(client_auth[0])
            
            # Update UI state
            self._on_enable_change()
            self._on_auto_detect_change()
            
        except Exception as e:
            self.logger.error(f"Failed to load NTLM configuration: {e}")
    
    def get_configuration(self) -> Dict[str, Any]:
        """
        Get current NTLM configuration.
        
        Returns:
            Dictionary with NTLM configuration settings
        """
        # Build upstream proxy string
        upstream_proxy = ""
        if self.upstream_proxy_var.get().strip():
            host = self.upstream_proxy_var.get().strip()
            port = self.proxy_port_var.get().strip() or "8080"
            upstream_proxy = f"{host}:{port}"
        
        config = {
            'enable_ntlm': self.enable_ntlm_var.get(),
            'auth_method': self.auth_method_var.get(),
            'upstream_proxy': upstream_proxy,
            'domain': self.domain_var.get().strip() if not self.auto_detect_domain_var.get() else "",
            'username': self.username_var.get().strip() if not self.auto_detect_domain_var.get() else "",
            'client_auth': [self.client_auth_var.get()],
            'auto_detect_domain': self.auto_detect_domain_var.get()
        }
        
        return config
    
    def set_configuration(self, config: Dict[str, Any]):
        """
        Set NTLM configuration.
        
        Args:
            config: Dictionary with NTLM configuration settings
        """
        try:
            # Set NTLM settings
            self.enable_ntlm_var.set(config.get('enable_ntlm', True))
            self.auth_method_var.set(config.get('auth_method', 'ANY'))
            
            # Set upstream proxy
            upstream_proxy = config.get('upstream_proxy', '')
            if ':' in upstream_proxy:
                host, port = upstream_proxy.rsplit(':', 1)
                self.upstream_proxy_var.set(host)
                self.proxy_port_var.set(port)
            else:
                self.upstream_proxy_var.set(upstream_proxy)
                self.proxy_port_var.set("8080")
            
            # Set domain settings
            self.domain_var.set(config.get('domain', ''))
            self.username_var.set(config.get('username', ''))
            self.auto_detect_domain_var.set(config.get('auto_detect_domain', True))
            
            # Set client auth
            client_auth = config.get('client_auth', ['NONE'])
            if isinstance(client_auth, list) and client_auth:
                self.client_auth_var.set(client_auth[0])
            
            # Update UI state
            self._on_enable_change()
            self._on_auto_detect_change()
            
        except Exception as e:
            self.logger.error(f"Failed to set NTLM configuration: {e}")
    
    def set_config_change_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """
        Set callback for configuration changes.
        
        Args:
            callback: Function to call when configuration changes
        """
        self._config_change_callback = callback
    
    def validate_configuration(self) -> tuple[bool, str]:
        """
        Validate current NTLM configuration.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.enable_ntlm_var.get():
            return True, ""  # No validation needed if disabled
        
        # Validate upstream proxy
        upstream_proxy = self.upstream_proxy_var.get().strip()
        if not upstream_proxy:
            return False, "Upstream proxy server is required when NTLM is enabled"
        
        # Validate port
        port = self.proxy_port_var.get().strip()
        if port:
            try:
                port_num = int(port)
                if not (1 <= port_num <= 65535):
                    return False, "Port must be between 1 and 65535"
            except ValueError:
                return False, "Port must be a valid number"
        
        # Validate domain if not auto-detect
        if not self.auto_detect_domain_var.get():
            domain = self.domain_var.get().strip()
            if not domain:
                return False, "Domain is required when auto-detect is disabled"
        
        return True, ""
    
    def _show_help(self):
        """Show NTLM help and troubleshooting information."""
        help_text = """
NTLM Authentication Help

What is NTLM?
NTLM (NT LAN Manager) is a Microsoft authentication protocol used in enterprise environments to authenticate users to proxy servers and other network resources.

Configuration Tips:
1. Enable NTLM Authentication: Check this to enable automatic NTLM authentication
2. Authentication Method: 
   - ANY: Supports all methods (recommended)
   - NTLM: NTLM authentication only
   - NEGOTIATE: Kerberos/NTLM negotiation
3. Upstream Proxy: Your company's proxy server (e.g., proxy.company.com:8080)
4. Domain Settings: 
   - Auto-detect: Uses your Windows domain credentials (recommended)
   - Manual: Specify domain and username manually

Troubleshooting:
- Ensure you're on a Windows domain-joined computer
- Check that the upstream proxy server supports NTLM
- Verify proxy server address and port are correct
- Try "ANY" authentication method if specific methods fail
- Contact your IT administrator for proxy server details

Common Enterprise Proxy Ports:
- 8080 (most common)
- 3128
- 8888
- 80
        """
        
        messagebox.showinfo("NTLM Authentication Help", help_text.strip())


if __name__ == "__main__":
    # Test the NTLM config panel
    root = tk.Tk()
    root.title("NTLM Configuration Test")
    root.geometry("600x700")
    
    panel = NTLMConfigPanel(root)
    panel.pack(fill="both", expand=True)
    
    def on_config_change(config):
        print("Configuration changed:", config)
    
    panel.set_config_change_callback(on_config_change)
    
    root.mainloop()