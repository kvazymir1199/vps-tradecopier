"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface AddTerminalDialogProps {
  onSubmit: (terminalId: string, role: "master" | "slave") => Promise<void>;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddTerminalDialog({ onSubmit, open, onOpenChange }: AddTerminalDialogProps) {
  const [terminalId, setTerminalId] = useState("");
  const [role, setRole] = useState<"master" | "slave">("master");
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await onSubmit(terminalId.trim(), role);
      setTerminalId("");
      setRole("master");
      onOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Terminal</DialogTitle>
          <DialogDescription>
            Manually register a terminal so the Hub creates its named pipes on next
            restart. It stays Disconnected until its EA connects.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <label className="text-sm font-medium">Terminal ID</label>
            <Input
              type="text"
              placeholder="e.g. master_1"
              value={terminalId}
              onChange={(e) => setTerminalId(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">Role</label>
            <Select value={role} onValueChange={(v) => setRole(v as "master" | "slave")}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="master">Master</SelectItem>
                <SelectItem value="slave">Slave</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!terminalId.trim() || submitting}>
            {submitting ? "Adding..." : "Add Terminal"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
