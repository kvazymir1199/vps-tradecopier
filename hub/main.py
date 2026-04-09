import asyncio
import concurrent.futures
import json
import logging
import os
import time
from pathlib import Path

from hub.config import Config, DB_PATH
from hub.db.manager import DatabaseManager
from hub.router.router import Router
from hub.transport.pipe_server import PipeServer
from hub.protocol.serializer import decode_master_message, encode_slave_command, decode_ack
from hub.monitor.health import HealthChecker
from hub.monitor.alerts import AlertSender

LOG_DIR = str(Path(DB_PATH).parent)
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
    def __init__(self):
        self.db = DatabaseManager(DB_PATH)
        self.config: Config | None = None
        self.router: Router | None = None
        self.alert_sender: AlertSender | None = None
        self.health_checker: HealthChecker | None = None
        self._pipe_servers: list[PipeServer] = []
        self._slave_cmd_pipes: dict[str, PipeServer] = {}
        self._known_masters: set[str] = set()
        self._known_slaves: set[str] = set()

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
                symbols = data.get("symbols", [])
                if symbols:
                    await self.db.save_terminal_symbols(terminal_id, symbols)
                    logger.info(f"Saved {len(symbols)} symbols for {terminal_id}")
                resume_from = await self.db.get_max_msg_id(terminal_id)
                logger.info(f"REGISTER: {terminal_id} ({role}) account={account} resume_from={resume_from}")
                return json.dumps({"ack_type": "ACK", "resume_from": resume_from}) + "\n"

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
                symbols = data.get("payload", {}).get("symbols", [])
                if symbols:
                    await self.db.save_terminal_symbols(terminal_id, symbols)
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
                symbols = data.get("symbols", [])
                if symbols:
                    await self.db.save_terminal_symbols(terminal_id, symbols)
                    logger.info(f"Saved {len(symbols)} symbols for {terminal_id}")
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
                symbols = data.get("payload", {}).get("symbols", [])
                if symbols:
                    await self.db.save_terminal_symbols(terminal_id, symbols)
                return None

            # ACK/NACK message
            ack = decode_ack(raw)
            logger.info(f"ACK from {ack.slave_id}: type={ack.ack_type} msg_id={ack.msg_id}")
            # Look up master_id from messages table for FK constraint
            master_id = await self.db.get_master_id_for_msg(ack.msg_id)
            if master_id:
                await self.db.insert_ack(
                    ack.msg_id, master_id, ack.slave_id,
                    ack.ack_type, ack.reason, ack.slave_ticket,
                    ack.ts_ms,
                )
            else:
                logger.warning(f"ACK msg_id={ack.msg_id} has no matching message, skipping")

        except Exception as e:
            logger.error(f"Error handling slave message: {e} — raw: {raw[:200]}")
        return None

    def _create_pipes(self, master_ids: set[str], slave_ids: set[str]):
        """Create and start PipeServers for new terminal IDs."""
        for mid in master_ids:
            if mid in self._known_masters:
                continue
            pipe_name = f"copier_{mid}"
            ps = PipeServer(pipe_name, self._handle_master_message)
            self._pipe_servers.append(ps)
            self._known_masters.add(mid)
            asyncio.create_task(ps.start())
            logger.info(f"Master pipe created: \\\\.\\pipe\\{pipe_name}")

        for sid in slave_ids:
            if sid in self._known_slaves:
                continue
            cmd_name = f"copier_{sid}_cmd"
            ack_name = f"copier_{sid}_ack"

            cmd_ps = PipeServer(cmd_name, self._noop_handler, write_only=True)
            ack_ps = PipeServer(ack_name, self._handle_slave_ack)

            self._slave_cmd_pipes[sid] = cmd_ps
            self._pipe_servers.append(cmd_ps)
            self._pipe_servers.append(ack_ps)
            self._known_slaves.add(sid)
            asyncio.create_task(cmd_ps.start())
            asyncio.create_task(ack_ps.start())
            logger.info(f"Slave pipes created: \\\\.\\pipe\\{cmd_name}, \\\\.\\pipe\\{ack_name}")

    async def start(self):
        # Ensure enough threads for blocking pipe I/O + writes
        loop = asyncio.get_event_loop()
        loop.set_default_executor(concurrent.futures.ThreadPoolExecutor(max_workers=32))

        await self.db.initialize()

        # Load config from DB (seed defaults on first launch)
        await self.db.seed_config_defaults()
        config_data = await self.db.get_config()
        self.config = Config.from_db(config_data)

        self.router = Router(self.db, self.config.resend_window_size)
        self.alert_sender = AlertSender(self.db, self.config)
        self.health_checker = HealthChecker(self.db, self.config, self._resend_message)

        # Collect terminal IDs from links AND registered terminals
        links = await self.db.get_active_links()
        terminals = await self.db.get_all_terminals()

        master_ids: set[str] = set()
        slave_ids: set[str] = set()
        for link in links:
            master_ids.add(link["master_id"])
            slave_ids.add(link["slave_id"])
        for t in terminals:
            if t["role"] == "master":
                master_ids.add(t["terminal_id"])
            elif t["role"] == "slave":
                slave_ids.add(t["terminal_id"])

        # Create pipes only for terminals that exist in DB
        self._create_pipes(master_ids, slave_ids)

        logger.info(f"Hub Service started — {len(self._pipe_servers)} pipes listening")
        asyncio.create_task(self._health_loop())
        asyncio.create_task(self._terminal_discovery_loop())
        await self._run_forever()

    @staticmethod
    async def _noop_handler(raw: str) -> str | None:
        return None

    async def _resend_message(self, msg: dict) -> None:
        """Retry delivery of an unACKed message by rebuilding and re-sending slave commands."""
        logger.info(
            f"Retrying msg_id={msg['msg_id']} for {msg['master_id']} "
            f"(attempt {msg['retry_count'] + 1}/{self.config.ack_max_retries})"
        )
        try:
            payload = json.loads(msg["payload"])
            master_msg = decode_master_message(json.dumps({
                "msg_id": msg["msg_id"],
                "master_id": msg["master_id"],
                "type": msg["type"],
                "ts_ms": int(time.time() * 1000),
                "payload": payload,
            }))
            links = await self.db.get_active_links(msg["master_id"])
            for link in links:
                cmd = await self.router._build_slave_command(master_msg, link)
                if cmd is None:
                    continue
                slave_pipe = self._slave_cmd_pipes.get(cmd.slave_id)
                if slave_pipe and slave_pipe._handle:
                    encoded = encode_slave_command(cmd)
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, slave_pipe._write, encoded)
                    logger.info(f"Retry forwarded {cmd.type} to {cmd.slave_id} (msg_id={cmd.msg_id})")
                else:
                    logger.warning(f"Retry: slave {cmd.slave_id} pipe not connected for msg_id={cmd.msg_id}")
        except Exception as e:
            logger.error(f"_resend_message error for msg_id={msg['msg_id']}: {e}")

    async def _terminal_discovery_loop(self):
        """Periodically check DB for newly registered terminals and create pipes."""
        while True:
            try:
                terminals = await self.db.get_all_terminals()
                new_masters: set[str] = set()
                new_slaves: set[str] = set()
                for t in terminals:
                    tid = t["terminal_id"]
                    if t["role"] == "master" and tid not in self._known_masters:
                        new_masters.add(tid)
                    elif t["role"] == "slave" and tid not in self._known_slaves:
                        new_slaves.add(tid)
                if new_masters or new_slaves:
                    self._create_pipes(new_masters, new_slaves)
            except Exception as e:
                logger.error(f"Terminal discovery error: {e}")
            await asyncio.sleep(2)

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
    hub = HubService()
    asyncio.run(hub.start())


if __name__ == "__main__":
    main()
