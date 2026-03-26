# Trade Copier

A trade copying system between MetaTrader 5 terminals. The master terminal opens trades, and they are automatically copied to one or more slave terminals.

## Architecture

```
Master EA (MT5)  ──named pipe──>  Hub Service (Python)  ──named pipe──>  Slave EA (MT5)
                   JSON msgs       central                SlaveCommands
                                   router
                                        │
                                     SQLite DB
                                        │
                                   FastAPI ──> Next.js UI
```

**Components:**
- **Hub Service** — central message router (asyncio + Windows named pipes)
- **Master EA** — MQL5 Expert Advisor that monitors trades and sends events to Hub
- **Slave EA** — MQL5 Expert Advisor that receives commands from Hub and executes them via CTrade
- **Web UI** — FastAPI backend + Next.js frontend for managing terminals, links, and settings

## Requirements

- **OS:** Windows 10/11 (named pipes — Windows-only IPC mechanism)
- **Python:** 3.11+ with [uv](https://docs.astral.sh/uv/) package manager
- **Node.js:** 18+ (for Next.js frontend)
- **MetaTrader 5:** with access to MetaEditor for compiling EAs

## Installation

### 1. Clone the repository

```bash
git clone <repo-url>
cd Tino-V
```

### 2. Install Python dependencies

```bash
uv sync
```

### 3. Install frontend dependencies

```bash
cd web/frontend
npm install
cd ../..
```

### 4. Compile the EAs

1. Copy the contents of the `ea/` folder to the MQL5 directory of your MT5 terminal
2. Open MetaEditor (F4 in the terminal)
3. Compile `TradeCopierMaster.mq5` and `TradeCopierSlave.mq5` (F7)

## Running

### Quick Start

```bash
start.bat
```

Launches all 3 services (Hub, FastAPI, Frontend) in separate windows.

### Manual Start

```bash
# 1. Hub Service
uv run python -m hub.main

# 2. FastAPI Backend (in another terminal)
uv run uvicorn web.api.main:app --host 0.0.0.0 --port 8000

# 3. Frontend (in another terminal)
cd web/frontend && npm run dev
```

### Stopping

```bash
stop.bat
```

## Configuration

### Terminal Setup

1. Open Web UI: http://localhost:3000
2. In MT5, attach Master EA to a chart on the master terminal:
   - `TerminalID` = `master_1`
   - `PipeName` = `copier_master_1`
3. Attach Slave EA to charts on slave terminals:
   - `TerminalID` = `slave_1` (or `slave_2`, etc.)
   - `CmdPipeName` = `copier_slave_1_cmd`
   - `AckPipeName` = `copier_slave_1_ack`

The EA will automatically register in the database and appear in the Web UI.

### Creating Links

In the Web UI, click **+ Add Link** and select:
- **Master** — trade source
- **Slave** — trade receiver
- **Lot Mode** — `multiplier` or `fixed` (fixed volume)
- **Lot Value** — value (e.g., `1.0` = same volume)
- **Suffix** — symbol suffix for the slave broker (e.g., `m` → `EURUSDm`, `.sml` → `EURUSD.sml`)

### Service Configuration

Settings are available in the Web UI: http://localhost:3000/settings

| Parameter | Default | Description |
|-----------|---------|-------------|
| VPS ID | vps_1 | VPS identifier |
| Heartbeat Interval | 10 sec | Heartbeat frequency from EA |
| Heartbeat Timeout | 30 sec | Timeout before Disconnected status |
| ACK Timeout | 5 sec | Timeout waiting for ACK from slave |
| ACK Max Retries | 3 | Number of retry attempts |
| Resend Window | 200 | Deduplication window size |
| Alert Dedup | 5 min | Alert deduplication interval |
| Telegram | off | Send alerts to Telegram |

## Supported Operations

| Operation | Description |
|-----------|-------------|
| OPEN | Open a new position |
| MODIFY | Modify SL/TP of an existing position |
| CLOSE | Fully close a position |
| CLOSE_PARTIAL | Partially close a position (by volume) |

## Magic Number Mapping

Formula: `slave_magic = master_magic - (master_magic % 100) + slave_setup_id`

Configured via the Web UI for each link.

## Database

SQLite in WAL mode. File: `%APPDATA%\MetaQuotes\Terminal\Common\Files\TradeCopier\copier.db`

Created automatically on the first Hub launch.

## Tests

```bash
uv run pytest                    # All tests
uv run pytest tests/test_router.py  # Specific file
uv run pytest -k "test_name"    # By name
```

## Project Structure

```
hub/                    # Python Hub Service
├── config.py           # Configuration (from SQLite)
├── main.py             # Entry point (asyncio)
├── db/                 # DB schema + DatabaseManager
├── protocol/           # Message models + serialization
├── mapping/            # Magic, symbol, lot mapping
├── router/             # Routing + ResendWindow
├── transport/          # Named pipe server
└── monitor/            # Health checks + Telegram alerts

ea/                     # MQL5 Expert Advisors
├── Include/            # Shared modules (pipe, protocol, logger, database)
├── Master/             # Master EA
└── Slave/              # Slave EA

web/
├── api/                # FastAPI backend
└── frontend/           # Next.js + shadcn/ui

tests/                  # pytest tests
```
