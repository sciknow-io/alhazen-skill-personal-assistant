'use client';

import { MessageCircle, Eye } from 'lucide-react';

export interface Touchpoint {
  id: string;
  name: string | null;
  content: string | null;
  interaction_type: string | null;
  interaction_date: string | null;
  undercurrent: string | null;
  commitments_made: string | null;
  created_at: string | null;
}

function fmtDate(d: string | null): string {
  return d ? String(d).slice(0, 10) : '—';
}

function unesc(s: string | null | undefined): string {
  return (s ?? '').replace(/\\n/g, '\n');
}

export function TouchpointTimeline({ touchpoints }: { touchpoints: Touchpoint[] }) {
  if (touchpoints.length === 0) {
    return (
      <p className="text-sm text-slate-400">
        No touchpoints logged. Log one after every meaningful interaction — with the undercurrent.
      </p>
    );
  }

  return (
    <ol className="relative ml-2 border-l border-slate-200">
      {touchpoints.map((tp) => (
        <li key={tp.id} className="mb-5 ml-4">
          <span className="absolute -left-[7px] mt-1.5 flex h-3.5 w-3.5 items-center justify-center rounded-full border border-white bg-slate-300" />
          <div className="flex items-center gap-2 text-xs text-slate-500">
            <span className="font-medium text-slate-700">
              {fmtDate(tp.interaction_date || tp.created_at)}
            </span>
            {tp.interaction_type && (
              <span className="flex items-center gap-1 rounded bg-slate-100 px-1.5 py-0.5">
                <MessageCircle className="w-3 h-3" />
                {tp.interaction_type}
              </span>
            )}
          </div>
          {tp.content && (
            <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{unesc(tp.content)}</p>
          )}
          {tp.undercurrent && (
            <div className="mt-2 flex items-start gap-2 rounded-md border border-violet-200 bg-violet-50 p-2">
              <Eye className="mt-0.5 w-3.5 h-3.5 flex-shrink-0 text-violet-500" />
              <p className="text-xs italic text-violet-800">{unesc(tp.undercurrent)}</p>
            </div>
          )}
          {tp.commitments_made && (
            <p className="mt-1.5 text-xs text-amber-700">
              <span className="font-semibold">Commitments made:</span> {unesc(tp.commitments_made)}
            </p>
          )}
        </li>
      ))}
    </ol>
  );
}
