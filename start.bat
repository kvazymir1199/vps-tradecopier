@echo off
setlocal
title Trade Copier — Launcher
cd /d "%~dp0"

:: ============================================================
:: Check for Administrator privileges
:: ============================================================
net session >nul 2>&1
if errorlevel 1 (
    echo.
    echo =============================================
    echo   Requesting Administrator privileges...
    echo =============================================
    echo.
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b 0
)

set "TOOLS_DIR=%~dp0tools"
set "PYTHON_EXE=%TOOLS_DIR%\python\python.exe"
set "UVICORN_EXE=%TOOLS_DIR%\python\Scripts\uvicorn.exe"
set "NPM_CMD=%TOOLS_DIR%\node\npm.cmd"

echo.
echo =============================================
echo   Trade Copier - Starting Services
echo =============================================
echo.

:: Check that install.bat was run
if not exist "%PYTHON_EXE%" (
    echo ERROR: Python not found in tools\python\.
    echo Please run install.bat first.
    echo.
    pause
    exit /b 1
)

if not exist "%UVICORN_EXE%" (
    echo ERROR: Python dependencies not installed.
    echo Please run install.bat first.
    echo.
    pause
    exit /b 1
)

if not exist "%NPM_CMD%" (
    echo ERROR: Node.js not found in tools\node\.
    echo Please run install.bat first.
    echo.
    pause
    exit /b 1
)

if not exist "%~dp0web\frontend\node_modules" (
    echo ERROR: Frontend dependencies not installed.
    echo Please run install.bat first.
    echo.
    pause
    exit /b 1
)

:: Add portable Node to PATH so npm child processes can find node.exe
set "PATH=%TOOLS_DIR%\node;%PATH%"

echo Starting Hub Service...
start "Hub Service" cmd /k "cd /d "%~dp0" && echo Starting Hub Service on named pipes... && "%PYTHON_EXE%" -m hub.main"

timeout /t 2 /nobreak >nul

echo Starting FastAPI Backend...
start "FastAPI Backend" cmd /k "cd /d "%~dp0" && echo Starting FastAPI on http://localhost:8000 && "%PYTHON_EXE%" -m uvicorn web.api.main:app --host 0.0.0.0 --port 8000"

timeout /t 1 /nobreak >nul

echo Starting Frontend...
start "Frontend" cmd /k "cd /d "%~dp0web\frontend" && echo Starting Next.js on http://localhost:3000 && "%NPM_CMD%" run dev"

echo.
echo =============================================
echo   All services started:
echo =============================================
echo   Hub Service    - named pipes
echo   FastAPI        - http://localhost:8000
echo   Frontend       - http://localhost:3000
echo.

timeout /t 3 /nobreak >nul
start http://localhost:3000
exit /b 0
