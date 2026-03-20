from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from web.api.database import get_db
from web.api.schemas import SymbolMappingCreate, SymbolMappingOut

router = APIRouter(tags=["symbol-mappings"])


@router.get("/links/{link_id}/symbol-mappings/suggestions")
async def get_symbol_suggestions(link_id: int):
    """Auto-match master and slave symbols."""
    async with get_db() as db:
        # Get link
        cursor = await db.execute(
            "SELECT * FROM master_slave_links WHERE id = ?", (link_id,)
        )
        link = await cursor.fetchone()
        if not link:
            raise HTTPException(status_code=404, detail="Link not found")

        master_id = link[1]  # master_id column
        slave_id = link[2]   # slave_id column

        # Get symbols for both terminals
        cursor = await db.execute(
            "SELECT symbol FROM terminal_symbols WHERE terminal_id = ? ORDER BY symbol",
            (master_id,),
        )
        master_symbols = [r[0] for r in await cursor.fetchall()]

        cursor = await db.execute(
            "SELECT symbol FROM terminal_symbols WHERE terminal_id = ? ORDER BY symbol",
            (slave_id,),
        )
        slave_symbols = [r[0] for r in await cursor.fetchall()]
        slave_set = set(slave_symbols)

        # Get existing mappings
        cursor = await db.execute(
            "SELECT master_symbol, slave_symbol FROM symbol_mappings WHERE link_id = ?",
            (link_id,),
        )
        existing = {r[0]: r[1] for r in await cursor.fetchall()}

        suggestions = []
        for ms in master_symbols:
            if ms in existing:
                suggestions.append({"master_symbol": ms, "slave_symbol": existing[ms], "status": "mapped"})
            elif ms in slave_set:
                suggestions.append({"master_symbol": ms, "slave_symbol": ms, "status": "auto"})
            else:
                # Try substring match
                match = None
                for ss in slave_symbols:
                    if ms in ss or ss in ms:
                        match = ss
                        break
                if match:
                    suggestions.append({"master_symbol": ms, "slave_symbol": match, "status": "auto"})
                else:
                    suggestions.append({"master_symbol": ms, "slave_symbol": None, "status": "unmapped"})

    return {
        "master_id": master_id,
        "slave_id": slave_id,
        "suggestions": suggestions,
        "slave_symbols": slave_symbols,
    }


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
