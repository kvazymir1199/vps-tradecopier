"use client";
import { useState, useEffect, useCallback, useRef } from "react";
import { fetchApi } from "@/lib/api";
import { Terminal } from "@/types";

export function useTerminals(pollInterval = 2000) {
  const [terminals, setTerminals] = useState<Terminal[]>([]);
  const [loading, setLoading] = useState(true);
  const mountedRef = useRef(true);

  const load = useCallback(async () => {
    try {
      const data = await fetchApi<Terminal[]>("/terminals");
      if (mountedRef.current) setTerminals(data);
    } catch (err) {
      console.error("Failed to load terminals:", err);
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    load();
    const interval = setInterval(load, pollInterval);
    return () => {
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, [load, pollInterval]);

  const createTerminal = async (terminalId: string, role: "master" | "slave") => {
    await fetchApi("/terminals", {
      method: "POST",
      body: JSON.stringify({ terminal_id: terminalId, role }),
    });
    await load();
  };

  const deleteTerminal = async (terminalId: string) => {
    await fetchApi(`/terminals/${terminalId}`, { method: "DELETE" });
    await load();
  };

  return { terminals, loading, createTerminal, deleteTerminal };
}
