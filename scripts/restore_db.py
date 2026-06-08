"""Restore script for the Trade Copier SQLite database.

Usage:
    python scripts/restore_db.py <backup_file> <db_path>

Steps:
    1. Sanity-check that the backup is a valid SQLite database
       (PRAGMA integrity_check on the backup file, not the destination).
    2. Refuse to overwrite a destination that is currently locked
       by another process (Hub must be stopped first — that's by design,
       online restore is out of scope).
    3. Copy the backup over the destination.
    4. Remove leftover WAL/SHM sidecar files; otherwise SQLite may surface
       stale frames from the previous WAL on the next open.
    5. Open the restored DB and run PRAGMA integrity_check; print "OK" or
       exit non-zero with the SQLite-reported error.
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
import time
from pathlib import Path


class RestoreError(RuntimeError):
    """Raised when the restore preconditions aren't met."""


def _backup_is_valid_sqlite(backup: Path) -> None:
    """integrity_check the backup so we never overwrite the destination with
    a half-copied or corrupt file. sqlite3 raises DatabaseError on a file
    that isn't even a SQLite header — translate that to our RestoreError so
    callers only have to handle one exception type."""
    try:
        conn = sqlite3.connect(str(backup))
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise RestoreError(f"backup is not a valid SQLite file: {exc}") from exc
    if not row or row[0] != "ok":
        raise RestoreError(
            f"backup failed integrity_check: {row[0] if row else '<empty>'}"
        )


def _destination_is_locked(dest: Path) -> bool:
    """Best-effort check: open the DB with a short busy_timeout and try a
    write transaction. If another connection holds the lock (Hub running),
    this raises and we abort."""
    if not dest.exists():
        return False
    try:
        conn = sqlite3.connect(str(dest), timeout=0.5)
        try:
            conn.execute("BEGIN IMMEDIATE")
            conn.rollback()
            return False
        finally:
            conn.close()
    except sqlite3.OperationalError:
        return True


def restore(backup_path: str, db_path: str) -> Path:
    """Replace the live DB with `backup_path`. Returns the restored path."""
    backup = Path(backup_path)
    if not backup.exists():
        raise FileNotFoundError(f"Backup not found: {backup}")

    dest = Path(db_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    _backup_is_valid_sqlite(backup)

    if _destination_is_locked(dest):
        raise RestoreError(
            f"destination DB is locked — stop the Hub before restoring: {dest}"
        )

    # Stamp the existing file in case the operator wants to revert.
    if dest.exists():
        stamp = time.strftime("%Y%m%d_%H%M%S")
        side = dest.with_suffix(f".pre_restore_{stamp}{dest.suffix}")
        shutil.copy2(str(dest), str(side))
        print(f"Existing DB preserved at: {side}")

    shutil.copy2(str(backup), str(dest))

    # WAL/SHM left over from the previous Hub run would surface stale frames.
    for ext in ("-wal", "-shm"):
        side = Path(str(dest) + ext)
        if side.exists():
            side.unlink()

    # Final sanity check on the restored file.
    try:
        conn = sqlite3.connect(str(dest))
        try:
            row = conn.execute("PRAGMA integrity_check").fetchone()
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise RestoreError(f"restored DB is not a valid SQLite file: {exc}") from exc
    if not row or row[0] != "ok":
        raise RestoreError(
            f"restored DB failed integrity_check: {row[0] if row else '<empty>'}"
        )

    print(f"Restore OK: {backup} → {dest}")
    return dest


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    try:
        restore(sys.argv[1], sys.argv[2])
    except (FileNotFoundError, RestoreError) as exc:
        print(f"restore failed: {exc}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
