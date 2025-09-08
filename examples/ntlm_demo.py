#!/usr/bin/env python3
"""
NTLM Authentication Demo

This demo shows how to use the px UI client with NTLM authentication
for enterprise proxy environments.
"""

import sys
import os
import logging
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from px_ui.ui.ntlm_config_panel import NTLMConfigPanel
from px_ui.config.config_manager import ConfigManager
from px_ui.proxy.configuration_bridge import PxConfigurationBridge
from px_ui.communication.event_system import EventSystem
from px_ui.models.proxy_status import ProxyStatus


class NTLMDemo:
    """NTLM Authentication Demo Application."""
    
    def __init__(self):
        """Initialize the demo application."""
        self.setup_logging()
        
        # Create main window
        self.root = tk.Tk()
        self.root.title("px UI Client - NTLM Authentication Demo")
        self.root.geometry("800x700")
        
        # Initialize components
        self.config_manager = ConfigManager()
        self.event_system = EventSystem()
        self.proxy_bridge = PxConfigurationBridge(self.event_system)
        
        # UI components
        self.ntlm_panel = None
        self.status_label = None
        self.start_button = None
        self.stop_button = None
        
        # Create UI
        self.create_ui()
        
        # Set up callbacks
        self.proxy_bridge.add_status_callback(self.on_proxy_status_change)
    
    def setup_logging(self):
        """Set up logging for the demo."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(__name__)
    
    def create_ui(self):
        """Create the demo UI."""
        # Main container
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        # Title
        title_label = ttk.Label(
            main_frame, 
            text="px UI Client - NTLM Authentication Demo",
            font=("TkDefaultFont", 16, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Description
        desc_text = """
This demo shows how to configure and use NTLM authentication with the px UI client.
Configure your enterprise proxy settings below and start the proxy to test NTLM authentication.
        """.strip()
        
        desc_label = ttk.Label(main_frame, text=desc_text, justify="center")
        desc_label.pack(pady=(0, 20))
        
        # NTLM Configuration Panel
        config_frame = ttk.LabelFrame(main_frame, text="NTLM Configuration", padding=10)
        config_frame.pack(fill="both", expand=True, pady=(0, 20))
        
        self.ntlm_panel = NTLMConfigPanel(config_frame, self.config_manager)
        self.ntlm_panel.pack(fill="both", expand=True)
        self.ntlm_panel.set_config_change_callback(self.on_ntlm_config_change)
        
        # Control Panel
        control_frame = ttk.LabelFrame(main_frame, text="Proxy Control", padding=10)
        control_frame.pack(fill="x", pady=(0, 20))
        
        # Buttons
        button_frame = ttk.Frame(control_frame)
        button_frame.pack(fill="x")
        
        self.start_button = ttk.Button(
            button_frame, 
            text="Start Proxy", 
            command=self.start_proxy
        )
        self.start_button.pack(side="left", padx=(0, 10))
        
        self.stop_button = ttk.Button(
            button_frame, 
            text="Stop Proxy", 
            command=self.stop_proxy,
            state="disabled"
        )
        self.stop_button.pack(side="left", padx=(0, 10))
        
        # Test button
        test_button = ttk.Button(
            button_frame, 
            text="Test Configuration", 
            command=self.test_configuration
        )
        test_button.pack(side="left", padx=(0, 10))
        
        # Help button
        help_button = ttk.Button(
            button_frame, 
            text="Help", 
            command=self.show_help
        )
        help_button.pack(side="right")
        
        # Status Panel
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding=10)
        status_frame.pack(fill="x")
        
        self.status_label = ttk.Label(
            status_frame, 
            text="Ready - Configure NTLM settings and start proxy",
            foreground="blue"
        )
        self.status_label.pack(anchor="w")
        
        # Proxy info
        self.proxy_info_label = ttk.Label(
            status_frame, 
            text="Proxy not running",
            font=("TkDefaultFont", 8)
        )
        self.proxy_info_label.pack(anchor="w", pady=(5, 0))
    
    def on_ntlm_config_change(self, config):
        """Handle NTLM configuration changes."""
        self.logger.info(f"NTLM configuration changed: {config}")
        
        # Validate configuration
        is_valid, error_msg = self.ntlm_panel.validate_configuration()
        
        if is_valid:
            self.status_label.configure(
                text="Configuration valid - Ready to start proxy",
                foreground="green"
            )
        else:
            self.status_label.configure(
                text=f"Configuration error: {error_msg}",
                foreground="red"
            )
    
    def start_proxy(self):
        """Start the proxy with NTLM configuration."""
        try:
            # Get NTLM configuration
            ntlm_config = self.ntlm_panel.get_configuration()
            
            # Validate configuration
            is_valid, error_msg = self.ntlm_panel.validate_configuration()
            if not is_valid:
                messagebox.showerror("Configuration Error", error_msg)
                return
            
            self.status_label.configure(text="Starting proxy...", foreground="orange")
            self.start_button.configure(state="disabled")
            
            # Start proxy
            success = self.proxy_bridge.start_proxy(ntlm_config)
            
            if success:
                self.status_label.configure(
                    text="Proxy started successfully with NTLM authentication",
                    foreground="green"
                )
                self.stop_button.configure(state="normal")
                
                # Show proxy info
                proxy_status = self.proxy_bridge.get_proxy_status()
                self.proxy_info_label.configure(
                    text=f"Listening on {proxy_status.get_listen_url()}"
                )
                
                # Show usage instructions
                self.show_usage_instructions(proxy_status)
                
            else:
                self.status_label.configure(
                    text="Failed to start proxy - Check logs for details",
                    foreground="red"
                )
                self.start_button.configure(state="normal")
        
        except Exception as e:
            self.logger.error(f"Error starting proxy: {e}")
            messagebox.showerror("Error", f"Failed to start proxy: {str(e)}")
            self.status_label.configure(
                text="Error starting proxy",
                foreground="red"
            )
            self.start_button.configure(state="normal")
    
    def stop_proxy(self):
        """Stop the proxy."""
        try:
            self.status_label.configure(text="Stopping proxy...", foreground="orange")
            self.stop_button.configure(state="disabled")
            
            success = self.proxy_bridge.stop_proxy()
            
            if success:
                self.status_label.configure(
                    text="Proxy stopped",
                    foreground="blue"
                )
                self.start_button.configure(state="normal")
                self.proxy_info_label.configure(text="Proxy not running")
            else:
                self.status_label.configure(
                    text="Failed to stop proxy",
                    foreground="red"
                )
                self.stop_button.configure(state="normal")
        
        except Exception as e:
            self.logger.error(f"Error stopping proxy: {e}")
            messagebox.showerror("Error", f"Failed to stop proxy: {str(e)}")
            self.stop_button.configure(state="normal")
    
    def test_configuration(self):
        """Test the NTLM configuration."""
        try:
            # Get configuration
            ntlm_config = self.ntlm_panel.get_configuration()
            
            # Validate
            is_valid, error_msg = self.ntlm_panel.validate_configuration()
            
            if is_valid:
                # Test px state configuration
                self.proxy_bridge._current_config = ntlm_config
                self.proxy_bridge._configure_px_state()
                
                messagebox.showinfo(
                    "Configuration Test", 
                    "✅ NTLM configuration is valid and ready to use!"
                )
            else:
                messagebox.showerror("Configuration Test", f"❌ Configuration error: {error_msg}")
        
        except Exception as e:
            self.logger.error(f"Error testing configuration: {e}")
            messagebox.showerror("Configuration Test", f"❌ Test failed: {str(e)}")
    
    def on_proxy_status_change(self, status: ProxyStatus):
        """Handle proxy status changes."""
        self.logger.info(f"Proxy status changed: {status}")
        
        if status.is_running:
            self.proxy_info_label.configure(
                text=f"Running on {status.get_listen_url()} - {status.active_connections} active connections"
            )
        else:
            self.proxy_info_label.configure(text="Proxy not running")
    
    def show_usage_instructions(self, proxy_status: ProxyStatus):
        """Show instructions for using the proxy."""
        proxy_url = proxy_status.get_listen_url()
        
        instructions = f"""
