# Frontend Shell V4 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the prototyped V4 admin shell (sidebar + topbar + dashboard) into the real Next.js app, wrapping the existing tables/dialogs and routing each screen.

**Architecture:** A root `layout.tsx` renders an `app-root` grid (sidebar + main(topbar + `.screen` children)) with one global Toaster; each screen becomes an App Router page; the home page becomes a Dashboard backed by the real `useTerminals`/`useLinks` hooks. Shell CSS is added to `globals.css` using the existing design-system tokens.

**Tech Stack:** Next.js (App Router) + React + TypeScript + Tailwind v4 / shadcn-ui tokens + sonner.

## Global Constraints

- Frontend only — no changes to Hub, EAs, FastAPI, or the DB.
- Fetch calls live inside hooks calling `fetchApi` directly; do not add wrappers to `lib/api.ts`.
- TypeScript: components/interfaces `PascalCase`, hooks `useCamelCase`.
- Use existing design-system tokens (`--primary`, `--card`, `--border`, `--muted`, `--muted-foreground`, `--foreground`, `--ring`, `--destructive`, `--radius`); add no new tokens.
- Exactly ONE `<main>` element (in `layout.tsx`) and ONE `<Toaster/>` (in `layout.tsx`).
- Online statuses: `Active | Connected | Syncing`. Issue statuses: `Disconnected | Error`.
- Sidebar V4 values: `--sb-w: 218px`, `--pad: 16px`; sidebar uses `--primary`/`--primary-foreground`; content background uses `--muted`.
- Active nav: `/` and `/settings` match exactly; other routes match by prefix.
- Drop all prototype debug chrome (V1–V4 switcher, theme toggle, Dialogs screen, mock, localStorage).
- Verification per task: `cd web/frontend && npx tsc --noEmit` (no unit tests exist). Final build in the last task.
- Work on branch `feat/frontend-shell-v4` (start from `main`).

---

## Setup (do once before Task 1)

- [ ] **Create the feature branch**

```bash
git checkout -b feat/frontend-shell-v4
```

- [ ] **Commit the already-written spec + this plan**

```bash
git add docs/superpowers/specs/2026-06-21-frontend-shell-v4-design.md \
        docs/superpowers/plans/2026-06-21-frontend-shell-v4.md
git commit -m "docs: spec + plan for frontend shell V4"
```

---

## Task 1: Shell CSS + icons

Foundational primitives every other task uses: the CSS classes and the SVG icon set.

**Files:**
- Modify: `web/frontend/src/app/globals.css` (append shell block at end)
- Create: `web/frontend/src/components/shell/icons.tsx`

**Interfaces:**
- Produces: CSS classes `app-root`, `sidebar`, `sidebar-brand`, `brand-mark`, `brand-name`, `nav`, `nav-item`, `sidebar-foot`, `dot`, `dot-live`, `main`, `topbar`, `topbar-title`, `topbar-sub`, `screen`, `metric-strip`, `metric`, `metric-label`, `metric-value`, `metric-sub`, `dash-section-label`, `dash-grid`, `hub-card`, `hub-card-alert`, `hub-card-top`, `hub-step`, `hub-card-title`, `hub-card-desc`, `hub-card-footer`, `hub-card-stat`, `hub-card-stat-alert`, `hub-cta`.
- Produces: `Icon` component `({ name }: { name: IconName }) => JSX`, and `type IconName = "dashboard" | "terminals" | "links" | "mappings" | "alerts" | "settings" | "telegram"`.

- [ ] **Step 1: Append the shell CSS block to `globals.css`**

Append to the end of `web/frontend/src/app/globals.css`:

