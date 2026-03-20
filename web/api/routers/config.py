from __future__ import annotations

from fastapi import APIRouter

from web.api.database import get_db
from web.api.schemas import ConfigOut, ConfigUpdate

router = APIRouter(prefix="/config", tags=["config"])


@router.get("", response_model=ConfigOut)
async def get_config():
    async with get_db() as db:
        cursor = await db.execute("SELECT key, value FROM config")
        rows = await cursor.fetchall()
    data = {r[0]: r[1] for r in rows}
    return ConfigOut.from_db(data)


@router.put("", response_model=ConfigOut)
async def update_config(body: ConfigUpdate):
    updates = {k: str(v) for k, v in body.model_dump(exclude_none=True).items()}
    # Преобразовать bool в строку для telegram_enabled
    if "telegram_enabled" in updates:
        updates["telegram_enabled"] = str(body.telegram_enabled).lower()
    async with get_db() as db:
        for key, value in updates.items():
            await db.execute(
                "INSERT INTO config (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        await db.commit()
        cursor = await db.execute("SELECT key, value FROM config")
        rows = await cursor.fetchall()
    data = {r[0]: r[1] for r in rows}
    return ConfigOut.from_db(data)
