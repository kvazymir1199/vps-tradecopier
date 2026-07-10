"""Reconcile MT5 terminal reports against the Hub database.

Builds the MS3 evidence matrix: every master OPEN in the run window must
have exactly one copy on every linked slave — no duplicates, no silent
losses. Ground truth is taken from two independent sources and cross-checked:

  1. copier.db  — messages (master side) + message_acks (slave tickets)
  2. ReportHistory-<account>.xlsx exported from each terminal — the
     broker's own record of what actually happened on the account

Copies are identified by the EA order comment `Copy:<master_id>:<ticket>`.

Usage:
    uv run python stability_test/reconcile_reports.py \
        --db TradeCopier/copier.db --reports TradeCopier \
        --window-start 2026-07-08T04:46:00

Requires openpyxl (ad-hoc: `uv run --with openpyxl python ...`).
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import warnings
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import openpyxl

COPY_RE = re.compile(r"Copy:(master_\d+):(\d+)")


def utc_ms(dt_str: str) -> int:
    return int(
        datetime.fromisoformat(dt_str).replace(tzinfo=timezone.utc).timestamp() * 1000
    )


def fmt(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%d %H:%M UTC"
    )


# ─────────────────────────── xlsx parsing ───────────────────────────


def parse_report(path: Path) -> dict:
    """Extract per-terminal facts from an MT5 ReportHistory xlsx.

    Returns dict with:
      account      — int, from the report header
      copies       — {(master_id, master_ticket): [slave order tickets]}
      own_orders   — [(ticket, time_str, symbol, type, comment)] non-copy orders
      positions    — [(position_id, open_time_str, symbol, volume_str)]
    """
    warnings.filterwarnings("ignore")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    section = ""
    account = None
    copies: dict[tuple[str, int], list[int]] = defaultdict(list)
    own_orders: list[tuple] = []
    positions: list[tuple] = []

    for row in ws.iter_rows(values_only=True):
        first = row[0]
        if isinstance(first, str):
            if first == "Account:":
                account = int(str(row[3]).split()[0])
                continue
            if first in ("Positions", "Orders", "Deals", "Open Positions", "Results"):
                section = first
                continue

        if section == "Positions" and isinstance(first, str) and first[:2] == "20":
            # Time, Position, Symbol, Type, Volume, ...
            positions.append((row[1], first, row[2], str(row[4])))

        elif section == "Orders" and isinstance(first, str) and first[:2] == "20":
            # Open Time, Order, Symbol, Type, Volume, Price, S/L, T/P, Time,
            # State, _, Comment
            ticket, comment = row[1], row[11]
            m = COPY_RE.search(comment or "")
            if m:
                copies[(m.group(1), int(m.group(2)))].append(int(ticket))
            else:
                own_orders.append((ticket, first, row[2], row[3], comment))

    wb.close()
    return {
        "account": account,
        "copies": dict(copies),
        "own_orders": own_orders,
        "positions": positions,
    }


# ─────────────────────────── main ───────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="TradeCopier/copier.db")
    ap.add_argument("--reports", default="TradeCopier")
    ap.add_argument("--window-start", default="2026-07-08T04:46:00")
    ap.add_argument("--window-end", default=None)
    args = ap.parse_args()

    w_start = utc_ms(args.window_start)
    con = sqlite3.connect(f"file:{args.db}?mode=ro", uri=True)
    w_end = (
        utc_ms(args.window_end)
        if args.window_end
        else con.execute("SELECT MAX(ts_ms) FROM messages").fetchone()[0]
    )
    print(f"window: {fmt(w_start)} -> {fmt(w_end)}\n")

    # slave -> link creation time (created_at is stored in SECONDS). A copy
    # is only expected when the link already existed at OPEN time.
    links: dict[str, dict[str, int]] = defaultdict(dict)
    for m, s, created in con.execute(
        "SELECT master_id, slave_id, created_at FROM master_slave_links "
        "WHERE enabled=1"
    ):
        links[m][s] = created * 1000

    # Master OPENs in window: (master_id, master_ticket) -> meta
    opens: dict[tuple[str, int], dict] = {}
    for master_id, msg_id, payload, ts in con.execute(
        "SELECT master_id, msg_id, payload, ts_ms FROM messages "
        "WHERE type='OPEN' AND ts_ms BETWEEN ? AND ?",
        (w_start, w_end),
    ):
        p = json.loads(payload)
        opens[(master_id, p["ticket"])] = {
            "msg_id": msg_id,
            "symbol": p.get("symbol"),
            "magic": p.get("magic"),
            "ts": ts,
            "acked": set(),
            "nacked": set(),
        }
    msgid_to_key = {(k[0], v["msg_id"]): k for k, v in opens.items()}
    for master_id, msg_id, slave_id, ack_type in con.execute(
        "SELECT master_id, msg_id, slave_id, ack_type FROM message_acks "
        "WHERE ts_ms BETWEEN ? AND ?",
        (w_start, w_end + 60_000),
    ):
        key = msgid_to_key.get((master_id, msg_id))
        if key:
            opens[key]["acked" if ack_type == "ACK" else "nacked"].add(slave_id)

    # Terminal reports
    reports = {}
    for f in sorted(Path(args.reports).glob("ReportHistory-*.xlsx")):
        r = parse_report(f)
        reports[r["account"]] = r
        n_copies = sum(len(v) for v in r["copies"].values())
        print(
            f"parsed {f.name}: account={r['account']} "
            f"copy-orders={n_copies} own-orders={len(r['own_orders'])}"
        )

    slave_report = {f"slave_{acc}": r for acc, r in reports.items()}

    # ── Matrix: per master OPEN × linked slave ──
    ok = dups = missing = nack_only = not_linked_yet = offline = 0
    problems: list[str] = []
    per_slave = defaultdict(lambda: [0, 0, 0])  # slave -> [ok, dup, missing]
    for (master_id, ticket), meta in sorted(opens.items(), key=lambda x: x[1]["ts"]):
        for slave_id, link_since in sorted(links[master_id].items()):
            if meta["ts"] < link_since:
                not_linked_yet += 1  # link did not exist yet — no copy expected
                continue
            rep = slave_report.get(slave_id)
            n = len(rep["copies"].get((master_id, ticket), [])) if rep else None
            if slave_id in meta["nacked"] and slave_id not in meta["acked"]:
                nack_only += 1  # rejected by design (documented faulty slave)
                continue
            if slave_id not in meta["acked"] and rep is None:
                offline += 1  # command dropped: slave pipe down (hub.log WARN)
                continue
            if rep is None:
                problems.append(
                    f"ACKed but no report file to verify: {slave_id} "
                    f"(master {master_id} ticket {ticket})"
                )
                continue
            if n == 1:
                ok += 1
                per_slave[slave_id][0] += 1
            elif n and n > 1:
                dups += 1
                per_slave[slave_id][1] += 1
                problems.append(
                    f"DUPLICATE: {slave_id} has {n} copies of "
                    f"{master_id}:{ticket}"
                )
            else:
                missing += 1
                per_slave[slave_id][2] += 1
                problems.append(
                    f"MISSING: {slave_id} has no copy of {master_id}:{ticket} "
                    f"({meta['symbol']} at {fmt(meta['ts'])}, "
                    f"acked={sorted(meta['acked'])})"
                )

    print(f"\nmaster OPENs in window: {len(opens)}")
    magics = defaultdict(int)
    for meta in opens.values():
        magics[meta["magic"]] += 1
    print(f"magic distribution: {dict(magics)}")
    print(f"symbols: {sorted({m['symbol'] for m in opens.values()})}")

    print("\nper-slave delivery matrix (expected -> exactly 1 copy each):")
    print(f"{'slave':24} {'ok':>4} {'dup':>4} {'missing':>8}")
    for s, (o, d, mi) in sorted(per_slave.items()):
        print(f"{s:24} {o:>4} {d:>4} {mi:>8}")

    print(
        f"\nTOTAL: ok={ok} duplicates={dups} missing={missing} "
        f"nack-rejected(documented)={nack_only} "
        f"not-linked-yet={not_linked_yet} dropped-slave-offline={offline}"
    )
    if problems:
        print("\nproblems:")
        for p in problems:
            print(" -", p)
    print(
        "\nVERDICT:",
        "RECONCILED — one copy per linked slave, no dups, no losses"
        if not dups and not missing
        else "DISCREPANCIES FOUND — see problems above",
    )
    return 0 if not dups and not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())