```css

/* ---------- V4 shell ---------- */
.app-root {
  --sb-w: 218px;
  --pad: 16px;
  --sb-bg: var(--primary);
  --sb-fg: var(--primary-foreground);
  --sb-muted: color-mix(in oklch, var(--primary-foreground) 55%, transparent);
  --sb-hover: color-mix(in oklch, var(--primary-foreground) 10%, transparent);
  --sb-active-bg: color-mix(in oklch, var(--primary-foreground) 18%, transparent);
  --sb-active-fg: var(--primary-foreground);
  --content-bg: var(--muted);
  --panel-bg: var(--card);

  display: grid;
  grid-template-columns: var(--sb-w) 1fr;
  height: 100vh;
  width: 100vw;
  overflow: hidden;
}

.sidebar {
  background: var(--sb-bg);
  color: var(--sb-fg);
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 18px 14px;
  min-width: 0;
}
.sidebar-brand { display: flex; align-items: center; gap: 10px; padding: 6px 8px 20px; }
.brand-mark {
  display: grid; place-items: center; width: 30px; height: 30px; border-radius: 8px;
  background: var(--sb-active-bg); color: var(--sb-active-fg); font-weight: 700; font-size: 12px;
}
.brand-name { font-weight: 600; font-size: 15px; color: var(--sb-fg); letter-spacing: -0.01em; }
.nav { display: flex; flex-direction: column; gap: 2px; margin-top: 2px; }
.nav-item {
  display: flex; align-items: center; gap: 11px; padding: 9px 10px; border: 0; background: transparent;
  color: var(--sb-muted); font: inherit; font-size: 14px; font-weight: 500; border-radius: 8px;
  cursor: pointer; text-align: left; width: 100%; text-decoration: none;
  transition: background .12s, color .12s;
}
.nav-item:hover { background: var(--sb-hover); color: var(--sb-fg); }
.nav-item.active { background: var(--sb-active-bg); color: var(--sb-active-fg); font-weight: 600; }
.nav-item svg { flex: none; opacity: .92; }
.sidebar-foot { margin-top: auto; display: flex; align-items: center; gap: 8px; padding: 10px 8px; font-size: 12px; color: var(--sb-muted); }
.dot { width: 7px; height: 7px; border-radius: 50%; }
.dot-live { background: oklch(0.72 0.17 150); }

.main { min-width: 0; height: 100vh; overflow: auto; background: var(--content-bg); }
.topbar {
  position: sticky; top: 0; z-index: 5; display: flex; align-items: flex-end; justify-content: space-between;
  gap: 16px; padding: var(--pad); padding-bottom: 12px; background: var(--content-bg); border-bottom: 1px solid var(--border);
}
.topbar-title { margin: 0; font-size: 17px; font-weight: 650; letter-spacing: -0.015em; }
.topbar-sub { margin: 3px 0 0; font-size: 13px; color: var(--muted-foreground); }

.screen { display: flex; flex-direction: column; gap: 16px; padding: var(--pad); max-width: 1240px; }

.metric-strip {
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 0;
  background: var(--card); border: 1px solid var(--border); border-radius: calc(var(--radius) - 2px); overflow: hidden;
}
.metric { border-right: 1px solid var(--border); padding: 14px 18px; }
.metric:last-child { border-right: 0; }
.metric-label { font-size: 11px; font-weight: 600; color: var(--muted-foreground); text-transform: uppercase; letter-spacing: .05em; }
.metric-value { font-size: 23px; font-weight: 680; letter-spacing: -0.02em; margin-top: 7px; line-height: 1; }
.metric-sub { font-size: 12px; color: var(--muted-foreground); margin-top: 7px; }

.dash-section-label { font-size: 12px; font-weight: 600; color: var(--muted-foreground); text-transform: uppercase; letter-spacing: .05em; padding-bottom: 4px; }
.dash-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 14px; grid-auto-rows: 1fr; }
.hub-card {
  display: flex; flex-direction: column; border: 1px solid var(--border); background: var(--card); color: var(--foreground);
  border-radius: var(--radius); padding: 20px; cursor: pointer; text-align: left; width: 100%; min-height: 140px; gap: 10px;
  text-decoration: none; transition: border-color .14s, box-shadow .14s;
}
.hub-card:hover { border-color: var(--ring); box-shadow: 0 2px 10px rgba(0,0,0,.07); }
.hub-card-alert { border-left: 3px solid var(--destructive); }
.hub-card-top { display: flex; align-items: center; justify-content: space-between; }
.hub-step { font-size: 11px; font-weight: 700; color: var(--muted-foreground); background: var(--muted); border-radius: 50%; width: 22px; height: 22px; display: grid; place-items: center; flex: none; }
.hub-card-title { font-size: 15px; font-weight: 650; letter-spacing: -0.01em; margin-top: 2px; }
.hub-card-desc { font-size: 13px; color: var(--muted-foreground); line-height: 1.45; flex: 1; }
.hub-card-footer { display: flex; align-items: center; justify-content: space-between; margin-top: auto; }
.hub-card-stat { font-size: 12px; color: var(--muted-foreground); font-variant-numeric: tabular-nums; }
.hub-card-stat-alert { color: var(--destructive); font-weight: 600; }
.hub-cta { font-size: 13px; font-weight: 600; color: var(--muted-foreground); flex: none; }
.hub-card:hover .hub-cta { color: var(--foreground); }
```

