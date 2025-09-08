# Response Details Dialog and Error Highlighting

This document describes the implementation of Task 7: Response Details Dialog and Error Highlighting functionality for the px UI client.

## Overview

The implementation provides comprehensive response inspection capabilities and visual error highlighting in the monitoring view. This includes:

1. **ResponseDetailsDialog** - A detailed dialog for viewing complete request/response information
2. **Error Highlighting** - Color-coded status indicators in the monitoring view
3. **Response Body Handling** - Truncation and formatting for large response bodies
4. **Export Functionality** - Export response details to files

## Components

### ResponseDetailsDialog

Located in `px_ui/ui/response_details_dialog.py`

#### Features

- **Tabbed Interface**: Overview, Request, Response Headers, and Response Body tabs
- **Content Formatting**: JSON, HTML, XML formatting options for response bodies
- **Export Functionality**: Export to JSON or text files
- **Full Content Viewing**: Separate dialog for viewing complete response bodies
- **URL Copying**: Copy request URL to clipboard
- **Error Information**: Display error messages and details

#### Key Methods

- `show()`: Display the dialog
- `_populate_content()`: Populate all tabs with data
- `_view_full_content()`: Show full response body in separate window
- `_export_details()`: Export response data to file
- `_format_bytes()`: Format byte counts for display

### Error Highlighting

Integrated into `px_ui/ui/monitoring_view.py`

#### Color Scheme

- **Green** (`success`): 2xx status codes - successful responses
- **Orange** (`client_error`): 4xx status codes - client errors
- **Red** (`server_error`): 5xx status codes - server errors
- **Red** (`error`): Network errors and other failures
- **Default** (`normal`): Pending requests and other statuses

#### Implementation

- **Tag Configuration**: Tkinter Treeview tags for different status types
- **Status Detection**: Methods to categorize response types
- **Visual Feedback**: Immediate color coding in the monitoring table

### Enhanced RequestEntry

Extended with additional error detection methods:

- `is_error()`: General error detection
- `is_client_error()`: 4xx status code detection
- `is_server_error()`: 5xx status code detection
- `is_success()`: 2xx status code detection

## Usage

### Viewing Response Details

1. **Double-click** any entry in the monitoring view
2. **Right-click** and select "View Details" from context menu
3. Navigate through tabs to view different aspects of the request/response

### Understanding Error Highlighting

- **Green entries**: Successful requests (200-299 status codes)
- **Orange entries**: Client errors (400-499 status codes) - check request format
- **Red entries**: Server errors (500+ status codes) or network failures
- **Default entries**: Pending requests or informational responses

### Exporting Data

1. Open response details dialog
2. Click "Export Details" button
3. Choose file format (JSON or text)
4. Select save location

## Technical Details

### Response Body Handling

- **Truncation**: Body preview limited to first 500 characters by default
- **Full Content**: "View Full Content" button for complete response bodies
- **Formatting**: Automatic JSON/XML formatting when possible
- **Large Response Handling**: Memory-efficient handling of large responses

### Error Detection Logic

```python
def is_error(self) -> bool:
    """Check if this entry represents an error."""
    return (self.error_message is not None or 
            (self.status_code is not None and self.status_code >= 400))
```

### Status Tag Assignment

```python
def _get_status_tag(self, entry: RequestEntry) -> str:
    """Get the appropriate tag for status-based highlighting."""
    if entry.error_message:
        return "error"
    elif entry.status_code is None:
        return "normal"
    elif 200 <= entry.status_code < 300:
        return "success"
    elif 400 <= entry.status_code < 500:
        return "client_error"
    elif entry.status_code >= 500:
        return "server_error"
    else:
        return "normal"
```

## Testing

### Test Coverage

- **Unit Tests**: `tests/test_response_details_dialog.py`
- **Integration Tests**: `tests/test_error_highlighting_integration.py`
- **Example Application**: `examples/response_details_example.py`

### Running Tests

```bash
# Run all response details tests
python -m pytest tests/test_response_details_dialog.py -v

# Run error highlighting integration tests
python -m pytest tests/test_error_highlighting_integration.py -v

# Run example application
python examples/response_details_example.py
```

### Test Scenarios

- Dialog creation and display
- Error highlighting for different status codes
- Response body formatting (JSON, XML, HTML)
- Export functionality
- URL copying
- Full content viewing
- Comprehensive error detection

## Requirements Satisfied

This implementation satisfies the following requirements from the specification:

### Requirement 3.1
✅ **WHEN a response is received THEN the system SHALL capture and display the HTTP status code**
- Status codes are captured and displayed in both monitoring view and details dialog

### Requirement 3.2
✅ **WHEN response status is 4xx or 5xx THEN the system SHALL highlight the entry in red color**
- 4xx errors highlighted in orange, 5xx errors highlighted in red

### Requirement 3.3
✅ **WHEN user clicks on a request entry THEN the system SHALL show detailed response headers and body preview**
- Double-click or context menu opens detailed response dialog

### Requirement 3.4
✅ **WHEN response contains authentication errors THEN the system SHALL display the specific error message**
- Error messages displayed in both monitoring view and details dialog

### Requirement 3.5
✅ **WHEN response body is large THEN the system SHALL truncate and show first 500 characters with option to view full content**
- Body preview truncated with "View Full Content" option for complete viewing

### Requirement 3.6
✅ **Response body truncation and full content viewing capabilities**
- Implemented with separate full content dialog and formatting options

## Integration Points

### With Monitoring View
- Seamless integration with existing monitoring table
- Context menu and double-click handlers
- Real-time error highlighting

### With Event System
- Uses existing RequestEntry objects
- Compatible with current event processing
- No changes required to event communication

### With Export System
- JSON and text export formats
- File dialog integration
- Error handling for export operations

## Future Enhancements

Potential improvements for future versions:

1. **Advanced Filtering**: Filter by error types in monitoring view
2. **Response Comparison**: Compare responses between requests
3. **Performance Metrics**: Additional timing and performance data
4. **Custom Formatting**: User-defined response body formatters
5. **Search Functionality**: Search within response content
6. **Response Caching**: Cache responses for offline viewing

## Dependencies

- **tkinter**: GUI framework (built-in with Python)
- **json**: JSON formatting (built-in)
- **xml.dom.minidom**: XML formatting (built-in)
- **html**: HTML unescaping (built-in)

No additional external dependencies required.