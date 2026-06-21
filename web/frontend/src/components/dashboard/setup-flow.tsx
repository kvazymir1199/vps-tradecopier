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
