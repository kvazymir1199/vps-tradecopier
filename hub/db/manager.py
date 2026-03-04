import time
from pathlib import Path

import aiosqlite

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class DatabaseManager:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self):
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        await self._conn.executescript(schema)

    async def close(self):
        if self._conn:
            await self._conn.close()

    async def execute(self, sql: str, params: tuple = ()):
        await self._conn.execute(sql, params)
        await self._conn.commit()

    async def fetch_one(self, sql: str, params: tuple = ()):
        cursor = await self._conn.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def fetch_all(self, sql: str, params: tuple = ()):
        cursor = await self._conn.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    async def register_terminal(
        self,
        terminal_id: str,
        role: str,
        account_number: int,
        broker_server: str,
    ):
        now = self._now_ms()
        await self._conn.execute(
            "INSERT OR IGNORE INTO terminals "
            "(terminal_id, role, account_number, broker_server, status, created_at, last_heartbeat) "
            "VALUES (?, ?, ?, ?, 'Starting', ?, ?)",
            (terminal_id, role, account_number, broker_server, now, now),
        )
        await self._conn.commit()

    async def update_terminal_status(
        self, terminal_id: str, status: str, status_message: str = ""
    ):
        await self._conn.execute(
            "UPDATE terminals SET status = ?, status_message = ? WHERE terminal_id = ?",
            (status, status_message, terminal_id),
        )
        await self._conn.commit()

    async def insert_message(
        self, msg_id: int, master_id: str, msg_type: str, payload: str, ts_ms: int
    ):
        await self._conn.execute(
            "INSERT INTO messages (msg_id, master_id, type, payload, ts_ms, status) "
            "VALUES (?, ?, ?, ?, ?, 'pending')",
            (msg_id, master_id, msg_type, payload, ts_ms),
        )
        await self._conn.commit()

    async def update_message_status(
        self, msg_id: int, master_id: str, status: str
    ):
        await self._conn.execute(
            "UPDATE messages SET status = ? WHERE msg_id = ? AND master_id = ?",
            (status, msg_id, master_id),
        )
        await self._conn.commit()

    async def insert_ack(
        self,
        msg_id: int,
        master_id: str,
        slave_id: str,
        ack_type: str,
        nack_reason: str | None,
        slave_ticket: int | None,
        ts_ms: int,
    ):
        await self._conn.execute(
            "INSERT INTO message_acks "
            "(msg_id, master_id, slave_id, ack_type, nack_reason, slave_ticket, ts_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (msg_id, master_id, slave_id, ack_type, nack_reason, slave_ticket, ts_ms),
        )
        await self._conn.commit()

    async def insert_trade_mapping(
        self,
        master_id: str,
        slave_id: str,
        master_ticket: int,
        slave_ticket: int | None,
        master_magic: int,
        slave_magic: int,
        symbol: str,
        master_volume: float,
        slave_volume: float,
    ):
        now = self._now_ms()
        await self._conn.execute(
            "INSERT INTO trade_mappings "
            "(master_id, slave_id, master_ticket, slave_ticket, master_magic, slave_magic, "
            "symbol, master_volume, slave_volume, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)",
            (master_id, slave_id, master_ticket, slave_ticket, master_magic,
             slave_magic, symbol, master_volume, slave_volume, now),
        )
        await self._conn.commit()

    async def update_trade_mapping_ack(
        self, master_id: str, slave_id: str, master_ticket: int, slave_ticket: int
    ):
        await self._conn.execute(
            "UPDATE trade_mappings SET slave_ticket = ?, status = 'open' "
            "WHERE master_id = ? AND slave_id = ? AND master_ticket = ?",
            (slave_ticket, master_id, slave_id, master_ticket),
        )
        await self._conn.commit()

    async def update_trade_mapping_status(
        self, master_id: str, slave_id: str, master_ticket: int, status: str
    ):
        closed_at = self._now_ms() if status in ("closed", "failed") else None
        await self._conn.execute(
            "UPDATE trade_mappings SET status = ?, closed_at = ? "
            "WHERE master_id = ? AND slave_id = ? AND master_ticket = ?",
            (status, closed_at, master_id, slave_id, master_ticket),
        )
        await self._conn.commit()
