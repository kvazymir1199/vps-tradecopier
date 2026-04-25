# MS2 Video Demonstration — Shooting Script

A **~5-minute screen recording** that visually confirms the three scenarios
that cannot be covered by automated tests (because they require a real MT5
terminal). All server-side guarantees are already proven in
`docs/ms2-approval-evidence.md` — this video is the operational confirmation.

## Setup before recording

Lay out three windows side-by-side:
- **Window 1 (left):** PowerShell tailing the Hub log
  ```powershell
  Get-Content -Wait path\to\hub.log
  ```
- **Window 2 (middle):** MT5 Master — chart + "Experts" tab visible
- **Window 3 (right):** MT5 Slave — chart + "Trade" tab + "Experts" tab

Start OBS / Win+G and record everything in one take.

---

## Scene 1 — Retry without double execution (~90 s)

**What this proves:** if an ACK is lost, Hub retries 3 times, Slave
recognizes duplicates and opens only **one** position.

**Prep:** the Slave EA has an input `InpTestDelayAckMs` (if not present, you
can achieve the same effect by briefly detaching the Slave EA right after
the position opens). Set delay to 20000 ms.

1. Show the Slave "Trade" tab: **0 positions open**. (5 s)
2. On the Master, right-click chart → New Order → **Buy EURUSD 0.10**. (5 s)
3. In the Hub log, point to:
   ```
   [Router] Forwarded OPEN msg_id=N to slave_1
   ```
4. Show the Slave "Trade" tab: **1 position opened** (BUY 0.10). (5 s)
5. Wait for the retry sequence. In the Hub log, highlight:
   ```
   [Health] ACK timeout for msg_id=N, retry 1/3
   [Health] ACK timeout for msg_id=N, retry 2/3
   [Health] ACK timeout for msg_id=N, retry 3/3
   [Health] Message msg_id=N expired after max retries
   ```
   (20 s)
6. In the Slave "Experts" tab, highlight three "Duplicate" messages:
   ```
   [Slave] Duplicate msg_id=N from master_1 — skipping
   ```
   (15 s)
7. Zoom in on the Slave "Trade" tab — still **1 position**, not 4. (10 s)
8. Say out loud: *"Four deliveries, one position. Retry bounded to 3.
   No double execution."* (5 s)

---

## Scene 2 — Master restart preserves msg_id (~60 s)

**What this proves:** after Master EA reload, the msg_id counter does
not reset to 1; it resumes from where it left off.

1. On the Master, execute 3–4 trades to advance the counter. Pause on the
   Master "Experts" tab showing the most recent log line, e.g.:
   ```
   [Master] Sent OPEN msg_id=12  → PersistMsgId: g_msgId=12
   ```
   (10 s)
2. Right-click the EA → Remove. Show "Expert removed" in the log. (5 s)
3. Wait ~3 seconds (show blank state). (3 s)
4. Drag the Master EA back onto the chart. (5 s)
5. In the Master "Experts" tab, highlight:
   ```
   [Master] Loaded g_msgId from GlobalVariable: 12
   [Master] REGISTER sent, waiting for ACK
   [Master] Hub returned resume_from=12
   [Master] Resuming — next msg_id=13
   ```
   (15 s)
6. Open one more trade on the Master. In the log:
   ```
   [Master] Sent OPEN msg_id=13
   ```
   Zoom on "13" — not "1". (10 s)
7. Say: *"Counter continued from 12. Restart did not reset idempotency."*
   (5 s)

---

## Scene 3 — Offline Slave does not destabilize the Hub (~90 s)

**What this proves:** when one Slave terminal is down, the Hub keeps
running, does not crash, and continues delivering to healthy Slaves.

**Prep:** the test environment has two Slaves (`slave_A` and `slave_B`),
both with magic mappings for the Master's setup.

1. In the browser UI at `localhost:3000`, show both Slaves **Connected**. (5 s)
2. Close the MT5 window of `slave_A` entirely (File → Exit). Wait for the
   UI to show `slave_A` as **Disconnected** after the heartbeat timeout. (15 s)
3. On the Master, open a new Buy trade. (5 s)
4. In the Hub log, highlight:
   ```
   [WARN] Slave slave_A pipe not connected, command dropped
   [INFO] Forwarded OPEN msg_id=N to slave_B
   ```
   (10 s)
5. Show the `slave_B` "Trade" tab: **new position appeared**. (5 s)
6. Open 2–3 more trades on the Master. In the Hub log, observe Hub still
   processing (not crashed, no stack trace). (15 s)
7. Restart `slave_A` (launch MT5, attach EA). In the Hub log:
   ```
   [INFO] REGISTER received from slave_A
   [INFO] Slave slave_A pipe connected
   ```
   (10 s)
8. Browser UI: `slave_A` flips back to **Connected**. (5 s)
9. Say: *"Hub uptime uninterrupted. Healthy Slave kept working.
   Offline Slave did not destabilize anything."* (5 s)

---

## Scene 4 — Direction Guard (optional, ~60 s)

**What this proves:** direction rules block mismatched trades without
blocking CLOSE / MODIFY.

1. In the UI, open a link → Add Magic Mapping → `master_setup=1,
   slave_setup=5, allowed_direction=BUY`. Save. (10 s)
2. In the table show new row, direction column displays **BUY** in green. (3 s)
3. On Master, open **Buy** EURUSD with magic `15010301` → Slave receives
   position. (10 s)
4. On Master, open **Sell** EURUSD with magic `15010301`. In Hub log:
   ```
   [Router] Direction guard blocked: allowed=BUY, got=SELL
   ```
   Slave "Trade" tab — no new position. (15 s)
5. On Master, **close** the original BUY position. Hub log shows CLOSE
   forwarded (no direction guard for CLOSE). Slave closes its position. (15 s)
6. Say: *"Direction guard blocks wrong-side opens but does not block
   close/modify operations."* (5 s)

---

## Closing frame (~15 s)

Switch to a terminal and run:
```bash
uv run pytest tests/test_ms2_proof.py -v
```
Zoom on the final line:
```
============================= 20 passed ==============================
```

Narration: *"Twenty automated tests, all passing. Three scenarios just
demonstrated live. MS2 approval ready."*

---

## Total run time

| Scene | Duration |
|-------|----------|
| 1. Retry without double execution | 90 s |
| 2. Master restart | 60 s |
| 3. Offline Slave | 90 s |
| 4. Direction Guard (optional) | 60 s |
| Closing | 15 s |
| **Total** | **~5 min** (4 min without Scene 4) |

## Tips

- Use a zoom/magnifier tool for log lines (PowerToys ZoomIt or OBS zoom filter).
- Speak over the recording in English so the client can follow.
- Keep the mouse still while log lines scroll — highlight by selecting
  the text rather than pointing.
- Before recording, set `ack_timeout_sec=5` and `ack_max_retries=3` in the
  config so retries fit in the shot.
