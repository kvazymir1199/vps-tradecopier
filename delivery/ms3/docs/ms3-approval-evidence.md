# Milestone 3 — Approval Evidence

**Format:** same as `docs/ms2-approval-evidence.md` — every client
criterion mapped to a named automated test, a section of the stability
report, or a reproducible procedure. Nothing is claimed without a
pointer to its proof.

**Pinned commit:** the commit that introduces this document and the
`delivery/ms3/` package. The acceptance zip is produced from that hash.

**Evidence sources referenced below:**

| Shorthand | Location |
|---|---|
| REPORT | `docs/ms3-stability-run.md` (final, v1.0) |
| JOURNAL | `journal.md` |
| RECON | `stability_test/reconcile_reports.py` + `delivery/ms3/artifacts/reconciliation-output.txt` |
| STRESS | `tests/test_ms3_stress.py` |
| PYTEST | `docs/ms3-pytest-output.txt` (canonical run, 189 passed) |
| PACKAGE | `delivery/ms3/` (artifacts: metrics CSVs, redacted hub.log, 6 broker reports) |
| VIDEO | MS3 functional demonstration videos (complementary, delivered separately) |

---

## 1. Test execution on target setup

| Criterion | Evidence |
|---|---|
| Full E2E on the VPS with 2 Master terminals | REPORT §1: 2 live Masters (OANDA `master_1715542650`, RoboForex `master_67185418`) routing concurrently for the whole window. STRESS `test_ms3_2_masters_concurrent_no_cross_talk` |
| At least 5 Slave terminals | REPORT §1: 5 live Slaves across 5 broker firms (XM, IC Markets, FxPro, RoboForex, AMarkets) — 7 broker firms total including masters. All ACKing throughout (REPORT §4) |
| Scalable to 10 | STRESS `test_ms3_10_slaves_pipe_connections_stable`: 10 simultaneous slave links, every one receives its mapping-correct command, per-slave magic transform verified (`15010305..15010314`), fan-out < 1 s |
| Multiple symbols | REPORT §7: master traded `EURUSD.sml` (OANDA naming), slaves executed `EURUSD` — live symbol resolution. Broader multi-symbol demo: VIDEO |
| Multiple MagicNumber instances | REPORT §7: two live setups in-window (magic 0 and magic 5), both copied. Unit coverage: `tests/test_magic.py`. Demo: VIDEO |

## 2. Functional test coverage

| Criterion | Evidence |
|---|---|
| OPEN buy and sell with SL and TP | REPORT §3: 26 OPENs routed and acked in-window. Broker-side proof: `ReportHistory-52953732.xlsx` shows buy 0.1 with SL/TP and sell 0.1 with SL 1.147/TP 1.139. VIDEO scenes 1–2 |
| MODIFY SL and TP updates | REPORT §3: 12 MODIFY acked. Broker-side proof: order 1798909313 placed SL 1.13/TP 1.15, position closed with SL 1.13467/TP 1.15433 — SL/TP changed after open. VIDEO scene 3 |
| CLOSE full close | REPORT §3: 24 CLOSE acked; RECON confirms every close mirrored. VIDEO scene 4 |
| CLOSE_PARTIAL partial close by volume | REPORT §3: 7 CLOSE_PARTIAL acked. Broker-side proof: position 1799653495 (sell 0.10) closed 0.05 + 0.02, remainder 0.03 left open — proportional partial close on a real broker. VIDEO scene 5 |
| Symbol suffix and mapping behavior | Live: `EURUSD.sml` → `EURUSD` (REPORT §7). Unit coverage: `tests/test_symbol.py` (explicit > suffix priority). Slave-side suffix demo: VIDEO scene 6 |
| Magic mapping — last two digits replaced | `tests/test_magic.py`; STRESS 10-slave test asserts the exact transformed magics; formula `slave_magic = master_magic − (master_magic % 100) + slave_setup_id`. VIDEO scene 7 |
| Instance isolation by MagicNumber | STRESS `test_ms3_2_masters_concurrent_no_cross_talk`: 2×20 concurrent messages, zero cross-boundary deliveries. RECON: only linked slaves ever received copies (116/116, link-chronology verified). VIDEO scene 8 |

## 3. Reliability and recovery

