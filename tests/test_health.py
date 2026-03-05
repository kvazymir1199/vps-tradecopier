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
