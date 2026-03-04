# Trade Copier — Architecture & Execution Plan

## 1. Overview

MT5 Trade Copier system: Master EA terminals detect trade events and send them through a Python Hub Service to Slave EA terminals for execution. All state is stored in a single SQLite database (`copier.db`). A web panel (FastAPI + Next.js) provides terminal management UI.

**Setup**: 2 Master terminals, up to 10 Slave terminals, single VPS.

## 2. Architecture

```
          Browser (localhost:3000)
               |
        +------+------+
        | Next.js App |
        | (shadcn/ui) |
        +------+------+
               | REST API (polling 5s)
               v
        +------+------+
        | FastAPI     |  :8000
        | (separate   |
        |  process)   |
        +------+------+
               | read + write
               v
+----------------+         +----------------+
| Master EA #1   |         | Master EA #2   |
| (MT5 Terminal) |         | (MT5 Terminal) |
+-------+--------+         +-------+--------+
        | pipe: master_1           | pipe: master_2
        v                          v
+----------------------------------------------+
|              Hub Service (Python)            |
|          Windows Service via NSSM            |
|                                              |
|  +-------------+  +----------------------+   |
|  | Router      |  | Monitor              |   |
|  | (msg routing|  | (heartbeats, alerts) |   |
|  |  + resend)  |  |                      |   |
|  +-------------+  +----------------------+   |
|  +------------------------------------------+|
|  |        SQLite Manager (WAL mode)         ||
|  +------------------------------------------+|
+---+----+----+----+----+----+----+----+----+--+
    |    |    |    |    |    |    |    |    |
    v    v    v    v    v    v    v    v    v
   S1   S2   S3   S4   S5   S6   S7   S8  ...S10
  (named pipe per slave)

              +--------------+
              |  copier.db   |
              |  (SQLite)    |
              +--------------+
```

### Components

| Component | Technology | Responsibility |
|-----------|------------|----------------|
| Master EA | MQL5 (EX5) | Detect trade events (OnTrade), send messages to Hub via named pipe |
| Hub Service | Python, Windows Service (NSSM) | Route messages, manage DB, monitor health, send alerts |
| Slave EA | MQL5 (EX5) | Receive commands from Hub, execute via CTrade, send ACK/NACK |
| Database | SQLite (WAL mode) | Single source of truth for all state |
| FastAPI | Python, separate process (:8000) | REST API for web panel, reads+writes copier.db directly |
| Web Panel | Next.js, shadcn/ui, Tailwind (:3000) | Terminal management UI, master-slave links CRUD, polling |

### Data Flow

```
1. Master EA detects trade event (OnTrade / timer poll)
2. Master EA sends JSON message via named pipe to Hub
3. Hub validates message, looks up subscriptions (master_slave_links)
4. Hub maps symbol (suffix/explicit mapping) and magic number
5. Hub maps lot size (multiplier or fixed, per link)
6. Hub sends transformed message to each subscribed Slave via named pipe
7. Slave EA receives command, executes via CTrade
8. Slave EA sends ACK (with slave_ticket) or NACK (with reason) to Hub
9. Hub records ACK/NACK in DB, updates trade_mappings
10. If ACK timeout: Hub retries up to 3 times, then alerts
```

### Named Pipe Naming Convention

| Pipe | Direction | Format |
|------|-----------|--------|
| Master → Hub | Master writes, Hub reads | `\\.\pipe\copier_master_{terminal_id}` |
| Hub → Slave | Hub writes, Slave reads | `\\.\pipe\copier_slave_{terminal_id}_cmd` |
| Slave → Hub | Slave writes, Hub reads | `\\.\pipe\copier_slave_{terminal_id}_ack` |

### Terminal Registration

When an EA is loaded onto a chart:
1. EA generates or reads its `terminal_id` from input parameters
2. EA opens its named pipe
3. EA sends a REGISTER message to Hub with: terminal_id, role, account_number, broker_server
4. Hub inserts into `terminals` table (INSERT OR IGNORE)
5. Hub sets status to `Starting` → `Connected`
6. EA begins heartbeat loop

### Transport: Named Pipes (Bidirectional, Local VPS)

