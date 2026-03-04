import json
from hub.protocol.serializer import encode_master_message, decode_master_message, encode_slave_command, decode_ack
from hub.protocol.models import MasterMessage, SlaveCommand, AckMessage, MessageType

def test_encode_decode_master_message_roundtrip():
    msg = MasterMessage(msg_id=1, master_id="master_1", type=MessageType.OPEN, ts_ms=1700000000000,
                        payload={"ticket": 123, "symbol": "EURUSD"})
    encoded = encode_master_message(msg)
    assert isinstance(encoded, str)
    assert encoded.endswith("\n")
    decoded = decode_master_message(encoded)
    assert decoded.msg_id == 1
    assert decoded.payload["ticket"] == 123

def test_encode_slave_command():
    cmd = SlaveCommand(msg_id=1, master_id="m1", slave_id="s1", type=MessageType.OPEN, ts_ms=170,
                       payload={"master_ticket": 123, "symbol": "EURUSD.s"})
    encoded = encode_slave_command(cmd)
    data = json.loads(encoded.strip())
    assert data["slave_id"] == "s1"

def test_decode_ack():
    raw = '{"msg_id": 1, "slave_id": "s1", "ack_type": "ACK", "slave_ticket": 999, "ts_ms": 170}\n'
    ack = decode_ack(raw)
    assert ack.slave_ticket == 999

def test_decode_nack():
    raw = '{"msg_id": 1, "slave_id": "s1", "ack_type": "NACK", "reason": "SYMBOL_NOT_FOUND", "ts_ms": 170}\n'
    ack = decode_ack(raw)
    assert ack.ack_type == "NACK"
    assert ack.reason == "SYMBOL_NOT_FOUND"
