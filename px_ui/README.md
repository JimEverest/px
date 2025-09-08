# px UI Client - Graphical Proxy Management Tool

A comprehensive graphical user interface for the px proxy library, providing PAC configuration, request monitoring, and advanced proxy management capabilities.

## 🚀 Quick Start

### Standard Application Launch

The **recommended** ways to start the px UI client:

```bash
# Method 1: Run as Python module (recommended)
python -m px_ui.main

# Method 2: Direct execution
python px_ui/main.py

# Method 3: Using convenience scripts
python start_px_ui.py          # Cross-platform Python script
./start_px_ui.sh              # Linux/macOS shell script  
start_px_ui.bat               # Windows batch file
```

### Development and Testing

For development and testing purposes:

```bash
# Integrated UI example (development/testing)
python examples/integrated_ui_example.py

# Error handling testing
python test_error_handling_integration.py

# PAC configuration testing
python test_pac_auto_save.py
```

## 📋 System Requirements

- **Python**: 3.8 or higher
- **Operating System**: Windows, macOS, or Linux
- **Dependencies**: All required packages are listed in the project requirements
- **Network**: Internet connection for proxy functionality testing

## 🏗️ Project Structure

```
px_ui/
├── main.py                     # 🎯 Main application entry point
├── README.md                   # This documentation
├── __init__.py                 # Package initialization
├── models/                     # Core data models
│   ├── request_data.py         # HTTP request data model
│   ├── response_data.py        # HTTP response data model
│   ├── pac_configuration.py    # PAC file configuration model
│   └── proxy_status.py         # Proxy service status model
├── ui/                         # User interface components
│   ├── main_window.py          # Main application window
│   ├── pac_config_panel.py     # PAC configuration interface
│   ├── monitoring_view.py      # Request monitoring interface
│   ├── no_proxy_panel.py       # No-proxy settings interface
│   ├── response_details_dialog.py # Response details viewer
│   └── error_*.py              # Error handling UI components
├── proxy/                      # Proxy extensions and monitoring
│   ├── proxy_controller.py     # Proxy service controller
│   ├── enhanced_handler.py     # Enhanced HTTP request handler
│   └── configuration_bridge.py # Configuration integration
├── communication/              # Event-driven communication
│   ├── event_system.py         # Core event system
│   ├── event_processor.py      # Event processing logic
│   └── event_queue.py          # Event queue management
├── config/                     # Configuration management
│   ├── config_manager.py       # Configuration persistence
│   └── ui_settings.py          # UI settings model
├── error_handling/             # Comprehensive error management
│   ├── error_manager.py        # Error detection and handling
│   ├── error_reporter.py       # Error reporting system
│   └── fallback_manager.py     # Fallback strategies
└── performance/                # Performance optimization
    ├── performance_monitor.py  # Resource monitoring
    ├── update_throttler.py     # UI update optimization
    └── resource_cleaner.py     # Memory management
```

## ✨ Key Features

### 🔧 Proxy Management
- **Start/Stop Control**: Easy proxy service management
- **Status Monitoring**: Real-time proxy status and statistics
- **Configuration Persistence**: Settings automatically saved

### 📝 PAC Configuration
- **Multiple Sources**: Inline editing, file loading, URL loading
- **Syntax Validation**: Real-time JavaScript syntax checking
- **Testing Tools**: Test PAC rules against specific URLs
- **Auto-Save**: Configuration automatically preserved

### 📊 Request Monitoring
- **Real-Time Display**: Live view of proxy requests and responses
- **Advanced Filtering**: Filter by URL, proxy type, status code
- **Response Details**: Detailed view of headers and content
- **Export Capabilities**: Save monitoring data for analysis

### 🚫 No-Proxy Settings
- **Bypass Configuration**: Configure direct connections
- **Pattern Support**: Wildcards, IP ranges, domain patterns
- **Visual Management**: Easy add/remove interface

