"""
Unit tests for data models in px_ui.models module.
Tests validation, serialization, and data integrity for core data structures.
"""

import pytest
from datetime import datetime
from dataclasses import asdict
import json

from px_ui.models.request_data import RequestData
from px_ui.models.response_data import ResponseData
from px_ui.models.pac_configuration import PACConfiguration
from px_ui.models.proxy_status import ProxyStatus


class TestRequestData:
    """Test RequestData model validation and functionality."""
    
    def test_request_data_creation(self):
        """Test creating RequestData with valid data."""
        timestamp = datetime.now()
        request = RequestData(
            timestamp=timestamp,
            url="https://example.com",
            method="GET",
            proxy_decision="PROXY 127.0.0.1:8080",
            status="pending",
            request_id="req_123"
        )
        
        assert request.timestamp == timestamp
        assert request.url == "https://example.com"
        assert request.method == "GET"
        assert request.proxy_decision == "PROXY 127.0.0.1:8080"
        assert request.status == "pending"
        assert request.request_id == "req_123"
    
    def test_request_data_direct_proxy(self):
        """Test RequestData with DIRECT proxy decision."""
        request = RequestData(
            timestamp=datetime.now(),
            url="https://internal.company.com",
            method="POST",
            proxy_decision="DIRECT",
            status="completed",
            request_id="req_456"
        )
        
        assert request.proxy_decision == "DIRECT"
        assert request.status == "completed"
    
    def test_request_data_serialization(self):
        """Test RequestData can be serialized to dict."""
        timestamp = datetime.now()
        request = RequestData(
            timestamp=timestamp,
            url="https://api.example.com/data",
            method="PUT",
            proxy_decision="PROXY proxy.corp.com:3128",
            status="error",
            request_id="req_789"
        )
        
        data_dict = asdict(request)
        assert data_dict["url"] == "https://api.example.com/data"
        assert data_dict["method"] == "PUT"
        assert data_dict["proxy_decision"] == "PROXY proxy.corp.com:3128"
        assert data_dict["status"] == "error"
        assert data_dict["request_id"] == "req_789"
    
    def test_request_data_status_values(self):
        """Test valid status values for RequestData."""
        valid_statuses = ["pending", "completed", "error"]
        
        for status in valid_statuses:
            request = RequestData(
                timestamp=datetime.now(),
                url="https://test.com",
                method="GET",
                proxy_decision="DIRECT",
                status=status,
                request_id=f"req_{status}"
            )
            assert request.status == status


class TestResponseData:
    """Test ResponseData model validation and functionality."""
    
    def test_response_data_creation(self):
        """Test creating ResponseData with valid data."""
        response = ResponseData(
            request_id="req_123",
            status_code=200,
            headers={"Content-Type": "application/json", "Content-Length": "1024"},
            body_preview='{"status": "success", "data": [...]}',
            content_length=1024,
            response_time=0.245
        )
        
        assert response.request_id == "req_123"
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "application/json"
        assert response.body_preview.startswith('{"status": "success"')
        assert response.content_length == 1024
        assert response.response_time == 0.245
    
    def test_response_data_error_status(self):
        """Test ResponseData with error status codes."""
        error_codes = [400, 401, 403, 404, 500, 502, 503]
        
        for code in error_codes:
            response = ResponseData(
                request_id=f"req_error_{code}",
                status_code=code,
                headers={"Content-Type": "text/html"},
                body_preview=f"<html><body>Error {code}</body></html>",
                content_length=50,
                response_time=0.1
            )
            assert response.status_code == code
            assert response.status_code >= 400  # Error status
    
    def test_response_data_large_content(self):
        """Test ResponseData with large content length."""
        response = ResponseData(
            request_id="req_large",
            status_code=200,
            headers={"Content-Type": "application/octet-stream"},
            body_preview="Binary data preview...",
            content_length=10485760,  # 10MB
            response_time=2.5
        )
        
        assert response.content_length == 10485760
        assert response.response_time == 2.5
    
    def test_response_data_empty_headers(self):
        """Test ResponseData with empty headers."""
        response = ResponseData(
            request_id="req_empty_headers",
            status_code=204,
            headers={},
            body_preview="",
            content_length=0,
            response_time=0.05
        )
        
        assert response.headers == {}
        assert response.body_preview == ""
        assert response.content_length == 0


