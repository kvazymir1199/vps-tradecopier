# Trade Copier Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an MT5 Trade Copier with Python Hub Service routing messages between Master and Slave EAs via named pipes, backed by a single SQLite database. Web panel (FastAPI + Next.js) for terminal and link management.

**Architecture:** Hub Service (Python, asyncio) is the central router. Master EAs detect trade events and send JSON messages through named pipes to Hub. Hub maps symbols, magic numbers, lot sizes per subscription, then forwards commands to Slave EAs. Slaves execute via CTrade and send ACK/NACK. All state lives in one SQLite DB (WAL mode). FastAPI (separate process) provides REST API for the Next.js web panel. Both Hub and FastAPI read+write the same SQLite via WAL mode.

**Tech Stack:** Python 3.11+ (asyncio, aiosqlite, win32pipe, FastAPI, uvicorn), MQL5, SQLite (WAL), Next.js 14+ (shadcn/ui, Tailwind, TypeScript), NSSM (Windows Service), Telegram Bot API.

**Reference docs:**
- Architecture: `docs/plans/2026-02-26-trade-copier-architecture.md`
- DB Structure: `docs/plans/2026-02-26-database-structure.md`
- Frontend Design: `docs/plans/2026-02-26-frontend-design.md`

---

## Project Structure

```
c:\Tino-V\
├── hub/                          # Python Hub Service
│   ├── __init__.py
│   ├── main.py                   # Entry point (asyncio)
│   ├── config.py                 # Config loader
│   ├── db/
│   │   ├── __init__.py
│   │   ├── manager.py            # SQLite manager (sole writer)
│   │   └── schema.sql            # DDL script
│   ├── protocol/
│   │   ├── __init__.py
│   │   ├── models.py             # Message dataclasses
│   │   └── serializer.py         # JSON encode/decode
│   ├── mapping/
│   │   ├── __init__.py
│   │   ├── magic.py              # Magic number logic
│   │   ├── symbol.py             # Symbol resolution
│   │   └── lot.py                # Lot size calculation
│   ├── transport/
│   │   ├── __init__.py
│   │   └── pipe_server.py        # Named pipe async server
│   ├── router/
│   │   ├── __init__.py
│   │   └── router.py             # Message routing engine
│   └── monitor/
│       ├── __init__.py
│       ├── health.py             # Health check loop
│       └── alerts.py             # Telegram/Email sender
├── scripts/
│   └── backup_db.py              # DB backup script
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_serializer.py
│   ├── test_magic.py
│   ├── test_symbol.py
│   ├── test_lot.py
│   ├── test_db_manager.py
│   ├── test_router.py
│   ├── test_pipe_server.py
│   ├── test_health.py
│   ├── test_alerts.py
│   └── test_integration.py
├── ea/
│   ├── Master/
│   │   └── TradeCopierMaster.mq5
│   ├── Slave/
│   │   └── TradeCopierSlave.mq5
│   └── Include/
│       ├── CopierPipe.mqh
│       ├── CopierProtocol.mqh
│       └── CopierLogger.mqh
├── web/
│   ├── api/                          # FastAPI backend
│   │   ├── __init__.py
│   │   ├── main.py                   # FastAPI app, CORS, lifespan
│   │   ├── database.py               # SQLite connection (aiosqlite, WAL)
│   │   ├── schemas.py                # Pydantic request/response models
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── terminals.py          # GET /api/terminals
│   │       ├── links.py              # CRUD /api/links
│   │       ├── symbol_mappings.py    # CRUD /api/links/{id}/symbol-mappings
│   │       └── magic_mappings.py     # CRUD /api/links/{id}/magic-mappings
│   └── frontend/                     # Next.js app
│       ├── package.json
│       ├── next.config.js
│       ├── tailwind.config.ts
│       ├── tsconfig.json
│       └── src/
│           ├── app/
│           │   ├── layout.tsx
│           │   ├── page.tsx          # Single page: terminals + links + mappings
│           │   └── globals.css
│           ├── components/
│           │   ├── terminals-table.tsx
│           │   ├── links-table.tsx
│           │   ├── mappings-panel.tsx
│           │   ├── add-link-dialog.tsx
│           │   ├── edit-link-dialog.tsx
│           │   ├── add-mapping-dialog.tsx
│           │   └── status-badge.tsx
│           ├── hooks/
│           │   ├── use-terminals.ts  # Polling hook (5s)
│           │   ├── use-links.ts
│           │   └── use-mappings.ts
│           ├── lib/
│           │   ├── api.ts            # Fetch wrapper
│           │   └── utils.ts          # formatTimeAgo, etc.
│           └── types/
│               └── index.ts          # TypeScript interfaces
├── config/
│   └── config.example.json
├── requirements.txt
└── pyproject.toml
```

---

## Phase 1: Project Scaffolding & Database Layer

### Task 1: Initialize Python project

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `hub/__init__.py`
- Create: `tests/__init__.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "trade-copier-hub"
version = "0.1.0"
requires-python = ">=3.11"

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

**Step 2: Create requirements.txt**

```
aiosqlite>=0.20.0
pywin32>=306
python-telegram-bot>=21.0
pytest>=8.0
pytest-asyncio>=0.23
```

**Step 3: Create empty __init__.py files**

Create `hub/__init__.py`, `hub/db/__init__.py`, `hub/protocol/__init__.py`, `hub/mapping/__init__.py`, `hub/transport/__init__.py`, `hub/router/__init__.py`, `hub/monitor/__init__.py`, `tests/__init__.py` — all empty.

**Step 4: Install dependencies**

Run: `cd c:\Tino-V && pip install -r requirements.txt`

**Step 5: Verify pytest runs**

Run: `cd c:\Tino-V && python -m pytest --co -q`
Expected: "no tests ran"

**Step 6: Commit**

```bash
git init
git add .
git commit -m "chore: initialize project scaffolding"
```

---

### Task 2: Database schema DDL

**Files:**
- Create: `hub/db/schema.sql`

**Step 1: Write the full DDL**

Write `hub/db/schema.sql` with all 9 tables from `docs/plans/2026-02-26-database-structure.md`:
- `terminals`, `master_slave_links`, `symbol_mappings`, `magic_mappings`
- `trade_mappings`, `messages`, `message_acks`, `heartbeats`, `alerts_history`
- All indexes, constraints, CHECK clauses
- PRAGMA statements at top: `journal_mode=WAL`, `busy_timeout=5000`, `foreign_keys=ON`, `synchronous=NORMAL`

**Step 2: Validate DDL syntax**

Run: `cd c:\Tino-V && python -c "import sqlite3; conn = sqlite3.connect(':memory:'); conn.executescript(open('hub/db/schema.sql').read()); print('OK'); conn.close()"`
Expected: `OK`

**Step 3: Commit**

```bash
git add hub/db/schema.sql
git commit -m "feat: add database DDL schema (9 tables)"
```

---

### Task 3: Database manager — init & terminal registration

**Files:**
- Create: `hub/db/manager.py`
- Create: `tests/test_db_manager.py`

**Step 1: Write failing tests for DB init and terminal registration**

```python
# tests/test_db_manager.py
import pytest
import aiosqlite
from hub.db.manager import DatabaseManager

@pytest.fixture
async def db():
    mgr = DatabaseManager(":memory:")
    await mgr.initialize()
    yield mgr
    await mgr.close()

