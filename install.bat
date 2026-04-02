@echo off
setlocal enabledelayedexpansion
title Trade Copier — Installer
cd /d "%~dp0"

if "%1"=="--setup" goto :setup

echo.
echo =============================================
echo   Trade Copier - First-Time Setup
echo =============================================
echo.

set NEED_RELAUNCH=0

:: [1/3] Python
where python >nul 2>&1
if errorlevel 1 (
    echo [1/3] Python not found. Installing...
    winget install --id Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo ERROR: Could not install Python automatically.
        echo Please install Python 3.12+ from: https://python.org
        echo.
        pause
        exit /b 1
    )
    set NEED_RELAUNCH=1
) else (
    echo [1/3] Python OK
)

:: [2/3] Node.js
where npm >nul 2>&1
if errorlevel 1 (
    echo [2/3] Node.js not found. Installing...
    winget install --id OpenJS.NodeJS.LTS --silent --accept-package-agreements --accept-source-agreements
    if errorlevel 1 (
        echo.
        echo ERROR: Could not install Node.js automatically.
        echo Please install Node.js 18+ from: https://nodejs.org
        echo.
        pause
        exit /b 1
    )
    set NEED_RELAUNCH=1
) else (
    echo [2/3] Node.js OK
)

:: If winget installed something, relaunch in a fresh cmd with updated PATH
if "%NEED_RELAUNCH%"=="1" (
    echo.
    echo [3/3] Finalizing installation in new window...
    start /wait "" cmd /k ""%~f0" --setup"
    exit /b 0
)

goto :setup

:: ============================================================
:: STAGE 2: Install packages (runs in fresh process if needed)
:: ============================================================
:setup

echo.
echo [3/3] Installing packages...
echo.

:: Create Python virtual environment
echo   - Creating virtual environment...
python -m venv .venv
if errorlevel 1 (
    echo.
    echo ERROR: Failed to create virtual environment.
    pause & exit /b 1
)

:: Install Python dependencies from pyproject.toml
echo   - Installing Python dependencies...
.venv\Scripts\pip.exe install . -q
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install Python dependencies.
    pause & exit /b 1
)

:: Install frontend dependencies
echo   - Installing frontend dependencies...
if not exist "%~dp0web\frontend\node_modules" (
    pushd "%~dp0web\frontend"
    npm install --silent
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install frontend dependencies.
        popd
        pause & exit /b 1
    )
    popd
) else (
    echo   - Frontend dependencies already installed.
)

echo.
echo =============================================
echo   Setup complete!
echo   Run start.bat to launch the application.
echo =============================================
echo.
pause
exit /b 0
