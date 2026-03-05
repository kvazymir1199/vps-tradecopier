"""Backup script for the Trade Copier SQLite database.

Usage:
    python scripts/backup_db.py <db_path> <backup_dir> [retention_days]

Steps:
    1. Connect to the DB and run PRAGMA wal_checkpoint(TRUNCATE)
    2. Copy the DB file to backup_dir with a date suffix
    3. Purge backups older than retention_days (default 30)
"""

from __future__ import annotations

import shutil
import sqlite3
import sys
import time
from pathlib import Path


def backup(db_path: str, backup_dir: str, retention_days: int = 30) -> Path:
    """Checkpoint WAL, copy DB file, purge old backups."""
    db = Path(db_path)
    if not db.exists():
        raise FileNotFoundError(f"Database not found: {db}")

    bak_dir = Path(backup_dir)
    bak_dir.mkdir(parents=True, exist_ok=True)

    # 1. Checkpoint WAL
    conn = sqlite3.connect(str(db))
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()

    # 2. Copy with date suffix
    date_suffix = time.strftime("%Y%m%d_%H%M%S")
    dest = bak_dir / f"{db.stem}_{date_suffix}{db.suffix}"
    shutil.copy2(str(db), str(dest))
    print(f"Backup created: {dest}")

    # 3. Purge old backups
    cutoff = time.time() - (retention_days * 86400)
    for f in bak_dir.glob(f"{db.stem}_*{db.suffix}"):
        if f.stat().st_mtime < cutoff:
            f.unlink()
            print(f"Purged old backup: {f}")

    return dest


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    db_path = sys.argv[1]
    backup_dir = sys.argv[2]
    retention_days = int(sys.argv[3]) if len(sys.argv) > 3 else 30

    backup(db_path, backup_dir, retention_days)


if __name__ == "__main__":
    main()
