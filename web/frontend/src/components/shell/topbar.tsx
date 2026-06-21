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
