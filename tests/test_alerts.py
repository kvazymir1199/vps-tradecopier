import time
from dataclasses import dataclass
from unittest.mock import patch

import pytest
from hub.monitor.alerts import AlertSender
from hub.db.manager import DatabaseManager


@dataclass
class FakeTelegram:
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""


@dataclass
class FakeConfig:
    alert_dedup_minutes: int = 5
    telegram: FakeTelegram = None

    def __post_init__(self):
        if self.telegram is None:
            self.telegram = FakeTelegram()


@pytest.fixture
async def sender():
    db = DatabaseManager(":memory:")
    await db.initialize()
    cfg = FakeConfig(telegram=FakeTelegram(enabled=False))
    s = AlertSender(db, cfg)
    yield s
    await db.close()


@pytest.mark.asyncio
async def test_alert_recorded_in_db(sender):
    alert = {"alert_type": "heartbeat_miss", "terminal_id": "slave_1", "message": "test alert"}
    await sender.send(alert)
    row = await sender._db.fetch_one("SELECT * FROM alerts_history WHERE alert_type = 'heartbeat_miss'")
    assert row is not None
    assert row["message"] == "test alert"


@pytest.mark.asyncio
async def test_alert_deduplication(sender):
    alert = {"alert_type": "heartbeat_miss", "terminal_id": "slave_1", "message": "test alert"}
    await sender.send(alert)
    await sender.send(alert)  # should be deduplicated
    rows = await sender._db.fetch_all("SELECT * FROM alerts_history WHERE alert_type = 'heartbeat_miss'")
    assert len(rows) == 1
