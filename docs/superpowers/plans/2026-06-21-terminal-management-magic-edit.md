# Terminal Management + Magic-Mapping Editing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make terminal Add/Delete and magic-mapping editing fully functional across the FastAPI backend and Next.js frontend.

**Architecture:** Backend gets a fixed `POST /terminals`, a new cascading `DELETE /terminals/{id}`, and a new `PUT /magic-mappings/{id}`, all following the existing `links.py` CRUD pattern. Frontend gets create/delete plumbing in `use-terminals`, an `updateMagicMapping` method in `use-mappings`, an Add-Terminal dialog with a Delete action in the terminals table, and an Edit-Magic-Mapping dialog wired into the mappings panel.

**Tech Stack:** Python 3.11 + FastAPI + aiosqlite (SQLite WAL), pytest-asyncio + httpx ASGITransport for tests; Next.js (App Router) + React + shadcn/ui + sonner toasts on the frontend.

## Global Constraints

- DB writes go through the `get_db()` async context manager; never block the event loop.
- SQLite stays in WAL mode; `PRAGMA foreign_keys = ON` is already set per-connection in `web/api/database.py`.
- `terminals.status` must be one of: `Starting`, `Connected`, `Syncing`, `Active`, `Paused`, `Disconnected`, `Error` (CHECK constraint).
- `terminals.created_at` / `last_heartbeat` are stored in **milliseconds** (`int(time.time() * 1000)`), matching `DatabaseManager.register_terminal`.
- Do NOT change Hub Service, EAs, the message protocol, or `hub/db/schema.sql`.
- Python: classes `PascalCase`, functions `snake_case`. TypeScript: components/interfaces `PascalCase`, hooks `useCamelCase`.
- Frontend fetch calls live inside hooks calling `fetchApi` directly (existing pattern in `use-mappings.ts`); do not add wrapper functions to `lib/api.ts`.
- The whole feature is built on a branch `feat/terminal-management-magic-edit` (we start on `main`).

---

## Setup (do once before Task 1)

- [ ] **Create the feature branch**

```bash
git checkout -b feat/terminal-management-magic-edit
```

- [ ] **Commit the already-written spec + this plan**

```bash
git add docs/superpowers/specs/2026-06-21-terminal-management-magic-edit-design.md \
        docs/superpowers/plans/2026-06-21-terminal-management-magic-edit.md
git commit -m "docs: spec + plan for terminal management and magic-mapping editing"
```

---

## Task 1: Fix `POST /terminals`

The current endpoint inserts `status='Inactive'` (violates CHECK) and omits `created_at` (NOT NULL) — it fails at runtime. Fix it to insert a valid status with millisecond timestamps, reject duplicates (409) and bad roles (400).

**Files:**
- Modify: `web/api/routers/terminals.py`
- Test: `tests/test_api_terminals.py`

