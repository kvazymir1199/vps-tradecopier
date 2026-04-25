import pytest
from hub.router.router import Router, ResendWindow
from hub.db.manager import DatabaseManager
from hub.protocol.models import MasterMessage, MessageType


@pytest.fixture
async def router():
    db = DatabaseManager(":memory:")
    await db.initialize()
    await db.register_terminal("master_1", "master", 111, "B1")
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.execute(
        "INSERT INTO master_slave_links (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at) "
        "VALUES ('master_1', 'slave_1', 1, 'multiplier', 2.0, '', 0)"
    )
    await db.execute(
        "INSERT INTO magic_mappings (link_id, master_setup_id, slave_setup_id) VALUES (1, 1, 5)"
    )
    r = Router(db)
    yield r
    await db.close()


@pytest.mark.asyncio
async def test_route_open_message(router):
    msg = MasterMessage(
        msg_id=1, master_id="master_1", type=MessageType.OPEN, ts_ms=170,
        payload={"ticket": 123, "symbol": "EURUSD", "direction": "BUY",
                 "volume": 0.1, "price": 1.085, "sl": 1.082, "tp": 1.089,
                 "magic": 15010301, "comment": "S01"},
    )
    commands = await router.route(msg)
    assert len(commands) == 1
    cmd = commands[0]
    assert cmd.slave_id == "slave_1"
    assert cmd.payload["symbol"] == "EURUSD"
    assert cmd.payload["volume"] == 0.2
    assert cmd.payload["magic"] == 15010305


@pytest.mark.asyncio
async def test_route_no_active_links(router):
    await router._db.execute("UPDATE master_slave_links SET enabled = 0 WHERE id = 1")
    msg = MasterMessage(
        msg_id=1, master_id="master_1", type=MessageType.OPEN, ts_ms=170,
        payload={"ticket": 123, "symbol": "EURUSD", "direction": "BUY",
                 "volume": 0.1, "price": 1.085, "sl": 1.082, "tp": 1.089,
                 "magic": 15010301, "comment": "S01"},
    )
    commands = await router.route(msg)
    assert len(commands) == 0


@pytest.mark.asyncio
async def test_route_skips_heartbeat(router):
    msg = MasterMessage(
        msg_id=1, master_id="master_1", type=MessageType.HEARTBEAT, ts_ms=170,
        payload={},
    )
    commands = await router.route(msg)
    assert len(commands) == 0


def test_resend_window_duplicate():
    rw = ResendWindow(max_size=5)
    rw.add("master_1", 1)
    assert rw.is_duplicate("master_1", 1) is True
    assert rw.is_duplicate("master_1", 2) is False


def test_resend_window_eviction():
    rw = ResendWindow(max_size=3)
    rw.add("m1", 1)
    rw.add("m1", 2)
    rw.add("m1", 3)
    rw.add("m1", 4)  # evicts 1
    assert rw.is_duplicate("m1", 1) is False
    assert rw.is_duplicate("m1", 2) is True


@pytest.mark.asyncio
async def test_route_duplicate_msg_id_skipped(router):
    msg = MasterMessage(
        msg_id=1, master_id="master_1", type=MessageType.OPEN, ts_ms=170,
        payload={"ticket": 123, "symbol": "EURUSD", "direction": "BUY",
                 "volume": 0.1, "price": 1.085, "sl": 1.082, "tp": 1.089,
                 "magic": 15010301, "comment": "S01"},
    )
    commands1 = await router.route(msg)
    commands2 = await router.route(msg)  # duplicate
    assert len(commands1) == 1
    assert len(commands2) == 0


@pytest.fixture
async def router_fixed():
    """Router with fixed lot mode (lot_value=0.20)."""
    db = DatabaseManager(":memory:")
    await db.initialize()
    await db.register_terminal("master_1", "master", 111, "B1")
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.execute(
        "INSERT INTO master_slave_links (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at) "
        "VALUES ('master_1', 'slave_1', 1, 'fixed', 0.20, '', 0)"
    )
    await db.execute(
        "INSERT INTO magic_mappings (link_id, master_setup_id, slave_setup_id) VALUES (1, 1, 5)"
    )
    r = Router(db)
    yield r
    await db.close()


