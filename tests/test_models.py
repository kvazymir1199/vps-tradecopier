from hub.protocol.models import MasterMessage, SlaveCommand, AckMessage, MessageType


def test_master_message_open():
    msg = MasterMessage(
        msg_id=1,
        master_id="master_1",
        type=MessageType.OPEN,
        ts_ms=1700000000000,
        payload={
            "ticket": 123, "symbol": "EURUSD", "direction": "BUY", "volume": 0.1,
            "price": 1.085, "sl": 1.082, "tp": 1.089, "magic": 15010301, "comment": "S01",
        },
    )
    assert msg.msg_id == 1
    assert msg.type == MessageType.OPEN


def test_slave_command_has_slave_fields():
    cmd = SlaveCommand(
        msg_id=1,
        master_id="master_1",
        slave_id="slave_1",
        type=MessageType.OPEN,
        ts_ms=1700000000000,
        payload={
            "master_ticket": 123, "symbol": "EURUSD.s", "direction": "BUY", "volume": 0.2,
            "price": 1.085, "sl": 1.082, "tp": 1.089, "magic": 15010305,
            "comment": "Copy:master_1:123",
        },
    )
    assert cmd.slave_id == "slave_1"


def test_ack_message():
    ack = AckMessage(
        msg_id=1, slave_id="slave_1", ack_type="ACK", slave_ticket=87654321, ts_ms=1700000000500
    )
    assert ack.ack_type == "ACK"


def test_nack_message():
    nack = AckMessage(
        msg_id=1, slave_id="slave_1", ack_type="NACK", reason="SYMBOL_NOT_FOUND", ts_ms=1700000000500
    )
    assert nack.reason == "SYMBOL_NOT_FOUND"
    assert nack.slave_ticket is None


def test_message_type_pending_values():
    assert MessageType.PENDING_PLACE == "PENDING_PLACE"
    assert MessageType.PENDING_MODIFY == "PENDING_MODIFY"
    assert MessageType.PENDING_DELETE == "PENDING_DELETE"


def test_master_message_pending_place():
    msg = MasterMessage(
        msg_id=10,
        master_id="master_1",
        type=MessageType.PENDING_PLACE,
        ts_ms=1700000000000,
        payload={
            "ticket": 456, "symbol": "EURUSD", "order_type": "BUY_LIMIT",
            "volume": 0.1, "price": 1.080, "sl": 1.075, "tp": 1.090,
            "magic": 15010301, "comment": "",
        },
    )
    assert msg.type == MessageType.PENDING_PLACE
    assert msg.payload["order_type"] == "BUY_LIMIT"
