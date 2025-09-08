#!/usr/bin/env python3
"""
Debug Proxy Issue

This script helps diagnose the 407 authentication issue with the px proxy.
"""

import sys
import os
import logging
import time
import requests
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from px_ui.config.config_manager import ConfigManager


def setup_logging():
    """Set up detailed logging."""
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def check_proxy_config():
    """Check current proxy configuration."""
    print("🔍 Checking Proxy Configuration")
    print("=" * 50)
    
    config_manager = ConfigManager()
    
    # Check proxy config
    proxy_config = config_manager.get_proxy_config()
    print(f"Current proxy config: {proxy_config}")
    
    # Check if NTLM is enabled but no upstream proxy
    if proxy_config.get('enable_ntlm', False):
        upstream_proxy = proxy_config.get('upstream_proxy', '')
        if not upstream_proxy:
            print("⚠️  WARNING: NTLM is enabled but no upstream proxy configured!")
            print("   This will cause 407 errors because px needs an upstream proxy for NTLM auth.")
            return False
        else:
            print(f"✅ Upstream proxy configured: {upstream_proxy}")
    
    return True


def check_px_state():
    """Check px library state."""
    print("\n🔍 Checking px Library State")
    print("=" * 50)
    
    try:
        from px.config import STATE
        
        print(f"px auth: {STATE.auth}")
        print(f"px listen: {STATE.listen}")
        print(f"px pac: {STATE.pac}")
        print(f"px config: {STATE.config}")
        
        if STATE.config:
            try:
                port = STATE.config.getint('proxy', 'port')
                print(f"px port: {port}")
            except Exception as e:
                print(f"Error getting port: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error checking px state: {e}")
        return False


def test_proxy_connection():
    """Test proxy connection."""
    print("\n🔍 Testing Proxy Connection")
    print("=" * 50)
    
    proxy_url = "http://127.0.0.1:3128"
    test_url = "http://httpbin.org/ip"
    
    try:
        # Test with requests
        proxies = {
            'http': proxy_url,
            'https': proxy_url
        }
        
        print(f"Testing connection to {test_url} via {proxy_url}")
        
        response = requests.get(test_url, proxies=proxies, timeout=10)
        print(f"✅ Success: {response.status_code}")
        print(f"Response: {response.text[:200]}")
        
        return True
        
    except requests.exceptions.ProxyError as e:
        print(f"❌ Proxy Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return False


def suggest_fixes():
    """Suggest fixes for common issues."""
    print("\n🔧 Suggested Fixes")
    print("=" * 50)
    
    config_manager = ConfigManager()
    proxy_config = config_manager.get_proxy_config()
    
    if proxy_config.get('enable_ntlm', False) and not proxy_config.get('upstream_proxy'):
        print("1. 🎯 MAIN ISSUE: NTLM enabled without upstream proxy")
        print("   Solutions:")
        print("   a) Disable NTLM authentication if you don't need it")
        print("   b) Configure an upstream proxy server in NTLM settings")
        print("   c) Set auth_method to 'NONE' for direct connections")
        print()
    
    print("2. 🔧 Quick Fix Options:")
    print("   Option A - Disable NTLM for testing:")
    print("   - Go to NTLM Authentication tab")
    print("   - Uncheck 'Enable NTLM Authentication'")
    print("   - Restart proxy")
    print()
    
    print("   Option B - Configure upstream proxy:")
    print("   - Go to NTLM Authentication tab")
    print("   - Set 'Proxy Server' to your company proxy")
    print("   - Set 'Port' (usually 8080, 3128, or 8888)")
    print("   - Restart proxy")
    print()
    
    print("   Option C - Use direct connection mode:")
    print("   - Set Authentication Method to 'NONE'")
    print("   - This bypasses NTLM and allows direct connections")


def create_test_config():
    """Create a test configuration that should work."""
    print("\n🔧 Creating Test Configuration")
    print("=" * 50)
    
    config_manager = ConfigManager()
    
    # Create a working configuration
    test_config = {
        'listen_address': '127.0.0.1',
        'port': 3128,
        'threads': 5,
        'enable_ntlm': False,  # Disable NTLM for testing
        'auth_method': 'NONE',  # No authentication
        'upstream_proxy': '',  # No upstream proxy
        'domain': '',
        'username': '',
        'client_auth': ['NONE'],
        'auto_detect_domain': True
    }
    
    print(f"Test configuration: {test_config}")
    
    # Save test configuration
    success = config_manager.save_proxy_config(test_config)
    if success:
        print("✅ Test configuration saved")
        print("   Please restart the proxy to apply changes")
    else:
        print("❌ Failed to save test configuration")
    
    return success


def main():
    """Run proxy diagnostics."""
    setup_logging()
    
    print("🔍 px UI Proxy Diagnostics")
    print("=" * 50)
    
    # Check configuration
    config_ok = check_proxy_config()
    
    # Check px state
    px_ok = check_px_state()
    
    # Test connection
    connection_ok = test_proxy_connection()
    
    # Provide suggestions
    suggest_fixes()
    
    # Offer to create test config
    if not config_ok:
        response = input("\nWould you like to create a test configuration? (y/n): ")
        if response.lower().startswith('y'):
            create_test_config()
    
    print("\n📋 Diagnostic Summary")
    print("=" * 50)
    print(f"Configuration: {'✅ OK' if config_ok else '❌ Issues found'}")
    print(f"px State: {'✅ OK' if px_ok else '❌ Issues found'}")
    print(f"Connection: {'✅ OK' if connection_ok else '❌ Failed'}")
    
    if not (config_ok and connection_ok):
        print("\n⚠️  Issues detected. Please follow the suggested fixes above.")
    else:
        print("\n✅ All checks passed!")


if __name__ == "__main__":
    main()