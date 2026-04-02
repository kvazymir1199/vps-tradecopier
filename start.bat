@echo off
setlocal enabledelayedexpansion
title Trade Copier — Setup & Launch
cd /d "%~dp0"

echo.
echo =============================================
echo   Trade Copier - One-Click Launcher
echo =============================================
echo.

:: [0] Python
where python >nul 2>&1
if errorlevel 1 (
    echo [0/5] Python not found. Installing via winget...
    winget install --id Python.Python.3.11 --silent --accept-package-agreements >nul 2>&1
    if errorlevel 1 (
        echo.
        echo ERROR: Could not install Python automatically.
        echo Please install Python 3.11+ manually from: https://python.org
        echo.
        pause
        exit /b 1
    )
)
echo [0/5] Python OK

:: [1] uv
where uv >nul 2>&1
if errorlevel 1 (
    echo [1/5] Installing uv package manager...
    pip install uv -q
)
echo [1/5] uv OK

:: [2] Python dependencies
echo [2/5] Syncing Python dependencies...
uv sync -q

:: [3] Node.js
where npm >nul 2>&1
if errorlevel 1 (
    echo [3/5] Node.js not found. Installing via winget...
    winget install --id OpenJS.NodeJS.LTS --silent --accept-package-agreements >nul 2>&1
    if errorlevel 1 (
        echo.
        echo ERROR: Could not install Node.js automatically.
        echo Please install Node.js 18+ manually from: https://nodejs.org
        echo.
        pause
        exit /b 1
    )
)
echo [3/5] Node.js OK

:: [4] Frontend dependencies
if not exist "%~dp0web\frontend\node_modules" (
    echo [4/5] Installing frontend dependencies...
    pushd "%~dp0web\frontend"
    call npm install --silent
    popd
    echo [4/5] Frontend dependencies OK
) else (
    echo [4/5] Frontend dependencies OK
)

:: [5] Start all services
echo [5/5] Starting services...
echo.

start "Hub Service" cmd /k "cd /d "%~dp0" && echo Starting Hub Service on named pipes... && uv run python -m hub.main"

timeout /t 2 /nobreak >nul

start "FastAPI Backend" cmd /k "cd /d "%~dp0" && echo Starting FastAPI on http://localhost:8000 && uv run uvicorn web.api.main:app --host 0.0.0.0 --port 8000"

timeout /t 1 /nobreak >nul

start "Frontend" cmd /k "cd /d "%~dp0\web\frontend" && echo Starting Next.js on http://localhost:3000 && npm run dev"

echo.
echo =============================================
echo   All services started:
echo =============================================
echo   Hub Service    - Windows named pipes
echo   FastAPI        - http://localhost:8000
echo   Frontend       - http://localhost:3000
echo.
echo   Opening dashboard in browser...
echo =============================================
echo.

timeout /t 3 /nobreak >nul
start http://localhost:3000
