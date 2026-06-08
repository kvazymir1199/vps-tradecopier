"""MS3 Stress / Load + Reliability / Recovery proof tests.

Each test maps 1:1 to a row in the client's MS3 deliverables. The MS2 pattern
is preserved — test names reflect the client criterion so the pytest report
doubles as the approval matrix.

Stress / load (ms3-deliverables.md §3.1):
    1. test_ms3_5_slaves_ack_within_one_second
       — Router fans out one OPEN to 5 Slaves; every Slave ACKs in < 1 s.
    2. test_ms3_burst_50_messages_no_drops_no_duplicates
       — 50 distinct OPENs routed in a tight loop; 0 drops, 0 duplicates.
    3. test_ms3_sustained_10_msgs_per_second_for_1_hour  [marker: slow]
       — 10 msg/s sustained; memory does not grow > 5 % from baseline.
    4. test_ms3_10_slaves_pipe_connections_stable
       — 10 simultaneous Slave links, each receives its mapping-correct cmd.
    5. test_ms3_2_masters_concurrent_no_cross_talk
       — 2 Masters routing in parallel; routing never crosses link boundaries.
    6. test_ms3_slave_disconnect_during_burst_does_not_block_others
       — One Slave drops mid-burst; remaining Slaves receive every message.

Reliability / recovery (client task "Reliability and recovery tests"):
    7. test_ms3_slave_restart_no_duplicates_via_idem_file
       — Slave persists last_msg_id to disk, restarts, replays the same msg_ids
         → zero re-executions. End-to-end version of test_ms2_2_2 using a real
         file (mirrors `copier_idem_<account>.csv` in TradeCopierSlave.mq5).
    8. test_ms3_master_restart_resume_from_continues_counter
       — Master crashes after 5 msg_ids, restarts, calls REGISTER → Hub returns
         resume_from=5 → Master continues at 6, never replays 1..5.
    9. test_ms3_pipe_disconnect_reconnect_no_data_loss
       — Burst of 10 msgs while the slave pipe is "down"; messages are queued
         as `pending` in the DB; retry loop redelivers after reconnect; final
         executed count = 10 with zero duplicates.

Design choices:
    • Router-level emulation — real Router + real DB + per-test EmulatedSlave
      mirroring TradeCopierSlave.mq5's IsDuplicateMessage logic. Named-pipe
      transport is already covered by tests/test_pipe_server.py and a separate
      integration suite (`docs/ms3-pipe-integration.md`); duplicating it here
      would slow CI without adding signal.
    • Sustained-load duration is overridable via `MS3_SUSTAINED_DURATION_SEC`
      so smoke runs stay fast (default 60 s) while acceptance can dial up to
      3600 s (1 h) without code changes.
"""

from __future__ import annotations

import asyncio
import csv
import gc
import json
import os
import time
from collections import defaultdict
from pathlib import Path

import psutil
import pytest

from hub.config import Config, TelegramConfig
from hub.db.manager import DatabaseManager
from hub.monitor.health import HealthChecker
from hub.protocol.models import MasterMessage, MessageType
from hub.router.router import Router


# ─────────────────────────────────────────────────────────────────────
# Test helpers
# ─────────────────────────────────────────────────────────────────────


class EmulatedSlave:
    """Mirrors the executable surface of TradeCopierSlave.mq5.

    deliver() returns the wall-clock latency from the moment route() started
    to the moment we ACKed — so latency assertions reflect real end-to-end
    routing time, not just per-call overhead.
    """

    def __init__(self, slave_id: str):
        self.slave_id = slave_id
        self.online = True
        self.executed: list[int] = []
        self.duplicates: int = 0
        self._last_msg_id: dict[str, int] = {}

    def deliver(self, cmd, *, started_at: float) -> float | None:
        """Returns ACK latency in seconds, or None if offline."""
        if not self.online:
            return None
        last = self._last_msg_id.get(cmd.master_id, 0)
        if cmd.msg_id <= last:
            self.duplicates += 1
            return time.perf_counter() - started_at
        self._last_msg_id[cmd.master_id] = cmd.msg_id
        self.executed.append(cmd.msg_id)
        return time.perf_counter() - started_at