**Interfaces:**
- Consumes: `TerminalCreate { terminal_id: str, role: str }`, `TerminalOut` (both already in `web/api/schemas.py`); `get_db` from `web.api.database`.
- Produces: `POST /api/terminals` → 201 `TerminalOut`; 400 on bad role; 409 on duplicate.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api_terminals.py`:

```python
@pytest.mark.asyncio
async def test_create_terminal(client):
    resp = await client.post("/api/terminals", json={"terminal_id": "M2", "role": "master"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["terminal_id"] == "M2"
    assert data["role"] == "master"
    assert data["status"] == "Disconnected"
    # created_at/last_heartbeat are stored in ms, so well above a seconds-epoch value
    assert data["last_heartbeat"] > 1_000_000_000_000


@pytest.mark.asyncio
async def test_create_terminal_duplicate(client):
    resp = await client.post("/api/terminals", json={"terminal_id": "M1", "role": "master"})
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_terminal_bad_role(client):
    resp = await client.post("/api/terminals", json={"terminal_id": "X1", "role": "boss"})
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api_terminals.py::test_create_terminal tests/test_api_terminals.py::test_create_terminal_duplicate tests/test_api_terminals.py::test_create_terminal_bad_role -v`
Expected: FAIL — `test_create_terminal` errors on the DB insert (NOT NULL / CHECK), `test_create_terminal_duplicate` returns 201/500 instead of 409.

- [ ] **Step 3: Rewrite `create_terminal`**

Replace the `create_terminal` function in `web/api/routers/terminals.py` with:

```python
@router.post("", response_model=TerminalOut, status_code=201)
async def create_terminal(body: TerminalCreate):
    """Register a terminal manually so Hub creates its pipes on next restart."""
    if body.role not in ("master", "slave"):
        raise HTTPException(status_code=400, detail="role must be 'master' or 'slave'")
    now_ms = int(time.time() * 1000)
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT terminal_id FROM terminals WHERE terminal_id = ?", (body.terminal_id,)
        )
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail="Terminal already exists")
        await db.execute(
            """INSERT INTO terminals
               (terminal_id, role, status, status_message, created_at, last_heartbeat)
               VALUES (?, ?, 'Disconnected', 'Registered manually', ?, ?)""",
            (body.terminal_id, body.role, now_ms, now_ms),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT * FROM terminals WHERE terminal_id = ?", (body.terminal_id,)
        )
        row = await cursor.fetchone()
    return dict(row)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api_terminals.py -v`
Expected: PASS (all create tests + the existing list/get tests).

- [ ] **Step 5: Commit**

```bash
git add web/api/routers/terminals.py tests/test_api_terminals.py
git commit -m "fix: make POST /terminals insert valid status + created_at, reject dupes/bad roles"
```

---

## Task 2: Add cascading `DELETE /terminals/{terminal_id}`

Delete a terminal and everything that depends on it: its links (which cascade to symbol/magic-mappings via the `link_id` FK), its heartbeats (no cascade — explicit), and its `terminal_symbols` (cascade on terminal delete).

**Files:**
- Modify: `web/api/routers/terminals.py`
- Test: `tests/test_api_terminals.py`

**Interfaces:**
- Consumes: `get_db`; `Response` from `fastapi`.
- Produces: `DELETE /api/terminals/{terminal_id}` → 204 on success, 404 if missing.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api_terminals.py` (note: `import web.api.database as database` is already at the top of the file):

```python
@pytest.mark.asyncio
async def test_delete_terminal_not_found(client):
    resp = await client.delete("/api/terminals/NOPE")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_terminal_cascade(client):
    # Build a link M1->S1 with a magic + symbol mapping via the API
    link = (await client.post("/api/links", json={"master_id": "M1", "slave_id": "S1"})).json()
    link_id = link["id"]
    await client.post(f"/api/links/{link_id}/magic-mappings", json={
        "master_setup_id": 1, "slave_setup_id": 5, "allowed_direction": "BOTH",
    })
    await client.post(f"/api/links/{link_id}/symbol-mappings", json={
        "master_symbol": "EURUSD", "slave_symbol": "EURUSDm",
    })
    # Insert a heartbeat row directly (no API for it); database.DB_PATH was set by the fixture
    async with aiosqlite.connect(database.DB_PATH) as db:
        await db.execute(
            "INSERT INTO heartbeats (terminal_id, vps_id, ts_ms, status_code) VALUES (?, ?, ?, ?)",
            ("M1", "vps_1", int(time.time() * 1000), 0),
        )
        await db.commit()

    resp = await client.delete("/api/terminals/M1")
    assert resp.status_code == 204

    # Terminal, link, mappings and heartbeats for M1 are all gone
    async with aiosqlite.connect(database.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        assert (await (await db.execute(
            "SELECT COUNT(*) c FROM terminals WHERE terminal_id='M1'")).fetchone())["c"] == 0
        assert (await (await db.execute(
            "SELECT COUNT(*) c FROM master_slave_links WHERE id=?", (link_id,))).fetchone())["c"] == 0
        assert (await (await db.execute(
            "SELECT COUNT(*) c FROM magic_mappings WHERE link_id=?", (link_id,))).fetchone())["c"] == 0
        assert (await (await db.execute(
            "SELECT COUNT(*) c FROM symbol_mappings WHERE link_id=?", (link_id,))).fetchone())["c"] == 0
        assert (await (await db.execute(
            "SELECT COUNT(*) c FROM heartbeats WHERE terminal_id='M1'")).fetchone())["c"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api_terminals.py::test_delete_terminal_not_found tests/test_api_terminals.py::test_delete_terminal_cascade -v`
