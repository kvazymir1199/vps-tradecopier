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
