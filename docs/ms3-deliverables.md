# Milestone 3 — Scope & Deliverables Proposal

**Status:** Proposal for client review
**Owner:** Denis Mironov
**Reference:** Architecture document `docs/plans/2026-02-26-trade-copier-architecture.md`,
section "Acceptance Criteria (Milestone 3)" (lines 425–431) and section 9
"Testing & Acceptance" (lines 391–413).

---

## 1. Purpose of this document

This document defines exactly what will be delivered as part of MS3, what
the acceptance criteria are, and the open decisions we need to confirm
before work starts. It mirrors the format we used for MS2 so that
approval evidence can be produced in the same style.

---

## 2. Official MS3 acceptance criteria (from the architecture document)

| # | Criterion | How it is verified in MS3 |
|---|---|---|
| 1 | 2 Master terminals + 5 Slave terminals running stably | Live MT5 run with 2 Master + 3 Slave across **5 different broker firms** (cross-broker certification) — see 3.2. The architecture's "5 Slaves" target is over-satisfied by the stress suite (8 Slaves, 3.1) |
| 2 | Scalability verified up to 8 Slaves | Automated stress test `test_ms3_8_slaves_pipe_connections_stable` — 8 emulated Slaves on the same Hub — see 3.1 |
| 3 | All E2E and stress tests pass | Full pytest suite + new `tests/test_ms3_stress.py` — see 3.1 |
| 4 | Stable operation during the agreed test window | 72-hour live MT5 run on the VPS — see 3.2 |
| 5 | Web panel stable; all CRUD operations verified | Polling + concurrent CRUD verification — see 3.3. New Telegram-config and alert-history pages also exercised — see section 4 |

> Note on criterion 2: the original architecture document mentions "up to
> 10 Slaves". For MS3 verification we propose **8** as a realistic upper
> bound that fits within a single VPS without requiring extra
> infrastructure. The architecture remains scalable beyond 8 — we simply
> do not certify load above that number as part of MS3.
>
> Note on criterion 1: the original document says "2 Master + 5 Slave
> terminals running stably". We intentionally split this verification
> into two complementary runs:
> - **Cross-broker live run** with 2 Master + 3 Slave on **5 different
>   broker firms** (certifies the system is broker-agnostic, not just
>   Pepperstone).
> - **Scalability stress** with 8 emulated Slaves (certifies the Hub
>   handles more than the original 5).
>
> The combination is strictly stronger than running 5 Slaves all on the
> same broker.

---

## 3. Deliverables

### 3.1 Automated stress / load test suite

A new test file `tests/test_ms3_stress.py` (analogous to MS2's
`tests/test_ms2_proof.py`), with 1:1 mapping to the stress targets in
section 9 of the architecture document.

| Test name | What it proves | Maps to |
|---|---|---|
| `test_ms3_5_slaves_concurrent_within_one_second` | All 5 Slaves receive and ACK within 1 s of an OPEN being routed | Crit. 1 |
| `test_ms3_burst_50_messages_in_1_second_no_drops` | Hub queues and delivers all 50; zero dropped, zero duplicated | Crit. 3 |
| `test_ms3_sustained_10_msgs_per_second_for_1_hour` | No memory leak (RSS ±5 % from baseline), DB query latency stable | Crit. 3, 4 |
| `test_ms3_8_slaves_pipe_connections_stable` | 8 simultaneous Slave pipe connections, all bidirectional, no starvation | Crit. 2 |
| `test_ms3_2_masters_concurrent_routing` | 2 Masters sending in parallel; messages routed to correct Slaves with no cross-talk | Crit. 1 |
| `test_ms3_slave_disconnect_does_not_block_others` | One Slave dropped mid-burst; remaining Slaves continue receiving without latency spikes | Crit. 1, 4 |

Each test runs against the real Hub process and emulated Slaves (no
mocking of the pipe transport). The 1-hour sustained test runs in a
separate CI target (`pytest -m slow`) so the regular suite stays fast.

