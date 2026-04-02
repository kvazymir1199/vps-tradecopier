from collections import deque

from hub.db.manager import DatabaseManager
from hub.protocol.models import MasterMessage, SlaveCommand, MessageType
from hub.mapping.magic import compute_slave_magic, parse_master_magic
from hub.mapping.symbol import resolve_symbol
from hub.mapping.lot import compute_slave_volume, compute_partial_close_volume


class ResendWindow:
    """Maintains last N messages per master_id for replay."""

    def __init__(self, max_size: int = 200):
        self._max_size = max_size
        self._windows: dict[str, deque[int]] = {}

    def is_duplicate(self, master_id: str, msg_id: int) -> bool:
        if master_id not in self._windows:
            return False
        return msg_id in self._windows[master_id]

    def add(self, master_id: str, msg_id: int):
        if master_id not in self._windows:
            self._windows[master_id] = deque(maxlen=self._max_size)
        self._windows[master_id].append(msg_id)

    def get_pending(self, master_id: str) -> list[int]:
        return list(self._windows.get(master_id, []))


class Router:
    def __init__(self, db: DatabaseManager, resend_window_size: int = 200):
        self._db = db
        self._resend = ResendWindow(resend_window_size)

    async def route(self, msg: MasterMessage) -> list[SlaveCommand]:
        if msg.type in (MessageType.HEARTBEAT, MessageType.REGISTER):
            return []

        if self._resend.is_duplicate(msg.master_id, msg.msg_id):
            return []

        self._resend.add(msg.master_id, msg.msg_id)

        links = await self._db.get_active_links(msg.master_id)
        commands = []
        for link in links:
            cmd = await self._build_slave_command(msg, link)
            if cmd:
                commands.append(cmd)
        return commands

    async def _build_slave_command(self, msg: MasterMessage, link: dict) -> SlaveCommand | None:
        # Resolve symbol
        explicit_mappings = await self._db.get_symbol_mappings(link["id"])
        slave_symbol = resolve_symbol(msg.payload.get("symbol", ""), link.get("symbol_suffix", ""), explicit_mappings)

        # Resolve magic
        master_magic = msg.payload.get("magic", 0)
        parsed = parse_master_magic(master_magic)
        magic_map = await self._db.get_magic_mappings(link["id"])
        slave_setup_id = magic_map.get(parsed["setup_id"])
        slave_magic = compute_slave_magic(master_magic, slave_setup_id) if slave_setup_id is not None else master_magic

        # Resolve volume
        slave_volume = compute_slave_volume(
            msg.payload.get("volume", 0), link["lot_mode"], link["lot_value"]
        )

        # Build payload
        payload = {**msg.payload}
        payload["master_ticket"] = payload.pop("ticket", None)
        payload["symbol"] = slave_symbol
        payload["magic"] = slave_magic
        payload["comment"] = f"Copy:{msg.master_id}:{payload.get('master_ticket', '')}"

        # Apply volume mapping only for types that carry volume
        if msg.type == MessageType.CLOSE_PARTIAL:
            payload["volume"] = compute_partial_close_volume(
                msg.payload.get("volume", 0),
                link["lot_mode"], link["lot_value"],
                msg.payload.get("master_open_volume", msg.payload.get("volume", 0)),
                slave_volume,
            )
        elif msg.type in (MessageType.OPEN, MessageType.PENDING_PLACE):
            payload["volume"] = slave_volume

        return SlaveCommand(
            msg_id=msg.msg_id,
            master_id=msg.master_id,
            slave_id=link["slave_id"],
            type=msg.type,
            ts_ms=msg.ts_ms,
            payload=payload,
        )
