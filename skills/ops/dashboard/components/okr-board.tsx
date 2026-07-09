'use client';

import { useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  Check,
  Loader2,
  Ban,
  Circle,
  CircleDashed,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────

export interface Objective {
  id: string;
  name: string;
  status: string; // draft | active | at-risk | met | missed | dropped
  period: string;
}

export interface WorkItem {
  id: string;
  name: string;
  kind: string; // story | task | subtask
  status: string; // not-started | in-progress | blocked | done | dropped
  children: WorkItem[];
  provider?: string | null; // github | jira | monday (if imported from a tracker)
  uri?: string | null;
  last_synced?: string | null;
}

function syncAge(iso?: string | null): string | null {
  if (!iso) return null;
  const then = new Date(String(iso).replace(' ', 'T'));
  if (isNaN(then.getTime())) return null;
  const days = Math.floor((Date.now() - then.getTime()) / 86400000);
  return days <= 0 ? 'today' : `${days}d ago`;
}

export interface KeyResult {
  id: string;
  name: string;
  status: string; // on-track | at-risk | off-track | met | missed
  metric: string;
  current: string;
  target_date: string | null;
  workitems: WorkItem[];
}

export interface TreeResponse {
  success: boolean;
  objective: Objective;
  key_results: KeyResult[];
  progress: { done: number; total: number; percent: number };
}

// ── Status palettes ─────────────────────────────────────────────────────────

const OBJECTIVE_STATUS_COLORS: Record<string, string> = {
  active: 'bg-teal-100 text-teal-800',
  'at-risk': 'bg-amber-100 text-amber-800',
  draft: 'bg-slate-100 text-slate-700',
  met: 'bg-green-100 text-green-800',
  missed: 'bg-gray-100 text-gray-500',
  dropped: 'bg-gray-100 text-gray-500',
};

const KR_STATUS_COLORS: Record<string, string> = {
  'on-track': 'bg-teal-100 text-teal-800',
  'at-risk': 'bg-amber-100 text-amber-800',
  'off-track': 'bg-red-100 text-red-800',
  met: 'bg-green-100 text-green-800',
  missed: 'bg-gray-100 text-gray-500',
};

const WORKITEM_STATUS: Record<
  string,
  { icon: React.ComponentType<{ className?: string }>; color: string; label: string }
> = {
  done: { icon: Check, color: 'text-green-600', label: 'done' },
  'in-progress': { icon: Loader2, color: 'text-amber-500', label: 'in progress' },
  blocked: { icon: Ban, color: 'text-red-500', label: 'blocked' },
  'not-started': { icon: CircleDashed, color: 'text-slate-400', label: 'not started' },
  dropped: { icon: Circle, color: 'text-slate-300', label: 'dropped' },
};

function ProgressBar({
  done,
  total,
  percent,
}: {
  done: number;
  total: number;
  percent: number;
}) {
  const pct = Math.min(100, Math.max(0, Math.round(percent)));
  return (
    <div className="mt-2">
      <div className="mb-1 flex justify-between text-xs text-slate-500">
        <span>Progress</span>
        <span>
          {done}/{total} ({pct}%)
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-slate-100">
        <div
          className={`h-2 rounded-full transition-all ${pct >= 100 ? 'bg-green-500' : 'bg-teal-400'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function WorkItemNode({ item, depth }: { item: WorkItem; depth: number }) {
  const meta = WORKITEM_STATUS[item.status] || WORKITEM_STATUS['not-started'];
  const Icon = meta.icon;
  return (
    <li>
      <div
        className="flex items-center gap-1.5 py-0.5 text-xs text-slate-600"
        style={{ paddingLeft: `${depth * 16}px` }}
      >
        <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${meta.color}`} aria-label={meta.label} />
        <span className={item.status === 'done' ? 'text-slate-400 line-through' : ''}>
          {item.name}
        </span>
        <span className="rounded bg-slate-100 px-1 py-0.5 text-[10px] uppercase tracking-wide text-slate-500">
          {item.kind}
        </span>
        {item.provider && item.uri && (
          <a
            href={item.uri}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-0.5 rounded bg-indigo-50 px-1 py-0.5 text-[10px] uppercase tracking-wide text-indigo-600 hover:bg-indigo-100"
            title={`Imported from ${item.provider}${item.last_synced ? ` · synced ${syncAge(item.last_synced)}` : ''}`}
          >
            {item.provider} ↗
            {syncAge(item.last_synced) && (
              <span className="normal-case text-indigo-400">· {syncAge(item.last_synced)}</span>
            )}
          </a>
        )}
      </div>
      {item.children && item.children.length > 0 && (
        <ul>
          {item.children.map((child) => (
            <WorkItemNode key={child.id} item={child} depth={depth + 1} />
          ))}
        </ul>
      )}
    </li>
  );
}

function KeyResultBlock({ kr }: { kr: KeyResult }) {
  return (
    <div className="border-t border-slate-100 pt-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <span className="text-sm font-medium text-slate-800">{kr.name}</span>
          <p className="mt-0.5 text-xs text-slate-500">
            {kr.metric}
            {kr.current ? <span> · current {kr.current}</span> : null}
            {kr.target_date ? (
              <span> · target {String(kr.target_date).slice(0, 10)}</span>
            ) : null}
          </p>
        </div>
        <span
          className={`flex-shrink-0 rounded px-1.5 py-0.5 text-xs font-medium ${
            KR_STATUS_COLORS[kr.status] || 'bg-slate-100 text-slate-700'
          }`}
        >
          {kr.status}
        </span>
      </div>
      {kr.workitems && kr.workitems.length > 0 && (
        <ul className="mt-2">
          {kr.workitems.map((wi) => (
            <WorkItemNode key={wi.id} item={wi} depth={0} />
          ))}
        </ul>
      )}
    </div>
  );
}

function ObjectiveCard({ objective }: { objective: Objective }) {
  const [expanded, setExpanded] = useState(false);
  const [tree, setTree] = useState<TreeResponse | null>(null);
  const [loading, setLoading] = useState(false);

  const toggle = async () => {
    if (expanded) {
      setExpanded(false);
      return;
    }
    setExpanded(true);
    if (!tree) {
      setLoading(true);
      try {
        const res = await fetch(`/api/ops/tree/${encodeURIComponent(objective.id)}`);
        const data = (await res.json()) as TreeResponse;
        setTree(data);
      } catch {
        setTree(null);
      } finally {
        setLoading(false);
      }
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <button className="flex w-full items-start justify-between text-left" onClick={toggle}>
        <div>
          <div className="flex items-center gap-2">
            {expanded ? (
              <ChevronDown className="w-4 h-4 text-slate-400" />
            ) : (
              <ChevronRight className="w-4 h-4 text-slate-400" />
            )}
            <span className="font-medium text-slate-800">{objective.name}</span>
            <span
              className={`rounded px-1.5 py-0.5 text-xs font-medium ${
                OBJECTIVE_STATUS_COLORS[objective.status] || 'bg-slate-100 text-slate-700'
              }`}
            >
              {objective.status}
            </span>
          </div>
          <p className="ml-6 mt-1 text-xs text-slate-500">{objective.period}</p>
        </div>
      </button>

      {tree?.progress && (
        <div className="ml-6">
          <ProgressBar
            done={tree.progress.done}
            total={tree.progress.total}
            percent={tree.progress.percent}
          />
        </div>
      )}

      {expanded && (
        <div className="ml-6 mt-3 space-y-3">
          {loading ? (
            <p className="text-xs text-slate-400">Loading…</p>
          ) : !tree || (tree.key_results || []).length === 0 ? (
            <p className="text-xs text-slate-400">No key results yet.</p>
          ) : (
            tree.key_results.map((kr) => <KeyResultBlock key={kr.id} kr={kr} />)
          )}
        </div>
      )}
    </div>
  );
}

export function OkrBoard({ objectives }: { objectives: Objective[] }) {
  if (objectives.length === 0) {
    return (
      <p className="text-sm text-slate-400">
        No objectives yet. What must be true in the first 90 days? Define an objective to start.
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {objectives.map((o) => (
        <ObjectiveCard key={o.id} objective={o} />
      ))}
    </div>
  );
}