@pytest.mark.asyncio
async def test_initialize_creates_tables(db):
    tables = await db.fetch_all("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    names = [r["name"] for r in tables]
    assert "terminals" in names
    assert "master_slave_links" in names
    assert "messages" in names

@pytest.mark.asyncio
async def test_register_terminal(db):
    await db.register_terminal("master_1", "master", 12345, "Broker-Live")
    row = await db.fetch_one("SELECT * FROM terminals WHERE terminal_id = ?", ("master_1",))
    assert row["role"] == "master"
    assert row["account_number"] == 12345
    assert row["status"] == "Starting"

@pytest.mark.asyncio
async def test_register_terminal_idempotent(db):
    await db.register_terminal("slave_1", "slave", 67890, "Broker-Demo")
    await db.register_terminal("slave_1", "slave", 67890, "Broker-Demo")  # no error
    rows = await db.fetch_all("SELECT * FROM terminals WHERE terminal_id = ?", ("slave_1",))
    assert len(rows) == 1

@pytest.mark.asyncio
async def test_update_terminal_status(db):
    await db.register_terminal("master_1", "master", 12345, "Broker-Live")
    await db.update_terminal_status("master_1", "Active", "")
    row = await db.fetch_one("SELECT status FROM terminals WHERE terminal_id = ?", ("master_1",))
    assert row["status"] == "Active"
```

**Step 2: Run tests to verify they fail**

Run: `cd c:\Tino-V && python -m pytest tests/test_db_manager.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 3: Implement DatabaseManager**

```python
# hub/db/manager.py
import time
from pathlib import Path
import aiosqlite

SCHEMA_PATH = Path(__file__).parent / "schema.sql"

class DatabaseManager:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self):
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        await self._conn.executescript(schema)

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def execute(self, sql: str, params: tuple = ()):
        await self._conn.execute(sql, params)
        await self._conn.commit()

    async def fetch_one(self, sql: str, params: tuple = ()):
        cursor = await self._conn.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def fetch_all(self, sql: str, params: tuple = ()):
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    async def register_terminal(self, terminal_id: str, role: str, account_number: int, broker_server: str):
        now = self._now_ms()
        await self._conn.execute(
            "INSERT OR IGNORE INTO terminals (terminal_id, role, account_number, broker_server, status, created_at, last_heartbeat) "
            "VALUES (?, ?, ?, ?, 'Starting', ?, ?)",
            (terminal_id, role, account_number, broker_server, now, now),
        )
        await self._conn.commit()

    async def update_terminal_status(self, terminal_id: str, status: str, status_message: str = ""):
        await self._conn.execute(
            "UPDATE terminals SET status = ?, status_message = ? WHERE terminal_id = ?",
            (status, status_message, terminal_id),
        )
        await self._conn.commit()
```

**Step 4: Run tests to verify they pass**

Run: `cd c:\Tino-V && python -m pytest tests/test_db_manager.py -v`
Expected: 4 passed

**Step 5: Commit**

```bash
git add hub/db/manager.py tests/test_db_manager.py
git commit -m "feat: DatabaseManager with init, register, status update"
```

---

### Task 4: DB manager — message & ACK storage, trade mappings

**Files:**
- Modify: `hub/db/manager.py`
- Modify: `tests/test_db_manager.py`

**Step 1: Write failing tests**

Add to `tests/test_db_manager.py`:

```python
@pytest.mark.asyncio
async def test_insert_message(db):
    await db.insert_message(1, "master_1", "OPEN", '{"ticket":123}', 1700000000000)
    row = await db.fetch_one("SELECT * FROM messages WHERE msg_id = 1 AND master_id = 'master_1'")
    assert row["type"] == "OPEN"
    assert row["status"] == "pending"

@pytest.mark.asyncio
async def test_insert_ack(db):
    await db.insert_message(1, "master_1", "OPEN", '{"ticket":123}', 1700000000000)
    await db.insert_ack(1, "master_1", "slave_1", "ACK", None, 87654321, 1700000000500)
    row = await db.fetch_one("SELECT * FROM message_acks WHERE msg_id = 1 AND slave_id = 'slave_1'")
    assert row["ack_type"] == "ACK"
    assert row["slave_ticket"] == 87654321

@pytest.mark.asyncio
async def test_insert_trade_mapping(db):
    await db.insert_trade_mapping("master_1", "slave_1", 123, None, 15010301, 15010305, "EURUSD.s", 0.1, 0.2)
    row = await db.fetch_one("SELECT * FROM trade_mappings WHERE master_ticket = 123")
    assert row["status"] == "pending"
    assert row["slave_magic"] == 15010305

@pytest.mark.asyncio
async def test_update_trade_mapping_on_ack(db):
    await db.insert_trade_mapping("master_1", "slave_1", 123, None, 15010301, 15010305, "EURUSD.s", 0.1, 0.2)
    await db.update_trade_mapping_ack("master_1", "slave_1", 123, slave_ticket=87654321)
    row = await db.fetch_one("SELECT * FROM trade_mappings WHERE master_ticket = 123")
    assert row["status"] == "open"
    assert row["slave_ticket"] == 87654321

@pytest.mark.asyncio
async def test_update_trade_mapping_closed(db):
    await db.insert_trade_mapping("master_1", "slave_1", 123, None, 15010301, 15010305, "EURUSD.s", 0.1, 0.2)
    await db.update_trade_mapping_ack("master_1", "slave_1", 123, slave_ticket=87654321)
    await db.update_trade_mapping_status("master_1", "slave_1", 123, "closed")
    row = await db.fetch_one("SELECT * FROM trade_mappings WHERE master_ticket = 123")
    assert row["status"] == "closed"
    assert row["closed_at"] is not None
```

**Step 2: Run to verify fail**

Run: `cd c:\Tino-V && python -m pytest tests/test_db_manager.py -v`
Expected: new tests FAIL

**Step 3: Implement methods in DatabaseManager**

Add to `hub/db/manager.py`:

```python
    async def insert_message(self, msg_id: int, master_id: str, msg_type: str, payload: str, ts_ms: int):
        await self._conn.execute(
            "INSERT INTO messages (msg_id, master_id, type, payload, ts_ms, status) VALUES (?, ?, ?, ?, ?, 'pending')",
            (msg_id, master_id, msg_type, payload, ts_ms),
        )
        await self._conn.commit()

    async def update_message_status(self, msg_id: int, master_id: str, status: str):
        await self._conn.execute(
            "UPDATE messages SET status = ? WHERE msg_id = ? AND master_id = ?",
            (status, msg_id, master_id),
        )
        await self._conn.commit()

    async def insert_ack(self, msg_id: int, master_id: str, slave_id: str, ack_type: str, nack_reason: str | None, slave_ticket: int | None, ts_ms: int):
        await self._conn.execute(
            "INSERT INTO message_acks (msg_id, master_id, slave_id, ack_type, nack_reason, slave_ticket, ts_ms) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (msg_id, master_id, slave_id, ack_type, nack_reason, slave_ticket, ts_ms),
        )
        await self._conn.commit()

    async def insert_trade_mapping(self, master_id: str, slave_id: str, master_ticket: int, slave_ticket: int | None, master_magic: int, slave_magic: int, symbol: str, master_volume: float, slave_volume: float):
        now = self._now_ms()
        await self._conn.execute(
            "INSERT INTO trade_mappings (master_id, slave_id, master_ticket, slave_ticket, master_magic, slave_magic, symbol, master_volume, slave_volume, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (master_id, slave_id, master_ticket, slave_ticket, master_magic, slave_magic, symbol, master_volume, slave_volume, now),
        )
        await self._conn.commit()

    async def update_trade_mapping_ack(self, master_id: str, slave_id: str, master_ticket: int, slave_ticket: int):
        await self._conn.execute(
            "UPDATE trade_mappings SET slave_ticket = ?, status = 'open' WHERE master_id = ? AND slave_id = ? AND master_ticket = ?",
            (slave_ticket, master_id, slave_id, master_ticket),
        )
        await self._conn.commit()

    async def update_trade_mapping_status(self, master_id: str, slave_id: str, master_ticket: int, status: str):
        closed_at = self._now_ms() if status in ("closed", "failed") else None
        await self._conn.execute(
            "UPDATE trade_mappings SET status = ?, closed_at = ? WHERE master_id = ? AND slave_id = ? AND master_ticket = ?",
            (status, closed_at, master_id, slave_id, master_ticket),
        )
        await self._conn.commit()
```

**Step 4: Run all tests**

Run: `cd c:\Tino-V && python -m pytest tests/test_db_manager.py -v`
Expected: all passed

**Step 5: Commit**

```bash
git add hub/db/manager.py tests/test_db_manager.py
git commit -m "feat: DB manager - messages, ACKs, trade mappings"
```

---

### Task 5: DB manager — links, heartbeats, data retention

**Files:**
- Modify: `hub/db/manager.py`
- Modify: `tests/test_db_manager.py`

**Step 1: Write failing tests for links and heartbeat storage**

```python
@pytest.mark.asyncio
async def test_get_active_links_for_master(db):
    await db.register_terminal("master_1", "master", 111, "B1")
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.register_terminal("slave_2", "slave", 333, "B3")
    await db.execute(
        "INSERT INTO master_slave_links (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at) VALUES (?, ?, 1, 'multiplier', 2.0, '.s', ?)",
        ("master_1", "slave_1", 1700000000000),
    )
    await db.execute(
        "INSERT INTO master_slave_links (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at) VALUES (?, ?, 0, 'fixed', 0.05, '.f', ?)",
        ("master_1", "slave_2", 1700000000000),
    )
    links = await db.get_active_links("master_1")
    assert len(links) == 1
    assert links[0]["slave_id"] == "slave_1"
    assert links[0]["lot_mode"] == "multiplier"

@pytest.mark.asyncio
async def test_insert_heartbeat(db):
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.insert_heartbeat("slave_1", "vps_1", 1700000000000, 0, "Active", "")
    row = await db.fetch_one("SELECT * FROM heartbeats WHERE terminal_id = 'slave_1'")
    assert row["vps_id"] == "vps_1"
    # Also check that terminals.last_heartbeat updated
    term = await db.fetch_one("SELECT last_heartbeat FROM terminals WHERE terminal_id = 'slave_1'")
    assert term["last_heartbeat"] == 1700000000000

@pytest.mark.asyncio
async def test_purge_old_heartbeats(db):
    await db.register_terminal("slave_1", "slave", 222, "B2")
    old_ts = 1700000000000  # old
    new_ts = int(time.time() * 1000)  # current
    await db.insert_heartbeat("slave_1", "vps_1", old_ts, 0, "Active", "")
    await db.insert_heartbeat("slave_1", "vps_1", new_ts, 0, "Active", "")
    await db.purge_old_heartbeats(max_age_days=0)  # purge everything older than now
    rows = await db.fetch_all("SELECT * FROM heartbeats")
    assert len(rows) <= 1
```

**Step 2: Run to verify fail, implement, run to verify pass**

Add `get_active_links`, `insert_heartbeat`, `purge_old_heartbeats`, `purge_old_messages` to DatabaseManager.

**Step 3: Commit**

```bash
git add hub/db/manager.py tests/test_db_manager.py
git commit -m "feat: DB manager - links query, heartbeats, data retention"
```

---

## Phase 2: Protocol & Message Models

### Task 6: Message dataclasses

**Files:**
- Create: `hub/protocol/models.py`
- Create: `tests/test_models.py`

**Step 1: Write failing tests**

```python
# tests/test_models.py
from hub.protocol.models import MasterMessage, SlaveCommand, AckMessage, MessageType

def test_master_message_open():
    msg = MasterMessage(
        msg_id=1, master_id="master_1", type=MessageType.OPEN, ts_ms=1700000000000,
        payload={"ticket": 123, "symbol": "EURUSD", "direction": "BUY", "volume": 0.1,
                 "price": 1.085, "sl": 1.082, "tp": 1.089, "magic": 15010301, "comment": "S01"}
    )
    assert msg.msg_id == 1
    assert msg.type == MessageType.OPEN

def test_slave_command_has_slave_fields():
    cmd = SlaveCommand(
        msg_id=1, master_id="master_1", slave_id="slave_1", type=MessageType.OPEN, ts_ms=1700000000000,
        payload={"master_ticket": 123, "symbol": "EURUSD.s", "direction": "BUY", "volume": 0.2,
                 "price": 1.085, "sl": 1.082, "tp": 1.089, "magic": 15010305, "comment": "Copy:master_1:123"}
    )
    assert cmd.slave_id == "slave_1"

def test_ack_message():
    ack = AckMessage(msg_id=1, slave_id="slave_1", ack_type="ACK", slave_ticket=87654321, ts_ms=1700000000500)
    assert ack.ack_type == "ACK"

def test_nack_message():
    nack = AckMessage(msg_id=1, slave_id="slave_1", ack_type="NACK", reason="SYMBOL_NOT_FOUND", ts_ms=1700000000500)
    assert nack.reason == "SYMBOL_NOT_FOUND"
    assert nack.slave_ticket is None
```

**Step 2: Implement models**

```python
# hub/protocol/models.py
from dataclasses import dataclass, field
from enum import StrEnum

class MessageType(StrEnum):
    OPEN = "OPEN"
    MODIFY = "MODIFY"
    CLOSE = "CLOSE"
    CLOSE_PARTIAL = "CLOSE_PARTIAL"
    HEARTBEAT = "HEARTBEAT"
    REGISTER = "REGISTER"

@dataclass
class MasterMessage:
    msg_id: int
    master_id: str
    type: MessageType
    ts_ms: int
    payload: dict

@dataclass
class SlaveCommand:
    msg_id: int
    master_id: str
    slave_id: str
    type: MessageType
    ts_ms: int
    payload: dict

@dataclass
class AckMessage:
    msg_id: int
    slave_id: str
    ack_type: str  # "ACK" or "NACK"
    ts_ms: int
    slave_ticket: int | None = None
    reason: str | None = None
```

**Step 3: Run tests, commit**

Run: `cd c:\Tino-V && python -m pytest tests/test_models.py -v`

```bash
git add hub/protocol/models.py tests/test_models.py
git commit -m "feat: protocol message dataclasses"
```

---

### Task 7: JSON serializer (encode/decode)

**Files:**
- Create: `hub/protocol/serializer.py`
- Create: `tests/test_serializer.py`

**Step 1: Write failing tests**

```python
# tests/test_serializer.py
import json
from hub.protocol.serializer import encode_master_message, decode_master_message, encode_slave_command, decode_ack
from hub.protocol.models import MasterMessage, SlaveCommand, AckMessage, MessageType

def test_encode_decode_master_message_roundtrip():
    msg = MasterMessage(msg_id=1, master_id="master_1", type=MessageType.OPEN, ts_ms=1700000000000,
                        payload={"ticket": 123, "symbol": "EURUSD"})
    encoded = encode_master_message(msg)
    assert isinstance(encoded, str)
    assert encoded.endswith("\n")
    decoded = decode_master_message(encoded)
    assert decoded.msg_id == 1
    assert decoded.payload["ticket"] == 123

def test_encode_slave_command():
    cmd = SlaveCommand(msg_id=1, master_id="m1", slave_id="s1", type=MessageType.OPEN, ts_ms=170,
                       payload={"master_ticket": 123, "symbol": "EURUSD.s"})
    encoded = encode_slave_command(cmd)
    data = json.loads(encoded.strip())
    assert data["slave_id"] == "s1"

def test_decode_ack():
    raw = '{"msg_id": 1, "slave_id": "s1", "ack_type": "ACK", "slave_ticket": 999, "ts_ms": 170}\n'
    ack = decode_ack(raw)
    assert ack.slave_ticket == 999

def test_decode_nack():
    raw = '{"msg_id": 1, "slave_id": "s1", "ack_type": "NACK", "reason": "SYMBOL_NOT_FOUND", "ts_ms": 170}\n'
    ack = decode_ack(raw)
    assert ack.ack_type == "NACK"
    assert ack.reason == "SYMBOL_NOT_FOUND"
```

**Step 2: Implement serializer**

Implement `encode_master_message`, `decode_master_message`, `encode_slave_command`, `decode_ack` using `json.dumps`/`json.loads` with newline termination.

**Step 3: Run tests, commit**

```bash
git add hub/protocol/serializer.py tests/test_serializer.py
git commit -m "feat: JSON serializer encode/decode with newline delimiter"
```

---

## Phase 3: Mapping Logic

### Task 8: Magic number mapping

**Files:**
- Create: `hub/mapping/magic.py`
- Create: `tests/test_magic.py`

**Step 1: Write failing tests**

```python
# tests/test_magic.py
from hub.mapping.magic import parse_master_magic, compute_slave_magic

def test_parse_master_magic():
    parts = parse_master_magic(15010301)
    assert parts == {"prefix": 15, "pair_id": 1, "direction_block": 3, "setup_id": 1}

def test_parse_master_magic_large():
    parts = parse_master_magic(15990905)
    assert parts == {"prefix": 15, "pair_id": 99, "direction_block": 9, "setup_id": 5}

def test_compute_slave_magic():
    result = compute_slave_magic(15010301, slave_setup_id=5)
    assert result == 15010305

def test_compute_slave_magic_same_setup():
    result = compute_slave_magic(15010301, slave_setup_id=1)
    assert result == 15010301

def test_compute_slave_magic_setup_99():
    result = compute_slave_magic(15010301, slave_setup_id=99)
    assert result == 15010399
```

**Step 2: Implement**

```python
# hub/mapping/magic.py
def parse_master_magic(magic: int) -> dict:
    s = str(magic)
    return {
        "prefix": int(s[0:2]),
        "pair_id": int(s[2:4]),
        "direction_block": int(s[4:6]),
        "setup_id": int(s[6:8]),
    }

def compute_slave_magic(master_magic: int, slave_setup_id: int) -> int:
    return master_magic - (master_magic % 100) + slave_setup_id
```

**Step 3: Run tests, commit**

```bash
git add hub/mapping/magic.py tests/test_magic.py
git commit -m "feat: magic number parse and slave mapping"
```

---

### Task 9: Symbol mapping resolver

**Files:**
- Create: `hub/mapping/symbol.py`
- Create: `tests/test_symbol.py`

**Step 1: Write failing tests**

```python
# tests/test_symbol.py
from hub.mapping.symbol import resolve_symbol

def test_suffix_mapping():
    result = resolve_symbol("EURUSD", suffix=".s", explicit_mappings={})
    assert result == "EURUSD.s"

def test_explicit_mapping_overrides_suffix():
    result = resolve_symbol("XAUUSD", suffix=".s", explicit_mappings={"XAUUSD": "GOLD.s"})
    assert result == "GOLD.s"

def test_empty_suffix():
    result = resolve_symbol("EURUSD", suffix="", explicit_mappings={})
    assert result == "EURUSD"

def test_suffix_with_underscore():
    result = resolve_symbol("GBPUSD", suffix="_demo", explicit_mappings={})
    assert result == "GBPUSD_demo"

def test_explicit_mapping_not_matching_falls_to_suffix():
    result = resolve_symbol("EURUSD", suffix=".f", explicit_mappings={"XAUUSD": "GOLD.f"})
    assert result == "EURUSD.f"
```

**Step 2: Implement**

```python
# hub/mapping/symbol.py
def resolve_symbol(master_symbol: str, suffix: str, explicit_mappings: dict[str, str]) -> str:
    if master_symbol in explicit_mappings:
        return explicit_mappings[master_symbol]
    return master_symbol + suffix
```

**Step 3: Run tests, commit**

```bash
git add hub/mapping/symbol.py tests/test_symbol.py
git commit -m "feat: symbol resolver with explicit mapping + suffix"
```

---

### Task 10: Lot size calculator

**Files:**
- Create: `hub/mapping/lot.py`
- Create: `tests/test_lot.py`

**Step 1: Write failing tests**

```python
# tests/test_lot.py
from hub.mapping.lot import compute_slave_volume, compute_partial_close_volume

def test_multiplier_mode():
    assert compute_slave_volume(0.1, "multiplier", 2.0) == 0.2

def test_fixed_mode():
    assert compute_slave_volume(0.1, "fixed", 0.05) == 0.05

def test_multiplier_mode_large():
    assert compute_slave_volume(1.0, "multiplier", 0.5) == 0.5

def test_partial_close_multiplier():
    vol = compute_partial_close_volume(
        master_close_volume=0.05, lot_mode="multiplier", lot_value=2.0,
        master_open_volume=0.1, slave_open_volume=0.2)
    assert vol == 0.1  # 0.05 * 2.0

def test_partial_close_fixed():
    vol = compute_partial_close_volume(
        master_close_volume=0.05, lot_mode="fixed", lot_value=0.1,
        master_open_volume=0.1, slave_open_volume=0.1)
    assert vol == 0.05  # (0.05/0.1) * 0.1
```

**Step 2: Implement**

```python
# hub/mapping/lot.py
def compute_slave_volume(master_volume: float, lot_mode: str, lot_value: float) -> float:
    if lot_mode == "multiplier":
        return master_volume * lot_value
    return lot_value  # fixed

def compute_partial_close_volume(master_close_volume: float, lot_mode: str, lot_value: float,
                                  master_open_volume: float, slave_open_volume: float) -> float:
    if lot_mode == "multiplier":
        return master_close_volume * lot_value
    ratio = master_close_volume / master_open_volume
    return ratio * slave_open_volume
```

**Step 3: Run tests, commit**

```bash
git add hub/mapping/lot.py tests/test_lot.py
git commit -m "feat: lot size calculator (multiplier + fixed + partial close)"
```

---

## Phase 4: Configuration

### Task 11: Config loader

**Files:**
- Create: `hub/config.py`
- Create: `config/config.example.json`
- Create: `tests/test_config.py` (minimal)

**Step 1: Write config.example.json**

```json
{
  "db_path": "C:\\TradeCopier\\data\\copier.db",
  "vps_id": "vps_1",
  "heartbeat_interval_sec": 10,
  "heartbeat_timeout_sec": 30,
  "ack_timeout_sec": 5,
  "ack_max_retries": 3,
  "resend_window_size": 200,
  "alert_dedup_minutes": 5,
  "telegram": {
    "enabled": true,
    "bot_token": "YOUR_BOT_TOKEN",
    "chat_id": "YOUR_CHAT_ID"
  },
  "email": {
    "enabled": false,
    "smtp_host": "",
    "smtp_port": 587,
    "username": "",
    "password": "",
    "from_addr": "",
    "to_addr": ""
  },
  "backup": {
    "enabled": true,
    "dir": "C:\\TradeCopier\\backups",
    "retention_days": 7
  }
}
```

**Step 2: Write config.py**

```python
# hub/config.py
import json
from dataclasses import dataclass
from pathlib import Path

@dataclass
class TelegramConfig:
    enabled: bool
    bot_token: str
    chat_id: str

@dataclass
class Config:
    db_path: str
    vps_id: str
    heartbeat_interval_sec: int
    heartbeat_timeout_sec: int
    ack_timeout_sec: int
    ack_max_retries: int
    resend_window_size: int
    alert_dedup_minutes: int
    telegram: TelegramConfig

    @classmethod
    def load(cls, path: str | Path) -> "Config":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            db_path=data["db_path"],
            vps_id=data["vps_id"],
            heartbeat_interval_sec=data.get("heartbeat_interval_sec", 10),
            heartbeat_timeout_sec=data.get("heartbeat_timeout_sec", 30),
            ack_timeout_sec=data.get("ack_timeout_sec", 5),
            ack_max_retries=data.get("ack_max_retries", 3),
            resend_window_size=data.get("resend_window_size", 200),
            alert_dedup_minutes=data.get("alert_dedup_minutes", 5),
            telegram=TelegramConfig(
                enabled=data.get("telegram", {}).get("enabled", False),
                bot_token=data.get("telegram", {}).get("bot_token", ""),
                chat_id=data.get("telegram", {}).get("chat_id", ""),
            ),
        )
```

**Step 3: Write test, run, commit**

```bash
git add hub/config.py config/config.example.json tests/test_config.py
git commit -m "feat: config loader with example config"
```

---

## Phase 5: Named Pipe Transport

### Task 12: Named pipe server (asyncio)

**Files:**
- Create: `hub/transport/pipe_server.py`
- Create: `tests/test_pipe_server.py`

**Step 1: Write failing tests**

Test that `PipeServer` can:
- Create a named pipe and accept a connection
- Read a newline-delimited JSON message
- Write a response back

Use `asyncio` and `win32pipe`/`win32file` for the test client side.

**Step 2: Implement PipeServer**

```python
# hub/transport/pipe_server.py
import asyncio
import logging
from collections.abc import Callable, Awaitable
import win32pipe
import win32file
import pywintypes

logger = logging.getLogger(__name__)

PIPE_BUFFER_SIZE = 4096

class PipeServer:
    """Async named pipe server. Creates a pipe, waits for client, reads newline-delimited messages."""

    def __init__(self, pipe_name: str, on_message: Callable[[str], Awaitable[str | None]]):
        self._pipe_name = f"\\\\.\\pipe\\{pipe_name}"
        self._on_message = on_message
        self._running = False
        self._handle = None

    async def start(self):
        self._running = True
        while self._running:
            try:
                await self._accept_and_serve()
            except Exception as e:
                logger.error(f"Pipe {self._pipe_name} error: {e}")
                await asyncio.sleep(1)

    async def _accept_and_serve(self):
        loop = asyncio.get_event_loop()
        self._handle = await loop.run_in_executor(None, self._create_and_connect)
        if not self._handle:
            return
        try:
            buffer = ""
            while self._running:
                data = await loop.run_in_executor(None, self._read)
                if data is None:
                    break
                buffer += data
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        response = await self._on_message(line)
                        if response:
                            await loop.run_in_executor(None, self._write, response)
        finally:
            win32file.CloseHandle(self._handle)
            self._handle = None

    def _create_and_connect(self):
        handle = win32pipe.CreateNamedPipe(
            self._pipe_name,
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
            win32pipe.PIPE_UNLIMITED_INSTANCES,
            PIPE_BUFFER_SIZE, PIPE_BUFFER_SIZE, 0, None,
        )
        win32pipe.ConnectNamedPipe(handle, None)
        return handle

    def _read(self) -> str | None:
        try:
            hr, data = win32file.ReadFile(self._handle, PIPE_BUFFER_SIZE)
            return data.decode("utf-8")
        except pywintypes.error:
            return None

    def _write(self, data: str):
        try:
            win32file.WriteFile(self._handle, data.encode("utf-8"))
        except pywintypes.error:
            pass

    def stop(self):
        self._running = False
```

**Step 3: Run tests, commit**

```bash
git add hub/transport/pipe_server.py tests/test_pipe_server.py
git commit -m "feat: async named pipe server for Windows"
```

---

## Phase 6: Router (Core Business Logic)

### Task 13: Message router

**Files:**
- Create: `hub/router/router.py`
- Create: `tests/test_router.py`

**Step 1: Write failing tests**

Test the Router class which:
- Receives a `MasterMessage`
- Looks up active links from DB
- Resolves symbol (suffix + explicit)
- Computes slave magic
- Computes slave volume
- Returns list of `SlaveCommand` objects

```python
# tests/test_router.py
import pytest
from hub.router.router import Router
from hub.db.manager import DatabaseManager
from hub.protocol.models import MasterMessage, MessageType

@pytest.fixture
async def router():
    db = DatabaseManager(":memory:")
    await db.initialize()
    # Setup test data
    await db.register_terminal("master_1", "master", 111, "B1")
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.execute(
        "INSERT INTO master_slave_links (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at) "
        "VALUES ('master_1', 'slave_1', 1, 'multiplier', 2.0, '.s', 0)"
    )
    await db.execute(
        "INSERT INTO magic_mappings (link_id, master_setup_id, slave_setup_id) VALUES (1, 1, 5)"
    )
    r = Router(db)
    yield r
    await db.close()

@pytest.mark.asyncio
async def test_route_open_message(router):
    msg = MasterMessage(msg_id=1, master_id="master_1", type=MessageType.OPEN, ts_ms=170,
                        payload={"ticket": 123, "symbol": "EURUSD", "direction": "BUY",
                                 "volume": 0.1, "price": 1.085, "sl": 1.082, "tp": 1.089,
                                 "magic": 15010301, "comment": "S01"})
    commands = await router.route(msg)
    assert len(commands) == 1
    cmd = commands[0]
    assert cmd.slave_id == "slave_1"
    assert cmd.payload["symbol"] == "EURUSD.s"
    assert cmd.payload["volume"] == 0.2
    assert cmd.payload["magic"] == 15010305

@pytest.mark.asyncio
async def test_route_no_active_links(router):
    # Disable the link
    await router._db.execute("UPDATE master_slave_links SET enabled = 0 WHERE id = 1")
    msg = MasterMessage(msg_id=1, master_id="master_1", type=MessageType.OPEN, ts_ms=170,
                        payload={"ticket": 123, "symbol": "EURUSD", "direction": "BUY",
                                 "volume": 0.1, "price": 1.085, "sl": 1.082, "tp": 1.089,
                                 "magic": 15010301, "comment": "S01"})
    commands = await router.route(msg)
    assert len(commands) == 0
```

**Step 2: Implement Router**

```python
# hub/router/router.py
from hub.db.manager import DatabaseManager
from hub.protocol.models import MasterMessage, SlaveCommand, MessageType
from hub.mapping.magic import compute_slave_magic, parse_master_magic
from hub.mapping.symbol import resolve_symbol
from hub.mapping.lot import compute_slave_volume

class Router:
    def __init__(self, db: DatabaseManager):
        self._db = db

    async def route(self, msg: MasterMessage) -> list[SlaveCommand]:
        links = await self._db.get_active_links(msg.master_id)
        commands = []
        for link in links:
            cmd = await self._build_slave_command(msg, link)
            if cmd:
                commands.append(cmd)
        return commands

    async def _build_slave_command(self, msg: MasterMessage, link: dict) -> SlaveCommand | None:
        # Resolve symbol
        explicit_mappings = await self._get_explicit_mappings(link["id"])
        slave_symbol = resolve_symbol(msg.payload.get("symbol", ""), link["symbol_suffix"], explicit_mappings)

        # Resolve magic
        master_magic = msg.payload.get("magic", 0)
        parsed = parse_master_magic(master_magic)
        magic_map = await self._get_magic_mapping(link["id"], parsed["setup_id"])
        slave_magic = compute_slave_magic(master_magic, magic_map) if magic_map is not None else master_magic

        # Resolve volume
        slave_volume = compute_slave_volume(msg.payload.get("volume", 0), link["lot_mode"], link["lot_value"])

        # Build payload
        payload = {**msg.payload}
        payload["master_ticket"] = payload.pop("ticket", None)
        payload["symbol"] = slave_symbol
        payload["magic"] = slave_magic
        payload["volume"] = slave_volume
        payload["comment"] = f"Copy:{msg.master_id}:{payload.get('master_ticket', '')}"

        return SlaveCommand(
            msg_id=msg.msg_id, master_id=msg.master_id, slave_id=link["slave_id"],
            type=msg.type, ts_ms=msg.ts_ms, payload=payload,
        )

    async def _get_explicit_mappings(self, link_id: int) -> dict[str, str]:
        rows = await self._db.fetch_all(
            "SELECT master_symbol, slave_symbol FROM symbol_mappings WHERE link_id = ?", (link_id,))
        return {r["master_symbol"]: r["slave_symbol"] for r in rows}

    async def _get_magic_mapping(self, link_id: int, master_setup_id: int) -> int | None:
        row = await self._db.fetch_one(
            "SELECT slave_setup_id FROM magic_mappings WHERE link_id = ? AND master_setup_id = ?",
            (link_id, master_setup_id))
        return row["slave_setup_id"] if row else None
```

**Step 3: Run tests, commit**

```bash
git add hub/router/router.py tests/test_router.py
git commit -m "feat: message router with symbol/magic/lot resolution"
```

---

### Task 14: Resend window & idempotency

**Files:**
- Modify: `hub/router/router.py`
- Modify: `tests/test_router.py`

**Step 1: Write failing tests for resend window**

Test that:
- Router maintains last N=200 messages per master_id in memory
- Duplicate msg_id is detected and skipped
- Messages beyond window are dropped from memory (still in DB)

**Step 2: Implement ResendWindow class inside router.py**

**Step 3: Run tests, commit**

```bash
git add hub/router/router.py tests/test_router.py
git commit -m "feat: resend window (N=200) and idempotency check"
```

---

## Phase 7: Monitoring & Alerts

### Task 15: Health check engine

**Files:**
- Create: `hub/monitor/health.py`
- Create: `tests/test_health.py`

**Step 1: Write failing tests**

```python
# tests/test_health.py
import time
import pytest
from hub.monitor.health import HealthChecker
from hub.db.manager import DatabaseManager

@pytest.fixture
async def checker():
    db = DatabaseManager(":memory:")
    await db.initialize()
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.update_terminal_status("slave_1", "Active")
    hc = HealthChecker(db, heartbeat_timeout_sec=30)
    yield hc
    await db.close()

@pytest.mark.asyncio
async def test_detect_heartbeat_timeout(checker):
    # Set last_heartbeat to 60 seconds ago
    old_ts = int(time.time() * 1000) - 60_000
    await checker._db.execute("UPDATE terminals SET last_heartbeat = ? WHERE terminal_id = 'slave_1'", (old_ts,))
    alerts = await checker.run_checks()
    types = [a["alert_type"] for a in alerts]
    assert "heartbeat_miss" in types

@pytest.mark.asyncio
async def test_no_alert_when_healthy(checker):
    now_ts = int(time.time() * 1000)
    await checker._db.execute("UPDATE terminals SET last_heartbeat = ? WHERE terminal_id = 'slave_1'", (now_ts,))
    alerts = await checker.run_checks()
    assert len(alerts) == 0
```

**Step 2: Implement HealthChecker**

Implement 5 health checks from architecture doc:
1. Heartbeat timeout (>30s)
2. ACK timeout (>15s)
3. Consecutive NACKs (>5)
4. Message queue depth (>50)
5. DB file size (>500 MB)

**Step 3: Run tests, commit**

```bash
git add hub/monitor/health.py tests/test_health.py
git commit -m "feat: health checker with 5 checks"
```

---

### Task 16: Alert sender (Telegram)

**Files:**
- Create: `hub/monitor/alerts.py`
- Create: `tests/test_alerts.py`

**Step 1: Write failing tests**

Test AlertSender:
- Sends Telegram message (mocked HTTP)
- Respects deduplication (same alert_type + terminal_id within 5 min → skip)
- Records to alerts_history table

**Step 2: Implement AlertSender with Telegram bot API (HTTP POST)**

Use `urllib.request` to avoid extra dependencies, or `python-telegram-bot`.

**Step 3: Run tests, commit**

```bash
git add hub/monitor/alerts.py tests/test_alerts.py
git commit -m "feat: alert sender (Telegram) with deduplication"
```

---

## Phase 8: Hub Service Main

### Task 17: Hub Service entry point

**Files:**
- Create: `hub/main.py`

**Step 1: Implement main.py**

```python
# hub/main.py
import asyncio
import logging
import sys
from hub.config import Config
from hub.db.manager import DatabaseManager
from hub.router.router import Router
from hub.transport.pipe_server import PipeServer
from hub.monitor.health import HealthChecker
from hub.monitor.alerts import AlertSender

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("hub")

class HubService:
    def __init__(self, config_path: str):
        self.config = Config.load(config_path)
        self.db = DatabaseManager(self.config.db_path)
        self.router = Router(self.db)
        self.alert_sender = AlertSender(self.db, self.config)
        self.health_checker = HealthChecker(self.db, self.config.heartbeat_timeout_sec)
        self._master_pipes: dict[str, PipeServer] = {}
        self._slave_cmd_pipes: dict[str, PipeServer] = {}
        self._slave_ack_pipes: dict[str, PipeServer] = {}

    async def start(self):
        await self.db.initialize()
        logger.info("Hub Service started")
        # Start health check loop
        asyncio.create_task(self._health_loop())
        # Start pipe listeners (dynamic based on DB terminals)
        await self._run_forever()

    async def _health_loop(self):
        while True:
            alerts = await self.health_checker.run_checks()
            for alert in alerts:
                await self.alert_sender.send(alert)
            await asyncio.sleep(10)

    async def _run_forever(self):
        # Main event loop — pipe servers are added dynamically as terminals register
        while True:
            await asyncio.sleep(1)

def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/config.json"
    hub = HubService(config_path)
    asyncio.run(hub.start())

if __name__ == "__main__":
    main()
```

**Step 2: Test that it starts without crash (smoke test)**

Run: `cd c:\Tino-V && python -c "from hub.main import HubService; print('import OK')"`

**Step 3: Commit**

```bash
git add hub/main.py
git commit -m "feat: Hub Service entry point with asyncio event loop"
```

---

## Phase 9: MQL5 Expert Advisors

### Task 18: Shared MQL5 includes

**Files:**
- Create: `ea/Include/CopierPipe.mqh` — Named pipe client for MQL5
- Create: `ea/Include/CopierProtocol.mqh` — JSON builder/parser (minimal, no external libs)
- Create: `ea/Include/CopierLogger.mqh` — File logging

**Step 1: Implement CopierPipe.mqh**

Windows named pipe client using `kernel32.dll` imports:
- `CreateFileW` to connect to pipe
- `WriteFile` to send messages
- `ReadFile` to receive (non-blocking with peek)
- Auto-reconnect on broken pipe

**Step 2: Implement CopierProtocol.mqh**

JSON builder using string concatenation (MQL5 has no JSON library):
- `BuildOpenMessage(msg_id, master_id, ticket, symbol, direction, volume, price, sl, tp, magic, comment)`
- `BuildModifyMessage(msg_id, master_id, ticket, magic, sl, tp)`
- `BuildCloseMessage(msg_id, master_id, ticket, magic)`
- `BuildClosePartialMessage(msg_id, master_id, ticket, magic, volume)`
- `BuildHeartbeatMessage(terminal_id, vps_id, account, broker, status_code, status_msg)`
- `BuildRegisterMessage(terminal_id, role, account, broker)`
- `ParseSlaveCommand(json_str)` — extract fields from Hub's command

**Step 3: Implement CopierLogger.mqh**

Simple file-based logger to `MQL5/Files/CopierLogs/`.

**Step 4: Commit**

```bash
git add ea/Include/
git commit -m "feat: MQL5 shared includes (pipe client, protocol, logger)"
```

---

### Task 19: Master EA

**Files:**
- Create: `ea/Master/TradeCopierMaster.mq5`

**Step 1: Implement Master EA**

Input parameters:
```mql5
input string TerminalID = "master_1";       // Unique terminal ID
input string VpsID      = "vps_1";          // VPS identifier
input string PipeName   = "copier_master_1"; // Named pipe name
input int    HeartbeatSec = 10;             // Heartbeat interval
```

Core logic:
- `OnInit()`: Connect pipe, send REGISTER message, set EventSetMillisecondTimer(100)
- `OnTrade()`: Detect new/modified/closed positions, build message, send to Hub
- `OnTimer()`: Poll pipe for responses, send heartbeat every N seconds
- `OnDeinit()`: Close pipe, log shutdown

Trade detection logic:
- Maintain local array of tracked positions (by magic number pattern `15XXXXXX`)
- On each `OnTrade()` call, compare current positions vs tracked:
  - New position found → OPEN message
  - Position SL/TP changed → MODIFY message
  - Position disappeared → CLOSE message
  - Position volume decreased → CLOSE_PARTIAL message
- msg_id counter: stored in global variable, strictly increasing

**Step 2: Commit**

```bash
git add ea/Master/TradeCopierMaster.mq5
git commit -m "feat: Master EA with trade detection and pipe communication"
```

---

### Task 20: Slave EA

**Files:**
- Create: `ea/Slave/TradeCopierSlave.mq5`

**Step 1: Implement Slave EA**

Input parameters:
```mql5
input string TerminalID    = "slave_1";
input string VpsID         = "vps_1";
input string CmdPipeName   = "copier_slave_1_cmd";   // Commands from Hub
input string AckPipeName   = "copier_slave_1_ack";   // ACKs back to Hub
input int    HeartbeatSec  = 10;
input int    MaxSlippage   = 10;  // points
```

Core logic:
- `OnInit()`: Connect both pipes (cmd + ack), send REGISTER, set timer
- `OnTimer()`: Poll cmd pipe for commands, execute, send ACK/NACK via ack pipe, send heartbeat
- Command execution via `CTrade`:
  - OPEN: `trade.PositionOpen(symbol, type, volume, price, sl, tp, comment)`
  - MODIFY: `trade.PositionModify(ticket, sl, tp)`
  - CLOSE: `trade.PositionClose(ticket)`
  - CLOSE_PARTIAL: `trade.PositionClosePartial(ticket, volume)`
- Idempotency: track `last_processed_msg_id` per master — skip if already seen
- Symbol validation: check `SymbolInfoInteger(symbol, SYMBOL_EXIST)` before execution
- Volume normalization: round to `SYMBOL_VOLUME_STEP`, check `SYMBOL_VOLUME_MIN`

**Step 2: Commit**

```bash
git add ea/Slave/TradeCopierSlave.mq5
git commit -m "feat: Slave EA with CTrade execution and ACK/NACK"
```

---

## Phase 10: Integration Testing

### Task 21: Python pipe integration test (simulated EAs)

**Files:**
- Create: `tests/test_integration.py`

**Step 1: Write integration test**

Simulate Master and Slave as Python pipe clients:
1. Start Hub Service (in-process, with in-memory DB)
2. Connect "Master" pipe client → send REGISTER → send OPEN message
3. Verify Hub routes to "Slave" pipe
4. Connect "Slave" pipe client → receive command → send ACK
5. Verify trade_mapping created in DB with status "open"

Test scenarios:
- Full OPEN flow
- MODIFY flow
- CLOSE flow
- CLOSE_PARTIAL flow
- Reconnect (kill slave client, reconnect, receive replayed messages)
- Idempotency (send same msg_id twice)
- Multi-master (two master clients sending to same slave)

**Step 2: Run integration tests**

Run: `cd c:\Tino-V && python -m pytest tests/test_integration.py -v`

**Step 3: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: integration tests with simulated Master/Slave pipes"
```

---

## Phase 11: Deployment & Utilities

### Task 22: Backup script

**Files:**
- Create: `scripts/backup_db.py`

**Step 1: Implement backup script**

```python
# scripts/backup_db.py
import sqlite3, shutil, sys
from pathlib import Path
from datetime import datetime, timedelta

def backup(db_path: str, backup_dir: str, retention_days: int = 7):
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    # Checkpoint WAL
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    # Copy
    date_str = datetime.utcnow().strftime("%Y%m%d")
    dest = backup_dir / f"copier_{date_str}.db"
    shutil.copy2(db_path, dest)
    # Purge old
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    for f in backup_dir.glob("copier_*.db"):
        date_part = f.stem.split("_")[1]
        try:
            file_date = datetime.strptime(date_part, "%Y%m%d")
            if file_date < cutoff:
                f.unlink()
        except ValueError:
            pass

if __name__ == "__main__":
    backup(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 7)
```

**Step 2: Commit**

```bash
git add scripts/backup_db.py
git commit -m "feat: database backup script with retention"
```

---

### Task 23: NSSM service setup documentation

**Files:**
- Create: `docs/runbook.md`

**Step 1: Write runbook**

Document:
- Prerequisites (Python 3.11+, NSSM)
- Installation steps
- `nssm install TradeCopierHub` command
- Config file setup
- EA installation in MT5 terminals
- How to verify health (check DB, check heartbeats)
- Troubleshooting guide (pipe errors, DB locked, no heartbeat)
- How to add new Master/Slave terminals
- How to configure symbol mappings and magic mappings

**Step 2: Commit**

```bash
git add docs/runbook.md
git commit -m "docs: deployment runbook and troubleshooting guide"
```

---

## Phase 12: FastAPI Backend

### Task 25: FastAPI project setup & DB connection

**Files:**
- Create: `web/api/__init__.py`
- Create: `web/api/main.py`
- Create: `web/api/database.py`
- Create: `web/api/schemas.py`
- Create: `web/api/routers/__init__.py`

**Step 1: Write database.py**

```python
# web/api/database.py
import aiosqlite
from contextlib import asynccontextmanager

DB_PATH: str = ""

def set_db_path(path: str):
    global DB_PATH
    DB_PATH = path

@asynccontextmanager
async def get_db():
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode = WAL")
    await conn.execute("PRAGMA busy_timeout = 5000")
    await conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        await conn.close()
```

**Step 2: Write schemas.py (Pydantic models)**

```python
# web/api/schemas.py
from pydantic import BaseModel

class TerminalOut(BaseModel):
    terminal_id: str
    role: str
    account_number: int | None
    broker_server: str | None
    status: str
    status_message: str
    last_heartbeat: int

class LinkOut(BaseModel):
    id: int
    master_id: str
    slave_id: str
    enabled: int
    lot_mode: str
    lot_value: float
    symbol_suffix: str
    created_at: int

class LinkCreate(BaseModel):
    master_id: str
    slave_id: str
    lot_mode: str = "multiplier"
    lot_value: float = 1.0
    symbol_suffix: str = ""

class LinkUpdate(BaseModel):
    enabled: int | None = None
    lot_mode: str | None = None
    lot_value: float | None = None
    symbol_suffix: str | None = None

class SymbolMappingOut(BaseModel):
    id: int
    link_id: int
    master_symbol: str
    slave_symbol: str

class SymbolMappingCreate(BaseModel):
    master_symbol: str
    slave_symbol: str

class MagicMappingOut(BaseModel):
    id: int
    link_id: int
    master_setup_id: int
    slave_setup_id: int

class MagicMappingCreate(BaseModel):
    master_setup_id: int
    slave_setup_id: int
```

**Step 3: Write main.py with CORS**

```python
# web/api/main.py
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from web.api.database import set_db_path
from web.api.routers import terminals, links, symbol_mappings, magic_mappings

app = FastAPI(title="Trade Copier API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(terminals.router, prefix="/api")
app.include_router(links.router, prefix="/api")
app.include_router(symbol_mappings.router, prefix="/api")
app.include_router(magic_mappings.router, prefix="/api")

# Set DB path from config or env
import os
set_db_path(os.environ.get("COPIER_DB_PATH", "C:\\TradeCopier\\data\\copier.db"))
```

**Step 4: Verify import**

Run: `cd c:\Tino-V && python -c "from web.api.main import app; print('FastAPI OK')"`

**Step 5: Commit**

```bash
git add web/api/
git commit -m "feat: FastAPI project setup with DB connection and schemas"
```

---

### Task 26: Terminals router (GET)

**Files:**
- Create: `web/api/routers/terminals.py`
- Create: `tests/test_api_terminals.py`

**Step 1: Write failing tests**

```python
# tests/test_api_terminals.py
import pytest
from httpx import AsyncClient, ASGITransport
from web.api.main import app
from web.api.database import set_db_path
import aiosqlite, tempfile, os
from pathlib import Path

SCHEMA_PATH = Path("hub/db/schema.sql")

@pytest.fixture
async def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    set_db_path(db_path)
    conn = await aiosqlite.connect(db_path)
    await conn.executescript(SCHEMA_PATH.read_text())
    await conn.execute(
        "INSERT INTO terminals VALUES ('master_1','master',12345,'Broker','Active','',0,0)")
    await conn.execute(
        "INSERT INTO terminals VALUES ('slave_1','slave',67890,'Broker','Connected','',0,0)")
    await conn.commit()
    await conn.close()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_get_terminals(client):
    resp = await client.get("/api/terminals")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["terminal_id"] in ("master_1", "slave_1")

@pytest.mark.asyncio
async def test_get_terminal_by_id(client):
    resp = await client.get("/api/terminals/master_1")
    assert resp.status_code == 200
    assert resp.json()["role"] == "master"

@pytest.mark.asyncio
async def test_get_terminal_not_found(client):
    resp = await client.get("/api/terminals/unknown")
    assert resp.status_code == 404
```

**Step 2: Implement terminals router**

```python
# web/api/routers/terminals.py
from fastapi import APIRouter, HTTPException
from web.api.database import get_db
from web.api.schemas import TerminalOut

router = APIRouter(tags=["terminals"])

@router.get("/terminals", response_model=list[TerminalOut])
async def list_terminals():
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM terminals ORDER BY role, terminal_id")
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

@router.get("/terminals/{terminal_id}", response_model=TerminalOut)
async def get_terminal(terminal_id: str):
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM terminals WHERE terminal_id = ?", (terminal_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(404, "Terminal not found")
        return dict(row)
```

**Step 3: Run tests, commit**

Run: `cd c:\Tino-V && python -m pytest tests/test_api_terminals.py -v`

```bash
git add web/api/routers/terminals.py tests/test_api_terminals.py
git commit -m "feat: GET /api/terminals endpoint"
```

---

### Task 27: Links router (CRUD)

**Files:**
- Create: `web/api/routers/links.py`
- Create: `tests/test_api_links.py`

**Step 1: Write failing tests**

Test all CRUD operations:
- `GET /api/links` — list all links
- `GET /api/links?master_id=master_1` — filter by master
- `POST /api/links` — create link (validate roles, unique pair)
- `PUT /api/links/{id}` — update link settings
- `PATCH /api/links/{id}/toggle` — toggle enabled
- `DELETE /api/links/{id}` — delete link (cascade)

**Step 2: Implement links router**

```python
# web/api/routers/links.py
from fastapi import APIRouter, HTTPException, Query
from web.api.database import get_db
from web.api.schemas import LinkOut, LinkCreate, LinkUpdate
import time

router = APIRouter(tags=["links"])

@router.get("/links", response_model=list[LinkOut])
async def list_links(master_id: str | None = Query(None)):
    async with get_db() as db:
        if master_id:
            cursor = await db.execute("SELECT * FROM master_slave_links WHERE master_id = ?", (master_id,))
        else:
            cursor = await db.execute("SELECT * FROM master_slave_links")
        return [dict(r) for r in await cursor.fetchall()]

@router.post("/links", response_model=LinkOut, status_code=201)
async def create_link(body: LinkCreate):
    async with get_db() as db:
        # Validate roles
        master = await (await db.execute("SELECT role FROM terminals WHERE terminal_id = ?", (body.master_id,))).fetchone()
        if not master or master["role"] != "master":
            raise HTTPException(400, "master_id must reference a terminal with role=master")
        slave = await (await db.execute("SELECT role FROM terminals WHERE terminal_id = ?", (body.slave_id,))).fetchone()
        if not slave or slave["role"] != "slave":
            raise HTTPException(400, "slave_id must reference a terminal with role=slave")
        # Check unique
        existing = await (await db.execute(
            "SELECT id FROM master_slave_links WHERE master_id = ? AND slave_id = ?",
            (body.master_id, body.slave_id))).fetchone()
        if existing:
            raise HTTPException(409, "Link with this master-slave pair already exists")
        now = int(time.time() * 1000)
        cursor = await db.execute(
            "INSERT INTO master_slave_links (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at) "
            "VALUES (?, ?, 1, ?, ?, ?, ?)",
            (body.master_id, body.slave_id, body.lot_mode, body.lot_value, body.symbol_suffix, now))
        await db.commit()
        row = await (await db.execute("SELECT * FROM master_slave_links WHERE id = ?", (cursor.lastrowid,))).fetchone()
        return dict(row)

@router.put("/links/{link_id}", response_model=LinkOut)
async def update_link(link_id: int, body: LinkUpdate):
    async with get_db() as db:
        existing = await (await db.execute("SELECT * FROM master_slave_links WHERE id = ?", (link_id,))).fetchone()
        if not existing:
            raise HTTPException(404, "Link not found")
        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if not updates:
            return dict(existing)
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [link_id]
        await db.execute(f"UPDATE master_slave_links SET {set_clause} WHERE id = ?", values)
        await db.commit()
        row = await (await db.execute("SELECT * FROM master_slave_links WHERE id = ?", (link_id,))).fetchone()
        return dict(row)

@router.patch("/links/{link_id}/toggle")
async def toggle_link(link_id: int):
    async with get_db() as db:
        existing = await (await db.execute("SELECT * FROM master_slave_links WHERE id = ?", (link_id,))).fetchone()
        if not existing:
            raise HTTPException(404, "Link not found")
        new_enabled = 0 if existing["enabled"] else 1
        await db.execute("UPDATE master_slave_links SET enabled = ? WHERE id = ?", (new_enabled, link_id))
        await db.commit()
        return {"id": link_id, "enabled": new_enabled}

@router.delete("/links/{link_id}", status_code=204)
async def delete_link(link_id: int):
    async with get_db() as db:
        existing = await (await db.execute("SELECT id FROM master_slave_links WHERE id = ?", (link_id,))).fetchone()
        if not existing:
            raise HTTPException(404, "Link not found")
        await db.execute("DELETE FROM master_slave_links WHERE id = ?", (link_id,))
        await db.commit()
```

**Step 3: Run tests, commit**

```bash
git add web/api/routers/links.py tests/test_api_links.py
git commit -m "feat: CRUD /api/links with validation"
```

---

### Task 28: Symbol & Magic mapping routers

**Files:**
- Create: `web/api/routers/symbol_mappings.py`
- Create: `web/api/routers/magic_mappings.py`
- Create: `tests/test_api_mappings.py`

**Step 1: Write failing tests for both mapping endpoints**

Test:
- `GET /api/links/{id}/symbol-mappings`
- `POST /api/links/{id}/symbol-mappings` (validate unique)
- `DELETE /api/symbol-mappings/{id}`
- Same for magic-mappings

**Step 2: Implement both routers**

Similar pattern to links router — simple CRUD with foreign key validation.

**Step 3: Run tests, commit**

```bash
git add web/api/routers/symbol_mappings.py web/api/routers/magic_mappings.py tests/test_api_mappings.py
git commit -m "feat: symbol and magic mapping CRUD endpoints"
```

---

## Phase 13: Next.js Frontend

### Task 29: Next.js project setup

**Files:**
- Create: `web/frontend/` (via npx create-next-app)

**Step 1: Initialize Next.js with TypeScript + Tailwind**

Run:
```bash
cd c:\Tino-V\web
npx create-next-app@latest frontend --typescript --tailwind --eslint --app --src-dir --no-import-alias
```

**Step 2: Install shadcn/ui**

Run:
```bash
cd c:\Tino-V\web\frontend
npx shadcn@latest init
npx shadcn@latest add table badge switch dialog select input button alert-dialog sonner
```

**Step 3: Create API client and types**

Create `src/lib/api.ts`:
```typescript
const API_BASE = "http://localhost:8000/api";

export async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(error.detail || res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}
```

Create `src/types/index.ts`:
```typescript
export interface Terminal {
  terminal_id: string;
  role: "master" | "slave";
  account_number: number | null;
  broker_server: string | null;
  status: string;
  status_message: string;
  last_heartbeat: number;
}

export interface Link {
  id: number;
  master_id: string;
  slave_id: string;
  enabled: number;
  lot_mode: "multiplier" | "fixed";
  lot_value: number;
  symbol_suffix: string;
  created_at: number;
}

export interface SymbolMapping {
  id: number;
  link_id: number;
  master_symbol: string;
  slave_symbol: string;
}

export interface MagicMapping {
  id: number;
  link_id: number;
  master_setup_id: number;
  slave_setup_id: number;
}
```

**Step 4: Commit**

```bash
git add web/frontend/
git commit -m "feat: Next.js project setup with shadcn/ui and API client"
```

---

### Task 30: Terminals table component (polling)

**Files:**
- Create: `web/frontend/src/hooks/use-terminals.ts`
- Create: `web/frontend/src/components/terminals-table.tsx`
- Create: `web/frontend/src/components/status-badge.tsx`

**Step 1: Implement polling hook**

```typescript
// src/hooks/use-terminals.ts
import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import { Terminal } from "@/types";

export function useTerminals(pollInterval = 5000) {
  const [terminals, setTerminals] = useState<Terminal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const data = await fetchApi<Terminal[]>("/terminals");
        setTerminals(data);
      } finally {
        setLoading(false);
      }
    };
    load();
    const interval = setInterval(load, pollInterval);
    return () => clearInterval(interval);
  }, [pollInterval]);

  return { terminals, loading };
}
```

**Step 2: Implement StatusBadge**

Color mapping: Active=green, Starting/Connected/Syncing=yellow, Paused=gray, Disconnected=orange, Error=red.

**Step 3: Implement TerminalsTable**

shadcn `Table` with columns: Terminal ID, Role, Account, Broker, Status (badge), Last Heartbeat (relative time).

**Step 4: Commit**

```bash
git add web/frontend/src/
git commit -m "feat: terminals table with status badges and polling"
```

---

### Task 31: Links table with CRUD

**Files:**
- Create: `web/frontend/src/hooks/use-links.ts`
- Create: `web/frontend/src/components/links-table.tsx`
- Create: `web/frontend/src/components/add-link-dialog.tsx`
- Create: `web/frontend/src/components/edit-link-dialog.tsx`

**Step 1: Implement useLinks hook**

Fetch, create, update, toggle, delete operations.

**Step 2: Implement LinksTable**

Table with columns: Master, Slave, Lot Mode, Lot Value, Suffix, Enabled (Switch toggle), Actions (Edit/Delete buttons). Row click selects link for mappings panel.

**Step 3: Implement AddLinkDialog**

shadcn Dialog with:
- Select: Master terminal (filtered to role=master)
- Select: Slave terminal (filtered to role=slave)
- Select: lot_mode (multiplier/fixed)
- Input: lot_value
- Input: symbol_suffix

**Step 4: Implement EditLinkDialog**

Same form, pre-filled with existing values.

**Step 5: Commit**

```bash
git add web/frontend/src/
git commit -m "feat: links table with add/edit/toggle/delete"
```

---

### Task 32: Mappings panel (symbol + magic)

**Files:**
- Create: `web/frontend/src/hooks/use-mappings.ts`
- Create: `web/frontend/src/components/mappings-panel.tsx`
- Create: `web/frontend/src/components/add-mapping-dialog.tsx`

**Step 1: Implement useMappings hook**

Fetch symbol and magic mappings for a given link_id. CRUD operations.

**Step 2: Implement MappingsPanel**

Shown when a link row is selected. Two sub-tables:
- Symbol Mappings: master_symbol → slave_symbol, delete button, add button
- Magic Mappings: master_setup_id → slave_setup_id, delete button, add button

**Step 3: Implement AddMappingDialog**

Generic dialog for adding either symbol or magic mapping. Two inputs + submit.

**Step 4: Commit**

```bash
git add web/frontend/src/
git commit -m "feat: mappings panel for symbol and magic mappings"
```

---

### Task 33: Main page assembly

**Files:**
- Modify: `web/frontend/src/app/page.tsx`
- Modify: `web/frontend/src/app/layout.tsx`

**Step 1: Assemble page.tsx**

```typescript
// src/app/page.tsx
"use client";
import { useState } from "react";
import { TerminalsTable } from "@/components/terminals-table";
import { LinksTable } from "@/components/links-table";
import { MappingsPanel } from "@/components/mappings-panel";
import { Toaster } from "@/components/ui/sonner";

