"use client";

import { useMemo, useState } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Toaster } from "@/components/ui/sonner";
import { useAlerts, AlertFilters } from "@/hooks/use-alerts";
import { AlertRecord } from "@/types";

const ALERT_TYPES = [
  "heartbeat_miss",
  "ack_timeout",
  "consecutive_nacks",
  "queue_depth",
  "slave_disconnected",
  "hub_started",
  "trade_copied",
  "daily_summary",
  "alert_storm",
];

function formatTs(ms: number) {
  return new Date(ms).toISOString().replace("T", " ").slice(0, 19);
}

function statusBadge(a: AlertRecord) {
  if (a.delivered) return <Badge variant="default">delivered</Badge>;
  if (a.muted) return <Badge variant="secondary">muted</Badge>;
  if (a.deduplicated) return <Badge variant="outline">dedup</Badge>;
  return <Badge variant="destructive">failed</Badge>;
}

export default function AlertsPage() {
  const [draft, setDraft] = useState<AlertFilters>({ limit: 200 });
  const { alerts, loading, setFilters } = useAlerts(draft);

  const apply = () => setFilters({ ...draft });
  const reset = () => {
    const next = { limit: 200 };
    setDraft(next);
    setFilters(next);
  };

  const stats = useMemo(() => {
    const delivered = alerts.filter((a) => a.delivered).length;
    const failed = alerts.filter((a) => !a.delivered && !a.muted && !a.deduplicated).length;
    const muted = alerts.filter((a) => a.muted).length;
    const dedup = alerts.filter((a) => a.deduplicated).length;
    return { delivered, failed, muted, dedup, total: alerts.length };
  }, [alerts]);

  return (
    <main className="container mx-auto py-8 space-y-6 px-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Alerts history</h1>
        <p className="text-sm text-muted-foreground">
          {stats.total} rows · {stats.delivered} delivered · {stats.failed} failed ·
          {" "}{stats.muted} muted · {stats.dedup} dedup
        </p>
      </div>

      {/* Filters */}
      <section className="grid grid-cols-1 md:grid-cols-5 gap-3 items-end">
        <div className="space-y-1.5">
          <label className="text-sm font-medium">Type</label>
          <Select
            value={draft.alert_type ?? "any"}
            onValueChange={(v) =>
              setDraft({ ...draft, alert_type: v === "any" ? undefined : v })
            }
          >
            <SelectTrigger>
              <SelectValue placeholder="Any" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any</SelectItem>
              {ALERT_TYPES.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium">Terminal ID</label>
          <Input
            value={draft.terminal_id ?? ""}
            onChange={(e) => setDraft({ ...draft, terminal_id: e.target.value })}
            placeholder="slave_1"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium">Delivered</label>
          <Select
            value={
              draft.delivered === undefined ? "any" : String(draft.delivered)
            }
            onValueChange={(v) =>
              setDraft({
                ...draft,
                delivered: v === "any" ? undefined : Number(v),
              })
            }
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="any">Any</SelectItem>
              <SelectItem value="1">Delivered</SelectItem>
              <SelectItem value="0">Not delivered</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium">Limit</label>
          <Input
            type="number"
            value={draft.limit ?? 200}
            onChange={(e) =>
              setDraft({ ...draft, limit: Number(e.target.value) || 200 })
            }
          />
        </div>
        <div className="flex gap-2">
          <Button onClick={apply}>Apply</Button>
          <Button variant="outline" onClick={reset}>
            Reset
          </Button>
        </div>
      </section>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Time (UTC)</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Terminal</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Retries</TableHead>
            <TableHead>Message</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {loading ? (
            <TableRow>
              <TableCell colSpan={6} className="text-muted-foreground">
                Loading…
              </TableCell>
            </TableRow>
          ) : alerts.length === 0 ? (
            <TableRow>
              <TableCell colSpan={6} className="text-muted-foreground">
                No alerts match these filters.
              </TableCell>
            </TableRow>
          ) : (
            alerts.map((a) => (
              <TableRow key={a.id}>
                <TableCell className="font-mono text-xs whitespace-nowrap">
                  {formatTs(a.sent_at)}
                </TableCell>
                <TableCell>
                  <Badge variant="outline">{a.alert_type}</Badge>
                </TableCell>
                <TableCell className="font-mono text-xs">
                  {a.terminal_id ?? "—"}
                </TableCell>
                <TableCell>{statusBadge(a)}</TableCell>
                <TableCell>{a.retry_count}</TableCell>
                <TableCell className="text-sm">{a.message}</TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      <Toaster />
    </main>
  );
}
