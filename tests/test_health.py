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

    async def resend_callback(msg):
        resent.append(msg)

    hc = HealthChecker(db, _make_config(), resend_callback=resend_callback)
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
