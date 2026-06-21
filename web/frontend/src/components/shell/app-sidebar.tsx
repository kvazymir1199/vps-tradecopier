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
