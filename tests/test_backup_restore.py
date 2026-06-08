"""DB backup / restore proof tests.

Maps to client task "Database recovery test using the backup and restore
procedure". The interface under test is the same one the operator runs from
the command line:

    python scripts/backup_db.py  <live_db>  <backup_dir>  [retention_days]
    python scripts/restore_db.py <backup_file>  <live_db>

Each test exercises the public `backup()` / `restore()` functions to keep the
contract verifiable from the runbook without spawning subprocesses.
"""

from __future__ import annotations

import shutil
import sqlite3
import time
from pathlib import Path

import pytest

from hub.db.manager import DatabaseManager
from scripts.backup_db import backup
from scripts.restore_db import RestoreError, restore


async def _seed_live_db(path: Path) -> None:
    """Populate a Trade Copier DB with the rows we expect to survive restore."""
    mgr = DatabaseManager(str(path))
    await mgr.initialize()
    await mgr.seed_config_defaults()
    await mgr.register_terminal("master_1", "master", 111, "BrokerA")
    await mgr.register_terminal("slave_1", "slave", 222, "BrokerB")
    await mgr.execute(
        "INSERT INTO master_slave_links "
        "(master_id, slave_id, enabled, lot_mode, lot_value, "
        "symbol_suffix, created_at) "
        "VALUES ('master_1', 'slave_1', 1, 'multiplier', 1.0, '', 0)"
    )
    await mgr.execute(
        "INSERT INTO magic_mappings "
        "(link_id, master_setup_id, slave_setup_id, allowed_direction) "
        "VALUES (1, 1, 5, 'BOTH')"
    )
    await mgr.close()


@pytest.mark.asyncio
async def test_backup_creates_file_and_integrity_passes(tmp_path):
    live = tmp_path / "copier.db"
    bak_dir = tmp_path / "backups"
    await _seed_live_db(live)

    dest = backup(str(live), str(bak_dir))
    assert dest.exists()
    # The destination must itself be a valid SQLite database.
    conn = sqlite3.connect(str(dest))
    try:
        row = conn.execute("PRAGMA integrity_check").fetchone()
    finally:
        conn.close()
    assert row and row[0] == "ok"


@pytest.mark.asyncio
async def test_backup_purges_files_older_than_retention(tmp_path):
    live = tmp_path / "copier.db"
    bak_dir = tmp_path / "backups"
    await _seed_live_db(live)

    # First backup, then back-date it so the next call considers it stale.
    older = backup(str(live), str(bak_dir))
    stale_ts = time.time() - (40 * 86400)  # 40 days ago
    import os
    os.utime(older, (stale_ts, stale_ts))

    # The backup filename includes a per-second timestamp — wait so the next
    # backup lands in a separate file rather than overwriting the stale one.
    time.sleep(1.1)

    # Second backup with 30-day retention — old one must be purged.
    newer = backup(str(live), str(bak_dir), retention_days=30)
    assert newer != older  # distinct filename
    assert not older.exists(), "stale backup should have been purged"
    assert newer.exists()


@pytest.mark.asyncio
async def test_restore_replaces_corrupted_live_db(tmp_path):
    """The headline scenario: live DB is corrupted, restore returns it to a
    queryable state with all rows intact."""
    live = tmp_path / "copier.db"
    bak_dir = tmp_path / "backups"
    await _seed_live_db(live)

    backup_file = backup(str(live), str(bak_dir))

    # Corrupt the live file. The header check during sqlite3.connect won't
    # always fire, but PRAGMA integrity_check on the corrupted file does.
    with live.open("r+b") as f:
        f.seek(100)
        f.write(b"\x00" * 4096)

    # Sanity: confirm the corruption surfaces before restore. SQLite can
    # raise DatabaseError (file unreadable) OR return a non-"ok" row depending
    # on how the corruption lines up with page boundaries — accept either.
    corrupted = False
    try:
        conn = sqlite3.connect(str(live))
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
            corrupted = (row is None) or (row[0] != "ok")
        finally:
            conn.close()
    except sqlite3.DatabaseError:
        corrupted = True
    assert corrupted, "test setup did not actually corrupt the DB"

    # Restore overwrites the corrupted file.
    restore(str(backup_file), str(live))

    # Post-restore the original rows must be queryable.
    conn = sqlite3.connect(str(live))
    try:
        rows = conn.execute(
            "SELECT terminal_id, role FROM terminals ORDER BY terminal_id"
        ).fetchall()
    finally:
        conn.close()
    assert rows == [("master_1", "master"), ("slave_1", "slave")]

    # The "before-restore" snapshot was preserved alongside.
    snapshots = list(live.parent.glob("copier.pre_restore_*.db"))
    assert len(snapshots) == 1


@pytest.mark.asyncio
async def test_restore_rejects_invalid_backup(tmp_path):
    live = tmp_path / "copier.db"
    await _seed_live_db(live)

    bad_backup = tmp_path / "bad.db"
    bad_backup.write_bytes(b"not a sqlite file at all")

    with pytest.raises(RestoreError):
        restore(str(bad_backup), str(live))

    # Live DB untouched.
    conn = sqlite3.connect(str(live))
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM terminals"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == 2


@pytest.mark.asyncio
async def test_restore_refuses_locked_destination(tmp_path):
    """If the Hub is running (holds a write-lock), restore must refuse — the
    Hub would otherwise overwrite the freshly-restored file at the next WAL
    checkpoint and silently lose data."""
    live = tmp_path / "copier.db"
    bak_dir = tmp_path / "backups"
    await _seed_live_db(live)
    backup_file = backup(str(live), str(bak_dir))

    # Hold a writer lock on the live DB to simulate the Hub being up.
    locker = sqlite3.connect(str(live), timeout=0.1)
    locker.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(RestoreError):
            restore(str(backup_file), str(live))
    finally:
        locker.rollback()
        locker.close()


@pytest.mark.asyncio
async def test_restore_clears_stale_wal_sidecar(tmp_path):
    """Leftover -wal / -shm from the previous Hub run would re-introduce
    stale frames after restore. The restore script must remove them."""
    live = tmp_path / "copier.db"
    bak_dir = tmp_path / "backups"
    await _seed_live_db(live)
    backup_file = backup(str(live), str(bak_dir))

    # Plant fake sidecars that would never match the restored DB header.
    wal = Path(str(live) + "-wal")
    shm = Path(str(live) + "-shm")
    wal.write_bytes(b"stale-wal")
    shm.write_bytes(b"stale-shm")

    restore(str(backup_file), str(live))

    assert not wal.exists(), "stale -wal must be removed during restore"
    assert not shm.exists(), "stale -shm must be removed during restore"