- [ ] **Step 2: Create `components/shell/icons.tsx`**

```tsx
import type { ReactNode } from "react";

export type IconName =
  | "dashboard"
  | "terminals"
  | "links"
  | "mappings"
  | "alerts"
  | "settings"
  | "telegram";

const PATHS: Record<IconName, ReactNode> = {
  dashboard: (
    <>
      <rect x="3" y="3" width="7" height="9" rx="1" />
      <rect x="14" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="12" width="7" height="9" rx="1" />
      <rect x="3" y="16" width="7" height="5" rx="1" />
    </>
  ),
  terminals: (
    <>
      <rect x="3" y="4" width="18" height="12" rx="2" />
      <path d="M8 20h8M12 16v4" />
    </>
  ),
  links: (
    <>
      <path d="M9 12a4 4 0 0 1 4-4h2a4 4 0 0 1 0 8h-1" />
      <path d="M15 12a4 4 0 0 1-4 4H9a4 4 0 0 1 0-8h1" />
    </>
  ),
  mappings: (
    <>
      <path d="M4 7h11l-3-3M4 7l3 3" />
      <path d="M20 17H9l3 3M20 17l-3-3" />
    </>
  ),
  alerts: (
    <>
      <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9" />
      <path d="M13.73 21a2 2 0 0 1-3.46 0" />
    </>
  ),
  settings: (
    <>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </>
  ),
  telegram: (
    <>
      <path d="M22 2 11 13" />
      <path d="M22 2 15 22l-4-9-9-4 20-7z" />
    </>
  ),
};

export function Icon({ name }: { name: IconName }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      width="18"
      height="18"
    >
      {PATHS[name]}
    </svg>
  );
}
```

- [ ] **Step 3: Type-check**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/app/globals.css web/frontend/src/components/shell/icons.tsx
git commit -m "feat(ui): V4 shell CSS + icon set"
```

---

## Task 2: Sidebar + Topbar

The shell chrome: navigation sidebar and the title/subtitle topbar.

**Files:**
- Create: `web/frontend/src/components/shell/app-sidebar.tsx`
- Create: `web/frontend/src/components/shell/topbar.tsx`

**Interfaces:**
- Consumes: `Icon`, `IconName` from `@/components/shell/icons`; CSS classes from Task 1.
- Produces: `AppSidebar` component (no props); `Topbar` component (no props). Both `"use client"`.

- [ ] **Step 1: Create `components/shell/app-sidebar.tsx`**

```tsx
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon, IconName } from "@/components/shell/icons";

const NAV: { href: string; label: string; icon: IconName }[] = [
  { href: "/", label: "Dashboard", icon: "dashboard" },
  { href: "/terminals", label: "Terminals", icon: "terminals" },
  { href: "/links", label: "Copy links", icon: "links" },
  { href: "/alerts", label: "Alerts", icon: "alerts" },
  { href: "/settings", label: "Settings", icon: "settings" },
  { href: "/settings/telegram", label: "Telegram", icon: "telegram" },
];