@pytest.mark.asyncio
async def test_route_close_partial_proportional(router_fixed):
    """CLOSE_PARTIAL with fixed lot should use proportional volume."""
    msg = MasterMessage(
        msg_id=1, master_id="master_1", type=MessageType.CLOSE_PARTIAL, ts_ms=170,
        payload={"ticket": 123, "symbol": "EURUSD",
                 "volume": 0.05,
                 "master_open_volume": 0.10,
                 "magic": 15010301},
    )
    commands = await router_fixed.route(msg)
    assert len(commands) == 1
    # fixed mode: slave_open = lot_value = 0.20
    # proportional: (0.05 / 0.10) * 0.20 = 0.10
    assert commands[0].payload["volume"] == 0.10


@pytest.mark.asyncio
async def test_route_close_partial_multiplier(router):
    """CLOSE_PARTIAL with multiplier should scale close volume."""
    msg = MasterMessage(
        msg_id=1, master_id="master_1", type=MessageType.CLOSE_PARTIAL, ts_ms=170,
        payload={"ticket": 123, "symbol": "EURUSD",
                 "volume": 0.05,
                 "master_open_volume": 0.10,
                 "magic": 15010301},
    )
    commands = await router.route(msg)
    assert len(commands) == 1
    # multiplier mode (2.0): 0.05 * 2.0 = 0.10
    assert commands[0].payload["volume"] == 0.10


@pytest.mark.asyncio
async def test_route_pending_place_message(router):
    """PENDING_PLACE should route with volume mapping applied."""
    msg = MasterMessage(
        msg_id=2, master_id="master_1", type=MessageType.PENDING_PLACE, ts_ms=170,
        payload={"ticket": 456, "symbol": "EURUSD", "order_type": "BUY_LIMIT",
                 "volume": 0.1, "price": 1.080, "sl": 1.075, "tp": 1.090,
                 "magic": 15010301, "comment": ""},
    )
    commands = await router.route(msg)
    assert len(commands) == 1
    cmd = commands[0]
    assert cmd.type == MessageType.PENDING_PLACE
    assert cmd.slave_id == "slave_1"
    assert cmd.payload["order_type"] == "BUY_LIMIT"
    assert cmd.payload["price"] == 1.080
    assert cmd.payload["volume"] == 0.2  # multiplier 2.0
    assert cmd.payload["magic"] == 15010305


@pytest.mark.asyncio
async def test_route_pending_modify_no_volume_override(router):
    """PENDING_MODIFY should NOT override volume in payload."""
    msg = MasterMessage(
        msg_id=3, master_id="master_1", type=MessageType.PENDING_MODIFY, ts_ms=170,
        payload={"ticket": 456, "magic": 15010301,
                 "price": 1.082, "sl": 1.077, "tp": 1.092},
    )
    commands = await router.route(msg)
    assert len(commands) == 1
    cmd = commands[0]
    assert cmd.type == MessageType.PENDING_MODIFY
    assert "volume" not in cmd.payload or cmd.payload.get("volume") is None or cmd.payload.get("volume") == 0


@pytest.mark.asyncio
async def test_route_pending_delete_message(router):
    """PENDING_DELETE should route correctly."""
    msg = MasterMessage(
        msg_id=4, master_id="master_1", type=MessageType.PENDING_DELETE, ts_ms=170,
        payload={"ticket": 456, "magic": 15010301},
    )
    commands = await router.route(msg)
    assert len(commands) == 1
    cmd = commands[0]
    assert cmd.type == MessageType.PENDING_DELETE
    assert cmd.payload["magic"] == 15010305


@pytest.mark.asyncio
async def test_route_skips_slave_without_magic_mapping():
    """Command must NOT be sent if no magic_mapping exists for the setup_id."""
    db = DatabaseManager(":memory:")
    await db.initialize()
    await db.register_terminal("master_1", "master", 111, "B1")
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.execute(
        "INSERT INTO master_slave_links (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at) "
        "VALUES ('master_1', 'slave_1', 1, 'multiplier', 2.0, '', 0)"
    )
    # Deliberately NO magic_mappings inserted
    r = Router(db)
    msg = MasterMessage(
        msg_id=1, master_id="master_1", type=MessageType.OPEN, ts_ms=170,
        payload={"ticket": 123, "symbol": "EURUSD", "direction": "BUY",
                 "volume": 0.1, "price": 1.085, "sl": 1.082, "tp": 1.089,
                 "magic": 15010301, "comment": ""},
    )
    commands = await r.route(msg)
    assert len(commands) == 0
    await db.close()


