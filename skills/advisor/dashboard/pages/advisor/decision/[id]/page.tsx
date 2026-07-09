'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ScenarioMatrix, Scenario } from '@/components/advisor/scenario-matrix';

/* ── Starry Night palette ── */
const T = {
  bg: '#070d1c',
  bgRaised: '#0c1628',
  panel: 'rgba(12,22,40,0.72)',
  fg: '#c8dde8',
  fgDim: '#8ba4b8',
  fgFaint: '#5e7387',
  teal: '#5aadaf',
  blue: '#5b8ab8',
  olive: '#b8c84a',
  mint: '#62c4bc',
  rust: '#c87a4a',
  red: '#e05555',
  border: 'rgba(90,173,175,0.18)',
  borderDim: 'rgba(200,221,232,0.08)',
  mono: "'JetBrains Mono', monospace",
  serif: "'DM Serif Display', serif",
  sans: "'DM Sans', sans-serif",
};

const STAKES_COLORS: Record<string, string> = {
  low: T.fgFaint,
  medium: T.blue,
  high: T.rust,
  irreversible: T.red,
};

const STANCE_COLORS: Record<string, string> = {
  for: T.mint,
  against: T.red,
  conditional: T.olive,
  reframe: T.blue,
};

interface Note {
  id: string;
  name: string | null;
  content: string | null;
  created_at: string | null;
}

interface Take extends Note {
  stance: string | null;
  advisor: string | null;
  advisor_id: string | null;
  archetype: string | null;
  pushback: string | null;
}

interface DecisionDetail {
  success: boolean;
  decision: {
    id: string;
    name: string;
    question: string | null;
    status: string | null;
    stakes: string | null;
    operator_style: string | null;
    outcome: string | null;
    review_date: string | null;
    review_due?: boolean;
  };
  notes: Record<string, Note[]>;
  takes: Take[];
  scenarios: Scenario[];
}

function unesc(s: string | undefined | null): string {
  return (s ?? '').replace(/\\n/g, '\n');
}

function Badge({ text, color }: { text: string; color: string }) {
  return (
    <span
      style={{
        fontFamily: T.mono,
        fontSize: '9px',
        color,
        background: `${color}18`,
        border: `1px solid ${color}40`,
        borderRadius: '2px',
        padding: '1px 6px',
        textTransform: 'uppercase',
        letterSpacing: '0.5px',
      }}
    >
      {text}
    </span>
  );
}

function SectionHeading({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontFamily: T.mono,
        fontSize: '10px',
        color: T.fgFaint,
        textTransform: 'uppercase',
        letterSpacing: '1.4px',
        marginBottom: '10px',
      }}
    >
      {children}
    </div>
  );
}

function NotePanel({ note }: { note: Note }) {
  return (
    <div
      style={{
        background: T.panel,
        border: `1px solid ${T.borderDim}`,
        borderRadius: '3px',
        padding: '14px 18px',
        marginBottom: '10px',
        fontSize: '13px',
        color: T.fg,
        lineHeight: 1.6,
      }}
    >
      {note.name && (
        <div style={{ fontFamily: T.mono, fontSize: '10px', color: T.teal, marginBottom: '6px' }}>
          {note.name}
          {note.created_at ? ` · ${String(note.created_at).slice(0, 10)}` : ''}
        </div>
      )}
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{unesc(note.content)}</ReactMarkdown>
    </div>
  );
}

