import aiosqlite
from contextlib import asynccontextmanager
from pathlib import Path

DB_PATH: str = ""

SCHEMA_PATH = Path(__file__).resolve().parent.parent.parent / "hub" / "db" / "schema.sql"


def set_db_path(path: str):
    global DB_PATH
    DB_PATH = path


async def initialize_db():
    """Create tables if they don't exist (uses the same schema as Hub)."""
    if not DB_PATH:
        return
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
