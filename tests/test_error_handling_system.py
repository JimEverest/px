#!/usr/bin/env python3
"""
Tests for comprehensive error handling and recovery system.

This module tests the error handling, retry mechanisms, fallback strategies,
and recovery capabilities of the px UI client.
"""

import pytest
import threading
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from px_ui.error_handling import (
    ErrorManager, ErrorCategory, ErrorSeverity, ErrorInfo,
    RetryManager, RetryPolicy, ExponentialBackoff, LinearBackoff, FixedBackoff,
    FallbackManager, FallbackStrategy,
    PACRecoveryStrategy, NetworkRecoveryStrategy, ProxyRecoveryStrategy, ConfigurationRecoveryStrategy
)


class TestErrorManager:
    """Test the ErrorManager class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.error_manager = ErrorManager()
        self.mock_handler = Mock()
        self.mock_handler.can_handle.return_value = True
        self.mock_handler.handle.return_value = True
    
    def test_error_manager_initialization(self):
        """Test error manager initialization."""
        assert self.error_manager is not None
        assert len(self.error_manager._handlers) == 0
        assert len(self.error_manager._error_history) == 0
        assert self.error_manager.max_history_size == 1000
    
    def test_add_remove_handler(self):
        """Test adding and removing error handlers."""
        # Add handler
        self.error_manager.add_handler(self.mock_handler)
        assert len(self.error_manager._handlers) == 1
        asser