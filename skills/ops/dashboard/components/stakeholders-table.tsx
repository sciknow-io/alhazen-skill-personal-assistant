'use client';

import Link from 'next/link';

export interface StakeholderRow {
  dossier_id: string;
  person_id: string;
  person_name: string;
  relationship: string | null;
  current_state: string | null;
  touchpoint_count: number;
  last_touchpoint_date: string | null;
  last_undercurrent: string | null;
  open_commitments: number;
  overdue_commitments: number;
}

function fmtDate(d: string | null): string {
  return d ? String(d).slice(0, 10) : '—';
}

export function StakeholdersTable({ stakeholders }: { stakeholders: StakeholderRow[] }) {
  if (stakeholders.length === 0) {
    return (
      <p className="text-sm text-slate-400">
        No dossiers yet. Add one per person who matters: add-dossier --person.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <th className="px-3 py-2">Person</th>
            <th className="px-3 py-2">Relationship</th>
            <th className="px-3 py-2">Current State</th>
            <th className="px-3 py-2">Last Touchpoint</th>
            <th className="px-3 py-2 text-right">Open</th>
            <th className="px-3 py-2 text-right">Overdue</th>
          </tr>
        </thead>
        <tbody>
          {stakeholders.map((s) => (
            <tr key={s.dossier_id} className="border-b border-slate-100 last:border-0 hover:bg-slate-50">
              <td className="px-3 py-2">
                <Link
                  href={`/ops/stakeholder/${s.person_id}`}
                  className="font-medium text-blue-700 hover:underline"
                >
                  {s.person_name}
                </Link>
              </td>
              <td className="px-3 py-2">
                {s.relationship ? (
                  <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-700">
                    {s.relationship}
                  </span>
                ) : (
                  <span className="text-slate-300">—</span>
                )}
              </td>
              <td className="max-w-xs truncate px-3 py-2 text-slate-600" title={s.current_state || ''}>
                {s.current_state || '—'}
              </td>
              <td className="px-3 py-2 text-slate-600">
                {fmtDate(s.last_touchpoint_date)}
                <span className="ml-1 text-xs text-slate-400">({s.touchpoint_count})</span>
              </td>
              <td className="px-3 py-2 text-right text-slate-700">{s.open_commitments}</td>
              <td className="px-3 py-2 text-right">
                {s.overdue_commitments > 0 ? (
                  <span className="font-semibold text-red-600">{s.overdue_commitments}</span>
                ) : (
                  <span className="text-slate-300">0</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
