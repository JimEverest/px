#!/usr/bin/env python3
"""
Main entry point for the px UI client application.

This is the standard way to launch the px UI client with all integrated components
including PAC configuration, request monitoring, and proxy management.
"""

import sys
import os
import logging
import signal
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def setup_logging(log_level: str = "INFO"):
    """Set up application logging."""
    log_dir = Path.home() / ".px-ui-client" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_dir / 'px_ui.log')
        ]
    )


def signal_handler(signum, frame):
    """Handle interrupt signals gracefully."""
    logger = logging.getLogger(__name__)
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    sys.exit(0)


def main():
    """Main application entry point."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("Starting px UI client application...")
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    
    main_window = None
    proxy_controller = None
    
    try:
        # Import required modules
        from px_ui.ui.main_window import MainWindow
        from px_ui.proxy.proxy_controller import ProxyController
        from px_ui.config.config_manager import ConfigManager
        
        logger.info("Creating main window with integrated components...")
        
        # Create main window first to get event system
        main_window = MainWindow()
        logger.info("Main window created successfully")
        logger.info(f"- Event system: {main_window.get_event_system() is not None}")
        logger.info(f"- PAC config panel: {main_window.pac_config_panel is not None}")
        logger.info(f"- Monitoring view: {main_window.monitoring_view is not None}")
        logger.info(f"- No proxy panel: {main_window.no_proxy_panel is not None}")
        
        # Create proxy controller with shared event system
        try:
            proxy_controller = ProxyController(main_window.get_event_system())
            logger.info("Proxy controller created successfully")
        except Exception as e:
            logger.warning(f"Failed to create proxy controller: {e}")
            logger.info("Using fallback proxy controller...")
            
            # Create a simple fallback proxy controller
            class FallbackProxyController:
                def __init__(self):
                    self.logger = logging.getLogger("FallbackProxyController")
                    self._running = False
                
                def start_proxy(self, config=None):
                    self.logger.info("Fallback: Simulating proxy start...")
                    self._running = True
                    return True
                
                def stop_proxy(self):
                    self.logger.info("Fallback: Simulating proxy stop...")
                    self._running = False
                    return True
                
                def is_running(self):
                    return self._running
                
                def shutdown(self):
                    self.logger.info("Fallback: Shutting down...")
            
            proxy_controller = FallbackProxyController()
        
        # Set up proxy control callbacks with proxy controller reference
        main_window.set_proxy_callbacks(
            proxy_controller.start_proxy, 
            proxy_controller.stop_proxy, 
            proxy_controller
        )
        
        logger.info("Proxy controller integrated with main window")
        
        # Display startup information
        logger.info("Application initialized successfully!")
        logger.info("Available features:")
        logger.info("  - PAC Configuration: Configure proxy auto-configuration")
        logger.info("  - Request Monitoring: View real-time proxy requests")
        logger.info("  - No Proxy Settings: Configure proxy bypass rules")
        logger.info("  - Error Handling: Comprehensive error reporting and recovery")
        logger.info("  - Performance Monitoring: Resource usage and optimization")
        
        # Start the main application loop
        logger.info("Starting main application loop...")
        main_window.run()
        
        return 0
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
        return 0
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        return 1
    
    finally:
        # Cleanup
        logger.info("Application shutdown initiated")
        
        if proxy_controller:
            try:
                if hasattr(proxy_controller, 'shutdown'):
                    proxy_controller.shutdown()
                logger.info("Proxy controller shutdown complete")
            except Exception as e:
                logger.error(f"Error during proxy controller shutdown: {e}")
        
        if main_window:
            try:
                if hasattr(main_window, 'cleanup'):
                    main_window.cleanup()
                logger.info("Main window cleanup complete")
            except Exception as e:
                logger.error(f"Error during main window cleanup: {e}")
        
        logger.info("px UI client shutdown complete")


if __name__ == "__main__":
    sys.exit(main())