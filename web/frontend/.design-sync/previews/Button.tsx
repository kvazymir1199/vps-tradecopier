import { Button } from "frontend";
import { Plus, Trash2, RefreshCw } from "lucide-react";

const row: React.CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: 12,
  alignItems: "center",
};

export function Variants() {
  return (
    <div style={row}>
      <Button>Add Link</Button>
      <Button variant="secondary">Edit</Button>
      <Button variant="outline">Cancel</Button>
      <Button variant="destructive">Delete</Button>
      <Button variant="ghost">Refresh</Button>
      <Button variant="link">View details</Button>
    </div>
  );
}

export function Sizes() {
  return (
    <div style={row}>
      <Button size="sm">Small</Button>
      <Button size="default">Default</Button>
      <Button size="lg">Large</Button>
      <Button size="icon" aria-label="Add">
        <Plus />
      </Button>
    </div>
  );
}

export function WithIcons() {
  return (
    <div style={row}>
      <Button>
        <Plus /> New Terminal
      </Button>
      <Button variant="outline">
        <RefreshCw /> Sync
      </Button>
      <Button variant="destructive">
        <Trash2 /> Remove
      </Button>
    </div>
  );
}

export function Disabled() {
  return (
    <div style={row}>
      <Button disabled>Saving…</Button>
      <Button variant="outline" disabled>
        Disabled
      </Button>
    </div>
  );
}
