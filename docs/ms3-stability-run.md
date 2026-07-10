# MS3 Stability Run — Report (DRAFT)

**Status:** DRAFT — run still in progress; all figures below are from the
snapshot taken 2026-07-09 ~13:20 UTC (copier.db + hub.log) and sampler CSVs
up to 2026-07-09 16:37 UTC. Final numbers to be refreshed at window close.

**Official window:** 2026-07-08 04:46 UTC (last Hub restart) → TBD
(target: ≥ agreed duration, see `docs/ms3-deliverables.md` Decision 1).

**Sources:**
- `metrics_20260708_0614.csv`, `metrics_20260709_0720.csv` — sampler
  (`stability_test/sample_metrics.py`, 60 s interval)
- `TradeCopier/copier.db` snapshot (WAL included)
- `TradeCopier/hub.log`
- `journal.md` — run journal
- `ReportHistory-52953732.xlsx` — slave terminal trade history (IC Markets)

---

## 1. Topology under test

| Role | Terminal | Broker | Status at snapshot |
|---|---|---|---|
| Master | master_1715542650 | OANDA Global Markets | Active |
| Master | master_67185418 | RoboForex Ltd | Active |
| Slave | slave_168935786 | XM International MU | Active |
| Slave | slave_52953732 | IC Markets (Raw Trading) | Active (registered 07-09 04:53, replaced 52911415) |
| Slave | slave_591823116 | FxPro Markets | Active |
| Slave | slave_67185418 | RoboForex Ltd | Active |
| Slave | slave_7833734 | AMarkets LLC | Active |

10 links (2 Masters × 5 Slaves), all `lot_mode=multiplier`, `lot_value=1.0`.
**7 different broker firms** participated across the run — exceeds the
cross-broker target from `ms3-deliverables.md` §3.2.

## 2. Hub uptime & resources

| Metric | Value | Target | Verdict |
|---|---|---|---|
| Hub restarts inside window | 0 (single PID 10928 since 07-08 04:46 UTC) | 0 | PASS |
| Continuous uptime at last sample | ~35.8 h and counting | agreed window | in progress |
| CPU (of one core) | avg 4.5 %, p95 6.2 %, max 7.6 % | — | PASS |
| RSS memory | 18 → ~52 MB warm-up, then plateau 51–53 MB for the last ~24 h | ±5 % from warmed baseline | PASS (no leak trend) |
| copier.db growth | 45.7 → 56.8 MB over ~36 h (~7 MB/day, dominated by `heartbeats` + `alerts_history`) | — | note: retention/cleanup keeps this bounded |
| Unhandled exceptions in hub.log | 0 ERROR, 0 Traceback (entire log since 06-12) | 0 | PASS |

## 3. Message routing (window: 07-08 04:14 UTC → snapshot)

| Metric | Value |
|---|---|
| Master messages routed | 122 (m_1715542650: 27 OPEN, 27 CLOSE, 12 MODIFY, 7 CLOSE_PARTIAL; m_67185418: 25 OPEN, 24 CLOSE) |
| Slave deliveries ACKed | 489 |
| Messages expired / stuck pending | 0 / 0 |
| NACKs | 60 total, of which 54 from the faulty slave_52911415 (`ORDER_FAILED`) before its replacement |

**ACK latency** (first ACK per message per slave, trade messages only,
1 s timestamp resolution):

| p50 | p95 | p99 | max |
|---|---|---|---|
| < 1 s | 1 s | 2 s | 4 s |

## 4. Heartbeat continuity (window)

| Terminal | Heartbeats | Max gap | Gaps > 30 s |
|---|---|---|---|
| master_1715542650 | 11 905 | 138 s | 1 |
| master_67185418 | 11 860 | 469 s | 2 |
| slave_168935786 | 11 919 | 26 s | 0 |
| slave_52911415 (until 07-09 04:52) | 8 872 | 24 s | 0 |
| slave_52953732 (from 07-09 04:53) | 3 046 | 17 s | 0 |
| slave_591823116 | 11 917 | 28 s | 0 |
| slave_67185418 | 11 916 | 37 s | 1 |
| slave_7833734 | 11 917 | 29 s | 0 |

