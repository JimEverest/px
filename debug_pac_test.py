#!/usr/bin/env python3
"""
Debug PAC testing to see what's going wrong.
"""

import sys
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from px_ui.models.pac_configuration import PACConfiguration

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

def debug_pac_test():
    """Debug PAC testing."""
    print("=== Debug PAC Testing ===")
    
    # Read the test.pac file
    pac_file = project_root / "test.pac"
    with open(pac_file, 'r', encoding='utf-8') as f:
        pac_content = f.read()
    
    print(f"PAC content length: {len(pac_content)}")
    
    # Create PAC configuration
    pac_config = PACConfiguration(
        source_type="file",
        source_path=str(pac_file),
        content=pac_content,
        encoding="utf-8"
    )
    
    # Validate PAC
    is_valid = pac_config.validate_pac_syntax()
    print(f"PAC validation: {is_valid}")
    if not is_valid:
        print(f"Validation errors: {pac_config.validation_errors}")
        return
    
    # Test a single URL with debugging
    test_url = "http://www.googleapis.com"
    test_host = "www.googleapis.com"
    
    print(f"\nTesting: {test_url} -> {test_host}")
    
    try:
        result = pac_config.test_url(test_url, test_host)
        print(f"Result: {result}")
        print(f"Result type: {type(result)}")
        
        if result is None:
            print("Result is None - checking why...")
            
            # Try direct JavaScript evaluation
            try:
                js_result = pac_config._evaluate_pac_with_javascript(test_url, test_host)
                print(f"Direct JS result: {js_result}")
            except Exception as e:
                print(f"Direct JS error: {e}")
                import traceback
                traceback.print_exc()
            
            # Try fallback evaluation
            try:
                fallback_result = pac_config._fallback_pac_evaluation(test_url, test_host)
                print(f"Fallback result: {fallback_result}")
            except Exception as e:
                print(f"Fallback error: {e}")
                import traceback
                traceback.print_exc()
        
    except Exception as e:
        print(f"Test error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_pac_test()