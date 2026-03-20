import aiosqlite
from contextlib import asynccontextmanager
from pathlib import Path

from hub.config import DB_PATH

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "hub" / "db" / "schema.sql"


async def initialize_db():
    """Create tables if they don't exist (uses the same schema as Hub)."""
    if not DB_PATH:
        return
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = await aiosqlite.connect(DB_PATH)
    try:
        schema = SCHEMA_PATH.read_text(encoding="utf-8")
        await conn.executescript(schema)
    finally:
        await conn.close()


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
