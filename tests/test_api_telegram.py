"""FastAPI endpoints for /api/telegram and /api/alerts.

Mirrors the fixture pattern used by tests/test_api_terminals.py: a fresh
SQLite file per test, schema applied directly, `database.DB_PATH`
monkey-patched. Telegram delivery is not exercised here — the test_alert
endpoint is invoked without bot credentials so it returns delivered=false
and we only check the row lands in alerts_history.
"""

from __future__ import annotations

import time
from pathlib import Path

import aiosqlite
import httpx
import pytest
from httpx import ASGITransport

import web.api.database as database
from hub.db.manager import DatabaseManager
from web.api.main import create_app

SCHEMA = (
    Path(__file__).resolve().parent.parent / "hub" / "db" / "schema.sql"
).read_text()


@pytest.fixture
async def client(tmp_path):
    db_path = str(tmp_path / "test.db")
    # Use DatabaseManager.initialize() so migrations + seed_config_defaults
    # produce exactly the same starting state the live API sees.
    mgr = DatabaseManager(db_path)
    await mgr.initialize()
    await mgr.seed_config_defaults()
    await mgr.close()

    database.DB_PATH = db_path
    app = create_app()

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_get_telegram_returns_defaults(client):
    r = await client.get("/api/telegram")
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is False
    assert data["bot_token"] == ""
    assert data["alert_storm_threshold"] == 10
    assert data["alerts_retention_days"] == 90
    assert data["alert_dedup_minutes"] == 5
    assert data["alert_enabled"]["trade_copied"] is False
    assert data["alert_enabled"]["heartbeat_miss"] is True


@pytest.mark.asyncio
async def test_put_telegram_updates_subset_of_fields(client):
    r = await client.put(
        "/api/telegram",
        json={"bot_token": "tok", "chat_id": "42", "enabled": True},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["enabled"] is True
    assert data["bot_token"] == "tok"
    assert data["chat_id"] == "42"
    assert data["daily_summary_time"] == "08:00"


@pytest.mark.asyncio
async def test_put_telegram_enables_alert_toggle(client):
    r = await client.put(
        "/api/telegram",
        json={"alert_enabled": {"trade_copied": True}},
    )
    assert r.status_code == 200
    assert r.json()["alert_enabled"]["trade_copied"] is True


@pytest.mark.asyncio
async def test_put_telegram_rejects_unknown_alert_type(client):
    r = await client.put(
        "/api/telegram",
        json={"alert_enabled": {"not_a_real_type": True}},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_mute_and_clear(client):
    before = int(time.time() * 1000)
    r = await client.post("/api/telegram/mute", json={"duration_seconds": 60})
    assert r.status_code == 200
    until = r.json()["muted_until_ms"]
    assert until >= before + 60_000 - 5_000

    r = await client.delete("/api/telegram/mute")
    assert r.json()["muted_until_ms"] == 0


@pytest.mark.asyncio
async def test_test_alert_records_failure_when_unconfigured(client):
    r = await client.post("/api/telegram/test")
    assert r.status_code == 200
    body = r.json()
    assert body["delivered"] is False
    assert "empty" in body["detail"]
    # Failure still lands on the /alerts page.
    rows = (await client.get("/api/alerts")).json()
    assert any(
        a["alert_type"] == "hub_started" and a["delivered"] == 0
        for a in rows
    )


@pytest.mark.asyncio
async def test_alerts_list_filters_by_type_and_limit(client):
    for _ in range(3):
        await client.post("/api/telegram/test")
    r = await client.get("/api/alerts?alert_type=hub_started&limit=2")
    rows = r.json()
    assert len(rows) == 2
    assert all(a["alert_type"] == "hub_started" for a in rows)


@pytest.mark.asyncio
async def test_alerts_list_filters_by_delivered(client):
    # Insert one delivered and one not via direct DB write.
    async with aiosqlite.connect(database.DB_PATH) as db:
        now = int(time.time() * 1000)
        await db.execute(
            "INSERT INTO alerts_history "
            "(alert_type, terminal_id, message, channel, sent_at, delivered, "
            "retry_count, deduplicated, muted) "
            "VALUES (?, ?, ?, 'telegram', ?, ?, 0, 0, 0)",
            ("ack_timeout", "m1", "ok-row", now, 1),
        )
        await db.execute(
            "INSERT INTO alerts_history "
            "(alert_type, terminal_id, message, channel, sent_at, delivered, "
            "retry_count, deduplicated, muted) "
            "VALUES (?, ?, ?, 'telegram', ?, ?, 0, 0, 0)",
            ("ack_timeout", "m1", "fail-row", now, 0),
        )
        await db.commit()

    delivered = (await client.get("/api/alerts?delivered=1")).json()
    assert all(a["delivered"] == 1 for a in delivered)
    assert any(a["message"] == "ok-row" for a in delivered)

    failed = (await client.get("/api/alerts?delivered=0")).json()
    assert all(a["delivered"] == 0 for a in failed)
    assert any(a["message"] == "fail-row" for a in failed)
