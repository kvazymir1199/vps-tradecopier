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