- Each pipe is unidirectional for clarity (separate read/write pipes)
- Messages are newline-delimited JSON (`\n` terminated)
- Max message size: 4 KB
- Non-blocking reads with 100ms poll interval on EA side
- Hub uses asyncio for concurrent pipe handling

### Hybrid Logic

- **EventSetMillisecondTimer(100)** on both Master and Slave EAs for pipe polling
- **OnTrade()** on Master EA for immediate trade event detection
- Hub uses Python asyncio event loop with concurrent pipe I/O

### Failure & Reconnect Handling

| Scenario | Behavior |
|----------|----------|
| Slave pipe disconnected | Hub queues messages (up to resend window N=200). When Slave reconnects, Hub replays pending. |
| Master pipe disconnected | Hub marks Master as Disconnected after heartbeat timeout. No new messages routed. |
| Hub restart | Hub reads last_msg_id per master from DB. Requests resend from Master if gap detected. EAs reconnect pipes automatically. |
| EA restart | EA re-registers, Hub replays any unacked messages from resend window. |
| DB locked | SQLite WAL mode allows concurrent reads. Hub is sole writer — no write contention. |

## 3. Message Protocol

### Message Format (JSON, newline-delimited)

#### Master -> Hub

```json
{
  "msg_id": 1001,
  "master_id": "master_1",
  "type": "OPEN",
  "ts_ms": 1709000000000,
  "payload": {
    "ticket": 12345678,
    "symbol": "EURUSD",
    "direction": "BUY",
    "volume": 0.10,
    "price": 1.08550,
    "sl": 1.08200,
    "tp": 1.08900,
    "magic": 15010301,
    "comment": "Setup #01"
  }
}
```

#### Hub -> Slave

```json
{
  "msg_id": 1001,
  "master_id": "master_1",
  "slave_id": "slave_1",
  "type": "OPEN",
  "ts_ms": 1709000000000,
  "payload": {
    "master_ticket": 12345678,
    "symbol": "EURUSD.s",
    "direction": "BUY",
    "volume": 0.20,
    "price": 1.08550,
    "sl": 1.08200,
    "tp": 1.08900,
    "magic": 15010305,
    "comment": "Copy:master_1:12345678"
  }
}
```

#### Slave -> Hub (ACK)

```json
{
  "msg_id": 1001,
  "slave_id": "slave_1",
  "ack_type": "ACK",
  "slave_ticket": 87654321,
  "ts_ms": 1709000000500
}
```

#### Slave -> Hub (NACK)

```json
{
  "msg_id": 1001,
  "slave_id": "slave_1",
  "ack_type": "NACK",
  "reason": "SYMBOL_NOT_FOUND",
  "ts_ms": 1709000000500
}
```

### Message Types

| Type | Payload Fields | Description |
|------|---------------|-------------|
| OPEN | ticket, symbol, direction, volume, price, sl, tp, magic, comment | Open new position |
| MODIFY | ticket, magic, sl, tp | Modify SL/TP of existing position |
| CLOSE | ticket, magic | Full close of position |
| CLOSE_PARTIAL | ticket, magic, volume | Partial close by specified volume |
| HEARTBEAT | vps_id, status_code, status_message, last_error | Terminal health pulse |
| REGISTER | terminal_id, role, account_number, broker_server | EA registration on load |

### NACK Reason Codes

| Code | Description |
|------|-------------|
| SYMBOL_NOT_FOUND | Symbol does not exist in Slave's MarketWatch |
| SYMBOL_NOT_MAPPED | No symbol mapping configured for this master→slave link |
| INSUFFICIENT_MARGIN | Not enough margin to open position |
| INVALID_VOLUME | Volume out of allowed range for symbol |
| TRADE_DISABLED | Trading disabled on Slave terminal |
| ORDER_FAILED | CTrade execution failed (with details) |
| DUPLICATE_MSG | Message already processed (idempotency check) |

### Delivery Rules

