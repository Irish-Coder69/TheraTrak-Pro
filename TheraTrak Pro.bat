@echo off
cd /d "%~dp0"
python main.py
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Could not start TheraTrak Pro.
    echo Make sure Python 3.10+ is installed and on your PATH.
    echo.
    pause
)
