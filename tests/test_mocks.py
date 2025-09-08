"""
Mock implementations for testing components that don't exist yet.
"""

from unittest.mock import Mock, MagicMock
from typing import Optional, Dict, Any, List
from datetime import datetime
import uuid


class MockPACValidator:
    """Mock PAC validator for testing."""
    
    def __init__(self):
        self.validation_results = {}
    
    def validate_syntax(self, pac_content: str) -> tuple[bool, List[str]]:
        """Mock PAC syntax validation."""
        if "function FindProxyForURL" not in pac_content:
            return False, ["Missing FindProxyForURL function"]
        
        if "INVALID_SYNTAX" in pac_content:
            return False, ["SyntaxError: Invalid syntax"]
        
        return True, []
    
    def test_url(self, url: str, pac_content: str) -> str:
        """Mock URL testing against PAC."""
        if "internal.company.com" in url:
            return "DIRECT"
        elif "google.com" in url:
            return "PROXY proxy1.company.com:8080; PROXY proxy2.company.com:8080"
        else:
            return "PROXY proxy.company.com:8080"
    
    def load_pac_from_file(self, file_path: str) -> str:
        """Mock loading PAC from file."""
        if "nonexistent" in file_path:
            raise FileNotFoundError(f"File not found: {file_path}")
        
        return '''
        function FindProxyForURL(url, host) {
            if (host == "example.com") return "DIRECT";
            return "PROXY proxy.corp.com:8080";
        }
        '''
    
    def load_pac_from_url(self, url: str) -> str:
        """Mock loading PAC from URL."""
        if "invalid" in url:
            raise Exception("Network error")
        
        return '''
        function FindProxyForURL(url, host) {
            return "PROXY proxy.company.com:8080";
        }
        '''
    
    def create_pac_configuration(self, source_type: str, source_path: str, content: str):
        """Mock creating PAC configuration."""
        from px_ui.models.pac_configuration import PACConfiguration
        
        is_valid, errors = self.validate_syntax(content)
        
        return PACConfiguration(
            source_type=source_type,
            source_path=source_path,
            content=content,
            encoding="utf-8",
            is_valid=is_valid,
            validation_errors=errors
        )
    
    def detect_encoding(self, content_bytes: bytes) -> str:
        """Mock encoding detection."""
        if content_bytes.startswith(b'\xff\xfe') or content_bytes.startswith(b'\xfe\xff'):
            return 'utf-16'
        elif content_bytes.startswith(b'\xef\xbb\xbf'):
            return 'utf-8-sig'
        else:
            return 'utf-8'


class MockConfigurationBridge:
    """Mock configuration bridge for testing."""
    
    def __init__(self):
        self.current_pac_config = None
        self.proxy_running = False
        self.proxy_port = 0
        self.proxy_address = ""
        self.upstream_proxy = None
    
    def apply_pac_configuration(self, pac_config) -> bool:
        """Mock applying PAC configuration."""
        if pac_config.is_valid:
            self.current_pac_config = pac_config
            return True
        return False
    
    def get_current_pac_configuration(self):
        """Mock getting current PAC configuration."""
        return self.current_pac_config
    
    def start_proxy(self, port: int, address: str = "127.0.0.1"):
        """Mock starting proxy."""
        self.proxy_running = True
        self.proxy_port = port
        self.proxy_address = address
    
    def stop_proxy(self):
        """Mock stopping proxy."""
        self.proxy_running = False
        self.proxy_port = 0
        self.proxy_address = ""
    
    def get_proxy_status(self):
        """Mock getting proxy status."""
        from px_ui.models.proxy_status import ProxyStatus
        
        return ProxyStatus(
            is_running=self.proxy_running,
            listen_address=self.proxy_address,
            port=self.proxy_port,
            mode="pac" if self.current_pac_config else "manual",
            active_connections=0,
            total_requests=0
        )
    
    def set_upstream_proxy(self, proxy_url: str):
        """Mock setting upstream proxy."""
        self.upstream_proxy = proxy_url


