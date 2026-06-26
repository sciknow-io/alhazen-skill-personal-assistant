"use client";

import { TrendingUp, TrendingDown, Minus } from "lucide-react";

interface MetricCardProps {
  metricType: string;
  latestValue: number;
  units?: string;
  avg7d: number;
  delta7d: number;
  direction: string;
}

function formatMetricName(type: string): string {
  return type
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function MetricCard({
  metricType,
  latestValue,
  units,
  avg7d,
  delta7d,
  direction,
}: MetricCardProps) {
  const TrendIcon =
    direction === "improving" ? TrendingUp :
    direction === "regressing" ? TrendingDown :
    Minus;

  const trendColor =
    direction === "improving" ? "text-green-400" :
    direction === "regressing" ? "text-red-400" :
    "text-[#8ba4b8]";

  return (
    <div className="rounded-lg border border-[#3d5c8f]/50 bg-[#0c1628] p-4 hover:border-[#5aadaf]/50 transition-colors">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm text-[#8ba4b8]">{formatMetricName(metricType)}</span>
        <TrendIcon className={`w-4 h-4 ${trendColor}`} />
      </div>
      <div className="text-2xl font-bold text-[#c8dde8]">
        {latestValue.toLocaleString(undefined, { maximumFractionDigits: 1 })}
        {units && <span className="text-sm text-[#8ba4b8] ml-1">{units}</span>}
      </div>
      <div className="text-xs text-[#8ba4b8] mt-1">
        7d avg: {avg7d.toLocaleString(undefined, { maximumFractionDigits: 1 })}
        <span className={`ml-1 ${trendColor}`}>
          ({delta7d >= 0 ? "+" : ""}{delta7d.toFixed(1)})
        </span>
      </div>
    </div>
  );
}
