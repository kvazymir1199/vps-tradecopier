"use client";

import { useEffect, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";
import { useTelegramSettings } from "@/hooks/use-telegram";
import { AlertType, TelegramSettings } from "@/types";

const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  heartbeat_miss: "Heartbeat miss",
  ack_timeout: "ACK timeout",
  consecutive_nacks: "NACK burst (5+)",
  queue_depth: "Pending queue >50",
  slave_disconnected: "Slave disconnected",
  hub_started: "Hub started / restarted",
  trade_copied: "Trade copied (high volume — opt-in)",
  daily_summary: "Daily summary",
  alert_storm: "Alert storm protection",
};

const MUTE_PRESETS: { label: string; seconds: number }[] = [
  { label: "30m", seconds: 30 * 60 },
  { label: "1h", seconds: 60 * 60 },
  { label: "4h", seconds: 4 * 60 * 60 },
  { label: "24h", seconds: 24 * 60 * 60 },
];

export default function TelegramSettingsPage() {
  const { settings, loading, saving, save, sendTest, setMute, clearMute } =
    useTelegramSettings();
  const [form, setForm] = useState<TelegramSettings | null>(null);
  const [testing, setTesting] = useState(false);

  useEffect(() => {
    if (settings && !form) setForm(settings);
  }, [settings, form]);

  const muteRemainingMs = useMemo(() => {
    if (!form || !form.mute_until_ms) return 0;
    const diff = form.mute_until_ms - Date.now();
    return diff > 0 ? diff : 0;
  }, [form]);

  if (loading || !form) {
    return (
      <main className="container mx-auto py-8 px-4">
        <h1 className="text-2xl font-bold mb-8">Telegram</h1>
        <p className="text-muted-foreground">Loading…</p>
        <Toaster />
      </main>
    );
  }

  const update = <K extends keyof TelegramSettings>(
    key: K,
    value: TelegramSettings[K]
  ) => setForm((prev) => (prev ? { ...prev, [key]: value } : prev));

  const toggleAlert = (at: AlertType, enabled: boolean) =>
    setForm((prev) =>
      prev
        ? {
            ...prev,
            alert_enabled: { ...prev.alert_enabled, [at]: enabled },
          }
        : prev
    );

  const onSave = async () => {
    if (!form) return;
    const ok = await save({
      enabled: form.enabled,
      bot_token: form.bot_token,
      chat_id: form.chat_id,
      daily_summary_time: form.daily_summary_time,
      alert_storm_threshold: form.alert_storm_threshold,
      alerts_retention_days: form.alerts_retention_days,
      alert_dedup_minutes: form.alert_dedup_minutes,
      alert_enabled: form.alert_enabled,
    });
    toast[ok ? "success" : "error"](ok ? "Saved" : "Save failed");
  };

  const onTest = async () => {
    setTesting(true);
    const res = await sendTest();
    setTesting(false);
    if (res.delivered) toast.success("Test alert delivered");
    else toast.error(`Test failed: ${res.detail}`);
  };

  return (
    <main className="container mx-auto py-8 space-y-8 px-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Telegram</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={onTest} disabled={testing}>
            {testing ? "Sending…" : "Test alert"}
          </Button>
          <Button onClick={onSave} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </div>
      </div>

      {/* Credentials */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Bot credentials</h2>
        <div className="grid gap-4 max-w-md">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium">Enabled</label>
            <Switch
              checked={form.enabled}
              onCheckedChange={(c) => update("enabled", c)}
            />
          </div>
          <Field label="Bot token">
            <Input
              value={form.bot_token}
              onChange={(e) => update("bot_token", e.target.value)}
              placeholder="123456:ABC-DEF…"
            />
          </Field>
          <Field label="Chat ID">
            <Input
              value={form.chat_id}
              onChange={(e) => update("chat_id", e.target.value)}
              placeholder="-1001234567890"
            />
          </Field>
        </div>
      </section>

      {/* Behaviour */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Behaviour</h2>
        <div className="grid gap-4 max-w-md">
          <Field label="Daily summary time (UTC, HH:MM)">
            <Input
              value={form.daily_summary_time}
              onChange={(e) => update("daily_summary_time", e.target.value)}
              placeholder="08:00"
            />
          </Field>
          <Field label="Dedup window (minutes)">
            <Input
              type="number"
              value={form.alert_dedup_minutes}
              onChange={(e) =>
                update("alert_dedup_minutes", Number(e.target.value))
              }
            />
          </Field>
          <Field label="Alert storm threshold (suppressed/window)">
            <Input
              type="number"
              value={form.alert_storm_threshold}
              onChange={(e) =>
                update("alert_storm_threshold", Number(e.target.value))
              }
            />
          </Field>
          <Field label="Alerts retention (days)">
            <Input
              type="number"
              value={form.alerts_retention_days}
              onChange={(e) =>
                update("alerts_retention_days", Number(e.target.value))
              }
            />
          </Field>
        </div>
      </section>

      {/* Mute */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Mute</h2>
        <p className="text-sm text-muted-foreground">
          {muteRemainingMs > 0
            ? `Muted until ${new Date(form.mute_until_ms).toISOString()} (${Math.ceil(
                muteRemainingMs / 60000
              )}m left)`
            : "Not muted."}
        </p>
        <div className="flex gap-2 flex-wrap">
          {MUTE_PRESETS.map((p) => (
            <Button
              key={p.seconds}
              variant="outline"
              onClick={async () => {
                const ok = await setMute(p.seconds);
                toast[ok ? "success" : "error"](
                  ok ? `Muted for ${p.label}` : "Mute failed"
                );
              }}
            >
              Mute {p.label}
            </Button>
          ))}
          <Button
            variant="outline"
            onClick={async () => {
              const ok = await clearMute();
              toast[ok ? "success" : "error"](
                ok ? "Mute cleared" : "Failed to clear mute"
              );
            }}
          >
            Clear mute
          </Button>
        </div>
      </section>

      {/* Alert toggles */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Alert types</h2>
        <div className="grid gap-3 max-w-md">
          {(Object.keys(ALERT_TYPE_LABELS) as AlertType[]).map((at) => (
            <div key={at} className="flex items-center justify-between">
              <label className="text-sm">{ALERT_TYPE_LABELS[at]}</label>
              <Switch
                checked={form.alert_enabled[at] ?? true}
                onCheckedChange={(c) => toggleAlert(at, c)}
              />
            </div>
          ))}
        </div>
      </section>

      <Toaster />
    </main>
  );
}

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-sm font-medium">{label}</label>
      {children}
    </div>
  );
}