function isActive(pathname: string, href: string): boolean {
  if (href === "/" || href === "/settings") return pathname === href;
  return pathname === href || pathname.startsWith(href + "/");
}

export function AppSidebar() {
  const pathname = usePathname();
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="brand-mark">TC</span>
        <span className="brand-name">Trade Copier</span>
      </div>
      <nav className="nav">
        {NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            className={"nav-item" + (isActive(pathname, n.href) ? " active" : "")}
          >
            <Icon name={n.icon} />
            <span>{n.label}</span>
          </Link>
        ))}
      </nav>
      <div className="sidebar-foot">
        <span className="dot dot-live" /> API · live
      </div>
    </aside>
  );
}
```

- [ ] **Step 2: Create `components/shell/topbar.tsx`**

```tsx
"use client";

import { usePathname } from "next/navigation";

const TITLES: { match: (p: string) => boolean; title: string; sub: string }[] = [
  { match: (p) => p === "/", title: "Dashboard", sub: "Live status across all terminals and copy links" },
  { match: (p) => p.startsWith("/terminals"), title: "Terminals", sub: "MT5 terminals connected to the copier" },
  { match: (p) => p.startsWith("/links"), title: "Copy links", sub: "Master → slave copy relationships" },
  { match: (p) => p.startsWith("/alerts"), title: "Alerts", sub: "Telegram alert history" },
  { match: (p) => p === "/settings/telegram", title: "Telegram", sub: "Telegram bot & alert settings" },
  { match: (p) => p.startsWith("/settings"), title: "Settings", sub: "Hub configuration" },
];

export function Topbar() {
  const pathname = usePathname();
  const entry =
    TITLES.find((t) => t.match(pathname)) ?? { title: "Trade Copier", sub: "" };
  return (
    <header className="topbar">
      <div>
        <h1 className="topbar-title">{entry.title}</h1>
        {entry.sub && <p className="topbar-sub">{entry.sub}</p>}
      </div>
    </header>
  );
}
```

Note: the `/settings/telegram` entry precedes the `/settings` entry so `find` matches the more specific route first.

- [ ] **Step 3: Type-check**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/components/shell/app-sidebar.tsx web/frontend/src/components/shell/topbar.tsx
git commit -m "feat(ui): shell sidebar + topbar"
```

---

## Task 3: Dashboard screen

The home page becomes a Dashboard: a metric strip + setup-flow cards, both backed by real hooks.

**Files:**
- Create: `web/frontend/src/components/dashboard/metric-strip.tsx`
- Create: `web/frontend/src/components/dashboard/setup-flow.tsx`
- Modify: `web/frontend/src/app/page.tsx` (full replacement)

**Interfaces:**
- Consumes: `useTerminals()` → `{ terminals }` (`Terminal.role`, `.status`); `useLinks()` → `{ links }` (`Link.enabled`); `Icon`/`IconName`; CSS classes from Task 1.
- Produces: `MetricStrip` (no props, client); `SetupFlow` (no props, client); default-export `DashboardPage`.

- [ ] **Step 1: Create `components/dashboard/metric-strip.tsx`**

```tsx
"use client";

import { useTerminals } from "@/hooks/use-terminals";
import { useLinks } from "@/hooks/use-links";

const ONLINE = ["Active", "Connected", "Syncing"];
const ISSUE = ["Disconnected", "Error"];

export function MetricStrip() {
  const { terminals } = useTerminals();
  const { links } = useLinks();

  const online = terminals.filter((t) => ONLINE.includes(t.status)).length;
  const masters = terminals.filter((t) => t.role === "master").length;
  const enabled = links.filter((l) => l.enabled).length;
  const issues = terminals.filter((t) => ISSUE.includes(t.status)).length;

  const metrics = [
    { label: "Terminals", value: terminals.length, sub: `${online} online` },
    { label: "Masters", value: masters, sub: "broadcasting" },
    { label: "Copy links", value: links.length, sub: `${enabled} enabled` },
    { label: "Issues", value: issues, sub: "need attention" },
  ];

  return (
    <div className="metric-strip">
      {metrics.map((m) => (
        <div className="metric" key={m.label}>
          <div className="metric-label">{m.label}</div>
          <div className="metric-value">{m.value}</div>
          <div className="metric-sub">{m.sub}</div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Create `components/dashboard/setup-flow.tsx`**

```tsx
"use client";

