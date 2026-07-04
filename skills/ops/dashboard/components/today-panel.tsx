'use client';

import { AlertTriangle, CalendarClock, Newspaper, Radar, Handshake } from 'lucide-react';

export interface BriefDue {
  spec_id: string;
  name: string;
  cadence: string | null;
  status: string;
  trial_runs: number | null;
  trial_target: number | null;
  last_brief: string | null;
  mode: string;
}

export interface CommitmentItem {
  id: string;
  name: string;
  owed_by: string;
  due_date: string | null;
  status: string;
  person_name: string;
  overdue: boolean;
}

export interface PrepItem {
  id: string;
  meeting_title: string | null;
  meeting_date: string;
}

export interface MonitorItem {
  id: string;
  name: string | null;
  question: string | null;
  last_checked: string | null;
  stale: boolean;
}

export interface TodayData {
  date: string;
  briefs_due: BriefDue[];
  overdue_commitments: CommitmentItem[];
  commitments_due_soon: CommitmentItem[];
  open_commitments: CommitmentItem[];
  upcoming_meeting_preps: PrepItem[];
  stale_monitors: MonitorItem[];
}

function fmtDate(d: string | null | undefined): string {
  return d ? String(d).slice(0, 10) : '—';
}

function owedLabel(c: CommitmentItem): string {
  return c.owed_by === 'me' ? `You owe ${c.person_name}` : `${c.person_name} owes you`;
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2 mb-3">
        <Icon className="w-4 h-4 text-slate-500" />
        <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
      </div>
      {children}
    </div>
  );
}

export function TodayPanel({ data }: { data: TodayData }) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Section icon={Newspaper} title="Briefs due">
        {data.briefs_due.length === 0 ? (
          <p className="text-sm text-slate-400">None due.</p>
        ) : (
          <ul className="space-y-2">
            {data.briefs_due.map((b) => (
              <li key={b.spec_id} className="text-sm">
                <span className="font-medium text-slate-800">{b.name}</span>
                <span className="text-slate-500"> ({b.cadence || 'daily'}, last: {fmtDate(b.last_brief) === '—' ? 'never' : fmtDate(b.last_brief)})</span>
                {b.status === 'trial' && (
                  <span className="ml-2 inline-block rounded bg-amber-100 px-1.5 py-0.5 text-xs font-medium text-amber-800">
                    TRIAL {b.trial_runs ?? 0}/{b.trial_target ?? 7} — run manually
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section icon={Handshake} title="Commitments">
        {data.overdue_commitments.length === 0 && data.commitments_due_soon.length === 0 ? (
          <p className="text-sm text-slate-400">Nothing overdue or imminent.</p>
        ) : (
          <ul className="space-y-2">
            {data.overdue_commitments.map((c) => (
              <li key={c.id} className="flex items-start gap-2 text-sm">
                <AlertTriangle className="mt-0.5 w-3.5 h-3.5 flex-shrink-0 text-red-500" />
                <span>
                  <span className="font-medium text-red-700">{c.name}</span>
                  <span className="text-slate-500"> — {owedLabel(c)}, due {fmtDate(c.due_date)}</span>
                </span>
              </li>
            ))}
            {data.commitments_due_soon.map((c) => (
              <li key={c.id} className="text-sm">
                <span className="font-medium text-slate-800">{c.name}</span>
                <span className="text-slate-500"> — {owedLabel(c)}, due {fmtDate(c.due_date)}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section icon={CalendarClock} title="Upcoming meetings with preps">
        {data.upcoming_meeting_preps.length === 0 ? (
          <p className="text-sm text-slate-400">
            No preps on file for the coming week. Any meetings that need one?
          </p>
        ) : (
          <ul className="space-y-2">
            {data.upcoming_meeting_preps.map((p) => (
              <li key={p.id} className="text-sm">
                <span className="text-slate-500">{fmtDate(p.meeting_date)}:</span>{' '}
                <span className="font-medium text-slate-800">{p.meeting_title || 'Untitled meeting'}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section icon={Radar} title="Stale monitors">
        {data.stale_monitors.length === 0 ? (
          <p className="text-sm text-slate-400">All monitors fresh.</p>
        ) : (
          <ul className="space-y-2">
            {data.stale_monitors.map((m) => (
              <li key={m.id} className="text-sm">
                <span className="font-medium text-amber-700">{m.name || m.question}</span>
                <span className="text-slate-500">
                  {' '}— last checked: {m.last_checked ? fmtDate(m.last_checked) : 'never'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}
