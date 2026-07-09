'use client';

import { useState } from 'react';
import { ChevronDown, ChevronRight, Bot, Hand } from 'lucide-react';

export interface Spec {
  id: string;
  name: string;
  status: string;
  cadence: string | null;
  sections: string | null;
  sources: string | null;
  dream_rationale: string | null;
  trial_runs: number;
  trial_target: number;
  brief_count: number;
  last_brief_date: string | null;
}

export interface BriefInstance {
  id: string;
  name: string | null;
  date: string | null;
  produced_manually: boolean;
  content?: string;
}

const STATUS_COLORS: Record<string, string> = {
  designed: 'bg-slate-100 text-slate-700',
  trial: 'bg-amber-100 text-amber-800',
  active: 'bg-green-100 text-green-800',
  retired: 'bg-gray-100 text-gray-500',
};

function TrialProgressBar({ runs, target }: { runs: number; target: number }) {
  const pct = Math.min(100, Math.round((runs / Math.max(target, 1)) * 100));
  return (
    <div className="mt-2">
      <div className="flex justify-between text-xs text-slate-500 mb-1">
        <span>Manual trial runs</span>
        <span>
          {runs}/{target}
        </span>
      </div>
      <div className="h-2 w-full rounded-full bg-slate-100">
        <div
          className={`h-2 rounded-full transition-all ${pct >= 100 ? 'bg-green-500' : 'bg-amber-400'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      {pct >= 100 && (
        <p className="mt-1 text-xs text-green-600">Trial target met — eligible for promote-spec.</p>
      )}
    </div>
  );
}

export function SpecsList({
  specs,
  onLoadBriefs,
}: {
  specs: Spec[];
  onLoadBriefs?: (specId: string) => Promise<BriefInstance[]>;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [instances, setInstances] = useState<Record<string, BriefInstance[]>>({});

  const toggle = async (specId: string) => {
    if (expanded === specId) {
      setExpanded(null);
      return;
    }
    setExpanded(specId);
    if (onLoadBriefs && !instances[specId]) {
      try {
        const briefs = await onLoadBriefs(specId);
        setInstances((prev) => ({ ...prev, [specId]: briefs }));
      } catch {
        setInstances((prev) => ({ ...prev, [specId]: [] }));
      }
    }
  };

  if (specs.length === 0) {
    return (
      <p className="text-sm text-slate-400">
        No brief specs yet. Design one dream-first: what would you build with unlimited headcount?
      </p>
    );
  }

  return (
    <div className="space-y-3">
      {specs.map((spec) => (
        <div key={spec.id} className="rounded-lg border border-slate-200 bg-white p-4">
          <button
            className="flex w-full items-start justify-between text-left"
            onClick={() => toggle(spec.id)}
          >
            <div>
              <div className="flex items-center gap-2">
                {expanded === spec.id ? (
                  <ChevronDown className="w-4 h-4 text-slate-400" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-slate-400" />
                )}
                <span className="font-medium text-slate-800">{spec.name}</span>
                <span
                  className={`rounded px-1.5 py-0.5 text-xs font-medium ${STATUS_COLORS[spec.status] || 'bg-slate-100 text-slate-700'}`}
                >
                  {spec.status}
                </span>
              </div>
              <p className="ml-6 mt-1 text-xs text-slate-500">
                {spec.cadence || 'daily'} · {spec.brief_count} instance{spec.brief_count === 1 ? '' : 's'}
                {spec.last_brief_date ? ` · last ${String(spec.last_brief_date).slice(0, 10)}` : ''}
              </p>
              {spec.dream_rationale && (
                <p className="ml-6 mt-1 text-xs italic text-slate-400">“{spec.dream_rationale}”</p>
              )}
            </div>
          </button>

          {(spec.status === 'designed' || spec.status === 'trial') && (
            <div className="ml-6">
              <TrialProgressBar runs={spec.trial_runs} target={spec.trial_target} />
            </div>
          )}

          {expanded === spec.id && (
            <div className="ml-6 mt-3 border-t border-slate-100 pt-3">
              {spec.sections && (
                <p className="text-xs text-slate-500 mb-1">
                  <span className="font-medium">Sections:</span> {spec.sections}
                </p>
              )}
              {spec.sources && (
                <p className="text-xs text-slate-500 mb-2">
                  <span className="font-medium">Sources:</span> {spec.sources}
                </p>
              )}
              {(instances[spec.id] || []).length === 0 ? (
                <p className="text-xs text-slate-400">No brief instances loaded.</p>
              ) : (
                <ul className="space-y-1">
                  {(instances[spec.id] || []).map((b) => (
                    <li key={b.id} className="flex items-center gap-2 text-xs text-slate-600">
                      {b.produced_manually ? (
                        <Hand className="w-3 h-3 text-amber-500" aria-label="manual" />
                      ) : (
                        <Bot className="w-3 h-3 text-blue-500" aria-label="automated" />
                      )}
                      <span>{b.name || b.id}</span>
                      <span className="text-slate-400">{b.date ? String(b.date).slice(0, 10) : ''}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
