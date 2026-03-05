from __future__ import annotations

from fastapi import APIRouter, HTTPException

from web.api.database import get_db
from web.api.schemas import TerminalOut

router = APIRouter(prefix="/terminals", tags=["terminals"])


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
