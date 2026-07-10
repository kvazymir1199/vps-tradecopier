# MS3 Stability Run — Report

**Status:** FINAL (v1.0, 2026-07-10). Certified figures are bounded by the
collected artifacts: copier.db + hub.log snapshot at 2026-07-09 13:20 UTC,
sampler CSVs up to 2026-07-09 16:37 UTC.

**Official window:** 2026-07-08 04:46 UTC (manual Hub restart, journaled)
→ 2026-07-09 16:37 UTC (last sampler row with unchanged Hub PID) —
**35 h 51 m of continuous, artifact-backed Hub uptime**. The terminal
session ran longer overall; figures beyond the last artifact timestamp are
not certified by this report.

**Sources:**
- `metrics_20260708_0614.csv`, `metrics_20260709_0720.csv` — sampler
  (`stability_test/sample_metrics.py`, 60 s interval)
- `TradeCopier/copier.db` snapshot (WAL included)
- `TradeCopier/hub.log`
- `journal.md` — run journal (all root causes confirmed by operator)
- `TradeCopier/ReportHistory-*.xlsx` — trade history exported from all 6
  terminals (2 masters + 5 slaves; RoboForex 67185418 hosts a master and a
  slave on the same account, so one file covers both roles)

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
| Continuous uptime (artifact-backed) | 35 h 51 m (07-08 04:46 → 07-09 16:37 UTC, PID 10928 unchanged) | agreed window | PASS for a 24 h window; see §8 note on duration |
| CPU (of one core) | avg 4.5 %, p95 6.2 %, max 7.6 % | — | PASS |
| RSS memory | 18 → ~52 MB warm-up, then plateau 51–53 MB for the last ~24 h | ±5 % from warmed baseline | PASS (no leak trend) |
| copier.db growth | 45.7 → 56.8 MB over ~36 h (~7 MB/day, dominated by `heartbeats` + `alerts_history`) | — | note: retention/cleanup keeps this bounded |
| Unhandled exceptions in hub.log | 0 ERROR, 0 Traceback (entire log since 06-12) | 0 | PASS |

## 3. Message routing (official window: 07-08 04:46 UTC → snapshot)

| Metric | Value |
|---|---|
| Master messages routed | 69, all acked (m_1715542650: 19 OPEN, 18 CLOSE, 12 MODIFY, 7 CLOSE_PARTIAL; m_67185418: 7 OPEN, 6 CLOSE) |
| Slave deliveries ACKed | 313 |
| Messages expired / stuck pending | 0 / 0 |
| NACKs | 7, all from the out-of-funds slave_52911415 (`ORDER_FAILED`) before its replacement |

**ACK latency** (first ACK per message per slave, trade messages only,
1 s timestamp resolution):

| p50 | p95 | p99 | max |
|---|---|---|---|
| < 1 s | 1 s | 2 s | 4 s |

## 4. Heartbeat continuity (from sampler start 07-08 04:14 UTC)

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
detection works (MS3 monitoring criterion). Root cause confirmed by the
operator: nightly VPS maintenance (`journal.md`).

## 5. Alerts & Telegram (official window: 07-08 04:46 UTC → snapshot)

| Alert type | Fired | Delivered | Deduplicated |
|---|---|---|---|
| consecutive_nacks | 23 318 | 774 | 22 484 |
| alert_storm | 388 | 388 | 0 |
| slave_disconnected | 12 | 12 | 0 |
| hub_started | 6 (5 of them are web-panel *test alerts* — see bug B2) | 6 | 0 |
| heartbeat_miss | 3 | 3 | 0 |
| daily_summary | 2 | 2 | 0 |

Deduplication and alert-storm protection worked as designed under a real
NACK flood (out-of-funds slave): 23.3 k raw events compressed to 774
deliveries plus explicit storm notifications. Alert history is fully queryable in
`alerts_history` (41 046 rows total).

## 6. Issues found during the run