export default function Home() {
  const [selectedLinkId, setSelectedLinkId] = useState<number | null>(null);

  return (
    <main className="container mx-auto py-8 space-y-8">
      <h1 className="text-2xl font-bold">Trade Copier — Terminal Management</h1>
      <TerminalsTable />
      <LinksTable onSelectLink={setSelectedLinkId} />
      {selectedLinkId && <MappingsPanel linkId={selectedLinkId} />}
      <Toaster />
    </main>
  );
}
```

**Step 2: Verify in browser**

Run FastAPI: `cd c:\Tino-V && uvicorn web.api.main:app --host 127.0.0.1 --port 8000`
Run Next.js: `cd c:\Tino-V\web\frontend && npm run dev`
Open: `http://localhost:3000`

**Step 3: Commit**

```bash
git add web/frontend/src/app/
git commit -m "feat: main page assembling all components"
```

---

## Phase 14: Final Validation

### Task 34: Full test suite run

**Step 1: Run all Hub unit tests**

Run: `cd c:\Tino-V && python -m pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 2: Run API tests**

Run: `cd c:\Tino-V && python -m pytest tests/test_api_*.py -v`
Expected: All API tests pass

**Step 3: Run integration tests**

Run: `cd c:\Tino-V && python -m pytest tests/test_integration.py -v`
Expected: All integration tests pass

**Step 4: Verify frontend builds**

Run: `cd c:\Tino-V\web\frontend && npm run build`
Expected: Build succeeds without errors

**Step 5: Verify DB schema**

Run: `cd c:\Tino-V && python -c "import sqlite3; conn = sqlite3.connect(':memory:'); conn.executescript(open('hub/db/schema.sql').read()); print([r[0] for r in conn.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall()])"`
Expected: all 9 table names printed

**Step 6: Final commit**

```bash
git add -A
git commit -m "milestone 2: trade copier hub + web panel complete"
```

---

## Summary: Task Dependency Graph

```
Phase 1: Scaffolding & DB
  Task 1 (init) → Task 2 (DDL) → Task 3 (DB manager init) → Task 4 (DB messages) → Task 5 (DB links)

