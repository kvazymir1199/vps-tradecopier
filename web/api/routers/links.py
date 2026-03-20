from __future__ import annotations

import time
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response

from web.api.database import get_db
from web.api.schemas import LinkCreate, LinkOut, LinkUpdate

router = APIRouter(prefix="/links", tags=["links"])


@router.get("", response_model=list[LinkOut])
async def list_links(master_id: Optional[str] = Query(None)):
    async with get_db() as db:
        if master_id:
            cursor = await db.execute(
                "SELECT * FROM master_slave_links WHERE master_id = ?",
                (master_id,),
            )
        else:
            cursor = await db.execute("SELECT * FROM master_slave_links")
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.post("", response_model=LinkOut, status_code=201)
async def create_link(body: LinkCreate):
    async with get_db() as db:
        # Validate master role
        cursor = await db.execute(
            "SELECT role FROM terminals WHERE terminal_id = ?", (body.master_id,)
        )
        master = await cursor.fetchone()
        if master is None:
            raise HTTPException(status_code=404, detail="Master terminal not found")
        if master["role"] != "master":
            raise HTTPException(
                status_code=400, detail="Terminal is not a master"
            )

        # Validate slave role
        cursor = await db.execute(
            "SELECT role FROM terminals WHERE terminal_id = ?", (body.slave_id,)
        )
        slave = await cursor.fetchone()
        if slave is None:
            raise HTTPException(status_code=404, detail="Slave terminal not found")
        if slave["role"] != "slave":
            raise HTTPException(
                status_code=400, detail="Terminal is not a slave"
            )

        # Check unique pair
        cursor = await db.execute(
            "SELECT id FROM master_slave_links WHERE master_id = ? AND slave_id = ?",
            (body.master_id, body.slave_id),
        )
        if await cursor.fetchone():
            raise HTTPException(
                status_code=409, detail="Link already exists for this pair"
            )

        now = int(time.time())
        cursor = await db.execute(
            """INSERT INTO master_slave_links
               (master_id, slave_id, lot_mode, lot_value, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (body.master_id, body.slave_id, body.lot_mode, body.lot_value, now),
        )
        await db.commit()
        link_id = cursor.lastrowid

        cursor = await db.execute(
            "SELECT * FROM master_slave_links WHERE id = ?", (link_id,)
        )
        row = await cursor.fetchone()
    return dict(row)


@router.put("/{link_id}", response_model=LinkOut)
async def update_link(link_id: int, body: LinkUpdate):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM master_slave_links WHERE id = ?", (link_id,)
        )
        existing = await cursor.fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Link not found")

        updates = body.model_dump(exclude_none=True)
        if not updates:
            return dict(existing)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [link_id]
        await db.execute(
            f"UPDATE master_slave_links SET {set_clause} WHERE id = ?",
            values,
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM master_slave_links WHERE id = ?", (link_id,)
        )
        row = await cursor.fetchone()
    return dict(row)


@router.patch("/{link_id}/toggle", response_model=LinkOut)
async def toggle_link(link_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM master_slave_links WHERE id = ?", (link_id,)
        )
        existing = await cursor.fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Link not found")

        new_enabled = 0 if existing["enabled"] else 1
        await db.execute(
            "UPDATE master_slave_links SET enabled = ? WHERE id = ?",
            (new_enabled, link_id),
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM master_slave_links WHERE id = ?", (link_id,)
        )
        row = await cursor.fetchone()
    return dict(row)


@router.delete("/{link_id}", status_code=204)
async def delete_link(link_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM master_slave_links WHERE id = ?", (link_id,)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Link not found")
        await db.execute("DELETE FROM master_slave_links WHERE id = ?", (link_id,))
        await db.commit()
    return Response(status_code=204)
