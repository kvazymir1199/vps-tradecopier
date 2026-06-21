import { Switch } from "frontend";

const label: React.CSSProperties = { display: "flex", gap: 8, alignItems: "center", fontSize: 14 };
const row: React.CSSProperties = { display: "flex", gap: 20, alignItems: "center", flexWrap: "wrap" };

export function States() {
  return (
    <div style={row}>
      <label style={label}>
        <Switch defaultChecked /> Link enabled
      </label>
      <label style={label}>
        <Switch /> Link paused
      </label>
      <label style={{ ...label, opacity: 0.6 }}>
        <Switch disabled defaultChecked /> Locked
      </label>
    </div>
  );
}

export function Sizes() {
  return (
    <div style={row}>
      <label style={label}>
        <Switch size="sm" defaultChecked /> Small
      </label>
      <label style={label}>
        <Switch size="default" defaultChecked /> Default
      </label>
    </div>
  );
}
