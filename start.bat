@echo off
setlocal
title Trade Copier — Launcher
cd /d "%~dp0"

echo.
echo =============================================
echo   Trade Copier - Starting Services
echo =============================================
echo.

:: Check that install.bat was run
if not exist "%~dp0.venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found.
    echo Please run install.bat first.
    echo.
    pause
    exit /b 1
)

if not exist "%~dp0web\frontend\node_modules" (
    echo ERROR: Frontend dependencies not found.
    echo Please run install.bat first.
    echo.
    pause
    exit /b 1
)

echo Starting Hub Service...
start "Hub Service" cmd /k "cd /d "%~dp0" && .venv\Scripts\python.exe -m hub.main"

timeout /t 2 /nobreak >nul

echo Starting FastAPI Backend...
start "FastAPI Backend" cmd /k "cd /d "%~dp0" && .venv\Scripts\uvicorn.exe web.api.main:app --host 0.0.0.0 --port 8000"

timeout /t 1 /nobreak >nul

echo Starting Frontend...
start "Frontend" cmd /k "cd /d "%~dp0\web\frontend" && npm run dev"

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
