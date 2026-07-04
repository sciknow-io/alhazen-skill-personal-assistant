'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ScoreTrajectory, TrajectoryPoint } from '@/components/scribe/score-trajectory';

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
  rust: '#c87a4a',
  border: 'rgba(90,173,175,0.18)',
  borderDim: 'rgba(200,221,232,0.08)',
  mono: "'JetBrains Mono', monospace",
  serif: "'DM Serif Display', serif",
  sans: "'DM Sans', sans-serif",
};

const STATUS_COLORS: Record<string, string> = {
  planning: '#5e7387',
  drafting: '#5b8ab8',
  'persona-review': '#b8c84a',
  'operator-review': '#c87a4a',
  final: '#62c4bc',
  shipped: '#5aadaf',
};

function unesc(s: string | undefined | null): string {
  return (s ?? '').replace(/\\n/g, '\n');
}

interface Review {
  id: string;
  content: string;
  would_act: boolean | null;
  persona: string | null;
  persona_id: string | null;
  created_at: string | null;
}

interface ScoreNote {
  id: string;
  content: string;
  clarity: number | null;
  concision: number | null;
  voice: number | null;
  persuasion: number | null;
  overall: number | null;
}

interface Draft {
  id: string;
  name: string;
  version: number;
  content: string;
  created_at: string | null;
  reviews: Review[];
  scores: ScoreNote[];
}

interface Target {
  id: string;
  name: string;
  cares_about: string | null;
  skeptical_of: string | null;
  action_drivers: string | null;
  reading_context: string | null;
}

interface NoteItem {
  id: string;
  name: string | null;
  content: string;
  created_at: string | null;
}

interface PieceData {
  success: boolean;
  piece: {
    id: string;
    name: string;
    description: string | null;
    type: string | null;
    status: string;
    goal: string | null;
    audience_summary: string | null;
    deadline: string | null;
  };
  targets: Target[];
  drafts: Draft[];
  score_trajectory: TrajectoryPoint[];
  notes: Record<string, NoteItem[]>;
}