Expected: FAIL with 405 Method Not Allowed (no DELETE route yet).

- [ ] **Step 3: Add the DELETE route + import `Response`**

In `web/api/routers/terminals.py`, change the FastAPI import line to include `Response`:

```python
from fastapi import APIRouter, HTTPException, Response
```

Then append this route to the file:

```python
@router.delete("/{terminal_id}", status_code=204)
async def delete_terminal(terminal_id: str):
    """Delete a terminal and its dependent links, mappings, and heartbeats."""
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT terminal_id FROM terminals WHERE terminal_id = ?", (terminal_id,)
        )
        if await cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Terminal not found")
        # Links cascade to symbol_mappings + magic_mappings via the link_id FK
        await db.execute(
            "DELETE FROM master_slave_links WHERE master_id = ? OR slave_id = ?",
            (terminal_id, terminal_id),
        )
        # heartbeats has no ON DELETE CASCADE — remove explicitly
        await db.execute("DELETE FROM heartbeats WHERE terminal_id = ?", (terminal_id,))
        # terminal_symbols cascades when the terminal row is removed
        await db.execute("DELETE FROM terminals WHERE terminal_id = ?", (terminal_id,))
        await db.commit()
    return Response(status_code=204)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_api_terminals.py -v`
Expected: PASS (all terminal tests).

- [ ] **Step 5: Commit**

```bash
git add web/api/routers/terminals.py tests/test_api_terminals.py
git commit -m "feat: add cascading DELETE /terminals/{id}"
```

---

## Task 3: Add `PUT /magic-mappings/{mapping_id}`

Allow editing `slave_setup_id` and `allowed_direction`. `master_setup_id` is part of `UNIQUE(link_id, master_setup_id)` and stays fixed.

**Files:**
- Modify: `web/api/schemas.py`
- Modify: `web/api/routers/magic_mappings.py`
- Test: `tests/test_api_mappings.py`

