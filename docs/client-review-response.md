# Response to Client Code Review — April 2026

## 1. Master event source: OnTradeTransaction vs OnTrade

**Decision: OnTrade (intentional)**

The Master EA uses `OnTrade` with timer-based polling instead of `OnTradeTransaction`. This was an intentional design decision:
- `OnTrade` provides a snapshot-based approach (checks all positions on each tick) which is simpler and more reliable for copy trading
- `OnTradeTransaction` is event-driven and can miss events if the EA is loaded after trades are already open
- `OnTrade` naturally handles reconnection scenarios — it re-detects existing positions

**Action:** Update documentation to reflect `OnTrade` as the final approach.

## 2. Persistent state file (copier_state.json)

**Decision: SQLite replaces JSON state file**

The JSON state file described in the original documents has been fully replaced by SQLite (WAL mode):
- `messages` table stores all processed messages with `msg_id`
- `acks` table stores acknowledgments
- `terminals` table tracks registered terminals
- SQLite provides ACID guarantees, WAL mode for concurrent reads, and a single source of truth

**Action:** Remove `copier_state.json` references from documentation.

## 3. Duplicate handling / idempotency

**Decision: ACK (not NACK) — bug fixed**

The documentation is correct: duplicates should receive ACK to signal "already processed, no further action needed." The previous NACK behavior was a bug that could cause the Hub to unnecessarily retry messages.

**Fix applied:** `ea/Slave/TradeCopierSlave.mq5` line 195 — changed `SendNack(cmd.msgId, "DUPLICATE_MSG")` to `SendAck(cmd.msgId, 0)`.

## 4. map_key-based mapping

**Decision: MagicNumber-based lookup (intentional simplification)**

The current implementation uses MagicNumber-based position lookup (`FindPositionByMagic(cmd.magic)`) instead of the documented `map_key = master_id | symbol_master | instance_id | master_position_uid` composite key.

Rationale:
- MagicNumber is already unique per strategy/symbol combination (`slave_magic = master_magic - (master_magic % 100) + slave_setup_id`)
- Simpler implementation with fewer failure points
- Works reliably for the current use case (Pepperstone, single broker)

**Action:** Update documentation to reflect MagicNumber-based lookup.

## 5. Message format alignment

**Decision: Current lean protocol is sufficient**

The implemented protocol uses a minimal set of fields:
- `msg_id`, `master_id`, `type`, `ts_ms`, `payload`
- Payload contains standard trade fields: `ticket`, `symbol`, `direction`, `volume`, `price`, `sl`, `tp`, `magic`, `comment`

Fields from the original spec that are NOT implemented (and not needed):
- `instance_id` — not needed, one EA per terminal
- `symbol_m` / `symbol_s` — replaced by `symbol` + server-side mapping
- `map_key` — replaced by MagicNumber
- `slave_uid` — replaced by `slave_ticket` in ACK
- `retcode` / `error_msg` — captured in NACK `reason` field

**Action:** Update specification to match actual protocol.

## 6. Multi-instance validation rules

**Decision: Partially implemented**

Currently implemented:
- Magic number mapping table (`magic_mappings`) — configurable per link
- Symbol mapping table (`symbol_mappings`) — configurable per link

Not yet implemented (optional safeguards for future):
- Direction validation derived from MagicNumber
- Whitelist of allowed MagicNumbers per slave

**Recommendation:** Magic mapping is mandatory for release. Direction validation is an optional safeguard for Phase 2.

## 7. Retry / resend behavior

**Decision: Simplified for MVP**

Current implementation:
- `ResendWindow` (N=200) in-memory deduplication per master_id
- ACK timeout monitoring in HealthChecker (alerts via Telegram)
- Heartbeat-based health checks

Not implemented (Phase 2):
- Automatic resend of unacknowledged messages
- Persistent resend queue surviving Hub restart

**Recommendation:** Current approach is sufficient for MVP. Full retry/resend is planned for Phase 2.

## 8. Pipe naming / transport convention

**Decision: Per-terminal pipes (intentional)**

Current naming convention:
```
Master → Hub:  \\.\pipe\copier_master_{account_number}
Hub → Slave:   \\.\pipe\copier_slave_{account_number}_cmd
Slave → Hub:   \\.\pipe\copier_slave_{account_number}_ack
```

The single-pipe example `TradeCopier_MT5_A` in the original docs was conceptual. Per-terminal pipes allow multiple masters and slaves to operate independently.

**Action:** Update documentation to reflect per-terminal pipe naming.

## 9. Authority of the two project documents

**Decision: Conceptual guidance, not binding specification**

The two documents (`trade-copier-architecture.md` and `trade-copier-implementation.md`) should be treated as **conceptual guidance**. The implementation intentionally deviates in several areas for simplicity and reliability:

| Area | Document | Implementation | Reason |
|------|----------|----------------|--------|
| Event source | OnTradeTransaction | OnTrade | More reliable for copy trading |
| State storage | JSON file | SQLite WAL | ACID, single source of truth |
| Position lookup | map_key composite | MagicNumber | Simpler, fewer failure points |
| Protocol fields | 12+ fields | 8 core fields | YAGNI — lean protocol |
| Pipe naming | Single pipe | Per-terminal | Supports multiple terminals |

**Action:** Update documentation to match the actual implemented architecture and mark it as the authoritative specification.

---

## Bugs Fixed in This Release

| # | Bug | Fix |
|---|-----|-----|
| 1 | `resolve_symbol()` ignored `symbol_suffix` — no suffix fallback | Added `symbol_suffix` parameter; suffix applied when no explicit mapping exists |
| 2 | `CLOSE_PARTIAL` used wrong volume formula for fixed mode | Now uses `compute_partial_close_volume()` with proportional calculation |
| 3 | Slave EA sent NACK for duplicate messages | Changed to ACK (idempotent — "already processed") |