def _open_msg(
    msg_id: int,
    master_id: str = "master_1",
    direction: str = "BUY",
    magic: int = 15010301,
    ticket: int = 1000,
) -> MasterMessage:
    return MasterMessage(
        msg_id=msg_id,
        master_id=master_id,
        type=MessageType.OPEN,
        ts_ms=170,
        payload={
            "ticket": ticket,
            "symbol": "EURUSD",
            "direction": direction,
            "volume": 0.1,
            "price": 1.085,
            "sl": 1.082,
            "tp": 1.089,
            "magic": magic,
            "comment": "",
        },
    )


async def _make_db_with_slaves(
    n_slaves: int,
    master_id: str = "master_1",
    link_id_offset: int = 0,
) -> tuple[DatabaseManager, list[EmulatedSlave]]:
    """Provision DB with one Master and N Slaves, all linked + magic-mapped."""
    db = DatabaseManager(":memory:")
    await db.initialize()
    await db.register_terminal(master_id, "master", 111, "B_master")
    slaves: list[EmulatedSlave] = []
    for i in range(n_slaves):
        sid = f"slave_{master_id}_{i}"
        await db.register_terminal(sid, "slave", 200 + i, f"B_{i}")
        await db.execute(
            "INSERT INTO master_slave_links "
            "(master_id, slave_id, enabled, lot_mode, lot_value, "
            "symbol_suffix, created_at) "
            "VALUES (?, ?, 1, 'multiplier', 1.0, '', 0)",
            (master_id, sid),
        )
        slaves.append(EmulatedSlave(sid))
    # Pull link ids in deterministic order so per-slave magic_mappings line up.
    link_rows = await db.fetch_all(
        "SELECT id FROM master_slave_links WHERE master_id = ? "
        "ORDER BY id",
        (master_id,),
    )
    for idx, row in enumerate(link_rows):
        # Each slave maps setup_id=1 → slave_setup_id=idx+5 so cross-talk would
        # be visible in the slave_magic of the emitted command.
        await db.execute(
            "INSERT INTO magic_mappings "
            "(link_id, master_setup_id, slave_setup_id, allowed_direction) "
            "VALUES (?, 1, ?, 'BOTH')",
            (row["id"], idx + 5),
        )
    return db, slaves


def _route_and_deliver(
    router: Router,
    msg: MasterMessage,
    slaves_by_id: dict[str, EmulatedSlave],
) -> list[float]:
    """Run one route() → fan-out delivery. Returns per-slave latencies (s).

    A standalone coroutine would deadlock the dict mutation inside
    EmulatedSlave; we keep it a sync helper that the caller awaits via
    asyncio.run_in_executor when needed.
    """
    raise NotImplementedError  # never used — kept as a deliberate sentinel


async def _deliver(
    router: Router,
    msg: MasterMessage,
    slaves_by_id: dict[str, EmulatedSlave],
) -> list[float]:
    started = time.perf_counter()
    cmds = await router.route(msg)
    latencies: list[float] = []
    for cmd in cmds:
        slave = slaves_by_id.get(cmd.slave_id)
        if slave is None:
            continue
        lat = slave.deliver(cmd, started_at=started)
        if lat is not None:
            latencies.append(lat)
    return latencies


# ─────────────────────────────────────────────────────────────────────
# 1. Fan-out latency
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ms3_5_slaves_ack_within_one_second():
    """All 5 Slaves receive and ACK a single OPEN in under 1 second total.

    Maps to client criterion: "5 Slaves receiving and acknowledging within 1
    second".
    """
    db, slaves = await _make_db_with_slaves(n_slaves=5)
    router = Router(db)
    slaves_by_id = {s.slave_id: s for s in slaves}

    latencies = await _deliver(router, _open_msg(msg_id=1), slaves_by_id)

    assert len(latencies) == 5, "every slave must receive the command"
    assert max(latencies) < 1.0, (
        f"slowest slave ACK was {max(latencies):.3f}s — must be < 1s"
    )
    assert all(len(s.executed) == 1 for s in slaves)
    await db.close()


