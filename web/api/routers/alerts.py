"""Alerts history API — read-only view used by the /alerts page.

Filters are intentionally narrow: alert_type, terminal_id, time range and
delivered flag. The page is for triage, not for replaying alerts.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query

from web.api.database import get_db
from web.api.schemas import AlertOut

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    limit: int = Query(default=200, ge=1, le=1000),
    alert_type: Optional[str] = None,
    terminal_id: Optional[str] = None,
    delivered: Optional[int] = Query(default=None, ge=0, le=1),
    since_ms: Optional[int] = None,
    until_ms: Optional[int] = None,
):
    clauses: list[str] = []
    params: list = []
    if alert_type:
        clauses.append("alert_type = ?")
        params.append(alert_type)
    if terminal_id:
        clauses.append("terminal_id = ?")
        params.append(terminal_id)
    if delivered is not None:
        clauses.append("delivered = ?")
        params.append(delivered)
    if since_ms is not None:
        clauses.append("sent_at >= ?")
        params.append(since_ms)
    if until_ms is not None:
        clauses.append("sent_at <= ?")
        params.append(until_ms)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    async with get_db() as db:
        cursor = await db.execute(
            f"SELECT id, alert_type, terminal_id, message, channel, sent_at, "
            f"delivered, retry_count, deduplicated, muted "
            f"FROM alerts_history {where} ORDER BY sent_at DESC LIMIT ?",
            tuple(params),
        )
        rows = await cursor.fetchall()

    return [
        AlertOut(
            id=r[0],
            alert_type=r[1],
            terminal_id=r[2],
            message=r[3],
            channel=r[4],
            sent_at=r[5],
            delivered=r[6],
            retry_count=r[7],
            deduplicated=r[8],
            muted=r[9],
        )
        for r in rows
    ]
