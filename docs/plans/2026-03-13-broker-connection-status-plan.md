# Broker Connection Status Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Show real broker connection status on frontend so operators see when a terminal loses network.

**Architecture:** EA heartbeat carries TERMINAL_CONNECTED flag → Hub maps to terminal status in DB → Frontend polls every 2s and shows status + message.

**Tech Stack:** MQL5 (EA), Python/asyncio (Hub), Next.js/React (Frontend), SQLite (DB)

---

### Task 1: Master EA — broker connection status in heartbeat

**Files:**
- Modify: `ea/Master/TradeCopierMaster.mq5:157-170`

**Step 1: Update heartbeat to include broker connection status**

Replace the heartbeat block (lines 158-170) with:

```mql5
   //--- Heartbeat
   if(TimeLocal() - g_lastHeartbeat >= HeartbeatSec)
   {
      int broker_connected = (int)TerminalInfoInteger(TERMINAL_CONNECTED);
      int status_code = broker_connected ? 0 : 1;
      string status_msg = broker_connected ? "OK" : "No broker connection";

      string hbMsg = BuildHeartbeatMessage(TerminalID, VpsID,
                                           AccountInfoInteger(ACCOUNT_LOGIN),
                                           AccountInfoString(ACCOUNT_COMPANY),
                                           status_code, status_msg, "");
      if(g_pipe.Send(hbMsg))
         g_logger.Debug("Heartbeat sent");
      else
         g_logger.Error("Heartbeat send failed");

      g_lastHeartbeat = TimeLocal();
   }
```

**Step 2: Compile in MetaEditor (F7) and verify no errors**

---

### Task 2: Slave EA — broker connection status in heartbeat

**Files:**
- Modify: `ea/Slave/TradeCopierSlave.mq5:144-157`

**Step 1: Update heartbeat to include broker connection status**

Replace the heartbeat block (lines 145-157) with:

```mql5
   //--- Heartbeat
   if(TimeLocal() - g_lastHeartbeat >= HeartbeatSec)
   {
      int broker_connected = (int)TerminalInfoInteger(TERMINAL_CONNECTED);
      int status_code = broker_connected ? 0 : 1;
      string status_msg = broker_connected ? "OK" : "No broker connection";

      string hbMsg = BuildHeartbeatMessage(TerminalID, VpsID,
                                           AccountInfoInteger(ACCOUNT_LOGIN),
                                           AccountInfoString(ACCOUNT_COMPANY),
                                           status_code, status_msg, "");
      if(g_ackPipe.Send(hbMsg))
         g_logger.Debug("Heartbeat sent");
      else
         g_logger.Error("Heartbeat send failed");

      g_lastHeartbeat = TimeLocal();
   }
```

**Step 2: Compile in MetaEditor (F7) and verify no errors**

**Step 3: Commit EA changes**

```bash
git add ea/Master/TradeCopierMaster.mq5 ea/Slave/TradeCopierSlave.mq5
git commit -m "feat: EA heartbeat reports broker connection status"
```

---

### Task 3: Hub — map heartbeat status_code to terminal status

**Files:**
- Modify: `hub/main.py:46-59` (master heartbeat handler)
- Modify: `hub/main.py:96-107` (slave heartbeat handler)

**Step 1: Update master heartbeat handler**

In `_handle_master_message`, the HEARTBEAT block currently does:
```python
await self.db.update_terminal_status(terminal_id, "Active", "OK")
```

Replace with:
```python
status_code = data.get("payload", {}).get("status_code", 0)
status_msg = data.get("payload", {}).get("status_msg", "OK")
if status_code == 0:
    await self.db.update_terminal_status(terminal_id, "Active", "OK")
else:
    await self.db.update_terminal_status(terminal_id, "Error", status_msg)
```

**Step 2: Update slave heartbeat handler**

In `_handle_slave_ack`, apply the same logic for HEARTBEAT processing.

**Step 3: Run tests**

```bash
uv run pytest tests/ -v
```

**Step 4: Commit**

```bash
git add hub/main.py
git commit -m "feat: Hub maps heartbeat status_code to terminal status"
```

---

### Task 4: Hub — fix FOREIGN KEY constraint on ACK insert

**Files:**
- Modify: `hub/main.py:61-85` (trade message handling)

**Step 1: Insert message record before routing**

In `_handle_master_message`, after `msg = decode_master_message(raw)` and before `commands = await self.router.route(msg)`, add:

```python
import json as _json
await self.db.insert_message(
    msg.msg_id, msg.master_id, str(msg.type),
    _json.dumps(msg.payload, separators=(',', ':')), msg.ts_ms,
)
```

**Step 2: Run tests**

```bash
uv run pytest tests/ -v
```

**Step 3: Commit**

```bash
git add hub/main.py
git commit -m "fix: insert message record before routing to satisfy FK constraint"
```

---

### Task 5: Frontend — faster polling + status message display

**Files:**
- Modify: `web/frontend/src/hooks/use-terminals.ts:6`
- Modify: `web/frontend/src/components/terminals-table.tsx:51-53`

**Step 1: Change polling interval from 5s to 2s**

In `use-terminals.ts` line 6, change:
```typescript
export function useTerminals(pollInterval = 5000) {
```
to:
```typescript
export function useTerminals(pollInterval = 2000) {
```

**Step 2: Show status_message in terminals table**

In `terminals-table.tsx`, replace the Status cell (line 51-53):
```tsx
<TableCell>
  <StatusBadge status={t.status} />
</TableCell>
```
with:
```tsx
<TableCell>
  <div className="flex items-center gap-2">
    <StatusBadge status={t.status} />
    {t.status_message && t.status_message !== "OK" && (
      <span className="text-xs text-muted-foreground">{t.status_message}</span>
    )}
  </div>
</TableCell>
```

**Step 3: Verify frontend builds**

```bash
cd web/frontend && npm run build
```

**Step 4: Commit**

```bash
git add web/frontend/src/hooks/use-terminals.ts web/frontend/src/components/terminals-table.tsx
git commit -m "feat: 2s polling + show status message on terminals table"
```

---

### Task 6: Integration test

**Step 1: Start Hub, connect both EAs, verify:**
- Terminals show `Active` (green) when broker is connected
- Disconnect broker network → within 10s heartbeat → status changes to `Error` (red) with "No broker connection" message
- Reconnect → status returns to `Active`

**Step 2: Final commit if any fixes needed**
