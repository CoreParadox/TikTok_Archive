@echo off
setlocal enabledelayedexpansion

:: Define paths
set "ROOT_DIR=%~dp0"
set "PYTHON_PORTABLE=%ROOT_DIR%python_portable"
set "VENV_DIR=%PYTHON_PORTABLE%\venv"
set "TOOLS_DIR=%ROOT_DIR%tools"
set "TEMP_DIR=%ROOT_DIR%temp"
set "PYTHON_URL=https://www.python.org/ftp/python/3.11.7/amd64"

:: Define Python components
set MSI_FILES=core dev doc exe launcher lib path pip tcltk test tools

echo Root directory: %ROOT_DIR%
echo Python portable directory: %PYTHON_PORTABLE%
echo Virtual environment directory: %VENV_DIR%

:: Step 1: Check for Python installation
echo Checking for system Python...
python --version >nul 2>&1
if %errorlevel% equ 1 (
    echo Found system Python installation
    set "PYTHON_EXE=python"
) else (
    echo System Python not found. Using portable Python installation...
    
    :: Check if we have a working portable Python
    echo Checking for existing portable Python...
    call :CheckPythonInstall
    if !errorlevel! equ 0 (
        echo Found existing portable Python installation
    ) else (
        echo Installing portable Python...
        
        :: Clean up any partial installation
        if exist "%PYTHON_PORTABLE%" (
            echo Cleaning up previous installation...
            rd /s /q "%PYTHON_PORTABLE%"
        )
        if exist "%TEMP_DIR%" (
            echo Cleaning up temp directory...
            rd /s /q "%TEMP_DIR%"
        )
        if exist "%ROOT_DIR%\Lib" (
            echo Cleaning up root Lib directory...
            rd /s /q "%ROOT_DIR%\Lib"
        )
        
        echo Creating directories...
        mkdir "%PYTHON_PORTABLE%"
        mkdir "%TEMP_DIR%"
        
        :: Download MSI files
        echo Downloading Python components...
        for %%i in (%MSI_FILES%) do (
            echo Downloading %%i.msi...
            powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%/%%i.msi' -OutFile '%TEMP_DIR%\%%i.msi'"
        )
        
        echo Installing Python components...
        for %%i in (%MSI_FILES%) do (
            echo Installing %%i.msi...
            msiexec /a "%TEMP_DIR%\%%i.msi" /qn TARGETDIR="%PYTHON_PORTABLE%"
        )
        
        :: Clean up MSI files
        echo Cleaning up MSI files...
        rd /s /q "%TEMP_DIR%"
        
        :: Create pyvenv.cfg
        echo Creating pyvenv.cfg...
        echo home = %PYTHON_PORTABLE% > "%PYTHON_PORTABLE%\pyvenv.cfg"
        echo include-system-site-packages = false >> "%PYTHON_PORTABLE%\pyvenv.cfg"
        echo version = 3.11.7 >> "%PYTHON_PORTABLE%\pyvenv.cfg"
        
        :: Create Scripts directory if it doesn't exist
        if not exist "%PYTHON_PORTABLE%\Scripts" mkdir "%PYTHON_PORTABLE%\Scripts"
        
        :: Set PYTHONPATH to ensure pip installs to correct location
        set "PYTHONPATH=%PYTHON_PORTABLE%\Lib\site-packages"
        
        :: Install pip manually
        echo Installing pip...
        mkdir "%TEMP_DIR%"
        powershell -Command "Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile '%TEMP_DIR%\get-pip.py'"
        "%PYTHON_PORTABLE%\python.exe" "%TEMP_DIR%\get-pip.py" --no-cache-dir --target="%PYTHON_PORTABLE%\Lib\site-packages"
        rd /s /q "%TEMP_DIR%"
        
        :: Test Python installation
        echo Testing Python installation...
        "%PYTHON_PORTABLE%\python.exe" -c "import tkinter" >nul 2>&1
        if !errorlevel! neq 0 (
            echo Error: Failed to import tkinter
            pause
            exit /b 1
        )
        
        :: Test pip installation
        echo Testing pip installation...
        "%PYTHON_PORTABLE%\python.exe" -m pip --version >nul 2>&1
        if !errorlevel! neq 0 (
            echo Error: Failed to install pip
            pause
            exit /b 1
        )
    )
    
    echo Setting Python executable to: %PYTHON_PORTABLE%\python.exe
    set "PYTHON_EXE=%PYTHON_PORTABLE%\python.exe"
    
    :: Add Scripts directory to PATH for pip
    echo Adding Scripts to PATH...
    set "PATH=%PYTHON_PORTABLE%\Scripts;%PATH%"
)

