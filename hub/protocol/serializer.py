import json
from hub.protocol.models import MasterMessage, SlaveCommand, AckMessage, MessageType


def encode_master_message(msg: MasterMessage) -> str:
    data = {
        "msg_id": msg.msg_id,
        "master_id": msg.master_id,
        "type": str(msg.type),
        "ts_ms": msg.ts_ms,
        "payload": msg.payload,
    }
    return json.dumps(data) + "\n"


def decode_master_message(raw: str) -> MasterMessage:
    data = json.loads(raw.strip())
    return MasterMessage(
        msg_id=data["msg_id"],
        master_id=data["master_id"],
        type=MessageType(data["type"]),
        ts_ms=data["ts_ms"],
        payload=data["payload"],
    )


def encode_slave_command(cmd: SlaveCommand) -> str:
    data = {
        "msg_id": cmd.msg_id,
        "master_id": cmd.master_id,
        "slave_id": cmd.slave_id,
        "type": str(cmd.type),
        "ts_ms": cmd.ts_ms,
        "payload": cmd.payload,
    }
    return json.dumps(data) + "\n"


def decode_ack(raw: str) -> AckMessage:
    data = json.loads(raw.strip())
    return AckMessage(
        msg_id=data["msg_id"],
        slave_id=data["slave_id"],
        ack_type=data["ack_type"],
        ts_ms=data["ts_ms"],
        slave_ticket=data.get("slave_ticket"),
        reason=data.get("reason"),
    )
