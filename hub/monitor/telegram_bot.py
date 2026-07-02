"""Telegram bot — read-only operator interface over long-polling.

Why long-polling and not webhooks: the Hub runs on a VPS without inbound
HTTPS exposure. `getUpdates` with a 25s long-poll lets us pull commands
without opening any port.

Commands accepted only from the configured `chat_id`(s). Anyone else is
silently ignored — no error reply, no log noise.

  /status            Hub uptime, pending messages, online terminals, last 5 alerts
  /last_alerts [N]   Last N alerts (default 10), newest first
  /mute [duration]   Suppress all outbound alerts (e.g. /mute 1h, /mute 30m).
                     /mute off cancels. Default 1h if no duration.
  /help              Lists the above
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from typing import Any

import httpx

from hub.db.manager import DatabaseManager
from hub.monitor.alerts import (
    TELEGRAM_API,
    AlertSender,
    _md_escape,
    telegram_ssl_context,
)
from hub.monitor.health import HealthChecker

logger = logging.getLogger(__name__)

# Long-poll timeout. Telegram caps at 50s; 25s strikes a balance between
# liveness and connection count.
_LONG_POLL_TIMEOUT_SEC = 25

# Recognised duration suffixes for /mute.
_DURATION_RE = re.compile(r"^(\d+)\s*([smhd])$", re.IGNORECASE)
_DURATION_UNITS_MS = {"s": 1_000, "m": 60_000, "h": 3_600_000, "d": 86_400_000}


def _parse_duration(text: str) -> int | None:
    """Parse '/mute 1h' style durations → milliseconds. None on bad input."""
    m = _DURATION_RE.match(text.strip())
    if not m:
        return None
    return int(m.group(1)) * _DURATION_UNITS_MS[m.group(2).lower()]


class TelegramBot:
    def __init__(
        self,
        db: DatabaseManager,
        config,
        alert_sender: AlertSender,
        health_checker: HealthChecker,
        hub_started_at_ms: int,
    ):
        self._db = db
        self._config = config
        self._alerts = alert_sender
        self._health = health_checker
        self._started_at_ms = hub_started_at_ms
        self._update_offset = 0
        self._running = False

    async def start(self) -> None:
        """Main long-polling loop. Exits silently if Telegram is disabled
        or unconfigured — the rest of the Hub keeps running."""
        if not self._config.telegram.enabled:
            logger.info("Telegram bot disabled by config — skipping bot loop")
            return
        if not self._config.telegram.bot_token:
            logger.info("Telegram bot_token empty — skipping bot loop")
            return

        self._running = True
        logger.info("Telegram bot long-polling started")
        while self._running:
            try:
                updates = await self._get_updates()
                for upd in updates:
                    await self._handle_update(upd)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                # Don't spin: back off briefly on errors (network blips,
                # bad token, Telegram 5xx). The loop continues.
                logger.warning(f"Telegram bot iteration failed: {exc}")
                await asyncio.sleep(5)

    def stop(self) -> None:
        self._running = False

    # ───────────────────── update fetching ────────────────────────────

    async def _get_updates(self) -> list[dict[str, Any]]:
        url = f"{TELEGRAM_API}/bot{self._config.telegram.bot_token}/getUpdates"
        params = {
            "offset": self._update_offset,
            "timeout": _LONG_POLL_TIMEOUT_SEC,
            "allowed_updates": json.dumps(["message"]),
        }

        async with httpx.AsyncClient(verify=telegram_ssl_context()) as client:
            resp = await client.get(
                url, params=params, timeout=_LONG_POLL_TIMEOUT_SEC + 5
            )
            resp.raise_for_status()
            data = resp.json()

        if not data.get("ok"):
            raise RuntimeError(f"getUpdates !ok: {data}")
        updates = data.get("result", [])
        if updates:
            self._update_offset = max(u["update_id"] for u in updates) + 1
        return updates

    # ─────────────────────── command routing ──────────────────────────

    async def _handle_update(self, upd: dict[str, Any]) -> None:
        msg = upd.get("message") or {}
        chat = msg.get("chat") or {}
        from_chat_id = str(chat.get("id", ""))
        text = (msg.get("text") or "").strip()
        if not from_chat_id or not text:
            return

        # Auth — drop anything not from the configured chat_id.
        allowed = self._config.telegram.chat_id.strip()
        if allowed and from_chat_id != allowed:
            logger.debug(f"ignored bot msg from non-allowed chat {from_chat_id}")
            return

        # Strip @botname suffix for group chats (Telegram appends it).
        first_token = text.split()[0] if text else ""
        cmd = first_token.split("@", 1)[0].lower()

        if cmd == "/status":
            await self._cmd_status()
        elif cmd == "/last_alerts":
            await self._cmd_last_alerts(text)
        elif cmd == "/mute":
            await self._cmd_mute(text)
        elif cmd in ("/help", "/start"):
            await self._cmd_help()
        # Unknown commands are silently ignored.

    # ─────────────────────────── commands ─────────────────────────────

    async def _cmd_status(self) -> None:
        snap = await self._health.status_snapshot()
        uptime_sec = (int(time.time() * 1000) - self._started_at_ms) // 1000
        h, rem = divmod(uptime_sec, 3600)
        m, s = divmod(rem, 60)
        uptime = f"{h:d}h {m:02d}m {s:02d}s"

        online = snap["online_terminals"]
        terminals_line = ", ".join(
            f"{_md_escape(t['terminal_id'])}({t['role'][0]})" for t in online[:10]
        ) or "_none_"
        if len(online) > 10:
            terminals_line += f" \\+{len(online) - 10} more"

        last_lines: list[str] = []
        for a in snap["last_alerts"]:
            ts = time.strftime("%H:%M:%S", time.gmtime(a["sent_at"] / 1000))
            tag = _md_escape(a["alert_type"])
            tid = _md_escape(a.get("terminal_id") or "-")
            last_lines.append(f"• `{ts}` *{tag}* {tid}")

        body = (
            f"*Hub status*\n"
            f"uptime: `{uptime}`\n"
            f"pending messages: `{snap['pending_messages']}`\n"
            f"terminals online: `{len(online)}/{snap['total_terminals']}`\n"
            f"{terminals_line}\n\n"
            f"*last 5 alerts*\n" + ("\n".join(last_lines) if last_lines else "_none_")
        )
        await self._alerts.send_raw_markdown(body)

    async def _cmd_last_alerts(self, text: str) -> None:
        parts = text.split()
        n = 10
        if len(parts) > 1:
            try:
                n = max(1, min(50, int(parts[1])))
            except ValueError:
                pass
        rows = await self._db.get_alerts(limit=n)
        if not rows:
            await self._alerts.send_raw_markdown("_no alerts in history_")
            return
        lines = [f"*Last {len(rows)} alerts*"]
        for a in rows:
            ts = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.gmtime(a["sent_at"] / 1000)
            )
            status = "✓" if a["delivered"] else (
                "muted" if a.get("muted") else
                "dup" if a.get("deduplicated") else "✗"
            )
            tag = _md_escape(a["alert_type"])
            tid = _md_escape(a.get("terminal_id") or "-")
            lines.append(f"• `{ts}` *{tag}* {tid} `{status}`")
        await self._alerts.send_raw_markdown("\n".join(lines))

    async def _cmd_mute(self, text: str) -> None:
        parts = text.split()
        if len(parts) > 1 and parts[1].lower() == "off":
            await self._db.set_mute_until_ms(0)
            await self._alerts.send_raw_markdown("_alerts un\\-muted_")
            return
        duration_ms = _parse_duration(parts[1]) if len(parts) > 1 else 3_600_000
        if duration_ms is None:
            await self._alerts.send_raw_markdown(
                "_bad duration\\. Use `/mute 1h`, `/mute 30m`, `/mute 90s`, `/mute off`\\._"
            )
            return
        until_ms = int(time.time() * 1000) + duration_ms
        await self._db.set_mute_until_ms(until_ms)
        until_human = time.strftime(
            "%Y-%m-%d %H:%M:%S UTC", time.gmtime(until_ms / 1000)
        )
        await self._alerts.send_raw_markdown(
            f"_alerts muted until_ `{_md_escape(until_human)}`"
        )

    async def _cmd_help(self) -> None:
        body = (
            "*Trade Copier — operator commands*\n"
            "`/status` — Hub uptime, pending, online terminals, last 5 alerts\n"
            "`/last_alerts [N]` — last N alerts \\(default 10\\)\n"
            "`/mute [duration]` — suppress alerts \\(e\\.g\\. `1h`, `30m`, `off`\\)\n"
            "`/help` — this message"
        )
        await self._alerts.send_raw_markdown(body)
