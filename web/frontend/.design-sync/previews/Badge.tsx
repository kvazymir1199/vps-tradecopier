import { Badge } from "frontend";

const row: React.CSSProperties = { display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" };

export function Variants() {
  return (
    <div style={row}>
      <Badge>Active</Badge>
      <Badge variant="secondary">Pending</Badge>
      <Badge variant="destructive">Error</Badge>
      <Badge variant="outline">Idle</Badge>
      <Badge variant="ghost">Muted</Badge>
      <Badge variant="link">Details</Badge>
    </div>
  );
}

export function Counts() {
  return (
    <div style={row}>
      <Badge>3 links</Badge>
      <Badge variant="secondary">12 mappings</Badge>
      <Badge variant="destructive">2 alerts</Badge>
      <Badge variant="outline">v0.1.0</Badge>
    </div>
  );
}
