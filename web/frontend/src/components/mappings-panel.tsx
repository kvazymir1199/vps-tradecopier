"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { toast } from "sonner";
import { fetchApi } from "@/lib/api";
import { useMappings } from "@/hooks/use-mappings";
import { SymbolSuggestionsResponse, AllowedDirection } from "@/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { AddMappingDialog } from "@/components/add-mapping-dialog";

interface MappingsPanelProps {
  linkId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const NONE_VALUE = "__none__";

type PairStatus = "saved" | "unsaved" | "unmapped";

export function MappingsPanel({ linkId, open, onOpenChange }: MappingsPanelProps) {
  const {
    symbolMappings,
    magicMappings,
    loading,
    refresh,
    deleteSymbolMapping,
    addSymbolMapping,
    addMagicMapping,
    deleteMagicMapping,
  } = useMappings(linkId);

  const [magicDialogOpen, setMagicDialogOpen] = useState(false);
  const [symbolPairs, setSymbolPairs] = useState<
    { master: string; slave: string | null }[]
  >([]);
  const [slaveSymbols, setSlaveSymbols] = useState<string[]>([]);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [search, setSearch] = useState("");
  // Snapshot of saved mappings from DB at load time
  const [savedSnapshot, setSavedSnapshot] = useState<Record<string, string>>({});

  const fetchSuggestions = useCallback(async () => {
    setSuggestionsLoading(true);
    try {
      const data = await fetchApi<SymbolSuggestionsResponse>(
        `/links/${linkId}/symbol-mappings/suggestions`
      );
      setSymbolPairs(
        data.suggestions.map((s) => ({
          master: s.master_symbol,
          slave: s.slave_symbol,
        }))
      );
      setSlaveSymbols(data.slave_symbols);
    } catch (err) {
      toast.error(
        err instanceof Error
          ? err.message
          : "Failed to fetch symbol suggestions"
      );
    } finally {
      setSuggestionsLoading(false);
    }
  }, [linkId]);

  // Build snapshot of what's saved in DB when symbolMappings load
  useEffect(() => {
    const snap: Record<string, string> = {};
    for (const m of symbolMappings) {
      snap[m.master_symbol] = m.slave_symbol;
    }
    setSavedSnapshot(snap);
  }, [symbolMappings]);

  useEffect(() => {
    if (open) {
      fetchSuggestions();
      setSearch("");
    }
  }, [open, fetchSuggestions]);

  const filteredPairs = useMemo(() => {
    if (!search.trim()) return symbolPairs;
    const q = search.toLowerCase();
    return symbolPairs.filter(
      (p) =>
        p.master.toLowerCase().includes(q) ||
        (p.slave && p.slave.toLowerCase().includes(q))
    );
  }, [symbolPairs, search]);

  const getStatus = (pair: { master: string; slave: string | null }): PairStatus => {
    if (!pair.slave) return "unmapped";
    const savedSlave = savedSnapshot[pair.master];
    if (savedSlave === pair.slave) return "saved";
    return "unsaved";
  };

  const handleSlaveChange = (masterSymbol: string, value: string) => {
    setSymbolPairs((prev) =>
      prev.map((p) =>
        p.master === masterSymbol
          ? { ...p, slave: value === NONE_VALUE ? null : value }
          : p
      )
    );
  };

  const handleSaveAll = async () => {
    setSaving(true);
    try {
      for (const m of symbolMappings) {
        await deleteSymbolMapping(m.id);
      }
      for (const pair of symbolPairs) {
        if (pair.slave) {
          await addSymbolMapping(pair.master, pair.slave);
        }
      }
      await refresh();
      toast.success("Symbol mappings saved");
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Failed to save symbol mappings"
      );
    } finally {
      setSaving(false);
    }
  };

  const handleAutoMatch = async () => {
    await fetchSuggestions();
    toast.success("Suggestions refreshed");
  };

