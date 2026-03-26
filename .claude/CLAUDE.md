# CLAUDE.md

Answer Always in English.

## Project Overview

**Trade Copier** — a trade copying system between MT5 terminals.

Consists of 4 components:
- **Hub Service** (Python) — central message router via Windows named pipes
- **Master EA** (MQL5) — monitors trades on the master terminal and sends them to Hub
- **Slave EA** (MQL5) — receives commands from Hub and executes trades via CTrade
- **Web UI** — FastAPI backend + Next.js frontend for managing terminals and links

**Broker**: Pepperstone
**Platform**: Windows (named pipes for IPC)
**Python**: 3.11+ with package manager `uv`

## Architecture

```
Master EA ──named pipe──> Hub Service ──named pipe──> Slave EA
  (MT5)     JSON msgs     (Python)     SlaveCommands   (MT5)
            <── ACK/NACK              <── ACK/NACK

                          Hub Service
                              │
                           SQLite (WAL)
                              │
                          FastAPI ──> Next.js UI
```

## Project Structure

```
hub/                          # Python Hub Service
├── db/
│   ├── schema.sql            # DDL (9 tables, WAL mode)
│   └── manager.py            # DatabaseManager (sole writer)
├── protocol/
│   ├── models.py             # MessageType, MasterMessage, SlaveCommand, AckMessage
│   └── serializer.py         # JSON encode/decode with newline delimiter
├── mapping/
│   ├── magic.py              # Magic number parse + slave mapping
│   ├── symbol.py             # Symbol resolution (explicit > suffix)
│   └── lot.py                # Lot size: multiplier, fixed, partial close
├── transport/
│   └── pipe_server.py        # Async Windows named pipe server
├── router/
│   └── router.py             # Message router + ResendWindow (N=200)
├── monitor/
│   ├── health.py             # 4 checks: heartbeat, ACK timeout, NACKs, queue
│   └── alerts.py             # Telegram alerts + deduplication (5 min)
├── config.py                 # Config loader (JSON)
└── main.py                   # HubService entry point (asyncio)

ea/                           # MQL5 Expert Advisors
├── Include/
│   ├── CopierPipe.mqh        # Named pipe client (kernel32.dll imports)
│   ├── CopierProtocol.mqh    # JSON builder/parser
│   └── CopierLogger.mqh      # File logger
├── Master/
│   └── TradeCopierMaster.mq5 # Master EA
└── Slave/
    └── TradeCopierSlave.mq5  # Slave EA

web/
├── api/                      # FastAPI backend
│   ├── main.py               # App with CORS
│   ├── database.py           # aiosqlite connection (WAL)
│   ├── schemas.py            # Pydantic models
│   └── routers/              # terminals, links, symbol_mappings, magic_mappings
└── frontend/                 # Next.js + shadcn/ui
    └── src/
        ├── app/              # App Router (page.tsx, layout.tsx)
        ├── components/       # Tables, dialogs, mappings panel
        ├── hooks/            # use-terminals (5s poll), use-links, use-mappings
        ├── lib/              # api.ts, utils.ts
        └── types/            # Terminal, Link, SymbolMapping, MagicMapping

tests/                        # 70 pytest tests (15 files)
scripts/backup_db.py          # DB backup with WAL checkpoint + retention
config/config.example.json    # Configuration example
```

## Build & Run Commands

### Hub Service
```bash
uv run python -m hub.main
```

### FastAPI Backend
```bash
uv run uvicorn web.api.main:app --reload --port 8000
```

### Frontend
```bash
cd web/frontend && npm run dev          # Dev (port 3000)
cd web/frontend && npm run build        # Production build
```

### Tests
```bash
uv run pytest                           # All tests
uv run pytest tests/test_router.py      # Specific file
uv run pytest -k "test_name"            # By name
```

### MQL5
Copy `ea/` to the MQL5 terminal directory, compile via MetaEditor.

## Key Concepts

### Magic Number Mapping
```
slave_magic = master_magic - (master_magic % 100) + slave_setup_id
```

### Symbol Resolution
Priority: explicit mapping > suffix rule (`master_symbol + suffix`).

### Lot Size Modes
- **multiplier**: `master_volume * lot_value`
- **fixed**: `lot_value` (constant)
- **partial close**: proportional recalculation

### Message Protocol
Newline-delimited JSON via Windows named pipes.
Types: OPEN, MODIFY, CLOSE, CLOSE_PARTIAL, HEARTBEAT, REGISTER.

### Database
SQLite WAL mode. 9 tables. DatabaseManager — sole writer.

## Development Rules

### MUST DO
1. **Read before modifying** — Always read a file before modifying it
2. **uv** — Use `uv` for dependencies, not pip
3. **Tests** — Cover new logic with tests (pytest-asyncio)
4. **Async** — Hub Service runs on asyncio, do not block the event loop
5. **WAL mode** — SQLite always in WAL mode

### FORBIDDEN
1. **DO NOT** block the asyncio event loop with synchronous calls
2. **DO NOT** write to the database bypassing DatabaseManager
3. **DO NOT** hardcode named pipe paths — use config.json
4. **DO NOT** remove health checks and alerts

## Naming Conventions

### Python
- Classes: `PascalCase` (DatabaseManager, PipeServer)
- Functions: `snake_case` (compute_slave_volume, resolve_symbol)
- Constants: `UPPER_CASE`

### MQL5
- Classes: `CClassName`, members: `m_member`, inputs: `InpName`
- Enums: `ENUM_TYPE_VALUE`, structs: `SStructName`
- Locals: `snake_case`

### TypeScript
- Interfaces/components: `PascalCase`
- Hooks: `useCamelCase`

## Documentation

- `docs/plans/` — Architecture, DB, frontend, implementation plan
- `.claude/rules/trading-logic.md` — Trading logic rules
- `.claude/rules/mql5-style.md` — MQL5 code style guide
