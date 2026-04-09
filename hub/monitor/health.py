import time
import logging
from collections.abc import Callable, Awaitable

from hub.db.manager import DatabaseManager
from hub.config import Config

logger = logging.getLogger(__name__)


class HealthChecker:
    def __init__(
        self,
        db: DatabaseManager,
        config: Config,
        resend_callback: Callable[[dict], Awaitable[None]],
    ):
        self._db = db
        self._config = config
        self._resend_callback = resend_callback
        self._heartbeat_timeout_ms = config.heartbeat_timeout_sec * 1000

    async def run_checks(self) -> list[dict]:
        alerts = []
        alerts.extend(await self._check_heartbeat_timeouts())
        alerts.extend(await self._check_ack_timeouts())
        alerts.extend(await self._check_consecutive_nacks())
        alerts.extend(await self._check_queue_depth())
        return alerts

    async def _check_heartbeat_timeouts(self) -> list[dict]:
        now = int(time.time() * 1000)
        cutoff = now - self._heartbeat_timeout_ms
        terminals = await self._db.fetch_all(
            "SELECT terminal_id, status, last_heartbeat FROM terminals "
            "WHERE status NOT IN ('Disconnected', 'Error') AND last_heartbeat < ?",
            (cutoff,),
        )
        alerts = []
        for t in terminals:
            await self._db.update_terminal_status(t["terminal_id"], "Disconnected", "Heartbeat timeout")
            alerts.append({
                "alert_type": "heartbeat_miss",
                "terminal_id": t["terminal_id"],
                "message": f"Terminal {t['terminal_id']} heartbeat timeout ({(now - t['last_heartbeat']) // 1000}s)",
            })
        return alerts

    async def _check_ack_timeouts(self) -> list[dict]:
        timeout_ms = self._config.ack_timeout_sec * 1000
        max_retries = self._config.ack_max_retries
        cutoff = int(time.time() * 1000) - timeout_ms

        # Messages that can still be retried (retry_count < max_retries)
        retryable = await self._db.fetch_all(
            "SELECT msg_id, master_id, type, payload, retry_count FROM messages "
            "WHERE status = 'pending' AND ts_ms < ? AND retry_count < ? "
            "ORDER BY ts_ms ASC",
            (cutoff, max_retries),
        )

        # Messages that have exhausted all retries (retry_count >= max_retries)
        exhausted = await self._db.fetch_all(
            "SELECT msg_id, master_id, type, payload, retry_count FROM messages "
            "WHERE status = 'pending' AND ts_ms < ? AND retry_count >= ? "
            "ORDER BY ts_ms ASC",
            (cutoff, max_retries),
        )

        alerts = []

        for msg in retryable:
            await self._db.increment_retry(msg["master_id"], msg["msg_id"])
            await self._resend_callback(msg)

        for msg in exhausted:
            await self._db.update_message_status(msg["msg_id"], msg["master_id"], "expired")
            alerts.append({
                "alert_type": "ack_timeout",
                "terminal_id": msg["master_id"],
                "message": (
                    f"ACK exhausted after {max_retries} retries "
                    f"for msg_id={msg['msg_id']} from {msg['master_id']}"
                ),
            })

        return alerts

    async def _check_consecutive_nacks(self) -> list[dict]:
        rows = await self._db.fetch_all(
            "SELECT slave_id, COUNT(*) as cnt FROM message_acks "
            "WHERE ack_type = 'NACK' "
            "GROUP BY slave_id HAVING cnt > 5"
        )
        alerts = []
        for r in rows:
            alerts.append({
                "alert_type": "consecutive_nacks",
                "terminal_id": r["slave_id"],
                "message": f"Slave {r['slave_id']} has {r['cnt']} NACKs",
            })
        return alerts

    async def _check_queue_depth(self) -> list[dict]:
        rows = await self._db.fetch_all(
            "SELECT master_id, COUNT(*) as cnt FROM messages "
            "WHERE status = 'pending' "
            "GROUP BY master_id HAVING cnt > 50"
        )
        alerts = []
        for r in rows:
            alerts.append({
                "alert_type": "queue_depth",
                "terminal_id": r["master_id"],
                "message": f"Master {r['master_id']} has {r['cnt']} pending messages",
            })
        return alerts
