"""
Configuration management for the px UI client.

This module provides configuration loading, saving, and validation
for application settings and user preferences.
"""

from .config_manager import ConfigManager
from .ui_settings import UISettings

__all__ = ['ConfigManager', 'UISettings']