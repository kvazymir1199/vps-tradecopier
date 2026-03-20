@echo off
title Trade Copier Launcher
cd /d "%~dp0"

echo ============================================
echo   Trade Copier - Starting all services...
echo ============================================
echo.

:: Start Hub Service
echo [1/3] Starting Hub Service...
start "Hub Service" cmd /k "cd /d "%~dp0" && uv run python -m hub.main"

:: Small delay so Hub initializes pipes before API connects
timeout /t 2 /nobreak >nul

:: Start FastAPI Backend
echo [2/3] Starting FastAPI Backend (port 8000)...
start "FastAPI Backend" cmd /k "cd /d "%~dp0" && uv run uvicorn web.api.main:app --host 0.0.0.0 --port 8000"

:: Start Next.js Frontend
echo [3/3] Starting Frontend (port 3000)...
start "Frontend" cmd /k "cd /d "%~dp0\web\frontend" && npm run dev"

echo.
echo ============================================
echo   All services started:
echo     Hub Service    - named pipes
echo     FastAPI        - http://localhost:8000
echo     Frontend       - http://localhost:3000
echo ============================================
echo.
echo Press any key to open the dashboard...
pause >nul
start http://localhost:3000
