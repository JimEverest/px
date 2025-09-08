@echo off
REM Windows batch file to start px UI client

echo 🚀 Starting px UI Client...
echo ==================================================

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Python is not installed or not in PATH
    echo 💡 Please install Python 3.8 or higher
    pause
    exit /b 1
)

REM Launch the application
echo ✅ Python found, launching px UI client...
echo.

python -m px_ui.main

if errorlevel 1 (
    echo.
    echo ❌ Application exited with error
    echo 💡 Check the log files for more details
    pause
) else (
    echo.
    echo 👋 px UI Client closed successfully
)

pause