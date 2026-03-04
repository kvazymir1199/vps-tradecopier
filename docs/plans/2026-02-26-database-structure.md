# Trade Copier — Database Structure

## Engine

**SQLite** with WAL (Write-Ahead Logging) mode.

- Single file: `copier.db`
- Single writer: Hub Service (Python) is the only process that writes to the DB
- Concurrency: WAL mode allows concurrent reads while Hub writes
- Location: `C:\TradeCopier\data\copier.db` (configurable in config.json)

## Initialization

```sql
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 5000;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;
```

---

## Tables

### 1. terminals

Stores all registered terminals (both Master and Slave).

```sql
CREATE TABLE terminals (
    terminal_id     TEXT    PRIMARY KEY,
    role            TEXT    NOT NULL CHECK (role IN ('master', 'slave')),
    account_number  INTEGER,
    broker_server   TEXT,
    status          TEXT    NOT NULL DEFAULT 'Starting'
                           CHECK (status IN (
                               'Starting', 'Connected', 'Syncing',
                               'Active', 'Paused', 'Disconnected', 'Error'
                           )),
    status_message  TEXT    DEFAULT '',
    created_at      INTEGER NOT NULL,  -- Unix epoch ms
    last_heartbeat  INTEGER NOT NULL   -- Unix epoch ms
);

CREATE INDEX idx_terminals_role ON terminals(role);
CREATE INDEX idx_terminals_status ON terminals(status);
```

**Status transitions:**
```
Starting -> Connected -> Syncing -> Active <-> Paused
Any -> Disconnected (heartbeat timeout > 30s)
Any -> Error (critical failure)
```

**Registration**: When EA is loaded on a chart, it sends REGISTER to Hub. Hub performs:
```sql
INSERT OR IGNORE INTO terminals (terminal_id, role, account_number, broker_server, status, created_at, last_heartbeat)
VALUES (?, ?, ?, ?, 'Starting', ?, ?);
```

---

### 2. master_slave_links

Defines which Slaves subscribe to which Masters, with copy settings.

```sql
CREATE TABLE master_slave_links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id       TEXT    NOT NULL REFERENCES terminals(terminal_id),
    slave_id        TEXT    NOT NULL REFERENCES terminals(terminal_id),
    enabled         INTEGER NOT NULL DEFAULT 1,  -- 1=active, 0=disabled
    lot_mode        TEXT    NOT NULL DEFAULT 'multiplier'
                           CHECK (lot_mode IN ('multiplier', 'fixed')),
    lot_value       REAL    NOT NULL DEFAULT 1.0,
    symbol_suffix   TEXT    DEFAULT '',  -- e.g. '.s', '.f', '_demo'
    created_at      INTEGER NOT NULL,

    UNIQUE(master_id, slave_id)
);

CREATE INDEX idx_links_master ON master_slave_links(master_id);
CREATE INDEX idx_links_slave ON master_slave_links(slave_id);
CREATE INDEX idx_links_enabled ON master_slave_links(enabled);
```

**Lot modes:**
- `multiplier`: slave_volume = master_volume * lot_value
- `fixed`: slave_volume = lot_value (constant)

---

### 3. symbol_mappings

Explicit symbol mappings per link. Overrides suffix rule when present.

```sql
CREATE TABLE symbol_mappings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id         INTEGER NOT NULL REFERENCES master_slave_links(id) ON DELETE CASCADE,
    master_symbol   TEXT    NOT NULL,
    slave_symbol    TEXT    NOT NULL,

    UNIQUE(link_id, master_symbol)
);

CREATE INDEX idx_sym_link ON symbol_mappings(link_id);
CREATE INDEX idx_sym_master ON symbol_mappings(master_symbol);
```

**Resolution order:**
1. Check `symbol_mappings` for (link_id, master_symbol) → use slave_symbol
2. Else append `master_slave_links.symbol_suffix` to master symbol

---

### 4. magic_mappings

Maps master setup_id to slave setup_id per link.

