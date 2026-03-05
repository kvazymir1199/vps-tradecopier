import asyncio
import logging
import sys

from hub.config import Config
from hub.db.manager import DatabaseManager
from hub.router.router import Router
from hub.transport.pipe_server import PipeServer
from hub.monitor.health import HealthChecker
from hub.monitor.alerts import AlertSender

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("hub")


class HubService:
    def __init__(self, config_path: str):
        self.config = Config.load(config_path)
        self.db = DatabaseManager(self.config.db_path)
        self.router = Router(self.db, self.config.resend_window_size)
        self.alert_sender = AlertSender(self.db, self.config)
        self.health_checker = HealthChecker(self.db, self.config.heartbeat_timeout_sec)

    async def start(self):
        await self.db.initialize()
        logger.info("Hub Service started")
        asyncio.create_task(self._health_loop())
        await self._run_forever()

    async def _health_loop(self):
        while True:
            try:
                alerts = await self.health_checker.run_checks()
                for alert in alerts:
                    await self.alert_sender.send(alert)
            except Exception as e:
                logger.error(f"Health check error: {e}")
            await asyncio.sleep(10)

    async def _run_forever(self):
        while True:
            await asyncio.sleep(1)


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else "config/config.json"
    hub = HubService(config_path)
    asyncio.run(hub.start())


if __name__ == "__main__":
    main()
