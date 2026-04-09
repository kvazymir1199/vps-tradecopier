# Phase 2: Retry, Idempotency, Direction Validation, Magic Whitelist

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the retry mechanism safe by adding restart-proof idempotency, implement automatic retry with exhaustion alerting, enforce magic whitelist strictly, and add direction validation in the Hub.

**Architecture:** Incremental changes to existing classes — HealthChecker gains retry logic + Config, Router gets two guard checks (direction + whitelist), DatabaseManager gets three new methods + a migration, Master EA parses `resume_from` from Hub REGISTER ACK, Slave EA persists idempotency state to file.

**Tech Stack:** Python 3.11+, aiosqlite, asyncio, MQL5, Next.js/React/shadcn

---

## File Map

| File | Change |
|---|---|
| `hub/db/schema.sql` | Add `retry_count` column to messages table |
| `hub/db/manager.py` | Add `get_max_msg_id`, `get_timed_out_messages`, `increment_retry`; add `retry_count` migration |
| `hub/monitor/health.py` | Accept `Config` + `resend_callback`; implement retry in `_check_ack_timeouts` |
| `hub/main.py` | REGISTER handler returns `resume_from` ACK; add `_resend_message`; update `HealthChecker` init |
| `hub/mapping/magic.py` | Add `direction_allowed` function |
| `hub/router/router.py` | Whitelist fix (skip instead of fallback); direction guard call |
| `hub/protocol/models.py` | No changes |
| `ea/Include/CopierProtocol.mqh` | Add `ParseResumeFrom` function |
| `ea/Master/TradeCopierMaster.mq5` | Parse hub response in `OnTimer`; call `HandleHubResponse` |
| `ea/Slave/TradeCopierSlave.mq5` | Add `LoadIdempotencyState` / `SaveIdempotencyState` |
| `web/frontend/src/components/add-mapping-dialog.tsx` | Expand magic mapping description |
| `tests/test_db_manager.py` | Add tests for 3 new methods |
| `tests/test_health.py` | Update fixture; add retry and exhaustion tests |
| `tests/test_router.py` | Add whitelist and direction tests |
| `tests/test_magic.py` | Add `direction_allowed` tests |

---

## Task 1: DB schema — add `retry_count` column

**Files:**
- Modify: `hub/db/schema.sql` (line 96–114, messages table)
- Modify: `hub/db/manager.py` (lines 23–65, `_run_migrations`)

- [ ] **Step 1: Update schema.sql**

In [hub/db/schema.sql](hub/db/schema.sql), after line 107 (`status TEXT NOT NULL DEFAULT 'pending'...`), add the `retry_count` column. The full messages table should be:

```sql
-- 6. messages
CREATE TABLE IF NOT EXISTS messages (
    msg_id          INTEGER NOT NULL,
    master_id       TEXT    NOT NULL,
    type            TEXT    NOT NULL CHECK (type IN (
                        'OPEN', 'MODIFY', 'CLOSE', 'CLOSE_PARTIAL',
                        'PENDING_PLACE', 'PENDING_MODIFY', 'PENDING_DELETE',
                        'HEARTBEAT', 'REGISTER'
                    )),
    payload         TEXT    NOT NULL,
    ts_ms           INTEGER NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'pending'
                           CHECK (status IN ('pending', 'sent', 'acked', 'nacked', 'expired')),
    retry_count     INTEGER NOT NULL DEFAULT 0,

    PRIMARY KEY (master_id, msg_id)
);
```

- [ ] **Step 2: Add migration in `_run_migrations`**

In [hub/db/manager.py](hub/db/manager.py), inside `_run_migrations` (after the existing migrations, before the final `if row and "PENDING_PLACE"` block), add:

```python
        # Migration: add retry_count column to messages
        cursor = await self._conn.execute("PRAGMA table_info(messages)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "retry_count" not in columns:
            await self._conn.execute(
                "ALTER TABLE messages ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0"
            )
            await self._conn.commit()
```

Place this block **before** the `messages_old` migration block (the PENDING_PLACE one).

- [ ] **Step 3: Run tests to verify migration doesn't break existing tests**

```bash
uv run pytest tests/test_db_manager.py -v
```

Expected: all existing tests pass.

- [ ] **Step 4: Commit**

```bash
git add hub/db/schema.sql hub/db/manager.py
git commit -m "feat: add retry_count column to messages table"
```

---

## Task 2: DatabaseManager — three new methods

