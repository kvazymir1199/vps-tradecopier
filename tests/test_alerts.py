"""AlertSender: persistence, dedup, mute, per-type toggle, retry-on-failure.

These tests use the production DatabaseManager + a FakeConfig that mirrors the
real Config dataclass. AlertSender is never given a real Telegram bot token, so
delivery is exercised by monkey-patching `_post_message`.
"""

import asyncio
import time
from dataclasses import dataclass, field

import pytest

from hub.config import ALERT_TYPES
from hub.db.manager import DatabaseManager
from hub.monitor.alerts import AlertSender


@dataclass
class FakeTelegram:
    enabled: bool = False
    bot_token: str = ""
    chat_id: str = ""
    daily_summary_time: str = "08:00"
    alert_storm_threshold: int = 10
    alerts_retention_days: int = 90
    alert_enabled: dict[str, bool] = field(default_factory=dict)


@dataclass
class FakeConfig:
    alert_dedup_minutes: int = 5
    telegram: FakeTelegram | None = None

    def __post_init__(self):
        if self.telegram is None:
            self.telegram = FakeTelegram()
        # Mimic Config.from_db: every known type defaults to enabled.
        for at in ALERT_TYPES:
            self.telegram.alert_enabled.setdefault(at, True)


@pytest.fixture
async def sender():
    db = DatabaseManager(":memory:")
    await db.initialize()
    cfg = FakeConfig(telegram=FakeTelegram(enabled=False))
    s = AlertSender(db, cfg)
    yield s
    await db.close()


# ───────────────────────── persistence ──────────────────────────────


@pytest.mark.asyncio
async def test_alert_recorded_in_db(sender):
    alert = {
        "alert_type": "heartbeat_miss",
        "terminal_id": "slave_1",
        "message": "test alert",
    }
    await sender.send(alert)
    row = await sender._db.fetch_one(
        "SELECT * FROM alerts_history WHERE alert_type = 'heartbeat_miss'"
    )
    assert row is not None
    assert row["message"] == "test alert"
    # Telegram disabled → delivered must stay 0 with no retries scheduled.
    assert row["delivered"] == 0
    assert row["retry_count"] == 0
    assert row["deduplicated"] == 0
    assert row["muted"] == 0


# ───────────────────────── dedup ────────────────────────────────────


@pytest.mark.asyncio
async def test_dedup_suppresses_second_send_with_flag(sender):
    """Second identical alert is persisted but flagged deduplicated=1.

    This is a deliberate change from MS2 behaviour: keeping the row makes the
    suppression visible in the /alerts UI and feeds the storm-tracker.
    """
    alert = {
        "alert_type": "heartbeat_miss",
        "terminal_id": "slave_1",
        "message": "test alert",
    }
    await sender.send(alert)
    await sender.send(alert)
    rows = await sender._db.fetch_all(
        "SELECT * FROM alerts_history WHERE alert_type = 'heartbeat_miss' "
        "ORDER BY id ASC"
    )
    assert len(rows) == 2
    assert rows[0]["deduplicated"] == 0
    assert rows[1]["deduplicated"] == 1


# ───────────────────────── mute gate ────────────────────────────────


@pytest.mark.asyncio
async def test_mute_window_suppresses_send_with_flag(sender):
    await sender._db.set_mute_until_ms(int(time.time() * 1000) + 60_000)
    await sender.send(
        {
            "alert_type": "ack_timeout",
            "terminal_id": "master_1",
            "message": "should be muted",
        }
    )
    row = await sender._db.fetch_one(
        "SELECT * FROM alerts_history WHERE alert_type = 'ack_timeout'"
    )
    assert row is not None
    assert row["muted"] == 1
    assert row["delivered"] == 0


