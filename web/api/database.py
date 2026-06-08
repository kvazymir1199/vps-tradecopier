import aiosqlite
from contextlib import asynccontextmanager
from pathlib import Path

from hub.config import DB_PATH
from hub.db.manager import DatabaseManager

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "hub" / "db" / "schema.sql"


async def initialize_db():
    """Ensure schema + migrations are applied.

    Routes the work through DatabaseManager so the API server applies the
    same migrations the Hub does. Without this the API would query columns
    that don't exist yet on a pre-MS3 database file.
    """
    if not DB_PATH:
        return
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    mgr = DatabaseManager(DB_PATH)
    try:
        await mgr.initialize()
        await mgr.seed_config_defaults()
    finally:
        await mgr.close()


@asynccontextmanager
async def get_db():
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode = WAL")
    await conn.execute("PRAGMA busy_timeout = 5000")
    await conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        await conn.close()
