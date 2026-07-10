# MS3 Stability Run — journal

## Baseline
- Hub start time: 2026-07-08 04:46:08 UTC (restart 32 min after sampler start; PID 7364 → 10928, `hub.log` line 82854, `hub_started` alert delivered)
- Sampler start time: 2026-07-08 04:14:47 UTC
- Initial copier.db size: 45.73 MB (WAL 4.05 MB)
- Terminals / links: 2 Masters (OANDA 1715542650, RoboForex 67185418) × 5 Slaves each = 10 links, all `multiplier=1.0`, no suffix.
  Slaves: XM 168935786, IC Markets 52911415 (replaced by 52953732 mid-run, see Events), FxPro 591823116, RoboForex 67185418, AMarkets 7833734.
  Stale record: Tickmill 25333441 — disconnected since 2026-07-02, not linked, 0 heartbeats in window.

## Events

Format: `YYYY-MM-DD HH:MM (UTC) — action — expected effect`

| Time (UTC) | Action | Notes |
|------|--------|-------|
| 2026-07-08 04:14 | Started `sample_metrics.py` (60 s interval) | metrics_20260708_0614.csv |
| 2026-07-08 04:46 | Hub restarted (PID 7364 → 10928) | Cause: **TODO — confirm (manual restart? config change?)**. `hub_started` alert delivered. Official window starts here |
| 2026-07-08 ~04:46 | slave_52911415 NACK burst begins (53 NACKs `ORDER_FAILED` in first hour) | Cause: **TODO — confirm (AutoTrading off? symbol not tradable?)**. `consecutive_nacks` + `alert_storm` alerts fired, dedup engaged |
| 2026-07-09 ~04:00 | Master heartbeat gaps: master_1715542650 138 s, master_67185418 469 s (2 gaps) | Cause: **TODO — confirm (terminal restart? VPS load at night?)**. 3 `heartbeat_miss` alerts delivered — detection verified live |
| 2026-07-09 04:52 | slave_52911415 (IC Markets) disconnected | `slave_disconnected` alert delivered |
| 2026-07-09 04:53 | slave_52953732 (IC Markets) registered as replacement | New account on same broker; ReportHistory-52953732.xlsx exported from it |
| 2026-07-09 05:17→05:20 | Sampler restarted (3 min gap between CSVs) | metrics_20260709_0720.csv; Hub PID unchanged (10928) — Hub itself not restarted |
| 2026-07-09 13:19 | Test alerts fired from web panel (2×) | Recorded with `alert_type='hub_started'` — misclassification, see bug list |
| 2026-07-09 13:20 | DB snapshot copied for analysis (last heartbeat in snapshot) | Run continues on VPS |
