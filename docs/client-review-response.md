# Implementation Review — Response to Client Questions (April 2026)

This document addresses each point raised during the client code review. For every question, I explain why the implementation differs from the original spec and what problem that choice solves.

---

## 1. Master Event Source: `OnTradeTransaction` vs `OnTrade`

> The documents describe `OnTradeTransaction` as the primary event source, but the implementation uses `OnTrade` with timer-based support. Was this intentional?

Yes, this was a deliberate change.

The original plan was to use `OnTradeTransaction` because it fires once per individual event — an order filled, a deal added, a position modified. In theory, that gives you surgical precision: you know exactly what happened and when.

In practice, it creates two serious problems for a copy-trading system.

First, `OnTradeTransaction` doesn't fire for things that already happened before the EA was loaded. If you attach the Master EA to a chart that already has three open positions, it simply doesn't know about them. With `OnTrade`, the very first call triggers a full position scan, and those three positions are immediately picked up and tracked. This matters a lot in real operation — you restart a terminal, the VPS reboots, MetaEditor forces an EA reload — and you need the system to just work without manual intervention.

Second, partial closes are surprisingly difficult to handle with `OnTradeTransaction`. MT5 splits them across multiple events (the original position is modified, a new deal is created, sometimes a new position appears), and reconstructing "this was a partial close of 0.03 lots" from those fragments is error-prone. With the snapshot approach, it's trivial: the previous volume was 0.10, the current volume is 0.07, so 0.03 was closed. Done.

The implementation uses `OnTrade()` as the reactive trigger and `OnTimer()` at 100 ms for pipe I/O, heartbeats, and reconnection logic. The actual trade detection happens in `ScanPositions()` — it builds a snapshot of all current positions, diffs it against the previous snapshot, and emits OPEN / MODIFY / CLOSE / CLOSE_PARTIAL messages based on what changed.

It's a simpler model, and simpler means fewer edge cases in production.

---

## 2. Persistent State File (`copier_state.json`)

> The documents describe a JSON state file with `last_msg_id`, position mappings, and atomic writes. The implementation uses SQLite. Should the JSON file still be part of the solution?

No. SQLite replaced it entirely, and it was the right call.

The original idea was a JSON file that gets written atomically (write to temp file, then rename). That pattern works, but it has real limitations once you move past a single process reading a single file.

The problem is that this system has two processes that need to read state: the Hub service and the FastAPI web backend. With a JSON file, you'd need file locking, or you'd risk one process reading a half-written file. You'd also need to manually implement crash recovery — if the process dies between writing the temp file and renaming it, you're left with stale state.

SQLite in WAL mode solves all of this out of the box. The Hub writes, FastAPI reads, and they never block each other. If the process crashes mid-transaction, SQLite rolls it back automatically. And because everything is in one database, the web panel can query message history, ACK status, terminal health — all with standard SQL instead of parsing JSON files.

The `messages` table stores every message with its `msg_id` and status (pending → sent → acked/nacked). The `message_acks` table records every slave response. The `trade_mappings` table tracks which master position maps to which slave position. All of this would have been extremely awkward to maintain in a flat JSON file.

One database, one writer (`DatabaseManager`), ACID guarantees. It's strictly better than the JSON approach for this use case.

---

## 3. Duplicate Handling / Idempotency

> The documents say duplicates should receive ACK. The implementation previously returned NACK. Which is correct?

ACK is correct. The NACK behavior was a bug, and it's been fixed.

Here's the reasoning. When a Slave receives a message it has already processed, the right response is "yes, I've handled this" — which is an ACK. If you send a NACK instead, the Hub interprets it as "something went wrong, maybe I should retry." That creates a pointless loop: Hub sends message, Slave says NACK because it's a duplicate, Hub retries, Slave says NACK again. Nobody wins.

The fix was straightforward: when the Slave detects a duplicate (the `msg_id` is less than or equal to the last processed ID for that master), it sends an ACK with `slave_ticket=0`. The zero ticket tells the Hub "I didn't open a new position, but the message is handled." The Hub records it, moves on, everyone's happy.

The system actually has two layers of duplicate protection. The Hub's `ResendWindow` (last 200 message IDs per master) catches duplicates before they even reach the Slave. The Slave's own idempotency check is a second safety net in case a message slips through — for example, after a Hub restart when the in-memory window is empty.

---

## 4. `map_key`-Based Mapping

> The documents define `map_key = master_id | symbol_master | instance_id | master_position_uid` for position resolution. The implementation uses MagicNumber. Should we implement strict `map_key` mapping?

No. MagicNumber is simpler and works perfectly for this setup.