@pytest.mark.asyncio
async def test_route_uses_computed_magic_not_master_magic():
    """When magic mapping IS present, slave_magic must be computed (not master_magic)."""
    db = DatabaseManager(":memory:")
    await db.initialize()
    await db.register_terminal("master_1", "master", 111, "B1")
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.execute(
        "INSERT INTO master_slave_links (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at) "
        "VALUES ('master_1', 'slave_1', 1, 'multiplier', 1.0, '', 0)"
    )
    await db.execute(
        "INSERT INTO magic_mappings (link_id, master_setup_id, slave_setup_id) VALUES (1, 1, 7)"
    )
    r = Router(db)
    msg = MasterMessage(
        msg_id=1, master_id="master_1", type=MessageType.OPEN, ts_ms=170,
        payload={"ticket": 123, "symbol": "EURUSD", "direction": "BUY",
                 "volume": 0.1, "price": 1.085, "sl": 1.082, "tp": 1.089,
                 "magic": 15010301, "comment": ""},
    )
    commands = await r.route(msg)
    assert len(commands) == 1
    assert commands[0].payload["magic"] == 15010307  # not 15010301
    await db.close()


@pytest.mark.asyncio
async def test_route_open_blocked_by_allowed_direction_mismatch():
    """OPEN with direction=BUY must be blocked when mapping's allowed_direction=SELL."""
    db = DatabaseManager(":memory:")
    await db.initialize()
    await db.register_terminal("master_1", "master", 111, "B1")
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.execute(
        "INSERT INTO master_slave_links (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at) "
        "VALUES ('master_1', 'slave_1', 1, 'multiplier', 1.0, '', 0)"
    )
    await db.execute(
        "INSERT INTO magic_mappings (link_id, master_setup_id, slave_setup_id, allowed_direction) "
        "VALUES (1, 1, 5, 'SELL')"
    )
    r = Router(db)
    msg = MasterMessage(
        msg_id=1, master_id="master_1", type=MessageType.OPEN, ts_ms=170,
        payload={"ticket": 123, "symbol": "EURUSD", "direction": "BUY",
                 "volume": 0.1, "price": 1.085, "sl": 1.082, "tp": 1.089,
                 "magic": 15010301, "comment": ""},
    )
    commands = await r.route(msg)
    assert len(commands) == 0
    await db.close()


@pytest.mark.asyncio
async def test_route_open_allowed_when_direction_matches():
    """OPEN with direction=BUY must pass when mapping's allowed_direction=BUY."""
    db = DatabaseManager(":memory:")
    await db.initialize()
    await db.register_terminal("master_1", "master", 111, "B1")
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.execute(
        "INSERT INTO master_slave_links (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at) "
        "VALUES ('master_1', 'slave_1', 1, 'multiplier', 1.0, '', 0)"
    )
    await db.execute(
        "INSERT INTO magic_mappings (link_id, master_setup_id, slave_setup_id, allowed_direction) "
        "VALUES (1, 1, 5, 'BUY')"
    )
    r = Router(db)
    msg = MasterMessage(
        msg_id=1, master_id="master_1", type=MessageType.OPEN, ts_ms=170,
        payload={"ticket": 123, "symbol": "EURUSD", "direction": "BUY",
                 "volume": 0.1, "price": 1.085, "sl": 1.082, "tp": 1.089,
                 "magic": 15010301, "comment": ""},
    )
    commands = await r.route(msg)
    assert len(commands) == 1
    await db.close()


@pytest.mark.asyncio
async def test_route_close_passes_regardless_of_allowed_direction():
    """CLOSE/MODIFY carry no direction — must pass even when allowed_direction is restricted."""
    db = DatabaseManager(":memory:")
    await db.initialize()
    await db.register_terminal("master_1", "master", 111, "B1")
    await db.register_terminal("slave_1", "slave", 222, "B2")
    await db.execute(
        "INSERT INTO master_slave_links (master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at) "
        "VALUES ('master_1', 'slave_1', 1, 'multiplier', 1.0, '', 0)"
    )
    await db.execute(
        "INSERT INTO magic_mappings (link_id, master_setup_id, slave_setup_id, allowed_direction) "
        "VALUES (1, 1, 5, 'BUY')"
    )
    r = Router(db)
    msg = MasterMessage(
        msg_id=1, master_id="master_1", type=MessageType.CLOSE, ts_ms=170,
        payload={"ticket": 123, "magic": 15010301},
    )
    commands = await r.route(msg)
    assert len(commands) == 1
    await db.close()