**Files:**
- Modify: `hub/db/manager.py`
- Modify: `tests/test_db_manager.py`

- [ ] **Step 1: Write failing tests**

Append to [tests/test_db_manager.py](tests/test_db_manager.py):

```python
@pytest.mark.asyncio
async def test_get_max_msg_id_empty(db):
    result = await db.get_max_msg_id("master_1")
    assert result == 0


@pytest.mark.asyncio
async def test_get_max_msg_id_returns_max(db):
    await db.insert_message(1, "master_1", "OPEN", '{"ticket":1}', 1000)
    await db.insert_message(5, "master_1", "OPEN", '{"ticket":5}', 2000)
    await db.insert_message(3, "master_1", "OPEN", '{"ticket":3}', 3000)
    result = await db.get_max_msg_id("master_1")
    assert result == 5


@pytest.mark.asyncio
async def test_get_max_msg_id_isolated_by_master(db):
    await db.insert_message(10, "master_1", "OPEN", '{}', 1000)
    await db.insert_message(2, "master_2", "OPEN", '{}', 1000)
    assert await db.get_max_msg_id("master_1") == 10
    assert await db.get_max_msg_id("master_2") == 2


@pytest.mark.asyncio
async def test_get_timed_out_messages_empty_when_fresh(db):
    await db.insert_message(1, "master_1", "OPEN", '{}', int(time.time() * 1000))
    result = await db.get_timed_out_messages(timeout_ms=15_000, max_retries=3)
    assert result == []


@pytest.mark.asyncio
async def test_get_timed_out_messages_returns_old_pending(db):
    old_ts = int(time.time() * 1000) - 20_000
    await db.execute(
        "INSERT INTO messages (msg_id, master_id, type, payload, ts_ms, status, retry_count) "
        "VALUES (1, 'master_1', 'OPEN', '{}', ?, 'pending', 0)",
        (old_ts,),
    )
    result = await db.get_timed_out_messages(timeout_ms=15_000, max_retries=3)
    assert len(result) == 1
    assert result[0]["msg_id"] == 1


@pytest.mark.asyncio
async def test_get_timed_out_messages_excludes_exhausted(db):
    old_ts = int(time.time() * 1000) - 20_000
    await db.execute(
        "INSERT INTO messages (msg_id, master_id, type, payload, ts_ms, status, retry_count) "
        "VALUES (1, 'master_1', 'OPEN', '{}', ?, 'pending', 3)",
        (old_ts,),
    )
    result = await db.get_timed_out_messages(timeout_ms=15_000, max_retries=3)
    assert result == []


@pytest.mark.asyncio
async def test_increment_retry_increments_count_and_resets_timer(db):
    now = int(time.time() * 1000)
    old_ts = now - 30_000
    await db.execute(
        "INSERT INTO messages (msg_id, master_id, type, payload, ts_ms, status, retry_count) "
        "VALUES (1, 'master_1', 'OPEN', '{}', ?, 'pending', 0)",
        (old_ts,),
    )
    await db.increment_retry("master_1", 1)
    row = await db.fetch_one(
        "SELECT retry_count, ts_ms FROM messages WHERE msg_id = 1 AND master_id = 'master_1'"
    )
    assert row["retry_count"] == 1
    assert row["ts_ms"] >= now  # timer reset to now
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_db_manager.py::test_get_max_msg_id_empty -v
```

Expected: `AttributeError: 'DatabaseManager' object has no attribute 'get_max_msg_id'`

- [ ] **Step 3: Implement the three methods**

In [hub/db/manager.py](hub/db/manager.py), add after `get_master_id_for_msg` (line 141):

```python
    async def get_max_msg_id(self, master_id: str) -> int:
        row = await self.fetch_one(
            "SELECT MAX(msg_id) as max_id FROM messages WHERE master_id = ?",
            (master_id,),
        )
        return row["max_id"] if row and row["max_id"] is not None else 0

    async def get_timed_out_messages(self, timeout_ms: int, max_retries: int) -> list[dict]:
        cutoff = self._now_ms() - timeout_ms
        return await self.fetch_all(
            "SELECT msg_id, master_id, type, payload, retry_count FROM messages "
            "WHERE status = 'pending' AND ts_ms < ? AND retry_count < ?",
            (cutoff, max_retries),
        )

    async def increment_retry(self, master_id: str, msg_id: int) -> None:
        await self._conn.execute(
            "UPDATE messages SET retry_count = retry_count + 1, ts_ms = ? "
            "WHERE master_id = ? AND msg_id = ?",
            (self._now_ms(), master_id, msg_id),
        )
        await self._conn.commit()
```