function SectionLabel({ children }: { children: React.ReactNode }) {
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

export default function PieceDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<PieceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [openDraft, setOpenDraft] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/scribe/piece/${id}`)
      .then((r) => r.json())
      .then((d) => setData(d.success ? d : null))
      .catch(() => {})
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

  if (!data) {
    return (
      <div
        style={{
          width: '100vw',
          height: '100vh',
          backgroundColor: T.bg,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: T.rust,
          fontFamily: T.mono,
          fontSize: '12px',
        }}
      >
        Piece not found.&nbsp;<Link href="/scribe" style={{ color: T.teal }}>Back to Scribe</Link>
      </div>
    );
  }

  const { piece, targets, drafts, score_trajectory, notes } = data;
  const statusColor = STATUS_COLORS[piece.status] ?? T.fgFaint;

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
      <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '16px 24px 48px' }}>
        {/* Header */}
        <div style={{ marginBottom: '20px' }}>
          <Link
            href="/scribe"
            style={{ fontFamily: T.mono, fontSize: '11px', color: T.fgFaint, textDecoration: 'none' }}
          >
            &larr; scribe
          </Link>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', marginTop: '6px' }}>
            <h1 style={{ fontFamily: T.serif, fontSize: '26px', margin: 0 }}>{piece.name}</h1>
            <span
              style={{
                fontFamily: T.mono,
                fontSize: '10px',
                color: statusColor,
                background: `${statusColor}15`,
                borderRadius: '2px',
                padding: '2px 8px',
                textTransform: 'uppercase',
              }}
            >
              {piece.status}
            </span>
            {piece.type && (
              <span style={{ fontFamily: T.mono, fontSize: '11px', color: T.fgDim }}>{piece.type}</span>
            )}
          </div>
          <div style={{ marginTop: '8px', fontSize: '13px', color: T.fgDim, lineHeight: 1.6 }}>
            {piece.goal && (
              <div>
                <span style={{ color: T.fgFaint }}>Goal:</span> {piece.goal}
              </div>
            )}
            {piece.audience_summary && (
              <div>
                <span style={{ color: T.fgFaint }}>Audience:</span> {piece.audience_summary}
              </div>
            )}
            {piece.deadline && (
              <div>
                <span style={{ color: T.fgFaint }}>Deadline:</span>{' '}
                {String(piece.deadline).slice(0, 10)}
              </div>
            )}
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
          {/* Main column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', minWidth: 0 }}>
            {/* Score trajectory */}
            <div>
              <SectionLabel>Score Trajectory Across Versions</SectionLabel>
              <ScoreTrajectory trajectory={score_trajectory} />
            </div>

            {/* Drafts */}
            <div>
              <SectionLabel>Drafts ({drafts.length})</SectionLabel>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {drafts.length === 0 && (
                  <div style={{ color: T.fgFaint, fontFamily: T.mono, fontSize: '12px' }}>
                    No drafts yet.
                  </div>
                )}
                {drafts.map((d) => {
                  const latestScores = d.scores[d.scores.length - 1];
                  return (
                    <div
                      key={d.id}
                      style={{
                        background: T.panel,
                        border: `1px solid ${T.borderDim}`,
                        borderRadius: '3px',
                      }}
                    >
                      <button
                        onClick={() => setOpenDraft(openDraft === d.id ? null : d.id)}
                        style={{
                          width: '100%',
                          textAlign: 'left',
                          background: 'transparent',
                          border: 'none',
                          padding: '10px 14px',
                          cursor: 'pointer',
                          display: 'flex',
                          alignItems: 'baseline',
                          gap: '12px',
                        }}
                      >
                        <span style={{ fontFamily: T.mono, fontSize: '12px', color: T.teal }}>
                          {openDraft === d.id ? '▾' : '▸'} v{d.version}
                        </span>
                        <span style={{ fontSize: '13px', color: T.fg }}>{d.name}</span>
                        {latestScores && (
                          <span style={{ fontFamily: T.mono, fontSize: '10px', color: T.fgDim }}>
                            C{latestScores.clarity ?? '—'} · Cn{latestScores.concision ?? '—'} · V
                            {latestScores.voice ?? '—'} · P{latestScores.persuasion ?? '—'} · O
                            {latestScores.overall ?? '—'}
                          </span>
                        )}
                        <span
                          style={{
                            marginLeft: 'auto',
                            fontFamily: T.mono,
                            fontSize: '10px',
                            color: T.fgFaint,
                          }}
                        >
                          {d.reviews.length} review{d.reviews.length === 1 ? '' : 's'}
                        </span>
                      </button>

                      {openDraft === d.id && (
                        <div style={{ padding: '0 18px 16px' }}>
                          {/* Draft content */}
                          <div
                            style={{
                              background: T.bgRaised,
                              border: `1px solid ${T.borderDim}`,
                              borderRadius: '3px',
                              padding: '14px 18px',
                              fontSize: '13px',
                              lineHeight: 1.7,
                              marginBottom: '12px',
                            }}
                          >
                            <div className="prose prose-sm prose-invert max-w-none">
                              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                {unesc(d.content)}
                              </ReactMarkdown>
                            </div>
                          </div>

                          {/* Persona verdicts */}
                          {d.reviews.map((rv) => (
                            <div
                              key={rv.id}
                              style={{
                                borderLeft: `3px solid ${
                                  rv.would_act === true
                                    ? T.olive
                                    : rv.would_act === false
                                    ? T.rust
                                    : T.fgFaint
                                }`,
                                padding: '6px 12px',
                                marginBottom: '8px',
                              }}
                            >
                              <div
                                style={{
                                  fontFamily: T.mono,
                                  fontSize: '10px',
                                  color: T.fgDim,
                                  marginBottom: '2px',
                                }}
                              >
                                {rv.persona ?? 'Persona'}
                                {rv.would_act === true && (
                                  <span style={{ color: T.olive }}> — WOULD ACT</span>
                                )}
                                {rv.would_act === false && (
                                  <span style={{ color: T.rust }}> — would NOT act</span>
                                )}
                              </div>
                              <div style={{ fontSize: '12px', color: T.fg, lineHeight: 1.6 }}>
                                {unesc(rv.content)}
                              </div>
                            </div>
                          ))}

                          {/* Score feedback */}
                          {d.scores.map((sn) => (
                            <div
                              key={sn.id}
                              style={{
                                fontSize: '12px',
                                color: T.fgDim,
                                fontStyle: 'italic',
                                padding: '6px 12px',
                              }}
                            >
                              {unesc(sn.content)}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

          {/* Side column */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', minWidth: 0 }}>
            {/* Target personas */}
            <div>
              <SectionLabel>Target Personas ({targets.length})</SectionLabel>
              {targets.length === 0 && (
                <div style={{ color: T.fgFaint, fontFamily: T.mono, fontSize: '12px' }}>
                  No target personas. Every piece needs readers to test against.
                </div>
              )}
              {targets.map((t) => (
                <div
                  key={t.id}
                  style={{
                    background: T.panel,
                    border: `1px solid ${T.borderDim}`,
                    borderRadius: '3px',
                    padding: '12px 14px',
                    marginBottom: '8px',
                  }}
                >
                  <div style={{ fontFamily: T.serif, fontSize: '15px', marginBottom: '6px' }}>
                    {t.name}
                  </div>
                  {t.cares_about && (
                    <div style={{ fontSize: '11px', color: T.fgDim, marginBottom: '3px' }}>
                      <span style={{ color: T.teal }}>cares:</span> {t.cares_about}
                    </div>
                  )}
                  {t.skeptical_of && (
                    <div style={{ fontSize: '11px', color: T.fgDim, marginBottom: '3px' }}>
                      <span style={{ color: T.rust }}>skeptical:</span> {t.skeptical_of}
                    </div>
                  )}
                  {t.action_drivers && (
                    <div style={{ fontSize: '11px', color: T.fgDim }}>
                      <span style={{ color: T.olive }}>acts on:</span> {t.action_drivers}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Primer / interview / plan notes */}
            {Object.entries(notes).map(([label, ns]) => (
              <div key={label}>
                <SectionLabel>{label} notes</SectionLabel>
                {ns.map((n) => (
                  <div
                    key={n.id}
                    style={{
                      background: T.panel,
                      border: `1px solid ${T.borderDim}`,
                      borderRadius: '3px',
                      padding: '12px 14px',
                      marginBottom: '8px',
                      fontSize: '12px',
                      lineHeight: 1.6,
                    }}
                  >
                    <div className="prose prose-sm prose-invert max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{unesc(n.content)}</ReactMarkdown>
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
