# Design: Terminal management + magic-mapping editing

Date: 2026-06-21

## Problem

Two pieces of the Web UI are stubbed (declared but not functional):

1. **Terminal management.** The frontend can only list terminals (read-only hook,
   read-only table). There is no UI to add or delete a terminal. The backend has a
   `POST /terminals` endpoint, but it is **broken**: it inserts `status='Inactive'`
   (not in the `terminals.status` CHECK list) and omits the `NOT NULL` column
   `created_at`, so the insert fails. There is no `DELETE` endpoint.

2. **Magic-mapping editing.** `magic_mappings` supports `GET`/`POST`/`DELETE` but no
   `PUT`. The UI exposes only a Delete button, so an existing mapping's
   `slave_setup_id` / `allowed_direction` can only be changed by deleting and
   recreating it.

This design adds: working **Add + Delete** for terminals (no Edit), and **edit** for
magic-mappings (`slave_setup_id` + `allowed_direction`).

## Scope

In scope:
- Fix `POST /terminals`; add `DELETE /terminals/{terminal_id}` with cascade.
- Add `PUT /magic-mappings/{mapping_id}`.
- Frontend: add-terminal dialog, delete-terminal action, edit-magic-mapping dialog,
  and the api.ts / hooks plumbing.
- Backend tests (pytest-asyncio).

Out of scope:
- No changes to Hub Service, EAs, the message protocol, or the DB schema.
- No terminal Edit (terminal_id is the PK; status/broker/account come from Hub via
  heartbeat — nothing meaningful to edit manually).
- No frontend unit tests (none exist in the project) — verified via `npm run build`
  plus a manual run.

## Background facts (verified against the code)

- `terminals` columns: `terminal_id` (PK), `role` CHECK in (`master`,`slave`),
  `account_number`, `broker_server`, `status` CHECK in
  (`Starting`,`Connected`,`Syncing`,`Active`,`Paused`,`Disconnected`,`Error`),
  `status_message`, `created_at` NOT NULL, `last_heartbeat` NOT NULL.
- Hub's `register_terminal` writes `created_at`/`last_heartbeat` in **milliseconds**
  (`_now_ms()`) with `status='Starting'`. Our manual create must be consistent (ms).
- API connections enable `PRAGMA foreign_keys = ON` (`web/api/database.py:35`), so
  `ON DELETE CASCADE` is active.
- FK relationships relevant to terminal delete:
  - `master_slave_links.master_id` / `.slave_id` → `terminals(terminal_id)`
    (**no** ON DELETE CASCADE).
  - `symbol_mappings.link_id` / `magic_mappings.link_id` → `master_slave_links(id)`
    **ON DELETE CASCADE**.
  - `terminal_symbols.terminal_id` → `terminals(terminal_id)` **ON DELETE CASCADE**.
  - `heartbeats.terminal_id` → `terminals(terminal_id)` (**no** ON DELETE CASCADE) —
    must be deleted explicitly or the FK blocks the terminal delete.
  - `trade_mappings` / `messages` reference terminal ids as plain TEXT (not FKs) —
    they do not block deletion.
- The existing `links.py` router is the reference pattern for full CRUD: dynamic
  `model_dump(exclude_none=True)` updates, 404/409 handling, `Response(status_code=204)`
  for delete.

## Backend design

### terminals.py

**Fix `POST /terminals`** (`create_terminal`):
- Validate `role in ("master", "slave")` → 400 otherwise.
- If `terminal_id` already exists → 409 (matches links' duplicate behaviour).
- Insert with:
  - `created_at = last_heartbeat = int(time.time() * 1000)` (ms, like Hub),
  - `status = 'Disconnected'` (valid CHECK value; terminal has not connected yet),
  - `status_message = 'Registered manually'`.
- Return the inserted row (`TerminalOut`), 201.

**Add `DELETE /terminals/{terminal_id}`** — single transaction:
1. 404 if the terminal does not exist.
2. `DELETE FROM master_slave_links WHERE master_id = ? OR slave_id = ?`
   (cascades symbol_mappings + magic_mappings via `link_id`).
3. `DELETE FROM heartbeats WHERE terminal_id = ?` (manual — no cascade).
4. `DELETE FROM terminals WHERE terminal_id = ?` (cascades terminal_symbols).
5. `commit`; return `Response(status_code=204)`.

Note: deletes are written explicitly (not relying solely on cascade) where a cascade
does not exist, so the operation is correct regardless of PRAGMA state.

### schemas.py

Add:

```python
class MagicMappingUpdate(BaseModel):
    slave_setup_id: Optional[int] = None
    allowed_direction: Optional[Literal["BUY", "SELL", "BOTH"]] = None
```

`TerminalCreate` already exists (`terminal_id`, `role`) — unchanged.

### magic_mappings.py

**Add `PUT /magic-mappings/{mapping_id}`** (`update_magic_mapping`), mirroring
`update_link`:
- 404 if the mapping does not exist.
- `updates = body.model_dump(exclude_none=True)`; if empty, return the existing row.
- Build `SET` clause dynamically; `UPDATE ... WHERE id = ?`; commit; return updated row.
- `master_setup_id` is not editable (it is part of `UNIQUE(link_id, master_setup_id)`;
  to change it the user deletes and recreates).

## Frontend design

- **lib/api.ts**: add `createTerminal(body)`, `deleteTerminal(terminalId)`,
  `updateMagicMapping(mappingId, body)` following the existing fetch helpers.
- **hooks/use-terminals.ts**: expose `createTerminal` and `deleteTerminal` (each
  refetches after success). 5s polling stays. Add `console.error` in the catch.
- **components/terminals-table.tsx**: a "+ Add Terminal" button in the header opening
  the add dialog; a Delete button per row guarded by a confirm.
- **components/add-terminal-dialog.tsx** (new): `terminal_id` text input + `role`
  select (master/slave), modelled on `add-link-dialog.tsx`.
- **components/mappings-panel.tsx**: an Edit button per magic-mapping row opening a new
  **edit-magic-mapping-dialog.tsx** (editable `slave_setup_id` + `allowed_direction`
  select; `master_setup_id` shown read-only). hook gains `updateMagicMapping`.

## Testing

`tests/test_api_terminals.py` (extend existing):
- create: success (201 + row), duplicate id → 409, bad role → 400.
- delete: success → 204; cascade removes the terminal's links and their
  magic/symbol-mappings; heartbeats for that terminal are removed; missing id → 404.

magic-mapping update tests (in the existing mappings test file):
- update success (slave_setup_id and/or allowed_direction), 404 for unknown id,
  invalid direction rejected by schema (422).

Frontend: `cd web/frontend && npm run build` must pass; manual smoke run of add/delete
terminal and edit magic-mapping.

## Risks / notes

- The terminal-delete cascade is the riskiest part: missing the explicit
  `heartbeats` delete would surface as a foreign-key error at runtime. Covered by a
  delete test that first inserts a heartbeat row.
- Manual-create `status='Disconnected'` means a freshly added terminal shows as
  disconnected until its EA connects and Hub updates it — intended.
