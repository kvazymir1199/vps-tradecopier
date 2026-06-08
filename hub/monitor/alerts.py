"""Alert dispatcher for Telegram notifications.

Pipeline for every alert:
  1. Persist a row in `alerts_history` with delivered=0 (always — even if muted
     / deduplicated / channel disabled — so the web panel can show *why* an
     alert wasn't delivered).
  2. Gate decisions: per-alert-type toggle → mute window → 5-minute dedup.
     A failed gate marks the row (muted=1 / deduplicated=1) and returns.
  3. If gates pass, dispatch a background delivery task with exponential
     backoff (10s → 30s → 90s). The row is UPDATEd after each attempt with
     the current retry_count and delivered flag.

Delivery failures never block trade routing — `send()` returns as soon as the
DB row is inserted.
"""

from __future__ import annotations

import asyncio
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Awaitable, Callable
from typing import Any

from hub.db.manager import DatabaseManager

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org"

# MarkdownV2 characters that MUST be escaped per Bot API spec.
_MD_ESCAPE_CHARS = r"_*[]()~`>#+-=|{}.!"

# Backoff schedule between Telegram delivery attempts (seconds).
RETRY_BACKOFF_SEC: tuple[int, ...] = (10, 30, 90)


def _md_escape(text: str) -> str:
    if not text:
        return ""
    out: list[str] = []
    for ch in text:
        if ch in _MD_ESCAPE_CHARS:
            out.append("\\")
        out.append(ch)
    return "".join(out)


def format_markdown_v2(
    alert_type: str,
    terminal_id: str | None,
    broker: str | None,
    message: str,
    fired_at_ms: int,
) -> str:
    """Compose the canonical MarkdownV2 alert body.

    Layout:
        *[ALERT_TYPE]* `terminal_id`
        _broker: broker_name_

        <message body>

        `fired at: YYYY-MM-DD HH:MM:SS UTC`
    """
    header = f"*\\[{_md_escape(alert_type.upper())}\\]*"
    if terminal_id:
        header += f"  `{_md_escape(terminal_id)}`"

    lines = [header]
    if broker:
        lines.append(f"_broker: {_md_escape(broker)}_")
    lines.append("")
    lines.append(_md_escape(message))
    lines.append("")
    ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(fired_at_ms / 1000))
    lines.append(f"`fired at: {_md_escape(ts)}`")
    return "\n".join(lines)