class TestPACConfiguration:
    """Test PACConfiguration model validation and functionality."""
    
    def test_pac_config_file_source(self):
        """Test PACConfiguration with file source."""
        pac_content = '''
        function FindProxyForURL(url, host) {
            if (host == "example.com") return "DIRECT";
            return "PROXY proxy.corp.com:8080";
        }
        '''
        
        config = PACConfiguration(
            source_type="file",
            source_path="/path/to/proxy.pac",
            content=pac_content,
            encoding="utf-8",
            is_valid=True,
            validation_errors=[]
        )
        
        assert config.source_type == "file"
        assert config.source_path == "/path/to/proxy.pac"
        assert "FindProxyForURL" in config.content
        assert config.encoding == "utf-8"
        assert config.is_valid is True
        assert config.validation_errors == []
    
    def test_pac_config_url_source(self):
        """Test PACConfiguration with URL source."""
        config = PACConfiguration(
            source_type="url",
            source_path="http://proxy.corp.com/proxy.pac",
            content="function FindProxyForURL(url, host) { return 'DIRECT'; }",
            encoding="utf-8",
            is_valid=True,
            validation_errors=[]
        )
        
        assert config.source_type == "url"
        assert config.source_path.startswith("http://")
        assert config.is_valid is True
    
    def test_pac_config_inline_source(self):
        """Test PACConfiguration with inline source."""
        inline_content = "function FindProxyForURL(url, host) { return 'PROXY 127.0.0.1:8080'; }"
        
        config = PACConfiguration(
            source_type="inline",
            source_path="",
            content=inline_content,
            encoding="utf-8",
            is_valid=True,
            validation_errors=[]
        )
        
        assert config.source_type == "inline"
        assert config.source_path == ""
        assert config.content == inline_content
    
    def test_pac_config_invalid_syntax(self):
        """Test PACConfiguration with invalid JavaScript syntax."""
        invalid_content = "function FindProxyForURL(url, host) { return PROXY; }"  # Missing quotes
        
        config = PACConfiguration(
            source_type="inline",
            source_path="",
            content=invalid_content,
            encoding="utf-8",
            is_valid=False,
            validation_errors=["SyntaxError: Unexpected token PROXY at line 1"]
        )
        
        assert config.is_valid is False
        assert len(config.validation_errors) > 0
        assert "SyntaxError" in config.validation_errors[0]
    
    def test_pac_config_encoding_types(self):
        """Test PACConfiguration with different encoding types."""
        # Use only supported encodings based on the model validation
        encodings = ["utf-8", "ascii", "latin-1", "cp1252"]
        
        for encoding in encodings:
            config = PACConfiguration(
                source_type="file",
                source_path=f"/path/to/proxy_{encoding}.pac",
                content="function FindProxyForURL(url, host) { return 'DIRECT'; }",
                encoding=encoding,
                is_valid=True,
                validation_errors=[]
            )
            assert config.encoding == encoding


class TestProxyStatus:
    """Test ProxyStatus model validation and functionality."""
    
    def test_proxy_status_running(self):
        """Test ProxyStatus when proxy is running."""
        status = ProxyStatus(
            is_running=True,
            listen_address="127.0.0.1",
            port=3128,
            mode="pac",
            active_connections=5,
            total_requests=1250
        )
        
        assert status.is_running is True
        assert status.listen_address == "127.0.0.1"
        assert status.port == 3128
        assert status.mode == "pac"
        assert status.active_connections == 5
        assert status.total_requests == 1250
    
    def test_proxy_status_stopped(self):
        """Test ProxyStatus when proxy is stopped."""
        # Use valid port number even when stopped (model validation requires 1-65535)
        status = ProxyStatus(
            is_running=False,
            listen_address="127.0.0.1",
            port=3128,  # Use valid port number
            mode="manual",
            active_connections=0,
            total_requests=0
        )
        
        assert status.is_running is False
        assert status.listen_address == "127.0.0.1"
        assert status.port == 3128
        assert status.active_connections == 0
        assert status.total_requests == 0
    
    def test_proxy_status_modes(self):
        """Test ProxyStatus with different proxy modes."""
        modes = ["manual", "pac", "auto"]
        
        for mode in modes:
            status = ProxyStatus(
                is_running=True,
                listen_address="0.0.0.0",
                port=8080,
                mode=mode,
                active_connections=2,
                total_requests=500
            )
            assert status.mode == mode
    
    def test_proxy_status_high_traffic(self):
        """Test ProxyStatus with high traffic numbers."""
        status = ProxyStatus(
            is_running=True,
            listen_address="127.0.0.1",
            port=3128,
            mode="pac",
            active_connections=100,
            total_requests=1000000
        )
        
        assert status.active_connections == 100
        assert status.total_requests == 1000000
    
    def test_proxy_status_serialization(self):
        """Test ProxyStatus serialization to JSON."""
        status = ProxyStatus(
            is_running=True,
            listen_address="192.168.1.100",
            port=8080,
            mode="auto",
            active_connections=25,
            total_requests=5000
        )
        
        status_dict = asdict(status)
        json_str = json.dumps(status_dict)
        parsed = json.loads(json_str)
        
        assert parsed["is_running"] is True
        assert parsed["listen_address"] == "192.168.1.100"
        assert parsed["port"] == 8080
        assert parsed["mode"] == "auto"
        assert parsed["active_connections"] == 25
        assert parsed["total_requests"] == 5000


class TestDataModelIntegration:
    """Test integration between different data models."""
    
    def test_request_response_correlation(self):
        """Test correlation between RequestData and ResponseData."""
        request_id = "req_integration_test"
        
        request = RequestData(
            timestamp=datetime.now(),
            url="https://api.example.com/users",
            method="GET",
            proxy_decision="PROXY proxy.corp.com:8080",
            status="pending",
            request_id=request_id
        )
        
        response = ResponseData(
            request_id=request_id,
            status_code=200,
            headers={"Content-Type": "application/json"},
            body_preview='{"users": [{"id": 1, "name": "John"}]}',
            content_length=256,
            response_time=0.5
        )
        
        # Verify correlation
        assert request.request_id == response.request_id
        assert request.status == "pending"  # Would be updated to "completed" in real scenario
    
    def test_pac_config_with_proxy_status(self):
        """Test PAC configuration affecting proxy status."""
        pac_config = PACConfiguration(
            source_type="inline",
            source_path="",
            content="function FindProxyForURL(url, host) { return 'PROXY 127.0.0.1:8080'; }",
            encoding="utf-8",
            is_valid=True,
            validation_errors=[]
        )
        
        proxy_status = ProxyStatus(
            is_running=True,
            listen_address="127.0.0.1",
            port=3128,
            mode="pac",  # Using PAC mode
            active_connections=0,
            total_requests=0
        )
        
        # Verify PAC is valid and proxy is in PAC mode
        assert pac_config.is_valid is True
        assert proxy_status.mode == "pac"
        assert proxy_status.is_running is True