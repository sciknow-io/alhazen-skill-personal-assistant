'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';

const MONO = "'JetBrains Mono', monospace";

interface AgendaItem {
  id: string;
  name?: string;
  [key: string]: unknown;
}

interface Agenda {
  generated_at: string;
  ops: { available: boolean; open_commitments: AgendaItem[]; active_specs: AgendaItem[]; upcoming_preps: AgendaItem[] };
  advisor: { available: boolean; in_flight: AgendaItem[]; reviews_due: AgendaItem[] };
  scribe: { available: boolean; awaiting_review: AgendaItem[]; in_draft: AgendaItem[] };
  analyst: { available: boolean; pending_gate: AgendaItem[]; running: AgendaItem[] };
  career: { available: boolean; deadlines: AgendaItem[]; active_projects: AgendaItem[] };
}

function Section({
  title,
  accent,
  available,
  groups,
  installHint,
}: {
  title: string;
  accent: string;
  available: boolean;
  groups: Array<{ label: string; items: AgendaItem[]; href: (i: AgendaItem) => string; line: (i: AgendaItem) => string }>;
  installHint: string;
}) {
  const total = groups.reduce((n, g) => n + g.items.length, 0);
  return (
    <div style={{
      border: '1px solid rgba(200, 221, 232, 0.08)',
      borderRadius: '3px',
      background: 'rgba(12, 22, 40, 0.72)',
      padding: '16px 20px',
    }}>
      <div style={{
        fontFamily: MONO,
        fontSize: '10px',
        color: accent,
        textTransform: 'uppercase',
        letterSpacing: '1.4px',
        marginBottom: '10px',
      }}>
        {title} {available ? `(${total})` : ''}
      </div>

      {!available ? (
        <div style={{ color: '#5e7387', fontFamily: MONO, fontSize: '11px' }}>
          {installHint}
        </div>
      ) : total === 0 ? (
        <div style={{ color: '#5e7387', fontFamily: MONO, fontSize: '11px' }}>
          Nothing pending.
        </div>
      ) : (
        groups.filter(g => g.items.length > 0).map(g => (
          <div key={g.label} style={{ marginBottom: '10px' }}>
            <div style={{ fontFamily: MONO, fontSize: '10px', color: '#5e7387', marginBottom: '4px' }}>
              {g.label}
            </div>
            {g.items.map(item => (
              <Link key={item.id} href={g.href(item)} style={{
                display: 'block',
                color: '#a9c0d0',
                fontSize: '12px',
                textDecoration: 'none',
                padding: '3px 0',
              }}>
                {g.line(item)}
              </Link>
            ))}
          </div>
        ))
      )}
    </div>
  );
}

export default function ChiefOfStaff() {
  const [agenda, setAgenda] = useState<Agenda | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch('/api/chief/agenda')
      .then(r => {
        if (!r.ok) throw new Error('Failed to load agenda');
        return r.json();
      })
      .then(d => setAgenda(d))
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#070d1c',
      fontFamily: "'DM Sans', sans-serif",
      color: '#c8dde8',
      padding: '24px 32px 64px',
    }}>
      <Link href="/" style={{ fontFamily: MONO, fontSize: '11px', color: '#5e7387', textDecoration: 'none' }}>
        &larr; hub
      </Link>
      <h1 style={{
        fontFamily: "'DM Serif Display', serif",
        fontSize: '28px',
        margin: '12px 0 4px',
      }}>
        Chief of Staff
      </h1>
      <div style={{ fontFamily: MONO, fontSize: '11px', color: '#5e7387', marginBottom: '24px' }}>
        {agenda ? `agenda generated ${agenda.generated_at.slice(0, 16).replace('T', ' ')} UTC` : ''}
      </div>

      {loading && (
        <div style={{ color: '#5e7387', fontFamily: MONO, fontSize: '12px' }}>Loading...</div>
      )}
      {error && (
        <div style={{ color: '#c96a6a', fontFamily: MONO, fontSize: '12px' }}>{error}</div>
      )}

      {agenda && (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(340px, 1fr))',
          gap: '16px',
          maxWidth: '1200px',
        }}>
          <Section
            title="Operations"
            accent="#b8c84a"
            available={agenda.ops.available}
            installHint="ops skill not installed."
            groups={[
              {
                label: 'Commitments',
                items: agenda.ops.open_commitments,
                href: () => '/ops',
                line: i => `⏰ ${i.name || i.id} — ${i.status}, owed by ${i.owed_by || '?'}`,
              },
              {
                label: 'Upcoming preps',
                items: agenda.ops.upcoming_preps,
                href: () => '/ops',
                line: i => `📋 ${i.title || i.id} — ${String(i.date || '').slice(0, 10)}`,
              },
            ]}
          />
          <Section
            title="Decisions"
            accent="#5aadaf"
            available={agenda.advisor.available}
            installHint="advisor skill not installed."
            groups={[
              {
                label: 'In flight',
                items: agenda.advisor.in_flight,
                href: i => `/advisor/decision/${i.id}`,
                line: i => `⚖️ ${i.name || i.id} — ${i.status} (${i.stakes || '?'} stakes)`,
              },
              {
                label: 'Reviews due',
                items: agenda.advisor.reviews_due,
                href: i => `/advisor/decision/${i.id}`,
                line: i => `🔁 ${i.name || i.id} — review due since ${String(i.review_date || '').slice(0, 10)}`,
              },
            ]}
          />
          <Section
            title="Communications"
            accent="#c9a15a"
            available={agenda.scribe.available}
            installHint="scribe skill not installed."
            groups={[
              {
                label: 'Awaiting review',
                items: agenda.scribe.awaiting_review,
                href: i => `/scribe/piece/${i.id}`,
                line: i => `✍️ ${i.name || i.id} — ${i.status}`,
              },
              {
                label: 'In draft',
                items: agenda.scribe.in_draft,
                href: i => `/scribe/piece/${i.id}`,
                line: i => `📝 ${i.name || i.id} — ${i.status}`,
              },
            ]}
          />
          <Section
            title="Research"
            accent="#5b8ab8"
            available={agenda.analyst.available}
            installHint="analyst skill not installed."
            groups={[
              {
                label: 'Pending gate',
                items: agenda.analyst.pending_gate,
                href: i => `/analyst/mission/${i.id}`,
                line: i => `🔬 ${i.name || i.id} — ${i.status}`,
              },
              {
                label: 'Running',
                items: agenda.analyst.running,
                href: i => `/analyst/mission/${i.id}`,
                line: i => `🔬 ${i.name || i.id} — ${i.status}`,
              },
            ]}
          />
          <Section
            title="Career"
            accent="#62c4bc"
            available={agenda.career.available}
            installHint="career skill not installed."
            groups={[
              {
                label: 'Deadlines (14d)',
                items: agenda.career.deadlines,
                href: i => `/career/opportunity/${i.id}`,
                line: i => `🎯 ${i.name || i.id} — ${String(i.deadline || '').slice(0, 10)}`,
              },
              {
                label: 'Active projects',
                items: agenda.career.active_projects,
                href: i => `/career/opportunity/${i.id}`,
                line: i => `🛠 ${i.name || i.id} (${i.role || '?'})`,
              },
            ]}
          />
        </div>
      )}
    </div>
  );
}
