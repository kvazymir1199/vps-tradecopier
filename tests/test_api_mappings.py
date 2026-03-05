"""Tests for symbol and magic mapping API routers."""

from __future__ import annotations

import time
from pathlib import Path

import aiosqlite
import pytest
import httpx
from httpx import ASGITransport

from web.api.database import set_db_path
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
            ("M1", "master", 12345, "Broker", "Active", "", now, now),
        )
        await db.execute(
            "INSERT INTO terminals VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("S1", "slave", 67890, "Broker", "Active", "", now, now),
        )
        await db.execute(
            """INSERT INTO master_slave_links
               (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at)
               VALUES (?, ?, 1, 'multiplier', 1.0, '', ?)""",
            ("M1", "S1", now),
        )
        await db.commit()

    set_db_path(db_path)
    app = create_app()

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Symbol mappings ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_symbol_mapping(client):
    resp = await client.post("/api/links/1/symbol-mappings", json={
        "master_symbol": "EURUSD",
        "slave_symbol": "EURUSDm",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["link_id"] == 1
    assert data["master_symbol"] == "EURUSD"
    assert data["slave_symbol"] == "EURUSDm"


@pytest.mark.asyncio
async def test_list_symbol_mappings(client):
    await client.post("/api/links/1/symbol-mappings", json={
        "master_symbol": "EURUSD", "slave_symbol": "EURUSDm",
    })
    await client.post("/api/links/1/symbol-mappings", json={
        "master_symbol": "GBPUSD", "slave_symbol": "GBPUSDm",
    })

    resp = await client.get("/api/links/1/symbol-mappings")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_create_duplicate_symbol_mapping(client):
    await client.post("/api/links/1/symbol-mappings", json={
        "master_symbol": "EURUSD", "slave_symbol": "EURUSDm",
    })
    resp = await client.post("/api/links/1/symbol-mappings", json={
        "master_symbol": "EURUSD", "slave_symbol": "EURUSDx",
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_symbol_mapping(client):
    create = await client.post("/api/links/1/symbol-mappings", json={
        "master_symbol": "EURUSD", "slave_symbol": "EURUSDm",
    })
    mapping_id = create.json()["id"]

    resp = await client.delete(f"/api/symbol-mappings/{mapping_id}")
    assert resp.status_code == 204

    resp = await client.get("/api/links/1/symbol-mappings")
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_delete_symbol_mapping_not_found(client):
    resp = await client.delete("/api/symbol-mappings/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_symbol_mapping_link_not_found(client):
    resp = await client.post("/api/links/9999/symbol-mappings", json={
        "master_symbol": "EURUSD", "slave_symbol": "EURUSDm",
    })
    assert resp.status_code == 404


# ── Magic mappings ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_magic_mapping(client):
    resp = await client.post("/api/links/1/magic-mappings", json={
        "master_setup_id": 100,
        "slave_setup_id": 200,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["link_id"] == 1
    assert data["master_setup_id"] == 100
    assert data["slave_setup_id"] == 200


@pytest.mark.asyncio
async def test_list_magic_mappings(client):
    await client.post("/api/links/1/magic-mappings", json={
        "master_setup_id": 100, "slave_setup_id": 200,
    })
    await client.post("/api/links/1/magic-mappings", json={
        "master_setup_id": 101, "slave_setup_id": 201,
    })

    resp = await client.get("/api/links/1/magic-mappings")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_create_duplicate_magic_mapping(client):
    await client.post("/api/links/1/magic-mappings", json={
        "master_setup_id": 100, "slave_setup_id": 200,
    })
    resp = await client.post("/api/links/1/magic-mappings", json={
        "master_setup_id": 100, "slave_setup_id": 999,
    })
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_delete_magic_mapping(client):
    create = await client.post("/api/links/1/magic-mappings", json={
        "master_setup_id": 100, "slave_setup_id": 200,
    })
    mapping_id = create.json()["id"]

    resp = await client.delete(f"/api/magic-mappings/{mapping_id}")
    assert resp.status_code == 204

    resp = await client.get("/api/links/1/magic-mappings")
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_delete_magic_mapping_not_found(client):
    resp = await client.delete("/api/magic-mappings/9999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_magic_mapping_link_not_found(client):
    resp = await client.post("/api/links/9999/magic-mappings", json={
        "master_setup_id": 100, "slave_setup_id": 200,
    })
    assert resp.status_code == 404