class MockEnhancedPxHandler:
    """Mock enhanced PX handler for testing."""
    
    def __init__(self, event_queue):
        self.event_queue = event_queue
        self.captured_requests = []
        self.captured_responses = []
        self.captured_errors = []
    
    def capture_request(self, url: str, method: str, proxy_decision: str, request_id: str = None):
        """Mock request capture."""
        if request_id is None:
            request_id = str(uuid.uuid4())
        
        from px_ui.communication.events import RequestEvent
        
        event = RequestEvent(
            event_type=None,  # Will be set by __post_init__
            timestamp=datetime.now(),
            event_id=str(uuid.uuid4()),
            url=url,
            method=method,
            proxy_decision=proxy_decision,
            request_id=request_id
        )
        
        self.captured_requests.append(event)
        self.event_queue.put_event(event)
    
    def capture_response(self, request_id: str, status_code: int, headers: Dict[str, str], 
                        body_preview: str, response_time: float):
        """Mock response capture."""
        from px_ui.communication.events import ResponseEvent
        
        event = ResponseEvent(
            event_type=None,  # Will be set by __post_init__
            timestamp=datetime.now(),
            event_id=str(uuid.uuid4()),
            request_id=request_id,
            status_code=status_code,
            headers=headers,
            body_preview=body_preview,
            content_length=len(body_preview),
            response_time=response_time
        )
        
        self.captured_responses.append(event)
        self.event_queue.put_event(event)
    
    def capture_error(self, request_id: str, error_type: str, message: str, details: Dict[str, Any] = None):
        """Mock error capture."""
        from px_ui.communication.events import ErrorEvent
        
        event = ErrorEvent(
            event_type=None,  # Will be set by __post_init__
            timestamp=datetime.now(),
            event_id=str(uuid.uuid4()),
            error_type=error_type,
            error_message=message,
            error_details=str(details) if details else None,
            request_id=request_id
        )
        
        self.captured_errors.append(event)
        self.event_queue.put_event(event)


class MockPerformanceMonitor:
    """Mock performance monitor for testing."""
    
    def __init__(self):
        self.monitoring = False
        self.start_memory = 0
        self.peak_memory = 0
    
    def start_monitoring(self):
        """Mock start monitoring."""
        self.monitoring = True
        import psutil
        import os
        process = psutil.Process(os.getpid())
        self.start_memory = process.memory_info().rss / 1024 / 1024
        self.peak_memory = self.start_memory
    
    def stop_monitoring(self) -> Dict[str, Any]:
        """Mock stop monitoring."""
        self.monitoring = False
        import psutil
        import os
        process = psutil.Process(os.getpid())
        current_memory = process.memory_info().rss / 1024 / 1024
        self.peak_memory = max(self.peak_memory, current_memory)
        
        return {
            'peak_memory_mb': self.peak_memory,
            'start_memory_mb': self.start_memory,
            'memory_increase_mb': self.peak_memory - self.start_memory
        }


class MockUpdateThrottler:
    """Mock update throttler for testing."""
    
    def __init__(self, max_updates_per_second: int = 50):
        self.max_updates_per_second = max_updates_per_second
        self.update_count = 0
        self.last_update_time = 0
    
    def request_update(self, update_func):
        """Mock update request."""
        import time
        current_time = time.time()
        
        # Simple throttling logic
        if current_time - self.last_update_time >= (1.0 / self.max_updates_per_second):
            update_func()
            self.update_count += 1
            self.last_update_time = current_time


class MockLogRotator:
    """Mock log rotator for testing."""
    
    def __init__(self, max_entries: int = 1000, cleanup_threshold: int = 1200):
        self.max_entries = max_entries
        self.cleanup_threshold = cleanup_threshold
    
    def check_rotation(self, entries: List[Any]):
        """Mock rotation check."""
        if len(entries) > self.cleanup_threshold:
            self.rotate_logs(entries)
    
    def rotate_logs(self, entries: List[Any]):
        """Mock log rotation."""
        if len(entries) > self.max_entries:
            # Keep only the most recent entries
            entries[:] = entries[-self.max_entries:]


class MockConfigLoader:
    """Mock configuration loader for testing."""
    
    def __init__(self):
        self.test_configs = {
            'development': {
                'https_proxy': 'http://127.0.0.1:33210',
                'proxy_host': '127.0.0.1',
                'proxy_port': 33210
            }
        }
    
    def load_test_configurations(self) -> Dict[str, Any]:
        """Mock loading test configurations."""
        return self.test_configs
    
    def get_test_proxy_config(self) -> Dict[str, Any]:
        """Mock getting test proxy config."""
        return self.test_configs.get('development', {})
    
    def load_config_file(self, file_path: str) -> Dict[str, Any]:
        """Mock loading config file."""
        if "test_proxy_config.ini" in file_path:
            return {
                'proxy': '127.0.0.1:33210',
                'port': '3128',
                'auth': 'NTLM'
            }
        return {}