import Link from "next/link";
import { useTerminals } from "@/hooks/use-terminals";
import { useLinks } from "@/hooks/use-links";
import { Icon, IconName } from "@/components/shell/icons";

const ONLINE = ["Active", "Connected", "Syncing"];
const ISSUE = ["Disconnected", "Error"];

export function SetupFlow() {
  const { terminals } = useTerminals();
  const { links } = useLinks();

  const online = terminals.filter((t) => ONLINE.includes(t.status)).length;
  const issues = terminals.filter((t) => ISSUE.includes(t.status)).length;
  const enabled = links.filter((l) => l.enabled).length;

  const cards: {
    step: string;
    href: string;
    icon: IconName;
    label: string;
    desc: string;
    stat: string;
    alertStat: string | null;
    alert: boolean;
  }[] = [
    {
      step: "1",
      href: "/terminals",
      icon: "terminals",
      label: "Terminals",
      desc: "Connect and monitor your MT5 master & slave accounts",
      stat: `${terminals.length} connected · ${online} online`,
      alertStat: issues > 0 ? `${issues} issue${issues > 1 ? "s" : ""}` : null,
      alert: issues > 0,
    },
    {
      step: "2",
      href: "/links",
      icon: "links",
      label: "Copy links",
      desc: "Create master → slave copy relationships with lot rules",
      stat: `${links.length} links · ${enabled} enabled`,
      alertStat: null,
      alert: false,
    },
    {
      step: "3",
      href: "/links",
      icon: "mappings",
      label: "Mappings",
      desc: "Map symbols and magic numbers per copy link",
      stat: "Open a link to manage mappings",
      alertStat: null,
      alert: false,
    },
  ];

  return (
    <>
      <div className="dash-section-label">Setup flow</div>
      <div className="dash-grid">
        {cards.map((c) => (
          <Link
            key={c.label}
            href={c.href}
            className={"hub-card" + (c.alert ? " hub-card-alert" : "")}
          >
            <div className="hub-card-top">
              <Icon name={c.icon} />
              <span className="hub-step">{c.step}</span>
            </div>
            <div className="hub-card-title">{c.label}</div>
            <div className="hub-card-desc">{c.desc}</div>
            <div className="hub-card-footer">
              <span className="hub-card-stat">
                {c.stat}
                {c.alertStat && (
                  <span className="hub-card-stat-alert"> · {c.alertStat}</span>
                )}
              </span>
              <span className="hub-cta">Open →</span>
            </div>
          </Link>
        ))}
      </div>
    </>
  );
}
```

- [ ] **Step 3: Replace `app/page.tsx`**

```tsx
import { MetricStrip } from "@/components/dashboard/metric-strip";
import { SetupFlow } from "@/components/dashboard/setup-flow";

export default function DashboardPage() {
  return (
    <>
      <MetricStrip />
      <SetupFlow />
    </>
  );
}
```

- [ ] **Step 4: Type-check**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/dashboard/metric-strip.tsx web/frontend/src/components/dashboard/setup-flow.tsx web/frontend/src/app/page.tsx
git commit -m "feat(ui): dashboard screen (metric strip + setup flow)"
```

---

## Task 4: Terminals + Links route pages

Move the terminals table and the links table (+ mappings panel) into their own routes.

**Files:**
- Create: `web/frontend/src/app/terminals/page.tsx`
- Create: `web/frontend/src/app/links/page.tsx`

