"use client";
import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { SymbolMapping, MagicMapping } from "@/types";

export function useMappings(linkId: number | null) {
  const [symbolMappings, setSymbolMappings] = useState<SymbolMapping[]>([]);
  const [magicMappings, setMagicMappings] = useState<MagicMapping[]>([]);
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!linkId) return;
    setLoading(true);
    try {
      const [sym, mag] = await Promise.all([
        fetchApi<SymbolMapping[]>(`/links/${linkId}/symbol-mappings`),
        fetchApi<MagicMapping[]>(`/links/${linkId}/magic-mappings`),
      ]);
      setSymbolMappings(sym);
      setMagicMappings(mag);
    } finally {
      setLoading(false);
    }
  }, [linkId]);

  useEffect(() => { refresh(); }, [refresh]);

  const addSymbolMapping = async (masterSymbol: string, slaveSymbol: string) => {
    await fetchApi(`/links/${linkId}/symbol-mappings`, {
      method: "POST",
      body: JSON.stringify({ master_symbol: masterSymbol, slave_symbol: slaveSymbol }),
    });
    await refresh();
  };

  const deleteSymbolMapping = async (id: number) => {
    await fetchApi(`/symbol-mappings/${id}`, { method: "DELETE" });
    await refresh();
  };

  const addMagicMapping = async (masterSetupId: number, slaveSetupId: number) => {
    await fetchApi(`/links/${linkId}/magic-mappings`, {
      method: "POST",
      body: JSON.stringify({ master_setup_id: masterSetupId, slave_setup_id: slaveSetupId }),
    });
    await refresh();
  };

  const deleteMagicMapping = async (id: number) => {
    await fetchApi(`/magic-mappings/${id}`, { method: "DELETE" });
    await refresh();
  };

  return { symbolMappings, magicMappings, loading, refresh, addSymbolMapping, deleteSymbolMapping, addMagicMapping, deleteMagicMapping };
}
