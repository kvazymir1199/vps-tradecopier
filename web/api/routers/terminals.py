from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from web.api.database import get_db
from web.api.schemas import TerminalCreate, TerminalOut

router = APIRouter(prefix="/terminals", tags=["terminals"])


@router.post("", response_model=TerminalOut, status_code=201)
async def create_terminal(body: TerminalCreate):
    """Register a terminal manually so Hub creates its pipes on next restart."""
    if body.role not in ("master", "slave"):
        raise HTTPException(status_code=400, detail="role must be 'master' or 'slave'")
    now_ms = int(time.time() * 1000)
    async with get_db() as db:
        await db.execute(
            """INSERT OR IGNORE INTO terminals (terminal_id, role, status, status_message, last_heartbeat)
               VALUES (?, ?, 'Inactive', 'Registered manually', ?)""",
            (body.terminal_id, body.role, now_ms),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM terminals WHERE terminal_id = ?", (body.terminal_id,)
        )
        row = await cursor.fetchone()
    return dict(row)


@router.get("", response_model=list[TerminalOut])
async def list_terminals():
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM terminals")
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.get("/{terminal_id}", response_model=TerminalOut)
async def get_terminal(terminal_id: str):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM terminals WHERE terminal_id = ?", (terminal_id,)
        )
        row = await cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Terminal not found")
    return dict(row)


@router.get("/{terminal_id}/symbols")
async def get_terminal_symbols(terminal_id: str):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT symbol FROM terminal_symbols WHERE terminal_id = ? ORDER BY symbol",
            (terminal_id,),
        )
        rows = await cursor.fetchall()
    return [r[0] for r in rows]
