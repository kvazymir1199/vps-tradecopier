import time

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


@pytest.mark.asyncio
async def test_insert_message(db):
    await db.insert_message(1, "master_1", "OPEN", '{"ticket":123}', 1700000000000)
    row = await db.fetch_one(
        "SELECT * FROM messages WHERE msg_id = 1 AND master_id = 'master_1'"
    )
    assert row["type"] == "OPEN"
    assert row["status"] == "pending"


@pytest.mark.asyncio
async def test_insert_ack(db):
    await db.insert_message(1, "master_1", "OPEN", '{"ticket":123}', 1700000000000)
    await db.insert_ack(1, "master_1", "slave_1", "ACK", None, 87654321, 1700000000500)
    row = await db.fetch_one(
        "SELECT * FROM message_acks WHERE msg_id = 1 AND slave_id = 'slave_1'"
    )
    assert row["ack_type"] == "ACK"
    assert row["slave_ticket"] == 87654321


@pytest.mark.asyncio
async def test_insert_trade_mapping(db):
    await db.insert_trade_mapping(
        "master_1", "slave_1", 123, None, 15010301, 15010305, "EURUSD.s", 0.1, 0.2
    )
    row = await db.fetch_one(
        "SELECT * FROM trade_mappings WHERE master_ticket = 123"
    )
    assert row["status"] == "pending"
    assert row["slave_magic"] == 15010305


@pytest.mark.asyncio
async def test_update_trade_mapping_on_ack(db):
    await db.insert_trade_mapping(
        "master_1", "slave_1", 123, None, 15010301, 15010305, "EURUSD.s", 0.1, 0.2
    )
    await db.update_trade_mapping_ack("master_1", "slave_1", 123, slave_ticket=87654321)
    row = await db.fetch_one(
        "SELECT * FROM trade_mappings WHERE master_ticket = 123"
    )
    assert row["status"] == "open"
    assert row["slave_ticket"] == 87654321


@pytest.mark.asyncio
async def test_update_trade_mapping_closed(db):
    await db.insert_trade_mapping(
        "master_1", "slave_1", 123, None, 15010301, 15010305, "EURUSD.s", 0.1, 0.2
    )
    await db.update_trade_mapping_ack("master_1", "slave_1", 123, slave_ticket=87654321)
    await db.update_trade_mapping_status("master_1", "slave_1", 123, "closed")
    row = await db.fetch_one(
        "SELECT * FROM trade_mappings WHERE master_ticket = 123"
    )
    assert row["status"] == "closed"
    assert row["closed_at"] is not None


@pytest.mark.asyncio
async def test_get_active_links_for_master(db):
    await db.register_terminal("master_1", "master", 111, "B1")
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.register_terminal("slave_2", "slave", 333, "B3")
    await db.execute(
        "INSERT INTO master_slave_links (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at) VALUES (?, ?, 1, 'multiplier', 2.0, '.s', ?)",
        ("master_1", "slave_1", 1700000000000),
    )
    await db.execute(
        "INSERT INTO master_slave_links (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at) VALUES (?, ?, 0, 'fixed', 0.05, '.f', ?)",
        ("master_1", "slave_2", 1700000000000),
    )
    links = await db.get_active_links("master_1")
    assert len(links) == 1
    assert links[0]["slave_id"] == "slave_1"
    assert links[0]["lot_mode"] == "multiplier"


@pytest.mark.asyncio
async def test_insert_heartbeat(db):
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.insert_heartbeat("slave_1", "vps_1", 1700000000000, 0, "Active", "")
    row = await db.fetch_one(
        "SELECT * FROM heartbeats WHERE terminal_id = 'slave_1'"
    )
    assert row["vps_id"] == "vps_1"
    term = await db.fetch_one(
        "SELECT last_heartbeat FROM terminals WHERE terminal_id = 'slave_1'"
    )
    assert term["last_heartbeat"] == 1700000000000


@pytest.mark.asyncio
async def test_purge_old_heartbeats(db):
    await db.register_terminal("slave_1", "slave", 222, "B2")
    old_ts = 1700000000000
    new_ts = int(time.time() * 1000)
    await db.insert_heartbeat("slave_1", "vps_1", old_ts, 0, "Active", "")
    await db.insert_heartbeat("slave_1", "vps_1", new_ts, 0, "Active", "")
    await db.purge_old_heartbeats(max_age_days=0)
    rows = await db.fetch_all("SELECT * FROM heartbeats")
    assert len(rows) <= 1
