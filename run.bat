@echo off
title Image Compressor
cd /d "%~dp0"

:: Check for Python Environment
python --version >nul 2>&1
if %errorlevel% neq 0 (
    py --version >nul 2>&1
    if %errorlevel% neq 0 (
        echo Python environment not detected. Preparing auto-download and install...
        echo Downloading Python 3.11 installer, please wait...
        curl -o python-installer.exe https://www.python.org/ftp/python/3.11.8/python-3.11.8-amd64.exe
        if exist python-installer.exe (
            echo Download complete! Installing Python silently...
            echo Please click "Yes" if a UAC privilege prompt appears!
            start /wait python-installer.exe InstallAllUsers=1 PrependPath=1 Include_test=0 target_dir="C:\Python311"
            echo Installation complete, cleaning up...
            del python-installer.exe
            
            set PATH=%PATH%;C:\Python311;C:\Python311\Scripts
            python --version >nul 2>&1
            if %errorlevel% neq 0 (
                 echo Python may have been installed successfully, but environment variables have not taken effect yet. Please re-run this script or restart your computer.
                 pause
                 exit /b 1
            )
        ) else (
            echo Python download failed. Please manually download and install from https://www.python.org/, remembering to check "Add Python to PATH"!
            pause
            exit /b 1
        )
    )
)

echo Checking and installing dependencies...
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    py -m pip install -r requirements.txt
)

echo Starting Image Compressor...
python main.py
if %errorlevel% neq 0 (
    py main.py
)
pause
