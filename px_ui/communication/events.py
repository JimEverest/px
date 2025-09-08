"""
Event data structures for proxy-to-UI communication.

This module defines the event types used to communicate between the proxy engine
and the UI components in a thread-safe manner.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional


class EventType(Enum):
    """Types of events that can be sent from proxy to UI."""
    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"
    STATUS = "status"
    PROXY_DECISION_UPDATE = "proxy_decision_update"


@dataclass
class BaseEvent:
    """Base class for all events."""
    event_type: EventType
    timestamp: datetime
    event_id: str
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now()


@dataclass
class RequestEvent(BaseEvent):
    """Event sent when a new request is started."""
    url: str
    method: str
    proxy_decision: str  # "DIRECT" or "PROXY host:port"
    request_id: str
    headers: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.event_type = EventType.REQUEST


@dataclass
class ResponseEvent(BaseEvent):
    """Event sent when a response is received."""
    request_id: str
    status_code: int
    headers: Dict[str, str]
    body_preview: str  # First 500 chars
    content_length: int
    response_time: float
    
    def __post_init__(self):
        super().__post_init__()
        self.event_type = EventType.RESPONSE


@dataclass
class ErrorEvent(BaseEvent):
    """Event sent when an error occurs."""
    error_type: str  # "network", "auth", "pac", "config"
    error_message: str
    error_details: Optional[str] = None
    request_id: Optional[str] = None
    url: Optional[str] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.event_type = EventType.ERROR


@dataclass
class StatusEvent(BaseEvent):
    """Event sent when proxy status changes."""
    is_running: bool
    listen_address: str
    port: int
    mode: str  # "manual", "pac", "auto"
    active_connections: int
    total_requests: int
    
    def __post_init__(self):
        super().__post_init__()
        self.event_type = EventType.STATUS


@dataclass
class ProxyDecisionUpdateEvent(BaseEvent):
    """Event sent when the proxy decision for a request is updated."""
    request_id: str
    proxy_decision: str
    
    def __post_init__(self):
        super().__post_init__()
        self.event_type = EventType.PROXY_DECISION_UPDATE