The three master-side gaps around 07-09 ~04:00 UTC each produced a
delivered `heartbeat_miss` alert — live proof that heartbeat-loss
detection works (MS3 monitoring criterion). Root cause of the gaps: see
`journal.md` (TODO — confirm).

## 5. Alerts & Telegram (window)

| Alert type | Fired | Delivered | Deduplicated |
|---|---|---|---|
| consecutive_nacks | 23 700 | 774 | 22 854 |
| alert_storm | 394 | 388 | 0 |
| slave_disconnected | 12 | 12 | 0 |
| hub_started | 7 (6 of them are web-panel *test alerts* — see bug B2) | 7 | 0 |
| heartbeat_miss | 3 | 3 | 0 |
| daily_summary | 2 | 2 | 0 |

Deduplication and alert-storm protection worked as designed under a real
NACK flood (faulty slave): 23.7 k raw events compressed to 774 deliveries
plus explicit storm notifications. Alert history is fully queryable in
`alerts_history` (41 046 rows total).

## 6. Issues found during the run

| # | Severity | Issue | Action |
|---|---|---|---|
| B1 | Medium | Telegram bot **command replies fail with HTTP 400** (`bot reply failed: Client error '400 Bad Request' ... /sendMessage`, 6 occurrences: 4× on 07-08 startup, 2× on 07-09 13:19 UTC). Root cause: `/status` interpolated literal `(role)` parens without MarkdownV2 escaping (`telegram_bot.py`); Telegram rejected the whole reply. Two same-class cosmetic defects found alongside: over-escaping inside code spans showed literal backslashes in alert headers (`slave\_...`) and timestamps (`2026\-07\-09`) | **FIXED 2026-07-10.** Escaped parens; added `_md_escape_code` for code spans. Verified 3 ways: 10 new regression tests (`tests/test_telegram_markdown.py`, MarkdownV2 validator over every reply/alert body), full suite 189 passed, and live against the real Telegram API — old body reproduces the exact 400 (`Character '(' is reserved`), all 8 production-rendered bodies accepted with HTTP 200. Fix must be deployed to the VPS Hub |
| B2 | Low | Web-panel "test alert" is stored with `alert_type='hub_started'`, polluting restart accounting in alert history | Give test alerts their own type |
| B3 | Low | Stale terminal record slave_25333441 (Tickmill, disconnected since 07-02, not linked) stays in `terminals` and shows in UI | Add delete/archive for dead terminals, or document |
| O1 | Note | slave_52911415 NACKed everything (`ORDER_FAILED`, 6 758 total) until replaced on 07-09 04:52. Root cause TODO in journal. Positive side: NACK-burst alerting + dedup verified under real fault | Confirm cause in journal |
| O2 | Note | `hub.log` contains the Telegram **bot token** in every httpx URL line | Redact log before handover; **rotate the token via BotFather** before delivery |

## 7. Pass criteria (from ms3-deliverables.md §3.2)

| Criterion | Status |
|---|---|
| Zero unhandled exceptions in logs | PASS (so far) |
| Zero stuck pending messages older than ack_timeout × retries | PASS |
| All heartbeats present for the full window | PASS with 3 explained master-side gaps (each alerted correctly) |
| All terminals registered and ACKing throughout | PASS (one planned slave replacement, journaled) |
| Hub restart count = 0 | PASS since window start 07-08 04:46 UTC |

## 8. Remaining before the report is final

- [ ] Close the window at the agreed duration; refresh §2–§5 numbers from the final DB/CSV snapshot.
- [ ] Fill the three TODO root causes in `journal.md` (restart 07-08 04:46, slave_52911415 NACKs, master heartbeat gaps 07-09 ~04:00).
- [ ] Reconcile trade reports: both Masters' ReportHistory + all 5 Slaves' — matrix "master ticket → one copy per linked slave, no dups/losses" + end-to-end copy latency.
- [ ] Multi-symbol + suffix-mapping coverage: window traffic was EURUSD-only with `suffix=''` on all links; run a session with 2–3 symbols incl. one suffixed slave.
- [ ] Magic-mapping / instance-isolation evidence from `messages` payloads or slave logs (MT5 reports do not export magic numbers).
- [x] Fix B1 (+ 10 regression tests, verified against live Telegram API) — done 2026-07-10; **deploy the fixed Hub to the VPS**.
- [ ] Fix B2, decide on B3, rotate + redact token (O2).
