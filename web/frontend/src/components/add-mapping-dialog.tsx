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

interface AddMappingDialogProps {
  type: "symbol" | "magic";
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (field1: string, field2: string) => Promise<void>;
}

export function AddMappingDialog({
  type,
  open,
  onOpenChange,
  onSubmit,
}: AddMappingDialogProps) {
  const [field1, setField1] = useState("");
  const [field2, setField2] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const isSymbol = type === "symbol";
  const label1 = isSymbol ? "Master Symbol" : "Master Setup ID";
  const label2 = isSymbol ? "Slave Symbol" : "Slave Setup ID";
  const placeholder1 = isSymbol ? "e.g. EURUSD" : "e.g. 1001";
  const placeholder2 = isSymbol ? "e.g. EURUSD.raw" : "e.g. 2001";

  const handleSubmit = async () => {
    setSubmitting(true);
    try {
      await onSubmit(field1, field2);
      setField1("");
      setField2("");
      onOpenChange(false);
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenChange = (value: boolean) => {
    if (!value) {
      setField1("");
      setField2("");
    }
    onOpenChange(value);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            Add {isSymbol ? "Symbol" : "Magic"} Mapping
          </DialogTitle>
          <DialogDescription>
            {isSymbol
              ? "Map a master symbol to a slave symbol."
              : (
                <>
                  Map a master setup ID to a slave setup ID.{" "}
                  The hub replaces the last two digits of the master magic number
                  with the slave setup ID. Example: master magic{" "}
                  <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">15010301</code>
                  {" "}→ slave magic{" "}
                  <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">15010305</code>.
                </>
              )}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <label className="text-sm font-medium">{label1}</label>
            <Input
              type={isSymbol ? "text" : "number"}
              placeholder={placeholder1}
              value={field1}
              onChange={(e) => setField1(e.target.value)}
            />
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium">{label2}</label>
            <Input
              type={isSymbol ? "text" : "number"}
              placeholder={placeholder2}
              value={field2}
              onChange={(e) => setField2(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => handleOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!field1 || !field2 || submitting}
          >
            {submitting ? "Adding..." : "Add Mapping"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
