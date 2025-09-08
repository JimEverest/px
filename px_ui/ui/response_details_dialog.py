"""
Response details dialog for displaying full response information.

This module provides the ResponseDetailsDialog class that shows detailed
response headers, body content, and request information in a formatted view.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from px_ui.error_handling.error_manager import ErrorCategory, ErrorSeverity
from typing import Dict, Optional
import json
import html
import re


class ResponseDetailsDialog:
    """
    Dialog for displaying detailed response information.
    
    Shows request details, response headers, and body content with
    proper formatting and truncation handling for large responses.
    """
    
    def __init__(self, parent, request_entry):
        """
        Initialize response details dialog.
        
        Args:
            parent: Parent widget
            request_entry: RequestEntry object containing request/response data
        """
        self.parent = parent
        self.entry = request_entry
        self.dialog = None
        self.full_body_content = ""  # Store full body content
        self.error_handler = None  # Will be set by parent component
        
    def show(self):
        """Show the response details dialog."""
        if self.dialog:
            self.dialog.lift()
            return
            
        self._create_dialog()
        self._populate_content()
        
    def _create_dialog(self):
        """Create the dialog window and UI components."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(f"Response Details - {self._truncate_url(self.entry.url, 50)}")
        self.dialog.geometry("800x600")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (800 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (600 // 2)
        self.dialog.geometry(f"800x600+{x}+{y}")
        
        # Handle dialog close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Create main frame
        main_frame = ttk.Frame(self.dialog)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True)
        
        # Create tabs
        self._create_overview_tab()
        self._create_request_tab()
        self._create_response_tab()
        self._create_body_tab()
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=(10, 0))
        
        # Buttons
        ttk.Button(button_frame, text="Copy URL", command=self._copy_url).pack(side="left")
        ttk.Button(button_frame, text="Export Details", command=self._export_details).pack(side="left", padx=(10, 0))
        ttk.Button(button_frame, text="Close", command=self._on_close).pack(side="right")
        
    def _create_overview_tab(self):
        """Create the overview tab with summary information."""
        overview_frame = ttk.Frame(self.notebook)
        self.notebook.add(overview_frame, text="Overview")
        
        # Create scrolled text widget
        text_widget = scrolledtext.ScrolledText(overview_frame, wrap="word", state="disabled")
        text_widget.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.overview_text = text_widget
        
    def _create_request_tab(self):
        """Create the request tab with request details."""
        request_frame = ttk.Frame(self.notebook)
        self.notebook.add(request_frame, text="Request")
        
        # Create scrolled text widget
        text_widget = scrolledtext.ScrolledText(request_frame, wrap="word", state="disabled")
        text_widget.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.request_text = text_widget
        
    def _create_response_tab(self):
        """Create the response tab with response headers."""
        response_frame = ttk.Frame(self.notebook)
        self.notebook.add(response_frame, text="Response Headers")
        
        # Create scrolled text widget
        text_widget = scrolledtext.ScrolledText(response_frame, wrap="word", state="disabled")
        text_widget.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.response_text = text_widget
        
    def _create_body_tab(self):
        """Create the body tab with response body content."""
        body_frame = ttk.Frame(self.notebook)
        self.notebook.add(body_frame, text="Response Body")
        
        # Control frame
        control_frame = ttk.Frame(body_frame)
        control_frame.pack(fill="x", padx=5, pady=5)
        
        # Body size info
        self.body_info_label = ttk.Label(control_frame, text="")
        self.body_info_label.pack(side="left")
        
        # View full content button
        self.view_full_button = ttk.Button(control_frame, text="View Full Content", 
                                         command=self._view_full_content)
        self.view_full_button.pack(side="right")
        
        # Format options
        format_frame = ttk.Frame(control_frame)
        format_frame.pack(side="right", padx=(0, 10))
        
        ttk.Label(format_frame, text="Format:").pack(side="left")
        self.format_var = tk.StringVar(value="Raw")
        format_combo = ttk.Combobox(format_frame, textvariable=self.format_var,
                                   values=["Raw", "JSON", "HTML", "XML"], 
                                   state="readonly", width=8)
        format_combo.pack(side="left", padx=(5, 0))
        format_combo.bind("<<ComboboxSelected>>", self._on_format_change)
        
        # Create scrolled text widget
        text_widget = scrolledtext.ScrolledText(body_frame, wrap="word", state="disabled")
        text_widget.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        
        self.body_text = text_widget
        
    def _populate_content(self):
        """Populate all tabs with content."""
        self._populate_overview()
        self._populate_request()
        self._populate_response()
        self._populate_body()
        
    def _populate_overview(self):
        """Populate the overview tab."""
        self.overview_text.config(state="normal")
        self.overview_text.delete("1.0", "end")
        
        # Basic information
        content = f"""REQUEST SUMMARY
{'=' * 50}
URL: {self.entry.url}
Method: {self.entry.method}
Timestamp: {self.entry.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}
Proxy Decision: {self.entry.proxy_decision}

"""
        
        # Response summary
        if self.entry.status_code is not None:
            status_text = f"Status Code: {self.entry.status_code}"
            if self.entry.is_error():
                status_text += " ❌ ERROR"
            else:
                status_text += " ✅ SUCCESS"
                
            response_time_str = f"{self.entry.response_time:.2f}ms" if self.entry.response_time is not None else "N/A"
            content += f"""RESPONSE SUMMARY
{'=' * 50}
{status_text}
Content Length: {self._format_bytes(self.entry.content_length)}
Response Time: {response_time_str}
Content Type: {self.entry.response_headers.get('content-type', 'Unknown')}

"""
        else:
            content += f"""RESPONSE SUMMARY
{'=' * 50}
Status: No response received
"""
            
        # Error information
        if self.entry.error_message:
            content += f"""ERROR DETAILS
{'=' * 50}
Error: {self.entry.error_message}

"""
            
        # Statistics
        header_count = len(self.entry.response_headers)
        content += f"""STATISTICS
{'=' * 50}
Request Headers: {len(self.entry.headers) if self.entry.headers else 0}
Response Headers: {header_count}
Body Preview Length: {len(self.entry.body_preview)} characters
"""
        
        self.overview_text.insert("1.0", content)
        self.overview_text.config(state="disabled")
        
    def _populate_request(self):
        """Populate the request tab."""
        self.request_text.config(state="normal")
        self.request_text.delete("1.0", "end")
        
        content = f"""REQUEST LINE
{self.entry.method} {self.entry.url}

PROXY DECISION
{self.entry.proxy_decision}

TIMESTAMP
{self.entry.timestamp.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}

REQUEST HEADERS
"""
        
        if self.entry.headers:
            for key, value in sorted(self.entry.headers.items()):
                content += f"{key}: {value}\n"
        else:
            content += "(No headers captured)\n"
            
        self.request_text.insert("1.0", content)
        self.request_text.config(state="disabled")
        
    def _populate_response(self):
        """Populate the response tab."""
        self.response_text.config(state="normal")
        self.response_text.delete("1.0", "end")
        
        if self.entry.status_code is not None:
            # Status line
            content = f"STATUS LINE\nHTTP/1.1 {self.entry.status_code} {self._get_status_text(self.entry.status_code)}\n\n"
            
            # Response time and size
            content += f"RESPONSE METRICS\n"
            content += f"Response Time: {self.entry.response_time:.2f}ms\n" if self.entry.response_time is not None else "Response Time: N/A\n"
            content += f"Content Length: {self._format_bytes(self.entry.content_length)}\n\n"
            
            # Headers
            content += "RESPONSE HEADERS\n"
            if self.entry.response_headers:
                for key, value in sorted(self.entry.response_headers.items()):
                    content += f"{key}: {value}\n"
            else:
                content += "(No headers received)\n"
        else:
            content = "No response received"
            
        if self.entry.error_message:
            content += f"\n\nERROR INFORMATION\n{self.entry.error_message}"
            
        self.response_text.insert("1.0", content)
        self.response_text.config(state="disabled")
        
    def _populate_body(self):
        """Populate the body tab."""
        # Update body info
        body_length = len(self.entry.body_preview)
        if self.entry.content_length > body_length:
            info_text = f"Showing {body_length} of {self._format_bytes(self.entry.content_length)} (truncated)"
            self.view_full_button.config(state="normal")
        else:
            info_text = f"Complete content: {self._format_bytes(body_length)}"
            self.view_full_button.config(state="disabled")
            
        self.body_info_label.config(text=info_text)
        
        # Store full content (for now, same as preview - would be extended in real implementation)
        self.full_body_content = self.entry.body_preview
        
        # Display content
        self._update_body_display()
        
    def _update_body_display(self):
        """Update body display based on selected format."""
        self.body_text.config(state="normal")
        self.body_text.delete("1.0", "end")
        
        content = self.entry.body_preview
        format_type = self.format_var.get()
        
        try:
            if format_type == "JSON" and content.strip():
                # Try to format as JSON
                parsed = json.loads(content)
                content = json.dumps(parsed, indent=2, ensure_ascii=False)
            elif format_type == "HTML" and content.strip():
                # Basic HTML formatting (just add line breaks)
                content = html.unescape(content)
            elif format_type == "XML" and content.strip():
                # Basic XML formatting
                content = self._format_xml(content)
        except (json.JSONDecodeError, Exception):
            # If formatting fails, show raw content
            pass
            
        if not content.strip():
            content = "(Empty response body)"
            
        self.body_text.insert("1.0", content)
        self.body_text.config(state="disabled")
        
    def _format_xml(self, xml_content: str) -> str:
        """Basic XML formatting."""
        try:
            import xml.dom.minidom
            dom = xml.dom.minidom.parseString(xml_content)
            return dom.toprettyxml(indent="  ")
        except:
            return xml_content
            
    def _on_format_change(self, event=None):
        """Handle format selection change."""
        self._update_body_display()
        
    def _view_full_content(self):
        """Show full content in a separate dialog."""
        if not self.full_body_content:
            messagebox.showinfo("No Content", "No full content available.")
            return
            
        # Create full content dialog
        full_dialog = tk.Toplevel(self.dialog)
        full_dialog.title("Full Response Body")
        full_dialog.geometry("900x700")
        full_dialog.transient(self.dialog)
        
        # Create text widget with scrollbars
        text_frame = ttk.Frame(full_dialog)
        text_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        text_widget = scrolledtext.ScrolledText(text_frame, wrap="word", state="disabled")
        text_widget.pack(fill="both", expand=True)
        
        # Insert content
        text_widget.config(state="normal")
        text_widget.insert("1.0", self.full_body_content)
        text_widget.config(state="disabled")
        
        # Close button
        button_frame = ttk.Frame(full_dialog)
        button_frame.pack(fill="x", padx=10, pady=(0, 10))
        ttk.Button(button_frame, text="Close", command=full_dialog.destroy).pack(side="right")
        
    def _copy_url(self):
        """Copy URL to clipboard."""
        self.dialog.clipboard_clear()
        self.dialog.clipboard_append(self.entry.url)
        messagebox.showinfo("Copied", "URL copied to clipboard")
        
    def _export_details(self):
        """Export response details to file."""
        from tkinter import filedialog
        
        filename = filedialog.asksaveasfilename(
            parent=self.dialog,
            title="Export Response Details",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if filename:
            try:
                export_data = {
                    "url": self.entry.url,
                    "method": self.entry.method,
                    "timestamp": self.entry.timestamp.isoformat(),
                    "proxy_decision": self.entry.proxy_decision,
                    "request_headers": self.entry.headers or {},
                    "status_code": self.entry.status_code,
                    "response_headers": self.entry.response_headers,
                    "response_time": self.entry.response_time,
                    "content_length": self.entry.content_length,
                    "body_preview": self.entry.body_preview,
                    "error_message": self.entry.error_message
                }
                
                if filename.endswith('.json'):
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
                else:
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(f"Response Details Export\n")
                        f.write(f"{'=' * 50}\n\n")
                        for key, value in export_data.items():
                            f.write(f"{key}: {value}\n")
                            
                messagebox.showinfo("Export Complete", f"Details exported to {filename}")
            except Exception as e:
                if self.error_handler:
                    self.error_handler.handle_error(
                        category=ErrorCategory.SYSTEM,
                        severity=ErrorSeverity.MEDIUM,
                        message="Failed to export response details",
                        details=str(e),
                        exception=e,
                        show_dialog=True,
                        context={"filename": filename}
                    )
                else:
                    messagebox.showerror("Export Error", f"Failed to export details: {str(e)}")
                
    def _on_close(self):
        """Handle dialog close."""
        if self.dialog:
            self.dialog.destroy()
            self.dialog = None
            
    def _truncate_url(self, url: str, max_length: int) -> str:
        """Truncate URL for display."""
        if len(url) <= max_length:
            return url
        return url[:max_length-3] + "..."
        
    def _format_bytes(self, bytes_count: int) -> str:
        """Format byte count for display."""
        if bytes_count < 1024:
            return f"{bytes_count} bytes"
        elif bytes_count < 1024 * 1024:
            return f"{bytes_count / 1024:.1f} KB"
        else:
            return f"{bytes_count / (1024 * 1024):.1f} MB"
            
    def _get_status_text(self, status_code: int) -> str:
        """Get status text for HTTP status code."""
        status_texts = {
            200: "OK", 201: "Created", 202: "Accepted", 204: "No Content",
            301: "Moved Permanently", 302: "Found", 304: "Not Modified",
            400: "Bad Request", 401: "Unauthorized", 403: "Forbidden", 404: "Not Found",
            405: "Method Not Allowed", 407: "Proxy Authentication Required",
            500: "Internal Server Error", 502: "Bad Gateway", 503: "Service Unavailable",
            504: "Gateway Timeout"
        }
        return status_texts.get(status_code, "Unknown")