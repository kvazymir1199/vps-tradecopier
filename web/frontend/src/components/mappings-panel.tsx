"use client";

import { useState } from "react";
import { toast } from "sonner";
import { useMappings } from "@/hooks/use-mappings";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { AddMappingDialog } from "@/components/add-mapping-dialog";

interface MappingsPanelProps {
  linkId: number;
}

export function MappingsPanel({ linkId }: MappingsPanelProps) {
  const {
    symbolMappings,
    magicMappings,
    loading,
    addSymbolMapping,
    deleteSymbolMapping,
    addMagicMapping,
    deleteMagicMapping,
  } = useMappings(linkId);

  const [symbolDialogOpen, setSymbolDialogOpen] = useState(false);
  const [magicDialogOpen, setMagicDialogOpen] = useState(false);

  const handleAddSymbol = async (masterSymbol: string, slaveSymbol: string) => {
    try {
      await addSymbolMapping(masterSymbol, slaveSymbol);
      toast.success("Symbol mapping added");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to add symbol mapping"
      );
      throw err;
    }
  };

  const handleDeleteSymbol = async (id: number) => {
    try {
      await deleteSymbolMapping(id);
      toast.success("Symbol mapping deleted");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to delete symbol mapping"
      );
    }
  };

  const handleAddMagic = async (masterSetupId: string, slaveSetupId: string) => {
    try {
      await addMagicMapping(parseInt(masterSetupId), parseInt(slaveSetupId));
      toast.success("Magic mapping added");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to add magic mapping"
      );
      throw err;
    }
  };

  const handleDeleteMagic = async (id: number) => {
    try {
      await deleteMagicMapping(id);
      toast.success("Magic mapping deleted");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to delete magic mapping"
      );
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <h3 className="text-md font-semibold">Mappings</h3>
        {loading && (
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent opacity-50" />
        )}
      </div>

      {/* Symbol Mappings */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-medium">Symbol Mappings</h4>
          <Button size="xs" onClick={() => setSymbolDialogOpen(true)}>
            Add
          </Button>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Master Symbol</TableHead>
              <TableHead>Slave Symbol</TableHead>
              <TableHead className="w-20">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {symbolMappings.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={3}
                  className="text-center text-muted-foreground"
                >
                  No symbol mappings
                </TableCell>
              </TableRow>
            ) : (
              symbolMappings.map((m) => (
                <TableRow key={m.id}>
                  <TableCell>{m.master_symbol}</TableCell>
                  <TableCell>{m.slave_symbol}</TableCell>
                  <TableCell>
                    <Button
                      variant="destructive"
                      size="xs"
                      onClick={() => handleDeleteSymbol(m.id)}
                    >
                      Delete
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      {/* Magic Mappings */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-sm font-medium">Magic Mappings</h4>
          <Button size="xs" onClick={() => setMagicDialogOpen(true)}>
            Add
          </Button>
        </div>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Master Setup ID</TableHead>
              <TableHead>Slave Setup ID</TableHead>
              <TableHead className="w-20">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {magicMappings.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={3}
                  className="text-center text-muted-foreground"
                >
                  No magic mappings
                </TableCell>
              </TableRow>
            ) : (
              magicMappings.map((m) => (
                <TableRow key={m.id}>
                  <TableCell>{m.master_setup_id}</TableCell>
                  <TableCell>{m.slave_setup_id}</TableCell>
                  <TableCell>
                    <Button
                      variant="destructive"
                      size="xs"
                      onClick={() => handleDeleteMagic(m.id)}
                    >
                      Delete
                    </Button>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>

      <AddMappingDialog
        type="symbol"
        open={symbolDialogOpen}
        onOpenChange={setSymbolDialogOpen}
        onSubmit={handleAddSymbol}
      />

      <AddMappingDialog
        type="magic"
        open={magicDialogOpen}
        onOpenChange={setMagicDialogOpen}
        onSubmit={handleAddMagic}
      />
    </div>
  );
}