| # | Severity | Issue | Action |
|---|---|---|---|
| B1 | Medium | Telegram bot **command replies fail with HTTP 400** (`bot reply failed: Client error '400 Bad Request' ... /sendMessage`, 6 occurrences: 4× on 07-08 startup, 2× on 07-09 13:19 UTC). Root cause: `/status` interpolated literal `(role)` parens without MarkdownV2 escaping (`telegram_bot.py`); Telegram rejected the whole reply. Two same-class cosmetic defects found alongside: over-escaping inside code spans showed literal backslashes in alert headers (`slave\_...`) and timestamps (`2026\-07\-09`) | **FIXED 2026-07-10.** Escaped parens; added `_md_escape_code` for code spans. Verified 3 ways: 10 new regression tests (`tests/test_telegram_markdown.py`, MarkdownV2 validator over every reply/alert body), full suite 189 passed, and live against the real Telegram API — old body reproduces the exact 400 (`Character '(' is reserved`), all 8 production-rendered bodies accepted with HTTP 200. Fix must be deployed to the VPS Hub |
| B2 | Low | Web-panel "test alert" is stored with `alert_type='hub_started'`, polluting restart accounting in alert history | Give test alerts their own type |
| B3 | Low | Stale terminal record slave_25333441 (Tickmill, disconnected since 07-02, not linked) stays in `terminals` and shows in UI | Add delete/archive for dead terminals, or document |
| O1 | Note | slave_52911415 NACKed everything (`ORDER_FAILED`, 6 758 total) until replaced on 07-09 04:52. **Root cause confirmed: the account ran out of funds** — the broker rejected every order; the Slave EA correctly NACKed instead of crashing. Positive side: NACK-burst alerting + dedup verified under a real, unplanned fault | Resolved — journaled; slave replaced with funded account 52953732 |
| O2 | Note | `hub.log` contains the Telegram **bot token** in every httpx URL line | Redact log before handover; **rotate the token via BotFather** before delivery |

## 7. Trade report reconciliation (DB × 6 terminal reports)

Produced by `stability_test/reconcile_reports.py` (committed; rerunnable
from a clean clone against the artifacts). Copies are identified by the
EA order comment `Copy:<master_id>:<ticket>` in each terminal's own
broker-side report, cross-checked against `messages`/`message_acks`.

**26 master OPENs in the window** (magic 0: 19, magic 5: 7; symbols
`EURUSD.sml` on the OANDA master mapped to `EURUSD` on all slaves —
live proof of symbol-mapping in the window):

| Slave | Expected copies | Found exactly 1 | Duplicates | Missing |
|---|---|---|---|---|
| slave_168935786 (XM) | 26 | 26 | 0 | 0 |
| slave_52953732 (IC Markets) | 19 | 19 | 0 | 0 |
| slave_591823116 (FxPro) | 26 | 26 | 0 | 0 |
| slave_67185418 (RoboForex) | 19 | 19 | 0 | 0 |
| slave_7833734 (AMarkets) | 26 | 26 | 0 | 0 |
| **Total** | **116** | **116** | **0** | **0** |

Excluded with documented cause (not losses):
- 7 deliveries "not-linked-yet" — trades at 04:53–04:59 UTC on 07-09,
  before the links to the replacement slave were created at 05:01–05:02
  (verified against `master_slave_links.created_at`). No link → no copy
  is correct behaviour.
- 7 deliveries to the dead slave_52911415 after its 04:52 disconnect —
  commands dropped with a WARN in hub.log, `slave_disconnected` alert
  delivered.

**VERDICT: RECONCILED — exactly one copy per linked slave, zero
duplicates, zero silent losses.** End-to-end copy latency is certified
from the DB (§3: p95 = 1 s); broker report clocks run in per-broker
server time and are not used for latency.

## 8. Pass criteria (from ms3-deliverables.md §3.2)

| Criterion | Status |
|---|---|
| Zero unhandled exceptions in logs | PASS |
| Zero stuck pending messages older than ack_timeout × retries | PASS |
| All heartbeats present for the full window | PASS with 3 explained master-side gaps (VPS maintenance; each alerted correctly) |
| All terminals registered and ACKing throughout | PASS (one journaled slave replacement after the account ran out of funds) |
| Hub restart count = 0 | PASS (07-08 04:46 → 07-09 16:37 UTC, PID unchanged) |
| One copy per linked slave, no dups/losses | PASS (§7 reconciliation) |

**Window duration note:** the artifacts certify 35 h 51 m of continuous
operation — comfortably above the 24 h option of ms3-deliverables.md
Decision 1, below the 72 h option. The client must confirm which duration
applies; if 72 h is required, the same methodology applies to a longer
capture without any code changes.

## 9. Follow-ups outside this report

- Multi-symbol breadth + slave-side `symbol_suffix` and magic-remap
  demonstration → covered by the MS3 functional test evidence (video
  plan), not by this stability report. Symbol mapping itself is already
  proven in-window (§7: `EURUSD.sml` → `EURUSD`).
- [x] Fix B1 (+ 10 regression tests, verified against live Telegram API) —
  done 2026-07-10; **deploy the fixed Hub to the VPS**.
- [ ] Fix B2, decide on B3.
- [ ] Rotate the bot token via BotFather and redact `hub.log` before
  handing artifacts to the client (O2).
