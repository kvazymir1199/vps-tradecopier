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
        cutoff = int(time.time() * 1000) - timeout_ms

        # Retryable messages: retry_count < max_retries
        retryable = await self._db.get_timed_out_messages(timeout_ms, self._config.ack_max_retries)
        for msg in retryable:
            await self._db.increment_retry(msg["master_id"], msg["msg_id"])
            await self._resend_callback(msg)

        # Exhausted messages: retry_count >= max_retries — expire and alert
        exhausted = await self._db.fetch_all(
            "SELECT msg_id, master_id FROM messages "
            "WHERE status = 'pending' AND ts_ms < ? AND retry_count >= ?",
            (cutoff, self._config.ack_max_retries),
        )
        alerts = []
        for msg in exhausted:
            await self._db.update_message_status(msg["msg_id"], msg["master_id"], "expired")
            alerts.append({
                "alert_type": "ack_timeout",
                "terminal_id": msg["master_id"],
                "message": (
                    f"ACK exhausted after {self._config.ack_max_retries} retries "
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

    async def status_snapshot(self) -> dict:
        """Compact Hub status used by the Telegram `/status` command."""
        now = int(time.time() * 1000)
        terminals = await self._db.fetch_all(
            "SELECT terminal_id, role, status, last_heartbeat FROM terminals"
        )
        online = [
            t for t in terminals
            if now - t["last_heartbeat"] < self._heartbeat_timeout_ms
        ]
        pending_row = await self._db.fetch_one(
            "SELECT COUNT(*) AS cnt FROM messages WHERE status = 'pending'"
        )
        last_alerts = await self._db.fetch_all(
            "SELECT alert_type, terminal_id, sent_at FROM alerts_history "
            "ORDER BY sent_at DESC LIMIT 5"
        )
        return {
            "pending_messages": int(pending_row["cnt"]) if pending_row else 0,
            "online_terminals": online,
            "total_terminals": len(terminals),
            "last_alerts": last_alerts,
        }

    async def compose_daily_summary(self, window_ms: int = 86_400_000) -> dict:
        """24-hour digest: messages routed, ACK rate, NACK count, top NACK
        reasons, alert count, uptime. Returned as an alert dict ready to send.
        """
        now = int(time.time() * 1000)
        cutoff = now - window_ms

        msg_row = await self._db.fetch_one(
            "SELECT COUNT(*) AS cnt FROM messages "
            "WHERE ts_ms >= ? AND type NOT IN ('HEARTBEAT', 'REGISTER')",
            (cutoff,),
        )
        ack_row = await self._db.fetch_one(
            "SELECT "
            "  SUM(CASE WHEN ack_type='ACK' THEN 1 ELSE 0 END) AS acks, "
            "  SUM(CASE WHEN ack_type='NACK' THEN 1 ELSE 0 END) AS nacks "
            "FROM message_acks WHERE ts_ms >= ?",
            (cutoff,),
        )
        nack_reasons = await self._db.fetch_all(
            "SELECT nack_reason, COUNT(*) AS cnt FROM message_acks "
            "WHERE ts_ms >= ? AND ack_type='NACK' AND nack_reason IS NOT NULL "
            "GROUP BY nack_reason ORDER BY cnt DESC LIMIT 3",
            (cutoff,),
        )
        alert_row = await self._db.fetch_one(
            "SELECT COUNT(*) AS cnt FROM alerts_history WHERE sent_at >= ?",
            (cutoff,),
        )

        msgs = int(msg_row["cnt"]) if msg_row else 0
        acks = int(ack_row["acks"] or 0) if ack_row else 0
        nacks = int(ack_row["nacks"] or 0) if ack_row else 0
        total_acks = acks + nacks
        ack_rate = (acks / total_acks * 100) if total_acks else 0.0
        alerts_fired = int(alert_row["cnt"]) if alert_row else 0

        lines = [
            f"messages routed: {msgs}",
            f"ACK rate: {ack_rate:.1f}% ({acks}/{total_acks})",
            f"NACKs: {nacks}",
            f"alerts fired: {alerts_fired}",
        ]
        if nack_reasons:
            top = ", ".join(f"{r['nack_reason']}={r['cnt']}" for r in nack_reasons)
            lines.append(f"top NACK reasons: {top}")
        return {
            "alert_type": "daily_summary",
            "terminal_id": None,
            "message": "\n".join(lines),
        }
