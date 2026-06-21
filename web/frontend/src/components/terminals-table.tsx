"use client";

import { useState } from "react";
import { useTerminals } from "@/hooks/use-terminals";
import { formatTimeAgo } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";
import { AddTerminalDialog } from "@/components/add-terminal-dialog";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export function TerminalsTable() {
  const { terminals, loading, createTerminal, deleteTerminal } = useTerminals();
  const [addOpen, setAddOpen] = useState(false);

  const handleAdd = async (terminalId: string, role: "master" | "slave") => {
    try {
      await createTerminal(terminalId, role);
      toast.success("Terminal added");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add terminal");
      throw err;
    }
  };

  const handleDelete = async (terminalId: string) => {
    if (!confirm(`Delete terminal "${terminalId}" and all its links/mappings?`)) return;
    try {
      await deleteTerminal(terminalId);
      toast.success("Terminal deleted");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete terminal");
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">Terminals</h2>
          {loading && (
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent opacity-50" />
          )}
        </div>
        <Button size="sm" onClick={() => setAddOpen(true)}>
          + Add Terminal
        </Button>
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Terminal ID</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Account</TableHead>
            <TableHead>Broker</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Last Heartbeat</TableHead>
            <TableHead className="w-20">Actions</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {terminals.length === 0 && !loading ? (
            <TableRow>
              <TableCell colSpan={7} className="text-center text-muted-foreground">
                No terminals connected
              </TableCell>
            </TableRow>
          ) : (
            terminals.map((t) => (
              <TableRow key={t.terminal_id}>
                <TableCell className="font-mono text-xs">{t.terminal_id}</TableCell>
                <TableCell className="capitalize">{t.role}</TableCell>
                <TableCell>{t.account_number ?? "-"}</TableCell>
                <TableCell>{t.broker_server ?? "-"}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <StatusBadge status={t.status} />
                    {t.status_message && t.status_message !== "OK" && (
                      <span className="text-xs text-muted-foreground">{t.status_message}</span>
                    )}
                  </div>
                </TableCell>
                <TableCell>{formatTimeAgo(t.last_heartbeat)}</TableCell>
                <TableCell>
                  <Button
                    variant="destructive"
                    size="xs"
                    onClick={() => handleDelete(t.terminal_id)}
                  >
                    Delete
                  </Button>
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
      <AddTerminalDialog open={addOpen} onOpenChange={setAddOpen} onSubmit={handleAdd} />
    </div>
  );
}
