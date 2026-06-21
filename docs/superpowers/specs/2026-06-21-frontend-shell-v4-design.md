# Design: Frontend shell V4 (sidebar + topbar + dashboard)

Date: 2026-06-21

## Problem

The web UI currently renders as a thin top `nav` bar (`layout.tsx`) over three
route pages plus a single home page that stacks the terminals table, links table,
and mappings panel. A new admin design ("V4") was prototyped in a separate
Claude design project: a left **sidebar** + sticky **topbar** + a **dashboard**
screen with a metric strip and setup-flow cards, wrapping the existing real
components. This design ports that shell into the real Next.js app.

The prototype (`app.jsx` / `Admin Dashboard.html`) mounts the real components
against a mock (`window.__tcDb`) and includes debug chrome (a V1–V4 variant
switcher, a theme toggle) and a Dialogs showcase screen. Those are prototype-only
and are dropped here.

## Scope

In scope:
- Replace the top-nav `layout.tsx` with the shell: sidebar + topbar + content area.
- Convert the home page into a Dashboard (metric strip + setup-flow cards) backed
  by real hooks.
- Split the current combined home page into `/terminals` and `/links` routes.
- Add the shell CSS to `globals.css`, reproducing the prototype's V4 look using the
  existing design-system tokens.
- Adapt the existing `alerts` / `settings` / `settings/telegram` pages to live
  inside the shell (no nested `<main>`, single global `Toaster`).

Out of scope / dropped:
- No backend changes (Hub, EAs, FastAPI, DB) — frontend only.
- Drop prototype debug chrome: V1–V4 variant switcher, theme toggle, the Dialogs
  showcase screen, `mock.js`, `window.__tcDb`, and the `localStorage`
  screen/variant/theme persistence.
- No frontend unit tests (none exist) — verified via `tsc --noEmit` + `npm run build`
  + manual smoke.

## Background facts (verified against the code)

- `globals.css` already defines every token the prototype CSS references
  (`--primary`, `--primary-foreground`, `--card`, `--border`, `--muted`,
  `--muted-foreground`, `--foreground`, `--background`, `--ring`, `--destructive`,
  `--accent`, `--radius`, plus `--sidebar*`), and a `.dark` block. The shell CSS
  drops in without new tokens.
- `useTerminals()` returns `{ terminals, loading, createTerminal, deleteTerminal }`;
  `Terminal` has `role` ('master'|'slave') and `status`.
- `useLinks()` returns `{ links, loading, refresh, createLink, updateLink,
  toggleLink, deleteLink }`; `Link` has `enabled` (0|1).
- `LinksTable` takes `onSelectLink: (linkId: number) => void` and is self-contained
  (uses its own hooks). `TerminalsTable` is self-contained.
- Current `app/page.tsx` renders TerminalsTable + LinksTable + MappingsPanel +
  Toaster in one `<main className="container mx-auto py-8 space-y-8 px-4">`.
- Existing pages `alerts`, `settings`, `settings/telegram` each wrap content in
  `<main className="container mx-auto py-8 …">` and render their own `<Toaster/>`.
- Status sets (from the prototype, consistent with the DB CHECK): online =
  `Active | Connected | Syncing`; issues = `Disconnected | Error`.

## Navigation & routes

Sidebar items (active state via `usePathname`):

| Label       | Route                  | Screen                                  |
|-------------|------------------------|-----------------------------------------|
| Dashboard   | `/`                    | MetricStrip + setup-flow cards          |
| Terminals   | `/terminals`           | `<TerminalsTable/>`                      |
| Copy links  | `/links`               | `<LinksTable/>` + `<MappingsPanel/>`     |
| Alerts      | `/alerts`              | existing alerts page (adapted)          |
| Settings    | `/settings`            | existing settings page (adapted)        |
| Telegram    | `/settings/telegram`   | existing telegram page (adapted)        |

Mappings are reached from the Links table (`onSelectLink` opens `MappingsPanel`) —
no separate Mappings route. No Dialogs screen.

## Architecture

Shell lives in the root `layout.tsx`; route pages render inside `.screen`:

```
layout.tsx (server component)
└─ <div className="app-root" data-variant="4">     // V4 hard-coded, no switcher
   ├─ <AppSidebar/>                                 // client: usePathname + next/link
   ├─ <main className="main">
   │   ├─ <Topbar/>                                 // client: title/subtitle by pathname
   │   └─ <div className="screen">{children}</div>
   │  </main>
   └─ <Toaster/>                                    // single global instance
```

### New components

