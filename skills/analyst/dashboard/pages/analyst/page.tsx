'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Compass, ListChecks, Package, AlertTriangle, ShieldCheck } from 'lucide-react';
import { MissionsBoard, Mission } from '@/components/analyst/missions-board';
import { FindingsTable, FindingRow } from '@/components/analyst/findings-table';

interface Deliverable {
  id: string;
  name: string;
  format: string | null;
  created_at: string | null;
}

interface MissionWithDeliverables extends Mission {
  deliverables: Deliverable[];
  created_at?: string;
}

type TabId = 'missions' | 'findings' | 'deliverables';

export default function AnalystHub() {
  const [missions, setMissions] = useState<MissionWithDeliverables[]>([]);
  const [findings, setFindings] = useState<FindingRow[]>([]);
  const [findingsLoaded, setFindingsLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>('missions');

  const fetchMissions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/analyst/missions');
      if (!res.ok) throw new Error('Failed to fetch missions');
      const data = await res.json();
      setMissions(data.missions || []);
    } catch (err) {
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchFindings = useCallback(async () => {
    try {
      const res = await fetch('/api/analyst/findings');
      if (!res.ok) throw new Error('Failed to fetch findings');
      const data = await res.json();
      setFindings(data.findings || []);
      setFindingsLoaded(true);
    } catch (err) {
      console.error('Fetch error:', err);
    }
  }, []);

  useEffect(() => {
    fetchMissions();
  }, [fetchMissions]);

  useEffect(() => {
    if (activeTab === 'findings' && !findingsLoaded) fetchFindings();
  }, [activeTab, findingsLoaded, fetchFindings]);

  const handleStatusChange = async (missionId: string, newStatus: string) => {
    try {
      await fetch('/api/analyst/missions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: missionId, status: newStatus }),
      });
      fetchMissions();
    } catch (err) {
      console.error('Status change error:', err);
    }
  };

  const stats = {
    total: missions.length,
    active: missions.filter((m) => m.status !== 'delivered').length,
    divergent: missions.reduce((acc, m) => acc + (m.divergent_count || 0), 0),
    unverified: missions.reduce((acc, m) => acc + (m.unverified_count || 0), 0),
    delivered: missions.filter((m) => m.status === 'delivered').length,
  };

  const statCards = [
    { label: 'Missions', value: stats.total, icon: Compass, color: 'text-slate-600', bg: 'bg-slate-100' },
    { label: 'Active', value: stats.active, icon: ListChecks, color: 'text-blue-600', bg: 'bg-blue-100' },
    { label: 'Divergent Claims', value: stats.divergent, icon: AlertTriangle, color: 'text-amber-600', bg: 'bg-amber-100' },
    { label: 'Unverified', value: stats.unverified, icon: ShieldCheck, color: 'text-orange-600', bg: 'bg-orange-100' },
    { label: 'Delivered', value: stats.delivered, icon: Package, color: 'text-green-600', bg: 'bg-green-100' },
  ];

  const deliverables = missions.flatMap((m) =>
    (m.deliverables || []).map((d) => ({ ...d, mission_id: m.id, mission_name: m.name }))
  );

  const tabs: Array<{ id: TabId; label: string; icon: typeof Compass }> = [
    { id: 'missions', label: 'Missions', icon: Compass },
    { id: 'findings', label: 'Findings', icon: ListChecks },
    { id: 'deliverables', label: 'Deliverables', icon: Package },
  ];

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">Analyst — Research Missions</h1>
        <span className="text-xs text-muted-foreground">
          brief → interview → plan → 3+ runs → consensus → verify → gate → deliver
        </span>
      </div>

      <div className="grid grid-cols-5 gap-2">
        {statCards.map((s) => (
          <Card key={s.label}>
            <CardContent className="p-3 flex items-center gap-2">
              <div className={`p-1.5 rounded ${s.bg}`}>
                <s.icon className={`h-4 w-4 ${s.color}`} />
              </div>
              <div>
                <p className="text-lg font-semibold leading-none">{s.value}</p>
                <p className="text-[10px] text-muted-foreground">{s.label}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="flex gap-1 border-b">
        {tabs.map((t) => (
          <Button
            key={t.id}
            variant="ghost"
            size="sm"
            className={`rounded-none border-b-2 text-xs ${
              activeTab === t.id ? 'border-primary text-primary' : 'border-transparent'
            }`}
            onClick={() => setActiveTab(t.id)}
          >
            <t.icon className="h-3.5 w-3.5 mr-1" />
            {t.label}
          </Button>
        ))}
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground py-8 text-center">Loading…</p>
      ) : activeTab === 'missions' ? (
        <MissionsBoard missions={missions} onStatusChange={handleStatusChange} />
      ) : activeTab === 'findings' ? (
        <FindingsTable findings={findings} />
      ) : (
        <div>
          {deliverables.length === 0 ? (
            <p className="text-xs text-muted-foreground py-4">
              No deliverables yet. Remember: not every deliverable is a wall of text —
              consider a dashboard, infographic, interactive page, or audio summary.
            </p>
          ) : (
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left">
                  <th className="py-1.5 pr-2 font-medium">Deliverable</th>
                  <th className="py-1.5 px-2 font-medium">Format</th>
                  <th className="py-1.5 px-2 font-medium">Mission</th>
                  <th className="py-1.5 px-2 font-medium">Created</th>
                </tr>
              </thead>
              <tbody>
                {deliverables.map((d) => (
                  <tr key={d.id} className="border-b last:border-0">
                    <td className="py-1.5 pr-2">{d.name}</td>
                    <td className="py-1.5 px-2">
                      <Badge variant="secondary" className="text-[10px]">
                        {d.format || 'brief'}
                      </Badge>
                    </td>
                    <td className="py-1.5 px-2">
                      <Link
                        href={`/analyst/mission/${d.mission_id}`}
                        className="text-primary hover:underline"
                      >
                        {d.mission_name}
                      </Link>
                    </td>
                    <td className="py-1.5 px-2 text-muted-foreground">
                      {d.created_at ? String(d.created_at).slice(0, 10) : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
