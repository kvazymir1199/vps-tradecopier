# Broker Connection Status on Frontend

## Problem

EA terminals can lose broker connection while the named pipe to Hub remains active.
Hub marks them as "Active" based on heartbeat arrival, but the terminal cannot execute orders.
Frontend shows green "Active" badge — misleading.

## Solution

EA heartbeat includes `TERMINAL_CONNECTED` status. Hub maps it to terminal status in DB.
Frontend shows the real status with 2s polling.

## Changes

### 1. EA Heartbeat (Master + Slave)

Both EAs already send heartbeat with `status_code`, `status_msg`, `last_error` in payload.
Change the values based on `TerminalInfoInteger(TERMINAL_CONNECTED)`:

- Connected: `status_code=0, status_msg="OK"`
- Disconnected: `status_code=1, status_msg="No broker connection"`

### 2. Hub Heartbeat Handler

Currently always sets status to "Active". Change to:

- `status_code == 0` → `update_terminal_status(id, "Active", "OK")`
- `status_code != 0` → `update_terminal_status(id, "Error", status_msg)`

Applies to both `_handle_master_message` and `_handle_slave_ack` HEARTBEAT handlers.

### 3. Frontend

- `use-terminals.ts`: polling interval 5000 → 2000 ms
- `terminals-table.tsx`: show `status_message` next to status badge when not "OK"

### 4. Bug Fix: FOREIGN KEY constraint on ACK insert

Hub inserts ACK into `message_acks` which has FK to `messages(master_id, msg_id)`.
But Hub never inserts into `messages` table when forwarding trade messages.
Fix: insert message record before forwarding, or remove FK constraint.
Chosen approach: insert message record in `_handle_master_message` before routing.

## Files to Modify

- `ea/Master/TradeCopierMaster.mq5` — heartbeat broker_connected check
- `ea/Slave/TradeCopierSlave.mq5` — heartbeat broker_connected check
- `hub/main.py` — status logic in heartbeat handlers + insert_message before routing
- `web/frontend/src/hooks/use-terminals.ts` — polling 5s → 2s
- `web/frontend/src/components/terminals-table.tsx` — show status_message