  const handleAddMagic = async (
    masterSetupId: string,
    slaveSetupId: string,
    allowedDirection?: string,
  ) => {
    try {
      await addMagicMapping(
        parseInt(masterSetupId),
        parseInt(slaveSetupId),
        (allowedDirection as AllowedDirection) ?? "BOTH",
      );
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

  const savedCount = symbolPairs.filter((p) => getStatus(p) === "saved").length;
  const unsavedCount = symbolPairs.filter((p) => getStatus(p) === "unsaved").length;
  const totalCount = symbolPairs.length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[85vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>
            Mappings
            {totalCount > 0 && (
              <span className="ml-2 text-sm font-normal text-muted-foreground">
                ({savedCount} saved
                {unsavedCount > 0 && (
                  <span className="text-yellow-600">, {unsavedCount} unsaved</span>
                )}
                {" / "}{totalCount} total)
              </span>
            )}
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto space-y-6">
          {/* Symbol Mappings */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-medium">Symbol Mappings</h4>
              <div className="flex items-center gap-2">
                <Button
                  size="xs"
                  variant="outline"
                  onClick={handleAutoMatch}
                  disabled={suggestionsLoading}
                >
                  Auto-Match
                </Button>
                <Button
                  size="xs"
                  onClick={handleSaveAll}
                  disabled={saving || suggestionsLoading}
                >
                  {saving ? "Saving..." : "Save All"}
                </Button>
              </div>
            </div>

            <Input
              type="text"
              placeholder="Search symbols..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="mb-2"
            />

            <div className="max-h-[40vh] overflow-y-auto border rounded-md">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Master Symbol</TableHead>
                    <TableHead>Slave Symbol</TableHead>
                    <TableHead className="w-20">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredPairs.length === 0 ? (
                    <TableRow>
                      <TableCell
                        colSpan={3}
                        className="text-center text-muted-foreground"
                      >
                        {suggestionsLoading
                          ? "Loading..."
                          : search
                            ? "No symbols match filter"
                            : "No symbols found"}
                      </TableCell>
                    </TableRow>
                  ) : (
                    filteredPairs.map((pair) => {
                      const status = getStatus(pair);
                      return (
                        <TableRow key={pair.master}>
                          <TableCell className="font-mono text-xs">
                            {pair.master}
                          </TableCell>
                          <TableCell>
                            <Select
                              value={pair.slave ?? NONE_VALUE}
                              onValueChange={(val) =>
                                handleSlaveChange(pair.master, val)
                              }
                            >
                              <SelectTrigger className="w-full h-8 text-xs">
                                <SelectValue placeholder="Select symbol" />
                              </SelectTrigger>
                              <SelectContent>
                                <SelectItem value={NONE_VALUE}>
                                  -- Select --
                                </SelectItem>
                                {slaveSymbols.map((sym) => (
                                  <SelectItem key={sym} value={sym}>
                                    {sym}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                          </TableCell>
                          <TableCell className="text-center text-xs">
                            {status === "saved" && (
                              <span className="text-green-600 font-medium">Saved</span>
                            )}
                            {status === "unsaved" && (
                              <span className="text-yellow-600 font-medium">Unsaved</span>
                            )}
                            {status === "unmapped" && (
                              <span className="text-muted-foreground">--</span>
                            )}
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </div>
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
                  <TableHead className="w-24">Direction</TableHead>
                  <TableHead className="w-20">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {magicMappings.length === 0 ? (
                  <TableRow>
                    <TableCell
                      colSpan={4}
                      className="text-center text-muted-foreground"
                    >
                      No magic mappings
                    </TableCell>
                  </TableRow>
                ) : (
                  magicMappings.map((m) => {
                    const dir = m.allowed_direction;
                    const dirClass =
                      dir === "BUY"
                        ? "text-green-600"
                        : dir === "SELL"
                          ? "text-red-600"
                          : "text-muted-foreground";
                    return (
                      <TableRow key={m.id}>
                        <TableCell>{m.master_setup_id}</TableCell>
                        <TableCell>{m.slave_setup_id}</TableCell>
                        <TableCell>
                          <span className={`font-mono text-xs font-medium ${dirClass}`}>
                            {dir}
                          </span>
                        </TableCell>
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
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
        </div>

        <AddMappingDialog
          type="magic"
          open={magicDialogOpen}
          onOpenChange={setMagicDialogOpen}
          onSubmit={handleAddMagic}
        />
      </DialogContent>
    </Dialog>
  );
}