- **msg_id**: uint64, strictly increasing per master_id
- **Sequencing**: Hub tracks `last_processed_msg_id` per (master_id, slave_id)
- **Resend window**: Hub stores last N=200 messages per master_id for replay
- **Idempotency**: Slave checks msg_id against last processed — if already handled, sends ACK without re-executing
- **ACK timeout**: Hub waits 5 seconds for ACK, retries up to 3 times, then marks as failed + alert
- **Validation**: Hub validates symbol mapping before forwarding to Slave; if unmapped → NACK from Hub

## 4. Magic Number Mapping

### Master Magic Format

8 digits: `15{pair_id:02d}{direction_block:02d}{setup_id:02d}`

Example: `15010301`
- `15` — fixed prefix
- `01` — pair_id (e.g., EURUSD)
- `03` — direction_block
- `01` — setup_id

### Slave Magic Mapping Rule

```
slave_magic = master_magic - (master_magic % 100) + slave_setup_id
```

Example:
- Master magic: `15010301` (setup_id = 01)
- Slave setup_id for this link: `05`
- Slave magic: `15010305`

### Mapping Table

Stored in `magic_mappings` table, per master_slave_link:

| link_id | master_setup_id | slave_setup_id |
|---------|----------------|----------------|
| 1 | 01 | 05 |
| 1 | 02 | 06 |
| 2 | 01 | 10 |

## 5. Symbol Naming / Suffix Handling

### Two-level mapping (priority order)

1. **Explicit mapping** (`symbol_mappings` table): direct master_symbol → slave_symbol per link
   - Example: XAUUSD → GOLD.s

2. **Suffix rule** (`master_slave_links.symbol_suffix`): Hub appends suffix to master symbol
   - Example: EURUSD + ".s" = EURUSD.s

**Priority**: Explicit mapping wins over suffix rule.

### Validation Chain

1. Hub receives OPEN/MODIFY/CLOSE from Master
2. Hub looks up link for each subscribed Slave
3. Hub resolves symbol:
   a. Check `symbol_mappings` for explicit mapping
   b. Else apply suffix from `master_slave_links.symbol_suffix`
   c. If no mapping possible → Hub generates NACK `SYMBOL_NOT_MAPPED`
4. Hub sends to Slave with resolved symbol
5. Slave verifies symbol exists in MarketWatch
   - If not found → NACK `SYMBOL_NOT_FOUND`

## 6. Lot Size Handling

### Modes (per master_slave_link)

| Mode | Field | Behavior |
|------|-------|----------|
| multiplier | lot_value = 2.0 | slave_volume = master_volume * lot_value |
| fixed | lot_value = 0.05 | slave_volume = lot_value (constant) |

### CLOSE_PARTIAL Volume

For partial closes with multiplier mode:
```
slave_close_volume = master_close_volume * lot_value
```

For fixed mode:
```
slave_close_volume = (master_close_volume / master_open_volume) * slave_open_volume
```
(Proportional to the ratio on Master)

### Validation

Slave EA normalizes volume to symbol's step size (SymbolInfoDouble SYMBOL_VOLUME_STEP) before execution. If resulting volume < SYMBOL_VOLUME_MIN → NACK `INVALID_VOLUME`.

## 7. Monitoring

### Heartbeat

- Each EA sends HEARTBEAT to Hub every **10 seconds**
- Hub records in `heartbeats` table
- Hub updates `terminals.last_heartbeat` and `terminals.status`

### Terminal Status Lifecycle

```
[EA loaded on chart]
       |
       v
   Starting --> Connected --> Syncing --> Active
                                            |
                                       +----+
                                       v    |
                                    Paused  | (resume)
                                       |    |
                                       +----+

   Any status --> Disconnected (heartbeat timeout > 30s)
   Any status --> Error (critical failure)
```

### Health Checks (5 checks)

| # | Check | Threshold | Action |
|---|-------|-----------|--------|
| 1 | Heartbeat timeout | >30 sec without heartbeat | Status → Disconnected, alert |
| 2 | ACK timeout | >15 sec without ACK on message | Retry 3x, then alert |
| 3 | Consecutive NACKs | >5 NACK in a row from one Slave | Status → Error, alert |
| 4 | Message queue depth | >50 pending messages for Slave | Alert "slave lagging" |
| 5 | DB file size | >500 MB | Warning: cleanup needed |