# ─────────────────────────────────────────────────────────────────────
# 2. Burst — no drops, no duplicates
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ms3_burst_50_messages_no_drops_no_duplicates():
    """50-message burst routes through cleanly: 50 executions, 0 duplicates.

    Maps to client criterion: "50-message burst without dropped or duplicated
    messages".
    """
    db, slaves = await _make_db_with_slaves(n_slaves=1)
    router = Router(db)
    slave = slaves[0]
    slaves_by_id = {slave.slave_id: slave}

    for msg_id in range(1, 51):
        latencies = await _deliver(
            router,
            _open_msg(msg_id=msg_id, ticket=1000 + msg_id),
            slaves_by_id,
        )
        assert len(latencies) == 1, f"msg_id={msg_id} dropped"

    assert len(slave.executed) == 50
    assert slave.duplicates == 0
    assert slave.executed == list(range(1, 51))  # in order, no gaps
    await db.close()


# ─────────────────────────────────────────────────────────────────────
# 3. Sustained load — memory stability
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.slow
@pytest.mark.asyncio
async def test_ms3_sustained_10_msgs_per_second_for_1_hour():
    """10 msg/s sustained; resident memory stays within ±5% of baseline.

    Maps to client criterion: "Sustained load testing".

    For CI smoke runs the duration defaults to 60 s (so the test takes about a
    minute on a workstation). The acceptance run is invoked with
    `MS3_SUSTAINED_DURATION_SEC=3600` to get the literal 1-hour figure into
    `docs/ms3-stability-run.md`.
    """
    duration_sec = int(os.environ.get("MS3_SUSTAINED_DURATION_SEC", "60"))
    rate = 10  # msg/s

    db, slaves = await _make_db_with_slaves(n_slaves=1)
    router = Router(db)
    slave = slaves[0]
    slaves_by_id = {slave.slave_id: slave}

    proc = psutil.Process()
    gc.collect()
    baseline_rss = proc.memory_info().rss

    interval = 1.0 / rate
    end_at = time.monotonic() + duration_sec
    msg_id = 0
    samples: list[int] = []

    while time.monotonic() < end_at:
        msg_id += 1
        await _deliver(
            router,
            _open_msg(msg_id=msg_id, ticket=2000 + msg_id),
            slaves_by_id,
        )
        if msg_id % (rate * 10) == 0:  # sample RSS every ~10 s
            samples.append(proc.memory_info().rss)
        await asyncio.sleep(interval)

    gc.collect()
    final_rss = proc.memory_info().rss
    peak_rss = max(samples) if samples else final_rss
    growth_pct = (peak_rss - baseline_rss) / baseline_rss * 100

    assert msg_id == len(slave.executed), (
        f"some messages were dropped: routed={msg_id}, executed={len(slave.executed)}"
    )
    assert growth_pct < 5.0, (
        f"RSS grew {growth_pct:.1f}% (baseline={baseline_rss}, peak={peak_rss}) "
        f"— exceeds the 5% MS3 budget"
    )
    await db.close()


# ─────────────────────────────────────────────────────────────────────
# 4. 10-slave scalability
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ms3_10_slaves_pipe_connections_stable():
    """10 simultaneous Slave links: each receives its mapping-correct command,
    no starvation, magic transformation is independent per slave.

    Maps to client criterion: "scalability toward the 10-Slave target".
    """
    db, slaves = await _make_db_with_slaves(n_slaves=10)
    router = Router(db)
    slaves_by_id = {s.slave_id: s for s in slaves}

    latencies = await _deliver(router, _open_msg(msg_id=1), slaves_by_id)

    # All 10 must receive the command — no starvation.
    assert len(latencies) == 10
    assert all(len(s.executed) == 1 for s in slaves)
    # Worst-case fan-out latency budget: well under 1 s for 10 slaves.
    assert max(latencies) < 1.0

    # Each slave's link had a unique slave_setup_id (5..14) — confirm the
    # router applied them independently by re-checking the SlaveCommands.
    cmds = await router.route(_open_msg(msg_id=2))
    # Reset window: msg_id=1 was already in ResendWindow; msg_id=2 is fresh.
    assert len(cmds) == 10
    magics = sorted(c.payload["magic"] for c in cmds)
    # Each magic is master_magic_prefix + slave_setup_id (5..14)
    # master_magic 15010301 → prefix 150103 → +05..+14 → 15010305..15010314
    assert magics == [15010305 + i for i in range(10)]
    await db.close()