```sql
CREATE TABLE magic_mappings (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id           INTEGER NOT NULL REFERENCES master_slave_links(id) ON DELETE CASCADE,
    master_setup_id   INTEGER NOT NULL,  -- positions 7-8 of master magic
    slave_setup_id    INTEGER NOT NULL,  -- replacement for positions 7-8

    UNIQUE(link_id, master_setup_id)
);

CREATE INDEX idx_magic_link ON magic_mappings(link_id);
```

**Magic formula:**
```
master_magic format: 15{pair_id:02d}{direction_block:02d}{setup_id:02d}
slave_magic = master_magic - (master_magic % 100) + slave_setup_id
```

Example: master_magic=15010301, slave_setup_id=05 → slave_magic=15010305

---

### 5. trade_mappings

Maps master trades to slave trades for lifecycle tracking.

```sql
CREATE TABLE trade_mappings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    master_id       TEXT    NOT NULL,
    slave_id        TEXT    NOT NULL,
    master_ticket   INTEGER NOT NULL,
    slave_ticket    INTEGER,           -- NULL until Slave ACKs with ticket
    master_magic    INTEGER NOT NULL,
    slave_magic     INTEGER NOT NULL,
    symbol          TEXT    NOT NULL,   -- slave symbol
    master_volume   REAL    NOT NULL,   -- original master volume
    slave_volume    REAL    NOT NULL,   -- copied slave volume
    status          TEXT    NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'open', 'partial_closed', 'closed', 'failed')),
    created_at      INTEGER NOT NULL,
    closed_at       INTEGER,

    UNIQUE(master_id, slave_id, master_ticket)
);

CREATE INDEX idx_trade_master ON trade_mappings(master_id, master_ticket);
CREATE INDEX idx_trade_slave ON trade_mappings(slave_id, slave_ticket);
CREATE INDEX idx_trade_status ON trade_mappings(status);
CREATE INDEX idx_trade_magic ON trade_mappings(master_magic);
```

**Status flow:**
```
pending -> open (Slave ACK received)
pending -> failed (3 retries exhausted or NACK)
open -> partial_closed (CLOSE_PARTIAL executed)
open -> closed (CLOSE executed)
partial_closed -> closed (remaining volume closed)
```

---

### 6. messages

All messages from Masters, with delivery status.

```sql
CREATE TABLE messages (
    msg_id          INTEGER NOT NULL,
    master_id       TEXT    NOT NULL,
    type            TEXT    NOT NULL CHECK (type IN (
                        'OPEN', 'MODIFY', 'CLOSE', 'CLOSE_PARTIAL',
                        'HEARTBEAT', 'REGISTER'
                    )),
    payload         TEXT    NOT NULL,    -- JSON string
    ts_ms           INTEGER NOT NULL,   -- Unix epoch ms
    status          TEXT    NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'sent', 'acked', 'nacked', 'expired')),

    PRIMARY KEY (master_id, msg_id)
);

CREATE INDEX idx_msg_status ON messages(status);
CREATE INDEX idx_msg_ts ON messages(ts_ms);
CREATE INDEX idx_msg_type ON messages(type);
```

**Notes:**
- msg_id is strictly increasing per master_id
- Resend window: Hub keeps last N=200 messages per master_id in memory; older stay in DB for audit
- Status `expired` = ACK timeout after 3 retries

---

### 7. message_acks

ACK/NACK responses from Slaves.

```sql
CREATE TABLE message_acks (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    msg_id          INTEGER NOT NULL,
    master_id       TEXT    NOT NULL,
    slave_id        TEXT    NOT NULL,
    ack_type        TEXT    NOT NULL CHECK (ack_type IN ('ACK', 'NACK')),
    nack_reason     TEXT,              -- NULL for ACK, reason code for NACK
    slave_ticket    INTEGER,           -- Slave ticket (if ACK on OPEN)
    ts_ms           INTEGER NOT NULL,

    FOREIGN KEY (master_id, msg_id) REFERENCES messages(master_id, msg_id)
);

CREATE INDEX idx_ack_msg ON message_acks(master_id, msg_id);
CREATE INDEX idx_ack_slave ON message_acks(slave_id);
CREATE INDEX idx_ack_type ON message_acks(ack_type);
```

---

### 8. heartbeats

Heartbeat history from all terminals.

