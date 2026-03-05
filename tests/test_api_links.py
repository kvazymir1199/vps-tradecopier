"""Tests for the links API router."""

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
            ("M2", "master", 12346, "Broker", "Active", "", now, now),
        )
        await db.execute(
            "INSERT INTO terminals VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("S1", "slave", 67890, "Broker", "Active", "", now, now),
        )
        await db.execute(
            "INSERT INTO terminals VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("S2", "slave", 67891, "Broker", "Active", "", now, now),
        )
        await db.commit()

    set_db_path(db_path)
    app = create_app()

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_link(client):
    resp = await client.post("/api/links", json={
        "master_id": "M1",
        "slave_id": "S1",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["master_id"] == "M1"
    assert data["slave_id"] == "S1"
    assert data["enabled"] == 1
    assert data["lot_mode"] == "multiplier"
    assert data["lot_value"] == 1.0


@pytest.mark.asyncio
async def test_create_link_invalid_roles(client):
    # slave as master
    resp = await client.post("/api/links", json={
        "master_id": "S1",
        "slave_id": "S2",
    })
    assert resp.status_code == 400

    # master as slave
    resp = await client.post("/api/links", json={
        "master_id": "M1",
        "slave_id": "M2",
    })
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_duplicate_link(client):
    await client.post("/api/links", json={"master_id": "M1", "slave_id": "S1"})
    resp = await client.post("/api/links", json={"master_id": "M1", "slave_id": "S1"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_links(client):
    await client.post("/api/links", json={"master_id": "M1", "slave_id": "S1"})
    await client.post("/api/links", json={"master_id": "M2", "slave_id": "S1"})

    resp = await client.get("/api/links")
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    # Filter by master_id
    resp = await client.get("/api/links", params={"master_id": "M1"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["master_id"] == "M1"


@pytest.mark.asyncio
async def test_update_link(client):
    create = await client.post("/api/links", json={
        "master_id": "M1", "slave_id": "S1"
    })
    link_id = create.json()["id"]

    resp = await client.put(f"/api/links/{link_id}", json={
        "lot_mode": "fixed",
        "lot_value": 0.5,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["lot_mode"] == "fixed"
    assert data["lot_value"] == 0.5
    # enabled should remain unchanged
    assert data["enabled"] == 1


@pytest.mark.asyncio
async def test_toggle_link(client):
    create = await client.post("/api/links", json={
        "master_id": "M1", "slave_id": "S1"
    })
    link_id = create.json()["id"]

    resp = await client.patch(f"/api/links/{link_id}/toggle")
    assert resp.status_code == 200
    assert resp.json()["enabled"] == 0

    resp = await client.patch(f"/api/links/{link_id}/toggle")
    assert resp.status_code == 200
    assert resp.json()["enabled"] == 1


@pytest.mark.asyncio
async def test_delete_link(client):
    create = await client.post("/api/links", json={
        "master_id": "M1", "slave_id": "S1"
    })
    link_id = create.json()["id"]

    resp = await client.delete(f"/api/links/{link_id}")
    assert resp.status_code == 204

    resp = await client.get("/api/links")
    assert len(resp.json()) == 0


@pytest.mark.asyncio
async def test_delete_link_not_found(client):
    resp = await client.delete("/api/links/9999")
    assert resp.status_code == 404
