@echo off
setlocal enabledelayedexpansion
title Trade Copier — Installer
cd /d "%~dp0"

set "TOOLS_DIR=%~dp0tools"
set "PYTHON_DIR=%TOOLS_DIR%\python"
set "NODE_DIR=%TOOLS_DIR%\node"
set "PYTHON_EXE=%PYTHON_DIR%\python.exe"
set "PIP_EXE=%PYTHON_DIR%\Scripts\pip.exe"
set "NODE_EXE=%NODE_DIR%\node.exe"
set "NPM_CMD=%NODE_DIR%\npm.cmd"

set "PYTHON_ZIP_URL=https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip"
set "GET_PIP_URL=https://bootstrap.pypa.io/get-pip.py"
set "NODE_ZIP_URL=https://nodejs.org/dist/v20.18.1/node-v20.18.1-win-x64.zip"

echo.
echo =============================================
echo   Trade Copier - First-Time Setup
echo =============================================
echo.

:: ============================================================
:: [1/6] Download Python embeddable
:: ============================================================
if exist "%PYTHON_EXE%" (
    echo [1/6] Python already downloaded.
) else (
    echo [1/6] Downloading Python 3.12...
    if not exist "%TOOLS_DIR%" mkdir "%TOOLS_DIR%"

    powershell -NoProfile -Command "Invoke-WebRequest -Uri '%PYTHON_ZIP_URL%' -OutFile '%TOOLS_DIR%\python.zip'"
    if errorlevel 1 (
        echo ERROR: Failed to download Python.
        pause & exit /b 1
    )

    echo       Extracting...
    powershell -NoProfile -Command "Expand-Archive -Path '%TOOLS_DIR%\python.zip' -DestinationPath '%PYTHON_DIR%' -Force"
    if errorlevel 1 (
        echo ERROR: Failed to extract Python.
        pause & exit /b 1
    )

    del "%TOOLS_DIR%\python.zip" 2>nul
    echo [1/6] Python downloaded.
)

:: ============================================================
:: [2/6] Configure Python for pip (enable import site)
:: ============================================================
if exist "%PIP_EXE%" (
    echo [2/6] pip already installed.
) else (
    echo [2/6] Configuring Python and installing pip...

    :: Configure _pth file: enable import site + add project root
    echo python312.zip> "%PYTHON_DIR%\python312._pth"
    echo .>> "%PYTHON_DIR%\python312._pth"
    echo ..\..>> "%PYTHON_DIR%\python312._pth"
    echo import site>> "%PYTHON_DIR%\python312._pth"

    :: Download and run get-pip.py
    powershell -NoProfile -Command "Invoke-WebRequest -Uri '%GET_PIP_URL%' -OutFile '%TOOLS_DIR%\get-pip.py'"
    if errorlevel 1 (
        echo ERROR: Failed to download get-pip.py.
        pause & exit /b 1
    )

    "%PYTHON_EXE%" "%TOOLS_DIR%\get-pip.py" --no-warn-script-location -q
    if errorlevel 1 (
        echo ERROR: Failed to install pip.
        pause & exit /b 1
    )

    del "%TOOLS_DIR%\get-pip.py" 2>nul
    echo [2/6] pip installed.
)

:: ============================================================
:: [3/6] Install Python dependencies
:: ============================================================
if exist "%PYTHON_DIR%\Lib\site-packages\uvicorn" (
    echo [3/6] Python dependencies already installed.
) else (
    echo [3/6] Installing Python dependencies...
    "%PIP_EXE%" install aiosqlite fastapi pywin32 python-telegram-bot uvicorn -q --no-warn-script-location
    if errorlevel 1 (
        echo ERROR: Failed to install Python dependencies.
        pause & exit /b 1
    )
    echo [3/6] Python dependencies installed.
)

:: ============================================================
:: [4/6] Download Node.js portable
:: ============================================================
if exist "%NODE_EXE%" (
    echo [4/6] Node.js already downloaded.
) else (
    echo [4/6] Downloading Node.js 20 LTS...

    powershell -NoProfile -Command "Invoke-WebRequest -Uri '%NODE_ZIP_URL%' -OutFile '%TOOLS_DIR%\node.zip'"
    if errorlevel 1 (
        echo ERROR: Failed to download Node.js.
        pause & exit /b 1
    )

    echo       Extracting...
    powershell -NoProfile -Command "Expand-Archive -Path '%TOOLS_DIR%\node.zip' -DestinationPath '%TOOLS_DIR%\node-temp' -Force"
    if errorlevel 1 (
        echo ERROR: Failed to extract Node.js.
        pause & exit /b 1
    )

    :: Node zip extracts into a subfolder (node-v20.18.1-win-x64), move contents up
    for /d %%D in ("%TOOLS_DIR%\node-temp\node-v*") do (
        move "%%D" "%NODE_DIR%" >nul
    )
    rmdir /s /q "%TOOLS_DIR%\node-temp" 2>nul

    del "%TOOLS_DIR%\node.zip" 2>nul
    echo [4/6] Node.js downloaded.
)

:: ============================================================
:: [5/6] Install frontend dependencies
:: ============================================================
if exist "%~dp0web\frontend\node_modules" (
    echo [5/6] Frontend dependencies already installed.
) else (
    echo [5/6] Installing frontend dependencies...
    set "PATH=%NODE_DIR%;%PATH%"
    pushd "%~dp0web\frontend"
    "%NPM_CMD%" install
    if errorlevel 1 (
        echo ERROR: Failed to install frontend dependencies.
        popd
        pause & exit /b 1
    )
    popd
    echo [5/6] Frontend dependencies installed.
)

:: ============================================================
:: [6/6] Done
:: ============================================================
echo.
echo =============================================
echo   [6/6] Setup complete!
echo   Run start.bat to launch the application.
echo =============================================
echo.
pause
exit /b 0
