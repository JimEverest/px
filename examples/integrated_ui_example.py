#!/usr/bin/env python3
"""
Example demonstrating the integrated UI with all components in a tabbed interface.

This example shows how all UI components (PAC configuration, monitoring view, 
and no proxy settings) are integrated into the main window with a tabbed interface.
"""

import sys
import os
import logging
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def setup_logging():
    """Set up logging for the example."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('integrated_ui_example.log')
        ]
    )

def main():
    """Run the integrated UI example."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        from px_ui.ui.main_window import MainWindow
        
        logger.info("Starting integrated UI example...")
        
        # Create main window first to get event system
        main_window = MainWindow()
        logger.info("Main window created with integrated components:")
        logger.info(f"- Event system: {main_window.get_event_system() is not None}")
        logger.info(f"- PAC config panel: {main_window.pac_config_panel is not None}")
        logger.info(f"- Monitoring view: {main_window.monitoring_view is not None}")
        logger.info(f"- No proxy panel: {main_window.no_proxy_panel is not None}")
        
        # Try to import and create proxy controller with shared event system
        try:
            from px_ui.proxy.proxy_controller import ProxyController
            proxy_controller = ProxyController(main_window.get_event_system())
            logger.info("Proxy controller created successfully")
        except Exception as e:
            logger.warning(f"Failed to create proxy controller: {e}")
            logger.info("Using fallback proxy controller...")
            
            # Create a simple fallback proxy controller
            class FallbackProxyController:
                def __init__(self):
                    self.logger = logging.getLogger("FallbackProxyController")
                
                def start_proxy(self, config=None):
                    self.logger.info("Fallback: Simulating proxy start...")
                    # In a real implementation, this would start the actual proxy
                    return True
                
                def stop_proxy(self):
                    self.logger.info("Fallback: Simulating proxy stop...")
                    # In a real implementation, this would stop the actual proxy
                    return True
            
            proxy_controller = FallbackProxyController()
        
        # Set up proxy control callbacks with proxy controller reference
        main_window.set_proxy_callbacks(proxy_controller.start_proxy, proxy_controller.stop_proxy, proxy_controller)
        
        logger.info("Proxy controller integrated with main window")
        
        # Get monitoring stats
        stats = main_window.get_monitoring_stats()
        logger.info(f"Initial monitoring stats: {stats}")
        
        # Demonstrate tab switching
        logger.info("Demonstrating tab switching...")
        main_window.switch_to_tab("PAC Configuration")
        logger.info("Switched to PAC Configuration tab")
        
        main_window.switch_to_tab("No Proxy Settings")
        logger.info("Switched to No Proxy Settings tab")
        
        main_window.switch_to_tab("Request Monitoring")
        logger.info("Switched to Request Monitoring tab")
        
        # Show configuration info
        pac_config = main_window.get_pac_configuration()
        if pac_config:
            logger.info(f"PAC configuration: {pac_config.get_source_display_name()}")
        else:
            logger.info("No PAC configuration set")
        
        no_proxy_config = main_window.get_no_proxy_configuration()
        if no_proxy_config:
            logger.info(f"No proxy configuration: {no_proxy_config.get_summary()}")
        else:
            logger.info("No proxy configuration not set")
        
        # Set window title to indicate this is an example
        main_window.root.title("px UI Client - Integrated Components Example")
        
        # Add example instructions
        main_window._update_status("Example running - Try switching between tabs to see all components")
        
        logger.info("Starting main UI loop...")
        logger.info("Use the tabs to explore:")
        logger.info("  - Request Monitoring: View real-time proxy requests")
        logger.info("  - PAC Configuration: Configure proxy auto-configuration")
        logger.info("  - No Proxy Settings: Configure proxy bypass rules")
        logger.info("Close the window to exit the example.")
        
        # Run the main loop
        main_window.run()
        
        logger.info("Integrated UI example completed")
        
    except KeyboardInterrupt:
        logger.info("Example interrupted by user")
    except Exception as e:
        logger.error(f"Error in integrated UI example: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())