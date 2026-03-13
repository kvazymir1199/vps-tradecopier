"use client";
import { useState, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import { Terminal } from "@/types";

export function useTerminals(pollInterval = 2000) {
  const [terminals, setTerminals] = useState<Terminal[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const data = await fetchApi<Terminal[]>("/terminals");
        if (mounted) setTerminals(data);
      } catch {
        // silently retry on next poll
      } finally {
        if (mounted) setLoading(false);
      }
    };
    load();
    const interval = setInterval(load, pollInterval);
    return () => { mounted = false; clearInterval(interval); };
  }, [pollInterval]);

  return { terminals, loading };
}