- [ ] **Step 4: Run all new DB tests**

```bash
uv run pytest tests/test_db_manager.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add hub/db/manager.py tests/test_db_manager.py
git commit -m "feat: add get_max_msg_id, get_timed_out_messages, increment_retry to DatabaseManager"
```

---

## Task 3: HealthChecker — retry logic

**Files:**
- Modify: `hub/monitor/health.py`
- Modify: `tests/test_health.py`

- [ ] **Step 1: Write failing tests**

Replace the content of [tests/test_health.py](tests/test_health.py) with:

```python
import time
import pytest
from hub.monitor.health import HealthChecker
from hub.db.manager import DatabaseManager
from hub.config import Config, TelegramConfig


def _make_config(**overrides) -> Config:
    defaults = dict(
        db_path=":memory:",
        vps_id="test",
        heartbeat_interval_sec=10,
        heartbeat_timeout_sec=30,
        ack_timeout_sec=15,
        ack_max_retries=3,
        resend_window_size=200,
        alert_dedup_minutes=5,
        telegram=TelegramConfig(enabled=False, bot_token="", chat_id=""),
    )
    defaults.update(overrides)
    return Config(**defaults)


@pytest.fixture
async def db():
    mgr = DatabaseManager(":memory:")
    await mgr.initialize()
    yield mgr
    await mgr.close()


@pytest.fixture
async def checker(db):
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.update_terminal_status("slave_1", "Active")
    resent = []
    hc = HealthChecker(db, _make_config(), resend_callback=lambda msg: resent.append(msg))
    hc._resent = resent
    yield hc


@pytest.mark.asyncio
async def test_detect_heartbeat_timeout(checker):
    old_ts = int(time.time() * 1000) - 60_000
    await checker._db.execute(
        "UPDATE terminals SET last_heartbeat = ? WHERE terminal_id = 'slave_1'", (old_ts,)
    )
    alerts = await checker.run_checks()
    types = [a["alert_type"] for a in alerts]
    assert "heartbeat_miss" in types


@pytest.mark.asyncio
async def test_no_alert_when_healthy(checker):
    now_ts = int(time.time() * 1000)
    await checker._db.execute(
        "UPDATE terminals SET last_heartbeat = ? WHERE terminal_id = 'slave_1'", (now_ts,)
    )
    alerts = await checker.run_checks()
    assert len(alerts) == 0


@pytest.mark.asyncio
async def test_retry_on_ack_timeout(checker, db):
    old_ts = int(time.time() * 1000) - 20_000
    await db.execute(
        "INSERT INTO messages (msg_id, master_id, type, payload, ts_ms, status, retry_count) "
        "VALUES (1, 'master_1', 'OPEN', '{\"ticket\":1}', ?, 'pending', 0)",
        (old_ts,),
    )
    alerts = await checker.run_checks()
    # No alert yet — retry_count(0) < max_retries(3)
    assert not any(a["alert_type"] == "ack_timeout" for a in alerts)
    # retry_count incremented
    row = await db.fetch_one(
        "SELECT retry_count FROM messages WHERE msg_id = 1 AND master_id = 'master_1'"
    )
    assert row["retry_count"] == 1
    # resend_callback was called
    assert len(checker._resent) == 1
    assert checker._resent[0]["msg_id"] == 1


@pytest.mark.asyncio
async def test_alert_and_expire_when_retries_exhausted(checker, db):
    old_ts = int(time.time() * 1000) - 20_000
    await db.execute(
        "INSERT INTO messages (msg_id, master_id, type, payload, ts_ms, status, retry_count) "
        "VALUES (1, 'master_1', 'OPEN', '{\"ticket\":1}', ?, 'pending', 3)",
        (old_ts,),
    )
    alerts = await checker.run_checks()
    types = [a["alert_type"] for a in alerts]
    assert "ack_timeout" in types
    # status updated to expired
    row = await db.fetch_one(
        "SELECT status FROM messages WHERE msg_id = 1 AND master_id = 'master_1'"
    )
    assert row["status"] == "expired"
    # No resend attempted
    assert len(checker._resent) == 0
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_health.py -v
```

Expected: failures because `HealthChecker.__init__` signature doesn't match.

- [ ] **Step 3: Update HealthChecker**

Replace [hub/monitor/health.py](hub/monitor/health.py) with:

```python
import time
import logging
from collections.abc import Callable, Awaitable
from typing import Any

from hub.db.manager import DatabaseManager
from hub.config import Config

logger = logging.getLogger(__name__)


class HealthChecker:
    def __init__(
        self,
        db: DatabaseManager,
        config: Config,
        resend_callback: Callable[[dict], Awaitable[None]],
    ):
        self._db = db
        self._config = config
        self._resend_callback = resend_callback
        self._heartbeat_timeout_ms = config.heartbeat_timeout_sec * 1000

    async def run_checks(self) -> list[dict]:
        alerts = []
        alerts.extend(await self._check_heartbeat_timeouts())
        alerts.extend(await self._check_ack_timeouts())
        alerts.extend(await self._check_consecutive_nacks())
        alerts.extend(await self._check_queue_depth())
        return alerts

    async def _check_heartbeat_timeouts(self) -> list[dict]:
        now = int(time.time() * 1000)
        cutoff = now - self._heartbeat_timeout_ms
        terminals = await self._db.fetch_all(
            "SELECT terminal_id, status, last_heartbeat FROM terminals "
            "WHERE status NOT IN ('Disconnected', 'Error') AND last_heartbeat < ?",
            (cutoff,),
        )
        alerts = []
        for t in terminals:
            await self._db.update_terminal_status(t["terminal_id"], "Disconnected", "Heartbeat timeout")
            alerts.append({
                "alert_type": "heartbeat_miss",
                "terminal_id": t["terminal_id"],
                "message": f"Terminal {t['terminal_id']} heartbeat timeout ({(now - t['last_heartbeat']) // 1000}s)",
            })
        return alerts

    async def _check_ack_timeouts(self) -> list[dict]:
        timeout_ms = self._config.ack_timeout_sec * 1000
        msgs = await self._db.get_timed_out_messages(timeout_ms, self._config.ack_max_retries)
        alerts = []
        for msg in msgs:
            if msg["retry_count"] < self._config.ack_max_retries:
                await self._db.increment_retry(msg["master_id"], msg["msg_id"])
                await self._resend_callback(msg)
            else:
                await self._db.update_message_status(msg["msg_id"], msg["master_id"], "expired")
                alerts.append({
                    "alert_type": "ack_timeout",
                    "terminal_id": msg["master_id"],
                    "message": (
                        f"ACK exhausted after {self._config.ack_max_retries} retries "
                        f"for msg_id={msg['msg_id']} from {msg['master_id']}"
                    ),
                })
        return alerts

    async def _check_consecutive_nacks(self) -> list[dict]:
        rows = await self._db.fetch_all(
            "SELECT slave_id, COUNT(*) as cnt FROM message_acks "
            "WHERE ack_type = 'NACK' "
            "GROUP BY slave_id HAVING cnt > 5"
        )
        alerts = []
        for r in rows:
            alerts.append({
                "alert_type": "consecutive_nacks",
                "terminal_id": r["slave_id"],
                "message": f"Slave {r['slave_id']} has {r['cnt']} NACKs",
            })
        return alerts

    async def _check_queue_depth(self) -> list[dict]:
        rows = await self._db.fetch_all(
            "SELECT master_id, COUNT(*) as cnt FROM messages "
            "WHERE status = 'pending' "
            "GROUP BY master_id HAVING cnt > 50"
        )
        alerts = []
        for r in rows:
            alerts.append({
                "alert_type": "queue_depth",
                "terminal_id": r["master_id"],
                "message": f"Master {r['master_id']} has {r['cnt']} pending messages",
            })
        return alerts
```

- [ ] **Step 4: Run health tests**

```bash
uv run pytest tests/test_health.py -v
```

Expected: all pass.

- [ ] **Step 5: Run full suite to catch regressions**

```bash
uv run pytest -v
```

Expected: all pass (main.py will fail to import until Task 4 — skip or fix temporarily if needed).

- [ ] **Step 6: Commit**

```bash
git add hub/monitor/health.py tests/test_health.py
git commit -m "feat: HealthChecker — retry on ACK timeout, expire after max_retries"
```

---

## Task 4: HubService — resend callback + resume_from in REGISTER ACK

**Files:**
- Modify: `hub/main.py`

- [ ] **Step 1: Update `start()` to pass Config + callback to HealthChecker**

In [hub/main.py](hub/main.py) line 212, change:

```python
        self.health_checker = HealthChecker(self.db, self.config.heartbeat_timeout_sec)
```

To:

