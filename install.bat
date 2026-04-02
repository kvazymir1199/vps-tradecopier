@echo off
setlocal enabledelayedexpansion
title Trade Copier — Installer
cd /d "%~dp0"

:: ============================================================
:: STAGE 2: called from Stage 1 in a fresh process with updated PATH
:: ============================================================
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

:: If winget installed something, relaunch in a fresh cmd to get updated PATH
if "%NEED_RELAUNCH%"=="1" (
    echo.
    echo [3/3] Finalizing installation...
    start /wait "" cmd /c ""%~f0" --setup & pause"
    goto :done
)

:: PATH already current, run setup directly
goto :setup

:: ============================================================
:: STAGE 2: Install Python/Node packages (fresh PATH)
:: ============================================================
:setup

echo.
echo [3/3] Installing packages...
echo.

echo   - Installing uv package manager...
python -m pip install uv -q

echo   - Installing Python dependencies...
python -m uv sync

echo   - Installing frontend dependencies...
if not exist "%~dp0web\frontend\node_modules" (
    pushd "%~dp0web\frontend"
    npm install --silent
    popd
) else (
    echo   - Frontend dependencies already installed.
)

:done
echo.
echo =============================================
echo   Setup complete!
echo   Run start.bat to launch the application.
echo =============================================
echo.
pause
exit /b 0