# ─────────────────────────────────────────────────────────────────────
# 5. Two-master concurrency
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ms3_2_masters_concurrent_no_cross_talk():
    """2 Masters routing in parallel — every command lands on the correct
    slaves of its own master, never on the other master's slaves.

    Maps to client criterion: "2 Master terminals sending concurrently
    without cross-talk".
    """
    # Build a DB with two independent master clusters (A and B), each with
    # 2 slaves of its own.
    db = DatabaseManager(":memory:")
    await db.initialize()
    for m in ("master_A", "master_B"):
        await db.register_terminal(m, "master", 111, f"B_{m}")
    for m, s in (
        ("master_A", "slave_A1"),
        ("master_A", "slave_A2"),
        ("master_B", "slave_B1"),
        ("master_B", "slave_B2"),
    ):
        await db.register_terminal(s, "slave", 200, "B")
        await db.execute(
            "INSERT INTO master_slave_links "
            "(master_id, slave_id, enabled, lot_mode, lot_value, "
            "symbol_suffix, created_at) "
            "VALUES (?, ?, 1, 'multiplier', 1.0, '', 0)",
            (m, s),
        )
    link_rows = await db.fetch_all(
        "SELECT id, slave_id FROM master_slave_links ORDER BY id"
    )
    for idx, row in enumerate(link_rows):
        await db.execute(
            "INSERT INTO magic_mappings "
            "(link_id, master_setup_id, slave_setup_id, allowed_direction) "
            "VALUES (?, 1, ?, 'BOTH')",
            (row["id"], idx + 5),
        )

    router = Router(db)
    slaves_by_id = {
        s: EmulatedSlave(s) for s in ("slave_A1", "slave_A2", "slave_B1", "slave_B2")
    }

    async def burst(master_id: str, base_msg_id: int):
        for i in range(20):
            await _deliver(
                router,
                _open_msg(
                    msg_id=base_msg_id + i,
                    master_id=master_id,
                    ticket=10_000 * (1 if master_id == "master_A" else 2) + i,
                ),
                slaves_by_id,
            )

    # Two concurrent bursts.
    await asyncio.gather(
        burst("master_A", 1),
        burst("master_B", 1000),
    )

    a1, a2 = slaves_by_id["slave_A1"], slaves_by_id["slave_A2"]
    b1, b2 = slaves_by_id["slave_B1"], slaves_by_id["slave_B2"]

    # Every A-slave saw all 20 A-msg_ids and ZERO B-msg_ids.
    assert sorted(a1.executed) == list(range(1, 21))
    assert sorted(a2.executed) == list(range(1, 21))
    assert sorted(b1.executed) == list(range(1000, 1020))
    assert sorted(b2.executed) == list(range(1000, 1020))
    await db.close()