```python
        self.health_checker = HealthChecker(self.db, self.config, self._resend_message)
```

- [ ] **Step 2: Add `_resend_message` method**

Add after `_noop_handler` (line 239):

```python
    async def _resend_message(self, msg: dict) -> None:
        """Retry delivery of an unACKed message by rebuilding and re-sending slave commands."""
        logger.info(
            f"Retrying msg_id={msg['msg_id']} for {msg['master_id']} "
            f"(attempt {msg['retry_count'] + 1}/{self.config.ack_max_retries})"
        )
        try:
            payload = json.loads(msg["payload"])
            master_msg = decode_master_message(json.dumps({
                "msg_id": msg["msg_id"],
                "master_id": msg["master_id"],
                "type": msg["type"],
                "ts_ms": int(time.time() * 1000),
                "payload": payload,
            }))
            links = await self.db.get_active_links(msg["master_id"])
            for link in links:
                cmd = await self.router._build_slave_command(master_msg, link)
                if cmd is None:
                    continue
                slave_pipe = self._slave_cmd_pipes.get(cmd.slave_id)
                if slave_pipe and slave_pipe._handle:
                    encoded = encode_slave_command(cmd)
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, slave_pipe._write, encoded)
                    logger.info(f"Retry forwarded {cmd.type} to {cmd.slave_id} (msg_id={cmd.msg_id})")
                else:
                    logger.warning(f"Retry: slave {cmd.slave_id} pipe not connected for msg_id={cmd.msg_id}")
        except Exception as e:
            logger.error(f"_resend_message error for msg_id={msg['msg_id']}: {e}")
```

- [ ] **Step 3: Update REGISTER handler to return `resume_from`**

In `_handle_master_message`, the REGISTER block currently ends with `return None` (line 61). Replace the REGISTER block with:

```python
            # Handle REGISTER
            if msg_type == "REGISTER":
                terminal_id = data.get("terminal_id", "")
                account = data.get("account", 0)
                broker = data.get("broker", "")
                role = data.get("role", "master").lower()
                await self.db.register_terminal(terminal_id, role, account, broker)
                symbols = data.get("symbols", [])
                if symbols:
                    await self.db.save_terminal_symbols(terminal_id, symbols)
                    logger.info(f"Saved {len(symbols)} symbols for {terminal_id}")
                resume_from = await self.db.get_max_msg_id(terminal_id)
                logger.info(f"REGISTER: {terminal_id} ({role}) account={account} resume_from={resume_from}")
                return json.dumps({"ack_type": "ACK", "resume_from": resume_from}) + "\n"
```

- [ ] **Step 4: Run the full test suite**

```bash
uv run pytest -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add hub/main.py
git commit -m "feat: Hub returns resume_from on REGISTER, implements _resend_message callback"
```

---

## Task 5: `direction_allowed` in magic.py

**Files:**
- Modify: `hub/mapping/magic.py`
- Modify: `tests/test_magic.py`

> **Note:** The direction encoding convention (what values of `direction_block` mean BUY vs SELL) is not documented in the codebase. The implementation below uses a placeholder convention. Verify with the client before deploying, and update `direction_allowed` if needed — the interface stays the same.
>
> Current observation: magic `15010301` → `direction_block=3`, used with `direction="BUY"` in tests. Placeholder uses `direction_block == 0` as unrestricted. Update the body once convention is confirmed.

- [ ] **Step 1: Write failing tests**

Append to [tests/test_magic.py](tests/test_magic.py):

```python
from hub.mapping.magic import direction_allowed

def test_direction_allowed_zero_is_unrestricted():
    assert direction_allowed(0, "BUY") is True
    assert direction_allowed(0, "SELL") is True

def test_direction_allowed_empty_direction_passes():
    assert direction_allowed(3, "") is True

def test_direction_allowed_returns_bool():
    result = direction_allowed(3, "BUY")
    assert isinstance(result, bool)
```

- [ ] **Step 2: Run to confirm failure**

```bash
uv run pytest tests/test_magic.py -v
```

Expected: `ImportError: cannot import name 'direction_allowed'`

- [ ] **Step 3: Add `direction_allowed` to magic.py**

Append to [hub/mapping/magic.py](hub/mapping/magic.py):

