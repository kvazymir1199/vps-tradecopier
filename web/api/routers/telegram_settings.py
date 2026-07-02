"""Telegram settings API — the back-end of the /settings/telegram page.

This is the only place where the web panel can flip per-alert toggles,
change the bot token, fire a sanity-check alert, or extend a `/mute`
window from the UI. Hub-side writes (e.g. `/mute` from a Telegram chat)
land in the same `config` key-value table, so reads here always reflect
the latest state.
"""

from __future__ import annotations

import time

import httpx
from fastapi import APIRouter, HTTPException

from hub.config import ALERT_TYPES
from hub.monitor.alerts import (
    TELEGRAM_API,
    format_markdown_v2,
    telegram_ssl_context,
)
from web.api.database import get_db
from web.api.schemas import (
    MuteRequest,
    MuteStatus,
    TelegramSettingsOut,
    TelegramSettingsUpdate,
    TelegramTestResult,
)

router = APIRouter(prefix="/telegram", tags=["telegram"])


async def _read_config_map() -> dict[str, str]:
    async with get_db() as db:
        cursor = await db.execute("SELECT key, value FROM config")
        rows = await cursor.fetchall()
    return {r[0]: r[1] for r in rows}


def _settings_from_map(data: dict[str, str]) -> TelegramSettingsOut:
    alert_enabled: dict[str, bool] = {}
    for at in ALERT_TYPES:
        alert_enabled[at] = data.get(f"alert_enabled_{at}", "true").lower() == "true"
    return TelegramSettingsOut(
        enabled=data.get("telegram_enabled", "false").lower() == "true",
        bot_token=data.get("telegram_bot_token", ""),
        chat_id=data.get("telegram_chat_id", ""),
        daily_summary_time=data.get("telegram_daily_summary_time", "08:00"),
        alert_storm_threshold=int(data.get("telegram_alert_storm_threshold", "10")),
        alerts_retention_days=int(data.get("telegram_alerts_retention_days", "90")),
        alert_dedup_minutes=int(data.get("alert_dedup_minutes", "5")),
        mute_until_ms=int(data.get("telegram_mute_until_ms", "0")),
        alert_enabled=alert_enabled,
    )


@router.get("", response_model=TelegramSettingsOut)
async def get_telegram_settings():
    return _settings_from_map(await _read_config_map())


@router.put("", response_model=TelegramSettingsOut)
async def update_telegram_settings(body: TelegramSettingsUpdate):
    updates: dict[str, str] = {}
    if body.enabled is not None:
        updates["telegram_enabled"] = "true" if body.enabled else "false"
    if body.bot_token is not None:
        updates["telegram_bot_token"] = body.bot_token
    if body.chat_id is not None:
        updates["telegram_chat_id"] = body.chat_id
    if body.daily_summary_time is not None:
        updates["telegram_daily_summary_time"] = body.daily_summary_time
    if body.alert_storm_threshold is not None:
        updates["telegram_alert_storm_threshold"] = str(body.alert_storm_threshold)
    if body.alerts_retention_days is not None:
        updates["telegram_alerts_retention_days"] = str(body.alerts_retention_days)
    if body.alert_dedup_minutes is not None:
        updates["alert_dedup_minutes"] = str(body.alert_dedup_minutes)
    if body.alert_enabled is not None:
        for at, flag in body.alert_enabled.items():
            if at not in ALERT_TYPES:
                raise HTTPException(400, f"unknown alert_type: {at}")
            updates[f"alert_enabled_{at}"] = "true" if flag else "false"

    if updates:
        async with get_db() as db:
            for k, v in updates.items():
                await db.execute(
                    "INSERT INTO config (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (k, v),
                )
            await db.commit()

    return _settings_from_map(await _read_config_map())


@router.post("/test", response_model=TelegramTestResult)
async def fire_test_alert():
    """Send a synthetic alert through the Telegram API.

    Independent of the Hub process so the operator can verify token+chat_id
    even when the Hub is down. Result lands in `alerts_history` with the
    delivery flag set, so it shows up on the /alerts page right away.
    """
    settings = _settings_from_map(await _read_config_map())
    now = int(time.time() * 1000)
    body = "Test alert from web panel — Telegram pipeline OK."

    if not settings.bot_token or not settings.chat_id:
        # Still record the attempt so the failure is visible on the /alerts
        # page — otherwise the operator gets nothing to triage from.
        async with get_db() as db:
            await db.execute(
                "INSERT INTO alerts_history "
                "(alert_type, terminal_id, message, channel, sent_at, delivered, "
                "retry_count, deduplicated, muted) "
                "VALUES (?, ?, ?, 'telegram', ?, 0, 0, 0, 0)",
                ("hub_started", None, body, now),
            )
            await db.commit()
        return TelegramTestResult(
            delivered=False, detail="bot_token/chat_id empty"
        )

    text = format_markdown_v2("hub_started", None, None, body, now)

    url = f"{TELEGRAM_API}/bot{settings.bot_token}/sendMessage"
    payload = {
        "chat_id": settings.chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": "true",
    }

    delivered = 0
    detail = "ok"
    try:
        async with httpx.AsyncClient(verify=telegram_ssl_context()) as client:
            resp = await client.post(url, data=payload, timeout=10)
        if resp.status_code == 200:
            delivered = 1
        else:
            # Telegram returns a JSON body with a human-readable `description`
            # on 4xx/5xx (bad token, wrong chat_id, …) — surface it verbatim.
            try:
                detail = resp.json().get("description", f"HTTP {resp.status_code}")
            except Exception:
                detail = f"HTTP {resp.status_code}"
    except Exception as e:
        detail = str(e)

    async with get_db() as db:
        await db.execute(
            "INSERT INTO alerts_history "
            "(alert_type, terminal_id, message, channel, sent_at, delivered, "
            "retry_count, deduplicated, muted) "
            "VALUES (?, ?, ?, 'telegram', ?, ?, 0, 0, 0)",
            ("hub_started", None, body, now, delivered),
        )
        await db.commit()

    return TelegramTestResult(delivered=bool(delivered), detail=detail)


@router.post("/mute", response_model=MuteStatus)
async def set_mute(req: MuteRequest):
    """Start a mute window. duration_seconds=0 cancels."""
    if req.duration_seconds < 0:
        raise HTTPException(400, "duration_seconds must be >= 0")
    until_ms = (
        int(time.time() * 1000) + req.duration_seconds * 1000
        if req.duration_seconds > 0 else 0
    )
    async with get_db() as db:
        await db.execute(
            "INSERT INTO config (key, value) VALUES ('telegram_mute_until_ms', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(until_ms),),
        )
        await db.commit()
    return MuteStatus(muted_until_ms=until_ms)


@router.delete("/mute", response_model=MuteStatus)
async def clear_mute():
    async with get_db() as db:
        await db.execute(
            "INSERT INTO config (key, value) VALUES ('telegram_mute_until_ms', '0') "
            "ON CONFLICT(key) DO UPDATE SET value = '0'"
        )
        await db.commit()
    return MuteStatus(muted_until_ms=0)