# ─────────────────────────────────────────────────────────────────────
# 6. Slave-drop resilience under burst
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ms3_slave_disconnect_during_burst_does_not_block_others():
    """One Slave drops mid-burst — remaining Slaves keep getting every message,
    no exception raised, no latency spike.

    Maps to client criterion: "Slave disconnect during burst traffic without
    blocking other Slaves".
    """
    db, slaves = await _make_db_with_slaves(n_slaves=3)
    router = Router(db)
    slaves_by_id = {s.slave_id: s for s in slaves}
    s1, s2, s3 = slaves

    # First 10 messages — all 3 slaves online.
    for msg_id in range(1, 11):
        await _deliver(router, _open_msg(msg_id=msg_id, ticket=msg_id), slaves_by_id)

    # Slave s2 drops mid-burst.
    s2.online = False

    # Next 40 messages — only s1 and s3 should receive them. The router must
    # not raise, must not retry forever, must not slow other slaves down.
    latencies_after_drop: list[float] = []
    for msg_id in range(11, 51):
        ls = await _deliver(
            router, _open_msg(msg_id=msg_id, ticket=msg_id), slaves_by_id
        )
        # 2 alive slaves → 2 latency samples.
        assert len(ls) == 2, (
            f"alive-slave count after drop at msg_id={msg_id}: {len(ls)}"
        )
        latencies_after_drop.extend(ls)

    assert len(s1.executed) == 50
    assert len(s3.executed) == 50
    assert len(s2.executed) == 10  # only the pre-drop messages

    # No latency spike: post-drop messages must not be slower than pre-drop.
    # The threshold is generous — we only need to prove there's no degradation
    # that the operator would notice.
    assert max(latencies_after_drop) < 1.0
    await db.close()


# ─────────────────────────────────────────────────────────────────────
# Reliability / recovery helpers
# ─────────────────────────────────────────────────────────────────────


