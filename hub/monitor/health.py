import time
import logging
from pathlib import Path

from hub.db.manager import DatabaseManager

logger = logging.getLogger(__name__)


class HealthChecker:
    def __init__(self, db: DatabaseManager, heartbeat_timeout_sec: int = 30):
        self._db = db
        self._heartbeat_timeout_ms = heartbeat_timeout_sec * 1000

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
        now = int(time.time() * 1000)
        cutoff = now - 15_000  # 15 seconds
        rows = await self._db.fetch_all(
            "SELECT msg_id, master_id, ts_ms FROM messages "
            "WHERE status = 'pending' AND ts_ms < ?",
            (cutoff,),
        )
        alerts = []
        for r in rows:
            alerts.append({
                "alert_type": "ack_timeout",
                "terminal_id": r["master_id"],
                "message": f"ACK timeout for msg_id={r['msg_id']} from {r['master_id']}",
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