:: Step 2: Check for ffmpeg in tools directory
echo Checking for FFmpeg...
if not exist "%TOOLS_DIR%\ffmpeg.exe" (
    echo FFmpeg not found. Downloading and installing to tools directory...
    
    :: Create tools directory if it doesn't exist
    if not exist "%TOOLS_DIR%" mkdir "%TOOLS_DIR%"
    
    :: Download ffmpeg
    echo Downloading FFmpeg...
    powershell -Command "$ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip' -OutFile '%TOOLS_DIR%\ffmpeg.zip'"
    
    :: Extract ffmpeg
    echo Extracting FFmpeg...
    powershell -Command "$ProgressPreference = 'SilentlyContinue'; Expand-Archive '%TOOLS_DIR%\ffmpeg.zip' -DestinationPath '%TOOLS_DIR%' -Force"
    
    :: Move ffmpeg.exe to tools directory and clean up
    for /d %%i in ("%TOOLS_DIR%\ffmpeg-*") do (
        move "%%i\bin\ffmpeg.exe" "%TOOLS_DIR%"
        rd /s /q "%%i"
    )
    del "%TOOLS_DIR%\ffmpeg.zip"
)

:: Step 3: Install virtualenv
echo Installing virtualenv...
"%PYTHON_EXE%" -m pip install virtualenv --no-cache-dir --no-warn-script-location
if !errorlevel! neq 0 (
    echo Error: Failed to install virtualenv
    pause
    exit /b 1
)

:: Step 4: Create virtual environment
if not exist "%VENV_DIR%" (
    echo Creating virtual environment...
    "%PYTHON_EXE%" -m virtualenv "%VENV_DIR%"
    if !errorlevel! neq 0 (
        echo Failed to create virtual environment. Exiting.
        exit /b 1
    )
)

:: Step 5: Activate virtual environment and install dependencies
echo Activating virtual environment...
call "%VENV_DIR%\Scripts\activate.bat"
if !errorlevel! neq 0 (
    echo Failed to activate virtual environment. Exiting.
    exit /b 1
)

echo Installing dependencies...
python -m pip install --upgrade pip --no-cache-dir
if !errorlevel! neq 0 (
    echo Error: Failed to upgrade pip
    pause
    exit /b 1
)

echo Installing requirements from requirements.txt...
python -m pip install -r "%ROOT_DIR%requirements.txt" --no-cache-dir
if !errorlevel! neq 0 (
    echo Error: Failed to install requirements
    pause
    exit /b 1
)

echo Setup complete! You can now run the app using Run.bat
pause

goto :eof

:: Function to check Python installation
:CheckPythonInstall
echo Checking python.exe...
if not exist "%PYTHON_PORTABLE%\python.exe" exit /b 1
echo Testing Python...
"%PYTHON_PORTABLE%\python.exe" --version >nul 2>&1
if !errorlevel! neq 0 exit /b 1
echo Testing tkinter...
"%PYTHON_PORTABLE%\python.exe" -c "import tkinter" >nul 2>&1
if !errorlevel! neq 0 exit /b 1
exit /b 0
