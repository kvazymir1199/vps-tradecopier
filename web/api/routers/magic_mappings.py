from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from web.api.database import get_db
from web.api.schemas import MagicMappingCreate, MagicMappingOut

router = APIRouter(tags=["magic-mappings"])


@router.get(
    "/links/{link_id}/magic-mappings",
    response_model=list[MagicMappingOut],
)
async def list_magic_mappings(link_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM magic_mappings WHERE link_id = ?", (link_id,)
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.post(
    "/links/{link_id}/magic-mappings",
    response_model=MagicMappingOut,
    status_code=201,
)
async def create_magic_mapping(link_id: int, body: MagicMappingCreate):
    async with get_db() as db:
        # Verify link exists
        cursor = await db.execute(
            "SELECT id FROM master_slave_links WHERE id = ?", (link_id,)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Link not found")

        # Check unique constraint
        cursor = await db.execute(
            "SELECT id FROM magic_mappings WHERE link_id = ? AND master_setup_id = ?",
            (link_id, body.master_setup_id),
        )
        if await cursor.fetchone():
            raise HTTPException(
                status_code=409,
                detail="Magic mapping already exists for this master_setup_id",
            )

        cursor = await db.execute(
            """INSERT INTO magic_mappings
               (link_id, master_setup_id, slave_setup_id, allowed_direction)
               VALUES (?, ?, ?, ?)""",
            (link_id, body.master_setup_id, body.slave_setup_id, body.allowed_direction),
        )
        await db.commit()
        mapping_id = cursor.lastrowid

        cursor = await db.execute(
            "SELECT * FROM magic_mappings WHERE id = ?", (mapping_id,)
        )
        row = await cursor.fetchone()
    return dict(row)


@router.delete("/magic-mappings/{mapping_id}", status_code=204)
async def delete_magic_mapping(mapping_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM magic_mappings WHERE id = ?", (mapping_id,)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Magic mapping not found")
        await db.execute("DELETE FROM magic_mappings WHERE id = ?", (mapping_id,))
        await db.commit()
    return Response(status_code=204)
