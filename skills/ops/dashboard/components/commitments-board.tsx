'use client';

import { AlertTriangle } from 'lucide-react';
import type { CommitmentItem } from './today-panel';

const COLUMN_ORDER = ['open', 'overdue', 'done', 'dropped'];

const COLUMN_LABELS: Record<string, string> = {
  open: 'Open',
  overdue: 'Overdue',
  done: 'Done',
  dropped: 'Dropped',
};

const COLUMN_STYLES: Record<string, string> = {
  open: 'border-blue-200',
  overdue: 'border-red-300',
  done: 'border-green-200',
  dropped: 'border-slate-200',
};

const NEXT_ACTIONS: Record<string, Array<{ label: string; status: string }>> = {
  open: [
    { label: 'Done', status: 'done' },
    { label: 'Overdue', status: 'overdue' },
    { label: 'Drop', status: 'dropped' },
  ],
  overdue: [
    { label: 'Done', status: 'done' },
    { label: 'Drop', status: 'dropped' },
  ],
  done: [{ label: 'Reopen', status: 'open' }],
  dropped: [{ label: 'Reopen', status: 'open' }],
};

function CommitmentCard({
  commitment,
  onStatusChange,
}: {
  commitment: CommitmentItem;
  onStatusChange?: (id: string, status: string) => void;
}) {
  const lateOpen = commitment.overdue && commitment.status === 'open';
  return (
    <div
      className={`mb-2 rounded-md border bg-white p-2 shadow-sm ${lateOpen ? 'border-red-300' : 'border-slate-200'}`}
    >
      <div className="flex items-start justify-between gap-1">
        <span className="text-xs font-medium text-slate-800">{commitment.name}</span>
        {lateOpen && <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0 text-red-500" />}
      </div>
      <div className="mt-1 flex items-center gap-1.5">
        <span
          className={`rounded px-1 py-0.5 text-[10px] font-semibold ${
            commitment.owed_by === 'me' ? 'bg-amber-100 text-amber-800' : 'bg-blue-100 text-blue-800'
          }`}
        >
          {commitment.owed_by === 'me' ? 'ME' : 'THEM'}
        </span>
        <span className="text-[11px] text-slate-500">{commitment.person_name}</span>
        {commitment.due_date && (
          <span className={`text-[11px] ${lateOpen ? 'text-red-600' : 'text-slate-400'}`}>
            due {String(commitment.due_date).slice(0, 10)}
          </span>
        )}
      </div>
      {onStatusChange && (
        <div className="mt-1.5 flex gap-1">
          {(NEXT_ACTIONS[commitment.status] || []).map((a) => (
            <button
              key={a.status}
              className="rounded border border-slate-200 px-1.5 py-0.5 text-[10px] text-slate-600 hover:bg-slate-50"
              onClick={() => onStatusChange(commitment.id, a.status)}
            >
              {a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export function CommitmentsBoard({
  commitments,
  onStatusChange,
}: {
  commitments: CommitmentItem[];
  onStatusChange?: (id: string, status: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
      {COLUMN_ORDER.map((status) => {
        const items = commitments.filter((c) => c.status === status);
        return (
          <div key={status} className={`rounded-lg border-t-4 bg-slate-50 p-2 ${COLUMN_STYLES[status]}`}>
            <div className="mb-2 flex items-center justify-between px-1">
              <span className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                {COLUMN_LABELS[status]}
              </span>
              <span className="text-xs text-slate-400">{items.length}</span>
            </div>
            {items.length === 0 ? (
              <p className="px-1 pb-2 text-[11px] text-slate-300">Empty</p>
            ) : (
              items.map((c) => (
                <CommitmentCard key={c.id} commitment={c} onStatusChange={onStatusChange} />
              ))
            )}
          </div>
        );
      })}
    </div>
  );
}