**Interfaces:**
- Consumes: `MagicMappingUpdate { slave_setup_id?: int, allowed_direction?: Literal["BUY","SELL","BOTH"] }` (new), `MagicMappingOut` (existing), `get_db`.
- Produces: `PUT /api/magic-mappings/{mapping_id}` → 200 `MagicMappingOut`; 404 if missing; 422 on invalid direction.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_api_mappings.py`:

```python
@pytest.mark.asyncio
async def test_update_magic_mapping(client):
    created = (await client.post("/api/links/1/magic-mappings", json={
        "master_setup_id": 1, "slave_setup_id": 5, "allowed_direction": "BOTH",
    })).json()
    mid = created["id"]

    resp = await client.put(f"/api/magic-mappings/{mid}", json={
        "slave_setup_id": 9, "allowed_direction": "BUY",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["slave_setup_id"] == 9
    assert data["allowed_direction"] == "BUY"
    assert data["master_setup_id"] == 1  # unchanged


@pytest.mark.asyncio
async def test_update_magic_mapping_partial(client):
    created = (await client.post("/api/links/1/magic-mappings", json={
        "master_setup_id": 2, "slave_setup_id": 5, "allowed_direction": "BOTH",
    })).json()
    mid = created["id"]

    resp = await client.put(f"/api/magic-mappings/{mid}", json={"allowed_direction": "SELL"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["allowed_direction"] == "SELL"
    assert data["slave_setup_id"] == 5  # untouched


@pytest.mark.asyncio
async def test_update_magic_mapping_not_found(client):
    resp = await client.put("/api/magic-mappings/9999", json={"allowed_direction": "BUY"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_magic_mapping_invalid_direction(client):
    created = (await client.post("/api/links/1/magic-mappings", json={
        "master_setup_id": 3, "slave_setup_id": 5, "allowed_direction": "BOTH",
    })).json()
    mid = created["id"]
    resp = await client.put(f"/api/magic-mappings/{mid}", json={"allowed_direction": "UP"})
    assert resp.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_api_mappings.py -k update_magic -v`
Expected: FAIL with 405 Method Not Allowed (no PUT route yet).

- [ ] **Step 3: Add the `MagicMappingUpdate` schema**

In `web/api/schemas.py`, directly below the `MagicMappingOut` class, add:

```python
class MagicMappingUpdate(BaseModel):
    slave_setup_id: Optional[int] = None
    allowed_direction: Optional[Literal["BUY", "SELL", "BOTH"]] = None
```

(`Optional` and `Literal` are already imported at the top of the file.)

- [ ] **Step 4: Add the PUT route**

In `web/api/routers/magic_mappings.py`, update the import line:

```python
from web.api.schemas import MagicMappingCreate, MagicMappingOut, MagicMappingUpdate
```

Then add this route after `create_magic_mapping` (before `delete_magic_mapping`):

```python
@router.put("/magic-mappings/{mapping_id}", response_model=MagicMappingOut)
async def update_magic_mapping(mapping_id: int, body: MagicMappingUpdate):
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM magic_mappings WHERE id = ?", (mapping_id,)
        )
        existing = await cursor.fetchone()
        if existing is None:
            raise HTTPException(status_code=404, detail="Magic mapping not found")

        updates = body.model_dump(exclude_none=True)
        if not updates:
            return dict(existing)

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [mapping_id]
        await db.execute(
            f"UPDATE magic_mappings SET {set_clause} WHERE id = ?", values
        )
        await db.commit()

        cursor = await db.execute(
            "SELECT * FROM magic_mappings WHERE id = ?", (mapping_id,)
        )
        row = await cursor.fetchone()
    return dict(row)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_api_mappings.py -v`
Expected: PASS (all mapping tests, old + new).

- [ ] **Step 6: Commit**

```bash
git add web/api/schemas.py web/api/routers/magic_mappings.py tests/test_api_mappings.py
git commit -m "feat: add PUT /magic-mappings/{id} for editing slave_setup_id + direction"
```

---

## Task 4: Frontend hooks — create/delete terminal + update magic-mapping

Wire the new backend endpoints into the React hooks. No frontend unit tests exist; verification is the production build in Task 7. Keep this task focused on the data layer.

**Files:**
- Modify: `web/frontend/src/hooks/use-terminals.ts`
- Modify: `web/frontend/src/hooks/use-mappings.ts`

**Interfaces:**
- Produces (use-terminals): `{ terminals, loading, createTerminal(terminalId: string, role: "master"|"slave"): Promise<void>, deleteTerminal(terminalId: string): Promise<void> }`.
- Produces (use-mappings): adds `updateMagicMapping(id: number, updates: { slave_setup_id?: number; allowed_direction?: AllowedDirection }): Promise<void>` to the existing return object.

- [ ] **Step 1: Rewrite `use-terminals.ts`**

Replace the whole file with:

```typescript
"use client";
import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { Terminal } from "@/types";

export function useTerminals(pollInterval = 2000) {
  const [terminals, setTerminals] = useState<Terminal[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await fetchApi<Terminal[]>("/terminals");
      setTerminals(data);
    } catch (err) {
      console.error("Failed to load terminals:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, pollInterval);
    return () => clearInterval(interval);
  }, [load, pollInterval]);

  const createTerminal = async (terminalId: string, role: "master" | "slave") => {
    await fetchApi("/terminals", {
      method: "POST",
      body: JSON.stringify({ terminal_id: terminalId, role }),
    });
    await load();
  };

  const deleteTerminal = async (terminalId: string) => {
    await fetchApi(`/terminals/${terminalId}`, { method: "DELETE" });
    await load();
  };

  return { terminals, loading, createTerminal, deleteTerminal };
}
```

- [ ] **Step 2: Add `updateMagicMapping` to `use-mappings.ts`**

In `web/frontend/src/hooks/use-mappings.ts`, add this function after `deleteMagicMapping`:

```typescript
  const updateMagicMapping = async (
    id: number,
    updates: { slave_setup_id?: number; allowed_direction?: AllowedDirection },
  ) => {
    await fetchApi(`/magic-mappings/${id}`, {
      method: "PUT",
      body: JSON.stringify(updates),
    });
    await refresh();
  };
```

Then add `updateMagicMapping` to the returned object:

```typescript
  return { symbolMappings, magicMappings, loading, refresh, addSymbolMapping, deleteSymbolMapping, addMagicMapping, deleteMagicMapping, updateMagicMapping };
```

- [ ] **Step 3: Type-check the changed files**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/hooks/use-terminals.ts web/frontend/src/hooks/use-mappings.ts
git commit -m "feat(ui): hook plumbing for terminal create/delete + magic-mapping update"
```

---

## Task 5: Add-Terminal dialog + Delete action in the terminals table

**Files:**
- Create: `web/frontend/src/components/add-terminal-dialog.tsx`
- Modify: `web/frontend/src/components/terminals-table.tsx`

**Interfaces:**
- Consumes: `useTerminals()` (`createTerminal`, `deleteTerminal` from Task 4); `sonner` `toast`; shadcn `Button`, `Dialog*`, `Input`, `Select*`.
- Produces: `AddTerminalDialog` component with props `{ onSubmit: (terminalId: string, role: "master"|"slave") => Promise<void>; open: boolean; onOpenChange: (open: boolean) => void }`.

- [ ] **Step 1: Create `add-terminal-dialog.tsx`**

```typescript
"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface AddTerminalDialogProps {
  onSubmit: (terminalId: string, role: "master" | "slave") => Promise<void>;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddTerminalDialog({ onSubmit, open, onOpenChange }: AddTerminalDialogProps) {
  const [terminalId, setTerminalId] = useState("");
  const [role, setRole] = useState<"master" | "slave">("master");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await onSubmit(terminalId.trim(), role);
      setTerminalId("");
      setRole("master");
      onOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Terminal</DialogTitle>
          <DialogDescription>
            Manually register a terminal so the Hub creates its named pipes on next
            restart. It stays Disconnected until its EA connects.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <label className="text-sm font-medium">Terminal ID</label>
            <Input
              type="text"
              placeholder="e.g. master_1"
              value={terminalId}
              onChange={(e) => setTerminalId(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">Role</label>
            <Select value={role} onValueChange={(v) => setRole(v as "master" | "slave")}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="master">Master</SelectItem>
                <SelectItem value="slave">Slave</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!terminalId.trim() || submitting}>
            {submitting ? "Adding..." : "Add Terminal"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Rewrite `terminals-table.tsx`**

Replace the whole file with:

```typescript
"use client";

import { useState } from "react";
import { useTerminals } from "@/hooks/use-terminals";
import { formatTimeAgo } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";
import { AddTerminalDialog } from "@/components/add-terminal-dialog";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export function TerminalsTable() {
  const { terminals, loading, createTerminal, deleteTerminal } = useTerminals();
  const [addOpen, setAddOpen] = useState(false);

  const handleAdd = async (terminalId: string, role: "master" | "slave") => {
    try {
      await createTerminal(terminalId, role);
      toast.success("Terminal added");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add terminal");
      throw err;
    }
  };

  const handleDelete = async (terminalId: string) => {
    if (!confirm(`Delete terminal "${terminalId}" and all its links/mappings?`)) return;
    try {
      await deleteTerminal(terminalId);
      toast.success("Terminal deleted");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete terminal");
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">Terminals</h2>
          {loading && (
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent opacity-50" />
          )}
        </div>
        <Button size="sm" onClick={() => setAddOpen(true)}>
          + Add Terminal
        </Button>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Terminal ID</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Account</TableHead>
            <TableHead>Broker</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Last Heartbeat</TableHead>
            <TableHead className="w-20">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {terminals.length === 0 && !loading ? (
            <TableRow>
              <TableCell colSpan={7} className="text-center text-muted-foreground">
                No terminals connected
              </TableCell>
            </TableRow>
          ) : (
            terminals.map((t) => (
              <TableRow key={t.terminal_id}>
                <TableCell className="font-mono text-xs">{t.terminal_id}</TableCell>
                <TableCell className="capitalize">{t.role}</TableCell>
                <TableCell>{t.account_number ?? "-"}</TableCell>
                <TableCell>{t.broker_server ?? "-"}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={t.status} />
                    {t.status_message && t.status_message !== "OK" && (
                      <span className="text-xs text-muted-foreground">{t.status_message}</span>
                    )}
                  </div>
                </TableCell>
                <TableCell>{formatTimeAgo(t.last_heartbeat)}</TableCell>
                <TableCell>
                  <Button
                    variant="destructive"
                    size="xs"
                    onClick={() => handleDelete(t.terminal_id)}
                  >
                    Delete
                  </Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      <AddTerminalDialog open={addOpen} onOpenChange={setAddOpen} onSubmit={handleAdd} />
    </div>
  );
}
```

- [ ] **Step 3: Type-check**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/components/add-terminal-dialog.tsx web/frontend/src/components/terminals-table.tsx
git commit -m "feat(ui): add-terminal dialog + delete action in terminals table"
```

---

## Task 6: Edit-Magic-Mapping dialog + wiring in the mappings panel

**Files:**
- Create: `web/frontend/src/components/edit-magic-mapping-dialog.tsx`
- Modify: `web/frontend/src/components/mappings-panel.tsx`

**Interfaces:**
- Consumes: `MagicMapping`, `AllowedDirection` from `@/types`; `updateMagicMapping` from `useMappings` (Task 4); shadcn `Button`, `Dialog*`, `Input`, `Select*`.
- Produces: `EditMagicMappingDialog` with props `{ mapping: MagicMapping | null; open: boolean; onOpenChange: (open: boolean) => void; onSubmit: (id: number, updates: { slave_setup_id: number; allowed_direction: AllowedDirection }) => Promise<void> }`.

- [ ] **Step 1: Create `edit-magic-mapping-dialog.tsx`**

```typescript
"use client";

import { useState, useEffect } from "react";
import { MagicMapping, AllowedDirection } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface EditMagicMappingDialogProps {
  mapping: MagicMapping | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (
    id: number,
    updates: { slave_setup_id: number; allowed_direction: AllowedDirection },
  ) => Promise<void>;
}

export function EditMagicMappingDialog({
  mapping,
  open,
  onOpenChange,
  onSubmit,
}: EditMagicMappingDialogProps) {
  const [slaveSetupId, setSlaveSetupId] = useState("");
  const [direction, setDirection] = useState<AllowedDirection>("BOTH");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (mapping) {
      setSlaveSetupId(String(mapping.slave_setup_id));
      setDirection(mapping.allowed_direction);
    }
  }, [mapping]);

  const handleSubmit = async () => {
    if (!mapping) return;
    setSubmitting(true);
    try {
      await onSubmit(mapping.id, {
        slave_setup_id: parseInt(slaveSetupId),
        allowed_direction: direction,
      });
      onOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Magic Mapping</DialogTitle>
          <DialogDescription>
            Change the slave setup ID or allowed direction. The master setup ID is
            fixed — delete and recreate the mapping to change it.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <label className="text-sm font-medium">Master Setup ID</label>
            <Input type="number" value={mapping?.master_setup_id ?? ""} disabled />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">Slave Setup ID</label>
            <Input
              type="number"
              value={slaveSetupId}
              onChange={(e) => setSlaveSetupId(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">Allowed Direction</label>
            <Select value={direction} onValueChange={(v) => setDirection(v as AllowedDirection)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="BOTH">Both (BUY + SELL)</SelectItem>
                <SelectItem value="BUY">BUY only</SelectItem>
                <SelectItem value="SELL">SELL only</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!slaveSetupId || submitting}>
            {submitting ? "Saving..." : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
```

- [ ] **Step 2: Wire it into `mappings-panel.tsx`**

(a) Add imports near the other component imports:

```typescript
import { SymbolSuggestionsResponse, AllowedDirection, MagicMapping } from "@/types";
import { EditMagicMappingDialog } from "@/components/edit-magic-mapping-dialog";
```

(replace the existing `import { SymbolSuggestionsResponse, AllowedDirection } from "@/types";` line with the first line above).

(b) Pull `updateMagicMapping` from the hook — change the destructure:

```typescript
  const {
    symbolMappings,
    magicMappings,
    loading,
    refresh,
    deleteSymbolMapping,
    addSymbolMapping,
    addMagicMapping,
    deleteMagicMapping,
    updateMagicMapping,
  } = useMappings(linkId);
```

(c) Add edit state next to `const [magicDialogOpen, setMagicDialogOpen] = useState(false);`:

```typescript
  const [editingMagic, setEditingMagic] = useState<MagicMapping | null>(null);
```

(d) Add the update handler next to `handleDeleteMagic`:

```typescript
  const handleUpdateMagic = async (
    id: number,
    updates: { slave_setup_id: number; allowed_direction: AllowedDirection },
  ) => {
    try {
      await updateMagicMapping(id, updates);
      toast.success("Magic mapping updated");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to update magic mapping"
      );
      throw err;
    }
  };
```

(e) In the magic-mappings table body, replace the single Delete `<TableCell>` (the actions cell inside `magicMappings.map`) with an Edit + Delete pair:

```typescript
                        <TableCell>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="xs"
                              onClick={() => setEditingMagic(m)}
                            >
                              Edit
                            </Button>
                            <Button
                              variant="destructive"
                              size="xs"
                              onClick={() => handleDeleteMagic(m.id)}
                            >
                              Delete
                            </Button>
                          </div>
                        </TableCell>
```

(f) Render the dialog next to the existing `<AddMappingDialog ... />`:

```typescript
        <EditMagicMappingDialog
          mapping={editingMagic}
          open={editingMagic !== null}
          onOpenChange={(o) => { if (!o) setEditingMagic(null); }}
          onSubmit={handleUpdateMagic}
        />
```

- [ ] **Step 3: Type-check**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/components/edit-magic-mapping-dialog.tsx web/frontend/src/components/mappings-panel.tsx
git commit -m "feat(ui): edit magic-mapping dialog wired into mappings panel"
```

---

## Task 7: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full backend test suite**

Run: `uv run pytest`
Expected: all tests pass (previously-passing tests + the new terminal/magic tests).

- [ ] **Step 2: Production build of the frontend**

Run: `cd web/frontend && npm run build`
Expected: build succeeds with no type errors.

- [ ] **Step 3: Manual smoke test (optional but recommended)**

Start backend + frontend, then:
- Add a terminal via "+ Add Terminal" → appears as Disconnected.
- Create a link to it, add a magic-mapping, Edit it (change slave id + direction) → row updates.
- Delete the terminal → terminal, its link and mappings disappear.

Run:
```bash
uv run uvicorn web.api.main:app --port 8000   # terminal 1
cd web/frontend && npm run dev                  # terminal 2 (http://localhost:3000)
```

- [ ] **Step 4: Final no-op commit check**

```bash
git status   # should be clean; all work committed across Tasks 1-6
```

---

## Self-Review

**Spec coverage:**
- Fix `POST /terminals` → Task 1. ✅
- `DELETE /terminals/{id}` cascade (links→mappings, explicit heartbeats, terminal_symbols) → Task 2. ✅
- `MagicMappingUpdate` schema + `PUT /magic-mappings/{id}` → Task 3. ✅
- Frontend create/delete terminal plumbing + `updateMagicMapping` → Task 4. ✅
- Add-terminal dialog + delete action → Task 5. ✅
- Edit-magic-mapping dialog + panel wiring → Task 6. ✅
- Backend tests (create/delete/cascade/update) → Tasks 1-3. ✅
- `npm run build` verification → Task 7. ✅

**Deviation from spec:** the spec mentioned adding `createTerminal`/`deleteTerminal`/`updateMagicMapping` to `lib/api.ts`. The codebase pattern (`use-mappings.ts`) calls `fetchApi` directly inside hooks, so the plan keeps that pattern instead of adding wrapper functions — same outcome, more consistent and DRY.

**Type consistency:** `createTerminal(terminalId, role)`, `deleteTerminal(terminalId)`, `updateMagicMapping(id, updates)` are defined identically in Task 4 and consumed with the same signatures in Tasks 5-6. `MagicMappingUpdate` fields match between schema (Task 3) and the frontend `updates` object (Tasks 4, 6). `EditMagicMappingDialog` `onSubmit` signature matches `handleUpdateMagic`.

**Placeholder scan:** no TBD/TODO; every code step contains complete code.