### 🛡️ Error Handling
- **Comprehensive Detection**: Automatic error detection and reporting
- **Recovery Strategies**: Intelligent fallback mechanisms
- **User Guidance**: Clear error messages and recovery suggestions
- **Error Reporting**: Detailed error reports for troubleshooting

### ⚡ Performance Features
- **Resource Optimization**: Automatic memory and CPU management
- **Update Throttling**: Smooth UI performance under high load
- **Virtual Scrolling**: Efficient handling of large data sets
- **Background Processing**: Non-blocking operations

## 🎮 User Interface

The application features a modern tabbed interface with:

1. **Request Monitoring**: Real-time proxy request/response monitoring
2. **PAC Configuration**: Proxy Auto-Configuration management
3. **No Proxy Settings**: Direct connection bypass rules

### Menu System
- **File**: Load/Save PAC files, Export logs and reports
- **Proxy**: Start/Stop proxy, Clear monitoring data
- **View**: Refresh interface, Toggle auto-scroll
- **Help**: About information and documentation

### Keyboard Shortcuts
- `Ctrl+O`: Load PAC file
- `Ctrl+S`: Save PAC file
- `Ctrl+E`: Export logs
- `F5`: Start proxy
- `F6`: Stop proxy

## 📁 Configuration Files

Configuration is automatically saved to platform-appropriate locations:

- **Windows**: `%APPDATA%\px-ui-client\px_ui_config.json`
- **macOS**: `~/Library/Application Support/px-ui-client/px_ui_config.json`
- **Linux**: `~/.config/px-ui-client/px_ui_config.json`

### Configuration Contents
- PAC configuration (source type, content, file paths)
- UI preferences (window size, positions, themes)
- Proxy settings (port, address, mode)
- No-proxy rules and patterns

## 🧪 Testing and Development

### Manual Testing
Follow the comprehensive testing guide:
```bash
# See detailed testing instructions
cat 手动测试验证指南.md
```

### Automated Testing
```bash
# Run all tests
python -m pytest tests/

# Run specific test categories
python tests/test_pac_validation.py
python tests/test_error_handling_system.py
python tests/test_performance.py
```

### Development Examples
```bash
# Component-specific examples
python examples/pac_config_example.py
python examples/monitoring_example.py
python examples/no_proxy_example.py
```

## 🔧 Troubleshooting

### Common Issues

1. **Application won't start**:
   - Check Python version (3.8+ required)
   - Verify all dependencies are installed
   - Check log files in `~/.px-ui-client/logs/`

2. **Proxy fails to start**:
   - Ensure port 3128 is not in use
   - Check firewall settings
   - Verify network permissions

3. **PAC configuration errors**:
   - Use the built-in PAC validator
   - Check JavaScript syntax
   - Test with simple PAC rules first

4. **Performance issues**:
   - Enable update throttling in settings
   - Clear monitoring logs regularly
   - Check system resource usage

### Log Files
Application logs are saved to:
- **Main log**: `~/.px-ui-client/logs/px_ui.log`
- **Error log**: `~/.px-ui-client/logs/error.log`
- **Performance log**: `~/.px-ui-client/logs/performance.log`

## 🤝 Contributing

This project follows a modular architecture with clear separation of concerns:

- **Models**: Data structures and validation
- **UI**: User interface components
- **Proxy**: Proxy service integration
- **Communication**: Event-driven messaging
- **Config**: Settings and persistence
- **Error Handling**: Comprehensive error management
- **Performance**: Optimization and monitoring

## 📄 License

This project is part of the px proxy library ecosystem and follows the same licensing terms.

## 🆘 Support

For issues, questions, or contributions:

1. Check the testing guide: `手动测试验证指南.md`
2. Review log files for error details
3. Use the built-in error reporting system
4. Consult the comprehensive documentation in each module

---

**Start the application now**: `python -m px_ui.main`