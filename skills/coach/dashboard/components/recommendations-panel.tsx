"use client";

import { AlertCircle } from "lucide-react";

interface Recommendation {
  id: string;
  name: string;
  content: string;
  priority: string;
  status: string;
}

interface RecommendationsPanelProps {
  recommendations: Recommendation[];
}

export function RecommendationsPanel({ recommendations }: RecommendationsPanelProps) {
  if (recommendations.length === 0) return null;

  return (
    <div className="space-y-2">
      {recommendations.map((r) => {
        const borderColor =
          r.priority === "high" ? "border-red-500/50" :
          r.priority === "medium" ? "border-[#b8c84a]/50" :
          "border-[#3d5c8f]/50";

        const badgeColor =
          r.priority === "high" ? "bg-red-500/20 text-red-400" :
          r.priority === "medium" ? "bg-[#b8c84a]/20 text-[#b8c84a]" :
          "bg-[#3d5c8f]/20 text-[#8ba4b8]";

        return (
          <div
            key={r.id}
            className={`rounded-lg border ${borderColor} bg-[#0c1628] px-4 py-3`}
          >
            <div className="flex items-center gap-2 mb-1">
              <AlertCircle className="w-4 h-4 text-[#b8c84a]" />
              <span className="font-medium text-[#c8dde8]">{r.name}</span>
              <span className={`text-xs px-1.5 py-0.5 rounded ${badgeColor}`}>
                {r.priority}
              </span>
            </div>
            <div className="text-sm text-[#8ba4b8] pl-6">{r.content}</div>
          </div>
        );
      })}
    </div>
  );
}
