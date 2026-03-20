"use client";

import { useState, useEffect } from "react";
import { Link } from "@/types";
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

interface EditLinkDialogProps {
  link: Link | null;
  onSubmit: (
    id: number,
    data: {
      lot_mode: string;
      lot_value: number;
    }
  ) => Promise<void>;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function EditLinkDialog({
  link,
  onSubmit,
  open,
  onOpenChange,
}: EditLinkDialogProps) {
  const [lotMode, setLotMode] = useState("multiplier");
  const [lotValue, setLotValue] = useState("1");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (link) {
      setLotMode(link.lot_mode);
      setLotValue(String(link.lot_value));
    }
  }, [link]);

  const handleSubmit = async () => {
    if (!link) return;
    setSubmitting(true);
    try {
      await onSubmit(link.id, {
        lot_mode: lotMode,
        lot_value: parseFloat(lotValue),
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
          <DialogTitle>Edit Link</DialogTitle>
          <DialogDescription>
            Update the settings for this copy-trading link.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <label className="text-sm font-medium">Master</label>
            <Input type="text" value={link?.master_id ?? ""} disabled />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">Slave</label>
            <Input type="text" value={link?.slave_id ?? ""} disabled />
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
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Saving..." : "Save Changes"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
