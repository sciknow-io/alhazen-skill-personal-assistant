'use client';

import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { MoreVertical, GitBranch, ListChecks, ShieldCheck, ShieldAlert } from 'lucide-react';

export interface Mission {
  id: string;
  name: string;
  status: string;
  decision_context: string | null;
  priority: string | null;
  run_count: number;
  finding_count: number;
  divergent_count: number;
  unverified_count: number;
  gate: { passed: boolean; recorded_at: string } | null;
}

interface MissionsBoardProps {
  missions: Mission[];
  onStatusChange: (missionId: string, newStatus: string) => void;
}

const STATUS_ORDER = [
  'briefing',
  'planning',
  'running',
  'aggregating',
  'verifying',
  'gated',
  'delivered',
];

const STATUS_COLORS: Record<string, string> = {
  briefing: 'bg-slate-100 text-slate-800',
  planning: 'bg-blue-100 text-blue-800',
  running: 'bg-purple-100 text-purple-800',
  aggregating: 'bg-amber-100 text-amber-800',
  verifying: 'bg-orange-100 text-orange-800',
  gated: 'bg-teal-100 text-teal-800',
  delivered: 'bg-green-100 text-green-800',
};

const PRIORITY_COLORS: Record<string, string> = {
  high: 'bg-red-500',
  medium: 'bg-yellow-500',
  low: 'bg-green-500',
};

function MissionCard({
  mission,
  onStatusChange,
}: {
  mission: Mission;
  onStatusChange: (missionId: string, newStatus: string) => void;
}) {
  return (
    <Card className="mb-1.5 hover:shadow-sm transition-shadow group">
      <CardContent className="p-2">
        <div className="flex items-center justify-between gap-1">
          <Link
            href={`/analyst/mission/${mission.id}`}
            className="flex-1 min-w-0 cursor-pointer"
          >
            <div className="flex items-center gap-1.5">
              {mission.priority === 'high' && (
                <div
                  className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${PRIORITY_COLORS[mission.priority]}`}
                  title="high priority"
                />
              )}
              <span
                className="text-xs font-medium group-hover:text-primary transition-colors truncate"
                title={mission.name}
              >
                {mission.name}
              </span>
            </div>
            {mission.decision_context && (
              <p
                className="text-[10px] text-muted-foreground truncate mt-0.5"
                title={mission.decision_context}
              >
                {mission.decision_context}
              </p>
            )}
          </Link>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-5 w-5 flex-shrink-0">
                <MoreVertical className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {STATUS_ORDER.filter((s) => s !== mission.status).map((s) => (
                <DropdownMenuItem key={s} onClick={() => onStatusChange(mission.id, s)}>
                  Move to {s}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        <div className="flex items-center gap-2 mt-1.5 text-[10px] text-muted-foreground">
          <span className="flex items-center gap-0.5" title="research runs">
            <GitBranch className="h-3 w-3" />
            {mission.run_count}
          </span>
          <span className="flex items-center gap-0.5" title="findings">
            <ListChecks className="h-3 w-3" />
            {mission.finding_count}
          </span>
          {mission.divergent_count > 0 && (
            <Badge variant="outline" className="text-[9px] px-1 py-0 border-amber-400 text-amber-700">
              {mission.divergent_count} divergent
            </Badge>
          )}
          {mission.gate &&
            (mission.gate.passed ? (
              <span className="flex items-center gap-0.5 text-teal-700" title="gate passed">
                <ShieldCheck className="h-3 w-3" />
              </span>
            ) : (
              <span className="flex items-center gap-0.5 text-red-600" title="gate failed">
                <ShieldAlert className="h-3 w-3" />
              </span>
            ))}
        </div>
      </CardContent>
    </Card>
  );
}

export function MissionsBoard({ missions, onStatusChange }: MissionsBoardProps) {
  return (
    <div className="grid grid-cols-7 gap-2 items-start">
      {STATUS_ORDER.map((status) => {
        const columnMissions = missions.filter((m) => m.status === status);
        return (
          <div key={status} className="min-w-0">
            <div className="flex items-center justify-between mb-1.5">
              <Badge className={`text-[10px] ${STATUS_COLORS[status] || ''}`} variant="secondary">
                {status}
              </Badge>
              <span className="text-[10px] text-muted-foreground">{columnMissions.length}</span>
            </div>
            {columnMissions.map((mission) => (
              <MissionCard key={mission.id} mission={mission} onStatusChange={onStatusChange} />
            ))}
          </div>
        );
      })}
    </div>
  );
}
