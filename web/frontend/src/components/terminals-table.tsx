"use client";

import { useTerminals } from "@/hooks/use-terminals";
import { formatTimeAgo } from "@/lib/utils";
import { StatusBadge } from "@/components/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export function TerminalsTable() {
  const { terminals, loading } = useTerminals();

  return (
    <div>
      <div className="flex items-center gap-2 mb-4">
        <h2 className="text-lg font-semibold">Terminals</h2>
        {loading && (
          <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent opacity-50" />
        )}
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
          </TableRow>
        </TableHeader>
        <TableBody>
          {terminals.length === 0 && !loading ? (
            <TableRow>
              <TableCell colSpan={6} className="text-center text-muted-foreground">
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
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>
    </div>
  );
}
