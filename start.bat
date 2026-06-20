@echo off
chcp 65001 >nul
title AI-RE Toolkit Launcher

echo.
echo =========================================
echo      AI-RE Toolkit Launcher
echo =========================================
echo.

cd /d "%~dp0"

REM Check Python
echo [1/4] Checking Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.8+
    pause
    exit /b 1
)
echo [OK] Python is ready

REM Check dependencies
echo.
echo [2/4] Checking dependencies...
pip show PySide6 >nul 2>&1
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install dependencies
        pause
        exit /b 1
    )
)
echo [OK] Dependencies are ready

REM Check tools directory
echo.
echo [3/4] Checking tools directory...
if not exist "tools\windows" mkdir "tools\windows"
if not exist "tools\windows\upx" (
    echo [INFO] UPX not found, recommended to download
)
if not exist "tools\windows\die" (
    echo [INFO] Detect It Easy not found, recommended to download
)
echo [OK] Tools directory ready

REM Check Ollama (optional)
echo.
echo [4/4] Checking Ollama service...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [INFO] Ollama service not running
    echo        To use local AI, run: ollama serve
    echo        Download: https://ollama.com/download
) else (
    echo [OK] Ollama is running
)

echo.
echo =========================================
echo      Environment check complete
echo      Starting AI-RE Toolkit...
echo =========================================
echo.

REM Launch main program
python src\main.py

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start program
    pause
)
