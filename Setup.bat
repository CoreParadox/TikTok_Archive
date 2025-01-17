@echo off
setlocal enabledelayedexpansion

:: Define paths
set PYTHON_PORTABLE=python_portable
set VENV_DIR=%PYTHON_PORTABLE%\venv
set TOOLS_DIR=tools

:: Step 1: Check for Python installation
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo Python not found. Using portable Python installation...
    if not exist %PYTHON_PORTABLE% (
        echo Downloading portable Python...
        powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.0/python-3.11.0-embed-amd64.zip' -OutFile 'python.zip'"
        powershell -Command "Expand-Archive python.zip -DestinationPath %PYTHON_PORTABLE%"
        del python.zip
    )
    set PYTHON_EXE=%PYTHON_PORTABLE%\python.exe
) else (
    set PYTHON_EXE=python
)

:: Step 2: Check for ffmpeg in tools directory
if not exist "%TOOLS_DIR%\ffmpeg.exe" (
    echo FFmpeg not found. Downloading and installing to tools directory...
    
    :: Create tools directory if it doesn't exist
    if not exist %TOOLS_DIR% mkdir %TOOLS_DIR%
    cd %TOOLS_DIR%
    
    :: Download ffmpeg
    echo Downloading FFmpeg...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile 'ffmpeg.zip'"
    
    :: Extract ffmpeg
    echo Extracting FFmpeg...
    powershell -Command "Expand-Archive -Path 'ffmpeg.zip' -DestinationPath '.' -Force"
    
    :: Move ffmpeg.exe to tools directory and clean up
    for /d %%i in (ffmpeg-*) do (
        move "%%i\bin\ffmpeg.exe" .
        rd /s /q "%%i"
    )
    del ffmpeg.zip
    
    cd ..
)

:: Step 3: Create virtual environment
if not exist %VENV_DIR% (
    echo Creating virtual environment...
    %PYTHON_EXE% -m venv %VENV_DIR%
    if %errorlevel% neq 0 (
        echo Failed to create virtual environment. Exiting.
        exit /b 1
    )
)

:: Step 4: Activate virtual environment and install dependencies
call %VENV_DIR%\Scripts\activate
if %errorlevel% neq 0 (
    echo Failed to activate virtual environment. Exiting.
    exit /b 1
)

echo Installing dependencies...
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    echo Failed to upgrade pip. Exiting.
    exit /b 1
)

pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Failed to install dependencies. Exiting.
    exit /b 1
)

echo Setup complete! You can now run the app by double-clicking Run.bat
pause
