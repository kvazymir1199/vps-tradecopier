from dataclasses import dataclass
from enum import StrEnum


class MessageType(StrEnum):
    OPEN = "OPEN"
    MODIFY = "MODIFY"
    CLOSE = "CLOSE"
    CLOSE_PARTIAL = "CLOSE_PARTIAL"
    HEARTBEAT = "HEARTBEAT"
    REGISTER = "REGISTER"


@dataclass
class MasterMessage:
    msg_id: int
    master_id: str
    type: MessageType
    ts_ms: int
    payload: dict


@dataclass
class SlaveCommand:
    msg_id: int
    master_id: str
    slave_id: str
    type: MessageType
    ts_ms: int
    payload: dict


@dataclass
class AckMessage:
    msg_id: int
    slave_id: str
    ack_type: str  # "ACK" or "NACK"
    ts_ms: int
    slave_ticket: int | None = None
    reason: str | None = None