Proxy Started Successfully!

Your px proxy with NTLM authentication is now running on:
{proxy_url}

To use this proxy:

1. Configure your browser:
   - HTTP Proxy: {proxy_status.listen_address}
   - Port: {proxy_status.port}

2. Test with curl:
   curl --proxy {proxy_url} https://www.google.com

3. The proxy will automatically handle NTLM authentication
   with your enterprise proxy server.

Note: Make sure your enterprise proxy server is configured
in the NTLM settings above.
        """.strip()
        
        messagebox.showinfo("Proxy Started", instructions)
    
    def show_help(self):
        """Show help information."""
        help_text = """
NTLM Authentication Demo Help

This demo shows how to use px UI client with NTLM authentication
for enterprise environments.

Configuration Steps:
1. Enable NTLM Authentication
2. Set Authentication Method (ANY recommended)
3. Configure Upstream Proxy (your company's proxy server)
4. Set Domain Settings (auto-detect recommended)
5. Click "Start Proxy"

Troubleshooting:
- Ensure you're on a Windows domain-joined computer
- Verify upstream proxy server address and port
- Check that your enterprise proxy supports NTLM
- Try "ANY" authentication method if specific methods fail

For more help, see the NTLM Configuration panel's help button.
        """
        
        messagebox.showinfo("Help", help_text.strip())
    
    def run(self):
        """Run the demo application."""
        self.logger.info("Starting NTLM Demo Application")
        
        # Start event system
        self.event_system.start()
        
        try:
            self.root.mainloop()
        finally:
            # Cleanup
            self.logger.info("Shutting down NTLM Demo Application")
            if self.proxy_bridge.get_proxy_status().is_running:
                self.proxy_bridge.stop_proxy()
            self.event_system.stop()


def main():
    """Main entry point."""
    print("🔐 px UI Client - NTLM Authentication Demo")
    print("=" * 50)
    
    try:
        # Check px library availability
        import px.main
        import px.config
        import px.handler
        print("✅ px library available")
        
        # Check NTLM support
        try:
            import spnego
            print("✅ NTLM support available")
        except ImportError:
            print("❌ Warning: spnego library not available - NTLM may not work")
        
        # Start demo
        demo = NTLMDemo()
        demo.run()
        
    except ImportError as e:
        print(f"❌ Error: Required library not available: {e}")
        print("Please ensure px library is installed and available.")
    except Exception as e:
        print(f"❌ Error starting demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()