import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"
import { Terminal } from "@/types"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatTimeAgo(tsMs: number): string {
  const now = Date.now();
  const diff = now - tsMs;
  if (diff < 0) return "just now";
  const seconds = Math.floor(diff / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/**
 * Full label for a terminal: "master_1715542650 — Pepperstone-Demo (master)".
 * Falls back to the raw id when the terminal is unknown or has no broker.
 */
export function terminalLabel(
  terminalId: string,
  terminal: Terminal | undefined
): string {
  if (!terminal) return terminalId;
  const broker = terminal.broker_server ? ` — ${terminal.broker_server}` : "";
  return `${terminalId}${broker} (${terminal.role})`;
}
