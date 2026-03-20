"use client";
import { useState, useEffect, useCallback } from "react";
import { fetchApi } from "@/lib/api";
import { Link } from "@/types";

export function useLinks() {
  const [links, setLinks] = useState<Link[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchApi<Link[]>("/links");
      setLinks(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const createLink = async (body: { master_id: string; slave_id: string; lot_mode: string; lot_value: number }) => {
    await fetchApi<Link>("/links", { method: "POST", body: JSON.stringify(body) });
    await refresh();
  };

  const updateLink = async (id: number, body: Partial<{ enabled: number; lot_mode: string; lot_value: number }>) => {
    await fetchApi<Link>(`/links/${id}`, { method: "PUT", body: JSON.stringify(body) });
    await refresh();
  };

  const toggleLink = async (id: number) => {
    await fetchApi(`/links/${id}/toggle`, { method: "PATCH" });
    await refresh();
  };

  const deleteLink = async (id: number) => {
    await fetchApi(`/links/${id}`, { method: "DELETE" });
    await refresh();
  };

  return { links, loading, refresh, createLink, updateLink, toggleLink, deleteLink };
}
