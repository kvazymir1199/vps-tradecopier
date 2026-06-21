import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  Button,
  Input,
} from "frontend";

export function AddLink() {
  return (
    <Dialog defaultOpen>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add copy link</DialogTitle>
          <DialogDescription>
            Connect a master terminal to a slave so trades are copied automatically.
          </DialogDescription>
        </DialogHeader>
        <div style={{ display: "grid", gap: 12, padding: "8px 0" }}>
          <Input placeholder="Master terminal ID" defaultValue="MT5-Master-01" />
          <Input placeholder="Slave terminal ID" defaultValue="MT5-Slave-A" />
        </div>
        <DialogFooter>
          <Button variant="outline">Cancel</Button>
          <Button>Create link</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
