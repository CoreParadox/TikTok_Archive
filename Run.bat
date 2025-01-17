@echo off
setlocal enabledelayedexpansion

:: Define paths
set PYTHON_PORTABLE=python_portable
set VENV_DIR=%PYTHON_PORTABLE%\venv

:: Activate virtual environment
call %VENV_DIR%\Scripts\activate
if %errorlevel% neq 0 (
    echo Failed to activate virtual environment. Please run Setup.bat first.
    pause
    exit /b 1
)

:: Run the app
python main.py

:: Cleanup
deactivate
