# Portable Installer Design

## Problem

`install.bat` relied on `winget` to install Python and Node.js system-wide. This approach fails because:

1. **Microsoft Store Python stub** — Windows 10/11 ships a fake `python.exe` in `%LOCALAPPDATA%\Microsoft\WindowsApps\` that prints "Python" and does nothing. `where python` finds it, making detection unreliable.
2. **PATH not updated in same session** — after `winget install`, the current cmd session doesn't see new tools until relaunched.
3. **Broken winget state** — `winget list` shows Python as "installed" even when files are missing (partial uninstall). Subsequent `winget install` skips it.
4. **Admin rights** — MSI installers and some winget operations require admin privileges the client may not have.

## Solution

Download **portable** (embeddable/zip) versions of Python and Node.js directly into a `tools/` directory inside the project. No system-level installation, no PATH manipulation, no admin rights.

## install.bat

### Prerequisites

- Windows 10/11 (PowerShell available for downloads)
- Internet connection (first run only, ~36 MB total download)

### Steps

```
[1/6] Download Python 3.12 embeddable zip (~11 MB)
      URL: https://www.python.org/ftp/python/3.12.10/python-3.12.10-embed-amd64.zip
      Extract to: tools\python\

[2/6] Configure Python for pip support
      - Edit tools\python\python312._pth: uncomment "import site"
      - Download get-pip.py from https://bootstrap.pypa.io/get-pip.py
      - Run: tools\python\python.exe get-pip.py

[3/6] Install Python dependencies
      Run: tools\python\Scripts\pip.exe install . -q
      This reads pyproject.toml and installs: aiosqlite, fastapi, pywin32,
      python-telegram-bot, uvicorn (+ setuptools as build dependency)

[4/6] Download Node.js 20 LTS portable zip (~25 MB)
      URL: https://nodejs.org/dist/v20.18.1/node-v20.18.1-win-x64.zip
      Extract to: tools\node\

[5/6] Install frontend dependencies
      Run: tools\node\npm.cmd install  (in web\frontend\)

[6/6] Done — print success message
```

### Skip Logic

Each step checks if already completed:
- Step 1: skip if `tools\python\python.exe` exists
- Step 2: skip if `tools\python\Scripts\pip.exe` exists
- Step 3: skip if `tools\python\Lib\site-packages\uvicorn` exists
- Step 4: skip if `tools\node\node.exe` exists
- Step 5: skip if `web\frontend\node_modules` exists

This makes `install.bat` idempotent — safe to run multiple times.

### Download Method

PowerShell `Invoke-WebRequest` (available on all Windows 10/11):
```powershell
powershell -NoProfile -Command "Invoke-WebRequest -Uri 'URL' -OutFile 'FILE'"
```

ZIP extraction via PowerShell:
```powershell
powershell -NoProfile -Command "Expand-Archive -Path 'FILE' -DestinationPath 'DIR' -Force"
```

### Python Embeddable Configuration

After extracting, the `python312._pth` file must be edited to enable `import site`:

```
python312.zip
.
import site
```

Without this line, pip and installed packages won't work.

## start.bat

### Prerequisites

- `install.bat` must have been run successfully

### Steps

```
[1] Check tools\python\python.exe exists → if not: "Run install.bat first"
[2] Check tools\node\node.exe exists → if not: "Run install.bat first"
[3] Start Hub Service:    tools\python\python.exe -m hub.main
[4] Start FastAPI:        tools\python\Scripts\uvicorn.exe web.api.main:app --host 0.0.0.0 --port 8000
[5] Start Frontend:       tools\node\npm.cmd run dev  (in web\frontend\)
[6] Open browser:         http://localhost:3000
```

Each service runs in its own cmd window (via `start "title" cmd /k "..."`).

## Directory Structure

```
project/
├── tools/                        # Created by install.bat (.gitignored)
│   ├── python/                   # Python 3.12 embeddable + packages
│   │   ├── python.exe
│   │   ├── python312._pth
│   │   ├── python312.zip         # Standard library (compressed)
│   │   ├── Scripts/
│   │   │   ├── pip.exe
│   │   │   └── uvicorn.exe
│   │   └── Lib/
│   │       └── site-packages/    # All Python dependencies
│   └── node/                     # Node.js 20 LTS portable
│       ├── node.exe
│       ├── npm.cmd
│       └── node_modules/         # npm's own modules
├── install.bat                   # One-time setup
├── start.bat                     # Daily launcher
├── .gitignore                    # Includes tools/
└── ...
```

## Files to Modify

| File | Action |
|------|--------|
| `install.bat` | Full rewrite — portable download approach |
| `start.bat` | Rewrite — use tools\ paths |
| `.gitignore` | Add `tools/` entry |

## Verification

1. Delete `tools/` and `.venv/` directories
2. Run `install.bat` — should download Python + Node, install all deps
3. Run `start.bat` — should start 3 services, open browser
4. Verify Hub Service window shows "Hub Service started"
5. Verify `http://localhost:8000/docs` loads FastAPI docs
6. Verify `http://localhost:3000` loads frontend
