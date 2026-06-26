"use client";

import { CheckCircle2, AlertTriangle, XCircle } from "lucide-react";

interface PipelineIndicatorProps {
  health: string | null;
  lastIngestDate: string | null;
}

export function PipelineIndicator({ health, lastIngestDate }: PipelineIndicatorProps) {
  const Icon =
    health === "healthy" ? CheckCircle2 :
    health === "stale" ? AlertTriangle :
    XCircle;

  const color =
    health === "healthy" ? "text-green-400" :
    health === "stale" ? "text-amber-400" :
    "text-red-400";

  const bgColor =
    health === "healthy" ? "bg-green-500/10 border-green-500/30" :
    health === "stale" ? "bg-amber-500/10 border-amber-500/30" :
    "bg-red-500/10 border-red-500/30";

  return (
    <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg border ${bgColor}`}>
      <Icon className={`w-4 h-4 ${color}`} />
      <span className={`text-sm font-medium ${color}`}>
        {health || "unknown"}
      </span>
      {lastIngestDate && (
        <span className="text-xs text-[#8ba4b8] ml-2">
          Last: {new Date(lastIngestDate).toLocaleDateString()}
        </span>
      )}
    </div>
  );
}
