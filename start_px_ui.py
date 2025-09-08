#!/usr/bin/env python3
"""
Convenient startup script for px UI client.

This script provides a simple way to launch the px UI client application
with proper error handling and user-friendly messages.
"""

import sys
import os
from pathlib import Path

def main():
    """Launch the px UI client application."""
    print("🚀 Starting px UI Client...")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Error: Python 3.8 or higher is required")
        print(f"   Current version: {sys.version}")
        return 1
    
    # Add project root to path
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    
    try:
        # Import and run the main application
        from px_ui.main import main as px_main
        print("✅ px UI Client modules loaded successfully")
        print("🎯 Launching application...")
        print()
        
        return px_main()
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Make sure all dependencies are installed")
        print("   Try: pip install -r requirements.txt")
        return 1
    except KeyboardInterrupt:
        print("\n👋 Application interrupted by user")
        return 0
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print("💡 Check the log files for more details")
        return 1

if __name__ == "__main__":
    sys.exit(main())