### 3.2 Live MT5 stability run (the "agreed test window")

A continuous run on the production-equivalent VPS with **2 Master + 3
Slave terminals, each on a different broker firm — 5 different brokers
in total**. This combination certifies the system is broker-agnostic
under real-world conditions, not just Pepperstone.

**Proposed duration:** **72 hours** continuous, no restart.

**Recorded metrics (stored in `docs/ms3-stability-run.md`):**

- Hub uptime, restart count (target: 0)
- Total messages routed per broker
- ACK latency p50 / p95 / p99 per broker (so we can spot if one broker
  is systematically slower)
- Heartbeat continuity per terminal
- Memory (RSS) and CPU sampled every 60 s
- Database size growth and WAL checkpoint frequency
- Any alerts fired (via the Telegram notification channel — see
  section 4)

**Pass criteria:** zero unhandled exceptions in logs, zero stuck
`pending`-status messages older than `ack_timeout × ack_max_retries`,
all heartbeats present for the full window, **all 5 brokers' terminals
remain registered and ACKing throughout**.

If 72 h is too long for the client's timeline, we can compress to
**24 h** without changing the methodology — please confirm in section 5.

### 3.3 Web panel stability under load

Verification that the FastAPI + Next.js panel is stable during the
live run, with all 5 broker terminals visible.

- Polling load: 5 terminals × `GET /api/terminals` every 5 s.
- Concurrent CRUD: create / update / delete on `links` and `mappings`
  while polling is active.
- New Telegram-config page (section 4) exercised: change
  `bot_token`/`chat_id`, toggle `enabled`, see the alert delivery
  reflect the change without Hub restart.
- New Alerts-history page (section 4) exercised: filter by terminal,
  by alert type, by time range.
- **Pass:** no failed requests, no UI lag > 500 ms, no DB lock errors
  in logs.

**Evidence:** captured network log + DB log committed under
`docs/ms3-web-panel-run.md`.

### 3.4 MS3 evidence document

`docs/ms3-approval-evidence.md` — same format as
`docs/ms2-approval-evidence.md`:

- Point-by-point evidence for each of the 5 acceptance criteria.
- Each claim backed by a named automated test or a reproducible
  procedure.
- File:line references into the codebase for every implementation
  detail that's load-bearing.
- Canonical pytest output committed as `docs/ms3-pytest-output.txt`.

### 3.5 Documentation updates

- Update `docs/plans/2026-02-26-trade-copier-architecture.md` to
  reflect the *implemented* architecture (some items still describe
  the original pre-implementation hypothesis — see
  `docs/client-review-response.md`, point 9).
- Add an MS3 section to `README.md` summarising how to run the stress
  suite, the long stability run, and where the evidence lives.

---

## 4. Telegram — final design (notification channel only)

Telegram is included in MS3 strictly as a **one-way notification
channel from Hub to a human operator**, with operator-issued commands
allowed for read-only queries and temporary alert muting. Telegram is
**not** used as a transport layer for trade signals between Master and
Slave. That boundary is final for MS3.

### 4.1 Recipients

**Single chat.** All alerts go to one Telegram chat configured by the
operator. No per-severity or per-terminal chat split.

### 4.2 Alert types

The default alert set in MS3 is **all five** of the following. The
operator can disable any of them via the web panel or `config.json`,
and add new ones in subsequent milestones if needed.

| Alert type | Trigger |
|---|---|
| **ACK timeout** *(existing)* | A message exceeds `ack_max_retries` without an ACK |
| **NACK burst** *(existing)* | More than 5 consecutive NACKs from the same Slave |
| **Heartbeat failure** *(existing)* | Terminal silent for more than 30 s |
| **Pending queue buildup** *(existing)* | More than 50 messages with `status='pending'` |
| **Slave disconnected** *(new)* | Pipe drop detected, immediate alert (does not wait for the 30 s heartbeat timeout) |
| **Hub started / restarted** *(new)* | Hub process startup, so an operator sees a restart even if no one was watching |
| **Trade copied successfully** *(new, opt-in)* | One alert per successful copy. **Disabled by default** because it produces a high message volume; the operator enables it in the web panel if they want it |
| **Daily summary** *(new)* | Once per day at a fixed UTC time, posts a digest: messages routed, ACK rate, NACK count, top NACK reasons, alerts fired, uptime |
| **Alert storm protection triggered** *(new)* | When the deduplication suppresses more than N alerts within the 5-minute window, fires a single "alerts are being throttled" message so the operator knows the silence is intentional |

