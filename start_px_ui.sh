#!/bin/bash
# Shell script to start px UI client on Linux/macOS

echo "🚀 Starting px UI Client..."
echo "=================================================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    if ! command -v python &> /dev/null; then
        echo "❌ Error: Python is not installed or not in PATH"
        echo "💡 Please install Python 3.8 or higher"
        exit 1
    else
        PYTHON_CMD="python"
    fi
else
    PYTHON_CMD="python3"
fi

# Check Python version
PYTHON_VERSION=$($PYTHON_CMD -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Error: Python 3.8 or higher is required"
    echo "   Current version: $PYTHON_VERSION"
    exit 1
fi

# Launch the application
echo "✅ Python $PYTHON_VERSION found, launching px UI client..."
echo ""

$PYTHON_CMD -m px_ui.main

EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Application exited with error (code: $EXIT_CODE)"
    echo "💡 Check the log files for more details"
else
    echo ""
    echo "👋 px UI Client closed successfully"
fi

exit $EXIT_CODE