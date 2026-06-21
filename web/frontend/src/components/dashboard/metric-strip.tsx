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
