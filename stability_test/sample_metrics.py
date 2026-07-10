"""Standalone metrics sampler for the MS3 stability run.

Samples once per interval (default 60 s):
  - Hub process (python -m hub.main): CPU %, RSS (working set), private bytes
  - SQLite files: copier.db, copier.db-wal, copier.db-shm sizes

Appends rows to a CSV file. Stdlib-only — no psutil, no project imports —
so this folder can be copied to the server as-is and run with any Python 3.11+:

    python sample_metrics.py
    python sample_metrics.py --interval 30 --out metrics.csv

Stop with Ctrl+C. Rows are flushed after every sample, so the CSV is
always readable mid-run. If the Hub process is not found (restart, crash),
the row is still written with empty process fields — gaps stay visible.
"""

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_DB_PATH = os.path.join(
    os.environ.get("APPDATA", ""),
    "MetaQuotes", "Terminal", "Common", "Files",
    "TradeCopier", "copier.db",
)

CSV_COLUMNS = [
    "timestamp_utc",
    "hub_pid",
    "cpu_percent",
    "rss_mb",
    "private_mb",
    "db_mb",
    "wal_mb",
    "shm_mb",
    "note",
]

# Finds the Hub python process by command line and returns its CPU time
# (total seconds) and memory counters as JSON. Name filter keeps this
# powershell process itself (whose command line also contains 'hub.main')
# out of the match.
PS_QUERY = r"""
$p = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" |
     Where-Object { $_.CommandLine -match 'hub\.main' } |
     Select-Object -First 1
if ($p) {
    $gp = Get-Process -Id $p.ProcessId -ErrorAction SilentlyContinue
    if ($gp) {
        @{
            pid = $p.ProcessId
            cpu_seconds = [double]$gp.CPU
            working_set = $gp.WorkingSet64
            private_bytes = $gp.PrivateMemorySize64
        } | ConvertTo-Json -Compress
    }
}
"""


def query_hub_process() -> dict | None:
    """Return {pid, cpu_seconds, working_set, private_bytes} or None."""
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_QUERY],
            capture_output=True, text=True, timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    out = result.stdout.strip()
    if not out:
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def file_size_mb(path: str) -> str:
    try:
        return f"{os.path.getsize(path) / (1024 * 1024):.2f}"
    except OSError:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--interval", type=float, default=60.0,
                        help="seconds between samples (default 60)")
    parser.add_argument("--db", default=DEFAULT_DB_PATH,
                        help="path to copier.db (default: MQL5 Common Files)")
    parser.add_argument("--out", default=None,
                        help="output CSV (default: metrics_YYYYMMDD_HHMM.csv next to this script)")
    args = parser.parse_args()

    out_path = Path(args.out) if args.out else (
        Path(__file__).parent
        / f"metrics_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    )
    write_header = not out_path.exists() or out_path.stat().st_size == 0

    print(f"[sampler] db:  {args.db}", flush=True)
    print(f"[sampler] out: {out_path}", flush=True)
    print(f"[sampler] interval: {args.interval:.0f}s  (Ctrl+C to stop)", flush=True)

    prev_pid = None
    prev_cpu_seconds = None
    prev_time = None

    with open(out_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if write_header:
            writer.writerow(CSV_COLUMNS)
            f.flush()

        while True:
            now = time.monotonic()
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            proc = query_hub_process()

            pid = cpu_pct = rss_mb = private_mb = ""
            note = ""
            if proc is None:
                note = "hub process not found"
                prev_pid = prev_cpu_seconds = prev_time = None
            else:
                pid = proc["pid"]
                rss_mb = f"{proc['working_set'] / (1024 * 1024):.1f}"
                private_mb = f"{proc['private_bytes'] / (1024 * 1024):.1f}"
                cpu_seconds = proc.get("cpu_seconds") or 0.0
                if pid == prev_pid and prev_cpu_seconds is not None:
                    elapsed = now - prev_time
                    if elapsed > 0:
                        # % of one core; can exceed 100 on multi-core spikes
                        cpu_pct = f"{(cpu_seconds - prev_cpu_seconds) / elapsed * 100:.1f}"
                elif prev_pid is not None and pid != prev_pid:
                    note = f"hub pid changed {prev_pid} -> {pid} (restart?)"
                prev_pid, prev_cpu_seconds, prev_time = pid, cpu_seconds, now

            row = [
                ts, pid, cpu_pct, rss_mb, private_mb,
                file_size_mb(args.db),
                file_size_mb(args.db + "-wal"),
                file_size_mb(args.db + "-shm"),
                note,
            ]
            writer.writerow(row)
            f.flush()
            print("[sample] " + ",".join(str(v) for v in row), flush=True)

            time.sleep(max(0.0, args.interval - (time.monotonic() - now)))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n[sampler] stopped")
        sys.exit(0)
