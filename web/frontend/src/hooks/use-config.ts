"use client";
import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { Config } from "@/types";

export function useConfig() {
  const [config, setConfig] = useState<Config | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await fetchApi<Config>("/config");
      setConfig(data);
    } catch {
      // retry on next manual load
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const saveConfig = async (updates: Partial<Config>) => {
    setSaving(true);
    try {
      const data = await fetchApi<Config>("/config", {
        method: "PUT",
        body: JSON.stringify(updates),
      });
      setConfig(data);
      return true;
    } catch {
      return false;
    } finally {
      setSaving(false);
    }
  };

  return { config, loading, saving, saveConfig, reload: load };
}
