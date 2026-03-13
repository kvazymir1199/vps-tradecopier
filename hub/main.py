import asyncio
import concurrent.futures
import json
import logging
import os
import sys
import time

from hub.config import Config
from hub.db.manager import DatabaseManager
from hub.router.router import Router
from hub.transport.pipe_server import PipeServer
from hub.protocol.serializer import decode_master_message, encode_slave_command, decode_ack
from hub.monitor.health import HealthChecker
from hub.monitor.alerts import AlertSender

LOG_DIR = "C:\\TradeCopier\\logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join(LOG_DIR, "hub.log"), encoding="utf-8"),
    ],
)
logger = logging.getLogger("hub")


class HubService:
    def __init__(self, config_path: str):
        self.config = Config.load(config_path)
        self.db = DatabaseManager(self.config.db_path)
        self.router = Router(self.db, self.config.resend_window_size)
        self.alert_sender = AlertSender(self.db, self.config)
        self.health_checker = HealthChecker(self.db, self.config.heartbeat_timeout_sec)
        self._pipe_servers: list[PipeServer] = []
        self._slave_cmd_pipes: dict[str, PipeServer] = {}

    async def _handle_master_message(self, raw: str) -> str | None:
        """Process a raw JSON message from a master EA."""
        try:
            data = json.loads(raw.strip())
            msg_type = data.get("type", "")

            # Handle REGISTER
            if msg_type == "REGISTER":
                terminal_id = data.get("terminal_id", "")
                account = data.get("account", 0)
                broker = data.get("broker", "")
                role = data.get("role", "master").lower()
                await self.db.register_terminal(terminal_id, role, account, broker)
                logger.info(f"REGISTER: {terminal_id} ({role}) account={account}")
                return None

            # Handle HEARTBEAT
            if msg_type == "HEARTBEAT":
                terminal_id = data.get("terminal_id", "")
                ts_ms = data.get("ts_ms", int(time.time() * 1000))
                status_code = data.get("payload", {}).get("status_code", 0)
                status_msg = data.get("payload", {}).get("status_msg", "OK")
                if status_code == 0:
                    await self.db.update_terminal_status(terminal_id, "Active", "OK")
                else:
                    await self.db.update_terminal_status(terminal_id, "Error", status_msg)
                await self.db.insert_heartbeat(
                    terminal_id, self.config.vps_id, ts_ms,
                    data.get("payload", {}).get("status_code", 0),
                    data.get("payload", {}).get("status_msg", "OK"),
                    data.get("payload", {}).get("last_error", ""),
                )
                return None

            # Trade messages — parse and route
            logger.info(f"Trade message received: type={msg_type} from {data.get('master_id', '?')}")
            msg = decode_master_message(raw)
            await self.db.insert_message(
                msg.msg_id, msg.master_id, str(msg.type),
                json.dumps(msg.payload, separators=(',', ':')), msg.ts_ms,
            )
            commands = await self.router.route(msg)
            logger.info(f"Router produced {len(commands)} command(s) for msg_id={msg.msg_id}")

            for cmd in commands:
                slave_pipe = self._slave_cmd_pipes.get(cmd.slave_id)
                if slave_pipe and slave_pipe._handle:
                    encoded = encode_slave_command(cmd)
                    try:
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, slave_pipe._write, encoded)
                        logger.info(f"Forwarded {cmd.type} to {cmd.slave_id} (msg_id={cmd.msg_id})")
                    except Exception as e:
                        logger.error(f"Failed to forward to {cmd.slave_id}: {e}")
                else:
                    logger.warning(f"Slave {cmd.slave_id} pipe not connected, command dropped")

            if not commands:
                logger.warning(f"No commands generated for {msg_type} msg_id={msg.msg_id} — check links/routing")

        except Exception as e:
            logger.error(f"Error handling master message: {e} — raw: {raw[:200]}")
        return None

    async def _handle_slave_ack(self, raw: str) -> str | None:
        """Process an ACK/NACK or REGISTER/HEARTBEAT from a slave EA."""
        try:
            data = json.loads(raw.strip())
            msg_type = data.get("type", "")

            if msg_type == "REGISTER":
                terminal_id = data.get("terminal_id", "")
                account = data.get("account", 0)
                broker = data.get("broker", "")
                await self.db.register_terminal(terminal_id, "slave", account, broker)
                logger.info(f"REGISTER: {terminal_id} (slave) account={account}")
                return None

            if msg_type == "HEARTBEAT":
                terminal_id = data.get("terminal_id", "")
                ts_ms = data.get("ts_ms", int(time.time() * 1000))
                status_code = data.get("payload", {}).get("status_code", 0)
                status_msg = data.get("payload", {}).get("status_msg", "OK")
                if status_code == 0:
                    await self.db.update_terminal_status(terminal_id, "Active", "OK")
                else:
                    await self.db.update_terminal_status(terminal_id, "Error", status_msg)
                await self.db.insert_heartbeat(
                    terminal_id, self.config.vps_id, ts_ms,
                    status_code, status_msg,
                    data.get("payload", {}).get("last_error", ""),
                )
                return None

            # ACK/NACK message
            ack = decode_ack(raw)
            logger.info(f"ACK from {ack.slave_id}: type={ack.ack_type} msg_id={ack.msg_id}")
            await self.db.insert_ack(
                ack.msg_id, "", ack.slave_id,
                ack.ack_type, ack.reason, ack.slave_ticket,
                ack.ts_ms,
            )

        except Exception as e:
            logger.error(f"Error handling slave message: {e} — raw: {raw[:200]}")
        return None

    async def start(self):
        # Ensure enough threads for blocking pipe I/O + writes
        loop = asyncio.get_event_loop()
        loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=32))

        await self.db.initialize()

        # Discover active links to know which pipes to create
        links = await self.db.get_active_links()

        # Collect unique master and slave IDs
        master_ids: set[str] = set()
        slave_ids: set[str] = set()
        for link in links:
            master_ids.add(link["master_id"])
            slave_ids.add(link["slave_id"])

        # Defaults so EA can connect even without links configured
        if not master_ids:
            master_ids.add("master_1")
        if not slave_ids:
            slave_ids.add("slave_1")

        # Create master pipes (one per master)
        for mid in master_ids:
            pipe_name = f"copier_{mid}"
            ps = PipeServer(pipe_name, self._handle_master_message)
            self._pipe_servers.append(ps)
            logger.info(f"Master pipe: \\\\.\\pipe\\{pipe_name}")

        # Create slave pipes (cmd + ack per slave)
        for sid in slave_ids:
            cmd_name = f"copier_{sid}_cmd"
            ack_name = f"copier_{sid}_ack"

            cmd_ps = PipeServer(cmd_name, self._noop_handler, write_only=True)
            ack_ps = PipeServer(ack_name, self._handle_slave_ack)

            self._slave_cmd_pipes[sid] = cmd_ps
            self._pipe_servers.append(cmd_ps)
            self._pipe_servers.append(ack_ps)
            logger.info(f"Slave pipes: \\\\.\\pipe\\{cmd_name}, \\\\.\\pipe\\{ack_name}")

        # Start all pipe servers as background tasks
        for ps in self._pipe_servers:
            asyncio.create_task(ps.start())

        logger.info(f"Hub Service started — {len(self._pipe_servers)} pipes listening")
        asyncio.create_task(self._health_loop())
        await self._run_forever()

    @staticmethod
    async def _noop_handler(raw: str) -> str | None:
        return None

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