The `map_key` idea came from thinking about a very general system — multiple brokers, multiple instances of the same EA on one terminal, positions that need to be distinguished by a combination of four fields. That's a lot of machinery, and for our actual deployment (Pepperstone, one EA per terminal, magic numbers that are already unique per strategy), it's unnecessary machinery.

Here's what happens in practice. Every position opened by the Master has a magic number like `15010301` — that encodes the pair, the direction block, and the setup ID. When the Hub forwards a CLOSE command to the Slave, it transforms the magic number using a simple formula: strip the last two digits and replace them with the slave's setup ID. So `15010301` becomes `15010305`. The Slave then scans its open positions, finds the one with magic `15010305`, and closes it.

This works because magic numbers are already designed to be unique identifiers. There's no scenario in the current architecture where two different positions on the same terminal would share the same magic number. The `map_key` approach would give us the same result with more complexity — string concatenation, composite key lookups, potential hash collisions.

The `trade_mappings` table still records the full relationship (master ticket, slave ticket, both magic numbers, symbol, volumes) for auditing and the web panel. But the operational lookup — "which position should I close?" — uses magic number directly. Simple, fast, reliable.

If the system ever expands to multiple brokers or multiple EAs per terminal, we can revisit this. But adding complexity for a scenario that doesn't exist yet would be premature.

---

## 5. Message Format Alignment

> The documents define fields like `instance_id`, `symbol_m`, `symbol_s`, `map_key`, `retcode`, etc. The implementation is leaner. Should it match the spec?

No. The lean protocol is intentional.

The original spec had 12+ fields per message because it was designed for maximum generality. But several of those fields turn out to be redundant or unnecessary when you look at how the system actually works:

- **`instance_id`** — removed because we run one EA per terminal. The `terminal_id` (derived from the account number) is already unique.

- **`symbol_m` / `symbol_s`** — removed because symbol mapping is the Hub's job, not the message's job. The Master sends `symbol: "EURUSD"`, the Hub looks up the mapping and transforms it to `"EURUSD.s"` before forwarding. The Slave doesn't need to know what the master symbol was.

- **`map_key`** — removed in favor of `magic`, as explained in point 4.

- **`retcode` / `error_msg`** — removed because the NACK `reason` field covers this. Instead of sending a numeric return code that the Hub would need to interpret, the Slave sends a human-readable reason like `SYMBOL_NOT_FOUND` or `ORDER_FAILED`. This is easier to log, easier to alert on, and easier to debug.

- **`slave_uid`** — replaced by `slave_ticket` in the ACK. The MT5 position ticket is the natural identifier.

Every field you add to a protocol has a cost. It has to be serialized on one end, parsed on the other, and every parser is a potential source of bugs — especially in MQL5, where JSON handling is manual string manipulation. Keeping the protocol lean means fewer places for things to go wrong, smaller messages over the pipe, and faster development when adding new message types.

The current protocol carries exactly the information needed to execute the trade and nothing more. That's a feature, not a limitation.

---

## 6. Multi-Instance Validation Rules

> Which validation rules are mandatory for release, and which are optional?

The system currently validates everything that could cause a real problem, and defers the "nice to have" checks to Phase 2.

**What's implemented and mandatory:**

The magic number mapping table controls which master setups are copied to which slave setups. This is the core routing logic — without it, trades go to the wrong accounts. That's in.

Symbol validation happens on the Slave side: if the resolved symbol doesn't exist in the terminal's MarketWatch, the Slave sends a NACK with `SYMBOL_NOT_FOUND`. If trading is disabled for that symbol, it's `TRADE_DISABLED`. These prevent the Slave from attempting trades that would fail anyway.

Volume normalization ensures the lot size conforms to the symbol's constraints — rounded down to the volume step, rejected if below the minimum, capped at the maximum. This prevents order rejection from the broker.

**What's deferred to Phase 2:**

Direction validation from the magic number (extracting the `direction_block` and checking that a BUY signal actually corresponds to a BUY-allowed magic) is a useful safety check, but it only matters if someone misconfigures the magic mapping table. For the current setup with a single broker, the risk is low.

A whitelist of allowed magic numbers per slave would let you say "this slave should only copy setups 01 and 03, ignore everything else." That's a nice administrative control, but it's not critical for launch — the magic mapping table already implicitly controls what gets copied by only containing entries for the setups you want.

Both of these are straightforward to add later without changing the architecture.

---

## 7. Retry / Resend Behavior

> The documents describe automatic retries and a persistent resend queue. The implementation only has monitoring and alerts. Is more work planned?

Yes, full retry is planned for Phase 2. But the current approach is intentionally conservative, and here's why.

