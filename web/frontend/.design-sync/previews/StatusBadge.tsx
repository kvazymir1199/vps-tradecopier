import { StatusBadge } from "frontend";

const row: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" };

export function AllStatuses() {
  const statuses = ["Active", "Starting", "Connected", "Syncing", "Paused", "Disconnected", "Error"];
  return (
    <div style={row}>
      {statuses.map((s) => (
        <StatusBadge key={s} status={s} />
      ))}
    </div>
  );
}