```python

def direction_allowed(direction_block: int, direction: str) -> bool:
    """Check if the magic number's direction_block permits the given trade direction.

    direction_block == 0 means the setup is unrestricted (trades both ways).
    The encoding convention for non-zero blocks must be confirmed with the client
    before this guard is enabled in the router.

    Placeholder implementation: all non-zero blocks are also treated as unrestricted
    until the convention is documented.
    """
    if not direction:
        return True
    if direction_block == 0:
        return True
    # TODO: replace with actual convention once confirmed, e.g.:
    # if direction_block % 2 == 0:
    #     return direction == "BUY"
    # return direction == "SELL"
    return True
```

- [ ] **Step 4: Run magic tests**

```bash
uv run pytest tests/test_magic.py -v
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add hub/mapping/magic.py tests/test_magic.py
git commit -m "feat: add direction_allowed to magic.py (placeholder pending convention confirmation)"
```

---

## Task 6: Router — whitelist fix + direction guard

**Files:**
- Modify: `hub/router/router.py`
- Modify: `tests/test_router.py`

- [ ] **Step 1: Write failing tests**

Append to [tests/test_router.py](tests/test_router.py):

```python
@pytest.mark.asyncio
async def test_route_skips_slave_without_magic_mapping():
    """Command must NOT be sent if no magic_mapping exists for the setup_id."""
    db = DatabaseManager(":memory:")
    await db.initialize()
    await db.register_terminal("master_1", "master", 111, "B1")
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.execute(
        "INSERT INTO master_slave_links (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at) "
        "VALUES ('master_1', 'slave_1', 1, 'multiplier', 2.0, '', 0)"
    )
    # Deliberately NO magic_mappings inserted
    r = Router(db)
    msg = MasterMessage(
        msg_id=1, master_id="master_1", type=MessageType.OPEN, ts_ms=170,
        payload={"ticket": 123, "symbol": "EURUSD", "direction": "BUY",
                 "volume": 0.1, "price": 1.085, "sl": 1.082, "tp": 1.089,
                 "magic": 15010301, "comment": ""},
    )
    commands = await r.route(msg)
    assert len(commands) == 0
    await db.close()


@pytest.mark.asyncio
async def test_route_uses_original_magic_not_fallback():
    """When magic mapping IS present, slave_magic must be computed (not master_magic)."""
    db = DatabaseManager(":memory:")
    await db.initialize()
    await db.register_terminal("master_1", "master", 111, "B1")
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.execute(
        "INSERT INTO master_slave_links (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at) "
        "VALUES ('master_1', 'slave_1', 1, 'multiplier', 1.0, '', 0)"
    )
    await db.execute(
        "INSERT INTO magic_mappings (link_id, master_setup_id, slave_setup_id) VALUES (1, 1, 7)"
    )
    r = Router(db)
    msg = MasterMessage(
        msg_id=1, master_id="master_1", type=MessageType.OPEN, ts_ms=170,
        payload={"ticket": 123, "symbol": "EURUSD", "direction": "BUY",
                 "volume": 0.1, "price": 1.085, "sl": 1.082, "tp": 1.089,
                 "magic": 15010301, "comment": ""},
    )
    commands = await r.route(msg)
    assert len(commands) == 1
    assert commands[0].payload["magic"] == 15010307  # not 15010301
    await db.close()
```

- [ ] **Step 2: Run to confirm first test fails (second should pass — existing code uses fallback)**

```bash
uv run pytest tests/test_router.py::test_route_skips_slave_without_magic_mapping -v
```

Expected: FAIL — currently the fallback sends with master_magic.

- [ ] **Step 3: Fix whitelist in router.py**

In [hub/router/router.py](hub/router/router.py), update the import at the top to include `direction_allowed`:

```python
from hub.mapping.magic import compute_slave_magic, parse_master_magic, direction_allowed
```

In `_build_slave_command`, replace lines 60–63:

```python
        # Resolve magic — strict whitelist: no mapping = skip this slave
        master_magic = msg.payload.get("magic", 0)
        parsed = parse_master_magic(master_magic)
        magic_map = await self._db.get_magic_mappings(link["id"])
        slave_setup_id = magic_map.get(parsed["setup_id"])
        if slave_setup_id is None:
            return None  # no magic mapping — this slave does not copy this setup
        slave_magic = compute_slave_magic(master_magic, slave_setup_id)

        # Direction guard — only for trade messages that carry a direction
        direction = msg.payload.get("direction", "")
        if not direction_allowed(parsed["direction_block"], direction):
            return None
```

- [ ] **Step 4: Run router tests**

```bash
uv run pytest tests/test_router.py -v
```

Expected: all pass (including the two new tests).