### Alerts

- **Channels**: Telegram (primary), Email (backup)
- **Credentials**: stored in `config.json` (outside repo), encrypted with Windows DPAPI
- **Deduplication**: one alert per type+terminal no more than once per 5 minutes
- **History**: all alerts logged to `alerts_history` table

### Heartbeat Payload

```json
{
  "vps_id": "vps_1",
  "terminal_id": "slave_3",
  "role": "slave",
  "account": 12345678,
  "broker_server": "BrokerName-Live",
  "ts_ms": 1709000010000,
  "status_code": 0,
  "status_message": "Active",
  "last_error": ""
}
```

## 8. Backup Strategy

- **Daily automated backup** of `copier.db` (file copy while in WAL mode is safe for reads)
- Backup script: `backup_db.py` runs via Windows Task Scheduler at 00:00 UTC
- Retention: 7 daily backups
- Restore procedure: stop Hub Service → replace copier.db → start Hub Service

## 9. Test Plan & Acceptance Criteria

### Unit Tests

| Test | What |
|------|------|
| Protocol encode/decode | JSON serialization/deserialization of all message types |
| Magic generator | Verify magic number format, mapping rule correctness |
| Symbol mapping | Suffix application, explicit mapping priority, edge cases |
| Lot calculation | Multiplier mode, fixed mode, partial close proportions |
| Volume normalization | Rounding to step size, min/max validation |

### Integration / E2E Tests

| Test | Scenario |
|------|----------|
| Master → Slave OPEN | Full flow: Master detects trade → Hub routes → Slave opens → ACK |
| MODIFY SL/TP | Master modifies → Slave updates → ACK |
| CLOSE full | Master closes → Slave closes → ACK |
| CLOSE_PARTIAL | Master partial close → Slave proportional close → ACK |
| Reconnect | Kill Slave pipe → messages queued → Slave reconnects → replay → ACK |
| Idempotency | Send same msg_id twice → Slave returns ACK without duplicate execution |
| Symbol suffix | Master sends EURUSD → Slave receives EURUSD.s |
| Symbol explicit | Master sends XAUUSD → Slave receives GOLD.s |
| NACK handling | Slave receives unmapped symbol → NACK → alert generated |
| Multi-master | 2 Masters send simultaneously → both routed correctly |

### Load / Stress Tests

| Test | Target |
|------|--------|
| 5 slaves concurrent | All 5 Slaves receive and ACK within 1 second |
| Burst: 50 messages in 1 sec | Hub queues and delivers all, no drops |
| Sustained: 10 msg/sec for 1 hour | No memory leaks, DB stays responsive |
| Goal: scalable to 10 slaves | Verify with 10 Slave pipe connections active |

### Acceptance Criteria (Milestone 2)

- [ ] 2 Master terminals + at least 1 Slave terminal working end-to-end
- [ ] OPEN / MODIFY(SL/TP) / CLOSE(full) / CLOSE_PARTIAL all functional
- [ ] Correct symbol suffix mapping applied
- [ ] Idempotency: no duplicate trades after EA or Hub restart
- [ ] Heartbeat + health checks writing to DB
- [ ] Alert trigger test (Telegram) successful
- [ ] Web panel: terminals list, links CRUD, symbol/magic mappings CRUD

### Acceptance Criteria (Milestone 3)

- [ ] 2 Master terminals + 5 Slave terminals stable operation
- [ ] Scalability verified up to 10 Slaves
- [ ] All E2E and stress tests pass
- [ ] Stable during agreed test window
- [ ] Web panel stable, all CRUD operations verified

## 10. Web Panel (FastAPI + Next.js)

See: `docs/plans/2026-02-26-frontend-design.md` for detailed design.

### Summary

- **FastAPI** (:8000) — REST API, separate process, reads+writes `copier.db` directly (WAL mode)
- **Next.js** (:3000) — shadcn/ui + Tailwind, single page app
- **No authentication** — localhost only
- **Polling** every 5 seconds for terminal status updates
- **Single page** with 3 sections: Terminals list, Master→Slave links CRUD, Symbol/Magic mappings
