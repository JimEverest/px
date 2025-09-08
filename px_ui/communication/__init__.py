# Communication module for proxy-UI event handling

from .events import (
    BaseEvent, EventType, RequestEvent, ResponseEvent, ErrorEvent, StatusEvent
)
from .event_queue import EventQueue, EventFilter
from .event_processor import EventProcessor, EventThrottler
from .event_system import (
    EventSystem, create_request_event, create_response_event,
    create_error_event, create_status_event
)

__all__ = [
    # Events
    'BaseEvent', 'EventType', 'RequestEvent', 'ResponseEvent', 'ErrorEvent', 'StatusEvent',
    # Queue and filtering
    'EventQueue', 'EventFilter',
    # Processing
    'EventProcessor', 'EventThrottler',
    # High-level interface
    'EventSystem',
    # Convenience functions
    'create_request_event', 'create_response_event', 'create_error_event', 'create_status_event'
]