**Interfaces:**
- Consumes: `TerminalsTable` from `@/components/terminals-table`; `LinksTable` (prop `onSelectLink: (linkId: number) => void`) from `@/components/links-table`; `MappingsPanel` (props `linkId: number`, `open: boolean`, `onOpenChange: (open: boolean) => void`) from `@/components/mappings-panel`.
- Produces: default-export pages at `/terminals` and `/links`.

- [ ] **Step 1: Create `app/terminals/page.tsx`**

```tsx
import { TerminalsTable } from "@/components/terminals-table";

export default function TerminalsPage() {
  return <TerminalsTable />;
}
```

- [ ] **Step 2: Create `app/links/page.tsx`**

```tsx
"use client";

import { useState } from "react";
import { LinksTable } from "@/components/links-table";
import { MappingsPanel } from "@/components/mappings-panel";

export default function LinksPage() {
  const [selectedLinkId, setSelectedLinkId] = useState<number | null>(null);

  return (
    <>
      <LinksTable onSelectLink={setSelectedLinkId} />
      {selectedLinkId && (
        <MappingsPanel
          linkId={selectedLinkId}
          open={true}
          onOpenChange={(open) => {
            if (!open) setSelectedLinkId(null);
          }}
        />
      )}
    </>
  );
}
```