Phase 2: Protocol
  Task 6 (models) → Task 7 (serializer)

Phase 3: Mapping (parallel to Phase 2)
  Task 8 (magic) ─┐
  Task 9 (symbol) ─┤→ all independent
  Task 10 (lot)  ──┘

Phase 4: Config
  Task 11 (config) ← needed by Phases 5-7

Phase 5: Transport
  Task 12 (pipe server) ← needs Task 11

Phase 6: Router
  Task 13 (router) ← needs Tasks 3-10
  Task 14 (resend) ← needs Task 13

Phase 7: Monitoring
  Task 15 (health) ← needs Task 3
  Task 16 (alerts) ← needs Task 15, Task 11

Phase 8: Hub main
  Task 17 (main.py) ← needs Tasks 12-16

Phase 9: MQL5 EAs (parallel to Python)
  Task 18 (includes) ─┐
  Task 19 (master EA) ─┤← needs Task 18
  Task 20 (slave EA)  ─┘← needs Task 18

Phase 10: Integration
  Task 21 (integration tests) ← needs Tasks 17-20

Phase 11: Deployment
  Task 22 (backup) ← needs Task 2
  Task 23 (runbook) ← needs all

Phase 12: FastAPI Backend (parallel to Phases 9-11, needs Phase 1)
  Task 25 (setup) → Task 26 (terminals GET) → Task 27 (links CRUD) → Task 28 (mappings CRUD)

Phase 13: Next.js Frontend (needs Phase 12)
  Task 29 (setup) → Task 30 (terminals table) → Task 31 (links CRUD UI) → Task 32 (mappings panel) → Task 33 (page assembly)

Phase 14: Validation
  Task 34 (full run) ← needs all
```

**Total: 34 tasks across 14 phases**
