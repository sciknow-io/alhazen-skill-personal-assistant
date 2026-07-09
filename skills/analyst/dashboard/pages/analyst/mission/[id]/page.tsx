'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ArrowLeft, Scale, Clock, Shield, Ban, Calendar } from 'lucide-react';
import { ConsensusMatrix, Finding, Run } from '@/components/analyst/consensus-matrix';
import { GatePanel, GateRecord } from '@/components/analyst/gate-panel';

/** Prepare TypeDB content for markdown rendering (unescape literal \n). */
function unesc(s: string | undefined | null): string {
  return (s ?? '').replace(/\\n/g, '\n');
}

interface NoteEntry {
  id: string;
  content: string;
  created_at: string;
}

interface Deliverable {
  id: string;
  name: string;
  format: string | null;
  created_at: string | null;
}

interface MissionDetail {
  success: boolean;
  mission: {
    id: string;
    name: string;
    description: string | null;
    status: string;
    decision_context: string | null;
    time_horizon: string | null;
    source_policy: string | null;
    exclusions: string | null;
    priority: string | null;
    deadline: string | null;
    decision_ref: string | null;
  };
  notes: Record<string, NoteEntry[]>;
  runs: Run[];
  findings: Finding[];
  gate: GateRecord | null;
  deliverables: Deliverable[];
}

const STATUS_COLORS: Record<string, string> = {
  briefing: 'bg-slate-100 text-slate-800',
  planning: 'bg-blue-100 text-blue-800',
  running: 'bg-purple-100 text-purple-800',
  aggregating: 'bg-amber-100 text-amber-800',
  verifying: 'bg-orange-100 text-orange-800',
  gated: 'bg-teal-100 text-teal-800',
  delivered: 'bg-green-100 text-green-800',
};

const NOTE_LABELS: Record<string, string> = {
  primer: 'Primer (operator brain dump)',
  interview: 'Operator Interview',
  plan: 'Research Plan',
  synthesis: 'Synthesis',
};

export default function MissionDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [detail, setDetail] = useState<MissionDetail | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchDetail = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch(`/api/analyst/mission/${id}`);
      if (!res.ok) throw new Error('Failed to fetch mission');
      const data = await res.json();
      setDetail(data);
    } catch (err) {
      console.error('Fetch error:', err);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchDetail();
  }, [fetchDetail]);

  if (loading) {
    return <p className="p-4 text-sm text-muted-foreground">Loading…</p>;
  }
  if (!detail || !detail.success) {
    return <p className="p-4 text-sm text-muted-foreground">Mission not found.</p>;
  }

  const { mission, notes, runs, findings, gate, deliverables } = detail;

  const quickInfo = [
    { icon: Scale, label: 'Decision', value: mission.decision_context },
    { icon: Clock, label: 'Time Horizon', value: mission.time_horizon },
    { icon: Shield, label: 'Source Policy', value: mission.source_policy },
    { icon: Ban, label: 'Exclusions', value: mission.exclusions },
    { icon: Calendar, label: 'Deadline', value: mission.deadline ? String(mission.deadline).slice(0, 10) : null },
  ].filter((q) => q.value);

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center gap-2">
        <Link href="/analyst" className="text-muted-foreground hover:text-primary">
          <ArrowLeft className="h-4 w-4" />
        </Link>
        <h1 className="text-xl font-semibold flex-1">{mission.name}</h1>
        {mission.priority && (
          <Badge variant="outline" className="text-xs">
            {mission.priority}
          </Badge>
        )}
        <Badge className={`text-xs ${STATUS_COLORS[mission.status] || ''}`} variant="secondary">
          {mission.status}
        </Badge>
      </div>

      {quickInfo.length > 0 && (
        <Card>
          <CardContent className="p-3 grid grid-cols-2 md:grid-cols-3 gap-3">
            {quickInfo.map((q) => (
              <div key={q.label} className="flex items-start gap-2">
                <q.icon className="h-3.5 w-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-[10px] text-muted-foreground">{q.label}</p>
                  <p className="text-xs">{q.value}</p>
                </div>
              </div>
            ))}
            {mission.decision_ref && (
              <div className="flex items-start gap-2">
                <Scale className="h-3.5 w-3.5 text-muted-foreground mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-[10px] text-muted-foreground">Advisor Decision (soft ref)</p>
                  <p className="text-xs font-mono">{mission.decision_ref}</p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <ConsensusMatrix findings={findings} runs={runs} />
          <GatePanel gate={gate} missionStatus={mission.status} />

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Deliverables ({deliverables.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {deliverables.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  None yet. Consider dashboard / infographic / interactive page / audio
                  summary — not just a wall of text.
                </p>
              ) : (
                <ul className="space-y-1">
                  {deliverables.map((d) => (
                    <li key={d.id} className="flex items-center gap-2 text-xs">
                      <Badge variant="secondary" className="text-[10px]">
                        {d.format || 'brief'}
                      </Badge>
                      <span>{d.name}</span>
                      <span className="text-muted-foreground ml-auto">
                        {d.created_at ? String(d.created_at).slice(0, 10) : ''}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Runs ({runs.length})</CardTitle>
            </CardHeader>
            <CardContent>
              {runs.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No runs yet. Fan out 3+ parallel runs with the same prompt.
                </p>
              ) : (
                <ul className="space-y-1.5">
                  {runs.map((r) => (
                    <li key={r.id} className="flex items-center gap-2 text-xs">
                      <span className="font-medium">{r.model || r.id}</span>
                      <Badge
                        variant="secondary"
                        className={`text-[10px] ml-auto ${
                          r.status === 'completed'
                            ? 'bg-green-100 text-green-800'
                            : r.status === 'failed'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-purple-100 text-purple-800'
                        }`}
                      >
                        {r.status || 'running'}
                      </Badge>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          {Object.entries(notes)
            .filter(([type]) => type !== 'gate')
            .map(([type, entries]) => (
              <Card key={type}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-sm">{NOTE_LABELS[type] || type}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {entries.map((n) => (
                    <div key={n.id} className="text-xs prose prose-xs max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {unesc(n.content)}
                      </ReactMarkdown>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ))}
        </div>
      </div>
    </div>
  );
}