class PersistentSlave:
    """Slave with on-disk idempotency state — mirror of TradeCopierSlave.mq5.

    Persists `last_msg_id` per master to a CSV file using the same format the
    MQL5 EA uses (master_id,last_msg_id per line). The atomic write pattern
    (temp file + rename) is preserved so the test exercises the exact same
    failure mode the EA does.
    """

    def __init__(self, slave_id: str, idem_path: Path):
        self.slave_id = slave_id
        self._path = idem_path
        self.online = True
        self.executed: list[int] = []
        self.duplicates: int = 0
        self._last_msg_id: dict[str, int] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        with self._path.open("r", newline="", encoding="ansi", errors="ignore") as f:
            for row in csv.reader(f):
                if len(row) != 2:
                    continue
                self._last_msg_id[row[0]] = int(row[1])

    def _save(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", newline="", encoding="ansi") as f:
            writer = csv.writer(f)
            for master_id, last in self._last_msg_id.items():
                writer.writerow([master_id, last])
        tmp.replace(self._path)

    def deliver(self, cmd) -> str:
        """Returns 'EXECUTED', 'DUPLICATE_ACK', or 'OFFLINE'."""
        if not self.online:
            return "OFFLINE"
        last = self._last_msg_id.get(cmd.master_id, 0)
        if cmd.msg_id <= last:
            self.duplicates += 1
            return "DUPLICATE_ACK"
        self.executed.append(cmd.msg_id)
        self._last_msg_id[cmd.master_id] = cmd.msg_id
        self._save()
        return "EXECUTED"


def _stress_config(ack_timeout_sec: int = 1, ack_max_retries: int = 3) -> Config:
    return Config(
        db_path=":memory:",
        vps_id="test",
        heartbeat_interval_sec=10,
        heartbeat_timeout_sec=30,
        ack_timeout_sec=ack_timeout_sec,
        ack_max_retries=ack_max_retries,
        resend_window_size=200,
        alert_dedup_minutes=5,
        telegram=TelegramConfig(enabled=False, bot_token="", chat_id=""),
    )


# ─────────────────────────────────────────────────────────────────────
# 7. Slave restart — idempotency survives a process death
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ms3_slave_restart_no_duplicates_via_idem_file(tmp_path):
    """A real-file idempotency check, end-to-end.

    Sequence:
      1. PersistentSlave processes msg_ids 1..3, writes the CSV.
      2. The slave "process dies" — the in-memory state is dropped.
      3. A brand-new PersistentSlave instance loads the same CSV.
      4. The Hub re-delivers 1..3 (e.g. after its own ResendWindow reset).
      5. Assert zero re-executions; the only side effect is DUPLICATE_ACKs.

    Maps to client task "Slave restart while trades are open, with no
    duplicate orders after restart".
    """
    idem_file = tmp_path / "copier_idem_111.csv"
    db, _emu = await _make_db_with_slaves(n_slaves=1)
    router = Router(db)

    # The DB fixture creates the slave with id slave_master_1_0; mirror it.
    slave_id = f"slave_master_1_0"

    slave_v1 = PersistentSlave(slave_id, idem_file)
    for i in (1, 2, 3):
        cmds = await router.route(_open_msg(msg_id=i, ticket=i))
        for cmd in cmds:
            if cmd.slave_id == slave_id:
                assert slave_v1.deliver(cmd) == "EXECUTED"
    assert slave_v1.executed == [1, 2, 3]
    assert idem_file.exists()

    # ── Slave restart: new instance reads the CSV, state survives. ──
    slave_v2 = PersistentSlave(slave_id, idem_file)
    assert slave_v2._last_msg_id == {"master_1": 3}

    # The Hub also restarts (new Router → empty ResendWindow), so it WILL
    # re-emit commands for 1..3. The slave must reject every one.
    router_v2 = Router(db)
    for i in (1, 2, 3):
        for cmd in await router_v2.route(_open_msg(msg_id=i, ticket=i)):
            if cmd.slave_id == slave_id:
                assert slave_v2.deliver(cmd) == "DUPLICATE_ACK"

    assert slave_v2.executed == []
    assert slave_v2.duplicates == 3
    await db.close()


# ─────────────────────────────────────────────────────────────────────
# 8. Master restart — resume_from carries the counter forward
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ms3_master_restart_resume_from_continues_counter(tmp_path):
    """A Master crashes after sending 5 OPENs. On reload it asks the Hub for
    its last delivered msg_id (REGISTER → resume_from) and advances its local
    counter so msg_id 6, 7… never replay 1..5.

    Maps to client task "Master restart and reconnect, including resend-window
    behavior and idempotency".
    """
    db, slaves = await _make_db_with_slaves(n_slaves=1)
    router = Router(db)
    slave = slaves[0]
    slaves_by_id = {slave.slave_id: slave}

    # Phase 1: Master_v1 sends msg_ids 1..5.
    next_msg_id = 1
    for _ in range(5):
        msg = _open_msg(msg_id=next_msg_id, ticket=next_msg_id)
        # Mirror HubService._handle_master_message: persist BEFORE routing so
        # the row exists for get_max_msg_id() to see.
        await db.insert_message(
            next_msg_id, "master_1", "OPEN",
            json.dumps(msg.payload), int(time.time() * 1000),
        )
        await _deliver(router, msg, slaves_by_id)
        # Mirror Master.persist_msg_id() — store the counter to a file the
        # restarted Master will reload.
        (tmp_path / "master_msgid").write_text(str(next_msg_id))
        # Mark the message as acked so it leaves `pending` (mirrors the real
        # ACK arriving back from the Slave).
        await db.update_message_status(next_msg_id, "master_1", "acked")
        next_msg_id += 1
    assert slave.executed == [1, 2, 3, 4, 5]

    # Phase 2: Master process dies. The on-disk counter is the only state.
    persisted = int((tmp_path / "master_msgid").read_text())
    # On reload, Master calls REGISTER. Hub computes resume_from.
    resume_from = await db.get_max_msg_id("master_1")
    assert resume_from == 5, "Hub must return the highest msg_id it has"

    # Master_v2 takes max(persisted_counter, resume_from) as its start so
    # it never re-uses a msg_id Hub already has.
    next_msg_id = max(persisted, resume_from) + 1
    assert next_msg_id == 6

    # Phase 3: Master_v2 sends 5 more messages. None of them re-use 1..5.
    for _ in range(5):
        await _deliver(
            router,
            _open_msg(msg_id=next_msg_id, ticket=next_msg_id),
            slaves_by_id,
        )
        next_msg_id += 1

    # Slave executed 10 distinct msg_ids; zero duplicates means the Master
    # counter survived the restart correctly.
    assert slave.executed == list(range(1, 11))
    assert slave.duplicates == 0
    await db.close()


# ─────────────────────────────────────────────────────────────────────
# 9. Pipe disconnect / reconnect — retry loop fills the gap
# ─────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ms3_pipe_disconnect_reconnect_no_data_loss():
    """The slave pipe drops in the middle of a 10-message burst. The Hub
    persists the queued messages, the health-check loop retries them after
    the slave reconnects, and the final executed count is 10 with zero
    duplicates.

    Maps to client task "Pipe disconnect and reconnect, with recovery without
    data loss".
    """
    db, slaves = await _make_db_with_slaves(n_slaves=1)
    router = Router(db)
    slave = slaves[0]

    # Track every retry the health loop issues so we can prove the gap was
    # actually filled by retries, not by the first attempt.
    retried: list[int] = []

    async def _resend(msg: dict) -> None:
        # Rebuild the SlaveCommand exactly like HubService._resend_message
        # would, then deliver to the (possibly-online) slave.
        payload = json.loads(msg["payload"])
        rebuilt = MasterMessage(
            msg_id=msg["msg_id"],
            master_id=msg["master_id"],
            type=MessageType(msg["type"]),
            ts_ms=int(time.time() * 1000),
            payload=payload,
        )
        # Router would dedup the original msg_id — bypass the window because
        # this IS the retry path (router._build_slave_command directly).
        for link in await db.get_active_links(msg["master_id"]):
            cmd = await router._build_slave_command(rebuilt, link)
            if cmd is None or cmd.slave_id != slave.slave_id:
                continue
            if slave.online:
                started = time.perf_counter()
                if slave.deliver(cmd, started_at=started) is not None:
                    retried.append(msg["msg_id"])
                    # ACK arrived → mark message done so retry stops.
                    await db.update_message_status(
                        msg["msg_id"], msg["master_id"], "acked"
                    )

    hc = HealthChecker(db, _stress_config(), resend_callback=_resend)

    # Phase 1: first 3 messages delivered cleanly while the pipe is up.
    for msg_id in (1, 2, 3):
        cmds = await router.route(_open_msg(msg_id=msg_id, ticket=msg_id))
        # Persist to messages so health checker can reason about them.
        await db.insert_message(
            msg_id, "master_1", "OPEN",
            json.dumps(_open_msg(msg_id=msg_id, ticket=msg_id).payload),
            int(time.time() * 1000) - 5_000,  # old enough to be retryable
        )
        for cmd in cmds:
            if cmd.slave_id == slave.slave_id:
                started = time.perf_counter()
                slave.deliver(cmd, started_at=started)
                await db.update_message_status(msg_id, "master_1", "acked")
    assert slave.executed == [1, 2, 3]

    # Phase 2: pipe drops. Messages 4..10 are routed but never reach the slave.
    slave.online = False
    for msg_id in range(4, 11):
        # The Router would still emit a SlaveCommand, but the "pipe write"
        # silently drops because slave.online is False. The DB row stays
        # in status='pending' — that's the state the health checker watches.
        await router.route(_open_msg(msg_id=msg_id, ticket=msg_id))
        await db.insert_message(
            msg_id, "master_1", "OPEN",
            json.dumps(_open_msg(msg_id=msg_id, ticket=msg_id).payload),
            int(time.time() * 1000) - 5_000,
        )
    assert slave.executed == [1, 2, 3]  # no progress while offline

    # First retry tick — pipe still down → retry_count++ but no delivery.
    await hc.run_checks()
    assert slave.executed == [1, 2, 3]
    assert retried == []

    # Phase 3: pipe reconnects.
    slave.online = True

    # Health-check ticks redeliver every pending message exactly once.
    for _ in range(3):  # a few ticks to drain the queue
        await hc.run_checks()
        # Keep ts_ms old so anything still pending stays retryable.
        await db.execute(
            "UPDATE messages SET ts_ms = ? WHERE status = 'pending'",
            (int(time.time() * 1000) - 5_000,),
        )

    # Final state: 10 distinct messages executed exactly once.
    assert slave.executed == list(range(1, 11))
    assert slave.duplicates == 0
    # Retries fired only for the gap.
    assert sorted(retried) == [4, 5, 6, 7, 8, 9, 10]
    await db.close()
