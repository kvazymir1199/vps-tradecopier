"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchApi } from "@/lib/api";
import { AlertRecord } from "@/types";

export interface AlertFilters {
  alert_type?: string;
  terminal_id?: string;
  delivered?: number;
  since_ms?: number;
  until_ms?: number;
  limit?: number;
}

function toQuery(filters: AlertFilters): string {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(filters)) {
    if (v === undefined || v === null || v === "") continue;
    params.set(k, String(v));
  }
  const s = params.toString();
  return s ? `?${s}` : "";
}

export function useAlerts(initialFilters: AlertFilters = { limit: 200 }) {
  const [alerts, setAlerts] = useState<AlertRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [filters, setFilters] = useState<AlertFilters>(initialFilters);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchApi<AlertRecord[]>(
        `/alerts${toQuery(filters)}`
      );
      setAlerts(data);
    } catch {
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  }, [filters]);

  useEffect(() => {
    load();
  }, [load]);

  // Light polling so the table stays fresh during a live run.
  useEffect(() => {
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  return { alerts, loading, filters, setFilters, reload: load };
}
