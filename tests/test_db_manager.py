import pytest
from hub.db.manager import DatabaseManager


@pytest.fixture
async def db():
    mgr = DatabaseManager(":memory:")
    await mgr.initialize()
    yield mgr
    await mgr.close()


@pytest.mark.asyncio
async def test_initialize_creates_tables(db):
    tables = await db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    names = [r["name"] for r in tables]
    assert "terminals" in names
    assert "master_slave_links" in names
    assert "messages" in names


@pytest.mark.asyncio
async def test_register_terminal(db):
    await db.register_terminal("master_1", "master", 12345, "Broker-Live")
    row = await db.fetch_one(
        "SELECT * FROM terminals WHERE terminal_id = ?", ("master_1",)
    )
    assert row["role"] == "master"
    assert row["account_number"] == 12345
    assert row["status"] == "Starting"


@pytest.mark.asyncio
async def test_register_terminal_idempotent(db):
    await db.register_terminal("slave_1", "slave", 67890, "Broker-Demo")
    await db.register_terminal("slave_1", "slave", 67890, "Broker-Demo")
    rows = await db.fetch_all(
        "SELECT * FROM terminals WHERE terminal_id = ?", ("slave_1",)
    )
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_update_terminal_status(db):
    await db.register_terminal("master_1", "master", 12345, "Broker-Live")
    await db.update_terminal_status("master_1", "Active", "")
    row = await db.fetch_one(
        "SELECT status FROM terminals WHERE terminal_id = ?", ("master_1",)
    )
    assert row["status"] == "Active"
