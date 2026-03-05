from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from web.api.database import get_db
from web.api.schemas import SymbolMappingCreate, SymbolMappingOut

router = APIRouter(tags=["symbol-mappings"])


@router.get(
    "/links/{link_id}/symbol-mappings",
    response_model=list[SymbolMappingOut],
)
async def list_symbol_mappings(link_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM symbol_mappings WHERE link_id = ?", (link_id,)
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


@router.post(
    "/links/{link_id}/symbol-mappings",
    response_model=SymbolMappingOut,
    status_code=201,
)
async def create_symbol_mapping(link_id: int, body: SymbolMappingCreate):
    async with get_db() as db:
        # Verify link exists
        cursor = await db.execute(
            "SELECT id FROM master_slave_links WHERE id = ?", (link_id,)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Link not found")

        # Check unique constraint
        cursor = await db.execute(
            "SELECT id FROM symbol_mappings WHERE link_id = ? AND master_symbol = ?",
            (link_id, body.master_symbol),
        )
        if await cursor.fetchone():
            raise HTTPException(
                status_code=409,
                detail="Symbol mapping already exists for this master_symbol",
            )

        cursor = await db.execute(
            """INSERT INTO symbol_mappings (link_id, master_symbol, slave_symbol)
               VALUES (?, ?, ?)""",
            (link_id, body.master_symbol, body.slave_symbol),
        )
        await db.commit()
        mapping_id = cursor.lastrowid

        cursor = await db.execute(
            "SELECT * FROM symbol_mappings WHERE id = ?", (mapping_id,)
        )
        row = await cursor.fetchone()
    return dict(row)


@router.delete("/symbol-mappings/{mapping_id}", status_code=204)
async def delete_symbol_mapping(mapping_id: int):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id FROM symbol_mappings WHERE id = ?", (mapping_id,)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Symbol mapping not found")
        await db.execute("DELETE FROM symbol_mappings WHERE id = ?", (mapping_id,))
        await db.commit()
    return Response(status_code=204)
