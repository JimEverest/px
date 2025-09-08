"""
No Proxy Configuration Panel for managing proxy bypass settings.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, simpledialog
import logging
from typing import Optional, Callable, List

from px_ui.models.no_proxy_configuration import NoProxyConfiguration
from px_ui.error_handling.error_manager import ErrorCategory, ErrorSeverity


class NoProxyPanel(ttk.Frame):
    """
    Panel for configuring no proxy settings.
    """
    
    def __init__(self, parent, **kwargs):
        """Initialize the no proxy configuration panel."""
        super().__init__(parent, **kwargs)
        
        self.logger = logging.getLogger(__name__)
        self.no_proxy_config = NoProxyConfiguration()
        
        # Callbacks for external integration
        self.on_config_changed: Optional[Callable[[NoProxyConfiguration], None]] = None
        
        # Error handling
        self.error_handler = None
        
        # UI state
        self._updating_ui = False
        
        # Create UI
        self._setup_ui()
        
        self.logger.info("No Proxy Configuration Panel initialized")
    
    def set_error_handler(self, error_handler):
        """Set the error handler for this component."""
        self.error_handler = error_handler
    
    def get_configuration(self) -> NoProxyConfiguration:
        """Get current no proxy configuration."""
        return self.no_proxy_config
    
    def set_configuration(self, config: NoProxyConfiguration):
        """Set no proxy configuration."""
        self.no_proxy_config = config
    
    def get_px_format(self) -> str:
        """Get configuration in px-compatible format."""
        return self.no_proxy_config.to_px_format()
    
    def get_summary(self) -> str:
        """Get configuration summary."""
        return self.no_proxy_config.get_summary()
    
    def _setup_ui(self):
        """Set up the user interface components."""
        # Configure grid weights
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Create main sections
        self._create_header_section()
        self._create_list_section()
        self._create_input_section()
        self._create_action_buttons()
        
        # Load initial configuration
        self._update_ui_from_config()
    
    def _create_header_section(self):
        """Create the header section with description."""
        header_frame = ttk.Frame(self)
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        
        # Title
        title_label = ttk.Label(
            header_frame, 
            text="No Proxy Settings", 
            font=("Arial", 12, "bold")
        )
        title_label.pack(anchor="w")
        
        # Description
        desc_text = ("Configure hosts and IP addresses that should bypass the proxy server. "
                    "Supports wildcards (*), IP ranges, and CIDR notation.")
        desc_label = ttk.Label(
            header_frame, 
            text=desc_text, 
            wraplength=500,
            justify="left"
        )
        desc_label.pack(anchor="w", pady=(5, 0))
    
    def _create_list_section(self):
        """Create the no proxy list section."""
        list_frame = ttk.LabelFrame(self, text="No Proxy List", padding=10)
        list_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)
        
        # Create listbox with scrollbar
        list_container = ttk.Frame(list_frame)
        list_container.grid(row=0, column=0, sticky="nsew")
        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)
        
        self.no_proxy_listbox = tk.Listbox(list_container, height=8)
        self.no_proxy_listbox.grid(row=0, column=0, sticky="nsew")
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(list_container, orient="vertical", command=self.no_proxy_listbox.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.no_proxy_listbox.config(yscrollcommand=scrollbar.set)
        
        # Bind selection events
        self.no_proxy_listbox.bind("<<ListboxSelect>>", self._on_selection_changed)
        self.no_proxy_listbox.bind("<Double-Button-1>", self._on_edit_entry)
    
    def _create_input_section(self):
        """Create the input section for adding new entries."""
        input_frame = ttk.LabelFrame(self, text="Add New Entry", padding=10)
        input_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=5)
        input_frame.grid_columnconfigure(1, weight=1)
        
        # Entry type selection
        ttk.Label(input_frame, text="Type:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        
        self.entry_type_var = tk.StringVar(value="host")
        type_frame = ttk.Frame(input_frame)
        type_frame.grid(row=0, column=1, sticky="w", pady=(0, 5))
        
        ttk.Radiobutton(
            type_frame, text="Host/Domain", variable=self.entry_type_var, 
            value="host", command=self._on_type_changed
        ).pack(side="left", padx=(0, 10))
        
        ttk.Radiobutton(
            type_frame, text="IP Address", variable=self.entry_type_var, 
            value="ip", command=self._on_type_changed
        ).pack(side="left", padx=(0, 10))
        
        ttk.Radiobutton(
            type_frame, text="IP Range/CIDR", variable=self.entry_type_var, 
            value="range", command=self._on_type_changed
        ).pack(side="left")
        
        # Input field
        ttk.Label(input_frame, text="Value:").grid(row=1, column=0, sticky="w", padx=(0, 5))
        
        self.entry_var = tk.StringVar()
        self.entry_field = ttk.Entry(input_frame, textvariable=self.entry_var, width=40)
        self.entry_field.grid(row=1, column=1, sticky="ew", padx=(0, 5))
        self.entry_field.bind("<Return>", lambda e: self._add_entry())
        
        # Add button
        self.add_button = ttk.Button(input_frame, text="Add", command=self._add_entry)
        self.add_button.grid(row=1, column=2)
        
        # Example text
        self.example_label = ttk.Label(input_frame, text="", font=("Arial", 8), foreground="gray")
        self.example_label.grid(row=2, column=1, sticky="w", pady=(2, 0))
        
        # Update example text
        self._on_type_changed()
    
    def _create_action_buttons(self):
        """Create action buttons."""
        button_frame = ttk.Frame(self)
        button_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(5, 10))
        
        # Remove button
        self.remove_button = ttk.Button(
            button_frame, text="Remove Selected", 
            command=self._remove_selected, state="disabled"
        )
        self.remove_button.pack(side="left")
        
        # Edit button
        self.edit_button = ttk.Button(
            button_frame, text="Edit Selected", 
            command=self._edit_selected, state="disabled"
        )
        self.edit_button.pack(side="left", padx=(5, 0))
        
        # Clear all button
        self.clear_button = ttk.Button(
            button_frame, text="Clear All", 
            command=self._clear_all
        )
        self.clear_button.pack(side="left", padx=(5, 0))
        
        # Import/Export buttons
        ttk.Separator(button_frame, orient="vertical").pack(side="left", fill="y", padx=10)
        
        self.import_button = ttk.Button(
            button_frame, text="Import from File", 
            command=self._import_from_file
        )
        self.import_button.pack(side="left")
        
        self.export_button = ttk.Button(
            button_frame, text="Export to File", 
            command=self._export_to_file
        )
        self.export_button.pack(side="left", padx=(5, 0))
        
        # Status label
        self.status_label = ttk.Label(button_frame, text="")
        self.status_label.pack(side="right")
    
    def _on_type_changed(self):
        """Handle entry type change."""
        entry_type = self.entry_type_var.get()
        
        examples = {
            "host": "Example: example.com, *.local, localhost",
            "ip": "Example: 192.168.1.1, 127.0.0.1",
            "range": "Example: 192.168.1.0/24, 10.0.0.0/8"
        }
        
        self.example_label.config(text=examples.get(entry_type, ""))
        
        # Clear current input
        self.entry_var.set("")
    
    def _add_entry(self):
        """Add a new no proxy entry."""
        entry_value = self.entry_var.get().strip()
        if not entry_value:
            if self.error_handler:
                self.error_handler.handle_error(
                    category=ErrorCategory.CONFIGURATION,
                    severity=ErrorSeverity.LOW,
                    message="Please enter a value",
                    show_dialog=True,
                    highlight_widget=self.entry_field
                )
            else:
                messagebox.showerror("Error", "Please enter a value.")
            return
        
        try:
            # Validate entry based on type
            entry_type = self.entry_type_var.get()
            if entry_type == "ip":
                self._validate_ip_address(entry_value)
            elif entry_type == "range":
                self._validate_ip_range(entry_value)
            
            # Add to configuration
            if entry_value not in self.no_proxy_config.patterns:
                self.no_proxy_config.add_pattern(entry_value)
                self._update_ui_from_config()
                self.entry_var.set("")  # Clear input
                self._update_status(f"Added: {entry_value}")
                
                # Notify change
                if self.on_config_changed:
                    self.on_config_changed(self.no_proxy_config)
            else:
                self._update_status(f"Entry already exists: {entry_value}")
        
        except Exception as e:
            if self.error_handler:
                self.error_handler.handle_error(
                    category=ErrorCategory.CONFIGURATION,
                    severity=ErrorSeverity.MEDIUM,
                    message="Invalid entry format",
                    details=str(e),
                    show_dialog=True,
                    highlight_widget=self.entry_field
                )
            else:
                messagebox.showerror("Invalid Entry", str(e))
    
    def _validate_ip_address(self, ip_str: str):
        """Validate IP address format."""
        import ipaddress
        try:
            ipaddress.ip_address(ip_str)
        except ValueError:
            raise ValueError(f"Invalid IP address: {ip_str}")
    
    def _validate_ip_range(self, range_str: str):
        """Validate IP range/CIDR format."""
        import ipaddress
        try:
            if '/' in range_str:
                ipaddress.ip_network(range_str, strict=False)
            elif '-' in range_str:
                # Handle range format like 192.168.1.1-192.168.1.100
                start_ip, end_ip = range_str.split('-', 1)
                ipaddress.ip_address(start_ip.strip())
                ipaddress.ip_address(end_ip.strip())
            else:
                raise ValueError("Range must contain '/' for CIDR or '-' for IP range")
        except ValueError as e:
            raise ValueError(f"Invalid IP range: {range_str} - {str(e)}")
    
    def _remove_selected(self):
        """Remove selected entries."""
        selection = self.no_proxy_listbox.curselection()
        if not selection:
            return
        
        # Get selected entries
        selected_entries = [self.no_proxy_listbox.get(i) for i in selection]
        
        # Confirm removal
        if len(selected_entries) == 1:
            message = f"Remove '{selected_entries[0]}'?"
        else:
            message = f"Remove {len(selected_entries)} selected entries?"
        
        if messagebox.askyesno("Confirm Removal", message):
            # Remove from configuration
            for entry in selected_entries:
                self.no_proxy_config.remove_pattern(entry)
            
            self._update_ui_from_config()
            self._update_status(f"Removed {len(selected_entries)} entry(ies)")
            
            # Notify change
            if self.on_config_changed:
                self.on_config_changed(self.no_proxy_config)
    
    def _edit_selected(self):
        """Edit selected entry."""
        selection = self.no_proxy_listbox.curselection()
        if not selection or len(selection) != 1:
            return
        
        current_value = self.no_proxy_listbox.get(selection[0])
        self._edit_entry_dialog(current_value)
    
    def _on_edit_entry(self, event=None):
        """Handle double-click to edit entry."""
        self._edit_selected()
    
    def _edit_entry_dialog(self, current_value: str):
        """Show edit entry dialog."""
        from tkinter import simpledialog
        
        new_value = simpledialog.askstring(
            "Edit Entry",
            "Edit no proxy entry:",
            initialvalue=current_value
        )
        
        if new_value and new_value != current_value:
            try:
                # Remove old value and add new one
                self.no_proxy_config.remove_pattern(current_value)
                self.no_proxy_config.add_pattern(new_value)
                self._update_ui_from_config()
                self._update_status(f"Updated: {current_value} → {new_value}")
                
                # Notify change
                if self.on_config_changed:
                    self.on_config_changed(self.no_proxy_config)
            
            except Exception as e:
                if self.error_handler:
                    self.error_handler.handle_error(
                        category=ErrorCategory.CONFIGURATION,
                        severity=ErrorSeverity.MEDIUM,
                        message="Failed to update entry",
                        details=str(e),
                        show_dialog=True
                    )
                else:
                    messagebox.showerror("Edit Error", f"Failed to update entry:\n{str(e)}")
    
    def _clear_all(self):
        """Clear all entries."""
        if not self.no_proxy_config.patterns:
            return
        
        if messagebox.askyesno("Confirm Clear", "Remove all no proxy entries?"):
            self.no_proxy_config.clear_patterns()
            self._update_ui_from_config()
            self._update_status("All entries cleared")
            
            # Notify change
            if self.on_config_changed:
                self.on_config_changed(self.no_proxy_config)
    
    def _import_from_file(self):
        """Import no proxy entries from file."""
        from tkinter import filedialog
        
        file_path = filedialog.askopenfilename(
            title="Import No Proxy Entries",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                imported_count = 0
                for line in lines:
                    entry = line.strip()
                    if entry and not entry.startswith('#'):
                        if entry not in self.no_proxy_config.patterns:
                            self.no_proxy_config.add_pattern(entry)
                            imported_count += 1
                
                self._update_ui_from_config()
                self._update_status(f"Imported {imported_count} entries from {file_path}")
                
                # Notify change
                if self.on_config_changed:
                    self.on_config_changed(self.no_proxy_config)
            
            except Exception as e:
                if self.error_handler:
                    self.error_handler.handle_error(
                        category=ErrorCategory.SYSTEM,
                        severity=ErrorSeverity.MEDIUM,
                        message="Failed to import entries",
                        details=str(e),
                        show_dialog=True,
                        context={"file_path": file_path}
                    )
                else:
                    messagebox.showerror("Import Error", f"Failed to import entries:\n{str(e)}")
    
    def _export_to_file(self):
        """Export no proxy entries to file."""
        if not self.no_proxy_config.patterns:
            messagebox.showinfo("Export", "No entries to export.")
            return
        
        from tkinter import filedialog
        
        file_path = filedialog.asksaveasfilename(
            title="Export No Proxy Entries",
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("All files", "*.*")
            ]
        )
        
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("# No Proxy Configuration\n")
                    f.write("# Generated by px UI Client\n\n")
                    
                    for host in sorted(self.no_proxy_config.patterns):
                        f.write(f"{host}\n")
                
                self._update_status(f"Exported {len(self.no_proxy_config.patterns)} entries to {file_path}")
                messagebox.showinfo("Export Complete", f"Exported {len(self.no_proxy_config.patterns)} entries to:\n{file_path}")
            
            except Exception as e:
                if self.error_handler:
                    self.error_handler.handle_error(
                        category=ErrorCategory.SYSTEM,
                        severity=ErrorSeverity.MEDIUM,
                        message="Failed to export entries",
                        details=str(e),
                        show_dialog=True,
                        context={"file_path": file_path}
                    )
                else:
                    messagebox.showerror("Export Error", f"Failed to export entries:\n{str(e)}")
    
    def _on_selection_changed(self, event=None):
        """Handle listbox selection change."""
        selection = self.no_proxy_listbox.curselection()
        has_selection = len(selection) > 0
        
        self.remove_button.config(state="normal" if has_selection else "disabled")
        self.edit_button.config(state="normal" if len(selection) == 1 else "disabled")
    
    def _update_ui_from_config(self):
        """Update UI elements from current configuration."""
        if self._updating_ui:
            return
        
        self._updating_ui = True
        try:
            # Update listbox
            self.no_proxy_listbox.delete(0, tk.END)
            for host in sorted(self.no_proxy_config.patterns):
                self.no_proxy_listbox.insert(tk.END, host)
            
            # Update button states
            self._on_selection_changed()
            
        finally:
            self._updating_ui = False
    
    def _update_status(self, message: str):
        """Update status label."""
        self.status_label.config(text=message)
        # Clear status after 3 seconds
        self.after(3000, lambda: self.status_label.config(text=""))


if __name__ == "__main__":
    # Test the panel
    root = tk.Tk()
    root.title("No Proxy Configuration Test")
    root.geometry("600x700")
    
    panel = NoProxyPanel(root)
    panel.pack(fill="both", expand=True, padx=10, pady=10)
    
    root.mainloop()