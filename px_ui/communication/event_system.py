"""
Complete event communication system for proxy-UI communication.

This module provides a high-level interface for the event communication system,
combining the event queue, processor, and filtering capabilities.
"""

from typing import Callable, Optional, List
from datetime import datetime

from .events import BaseEvent, EventType, RequestEvent, ResponseEvent, ErrorEvent, StatusEvent, ProxyDecisionUpdateEvent
from .event_queue import EventQueue, EventFilter
from .event_processor import EventProcessor


class EventSystem:
    """
    High-level interface for the event communication system.
    
    This class provides a simple interface for setting up and managing
    the complete event communication system between proxy and UI.
    """
    
    def __init__(self, queue_size: int = 1000, max_events_per_second: int = 50):
        """
        Initialize the event system.
        
        Args:
            queue_size: Maximum size of event queue
            max_events_per_second: Maximum events to process per second
        """
        self.queue = EventQueue(max_size=queue_size)
        self.processor = EventProcessor(self.queue, max_events_per_second)
        self.filter = EventFilter()
        
        # Set initial filter
        self.processor.set_filter(self.filter)
    
    def start(self):
        """Start the event processing system."""
        self.processor.start_processing()
    
    def stop(self):
        """Stop the event processing system."""
        self.processor.stop_processing()
    
    def send_event(self, event: BaseEvent, block: bool = False, timeout: Optional[float] = None) -> bool:
        """
        Send an event to the system.
        
        Args:
            event: Event to send
            block: Whether to block if queue is full
            timeout: Timeout for blocking operation
            
        Returns:
            True if event was sent successfully
        """
        return self.queue.put_event(event, block=block, timeout=timeout)
    
    def add_request_handler(self, handler: Callable[[RequestEvent], None]):
        """Add handler for request events."""
        self.processor.add_handler(EventType.REQUEST, handler)
    
    def add_response_handler(self, handler: Callable[[ResponseEvent], None]):
        """Add handler for response events."""
        self.processor.add_handler(EventType.RESPONSE, handler)
    
    def add_error_handler(self, handler: Callable[[ErrorEvent], None]):
        """Add handler for error events."""
        self.processor.add_handler(EventType.ERROR, handler)
    
    def add_status_handler(self, handler: Callable[[StatusEvent], None]):
        """Add handler for status events."""
        self.processor.add_handler(EventType.STATUS, handler)

    def add_proxy_decision_update_handler(self, handler: Callable[[ProxyDecisionUpdateEvent], None]):
        """Add handler for proxy decision update events."""
        self.processor.add_handler(EventType.PROXY_DECISION_UPDATE, handler)
    
    def remove_handler(self, event_type: EventType, handler: Callable[[BaseEvent], None]):
        """Remove an event handler."""
        self.processor.remove_handler(event_type, handler)
    
    def set_event_filter(self, event_types: Optional[List[EventType]] = None,
                        url_patterns: Optional[List[str]] = None,
                        status_codes: Optional[List[int]] = None,
                        proxy_types: Optional[List[str]] = None,
                        time_range: Optional[tuple] = None):
        """
        Set event filtering criteria.
        
        Args:
            event_types: List of event types to include
            url_patterns: List of URL patterns to match
            status_codes: List of HTTP status codes to include
            proxy_types: List of proxy types to include (DIRECT, PROXY)
            time_range: Tuple of (start_time, end_time) for time filtering
        """
        if event_types is not None:
            self.filter.set_event_types(event_types)
        
        if url_patterns is not None:
            self.filter.set_url_patterns(url_patterns)
        
        if status_codes is not None:
            self.filter.set_status_codes(status_codes)
        
        if proxy_types is not None:
            self.filter.set_proxy_types(proxy_types)
        
        if time_range is not None:
            start_time, end_time = time_range
            self.filter.set_time_range(start_time, end_time)
    
    def clear_filter(self):
        """Clear all event filtering criteria."""
        self.filter.clear()
    
    def process_batch(self, max_events: int = 10) -> int:
        """
        Process a batch of events manually (for synchronous processing).
        
        Args:
            max_events: Maximum events to process
            
        Returns:
            Number of events processed
        """
        return self.processor.process_single_batch(max_events)
    
    def get_stats(self) -> dict:
        """Get system statistics."""
        return self.processor.get_stats()
    
    def clear_queue(self):
        """Clear all events from the queue."""
        self.queue.clear()
    
    def is_running(self) -> bool:
        """Check if the event system is running."""
        return self.processor._running


# Convenience functions for creating events
def create_request_event(url: str, method: str, proxy_decision: str, request_id: str,
                        headers: Optional[dict] = None, event_id: Optional[str] = None) -> RequestEvent:
    """Create a request event."""
    import uuid
    return RequestEvent(
        event_type=EventType.REQUEST,  # This will be overridden by __post_init__
        timestamp=datetime.now(),
        event_id=event_id or str(uuid.uuid4()),
        url=url,
        method=method,
        proxy_decision=proxy_decision,
        request_id=request_id,
        headers=headers
    )


def create_response_event(request_id: str, status_code: int, headers: dict,
                         body_preview: str, content_length: int, response_time: float,
                         event_id: Optional[str] = None) -> ResponseEvent:
    """Create a response event."""
    import uuid
    return ResponseEvent(
        event_type=EventType.RESPONSE,  # This will be overridden by __post_init__
        timestamp=datetime.now(),
        event_id=event_id or str(uuid.uuid4()),
        request_id=request_id,
        status_code=status_code,
        headers=headers,
        body_preview=body_preview,
        content_length=content_length,
        response_time=response_time
    )


def create_error_event(error_type: str, error_message: str, error_details: Optional[str] = None,
                      request_id: Optional[str] = None, url: Optional[str] = None,
                      event_id: Optional[str] = None) -> ErrorEvent:
    """Create an error event."""
    import uuid
    return ErrorEvent(
        event_type=EventType.ERROR,  # This will be overridden by __post_init__
        timestamp=datetime.now(),
        event_id=event_id or str(uuid.uuid4()),
        error_type=error_type,
        error_message=error_message,
        error_details=error_details,
        request_id=request_id,
        url=url
    )


def create_status_event(is_running: bool, listen_address: str, port: int, mode: str,
                       active_connections: int, total_requests: int,
                       event_id: Optional[str] = None) -> StatusEvent:
    """Create a status event."""
    import uuid
    return StatusEvent(
        event_type=EventType.STATUS,  # This will be overridden by __post_init__
        timestamp=datetime.now(),
        event_id=event_id or str(uuid.uuid4()),
        is_running=is_running,
        listen_address=listen_address,
        port=port,
        mode=mode,
        active_connections=active_connections,
        total_requests=total_requests
    )