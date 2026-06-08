"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { TelegramSettings, TelegramSettingsUpdate } from "@/types";

export function useTelegramSettings() {
  const [settings, setSettings] = useState<TelegramSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await fetchApi<TelegramSettings>("/telegram");
      setSettings(data);
    } catch {
      // silent — let the page render its empty state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const save = async (updates: TelegramSettingsUpdate) => {
    setSaving(true);
    try {
      const data = await fetchApi<TelegramSettings>("/telegram", {
        method: "PUT",
        body: JSON.stringify(updates),
      });
      setSettings(data);
      return true;
    } catch {
      return false;
    } finally {
      setSaving(false);
    }
  };

  const sendTest = async () => {
    try {
      return await fetchApi<{ delivered: boolean; detail: string }>(
        "/telegram/test",
        { method: "POST" }
      );
    } catch (e) {
      return { delivered: false, detail: (e as Error).message };
    }
  };

  const setMute = async (durationSeconds: number) => {
    try {
      const res = await fetchApi<{ muted_until_ms: number }>(
        "/telegram/mute",
        {
          method: "POST",
          body: JSON.stringify({ duration_seconds: durationSeconds }),
        }
      );
      if (settings) {
        setSettings({ ...settings, mute_until_ms: res.muted_until_ms });
      }
      return true;
    } catch {
      return false;
    }
  };

  const clearMute = async () => {
    try {
      const res = await fetchApi<{ muted_until_ms: number }>(
        "/telegram/mute",
        { method: "DELETE" }
      );
      if (settings) {
        setSettings({ ...settings, mute_until_ms: res.muted_until_ms });
      }
      return true;
    } catch {
      return false;
    }
  };

  return {
    settings,
    loading,
    saving,
    save,
    sendTest,
    setMute,
    clearMute,
    reload: load,
  };
}