export default function DecisionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [detail, setDetail] = useState<DecisionDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/advisor/decision/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error('Failed to fetch decision');
        return r.json();
      })
      .then((data) => {
        if (data.success === false) throw new Error(data.error ?? 'Not found');
        setDetail(data);
      })
      .catch((e) => setError(String(e.message ?? e)))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div
        style={{
          width: '100vw',
          height: '100vh',
          backgroundColor: T.bg,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: T.fgFaint,
          fontFamily: T.mono,
          fontSize: '11px',
        }}
      >
        Loading...
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div
        style={{
          width: '100vw',
          height: '100vh',
          backgroundColor: T.bg,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '12px',
          color: T.fgDim,
          fontFamily: T.mono,
          fontSize: '12px',
        }}
      >
        <div>{error ?? 'Decision not found'}</div>
        <Link href="/advisor" style={{ color: T.teal }}>
          &larr; back to advisor hub
        </Link>
      </div>
    );
  }

  const d = detail.decision;
  const stakesColor = STAKES_COLORS[d.stakes ?? ''] ?? T.fgFaint;

  return (
    <div
      style={{
        width: '100vw',
        minHeight: '100vh',
        backgroundColor: T.bg,
        fontFamily: T.sans,
        color: T.fg,
      }}
    >
      <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '20px 24px 60px' }}>
        {/* ── Header ── */}
        <Link
          href="/advisor"
          style={{ fontFamily: T.mono, fontSize: '11px', color: T.fgFaint, textDecoration: 'none' }}
        >
          &larr; advisor hub
        </Link>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '8px', flexWrap: 'wrap' }}>
          <h1 style={{ fontFamily: T.serif, fontSize: '26px', margin: 0, lineHeight: 1.2 }}>
            {d.name}
          </h1>
          {d.status && <Badge text={d.status} color={T.teal} />}
          {d.stakes && <Badge text={d.stakes} color={stakesColor} />}
          {d.review_due && <Badge text="review due" color={T.red} />}
        </div>
        {d.question && (
          <div style={{ fontSize: '14px', color: T.fgDim, marginTop: '8px', lineHeight: 1.5 }}>
            {d.question}
          </div>
        )}
        <div style={{ fontFamily: T.mono, fontSize: '10px', color: T.fgFaint, marginTop: '8px' }}>
          {d.operator_style ? `operator style: ${d.operator_style}` : ''}
          {d.review_date ? `  ·  review ${String(d.review_date).slice(0, 10)}` : ''}
        </div>
        {d.outcome && (
          <div
            style={{
              marginTop: '14px',
              background: T.panel,
              border: `1px solid ${T.border}`,
              borderRadius: '3px',
              padding: '12px 16px',
            }}
          >
            <span style={{ fontFamily: T.mono, fontSize: '10px', color: T.teal, textTransform: 'uppercase', letterSpacing: '1px' }}>
              Outcome
            </span>
            <div style={{ fontSize: '14px', marginTop: '4px' }}>{d.outcome}</div>
          </div>
        )}

        <div style={{ display: 'flex', gap: '24px', marginTop: '28px', alignItems: 'flex-start', flexWrap: 'wrap' }}>
          {/* ── Main column ── */}
          <div style={{ flex: '2 1 560px', minWidth: 0 }}>
            {/* Primer + Interview */}
            {(detail.notes.primer?.length || detail.notes.interview?.length) && (
              <div style={{ marginBottom: '24px' }}>
                <SectionHeading>Primer &amp; Interview</SectionHeading>
                {(detail.notes.primer ?? []).map((n) => (
                  <NotePanel key={n.id} note={n} />
                ))}
                {(detail.notes.interview ?? []).map((n) => (
                  <NotePanel key={n.id} note={n} />
                ))}
              </div>
            )}

            {/* Takes per advisor */}
            <div style={{ marginBottom: '24px' }}>
              <SectionHeading>Independent Takes ({detail.takes.length})</SectionHeading>
              {detail.takes.length === 0 ? (
                <div style={{ color: T.fgFaint, fontFamily: T.mono, fontSize: '12px', padding: '12px' }}>
                  No takes yet — each advisor writes theirs without seeing the others.
                </div>
              ) : (
                detail.takes.map((t) => {
                  const stanceColor = STANCE_COLORS[t.stance ?? ''] ?? T.fgFaint;
                  return (
                    <div
                      key={t.id}
                      style={{
                        background: T.panel,
                        border: `1px solid ${T.borderDim}`,
                        borderRadius: '3px',
                        padding: '14px 18px',
                        marginBottom: '10px',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
                        <span style={{ fontFamily: T.serif, fontSize: '16px', color: T.fg }}>
                          {t.advisor ?? 'Unknown seat'}
                        </span>
                        {t.archetype && (
                          <span style={{ fontFamily: T.mono, fontSize: '10px', color: T.teal }}>
                            {t.archetype}
                          </span>
                        )}
                        {t.stance && <Badge text={t.stance} color={stanceColor} />}
                        {t.pushback && (
                          <span style={{ fontFamily: T.mono, fontSize: '9px', color: T.fgFaint }}>
                            pushback: {t.pushback}
                          </span>
                        )}
                      </div>
                      <div style={{ fontSize: '13px', lineHeight: 1.6 }}>
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{unesc(t.content)}</ReactMarkdown>
                      </div>
                    </div>
                  );
                })
              )}
            </div>

            {/* Debate */}
            {(detail.notes.debate ?? []).length > 0 && (
              <div style={{ marginBottom: '24px' }}>
                <SectionHeading>Debate (challenge &rarr; converge)</SectionHeading>
                {(detail.notes.debate ?? []).map((n) => (
                  <NotePanel key={n.id} note={n} />
                ))}
              </div>
            )}

            {/* Bias check */}
            {(detail.notes.bias_check ?? []).length > 0 && (
              <div style={{ marginBottom: '24px' }}>
                <SectionHeading>Bias Check</SectionHeading>
                {(detail.notes.bias_check ?? []).map((n) => (
                  <NotePanel key={n.id} note={n} />
                ))}
              </div>
            )}

            {/* Scenario matrix */}
            <div style={{ marginBottom: '24px' }}>
              <SectionHeading>Scenario Stress-Tests ({detail.scenarios.length})</SectionHeading>
              <ScenarioMatrix scenarios={detail.scenarios} />
            </div>
          </div>

          {/* ── Side column: Journal ── */}
          <div style={{ flex: '1 1 320px', minWidth: 0 }}>
            <SectionHeading>Journal</SectionHeading>
            {(detail.notes.journal ?? []).length === 0 ? (
              <div style={{ color: T.fgFaint, fontFamily: T.mono, fontSize: '12px', padding: '12px' }}>
                No journal entries yet. Recorded at decide time and on review.
              </div>
            ) : (
              (detail.notes.journal ?? []).map((n) => <NotePanel key={n.id} note={n} />)
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
