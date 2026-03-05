"use client";
import { Badge } from "@/components/ui/badge";

const statusColors: Record<string, string> = {
  Active: "bg-green-500 hover:bg-green-600",
  Starting: "bg-yellow-500 hover:bg-yellow-600",
  Connected: "bg-yellow-500 hover:bg-yellow-600",
  Syncing: "bg-yellow-500 hover:bg-yellow-600",
  Paused: "bg-gray-500 hover:bg-gray-600",
  Disconnected: "bg-orange-500 hover:bg-orange-600",
  Error: "bg-red-500 hover:bg-red-600",
};

export function StatusBadge({ status }: { status: string }) {
  return (
    <Badge className={`${statusColors[status] || "bg-gray-400"} text-white`}>
      {status}
    </Badge>
  );
}