The client can override this default set at any time via the web
panel. Each alert type is a row in an `alerts_config` table with an
`enabled` boolean — it ships with these defaults but is fully editable.

### 4.3 Per-terminal tagging

Every Telegram message is tagged with the terminal name and broker so
the operator can filter visually. Format:

```
[Slave • IC Markets • acc 87654321]
NACK burst: 6 consecutive NACKs in last 60 s
Last reason: SYMBOL_NOT_FOUND (XAUUSD.s)
```

### 4.4 Operator interaction (bidirectional bot)

The bot accepts the following commands from the configured chat
(commands from any other chat are ignored to prevent abuse):

| Command | Effect |
|---|---|
| `/status` | Returns Hub uptime, count of pending messages, list of online terminals, last 5 alerts |
| `/last_alerts [N]` | Returns the last N alerts (default 10), most recent first |
| `/mute [duration]` | Suppresses **all** outbound alerts for the given duration (e.g. `/mute 1h`, `/mute 30m`). `/mute off` re-enables. Default 1 h if no duration given |
| `/help` | Lists all commands |

**Implementation:** Telegram **long-polling** (`getUpdates` API), so no
inbound HTTPS / webhook is required on the VPS. A small async task in
the Hub polls every 2 s.

**Authentication:** the bot only accepts commands from the
`chat_id`(s) listed in the config. Anyone else is silently ignored.

### 4.5 Configuration — both web panel **and** `config.json`

The operator can configure Telegram in either place; both stay in sync:

- **`config.json`** is the bootstrap source. On Hub startup, if the
  `telegram_settings` table in SQLite is empty, values are seeded
  from `config.json`.
- **Web panel** (`/settings/telegram` page) writes directly to the
  SQLite `telegram_settings` table. Changes take effect within the
  next health-check tick (no Hub restart required).
- A "Sync to config.json" button in the web panel persists the
  current DB settings back to `config.json` so manual edits and UI
  edits do not drift.

Editable fields: `enabled`, `bot_token`, `chat_id`, `daily_summary_time`,
plus the per-alert-type `enabled` toggles (4.2).

### 4.6 Alert history in the web panel

Every alert (delivered or not, deduplicated or not) is persisted to a
new SQLite table:

```sql
CREATE TABLE alerts (
  id            INTEGER PRIMARY KEY,
  fired_at      INTEGER NOT NULL,    -- ms epoch
  alert_type    TEXT NOT NULL,
  terminal_id   TEXT,                -- nullable for global alerts
  message       TEXT NOT NULL,
  delivered     INTEGER NOT NULL,    -- 0/1
  retry_count   INTEGER NOT NULL,
  deduplicated  INTEGER NOT NULL     -- 0/1
);
```

The web panel adds an **Alerts** page with:

- Table view of the last 1 000 alerts.
- Filters: alert type, terminal, time range, delivered yes/no.
- One-click "test alert" button that fires a synthetic alert through
  the full pipeline (verifies bot token + chat_id without waiting for
  a real failure).

Retention: 90 days, then auto-purged by a daily cleanup task in the
Hub.

### 4.7 Markdown formatting

All alerts are sent in **MarkdownV2** format with a consistent
template:

```
*[ALERT_TYPE]*  `terminal_name`
_broker: <broker_name>_

<message body — multi-line, monospace for log excerpts>

`fired at: <UTC timestamp>`
```

This makes alerts visually distinct in the chat (bold severity, mono
terminal IDs, italics for metadata).

