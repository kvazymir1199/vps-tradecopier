"use client";

import { useEffect, useState } from "react";
import { useConfig } from "@/hooks/use-config";
import { Config } from "@/types";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";

export default function SettingsPage() {
  const { config, loading, saving, saveConfig } = useConfig();
  const [form, setForm] = useState<Config | null>(null);

  useEffect(() => {
    if (config && !form) {
      setForm(config);
    }
  }, [config, form]);

  if (loading || !form) {
    return (
      <main className="container mx-auto py-8 px-4">
        <h1 className="text-2xl font-bold mb-8">Settings</h1>
        <p className="text-muted-foreground">Loading...</p>
        <Toaster />
      </main>
    );
  }

  const updateField = <K extends keyof Config>(key: K, value: Config[K]) => {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  };

  const handleSave = async () => {
    if (!form) return;
    const ok = await saveConfig(form);
    if (ok) {
      toast.success("Saved!");
    } else {
      toast.error("Failed to save settings");
    }
  };

  return (
    <main className="container mx-auto py-8 space-y-8 px-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Settings</h1>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? "Saving..." : "Save"}
        </Button>
      </div>

      {/* General */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">General</h2>
        <div className="grid gap-4 max-w-md">
          <FieldRow label="VPS ID">
            <Input
              value={form.vps_id}
              onChange={(e) => updateField("vps_id", e.target.value)}
            />
          </FieldRow>
        </div>
      </section>

      {/* Timing */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Timing</h2>
        <div className="grid gap-4 max-w-md">
          <FieldRow label="Heartbeat Interval (sec)">
            <Input
              type="number"
              value={form.heartbeat_interval_sec}
              onChange={(e) =>
                updateField("heartbeat_interval_sec", Number(e.target.value))
              }
            />
          </FieldRow>
          <FieldRow label="Heartbeat Timeout (sec)">
            <Input
              type="number"
              value={form.heartbeat_timeout_sec}
              onChange={(e) =>
                updateField("heartbeat_timeout_sec", Number(e.target.value))
              }
            />
          </FieldRow>
          <FieldRow label="ACK Timeout (sec)">
            <Input
              type="number"
              value={form.ack_timeout_sec}
              onChange={(e) =>
                updateField("ack_timeout_sec", Number(e.target.value))
              }
            />
          </FieldRow>
          <FieldRow label="ACK Max Retries">
            <Input
              type="number"
              value={form.ack_max_retries}
              onChange={(e) =>
                updateField("ack_max_retries", Number(e.target.value))
              }
            />
          </FieldRow>
        </div>
      </section>

      {/* Router */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Router</h2>
        <div className="grid gap-4 max-w-md">
          <FieldRow label="Resend Window Size">
            <Input
              type="number"
              value={form.resend_window_size}
              onChange={(e) =>
                updateField("resend_window_size", Number(e.target.value))
              }
            />
          </FieldRow>
        </div>
      </section>

      {/* Alerts */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Alerts</h2>
        <div className="grid gap-4 max-w-md">
          <FieldRow label="Alert Dedup (minutes)">
            <Input
              type="number"
              value={form.alert_dedup_minutes}
              onChange={(e) =>
                updateField("alert_dedup_minutes", Number(e.target.value))
              }
            />
          </FieldRow>
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium">Telegram Enabled</label>
            <Switch
              checked={form.telegram_enabled}
              onCheckedChange={(checked) =>
                updateField("telegram_enabled", checked)
              }
            />
          </div>
          <FieldRow label="Telegram Bot Token">
            <Input
              value={form.telegram_bot_token}
              onChange={(e) =>
                updateField("telegram_bot_token", e.target.value)
              }
              placeholder="123456:ABC-DEF..."
            />
          </FieldRow>
          <FieldRow label="Telegram Chat ID">
            <Input
              value={form.telegram_chat_id}
              onChange={(e) => updateField("telegram_chat_id", e.target.value)}
              placeholder="-1001234567890"
            />
          </FieldRow>
        </div>
      </section>

      <Toaster />
    </main>
  );
}

function FieldRow({
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
