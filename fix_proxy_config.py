#!/usr/bin/env python3
"""
Fix Proxy Configuration

This script fixes the proxy configuration to work without NTLM for testing.
"""

import sys
import os
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from px_ui.config.config_manager import ConfigManager


def fix_config():
    """Fix the proxy configuration."""
    print("🔧 Fixing Proxy Configuration")
    print("=" * 50)
    
    config_manager = ConfigManager()
    
    # Get current config
    current_config = config_manager.get_proxy_config()
    print(f"Current config: {current_config}")
    
    # Create fixed configuration
    fixed_config = {
        'listen_address': '127.0.0.1',
        'port': 3128,
        'threads': 5,
        'enable_ntlm': False,  # Disable NTLM for now
        'auth_method': 'NONE',  # No authentication
        'upstream_proxy': '',  # No upstream proxy
        'domain': '',
        'username': '',
        'client_auth': ['NONE'],
        'auto_detect_domain': True
    }
    
    print(f"Fixed config: {fixed_config}")
    
    # Save fixed configuration
    success = config_manager.save_proxy_config(fixed_config)
    
    if success:
        print("✅ Configuration fixed successfully!")
        print("\nNext steps:")
        print("1. Restart the px UI application")
        print("2. Start the proxy service")
        print("3. Test with: curl -x http://127.0.0.1:3128 http://httpbin.org/ip")
        print("\nTo enable NTLM later:")
        print("1. Go to NTLM Authentication tab")
        print("2. Set a real upstream proxy server")
        print("3. Enable NTLM authentication")
    else:
        print("❌ Failed to save configuration")
    
    return success


def main():
    """Main function."""
    print("🔧 px UI Proxy Configuration Fix")
    print("=" * 50)
    
    success = fix_config()
    
    if success:
        print("\n🎉 Configuration fixed! Please restart the application.")
    else:
        print("\n❌ Failed to fix configuration.")
    
    return success


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)