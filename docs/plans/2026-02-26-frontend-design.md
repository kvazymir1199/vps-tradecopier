# Trade Copier — Frontend Design (FastAPI + Next.js)

## Overview

Web panel for managing Trade Copier terminal links. Single page application with terminal status monitoring and Master→Slave link configuration.

**Access**: localhost only, no authentication.

## Architecture

```
Browser (localhost:3000)
       |
+------+------+
| Next.js App |  :3000
| shadcn/ui   |
| Tailwind    |
+------+------+
       | REST API (polling every 5s for statuses)
       v
+------+------+
| FastAPI     |  :8000
| (separate   |
|  process)   |
+------+------+
       | read + write (WAL mode)
       v
+--------------+
|  copier.db   |
|  (SQLite)    |
+--------------+
       ^
       | read + write
+------+------+
| Hub Service |
| (separate   |
|  process)   |
+-------------+
```

- **FastAPI** runs as a separate process from Hub Service
- Both processes access `copier.db` via SQLite WAL mode (safe concurrent read+write)
- No inter-process communication between FastAPI and Hub — they share the database
- Next.js polls FastAPI every 5 seconds for terminal status updates

## FastAPI REST API

### Endpoints

#### Terminals (read-only)

```
GET /api/terminals
  → [{ terminal_id, role, account_number, broker_server, status, status_message, last_heartbeat }]
  → Used by polling (every 5s)

GET /api/terminals/{terminal_id}
  → { terminal_id, role, account_number, broker_server, status, status_message, created_at, last_heartbeat }
```

#### Master-Slave Links (CRUD)

```
GET /api/links
  → [{ id, master_id, slave_id, enabled, lot_mode, lot_value, symbol_suffix, created_at }]

GET /api/links?master_id=master_1
  → filtered by master_id

POST /api/links
  body: { master_id, slave_id, lot_mode, lot_value, symbol_suffix }
  → { id, ... }
  → Validation: master must have role=master, slave must have role=slave, pair must be unique

PUT /api/links/{id}
  body: { enabled?, lot_mode?, lot_value?, symbol_suffix? }
  → { id, ... }

PATCH /api/links/{id}/toggle
  → toggles enabled (1→0 or 0→1)
  → { id, enabled }

DELETE /api/links/{id}
  → 204 No Content
  → Cascades: deletes related symbol_mappings and magic_mappings
```

#### Symbol Mappings (CRUD, per link)

```
GET /api/links/{link_id}/symbol-mappings
  → [{ id, link_id, master_symbol, slave_symbol }]

POST /api/links/{link_id}/symbol-mappings
  body: { master_symbol, slave_symbol }
  → { id, ... }
  → Validation: (link_id, master_symbol) must be unique

DELETE /api/symbol-mappings/{id}
  → 204 No Content
```

#### Magic Mappings (CRUD, per link)

```
GET /api/links/{link_id}/magic-mappings
  → [{ id, link_id, master_setup_id, slave_setup_id }]

POST /api/links/{link_id}/magic-mappings
  body: { master_setup_id, slave_setup_id }
  → { id, ... }
  → Validation: (link_id, master_setup_id) must be unique

DELETE /api/magic-mappings/{id}
  → 204 No Content
```

### Error Responses

```json
{
  "detail": "Link with this master-slave pair already exists"
}
```

HTTP status codes: 400 (validation), 404 (not found), 409 (conflict/duplicate).

### CORS

Allow origin `http://localhost:3000` only.

## Next.js Frontend

### Tech Stack

- Next.js 14+ (App Router)
- shadcn/ui components
- Tailwind CSS
- TypeScript
- Fetch API for REST calls (no extra HTTP library)

### Single Page Layout

One page at `/` with three vertical sections:

```
+----------------------------------------------------------+
|  Trade Copier — Terminal Management                      |
+----------------------------------------------------------+
|                                                          |
|  SECTION 1: Terminals                                    |
|  +----------------------------------------------------+  |
|  | Terminal ID | Role   | Account | Status | Heartbeat|  |
|  |-------------|--------|---------|--------|----------|  |
|  | master_1    | Master | 12345   | Active | 2s ago   |  |
|  | slave_1     | Slave  | 67890   | Active | 5s ago   |  |
|  | slave_2     | Slave  | 11111   | Discon | 45s ago  |  |
|  +----------------------------------------------------+  |
|  (auto-refresh every 5 seconds)                          |
|                                                          |
+----------------------------------------------------------+
|                                                          |
|  SECTION 2: Master → Slave Links          [+ Add Link]   |
|  +----------------------------------------------------+  |
|  | Master   | Slave   | Lot    | Value | Sfx | On |Act|  |
|  |----------|---------|--------|-------|-----|----|----|  |
|  | master_1 | slave_1 | multi  | 2.0   | .s  | ON |E/D|  |
|  | master_1 | slave_2 | fixed  | 0.05  | .f  | OFF|E/D|  |
|  +----------------------------------------------------+  |
|  (click row to expand mappings below)                    |
|                                                          |
+----------------------------------------------------------+
|                                                          |
|  SECTION 3: Mappings (for selected link)                 |
|  Shown when a link row is selected                       |
|                                                          |
|  Symbol Mappings                     [+ Add Mapping]     |
|  +----------------------------------------------------+  |
|  | Master Symbol | Slave Symbol | Actions              |  |
|  |---------------|--------------|----------------------|  |
|  | XAUUSD        | GOLD.s       | [Delete]             |  |
|  +----------------------------------------------------+  |
|                                                          |
|  Magic Mappings                      [+ Add Mapping]     |
|  +----------------------------------------------------+  |
|  | Master Setup ID | Slave Setup ID | Actions          |  |
|  |-----------------|----------------|------------------|  |
|  | 01              | 05             | [Delete]         |  |
|  +----------------------------------------------------+  |
|                                                          |
+----------------------------------------------------------+
```

### UI Components (shadcn/ui)

| Component | shadcn component | Usage |
|-----------|-----------------|-------|
| Terminal table | `Table` | Read-only list with status badges |
| Status badge | `Badge` | Green=Active, Yellow=Starting/Syncing, Gray=Disconnected/Paused, Red=Error |
| Links table | `Table` | Master→Slave links with inline toggle |
| Enable toggle | `Switch` | Toggle link enabled/disabled |
| Add Link dialog | `Dialog` + `Select` + `Input` | Create new link |
| Edit Link dialog | `Dialog` + `Select` + `Input` | Modify link settings |
| Mappings tables | `Table` | Symbol and magic mappings for selected link |
| Add Mapping dialog | `Dialog` + `Input` | Create new mapping |
| Delete confirmation | `AlertDialog` | Confirm destructive actions |
| Toast notifications | `Sonner` | Success/error feedback |

### Data Flow

1. **On page load**: Fetch `/api/terminals`, `/api/links`
2. **Polling**: Every 5 seconds, re-fetch `/api/terminals` to update statuses
3. **On link select**: Fetch `/api/links/{id}/symbol-mappings` and `/api/links/{id}/magic-mappings`
4. **On CRUD action**: POST/PUT/DELETE → refetch affected data → show toast

### Relative Time Display

`last_heartbeat` shown as "X sec ago" / "X min ago" using simple calculation:
```
now_ms - last_heartbeat_ms → format as human-readable
```

## Project Structure

```
web/
├── api/                          # FastAPI backend
│   ├── __init__.py
│   ├── main.py                   # FastAPI app, CORS, lifespan
│   ├── database.py               # SQLite connection (aiosqlite, WAL)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── terminals.py          # GET /api/terminals
│   │   ├── links.py              # CRUD /api/links
│   │   ├── symbol_mappings.py    # CRUD /api/links/{id}/symbol-mappings
│   │   └── magic_mappings.py     # CRUD /api/links/{id}/magic-mappings
│   └── schemas.py                # Pydantic models
├── frontend/                     # Next.js app
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx          # Main page (single page)
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── terminals-table.tsx
│   │   │   ├── links-table.tsx
│   │   │   ├── mappings-panel.tsx
│   │   │   ├── add-link-dialog.tsx
│   │   │   ├── edit-link-dialog.tsx
│   │   │   ├── add-mapping-dialog.tsx
│   │   │   └── status-badge.tsx
│   │   ├── hooks/
│   │   │   ├── use-terminals.ts  # Polling hook for terminals
│   │   │   ├── use-links.ts
│   │   │   └── use-mappings.ts
│   │   ├── lib/
│   │   │   ├── api.ts            # Fetch wrapper for FastAPI
│   │   │   └── utils.ts          # formatTimeAgo, etc.
│   │   └── types/
│   │       └── index.ts          # TypeScript interfaces
│   └── components/ui/            # shadcn/ui generated components
└── requirements.txt              # FastAPI dependencies
```

## Deployment

| Service | Port | Run command |
|---------|------|-------------|
| Hub Service | — (pipes only) | `python -m hub.main config/config.json` |
| FastAPI | 8000 | `uvicorn web.api.main:app --host 127.0.0.1 --port 8000` |
| Next.js (dev) | 3000 | `cd web/frontend && npm run dev` |
| Next.js (prod) | 3000 | `cd web/frontend && npm run build && npm start` |

All three processes run as Windows Services via NSSM on the VPS.
