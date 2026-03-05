import time
import logging
import urllib.request
import urllib.parse
import json

from hub.db.manager import DatabaseManager

logger = logging.getLogger(__name__)


class AlertSender:
    def __init__(self, db: DatabaseManager, config):
        self._db = db
        self._config = config

    async def send(self, alert: dict):
        alert_type = alert["alert_type"]
        terminal_id = alert.get("terminal_id", "")
        message = alert["message"]

        if await self._is_duplicate(alert_type, terminal_id):
            logger.debug(f"Alert deduplicated: {alert_type} for {terminal_id}")
            return

        delivered = 0
        if self._config.telegram.enabled:
            try:
                self._send_telegram(message)
                delivered = 1
            except Exception as e:
                logger.error(f"Telegram send failed: {e}")
                delivered = -1

        now = int(time.time() * 1000)
        await self._db.execute(
            "INSERT INTO alerts_history (alert_type, terminal_id, message, channel, sent_at, delivered) "
            "VALUES (?, ?, ?, 'telegram', ?, ?)",
            (alert_type, terminal_id, message, now, delivered),
        )

    async def _is_duplicate(self, alert_type: str, terminal_id: str) -> bool:
        dedup_ms = self._config.alert_dedup_minutes * 60 * 1000
        cutoff = int(time.time() * 1000) - dedup_ms
        row = await self._db.fetch_one(
            "SELECT id FROM alerts_history "
            "WHERE alert_type = ? AND terminal_id = ? AND sent_at > ?",
            (alert_type, terminal_id, cutoff),
        )
        return row is not None

    def _send_telegram(self, message: str):
        token = self._config.telegram.bot_token
        chat_id = self._config.telegram.chat_id
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": message}).encode()
        req = urllib.request.Request(url, data=data)
        urllib.request.urlopen(req, timeout=10)