@pytest.mark.asyncio
async def test_force_bypasses_mute_and_dedup(sender):
    """Synthetic alerts (Test button, hub_started) must always go through."""
    await sender._db.set_mute_until_ms(int(time.time() * 1000) + 60_000)
    await sender.send(
        {"alert_type": "hub_started", "message": "first"}, force=True
    )
    await sender.send(
        {"alert_type": "hub_started", "message": "second"}, force=True
    )
    rows = await sender._db.fetch_all(
        "SELECT * FROM alerts_history WHERE alert_type = 'hub_started' "
        "ORDER BY id"
    )
    assert len(rows) == 2
    # Neither got muted/deduplicated despite the active mute window.
    assert all(r["muted"] == 0 and r["deduplicated"] == 0 for r in rows)


# ───────────────────────── per-type toggle ──────────────────────────


@pytest.mark.asyncio
async def test_disabled_type_is_persisted_but_not_delivered(sender):
    sender._config.telegram.alert_enabled["trade_copied"] = False
    await sender.send(
        {
            "alert_type": "trade_copied",
            "terminal_id": "slave_2",
            "message": "should not deliver",
        }
    )
    row = await sender._db.fetch_one(
        "SELECT * FROM alerts_history WHERE alert_type = 'trade_copied'"
    )
    assert row is not None
    assert row["delivered"] == 0


# ───────────────────────── retry / delivery ─────────────────────────


@pytest.mark.asyncio
async def test_retry_records_attempts_and_finally_marks_failed(monkeypatch):
    db = DatabaseManager(":memory:")
    await db.initialize()
    cfg = FakeConfig(
        telegram=FakeTelegram(enabled=True, bot_token="t", chat_id="c")
    )
    s = AlertSender(db, cfg)

    # Replace the network call with a stub that always fails, and the
    # backoff with zero so the test stays fast.
    monkeypatch.setattr(
        "hub.monitor.alerts.RETRY_BACKOFF_SEC", (0, 0, 0)
    )

    async def _fail(self, _text):
        raise RuntimeError("simulated network failure")

    monkeypatch.setattr(AlertSender, "_post_message", _fail)

    await s.send(
        {
            "alert_type": "queue_depth",
            "terminal_id": "master_x",
            "message": "boom",
        }
    )
    await s.wait_until_idle(timeout=2)

    row = await db.fetch_one(
        "SELECT delivered, retry_count FROM alerts_history "
        "WHERE alert_type = 'queue_depth'"
    )
    assert row is not None
    assert row["delivered"] == 0
    assert row["retry_count"] == 3
    await db.close()


@pytest.mark.asyncio
async def test_retry_marks_delivered_on_first_success(monkeypatch):
    db = DatabaseManager(":memory:")
    await db.initialize()
    cfg = FakeConfig(
        telegram=FakeTelegram(enabled=True, bot_token="t", chat_id="c")
    )
    s = AlertSender(db, cfg)
    monkeypatch.setattr("hub.monitor.alerts.RETRY_BACKOFF_SEC", (0, 0, 0))

    async def _ok(self, _text):
        return

    monkeypatch.setattr(AlertSender, "_post_message", _ok)

    await s.send(
        {
            "alert_type": "consecutive_nacks",
            "terminal_id": "slave_3",
            "message": "n=6",
        }
    )
    await s.wait_until_idle(timeout=2)

    row = await db.fetch_one(
        "SELECT delivered, retry_count FROM alerts_history "
        "WHERE alert_type = 'consecutive_nacks'"
    )
    assert row["delivered"] == 1
    assert row["retry_count"] == 0
    await db.close()


# ───────────────────────── storm tracker ────────────────────────────


@pytest.mark.asyncio
async def test_storm_tracker_fires_when_threshold_reached():
    db = DatabaseManager(":memory:")
    await db.initialize()
    cfg = FakeConfig(
        telegram=FakeTelegram(enabled=False, alert_storm_threshold=3)
    )
    s = AlertSender(db, cfg)

    base = {"alert_type": "ack_timeout", "terminal_id": "m1", "message": "x"}
    # First call is the unique alert — not dedup. Subsequent N hits are.
    await s.send(base)
    for _ in range(5):
        await s.send(base)

    storm = await db.fetch_one(
        "SELECT * FROM alerts_history WHERE alert_type = 'alert_storm'"
    )
    assert storm is not None, "alert_storm row should have been emitted"
    await db.close()
