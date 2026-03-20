@echo off
title Trade Copier - Stop
echo ============================================
echo   Trade Copier - Stopping all services...
echo ============================================
echo.

:: Kill Python processes (Hub + FastAPI)
taskkill /fi "WINDOWTITLE eq Hub Service*" /f 2>nul
taskkill /fi "WINDOWTITLE eq FastAPI Backend*" /f 2>nul

:: Kill Node.js (Frontend)
taskkill /fi "WINDOWTITLE eq Frontend*" /f 2>nul

echo.
echo   All services stopped.
echo ============================================
pause