class AlertSender:
    def __init__(self, db: DatabaseManager, config):
        self._db = db
        self._config = config
        # Track suppressed-via-dedup counter for the rolling alert_storm window.
        self._suppressed_in_window = 0
        self._window_start_ms = int(time.time() * 1000)
        self._storm_emitted = False
        # Optional resolver: terminal_id → broker name (set by HubService).
        self._broker_resolver: Callable[[str], Awaitable[str | None]] | None = None
        # Track in-flight delivery tasks so tests/shutdown can await them.
        self._tasks: set[asyncio.Task] = set()

    # ─────────────────────────── public API ────────────────────────────

    def set_broker_resolver(
        self, resolver: Callable[[str], Awaitable[str | None]]
    ) -> None:
        self._broker_resolver = resolver

    async def send(self, alert: dict[str, Any], *, force: bool = False) -> int:
        """Process one alert. Returns the alerts_history row id.

        `force=True` bypasses per-type / mute / dedup gates — used by the
        "Test alert" button and the hub_started one-shot.
        """
        alert_type = alert["alert_type"]
        terminal_id = alert.get("terminal_id") or None
        message = alert["message"]
        now = int(time.time() * 1000)

        # Resolve broker for nicer MarkdownV2 rendering.
        broker: str | None = None
        if terminal_id and self._broker_resolver is not None:
            try:
                broker = await self._broker_resolver(terminal_id)
            except Exception as exc:  # broker lookup must never block alerts
                logger.debug(f"broker resolver failed for {terminal_id}: {exc}")

        # ── Gate 1: per-alert-type toggle ──
        if not force and not self._config.telegram.alert_enabled.get(alert_type, True):
            return await self._db.insert_alert(
                alert_type=alert_type,
                terminal_id=terminal_id,
                message=message,
                channel="telegram",
                sent_at=now,
                delivered=0,
            )

        # ── Gate 2: mute window ──
        mute_until = await self._db.get_mute_until_ms()
        if not force and mute_until > now:
            logger.debug(f"alert muted until {mute_until}: {alert_type}")
            return await self._db.insert_alert(
                alert_type=alert_type,
                terminal_id=terminal_id,
                message=message,
                channel="telegram",
                sent_at=now,
                delivered=0,
                muted=1,
            )

        # ── Gate 3: 5-minute dedup ──
        if not force and await self._is_duplicate(alert_type, terminal_id or "", now):
            self._track_suppression(now)
            row_id = await self._db.insert_alert(
                alert_type=alert_type,
                terminal_id=terminal_id,
                message=message,
                channel="telegram",
                sent_at=now,
                delivered=0,
                deduplicated=1,
            )
            await self._maybe_emit_storm(now)
            return row_id

        # ── Persist first, then dispatch delivery in the background. ──
        row_id = await self._db.insert_alert(
            alert_type=alert_type,
            terminal_id=terminal_id,
            message=message,
            channel="telegram",
            sent_at=now,
            delivered=0,
        )

        if self._config.telegram.enabled and self._config.telegram.bot_token:
            text = format_markdown_v2(alert_type, terminal_id, broker, message, now)
            task = asyncio.create_task(self._deliver_with_retry(row_id, text))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
        return row_id

    async def fire_test(self) -> int:
        """Synthetic alert used by the web-panel 'Test alert' button."""
        return await self.send(
            {
                "alert_type": "hub_started",
                "terminal_id": None,
                "message": "Test alert from web panel — Telegram pipeline OK.",
            },
            force=True,
        )

    async def send_raw_markdown(self, text_markdown_v2: str) -> bool:
        """Send a pre-formatted MarkdownV2 message without persisting.

        Used by the bot's `/status`, `/last_alerts`, `/help` replies.
        """
        if not (self._config.telegram.enabled and self._config.telegram.bot_token):
            return False
        try:
            await self._post_message(text_markdown_v2)
            return True
        except Exception as exc:
            logger.warning(f"bot reply failed: {exc}")
            return False

    async def wait_until_idle(self, timeout: float | None = None) -> None:
        """Used by tests to wait for in-flight delivery tasks to settle."""
        if not self._tasks:
            return
        await asyncio.wait(list(self._tasks), timeout=timeout)

    # ─────────────────────────── internals ─────────────────────────────

    async def _is_duplicate(
        self, alert_type: str, terminal_id: str, now_ms: int
    ) -> bool:
        dedup_ms = self._config.alert_dedup_minutes * 60 * 1000
        cutoff = now_ms - dedup_ms
        row = await self._db.fetch_one(
            "SELECT id FROM alerts_history "
            "WHERE alert_type = ? AND COALESCE(terminal_id, '') = ? "
            "AND sent_at > ? AND deduplicated = 0",
            (alert_type, terminal_id, cutoff),
        )
        return row is not None

    def _track_suppression(self, now_ms: int) -> None:
        """Roll the suppression window every dedup-minutes interval."""
        window_ms = self._config.alert_dedup_minutes * 60 * 1000
        if now_ms - self._window_start_ms > window_ms:
            self._window_start_ms = now_ms
            self._suppressed_in_window = 0
            self._storm_emitted = False
        self._suppressed_in_window += 1

    async def _maybe_emit_storm(self, now_ms: int) -> None:
        threshold = self._config.telegram.alert_storm_threshold
        if (
            threshold > 0
            and self._suppressed_in_window >= threshold
            and not self._storm_emitted
            and self._config.telegram.alert_enabled.get("alert_storm", True)
        ):
            self._storm_emitted = True
            await self.send(
                {
                    "alert_type": "alert_storm",
                    "terminal_id": None,
                    "message": (
                        f"{self._suppressed_in_window} alerts suppressed in "
                        f"{self._config.alert_dedup_minutes}m — throttling active."
                    ),
                },
                force=True,
            )

    async def _deliver_with_retry(self, row_id: int, text_markdown: str) -> None:
        attempts = 0
        last_error: str | None = None
        for delay in (0, *RETRY_BACKOFF_SEC):
            if delay:
                await asyncio.sleep(delay)
            attempts += 1
            try:
                await self._post_message(text_markdown)
                await self._db.execute(
                    "UPDATE alerts_history SET delivered = 1, retry_count = ? WHERE id = ?",
                    (attempts - 1, row_id),
                )
                return
            except Exception as exc:  # network or 4xx/5xx from Telegram
                last_error = str(exc)
                logger.warning(
                    f"Telegram delivery attempt {attempts} failed (row_id={row_id}): {exc}"
                )

        # All attempts exhausted.
        await self._db.execute(
            "UPDATE alerts_history SET delivered = 0, retry_count = ? WHERE id = ?",
            (len(RETRY_BACKOFF_SEC), row_id),
        )
        logger.error(
            f"Telegram delivery exhausted after {len(RETRY_BACKOFF_SEC)} retries "
            f"(row_id={row_id}): {last_error}"
        )

    async def _post_message(self, text_markdown: str) -> None:
        token = self._config.telegram.bot_token
        chat_id = self._config.telegram.chat_id
        if not token or not chat_id:
            raise RuntimeError("telegram bot_token/chat_id not configured")
        url = f"{TELEGRAM_API}/bot{token}/sendMessage"
        data = urllib.parse.urlencode(
            {
                "chat_id": chat_id,
                "text": text_markdown,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": "true",
            }
        ).encode()

        loop = asyncio.get_running_loop()

        def _blocking_post() -> None:
            req = urllib.request.Request(url, data=data)
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status != 200:
                    raise RuntimeError(f"HTTP {resp.status}")

        await loop.run_in_executor(None, _blocking_post)
