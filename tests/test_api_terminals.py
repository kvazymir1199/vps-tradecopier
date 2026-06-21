"""Tests for the terminals API router."""

from __future__ import annotations

import time
from pathlib import Path

import aiosqlite
import pytest
import httpx
from httpx import ASGITransport

import web.api.database as database
from web.api.main import create_app

SCHEMA = (Path(__file__).resolve().parent.parent / "hub" / "db" / "schema.sql").read_text()


@pytest.fixture
async def client(tmp_path):
    db_path = str(tmp_path / "test.db")

    async with aiosqlite.connect(db_path) as db:
        await db.executescript(SCHEMA)
        now = int(time.time())
        await db.execute(
            "INSERT INTO terminals VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("M1", "master", 12345, "Broker-Server", "Active", "", now, now),
        )
        await db.execute(
            "INSERT INTO terminals VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("S1", "slave", 67890, "Broker-Server", "Active", "", now, now),
        )
        await db.commit()

    database.DB_PATH = db_path
    app = create_app()

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_list_terminals(client):
    resp = await client.get("/api/terminals")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    ids = {t["terminal_id"] for t in data}
    assert ids == {"M1", "S1"}


@pytest.mark.asyncio
async def test_get_terminal(client):
    resp = await client.get("/api/terminals/M1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["terminal_id"] == "M1"
    assert data["role"] == "master"
    assert data["account_number"] == 12345


@pytest.mark.asyncio
async def test_get_terminal_not_found(client):
    resp = await client.get("/api/terminals/NOPE")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_terminal(client):
    resp = await client.post("/api/terminals", json={"terminal_id": "M2", "role": "master"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["terminal_id"] == "M2"
    assert data["role"] == "master"
    assert data["status"] == "Disconnected"
    # created_at/last_heartbeat are stored in ms, so well above a seconds-epoch value
    assert data["last_heartbeat"] > 1_000_000_000_000


@pytest.mark.asyncio
async def test_create_terminal_duplicate(client):
    resp = await client.post("/api/terminals", json={"terminal_id": "M1", "role": "master"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_terminal_bad_role(client):
    resp = await client.post("/api/terminals", json={"terminal_id": "X1", "role": "boss"})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_terminal_not_found(client):
    resp = await client.delete("/api/terminals/NOPE")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_terminal_cascade(client):
    # Build a link M1->S1 with a magic + symbol mapping via the API
    link = (await client.post("/api/links", json={"master_id": "M1", "slave_id": "S1"})).json()
    link_id = link["id"]
    await client.post(f"/api/links/{link_id}/magic-mappings", json={
        "master_setup_id": 1, "slave_setup_id": 5, "allowed_direction": "BOTH",
    })
    await client.post(f"/api/links/{link_id}/symbol-mappings", json={
        "master_symbol": "EURUSD", "slave_symbol": "EURUSDm",
    })
    # Insert a heartbeat row directly (no API for it); database.DB_PATH was set by the fixture
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute(
            "INSERT INTO heartbeats (terminal_id, vps_id, ts_ms, status_code) VALUES (?, ?, ?, ?)",
            ("M1", "vps_1", int(time.time() * 1000), 0),
        )
        await db.commit()

    resp = await client.delete("/api/terminals/M1")
    assert resp.status_code == 204

    # Terminal, link, mappings and heartbeats for M1 are all gone
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        assert (await (await db.execute(
            "SELECT COUNT(*) c FROM terminals WHERE terminal_id='M1'")).fetchone())["c"] == 0
        assert (await (await db.execute(
            "SELECT COUNT(*) c FROM master_slave_links WHERE id=?", (link_id,))).fetchone())["c"] == 0
        assert (await (await db.execute(
            "SELECT COUNT(*) c FROM magic_mappings WHERE link_id=?", (link_id,))).fetchone())["c"] == 0
        assert (await (await db.execute(
            "SELECT COUNT(*) c FROM symbol_mappings WHERE link_id=?", (link_id,))).fetchone())["c"] == 0
        assert (await (await db.execute(
            "SELECT COUNT(*) c FROM heartbeats WHERE terminal_id='M1'")).fetchone())["c"] == 0