### 4.8 Delivery retries

If the Telegram API returns a non-200 response, the alert is retried
**up to 3 times** with exponential backoff (10 s → 30 s → 90 s).
After 3 failures the alert is marked `delivered=0` in the alerts
table, but the Hub continues operating normally — Telegram delivery
failure never blocks trade routing.

### 4.9 What MS3 verifies for Telegram

- All 9 alert types fire under simulated conditions in
  `tests/test_ms3_stress.py`.
- Deduplication is honored under burst load.
- Operator commands (`/status`, `/mute`, etc.) work end-to-end via
  long-polling.
- Web panel config changes propagate to the Hub within one
  health-check tick.
- A simulated Telegram API failure does not crash the Hub or block
  trade routing; the alert lands in the alerts table with
  `delivered=0` and `retry_count=3`.
- A live test during the 72 h stability run confirms zero alert spam
  during normal operation and correct alert delivery during induced
  failures.

---

## 5. Decisions still needed from the client

Telegram design is fully specified above and does not require further
decisions. The following two items still need explicit confirmation
before MS3 starts:

### Decision 1 — Stability test window duration

**72 h** (recommended) or **24 h**?

### Decision 2 — Brokers and demo accounts for the live MT5 run

The MS3 live run requires **5 different broker firms**, with **2 of
them hosting Master accounts** and **3 hosting Slave accounts** (one
terminal per broker). Please provide:

For each of the 5 brokers:

- Broker name
- Account number
- Password
- Server name
- Role: Master or Slave

We need this list before MS3 starts because:

- Each broker requires its own MT5 client installation on the VPS
  (~1 GB disk per broker).
- Symbol naming conventions differ per broker (e.g. `EURUSD` vs
  `EURUSD.s` vs `EURUSD.r`); the symbol-mapping table must be
  pre-configured per Slave before the stability run begins.
- Some brokers reject demo logins from VPS IP ranges; verifying this
  early avoids surprises on day 3 of a 3-day stability run.

If the client has no preference, the default is "all 5 on Pepperstone
demo accounts that I will provision myself" — but that does not satisfy
the cross-broker certification value of MS3, so an explicit list of
real broker firms is recommended.

---

## 6. Estimated timeline

Assuming **72 h** test window and **5 client-provided brokers**:

| Phase | Duration |
|---|---|
| Stress test suite (3.1) | 3 days |
| Telegram redesign — web-panel config, bot commands, history view, retries, MarkdownV2 (section 4) | 4 days |
| Multi-broker VPS setup (5 MT5 clients, symbol mapping per broker) | 2 days |
| Web panel verification (3.3) | 1 day |
| Long stability run (3.2, 72 h wall clock) | 3 days (mostly waiting) |
| Evidence doc (3.4) | 0.5 day |
| Documentation updates (3.5) | 0.5 day |
| Buffer for issues found during the run | 2 days |
| **Total** | **~16 calendar days** |

If the client switches to 24 h test window, total drops by ~2 days.
If the client switches all 5 brokers to Pepperstone (defeating
cross-broker value but easier), VPS setup drops by 1.5 days.

---

## 7. Acceptance evidence

On MS3 completion the following will be present in the repository,
all pinned to the same final commit (same approach as MS2):

- `tests/test_ms3_stress.py` — automated stress tests, all passing.
- `docs/ms3-approval-evidence.md` — point-by-point evidence per
  criterion.
- `docs/ms3-pytest-output.txt` — canonical pytest output from the
  final commit.
- `docs/ms3-stability-run.md` — full metrics from the 72 h run
  (uptime, latency percentiles per broker, memory profile, alert
  log).
- `docs/ms3-web-panel-run.md` — log + network capture from the web
  panel verification run.
- A short MS3 section in `README.md` describing how to reproduce
  everything from a clean clone.

The acceptance review will be a single git commit hash + a fresh
GitHub zip from that hash, exactly as MS2 was finalised in commit
`965ee0f`.
