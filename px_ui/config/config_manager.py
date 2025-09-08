"""
Configuration manager for loading and saving application settings.
"""

import os
import json
import logging
from pathlib import Path
from typing import Optional
from .ui_settings import UISettings


class ConfigManager:
    """
    Manages loading and saving of application configuration.
    
    Handles UI settings persistence, default configuration creation,
    and configuration file validation.
    """
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_dir: Custom configuration directory path.
                       If None, uses default user config directory.
        """
        self.logger = logging.getLogger(__name__)
        
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            self.config_dir = self._get_default_config_dir()
        
        self.config_file = self.config_dir / "px_ui_config.json"
        self._ensure_config_dir()
    
    def _get_default_config_dir(self) -> Path:
        """Get the default configuration directory based on OS."""
        if os.name == 'nt':  # Windows
            config_base = os.environ.get('APPDATA', os.path.expanduser('~'))
            return Path(config_base) / "px-ui-client"
        else:  # Unix-like systems
            config_base = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
            return Path(config_base) / "px-ui-client"
    
    def _ensure_config_dir(self):
        """Ensure the configuration directory exists."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.logger.error(f"Failed to create config directory {self.config_dir}: {e}")
            raise
    
    def load_settings(self) -> UISettings:
        """
        Load UI settings from configuration file.
        
        Returns:
            UISettings object with loaded or default settings.
        """
        if not self.config_file.exists():
            self.logger.info("Configuration file not found, using defaults")
            return UISettings()
        
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            settings = UISettings.from_dict(data)
            self.logger.info(f"Loaded settings from {self.config_file}")
            return settings
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            self.logger.error(f"Failed to load settings from {self.config_file}: {e}")
            self.logger.info("Using default settings")
            return UISettings()
        except OSError as e:
            self.logger.error(f"Failed to read config file {self.config_file}: {e}")
            return UISettings()
    
    def save_settings(self, settings: UISettings) -> bool:
        """
        Save UI settings to configuration file.
        
        Args:
            settings: UISettings object to save.
            
        Returns:
            True if saved successfully, False otherwise.
        """
        try:
            # Create backup of existing config
            if self.config_file.exists():
                backup_file = self.config_file.with_suffix('.json.bak')
                self.config_file.replace(backup_file)
            
            # Save new configuration
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(settings.to_dict(), f, indent=2)
            
            self.logger.info(f"Saved settings to {self.config_file}")
            return True
            
        except OSError as e:
            self.logger.error(f"Failed to save settings to {self.config_file}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error saving settings: {e}")
            return False
    
    def get_proxy_config(self) -> dict:
        """
        Get proxy configuration including NTLM settings.
        
        Returns:
            Dictionary with proxy configuration
        """
        try:
            settings = self.load_settings()
            
            # Default proxy configuration
            proxy_config = {
                'listen_address': settings.proxy_address,
                'port': settings.proxy_port,
                'threads': 5,
                'enable_ntlm': True,
                'auth_method': 'ANY',
                'upstream_proxy': '',
                'domain': '',
                'username': '',
                'client_auth': ['NONE'],
                'auto_detect_domain': True
            }
            
            # Load additional proxy config if exists
            proxy_config_file = self.config_dir / "proxy_config.json"
            if proxy_config_file.exists():
                with open(proxy_config_file, 'r', encoding='utf-8') as f:
                    additional_config = json.load(f)
                    proxy_config.update(additional_config)
            
            return proxy_config
            
        except Exception as e:
            self.logger.error(f"Failed to load proxy configuration: {e}")
            return {
                'listen_address': '127.0.0.1',
                'port': 3128,
                'threads': 5,
                'enable_ntlm': True,
                'auth_method': 'ANY',
                'upstream_proxy': '',
                'domain': '',
                'username': '',
                'client_auth': ['NONE'],
                'auto_detect_domain': True
            }
    
    def save_proxy_config(self, config: dict) -> bool:
        """
        Save proxy configuration including NTLM settings.
        
        Args:
            config: Dictionary with proxy configuration
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            proxy_config_file = self.config_dir / "proxy_config.json"
            
            # Create backup if exists
            if proxy_config_file.exists():
                backup_file = proxy_config_file.with_suffix('.json.bak')
                proxy_config_file.replace(backup_file)
            
            # Save proxy configuration
            with open(proxy_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2)
            
            self.logger.info(f"Saved proxy configuration to {proxy_config_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save proxy configuration: {e}")
            return False
    
    def reset_to_defaults(self) -> UISettings:
        """
        Reset configuration to defaults and save.
        
        Returns:
            New UISettings object with default values.
        """
        default_settings = UISettings()
        
        if self.save_settings(default_settings):
            self.logger.info("Reset configuration to defaults")
        else:
            self.logger.warning("Failed to save default configuration")
        
        return default_settings
    
    def backup_config(self, backup_path: Optional[str] = None) -> bool:
        """
        Create a backup of the current configuration.
        
        Args:
            backup_path: Custom backup file path. If None, creates
                        timestamped backup in config directory.
                        
        Returns:
            True if backup created successfully, False otherwise.
        """
        if not self.config_file.exists():
            self.logger.warning("No configuration file to backup")
            return False
        
        try:
            if backup_path:
                backup_file = Path(backup_path)
            else:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_file = self.config_dir / f"px_ui_config_{timestamp}.json"
            
            backup_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.config_file, 'rb') as src, open(backup_file, 'wb') as dst:
                dst.write(src.read())
            
            self.logger.info(f"Created configuration backup: {backup_file}")
            return True
            
        except OSError as e:
            self.logger.error(f"Failed to create backup: {e}")
            return False
    
    def restore_config(self, backup_path: str) -> bool:
        """
        Restore configuration from backup file.
        
        Args:
            backup_path: Path to backup file to restore.
            
        Returns:
            True if restored successfully, False otherwise.
        """
        backup_file = Path(backup_path)
        
        if not backup_file.exists():
            self.logger.error(f"Backup file not found: {backup_file}")
            return False
        
        try:
            # Validate backup file by trying to load it
            with open(backup_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            UISettings.from_dict(data)  # Validate structure
            
            # Create backup of current config
            if self.config_file.exists():
                current_backup = self.config_file.with_suffix('.json.pre_restore')
                self.config_file.replace(current_backup)
            
            # Restore from backup
            with open(backup_file, 'rb') as src, open(self.config_file, 'wb') as dst:
                dst.write(src.read())
            
            self.logger.info(f"Restored configuration from {backup_file}")
            return True
            
        except (json.JSONDecodeError, ValueError, OSError) as e:
            self.logger.error(f"Failed to restore configuration: {e}")
            return False
    
    def save_pac_configuration(self, pac_config) -> bool:
        """Save PAC configuration to persistent storage."""
        try:
            # Load existing configuration
            config_data = {}
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)
            
            # Update PAC configuration
            pac_data = {
                'source_type': pac_config.source_type,
                'source_path': pac_config.source_path,
                'content': pac_config.content,
                'encoding': pac_config.encoding
            }
            
            config_data['pac_configuration'] = pac_data
            
            # Save updated configuration
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug("PAC configuration saved successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save PAC configuration: {e}")
            return False
    
    def load_pac_configuration(self):
        """Load PAC configuration from persistent storage."""
        try:
            if not self.config_file.exists():
                self.logger.debug("No configuration file found")
                return None
            
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            pac_data = config_data.get('pac_configuration')
            if pac_data:
                from px_ui.models.pac_configuration import PACConfiguration
                return PACConfiguration(
                    source_type=pac_data.get('source_type', 'inline'),
                    source_path=pac_data.get('source_path', ''),
                    content=pac_data.get('content', ''),
                    encoding=pac_data.get('encoding', 'utf-8')
                )
            
            self.logger.debug("No PAC configuration found in config file")
            return None
            
        except Exception as e:
            self.logger.error(f"Failed to load PAC configuration: {e}")
            return None
    
    def get_config_info(self) -> dict:
        """
        Get information about the current configuration.
        
        Returns:
            Dictionary with configuration file information.
        """
        info = {
            'config_dir': str(self.config_dir),
            'config_file': str(self.config_file),
            'exists': self.config_file.exists(),
            'readable': False,
            'size': 0,
            'modified': None
        }
        
        if info['exists']:
            try:
                stat = self.config_file.stat()
                info['size'] = stat.st_size
                info['modified'] = stat.st_mtime
                info['readable'] = os.access(self.config_file, os.R_OK)
            except OSError:
                pass
        
        return info