```sql
CREATE TABLE heartbeats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    terminal_id     TEXT    NOT NULL REFERENCES terminals(terminal_id),
    vps_id          TEXT    NOT NULL,
    ts_ms           INTEGER NOT NULL,
    status_code     INTEGER NOT NULL,  -- 0=OK, non-zero=issue
    status_message  TEXT    DEFAULT '',
    last_error      TEXT    DEFAULT ''
);

CREATE INDEX idx_hb_terminal ON heartbeats(terminal_id);
CREATE INDEX idx_hb_ts ON heartbeats(ts_ms);
```

**Retention**: Hub purges heartbeats older than 7 days (configurable).

---

### 9. alerts_history

All generated alerts.

```sql
CREATE TABLE alerts_history (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type      TEXT    NOT NULL,   -- 'heartbeat_miss', 'ack_timeout', 'consecutive_nacks', 'queue_depth', 'db_size'
    terminal_id     TEXT,
    message         TEXT    NOT NULL,
    channel         TEXT    NOT NULL CHECK (channel IN ('telegram', 'email')),
    sent_at         INTEGER NOT NULL,   -- Unix epoch ms
    delivered       INTEGER NOT NULL DEFAULT 0  -- 0=pending, 1=delivered, -1=failed
);

CREATE INDEX idx_alert_type ON alerts_history(alert_type);
CREATE INDEX idx_alert_terminal ON alerts_history(terminal_id);
CREATE INDEX idx_alert_sent ON alerts_history(sent_at);
```

**Deduplication**: Hub checks before sending: no duplicate alert for same (alert_type, terminal_id) within 5 minutes.

---

## Entity Relationship Diagram

```
terminals
    |
    +--< master_slave_links (master_id FK, slave_id FK)
    |       |
    |       +--< symbol_mappings (link_id FK)
    |       |
    |       +--< magic_mappings (link_id FK)
    |
    +--< heartbeats (terminal_id FK)
    |
    +--< alerts_history (terminal_id)

messages (master_id, msg_id PK)
    |
    +--< message_acks (master_id, msg_id FK)

trade_mappings (master_id, slave_id, master_ticket UNIQUE)
```

## Concurrency & Locking Strategy

| Aspect | Approach |
|--------|----------|
| Write access | Hub Service and FastAPI both write (WAL mode handles concurrency) |
| Read access | EAs do NOT read DB directly — they communicate with Hub via pipes. FastAPI reads directly. |
| WAL mode | Enables concurrent reads during writes (used by backup script and FastAPI) |
| Transactions | Hub and FastAPI use explicit transactions for atomic multi-table updates |
| Busy timeout | 5000ms — handles rare lock contention between Hub and FastAPI |

## Backup Strategy

| Parameter | Value |
|-----------|-------|
| Method | File copy of `copier.db` (WAL checkpoint first) |
| Schedule | Daily at 00:00 UTC via Windows Task Scheduler |
| Retention | 7 daily backups |
| Location | `C:\TradeCopier\backups\copier_YYYYMMDD.db` |
| Restore | Stop Hub Service → replace copier.db → start Hub Service |

### Backup Script (backup_db.py)

```python
# Pseudocode
1. Connect to copier.db
2. Execute PRAGMA wal_checkpoint(TRUNCATE)
3. Close connection
4. Copy copier.db to backups/copier_YYYYMMDD.db
5. Delete backups older than 7 days
```

## Data Retention

| Table | Retention | Cleanup |
|-------|-----------|---------|
| terminals | Permanent | Manual deletion only |
| master_slave_links | Permanent | Manual deletion only |
| symbol_mappings | Permanent | Cascade on link delete |
| magic_mappings | Permanent | Cascade on link delete |
| trade_mappings | Permanent | Archive after 90 days (future) |
| messages | 30 days | Hub purges older records daily |
| message_acks | 30 days | Hub purges older records daily |
| heartbeats | 7 days | Hub purges older records daily |
| alerts_history | 90 days | Hub purges older records daily |

## Migration Path

SQLite is sufficient for single-VPS deployment. If multi-VPS is needed in the future:
- Replace SQLite with PostgreSQL
- Hub Service connects via connection string (config change)
- SQL syntax is kept compatible (standard SQL, no SQLite-specific features beyond PRAGMAs)
- Schema migration script provided at that time
