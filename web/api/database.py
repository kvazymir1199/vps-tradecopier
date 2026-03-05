import aiosqlite
from contextlib import asynccontextmanager

DB_PATH: str = ""


def set_db_path(path: str):
    global DB_PATH
    DB_PATH = path


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
