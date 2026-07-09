'use client';

import { useCallback, useEffect, useState } from 'react';
import { Target, Sunrise, Newspaper, Users, Handshake, Radar } from 'lucide-react';
import { TodayPanel, TodayData, CommitmentItem, MonitorItem } from '@/components/ops/today-panel';
import { SpecsList, Spec, BriefInstance } from '@/components/ops/specs-list';
import { StakeholdersTable, StakeholderRow } from '@/components/ops/stakeholders-table';
import { CommitmentsBoard } from '@/components/ops/commitments-board';
import { OkrBoard, Objective } from '@/components/ops/okr-board';

type TabId = 'okrs' | 'today' | 'briefs' | 'stakeholders' | 'commitments' | 'monitors';

const TABS: Array<{ id: TabId; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { id: 'okrs', label: 'OKRs', icon: Target },
  { id: 'today', label: 'Today', icon: Sunrise },
  { id: 'briefs', label: 'Briefs', icon: Newspaper },
  { id: 'stakeholders', label: 'Stakeholders', icon: Users },
  { id: 'commitments', label: 'Commitments', icon: Handshake },
  { id: 'monitors', label: 'Monitors', icon: Radar },
];

function fmtDate(d: string | null | undefined): string {
  return d ? String(d).slice(0, 10) : '—';
}

export default function OpsHub() {
  const [activeTab, setActiveTab] = useState<TabId>('okrs');
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [today, setToday] = useState<TodayData | null>(null);
  const [specs, setSpecs] = useState<Spec[]>([]);
  const [stakeholders, setStakeholders] = useState<StakeholderRow[]>([]);
  const [commitments, setCommitments] = useState<CommitmentItem[]>([]);
  const [monitors, setMonitors] = useState<MonitorItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState<Set<TabId>>(new Set());

  const loadTab = useCallback(async (tab: TabId) => {
    setLoading(true);
    try {
      if (tab === 'okrs') {
        const res = await fetch('/api/ops/objectives');
        const data = await res.json();
        setObjectives(data.objectives || []);
      } else if (tab === 'today') {
        const res = await fetch('/api/ops/today');
        setToday(await res.json());
      } else if (tab === 'briefs') {
        const res = await fetch('/api/ops/specs');
        const data = await res.json();
        setSpecs(data.specs || []);
      } else if (tab === 'stakeholders') {
        const res = await fetch('/api/ops/stakeholders');
        const data = await res.json();
        setStakeholders(data.stakeholders || []);
      } else if (tab === 'commitments') {
        const res = await fetch('/api/ops/commitments');
        const data = await res.json();
        setCommitments(data.commitments || []);
      } else if (tab === 'monitors') {
        const res = await fetch('/api/ops/monitors');
        const data = await res.json();
        setMonitors(data.monitors || []);
      }
      setLoaded((prev) => new Set(prev).add(tab));
    } catch (err) {
      console.error('Ops tab load error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTab('okrs');
  }, [loadTab]);

  const switchTab = (tab: TabId) => {
    setActiveTab(tab);
    if (!loaded.has(tab)) loadTab(tab);
  };

  const loadBriefs = useCallback(async (specId: string): Promise<BriefInstance[]> => {
    const res = await fetch(`/api/ops/briefs?spec=${encodeURIComponent(specId)}`);
    const data = await res.json();
    return data.briefs || [];
  }, []);

  const handleCommitmentStatus = useCallback(async (id: string, status: string) => {
    await fetch('/api/ops/commitments', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id, status }),
    });
    const res = await fetch('/api/ops/commitments');
    const data = await res.json();
    setCommitments(data.commitments || []);
  }, []);

  return (
    <div className="mx-auto max-w-6xl p-6">
      <h1 className="mb-1 text-2xl font-bold text-slate-800">Ops</h1>
      <p className="mb-4 text-sm text-slate-500">
        The operational powerhouse: OKRs, briefs, stakeholder CRM, commitments, monitors.
      </p>

      <div className="mb-4 flex gap-1 border-b border-slate-200">
        {TABS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => switchTab(id)}
            className={`flex items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium transition-colors ${
              activeTab === id
                ? 'border-blue-600 text-blue-700'
                : 'border-transparent text-slate-500 hover:text-slate-700'
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {loading && !loaded.has(activeTab) ? (
        <p className="py-8 text-center text-sm text-slate-400">Loading…</p>
      ) : (
        <>
          {activeTab === 'okrs' && <OkrBoard objectives={objectives} />}

          {activeTab === 'today' && today && <TodayPanel data={today} />}

          {activeTab === 'briefs' && <SpecsList specs={specs} onLoadBriefs={loadBriefs} />}

          {activeTab === 'stakeholders' && <StakeholdersTable stakeholders={stakeholders} />}

          {activeTab === 'commitments' && (
            <CommitmentsBoard commitments={commitments} onStatusChange={handleCommitmentStatus} />
          )}

          {activeTab === 'monitors' && (
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-3 py-2">Monitor</th>
                    <th className="px-3 py-2">Question</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Last Checked</th>
                  </tr>
                </thead>
                <tbody>
                  {monitors.length === 0 ? (
                    <tr>
                      <td colSpan={4} className="px-3 py-4 text-center text-slate-400">
                        No monitors. What standing question would unlimited headcount answer for you?
                      </td>
                    </tr>
                  ) : (
                    monitors.map((m) => (
                      <tr key={m.id} className="border-b border-slate-100 last:border-0">
                        <td className="px-3 py-2 font-medium text-slate-800">{m.name || '—'}</td>
                        <td className="px-3 py-2 text-slate-600">{m.question || '—'}</td>
                        <td className="px-3 py-2">
                          {m.stale ? (
                            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800">
                              stale
                            </span>
                          ) : (
                            <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">
                              fresh
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-slate-600">
                          {m.last_checked ? fmtDate(m.last_checked) : 'never'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