- **`components/shell/icons.tsx`** — an `Icon` component rendering inline SVG by
  `name`: `dashboard`, `terminals`, `links` (from the prototype) plus `alerts`
  (bell), `settings` (gear), `telegram` (send). One `<svg>` wrapper, `name`-keyed
  path map.
- **`components/shell/app-sidebar.tsx`** (`"use client"`) — brand ("TC" mark +
  "Trade Copier"), a nav list built from a `NAV` array of `{ href, label, icon }`,
  active item when `usePathname()` matches (`/` exact; others by prefix), each item
  a `next/link`. Footer: a live dot + "API · live".
- **`components/shell/topbar.tsx`** (`"use client"`) — looks up
  `[title, subtitle]` from a `pathname → tuple` map and renders the topbar header.
  No controls (switcher/theme dropped).
- **`components/dashboard/metric-strip.tsx`** (`"use client"`) — `useTerminals()` +
  `useLinks()` → four `.metric` cards: Terminals (`{online} online`), Masters
  (`broadcasting`), Copy links (`{enabled} enabled`), Issues (`need attention`).
- **`components/dashboard/setup-flow.tsx`** (`"use client"`) — three `.hub-card`
  links: Terminals → `/terminals`, Copy links → `/links`, Mappings → `/links`.
  The Terminals card shows an alert accent + issue count when issues > 0. Uses
  `useTerminals()` + `useLinks()` for the footer stats.

### New route pages

- **`app/terminals/page.tsx`** — renders `<TerminalsTable/>`.
- **`app/links/page.tsx`** (`"use client"`) — holds `selectedLinkId` state, renders
  `<LinksTable onSelectLink={setSelectedLinkId}/>` and the `<MappingsPanel/>` when a
  link is selected (the logic currently in `page.tsx`).

### Modified files

- **`app/layout.tsx`** — replace the top-nav with the shell tree above; keep fonts;
  add the single global `<Toaster/>`.
- **`app/page.tsx`** — becomes the Dashboard: `<MetricStrip/>` + a "Setup flow"
  label + `<SetupFlow/>`.
- **`app/globals.css`** — append a shell CSS block reproducing V4: `.app-root`
  (grid), `.sidebar` + nav, `.main`, `.topbar`, `.screen`, `.metric-strip`/`.metric`,
  `.panel*`, `.dash-*`/`.hub-card*`, `.link-grid`/`.link-card`, `.mono`. Shell
  variables (`--sb-w`, `--pad`, `--content-bg`, `--panel-bg`, `--panel-border`,
  `--panel-radius`, `--panel-shadow`, `--metric-border`, `--sb-bg`, `--sb-fg`,
  `--sb-muted`, `--sb-hover`, `--sb-active-bg`, `--sb-active-fg`) are defined on
  `.app-root` with the prototype's V4 values (sidebar uses `--primary` /
  `--primary-foreground`; content-bg uses `--muted`; `--sb-w: 218px`; `--pad: 16px`).
- **`app/alerts/page.tsx`**, **`app/settings/page.tsx`**,
  **`app/settings/telegram/page.tsx`** — replace each `<main className="container
  mx-auto py-8 …">` wrapper with a `<div className="space-y-…">` (the `.screen`
  already supplies padding/centering and the shell owns the single `<main>`), and
  remove each page's local `<Toaster/>` (now global in layout).

## Data flow

MetricStrip and SetupFlow read live data through the existing `useTerminals()` and
`useLinks()` hooks — no mock, no `window.__tcDb`. Everything goes to
`http://localhost:8000/api` like the rest of the app.

## CSS fidelity note

The prototype's exact CSS values cannot be byte-extracted from Drive reliably, so
the shell CSS is re-authored from the V4 structure and known token usage. It
reproduces the V4 look; minor spacing/size values may be tuned against the
prototype afterward.

## Testing

- `cd web/frontend && npx tsc --noEmit` — no type errors.
- `cd web/frontend && npm run build` — production build succeeds.
- Manual smoke: sidebar navigates between all six routes with correct active state;
  dashboard metrics reflect real data; `/links` opens the mappings panel; existing
  alerts/settings/telegram render inside the shell with no duplicate `<main>` or
  doubled toasts.

## Risks / notes

- Nested `<main>` and duplicate `<Toaster/>` are the main integration hazards —
  explicitly handled by adapting the three existing pages.
- `next/link` prefetch + `usePathname` active state must treat `/` as exact match so
  it isn't always "active".
- Sidebar is fixed-width (no mobile collapse in this iteration) — matches the
  prototype; responsive behavior is out of scope.
