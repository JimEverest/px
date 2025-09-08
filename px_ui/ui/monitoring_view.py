"""
Request monitoring view with real-time updates.

This module provides the MonitoringView class that displays request/response data
in real-time using a Tkinter Treeview with filtering capabilities and context menus.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import re

from px_ui.communication.events import RequestEvent, ResponseEvent, ErrorEvent, EventType, ProxyDecisionUpdateEvent
from px_ui.communication.event_system import EventSystem
from px_ui.ui.response_details_dialog import ResponseDetailsDialog
from px_ui.error_handling.error_manager import ErrorManager, ErrorCategory, ErrorSeverity, get_error_manager
from px_ui.performance import PerformanceMonitor, PerformanceConfig, MemoryManager, UpdateThrottler


class RequestEntry:
    """Represents a single request entry in the monitoring view."""
    
    def __init__(self, request_event: RequestEvent):
        """Initialize request entry from request event."""
        self.request_id = request_event.request_id
        self.timestamp = request_event.timestamp
        self.url = request_event.url
        self.method = request_event.method
        self.proxy_decision = request_event.proxy_decision
        self.headers = request_event.headers or {}
        
        # Response data (filled when response arrives)
        self.status_code: Optional[int] = None
        self.response_headers: Dict[str, str] = {}
        self.body_preview: str = ""
        self.content_length: int = 0
        self.response_time: Optional[float] = None
        self.error_message: Optional[str] = None
        
    def update_response(self, response_event: ResponseEvent):
        """Update entry with response data."""
        self.status_code = response_event.status_code
        self.response_headers = response_event.headers
        self.body_preview = response_event.body_preview
        self.content_length = response_event.content_length
        self.response_time = response_event.response_time
        
    def update_error(self, error_event: ErrorEvent):
        """Update entry with error information."""
        self.error_message = error_event.error_message
        self.status_code = 0  # Indicate error state
        
    def get_status_display(self) -> str:
        """Get display string for status."""
        if self.error_message:
            return f"ERROR: {self.error_message}"
        elif self.status_code is None:
            return "Pending"
        else:
            return str(self.status_code)
            
    def is_error(self) -> bool:
        """Check if this entry represents an error."""
        return (self.error_message is not None or 
                (self.status_code is not None and self.status_code >= 400))
    
    def is_client_error(self) -> bool:
        """Check if this entry represents a 4xx client error."""
        return self.status_code is not None and 400 <= self.status_code < 500
    
    def is_server_error(self) -> bool:
        """Check if this entry represents a 5xx server error."""
        return self.status_code is not None and self.status_code >= 500
    
    def is_success(self) -> bool:
        """Check if this entry represents a successful response."""
        return self.status_code is not None and 200 <= self.status_code < 300


class MonitoringView(ttk.Frame):
    """
    Request monitoring view with real-time updates.
    
    Displays request/response data in a Treeview with filtering capabilities
    and context menus for detailed inspection.
    """
    
    def __init__(self, parent, event_system: EventSystem):
        """
        Initialize monitoring view.
        
        Args:
            parent: Parent widget
            event_system: Event system for receiving proxy events
        """
        super().__init__(parent)
        self.event_system = event_system
        self.entries: Dict[str, RequestEntry] = {}
        self.filtered_entries: List[str] = []  # List of request_ids that pass filters
        
        # Error handling
        self.error_manager = get_error_manager()
        self.error_handler = None
        
        # Filter settings
        self.url_filter = ""
        self.proxy_filter = "All"  # "All", "DIRECT", "PROXY"
        self.status_filter = "All"  # "All", "Success", "Error"
        
        # Performance optimizations
        self.performance_monitor = PerformanceMonitor(PerformanceConfig(
            max_entries=1000,
            max_memory_mb=200,  # Limit for monitoring view
            max_body_size=5120,  # 5KB for response bodies
            max_updates_per_second=20,  # Limit UI updates
            throttle_mode="adaptive"
        ))
        
        # UI update control with throttling
        self.update_pending = False
        self.max_entries = 1000  # Maximum entries to keep in memory
        
        # Virtual scrolling for large datasets
        self.virtual_scrolling = True
        self.visible_range = (0, 100)  # Only render visible items
        self.total_items = 0
        
        self._setup_ui()
        self._setup_event_handlers()
    
    def set_error_handler(self, error_handler):
        """Set the error handler for this component."""
        self.error_handler = error_handler
        self._setup_performance_integration()
        
        # Start performance monitoring
        self.performance_monitor.start_monitoring()
        
    def _setup_ui(self):
        """Set up the user interface components."""
        # Create main container
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Filter frame
        filter_frame = ttk.Frame(self)
        filter_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        filter_frame.grid_columnconfigure(1, weight=1)
        
        # URL filter
        ttk.Label(filter_frame, text="URL Filter:").grid(row=0, column=0, padx=(0, 5))
        self.url_filter_var = tk.StringVar()
        self.url_filter_var.trace("w", self._on_filter_change)
        url_entry = ttk.Entry(filter_frame, textvariable=self.url_filter_var)
        url_entry.grid(row=0, column=1, sticky="ew", padx=(0, 10))
        
        # Proxy filter
        ttk.Label(filter_frame, text="Proxy:").grid(row=0, column=2, padx=(0, 5))
        self.proxy_filter_var = tk.StringVar(value="All")
        self.proxy_filter_var.trace("w", self._on_filter_change)
        proxy_combo = ttk.Combobox(filter_frame, textvariable=self.proxy_filter_var,
                                  values=["All", "DIRECT", "PROXY"], state="readonly", width=10)
        proxy_combo.grid(row=0, column=3, padx=(0, 10))
        
        # Status filter
        ttk.Label(filter_frame, text="Status:").grid(row=0, column=4, padx=(0, 5))
        self.status_filter_var = tk.StringVar(value="All")
        self.status_filter_var.trace("w", self._on_filter_change)
        status_combo = ttk.Combobox(filter_frame, textvariable=self.status_filter_var,
                                   values=["All", "Success", "Error"], state="readonly", width=10)
        status_combo.grid(row=0, column=5, padx=(0, 10))
        
        # Clear button
        clear_btn = ttk.Button(filter_frame, text="Clear Logs", command=self.clear_logs)
        clear_btn.grid(row=0, column=6)
        
        # Monitoring table
        table_frame = ttk.Frame(self)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=(0, 5))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        
        # Treeview with columns
        columns = ("timestamp", "method", "url", "proxy", "status", "response_time")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=15)
        
        # Configure columns
        self.tree.heading("timestamp", text="Time")
        self.tree.heading("method", text="Method")
        self.tree.heading("url", text="URL")
        self.tree.heading("proxy", text="Proxy Decision")
        self.tree.heading("status", text="Status")
        self.tree.heading("response_time", text="Time (ms)")
        
        # Column widths
        self.tree.column("timestamp", width=120, minwidth=100)
        self.tree.column("method", width=60, minwidth=50)
        self.tree.column("url", width=300, minwidth=200)
        self.tree.column("proxy", width=150, minwidth=100)
        self.tree.column("status", width=80, minwidth=60)
        self.tree.column("response_time", width=80, minwidth=60)
        
        # Configure tags for error highlighting
        self.tree.tag_configure("error", background="#ffebee", foreground="#c62828")  # Light red background, dark red text
        self.tree.tag_configure("client_error", background="#fff3e0", foreground="#ef6c00")  # Light orange for 4xx
        self.tree.tag_configure("server_error", background="#ffebee", foreground="#d32f2f")  # Light red for 5xx
        self.tree.tag_configure("success", background="#e8f5e8", foreground="#2e7d32")  # Light green for 2xx
        self.tree.tag_configure("normal", background="", foreground="")  # Default colors
        
        # Scrollbars
        v_scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        h_scrollbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=v_scrollbar.set, xscrollcommand=h_scrollbar.set)
        
        # Grid layout
        self.tree.grid(row=0, column=0, sticky="nsew")
        v_scrollbar.grid(row=0, column=1, sticky="ns")
        h_scrollbar.grid(row=1, column=0, sticky="ew")
        
        # Context menu
        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="View Details", command=self._show_details)
        self.context_menu.add_command(label="Copy URL", command=self._copy_url)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Clear Selection", command=self._clear_selection)
        
        # Bind events
        self.tree.bind("<Button-3>", self._show_context_menu)  # Right click
        self.tree.bind("<Double-1>", self._show_details)  # Double click
        
        # Virtual scrolling events
        if self.virtual_scrolling:
            self.tree.bind("<MouseWheel>", self._on_mousewheel)
            self.tree.bind("<Button-4>", self._on_mousewheel)  # Linux
            self.tree.bind("<Button-5>", self._on_mousewheel)  # Linux
        
    def _setup_event_handlers(self):
        """Set up event handlers for proxy events."""
        self.event_system.add_request_handler(self._handle_request_event)
        self.event_system.add_response_handler(self._handle_response_event)
        self.event_system.add_error_handler(self._handle_error_event)
        self.event_system.add_proxy_decision_update_handler(self._handle_proxy_decision_update_event)
        
    def _handle_proxy_decision_update_event(self, event: ProxyDecisionUpdateEvent):
        """Handle proxy decision update event."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Received proxy decision update for request {event.request_id}: {event.proxy_decision}")
        if event.request_id in self.entries:
            self.entries[event.request_id].proxy_decision = event.proxy_decision
            self._schedule_ui_update()
        else:
            logger.warning(f"Request ID {event.request_id} not found in entries.")
        
    def _handle_request_event(self, event: RequestEvent):
        """Handle incoming request event."""
        try:
            entry = RequestEntry(event)
            self.entries[event.request_id] = entry
            
            # Use memory manager for cleanup decisions
            memory_manager = self.performance_monitor.get_memory_manager()
            if memory_manager:
                if memory_manager.should_cleanup(len(self.entries)):
                    cleanup_amount = memory_manager.calculate_cleanup_amount(len(self.entries))
                    if cleanup_amount > 0:
                        # Let memory manager handle cleanup
                        memory_manager.force_cleanup(cleanup_amount)
            else:
                # Fallback to old cleanup method
                if len(self.entries) > self.max_entries:
                    self._cleanup_old_entries()
            
            # Schedule UI update with throttling
            self._schedule_ui_update()
            
        except Exception as e:
            self.error_manager.handle_error(
                category=ErrorCategory.UI,
                severity=ErrorSeverity.LOW,
                message=f"Failed to handle request event: {str(e)}",
                context={'event_id': event.event_id, 'request_id': event.request_id},
                exception=e
            )
        
    def _handle_response_event(self, event: ResponseEvent):
        """Handle incoming response event."""
        try:
            if event.request_id in self.entries:
                self.entries[event.request_id].update_response(event)
                self._schedule_ui_update()
            else:
                # Log missing request entry but don't treat as error
                pass
                
        except Exception as e:
            self.error_manager.handle_error(
                category=ErrorCategory.UI,
                severity=ErrorSeverity.LOW,
                message=f"Failed to handle response event: {str(e)}",
                context={'event_id': event.event_id, 'request_id': event.request_id},
                exception=e
            )
            
    def _handle_error_event(self, event: ErrorEvent):
        """Handle incoming error event."""
        try:
            if event.request_id and event.request_id in self.entries:
                self.entries[event.request_id].update_error(event)
                self._schedule_ui_update()
            
            # Also handle the error through error management system
            if self.error_handler:
                self.error_handler.handle_error(
                    category=ErrorCategory.NETWORK if event.error_type == 'network' else ErrorCategory.SYSTEM,
                    severity=ErrorSeverity.MEDIUM,
                    message=event.error_message,
                    details=event.error_details,
                    context={
                        'event_id': event.event_id,
                        'request_id': event.request_id,
                        'url': event.url,
                        'error_type': event.error_type
                    },
                    show_dialog=False  # Don't show dialog for individual request errors
                )
            else:
                # Fallback to global error manager
                self.error_manager.handle_error(
                    category=ErrorCategory.NETWORK if event.error_type == 'network' else ErrorCategory.SYSTEM,
                    severity=ErrorSeverity.MEDIUM,
                    message=event.error_message,
                    details=event.error_details,
                    context={
                        'event_id': event.event_id,
                        'request_id': event.request_id,
                        'url': event.url,
                        'error_type': event.error_type
                    }
                )
            
        except Exception as e:
            # Fallback error handling to prevent cascading failures
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to handle error event: {e}")
            
    def _schedule_ui_update(self):
        """Schedule UI update to avoid excessive refreshes."""
        if not self.update_pending:
            self.update_pending = True
            self.after_idle(self._update_ui)
            
    def _update_ui(self):
        """Update the UI with current data."""
        self.update_pending = False
        
        # Apply filters and update display
        self._apply_filters()
        self._refresh_tree()
        
    def _apply_filters(self):
        """Apply current filters to entries."""
        self.filtered_entries.clear()
        
        url_pattern = self.url_filter_var.get().lower()
        proxy_filter = self.proxy_filter_var.get()
        status_filter = self.status_filter_var.get()
        
        for request_id, entry in self.entries.items():
            # URL filter
            if url_pattern and url_pattern not in entry.url.lower():
                continue
                
            # Proxy filter
            if proxy_filter != "All":
                if proxy_filter == "DIRECT" and not entry.proxy_decision.startswith("DIRECT"):
                    continue
                elif proxy_filter == "PROXY" and not entry.proxy_decision.startswith("PROXY"):
                    continue
                    
            # Status filter
            if status_filter != "All":
                if status_filter == "Success" and entry.is_error():
                    continue
                elif status_filter == "Error" and not entry.is_error():
                    continue
                    
            self.filtered_entries.append(request_id)
            
        # Sort by timestamp (newest first)
        self.filtered_entries.sort(key=lambda rid: self.entries[rid].timestamp, reverse=True)
        
    def _refresh_tree(self):
        """Refresh the tree view with filtered entries."""
        import logging
        logger = logging.getLogger(__name__)

        # Clear existing items
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Add filtered entries
        for request_id in self.filtered_entries:
            entry = self.entries[request_id]
            logger.info(f"Displaying entry: {entry.request_id}, proxy_decision: {entry.proxy_decision}")
            
            # Format values
            timestamp = entry.timestamp.strftime("%H:%M:%S.%f")[:-3]  # Include milliseconds
            method = entry.method
            url = entry.url
            proxy = entry.proxy_decision
            status = entry.get_status_display()
            response_time = f"{entry.response_time:.0f}" if entry.response_time else ""
            
            # Determine tag for error highlighting
            tag = self._get_status_tag(entry)
            
            # Insert item with appropriate tag
            item_id = self.tree.insert("", "end", values=(timestamp, method, url, proxy, status, response_time), tags=(tag,))
                
        # Auto-scroll to top (newest entries)
        if self.tree.get_children():
            self.tree.see(self.tree.get_children()[0])
            
    def _on_filter_change(self, *args):
        """Handle filter changes."""
        self._schedule_ui_update()
        
    def _cleanup_old_entries(self):
        """Remove old entries to limit memory usage."""
        # Sort by timestamp and keep only the newest entries
        sorted_entries = sorted(self.entries.items(), 
                              key=lambda x: x[1].timestamp, reverse=True)
        
        # Keep only the newest max_entries
        entries_to_keep = dict(sorted_entries[:self.max_entries])
        self.entries = entries_to_keep
        
    def _show_context_menu(self, event):
        """Show context menu on right click."""
        # Select item under cursor
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)
            
    def _show_details(self, event=None):
        """Show detailed view of selected entry."""
        selection = self.tree.selection()
        if not selection:
            return
            
        # Get selected item data
        item = selection[0]
        values = self.tree.item(item, "values")
        if not values:
            return
            
        # Find corresponding entry
        url = values[2]  # URL is in column 2
        timestamp_str = values[0]  # Timestamp is in column 0
        
        # Find matching entry (this is a simple approach, could be improved)
        matching_entry = None
        for entry in self.entries.values():
            if (entry.url == url and 
                entry.timestamp.strftime("%H:%M:%S.%f")[:-3] == timestamp_str):
                matching_entry = entry
                break
                
        if matching_entry:
            self._show_response_details(matching_entry)
            
    def _get_status_tag(self, entry: RequestEntry) -> str:
        """Get the appropriate tag for status-based highlighting."""
        if entry.error_message:
            return "error"
        elif entry.status_code is None:
            return "normal"
        elif 200 <= entry.status_code < 300:
            return "success"
        elif 400 <= entry.status_code < 500:
            return "client_error"
        elif entry.status_code >= 500:
            return "server_error"
        else:
            return "normal"
    
    def _show_response_details(self, entry: RequestEntry):
        """Show response details dialog."""
        dialog = ResponseDetailsDialog(self, entry)
        dialog.show()
        
    def _copy_url(self):
        """Copy selected URL to clipboard."""
        selection = self.tree.selection()
        if not selection:
            return
            
        item = selection[0]
        values = self.tree.item(item, "values")
        if values and len(values) > 2:
            url = values[2]
            self.clipboard_clear()
            self.clipboard_append(url)
            
    def _clear_selection(self):
        """Clear tree selection."""
        self.tree.selection_remove(self.tree.selection())
        
    def clear_logs(self):
        """Clear all monitoring logs with error handling."""
        try:
            if messagebox.askyesno("Clear Logs", "Are you sure you want to clear all monitoring logs?"):
                self.entries.clear()
                self.filtered_entries.clear()
                self._refresh_tree()
                
        except Exception as e:
            self.error_manager.handle_error(
                category=ErrorCategory.UI,
                severity=ErrorSeverity.LOW,
                message=f"Failed to clear monitoring logs: {str(e)}",
                context={'operation': 'clear_logs'},
                exception=e
            )
            
            # Show error message to user through error handler
            if self.error_handler:
                self.error_handler.handle_error(
                    category=ErrorCategory.UI,
                    severity=ErrorSeverity.MEDIUM,
                    message="Failed to clear monitoring logs",
                    details=str(e),
                    show_dialog=True
                )
            else:
                messagebox.showerror("Error", f"Failed to clear logs: {str(e)}")
            
    def get_entry_count(self) -> int:
        """Get total number of entries."""
        return len(self.entries)
        
    def get_filtered_count(self) -> int:
        """Get number of filtered entries."""
        return len(self.filtered_entries)
    
    def _setup_performance_integration(self):
        """Set up performance monitoring integration."""
        # Get performance components
        memory_manager = self.performance_monitor.get_memory_manager()
        update_throttler = self.performance_monitor.get_update_throttler()
        
        if memory_manager:
            # Register cleanup callback for memory management
            memory_manager.add_cleanup_callback(self._on_memory_cleanup)
            
            # Register memory warning callback
            memory_manager.add_memory_warning_callback(self._on_memory_warning)
        
        if update_throttler:
            # Store reference for throttled updates
            self.update_throttler = update_throttler
        
        # Add performance alert callback
        self.performance_monitor.add_alert_callback(self._on_performance_alert)
    
    def _on_memory_cleanup(self, entries_to_remove: int):
        """Handle memory cleanup request."""
        try:
            if entries_to_remove <= 0:
                return
            
            # Sort entries by timestamp (oldest first)
            sorted_entries = sorted(
                self.entries.items(),
                key=lambda x: x[1].timestamp
            )
            
            # Remove oldest entries
            entries_removed = 0
            for request_id, _ in sorted_entries:
                if entries_removed >= entries_to_remove:
                    break
                
                if request_id in self.entries:
                    del self.entries[request_id]
                    entries_removed += 1
            
            # Update filtered entries list
            self.filtered_entries = [
                rid for rid in self.filtered_entries
                if rid in self.entries
            ]
            
            # Schedule UI update
            self._schedule_ui_update()
            
            self.error_manager.handle_error(
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.LOW,
                message=f"Memory cleanup: removed {entries_removed} old entries",
                context={'entries_removed': entries_removed}
            )
            
        except Exception as e:
            self.error_manager.handle_error(
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.MEDIUM,
                message=f"Error during memory cleanup: {str(e)}",
                exception=e
            )
    
    def _on_memory_warning(self, memory_stats):
        """Handle memory usage warning."""
        try:
            # Show warning in status or log
            warning_msg = f"High memory usage: {memory_stats.process_memory_mb:.1f}MB"
            
            # Could show a warning dialog or status message
            # For now, just log it
            self.error_manager.handle_error(
                category=ErrorCategory.SYSTEM,
                severity=ErrorSeverity.LOW,
                message=warning_msg,
                context={
                    'memory_mb': memory_stats.process_memory_mb,
                    'entries_count': memory_stats.entries_count
                }
            )
            
        except Exception as e:
            print(f"Error handling memory warning: {e}")
    
    def _on_performance_alert(self, alert_type: str, alert_data: dict):
        """Handle performance alerts."""
        try:
            severity_map = {
                'warning': ErrorSeverity.LOW,
                'error': ErrorSeverity.MEDIUM,
                'critical': ErrorSeverity.HIGH
            }
            
            severity = severity_map.get(alert_data.get('severity', 'warning'), ErrorSeverity.LOW)
            
            self.error_manager.handle_error(
                category=ErrorCategory.PERFORMANCE,
                severity=severity,
                message=f"Performance alert: {alert_data.get('message', alert_type)}",
                context={
                    'alert_type': alert_type,
                    'alert_data': alert_data
                }
            )
            
        except Exception as e:
            print(f"Error handling performance alert: {e}")
    
    def _schedule_ui_update(self):
        """Schedule UI update with throttling."""
        if not self.update_pending:
            self.update_pending = True
            
            # Use throttled update if available
            if hasattr(self, 'update_throttler') and self.update_throttler:
                success = self.update_throttler.request_update(
                    lambda: self.after_idle(self._update_ui),
                    priority=1
                )
                if not success:
                    # Fallback to direct update if throttled
                    self.after_idle(self._update_ui)
            else:
                self.after_idle(self._update_ui)
    
    def _update_ui(self):
        """Update the UI with current data (with performance optimizations)."""
        self.update_pending = False
        
        try:
            # Update memory manager with current entry count
            memory_manager = self.performance_monitor.get_memory_manager()
            if memory_manager:
                memory_manager.update_entries_count(len(self.entries))
            
            # Apply filters and update display
            self._apply_filters()
            
            # Use virtual scrolling for large datasets
            if self.virtual_scrolling and len(self.filtered_entries) > 200:
                self._refresh_tree_virtual()
            else:
                self._refresh_tree()
                
        except Exception as e:
            self.error_manager.handle_error(
                category=ErrorCategory.UI,
                severity=ErrorSeverity.MEDIUM,
                message=f"Error updating monitoring UI: {str(e)}",
                exception=e
            )
    
    def _refresh_tree_virtual(self):
        """Refresh tree view with virtual scrolling for large datasets."""
        try:
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)
            
            # Calculate visible range
            total_entries = len(self.filtered_entries)
            self.total_items = total_entries
            
            # Only render visible items (performance optimization)
            start_idx, end_idx = self.visible_range
            end_idx = min(end_idx, total_entries)
            
            visible_entries = self.filtered_entries[start_idx:end_idx]
            
            # Add visible entries to tree
            for request_id in visible_entries:
                if request_id not in self.entries:
                    continue
                    
                entry = self.entries[request_id]
                
                # Truncate response body for display (memory optimization)
                memory_manager = self.performance_monitor.get_memory_manager()
                if memory_manager and entry.body_preview:
                    entry.body_preview = memory_manager.truncate_response_body(
                        entry.body_preview,
                        entry.response_headers.get('content-type', '')
                    )
                
                # Format values
                timestamp = entry.timestamp.strftime("%H:%M:%S.%f")[:-3]
                method = entry.method
                url = entry.url
                proxy = entry.proxy_decision
                status = entry.get_status_display()
                response_time = f"{entry.response_time:.0f}" if entry.response_time else ""
                
                # Determine tag for error highlighting
                tag = self._get_status_tag(entry)
                
                # Insert item with appropriate tag
                self.tree.insert("", "end", values=(timestamp, method, url, proxy, status, response_time), tags=(tag,))
            
            # Update scrollbar to reflect virtual scrolling
            if total_entries > 0:
                # This is a simplified virtual scrolling - in a full implementation,
                # you'd need to customize the scrollbar behavior
                pass
                
        except Exception as e:
            print(f"Error in virtual tree refresh: {e}")
            # Fallback to regular refresh
            self._refresh_tree()
    
    def _on_mousewheel(self, event):
        """Handle mouse wheel for virtual scrolling."""
        if not self.virtual_scrolling or self.total_items <= 200:
            return
        
        try:
            # Calculate scroll direction
            if event.delta:
                delta = -1 * (event.delta / 120)
            else:
                delta = -1 if event.num == 4 else 1
            
            # Update visible range
            start_idx, end_idx = self.visible_range
            range_size = end_idx - start_idx
            
            new_start = max(0, min(self.total_items - range_size, start_idx + int(delta * 5)))
            new_end = min(self.total_items, new_start + range_size)
            
            if (new_start, new_end) != self.visible_range:
                self.visible_range = (new_start, new_end)
                self._refresh_tree_virtual()
            
        except Exception as e:
            print(f"Error in virtual scrolling: {e}")
    
    def cleanup_resources(self):
        """Clean up resources when view is destroyed."""
        try:
            # Stop performance monitoring
            if hasattr(self, 'performance_monitor'):
                self.performance_monitor.stop_monitoring()
            
            # Clear entries to free memory
            self.entries.clear()
            self.filtered_entries.clear()
            
        except Exception as e:
            print(f"Error during resource cleanup: {e}")
    
    def get_performance_stats(self) -> dict:
        """Get performance statistics for this view."""
        try:
            if hasattr(self, 'performance_monitor'):
                stats = self.performance_monitor.get_performance_stats()
                return {
                    'entries_count': len(self.entries),
                    'filtered_count': len(self.filtered_entries),
                    'memory_usage_mb': stats.memory_stats.process_memory_mb if stats.memory_stats else 0,
                    'performance_score': stats.performance_score,
                    'virtual_scrolling': self.virtual_scrolling,
                    'visible_range': self.visible_range,
                    'total_items': self.total_items
                }
            else:
                return {
                    'entries_count': len(self.entries),
                    'filtered_count': len(self.filtered_entries)
                }
        except Exception as e:
            print(f"Error getting performance stats: {e}")
            return {}