| Criterion | Evidence |
|---|---|
| Slave restart with open trades — no duplicates | STRESS `test_ms3_slave_restart_no_duplicates_via_idem_file` (on-disk idempotency file, same format as the EA's `copier_idem_<account>.csv`). Live: RECON found **0 duplicates** across 116 deliveries including a mid-run slave replacement (JOURNAL 07-09 04:52–05:02) |
| Master restart — resend window & idempotency | STRESS `test_ms3_master_restart_resume_from_continues_counter` (REGISTER → `resume_from`, counter never replays). MS2 video scene 2 demonstrated it live on MT5 |
| Pipe disconnect/reconnect — no data loss | STRESS `test_ms3_pipe_disconnect_reconnect_no_data_loss` (10-msg burst with pipe down mid-burst; retry loop redelivers; 10 executed, 0 dups). Live: slave_52911415 pipe drop at 07-09 04:52 — Hub uninterrupted, healthy slaves unaffected (REPORT §2, §4) |
| DB recovery — backup & restore | `tests/test_backup_restore.py`; procedures `scripts/backup_db.py` / `scripts/restore_db.py`; operational steps in README Phase 11. VIDEO scene 9 |

## 4. Monitoring and alert validation

| Criterion | Evidence |
|---|---|
| Heartbeat loss detection + alert | REPORT §4: 3 real heartbeat gaps (VPS maintenance) each produced a delivered `heartbeat_miss` alert — detected and alerted live, unstaged |
| Health checks trigger at thresholds | REPORT §5: NACK-burst threshold fired under a real fault (out-of-funds slave); queue/ACK-timeout checks covered by `tests/test_health.py` |
| Telegram delivery verified | REPORT §5: 1 185 alerts delivered in-window across 6 types. Delivery-failure resilience: `tests/test_alerts.py` (retry/backoff, hub never blocks) |
| Alert configuration | Per-type toggles in web panel + `config` table; exercised by `tests/test_api_telegram.py` |
| Alert history stored in DB and readable | `alerts_history` table, 41 046 rows at snapshot; filterable web page; queried throughout REPORT §5 |
| Operator command validation | `tests/test_telegram_bot.py` (auth, /status, /last_alerts, /mute variants). Reply formatting verified against the **live Telegram API** after fix B1 (see §5) |

## 5. Bug fixing and stabilization

| Item | Evidence |
|---|---|
| B1 — bot replies HTTP 400 (found during the run) | Root-caused (unescaped MarkdownV2 parens in `/status`), fixed, and verified three ways: 10 regression tests (`tests/test_telegram_markdown.py`), full suite 189 passed, live API check — old body reproduces the exact 400, all 8 production bodies accepted. REPORT §6 |
| Known low-priority issues | B2 (web test-alert typed as `hub_started`), B3 (no delete/archive for dead terminal records) — documented in REPORT §6 with agreed follow-up |
| Stable release candidate | PYTEST: 189 passed at the pinned commit; REPORT: 35 h 51 m continuous run, zero unhandled exceptions |

## 6. Final delivery package

| Item | Location |
|---|---|
| Compiled EX5 (Master + Slave) | `ea/Master/TradeCopierMaster.ex5`, `ea/Slave/TradeCopierSlave.ex5` |
| Full EA source | `ea/` (`.mq5` + `Include/*.mqh`) |
| Final DB schema | `hub/db/schema.sql` |
| Configuration | Stored in the SQLite `config` table (seeded on first run, edited via web panel) — reference: README "Configuration Reference" |
| Documentation | README (setup 12 phases, daily ops, troubleshooting), `docs/plans/*` (architecture), this document |
| Runbook / handover guide | README sections: Server Setup, Daily Operations, **Health-check checklist**, Operator Telegram commands, Troubleshooting |
| Run artifacts | PACKAGE: metrics CSVs, redacted hub.log, 6 broker trade reports, reconciliation output |

## 7. Acceptance criteria — status

| Acceptance criterion | Status |
|---|---|
| System passes the full test plan | 189 automated tests passed (PYTEST); functional matrix above fully mapped |
| Stable operation during an agreed test window on the VPS | 35 h 51 m artifact-backed continuous operation, 0 restarts, 0 unhandled exceptions (REPORT §2, §8) — exceeds the 24 h option; duration sign-off pending client confirmation |
| Copy and monitoring correct with ≥5 slaves, scalable to 10 | 5 live slaves reconciled 116/116 with 0 dups / 0 losses (RECON); 10-slave scalability proven by STRESS |
