'use client';

import { use, useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowLeft, Compass, Handshake, Clock } from 'lucide-react';
import { TouchpointTimeline, Touchpoint } from '@/components/ops/touchpoint-timeline';
import type { CommitmentItem } from '@/components/ops/today-panel';

interface Dossier {
  id: string;
  name: string | null;
  relationship: string | null;
  current_state: string | null;
  history_summary: string | null;
}

interface PrepPack {
  id: string;
  meeting_title: string | null;
  meeting_date: string | null;
  content: string | null;
}

interface StakeholderData {
  success: boolean;
  person?: { id: string; name: string };
  dossier?: Dossier | null;
  touchpoints?: Touchpoint[];
  commitments?: CommitmentItem[];
  open_commitments?: CommitmentItem[];
  meeting_preps?: PrepPack[];
  error?: string;
}

function fmtDate(d: string | null | undefined): string {
  return d ? String(d).slice(0, 10) : '—';
}

function unesc(s: string | null | undefined): string {
  return (s ?? '').replace(/\\n/g, '\n');
}

export default function StakeholderDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<StakeholderData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/ops/stakeholder/${encodeURIComponent(id)}`)
      .then((r) => r.json())
      .then(setData)
      .catch((err) => console.error('Stakeholder fetch error:', err))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <p className="p-8 text-center text-sm text-slate-400">Loading…</p>;
  }
  if (!data || !data.success || !data.person) {
    return (
      <div className="p-8 text-center">
        <p className="text-sm text-red-600">{data?.error || 'Stakeholder not found'}</p>
        <Link href="/ops" className="mt-2 inline-block text-sm text-blue-700 hover:underline">
          Back to Ops
        </Link>
      </div>
    );
  }

  const dossier = data.dossier;
  const touchpoints = data.touchpoints || [];
  const commitments = data.commitments || [];
  const openCount = (data.open_commitments || []).length;
  const lastTouchpoint = touchpoints[0];

  return (
    <div className="mx-auto max-w-5xl p-6">
      <Link href="/ops" className="mb-3 inline-flex items-center gap-1 text-sm text-blue-700 hover:underline">
        <ArrowLeft className="w-3.5 h-3.5" /> Ops
      </Link>

      <div className="mb-4">
        <h1 className="text-2xl font-bold text-slate-800">{data.person.name}</h1>
        {dossier?.relationship && (
          <span className="mt-1 inline-block rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700">
            {dossier.relationship}
          </span>
        )}
      </div>

      <div className="mb-6 grid gap-3 sm:grid-cols-3">
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Compass className="w-3.5 h-3.5" /> Current State
          </div>
          <p className="mt-1 text-sm text-slate-700">{dossier?.current_state || '—'}</p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Handshake className="w-3.5 h-3.5" /> Open Commitments
          </div>
          <p className="mt-1 text-sm font-semibold text-slate-700">{openCount}</p>
        </div>
        <div className="rounded-lg border border-slate-200 bg-white p-3">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Clock className="w-3.5 h-3.5" /> Last Touchpoint
          </div>
          <p className="mt-1 text-sm text-slate-700">
            {lastTouchpoint ? fmtDate(lastTouchpoint.interaction_date || lastTouchpoint.created_at) : 'never'}
          </p>
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          {dossier?.history_summary && (
            <div className="mb-5 rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="mb-2 text-sm font-semibold text-slate-700">Dossier — how we got here</h2>
              <p className="whitespace-pre-wrap text-sm text-slate-600">{unesc(dossier.history_summary)}</p>
            </div>
          )}
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Touchpoints</h2>
          <TouchpointTimeline touchpoints={touchpoints} />
        </div>

        <div>
          <h2 className="mb-3 text-sm font-semibold text-slate-700">Commitments</h2>
          {commitments.length === 0 ? (
            <p className="text-sm text-slate-400">None tracked.</p>
          ) : (
            <ul className="space-y-2">
              {commitments.map((c) => (
                <li key={c.id} className="rounded-md border border-slate-200 bg-white p-2">
                  <p className="text-xs font-medium text-slate-800">{c.name}</p>
                  <div className="mt-1 flex items-center gap-1.5 text-[11px]">
                    <span
                      className={`rounded px-1 py-0.5 font-semibold ${
                        c.owed_by === 'me' ? 'bg-amber-100 text-amber-800' : 'bg-blue-100 text-blue-800'
                      }`}
                    >
                      {c.owed_by === 'me' ? 'ME' : 'THEM'}
                    </span>
                    <span className="text-slate-500">{c.status}</span>
                    {c.due_date && (
                      <span className={c.overdue ? 'text-red-600' : 'text-slate-400'}>
                        due {fmtDate(c.due_date)}
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}

          <h2 className="mb-3 mt-6 text-sm font-semibold text-slate-700">Recent Meeting Preps</h2>
          {(data.meeting_preps || []).length === 0 ? (
            <p className="text-sm text-slate-400">No preps on file.</p>
          ) : (
            <ul className="space-y-2">
              {(data.meeting_preps || []).map((p) => (
                <li key={p.id} className="rounded-md border border-slate-200 bg-white p-2">
                  <p className="text-xs font-medium text-slate-800">{p.meeting_title || 'Untitled'}</p>
                  <p className="text-[11px] text-slate-400">{fmtDate(p.meeting_date)}</p>
                  {p.content && (
                    <details className="mt-1">
                      <summary className="cursor-pointer text-[11px] text-blue-700">view prep</summary>
                      <p className="mt-1 whitespace-pre-wrap text-xs text-slate-600">{unesc(p.content)}</p>
                    </details>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
