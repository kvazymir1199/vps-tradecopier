# Milestone 3 — Delivery Package

Everything the MS3 acceptance needs, in one place. Documents live in the
repository (single source of truth); this folder carries the run
**artifacts** that back them, plus this index.

## Start here

All documents are included in `docs/` inside this package (snapshots of
the repository originals at the pinned commit).

| Document | Purpose |
|---|---|
| [`docs/ms3-approval-evidence.md`](docs/ms3-approval-evidence.md) | **Acceptance matrix** — every client criterion → its proof (test name / report section / artifact) |
| [`docs/ms3-stability-run.md`](docs/ms3-stability-run.md) | Stability run report: 35 h 51 m continuous, 0 restarts, 0 unhandled exceptions, reconciliation 116/116 |
| [`docs/ms3-pytest-output.txt`](docs/ms3-pytest-output.txt) | Canonical test run at the pinned commit — 189 passed |
| [`docs/journal.md`](docs/journal.md) | Run journal — every event with operator-confirmed root cause |
| [`docs/runbook.md`](docs/runbook.md) | **Runbook / handover guide**: server setup (12 phases), daily operations, health-check checklist, operator Telegram commands, troubleshooting, configuration reference |

## Artifacts in this folder

| Path | Contents |
|---|---|
| `artifacts/metrics_20260708_0614.csv`, `artifacts/metrics_20260709_0720.csv` | Hub CPU / RSS / DB-size samples every 60 s for the whole window (`stability_test/sample_metrics.py`) |
| `artifacts/hub.redacted.log` | Full Hub log for the window. Bot token redacted (`bot<TOKEN-REDACTED>`); otherwise byte-identical to the VPS original |
| `artifacts/reconciliation-output.txt` | Output of `stability_test/reconcile_reports.py`: 116/116 deliveries, 0 duplicates, 0 losses |
| `reports/ReportHistory-*.xlsx` | Trade history exported from all 6 terminals (2 masters + 5 slaves; RoboForex 67185418 hosts a master and a slave on one account) — the brokers' own records |

## Binaries & source

| Item | Path |
|---|---|
| Compiled EAs | `ea/Master/TradeCopierMaster.ex5`, `ea/Slave/TradeCopierSlave.ex5` (built from the sources at this commit) |
| EA source | `ea/Master/*.mq5`, `ea/Slave/*.mq5`, `ea/Include/*.mqh` |
| DB schema | `hub/db/schema.sql` |
| Hub / API / UI source | `hub/`, `web/` |

Configuration is stored in the SQLite `config` table — seeded with
defaults on first Hub start, edited via the web panel Settings page. See
"Configuration Reference" in the repo README. There is no config file to
template.

## Reproducing the evidence from a clean clone

```bash
git clone <repo-url> && cd <repo>
uv sync
uv run pytest -v                       # expect: 189 passed
uv run --with openpyxl python stability_test/reconcile_reports.py \
    --db <path-to-copier.db> --reports delivery/ms3/reports
```

## Known follow-ups (documented, non-blocking)

- B2: web-panel "test alert" is stored as `hub_started` in alert history.
- B3: no UI action to remove stale terminal records.
- Operational: rotate the Telegram bot token before production use (the
  test token was present in unredacted VPS logs).
