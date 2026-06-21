"use client";

import { useState, useEffect } from "react";
import { MagicMapping, AllowedDirection } from "@/types";
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

interface EditMagicMappingDialogProps {
  mapping: MagicMapping | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (
    id: number,
    updates: { slave_setup_id: number; allowed_direction: AllowedDirection },
  ) => Promise<void>;
}

export function EditMagicMappingDialog({
  mapping,
  open,
  onOpenChange,
  onSubmit,
}: EditMagicMappingDialogProps) {
  const [slaveSetupId, setSlaveSetupId] = useState("");
  const [direction, setDirection] = useState<AllowedDirection>("BOTH");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (mapping) {
      setSlaveSetupId(String(mapping.slave_setup_id));
      setDirection(mapping.allowed_direction);
    }
  }, [mapping]);

  const handleSubmit = async () => {
    if (!mapping) return;
    setSubmitting(true);
    try {
      await onSubmit(mapping.id, {
        slave_setup_id: parseInt(slaveSetupId),
        allowed_direction: direction,
      });
      onOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Magic Mapping</DialogTitle>
          <DialogDescription>
            Change the slave setup ID or allowed direction. The master setup ID is
            fixed — delete and recreate the mapping to change it.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <label className="text-sm font-medium">Master Setup ID</label>
            <Input type="number" value={mapping?.master_setup_id ?? ""} disabled />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">Slave Setup ID</label>
            <Input
              type="number"
              value={slaveSetupId}
              onChange={(e) => setSlaveSetupId(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">Allowed Direction</label>
            <Select value={direction} onValueChange={(v) => setDirection(v as AllowedDirection)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="BOTH">Both (BUY + SELL)</SelectItem>
                <SelectItem value="BUY">BUY only</SelectItem>
                <SelectItem value="SELL">SELL only</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={!slaveSetupId || submitting}>
            {submitting ? "Saving..." : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
