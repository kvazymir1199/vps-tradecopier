# MS3 Stability Run — server test kit

Self-contained folder for the stability run on the server. Copy the whole
folder anywhere on the VPS and run with system Python 3.11+ — no packages,
no project imports required.

## 1. Start the sampler (before or right after Hub starts)

```powershell
python sample_metrics.py
```

Options:

| Flag | Default | Meaning |
|------|---------|---------|
| `--interval` | `60` | seconds between samples |
| `--db` | `%APPDATA%\MetaQuotes\Terminal\Common\Files\TradeCopier\copier.db` | path to copier.db |
| `--out` | `metrics_YYYYMMDD_HHMM.csv` next to the script | output CSV |

Each row: UTC timestamp, Hub PID, CPU % (of one core, averaged over the
interval), RSS and private memory in MB, sizes of `copier.db` / `-wal` /
`-shm` in MB, plus a note when the Hub process disappears or its PID
changes (restart detection). The CSV is flushed every sample — safe to
open/copy mid-run.

The first row has an empty CPU % (needs two samples to compute a delta).

## 2. Fix the baseline

Record in `journal.md` at the start of the run:

- Hub start time — from `hub.log` or the `hub_started` alert in `alerts_history`
- Initial `copier.db` size (the sampler's first row also captures it)
- Terminal/EA versions and which master/slave pairs are linked

## 3. Keep the run journal

Log every manual action in `journal.md` with a timestamp (opened a trade,
restarted a terminal, changed a mapping, network hiccup). Without it the
final `ms3-stability-run.md` report cannot correlate metric spikes with
events.

## 4. After the run

Bring back to the workstation:

- `metrics_*.csv`
- `journal.md`
- `hub.log` (from the DB folder)