- [ ] **Step 3: Type-check**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/app/terminals/page.tsx web/frontend/src/app/links/page.tsx
git commit -m "feat(ui): terminals + links route pages"
```

---

## Task 5: Integrate shell into layout + adapt existing pages

Swap the top-nav layout for the shell and adapt the three existing pages so there is exactly one `<main>` and one `<Toaster/>`. These land together to avoid a nested-`<main>` / double-toaster intermediate state.

**Files:**
- Modify: `web/frontend/src/app/layout.tsx` (full replacement)
- Modify: `web/frontend/src/app/alerts/page.tsx` (wrapper + toaster)
- Modify: `web/frontend/src/app/settings/page.tsx` (wrappers + toaster)
- Modify: `web/frontend/src/app/settings/telegram/page.tsx` (wrappers + toaster)

**Interfaces:**
- Consumes: `AppSidebar`, `Topbar` from `@/components/shell/*`; `Toaster` from `@/components/ui/sonner`.
- Produces: the shell layout; existing pages now render inside `.screen` with no own `<main>`/`<Toaster/>`.

- [ ] **Step 1: Replace `app/layout.tsx`**

```tsx
import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AppSidebar } from "@/components/shell/app-sidebar";
import { Topbar } from "@/components/shell/topbar";
import { Toaster } from "@/components/ui/sonner";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Trade Copier",
  description: "MT5 Trade Copier Terminal Management",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <div className="app-root" data-variant="4">
          <AppSidebar />
          <main className="main">
            <Topbar />
            <div className="screen">{children}</div>
          </main>
        </div>
        <Toaster />
      </body>
    </html>
  );
}
```

- [ ] **Step 2: Adapt `app/alerts/page.tsx`**

Remove the Toaster import line:

```tsx
import { Toaster } from "@/components/ui/sonner";
```

Change the opening wrapper from:

```tsx
    <main className="container mx-auto py-8 space-y-6 px-4">
```
to:
```tsx
    <div className="space-y-6">
```

Remove the line `      <Toaster />` near the end, and change the closing `</main>` to `</div>`.

- [ ] **Step 3: Adapt `app/settings/page.tsx`**

Remove the Toaster import line:

```tsx
import { Toaster } from "@/components/ui/sonner";
```

In the loading branch, change:

```tsx
      <main className="container mx-auto py-8 px-4">
        <h1 className="text-2xl font-bold mb-8">Settings</h1>
        <p className="text-muted-foreground">Loading...</p>
        <Toaster />
      </main>
```
to:
```tsx
      <div>
        <h1 className="text-2xl font-bold mb-8">Settings</h1>
        <p className="text-muted-foreground">Loading...</p>
      </div>
```

In the main return, change the opening `<main className="container mx-auto py-8 space-y-8 px-4">` to `<div className="space-y-8">`, remove the `      <Toaster />` line before the close, and change the closing `</main>` to `</div>`.

- [ ] **Step 4: Adapt `app/settings/telegram/page.tsx`**

Remove the Toaster import line:

```tsx
import { Toaster } from "@/components/ui/sonner";
```

In the loading branch, change:

```tsx
      <main className="container mx-auto py-8 px-4">
        <h1 className="text-2xl font-bold mb-8">Telegram</h1>
        <p className="text-muted-foreground">Loading…</p>
        <Toaster />
      </main>
```
to:
```tsx
      <div>
        <h1 className="text-2xl font-bold mb-8">Telegram</h1>
        <p className="text-muted-foreground">Loading…</p>
      </div>
```

In the main return, change the opening `<main className="container mx-auto py-8 space-y-8 px-4">` to `<div className="space-y-8">`, remove the `      <Toaster />` line before the close, and change the closing `</main>` to `</div>`.

- [ ] **Step 5: Type-check**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/app/layout.tsx web/frontend/src/app/alerts/page.tsx web/frontend/src/app/settings/page.tsx web/frontend/src/app/settings/telegram/page.tsx
git commit -m "feat(ui): wire shell layout + adapt existing pages into screen"
```

---

## Task 6: Full verification

**Files:** none (verification only).

- [ ] **Step 1: Type-check the whole frontend**

Run: `cd web/frontend && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 2: Production build**

Run: `cd web/frontend && npm run build`
Expected: build succeeds; routes `/`, `/terminals`, `/links`, `/alerts`, `/settings`, `/settings/telegram` all compile.

- [ ] **Step 3: Manual smoke (recommended)**

Start backend + frontend and verify:
- Sidebar navigates between all six routes; active item highlights correctly (Dashboard only on `/`, Settings not highlighted on `/settings/telegram`).
- Dashboard metrics + setup-flow reflect real data; the Terminals card shows the alert accent when a terminal is Disconnected/Error.
- `/links` opens the mappings panel on row click.
- `/alerts`, `/settings`, `/settings/telegram` render inside the shell with a single top bar and a single toaster (toasts fire once).

```bash
uv run uvicorn web.api.main:app --port 8000   # terminal 1
cd web/frontend && npm run dev                  # terminal 2 (http://localhost:3000)
```

- [ ] **Step 4: Confirm clean tree**

```bash
git status   # all work committed across Tasks 1-5
```

---

## Self-Review

**Spec coverage:**
- Shell in layout (sidebar + topbar + screen + single Toaster) → Task 5 (+ Task 2 components). ✅
- Dashboard (metric strip + setup-flow, real hooks) → Task 3. ✅
- Routes `/terminals`, `/links` (+ MappingsPanel) → Task 4. ✅
- Existing `/alerts`, `/settings`, `/settings/telegram` adapted (no nested main, single toaster) → Task 5. ✅
- Shell CSS on existing tokens + V4 values → Task 1. ✅
- Icons incl. alerts/settings/telegram → Task 1. ✅
- Active nav: `/` and `/settings` exact, others prefix; telegram before settings in topbar → Task 2. ✅
- Drop debug chrome / mock / localStorage → not ported (only the real pieces are built). ✅
- Verification tsc + build + manual → Task 6. ✅

**Placeholder scan:** no TBD/TODO; every code step contains complete code. The three page adaptations in Task 5 are described as exact string replacements against the current files (verified against their current content).

**Type consistency:** `IconName` (Task 1) is the same union consumed in Tasks 2 & 3. `AppSidebar`/`Topbar` (Task 2) are consumed by name in Task 5. `MetricStrip`/`SetupFlow` (Task 3) consumed by `page.tsx` in Task 3. `LinksTable` `onSelectLink` and `MappingsPanel` props (Task 4) match the existing components. Online/issue status arrays are identical across metric-strip and setup-flow.