- [ ] **Step 5: Run full suite**

```bash
uv run pytest -v
```

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add hub/router/router.py tests/test_router.py
git commit -m "feat: router strict magic whitelist + direction guard"
```

---

## Task 7: Master EA — parse resume_from from Hub REGISTER ACK

**Files:**
- Modify: `ea/Include/CopierProtocol.mqh`
- Modify: `ea/Master/TradeCopierMaster.mq5`

- [ ] **Step 1: Add `ParseResumeFrom` to CopierProtocol.mqh**

In [ea/Include/CopierProtocol.mqh](ea/Include/CopierProtocol.mqh), append before the final `#endif`:

```cpp
//+------------------------------------------------------------------+
//| ParseResumeFrom — extract resume_from integer from Hub ACK JSON  |
//| Returns 0 if field not present or not a valid number.            |
//+------------------------------------------------------------------+
int ParseResumeFrom(const string &raw)
{
   string val = _JsonExtractNum(raw, "resume_from");
   if(val == "")
      return 0;
   return (int)StringToInteger(val);
}
```

- [ ] **Step 2: Add `HandleHubResponse` to TradeCopierMaster.mq5**

In [ea/Master/TradeCopierMaster.mq5](ea/Master/TradeCopierMaster.mq5), add a new function before `OnTrade`:

```cpp
//+------------------------------------------------------------------+
//| HandleHubResponse — process any response received from Hub       |
//+------------------------------------------------------------------+
void HandleHubResponse(const string &raw)
{
   int resume_from = ParseResumeFrom(raw);
   if(resume_from > g_msgId)
   {
      g_msgId = resume_from;
      PersistMsgId();
      g_logger.Info(StringFormat("[Master] resume_from=%d received from Hub — msg_id advanced", g_msgId));
   }
}
```

- [ ] **Step 3: Update `OnTimer` to call `HandleHubResponse` instead of discarding**

In [ea/Master/TradeCopierMaster.mq5](ea/Master/TradeCopierMaster.mq5), find the polling block in `OnTimer` (currently lines ~188–193):

```cpp
   //--- Poll pipe for any responses (discard; master is fire-and-forget)
   string recv = g_pipe.Receive();
   while(StringLen(recv) > 0)
   {
      g_logger.Debug(StringFormat("Received: %s", recv));
      recv = g_pipe.Receive();
   }
```

Replace with:

```cpp
   //--- Poll pipe for responses (parse resume_from on REGISTER ACK)
   string recv = g_pipe.Receive();
   while(StringLen(recv) > 0)
   {
      HandleHubResponse(recv);
      recv = g_pipe.Receive();
   }
```

- [ ] **Step 4: Compile in MetaEditor**

Open MetaEditor, compile `ea/Master/TradeCopierMaster.mq5`.
Expected: 0 errors, 0 warnings.

- [ ] **Step 5: Commit**

```bash
git add ea/Include/CopierProtocol.mqh ea/Master/TradeCopierMaster.mq5
git commit -m "feat: Master EA parses resume_from from Hub REGISTER ACK"
```

---

## Task 8: Slave EA — file-backed idempotency state

**Files:**
- Modify: `ea/Slave/TradeCopierSlave.mq5`

- [ ] **Step 1: Add `LoadIdempotencyState` and `SaveIdempotencyState`**

In [ea/Slave/TradeCopierSlave.mq5](ea/Slave/TradeCopierSlave.mq5), add two functions after `RecordProcessedMessage`:

```cpp
//+------------------------------------------------------------------+
//| LoadIdempotencyState — restore last_msg_id per master from file  |
//| File: MQL5/Files/copier_idem_<account>.csv                       |
//| Format per line: master_id,last_msg_id                           |
//+------------------------------------------------------------------+
void LoadIdempotencyState()
{
   string filename = "copier_idem_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ".csv";
   int handle = FileOpen(filename, FILE_READ | FILE_CSV | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
   {
      g_logger.Info("[Slave] No idempotency file found — starting fresh");
      return;
   }
   int loaded = 0;
   while(!FileIsEnding(handle))
   {
      string master_id = FileReadString(handle);
      if(FileIsEnding(handle)) break;  // guard against trailing newline
      int last_id = (int)FileReadNumber(handle);
      if(master_id != "")
      {
         RecordProcessedMessage(master_id, last_id);
         loaded++;
      }
   }
   FileClose(handle);
   g_logger.Info(StringFormat("[Slave] Loaded idempotency state: %d masters", loaded));
}

//+------------------------------------------------------------------+
//| SaveIdempotencyState — persist current idempotency table to file |
//+------------------------------------------------------------------+
void SaveIdempotencyState()
{
   string filename = "copier_idem_" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ".csv";
   int handle = FileOpen(filename, FILE_WRITE | FILE_CSV | FILE_ANSI, ',');
   if(handle == INVALID_HANDLE)
   {
      g_logger.Error("[Slave] Failed to open idempotency file for writing");
      return;
   }
   for(int i = 0; i < g_idempotencyCount; i++)
   {
      FileWrite(handle, g_idempotency[i].master_id, g_idempotency[i].last_msg_id);
   }
   FileClose(handle);
}
```

