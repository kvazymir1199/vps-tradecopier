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

:: [1/3] Python — check for REAL Python 3 (not Microsoft Store stub)
python --version 2>&1 | findstr /r "Python 3\." >nul 2>&1
if errorlevel 1 (
    echo [1/3] Python not found. Installing Python 3.12...
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
:: STAGE 2: Install packages
:: ============================================================
:setup

echo.
echo [3/3] Installing packages...
echo.

:: Show Python version for confirmation
for /f "tokens=*" %%V in ('python --version 2^>^&1') do echo   - Using %%V

:: Remove previous virtual environment if it exists
if exist "%~dp0.venv" (
    echo   - Removing previous virtual environment...
    rmdir /s /q "%~dp0.venv"
)

:: Create virtual environment — try py launcher first, then python
echo   - Creating virtual environment...
py -3 -m venv "%~dp0.venv" >nul 2>&1
if errorlevel 1 (
    python -m venv "%~dp0.venv"
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to create virtual environment.
        pause & exit /b 1
    )
)

:: Install Python dependencies from pyproject.toml
echo   - Installing Python dependencies...
"%~dp0.venv\Scripts\pip.exe" install . -q
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
