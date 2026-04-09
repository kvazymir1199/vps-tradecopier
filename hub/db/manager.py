import time
from pathlib import Path

import aiosqlite

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


class DatabaseManager:
    def __init__(self, db_path: str):
        self._db_path = db_path
        self._conn: aiosqlite.Connection | None = None

    async def initialize(self):
        # Ensure parent directory exists (e.g. Common\Files\TradeCopier\)
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        await self._conn.executescript(schema)
        await self._run_migrations()

    async def _run_migrations(self):
        """Apply incremental migrations for existing databases."""
        # Migration: add order_type column to trade_mappings (for pending orders support)
        cursor = await self._conn.execute("PRAGMA table_info(trade_mappings)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "order_type" not in columns:
            await self._conn.execute(
                "ALTER TABLE trade_mappings ADD COLUMN order_type TEXT DEFAULT NULL"
            )
            await self._conn.commit()

        # Migration: add retry_count column to messages
        cursor = await self._conn.execute("PRAGMA table_info(messages)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "retry_count" not in columns:
            await self._conn.execute(
                "ALTER TABLE messages ADD COLUMN retry_count INTEGER NOT NULL DEFAULT 0"
            )
            await self._conn.commit()

        # Migration: recreate messages table with updated CHECK constraint
        # (adds PENDING_PLACE, PENDING_MODIFY, PENDING_DELETE types)
        # Must disable FK checks to avoid constraint failures during table rename
        cursor = await self._conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='messages'"
        )
        row = await cursor.fetchone()
        if row and "PENDING_PLACE" not in row[0]:
            await self._conn.executescript("""
                PRAGMA foreign_keys = OFF;
                ALTER TABLE messages RENAME TO messages_old;
                CREATE TABLE messages (
                    msg_id   INTEGER NOT NULL,
                    master_id TEXT   NOT NULL,
                    type     TEXT    NOT NULL CHECK (type IN (
                        'OPEN', 'MODIFY', 'CLOSE', 'CLOSE_PARTIAL',
                        'PENDING_PLACE', 'PENDING_MODIFY', 'PENDING_DELETE',
                        'HEARTBEAT', 'REGISTER'
                    )),
                    payload  TEXT    NOT NULL,
                    ts_ms    INTEGER NOT NULL,
                    status   TEXT    NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'sent', 'acked', 'nacked', 'expired')),
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (master_id, msg_id)
                );
                INSERT INTO messages SELECT * FROM messages_old;
                DROP TABLE messages_old;
                CREATE INDEX IF NOT EXISTS idx_msg_status ON messages(status);
                CREATE INDEX IF NOT EXISTS idx_msg_ts ON messages(ts_ms);
                CREATE INDEX IF NOT EXISTS idx_msg_type ON messages(type);
                PRAGMA foreign_keys = ON;
            """)

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
            "INSERT INTO terminals "
            "(terminal_id, role, account_number, broker_server, status, created_at, last_heartbeat) "
            "VALUES (?, ?, ?, ?, 'Starting', ?, ?) "
            "ON CONFLICT(terminal_id) DO UPDATE SET "
            "account_number = excluded.account_number, "
            "broker_server = excluded.broker_server",
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

    async def get_master_id_for_msg(self, msg_id: int) -> str | None:
        cursor = await self._conn.execute(
            "SELECT master_id FROM messages WHERE msg_id = ?", (msg_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None

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

    async def get_all_terminals(self) -> list[dict]:
        return await self.fetch_all("SELECT * FROM terminals")

    async def get_active_links(self, master_id: str | None = None) -> list[dict]:
        if master_id:
            return await self.fetch_all(
                "SELECT * FROM master_slave_links WHERE master_id = ? AND enabled = 1",
                (master_id,),
            )
        return await self.fetch_all(
            "SELECT * FROM master_slave_links WHERE enabled = 1",
        )

    async def get_symbol_mappings(self, link_id: int) -> dict[str, str]:
        rows = await self.fetch_all(
            "SELECT master_symbol, slave_symbol FROM symbol_mappings WHERE link_id = ?",
            (link_id,),
        )
        return {r["master_symbol"]: r["slave_symbol"] for r in rows}

    async def get_magic_mappings(self, link_id: int) -> dict[int, int]:
        rows = await self.fetch_all(
            "SELECT master_setup_id, slave_setup_id FROM magic_mappings WHERE link_id = ?",
            (link_id,),
        )
        return {r["master_setup_id"]: r["slave_setup_id"] for r in rows}

    async def insert_heartbeat(
        self,
        terminal_id: str,
        vps_id: str,
        ts_ms: int,
        status_code: int,
        status_message: str,
        last_error: str,
    ):
        await self._conn.execute(
            "INSERT INTO heartbeats (terminal_id, vps_id, ts_ms, status_code, status_message, last_error) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (terminal_id, vps_id, ts_ms, status_code, status_message, last_error),
        )
        await self._conn.execute(
            "UPDATE terminals SET last_heartbeat = ? WHERE terminal_id = ?",
            (ts_ms, terminal_id),
        )
        await self._conn.commit()

    async def purge_old_heartbeats(self, max_age_days: int = 7):
        cutoff = self._now_ms() - (max_age_days * 86400 * 1000)
        await self._conn.execute(
            "DELETE FROM heartbeats WHERE ts_ms < ?", (cutoff,)
        )
        await self._conn.commit()

    async def purge_old_messages(self, max_age_days: int = 30):
        cutoff = self._now_ms() - (max_age_days * 86400 * 1000)
        await self._conn.execute(
            "DELETE FROM message_acks WHERE ts_ms < ?", (cutoff,)
        )
        await self._conn.execute(
            "DELETE FROM messages WHERE ts_ms < ?", (cutoff,)
        )
        await self._conn.commit()

    # ── Config (key-value settings) ──────────────────────────────

    async def get_config(self) -> dict[str, str]:
        rows = await self.fetch_all("SELECT key, value FROM config")
        return {r["key"]: r["value"] for r in rows}

    async def set_config(self, key: str, value: str):
        await self._conn.execute(
            "INSERT INTO config (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        await self._conn.commit()

    async def set_config_bulk(self, items: dict[str, str]):
        for key, value in items.items():
            await self._conn.execute(
                "INSERT INTO config (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        await self._conn.commit()

    async def save_terminal_symbols(self, terminal_id: str, symbols: list[str]):
        """Replace terminal's symbol list (full sync from MarketWatch)."""
        await self._conn.execute(
            "DELETE FROM terminal_symbols WHERE terminal_id = ?", (terminal_id,)
        )
        for sym in symbols:
            await self._conn.execute(
                "INSERT INTO terminal_symbols (terminal_id, symbol) VALUES (?, ?)",
                (terminal_id, sym),
            )
        await self._conn.commit()

    async def get_terminal_symbols(self, terminal_id: str) -> list[str]:
        rows = await self.fetch_all(
            "SELECT symbol FROM terminal_symbols WHERE terminal_id = ? ORDER BY symbol",
            (terminal_id,),
        )
        return [r["symbol"] for r in rows]

    async def seed_config_defaults(self):
        """Insert default config values if they are not already set."""
        defaults = {
            "vps_id": "vps_1",
            "heartbeat_interval_sec": "10",
            "heartbeat_timeout_sec": "30",
            "ack_timeout_sec": "5",
            "ack_max_retries": "3",
            "resend_window_size": "200",
            "alert_dedup_minutes": "5",
            "telegram_enabled": "false",
            "telegram_bot_token": "",
            "telegram_chat_id": "",
        }
        for key, value in defaults.items():
            await self._conn.execute(
                "INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)",
                (key, value),
            )
        await self._conn.commit()
