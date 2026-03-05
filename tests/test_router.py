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
        "VALUES ('master_1', 'slave_1', 1, 'multiplier', 2.0, '.s', 0)"
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
    assert cmd.payload["symbol"] == "EURUSD.s"
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
