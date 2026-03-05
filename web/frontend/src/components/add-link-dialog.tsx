"use client";

import { useState } from "react";
import { Terminal } from "@/types";
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

interface AddLinkDialogProps {
  terminals: Terminal[];
  onSubmit: (data: {
    master_id: string;
    slave_id: string;
    lot_mode: string;
    lot_value: number;
    symbol_suffix: string;
  }) => Promise<void>;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddLinkDialog({
  terminals,
  onSubmit,
  open,
  onOpenChange,
}: AddLinkDialogProps) {
  const [masterId, setMasterId] = useState("");
  const [slaveId, setSlaveId] = useState("");
  const [lotMode, setLotMode] = useState("multiplier");
  const [lotValue, setLotValue] = useState("1");
  const [symbolSuffix, setSymbolSuffix] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const masters = terminals.filter((t) => t.role === "master");
  const slaves = terminals.filter((t) => t.role === "slave");

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await onSubmit({
        master_id: masterId,
        slave_id: slaveId,
        lot_mode: lotMode,
        lot_value: parseFloat(lotValue),
        symbol_suffix: symbolSuffix,
      });
      setMasterId("");
      setSlaveId("");
      setLotMode("multiplier");
      setLotValue("1");
      setSymbolSuffix("");
      onOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Link</DialogTitle>
          <DialogDescription>
            Create a new copy-trading link between a master and slave terminal.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <label className="text-sm font-medium">Master</label>
            <Select value={masterId} onValueChange={setMasterId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select master terminal" />
              </SelectTrigger>
              <SelectContent>
                {masters.map((t) => (
                  <SelectItem key={t.terminal_id} value={t.terminal_id}>
                    {t.terminal_id} ({t.account_number ?? "N/A"})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">Slave</label>
            <Select value={slaveId} onValueChange={setSlaveId}>
              <SelectTrigger className="w-full">
                <SelectValue placeholder="Select slave terminal" />
              </SelectTrigger>
              <SelectContent>
                {slaves.map((t) => (
                  <SelectItem key={t.terminal_id} value={t.terminal_id}>
                    {t.terminal_id} ({t.account_number ?? "N/A"})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">Lot Mode</label>
            <Select value={lotMode} onValueChange={setLotMode}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="multiplier">Multiplier</SelectItem>
                <SelectItem value="fixed">Fixed</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">Lot Value</label>
            <Input
              type="number"
              step="0.01"
              min="0"
              value={lotValue}
              onChange={(e) => setLotValue(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">Symbol Suffix</label>
            <Input
              type="text"
              placeholder="e.g. .raw"
              value={symbolSuffix}
              onChange={(e) => setSymbolSuffix(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!masterId || !slaveId || submitting}
          >
            {submitting ? "Creating..." : "Create Link"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
