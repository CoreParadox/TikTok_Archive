@echo off
setlocal enabledelayedexpansion

:: Define paths
set "ROOT_DIR=%~dp0"
set "PYTHON_PORTABLE=%ROOT_DIR%python_portable"
set "VENV_DIR=%PYTHON_PORTABLE%\venv"
set "TOOLS_DIR=%ROOT_DIR%tools"

:: Add tools directory to PATH
set "PATH=%TOOLS_DIR%;%PATH%"

:: Activate virtual environment
call "%VENV_DIR%\Scripts\activate.bat"
if %errorlevel% neq 0 (
    echo Failed to activate virtual environment. Please run Setup.bat first.
    pause
    exit /b 1
)

:: Run the app
python "%ROOT_DIR%\main.py"

:: Cleanup
deactivate
endlocal