- [ ] **Step 2: Call `LoadIdempotencyState` in `OnInit`**

Find `OnInit` in [ea/Slave/TradeCopierSlave.mq5](ea/Slave/TradeCopierSlave.mq5). After `g_idempotencyCount = 0;` (where the idempotency array is zeroed), add:

```cpp
   //--- Restore idempotency state from previous session
   LoadIdempotencyState();
```

- [ ] **Step 3: Call `SaveIdempotencyState` after `RecordProcessedMessage`**

Find every call to `RecordProcessedMessage(...)` in the Slave EA. After each call, add:

```cpp
      SaveIdempotencyState();
```

There should be exactly one such call site (inside the command processing block, after the successful trade execution and before the ACK is sent).

- [ ] **Step 4: Compile in MetaEditor**

Open MetaEditor, compile `ea/Slave/TradeCopierSlave.mq5`.
Expected: 0 errors, 0 warnings.

- [ ] **Step 5: Commit**

```bash
git add ea/Slave/TradeCopierSlave.mq5
git commit -m "feat: Slave EA persists idempotency state to file — restart-safe dedup"
```

---

## Task 9: Frontend — magic mapping dialog description

**Files:**
- Modify: `web/frontend/src/components/add-mapping-dialog.tsx`

- [ ] **Step 1: Update the DialogDescription for magic type**

In [web/frontend/src/components/add-mapping-dialog.tsx](web/frontend/src/components/add-mapping-dialog.tsx), replace lines 65–69:

```tsx
          <DialogDescription>
            {isSymbol
              ? "Map a master symbol to a slave symbol."
              : "Map a master setup ID to a slave setup ID."}
          </DialogDescription>
```

With:

```tsx
          <DialogDescription>
            {isSymbol
              ? "Map a master symbol to a slave symbol."
              : (
                <>
                  Map a master setup ID to a slave setup ID.{" "}
                  The hub replaces the last two digits of the master magic number
                  with the slave setup ID. Example: master magic{" "}
                  <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">15010301</code>
                  {" "}→ slave magic{" "}
                  <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">15010305</code>.
                </>
              )}
          </DialogDescription>
```

- [ ] **Step 2: Verify the frontend builds without errors**

```bash
cd web/frontend && npm run build
```

Expected: successful build, no TypeScript errors.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/components/add-mapping-dialog.tsx
git commit -m "feat: add magic number transformation explanation to Add Magic Mapping dialog"
```

---

## Task 10: Final verification

- [ ] **Step 1: Run full test suite**

```bash
uv run pytest -v
```

Expected: all tests pass (70+ tests green).

- [ ] **Step 2: Verify hub starts cleanly**

```bash
uv run python -m hub.main
```

Expected: no startup errors, log shows "Hub Service started".

- [ ] **Step 3: Manual ACK flow check**

1. Start the Hub
2. Connect Master EA — Hub log should show `resume_from=N` in REGISTER response
3. Open a trade on Master — message appears in `messages` table with `status='pending'`, `retry_count=0`
4. Stop the Slave EA (simulate no ACK)
5. Wait 15+ seconds — Hub log should show retry attempt, `retry_count` increments to 1
6. After 3 retries — `status='expired'`, Telegram alert fired (if configured)

- [ ] **Step 4: Magic whitelist check**

1. In Web UI, open a link's Mappings panel
2. Delete all magic mappings for the link
3. Open a trade on Master
4. Verify in Hub logs: "No magic mapping for setup_id=X — skipping"
5. Verify no command reached Slave

- [ ] **Step 5: Check dialog description in UI**

1. `cd web/frontend && npm run dev`
2. Open the app, navigate to a link's Mappings
3. Click "Add Magic Mapping"
4. Verify the description shows the example with `15010301 → 15010305`
