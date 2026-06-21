import { Input } from "frontend";

const col: React.CSSProperties = { display: "grid", gap: 12, maxWidth: 320 };

export function Default() {
  return (
    <div style={col}>
      <Input placeholder="Terminal ID (e.g. master_1)" />
    </div>
  );
}

export function Filled() {
  return (
    <div style={col}>
      <Input defaultValue="MT5-Master-01" />
    </div>
  );
}

export function Types() {
  return (
    <div style={col}>
      <Input type="number" placeholder="Lot value" defaultValue="1.5" step="0.01" />
      <Input type="password" defaultValue="bot-token-secret" />
    </div>
  );
}

export function Disabled() {
  return (
    <div style={col}>
      <Input defaultValue="MT5-Master-01" disabled />
    </div>
  );
}