Automatic retry in a trading system is dangerous if you get it wrong. Imagine this: the Hub sends an OPEN command to the Slave, the Slave opens the position, but the ACK gets lost because the pipe disconnects. The Hub doesn't see the ACK, waits 5 seconds, and retries. Now the Slave opens a second position for the same trade. You've just doubled the client's exposure.

To do automatic retry safely, you need bulletproof idempotency — the Slave must be able to recognize "I already opened this exact position" and respond with an ACK instead of opening another one. The current idempotency check (based on `msg_id`) handles this for identical messages, but there are edge cases around Hub restarts where the `msg_id` sequence could reset.

So for MVP, the approach is: monitor everything, alert immediately, let a human decide. The system watches for ACK timeouts (15 seconds), consecutive NACKs (more than 5), heartbeat failures (30 seconds), and queue buildup (more than 50 pending messages). All of these trigger Telegram alerts with deduplication so you don't get spammed.

The pipe layer handles reconnection automatically — both the Master and Slave EAs retry the pipe connection every 100 ms and re-register when it comes back. So transient pipe failures recover on their own. What doesn't auto-recover is trade execution failures, and those are exactly the cases where you want a human looking at it.

Phase 2 will add controlled retry with proper safeguards: persistent message queue, configurable retry count, and stronger idempotency guarantees that survive Hub restarts.

---

## 8. Pipe Naming / Transport Convention

> The documents use a single pipe example like `TradeCopier_MT5_A`. The implementation uses per-terminal pipes. Which is correct?

Per-terminal pipes. The single-pipe example in the original docs was just a simplified illustration.

The actual naming convention uses the account number to create unique pipe names:

```
Master → Hub:   \\.\pipe\copier_master_12345678
Hub → Slave:    \\.\pipe\copier_slave_87654321_cmd
Slave → Hub:    \\.\pipe\copier_slave_87654321_ack
```

This is necessary because the system supports 2 Master terminals and up to 10 Slaves running simultaneously. If they all shared a single pipe, you'd need multiplexing logic to figure out which terminal sent which message. With per-terminal pipes, each connection is isolated — the Hub knows exactly who it's talking to based on which pipe the data arrived on.

The Slave uses two separate pipes (one for receiving commands, one for sending ACKs) because Windows named pipes work best as unidirectional channels. Trying to do bidirectional communication on a single pipe introduces timing issues and buffering complexity that simply isn't worth it.

The Hub creates pipes dynamically based on which terminals are registered in the database. When a new terminal registers (via the web panel or by self-registering on first connection), the Hub's discovery loop picks it up and opens the corresponding pipe. No hardcoded pipe names, no configuration files to edit.

---

## 9. Authority of the Two Project Documents

> Should the architecture and implementation documents be treated as binding specifications or conceptual guidance?

Conceptual guidance. The implementation is the source of truth.

The original documents were written before a single line of code existed. They made reasonable assumptions about the best approach, but several of those assumptions turned out to be wrong — or at least suboptimal — once we started building.

That's normal. A spec written before implementation is a hypothesis about what will work. The implementation is the experiment that tests it. In our case, the experiment showed that:

- `OnTrade` handles edge cases (EA restart, positions already open) better than `OnTradeTransaction`
- SQLite is strictly better than a JSON state file when multiple processes need access
- MagicNumber already provides unique identification without a composite `map_key`
- Half the protocol fields were carrying information that nobody consumed
- Automatic retry without rock-solid idempotency is more dangerous than manual intervention

Every deviation was driven by a concrete problem encountered during development, not by preference or convenience. The code has been tested against these scenarios; the spec was not.

My recommendation: update the architecture document to reflect the implemented design and treat it as the authoritative reference going forward. Keep the original documents in the repo as historical context — they're useful for understanding the initial thinking — but they should not be used to evaluate whether the implementation is "correct."

---

## Appendix: Bugs Fixed During This Review

Three bugs were identified and fixed as part of this review process:

1. **Symbol suffix ignored** — `resolve_symbol()` had no fallback to the suffix rule. If no explicit mapping existed, it returned the master symbol unchanged instead of appending the configured suffix. Fixed in `hub/mapping/symbol.py`.

2. **Partial close volume calculation wrong in fixed mode** — When lot mode was "fixed" (constant lot size), the partial close volume was calculated using the multiplier formula instead of a proportional ratio. For example, if the master closed half the position, the slave should also close half — regardless of lot mode. Fixed in `hub/mapping/lot.py` with `compute_partial_close_volume()`.

3. **NACK on duplicate messages** — As discussed in point 3, the Slave sent NACK for duplicates, which could trigger unnecessary retries. Changed to ACK with `slave_ticket=0` in `TradeCopierSlave.mq5`.
