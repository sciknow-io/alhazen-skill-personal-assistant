'use client';

import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface Sample {
  id: string;
  name: string;
  kind: string;
  doc_type: string | null;
  why_it_works: string | null;
}

export interface Analysis {
  id: string;
  name: string | null;
  content: string;
  created_at: string | null;
}

export interface ProfileData {
  profile: {
    id: string;
    name: string;
    description: string | null;
    status: string;
    genre: string | null;
  };
  style_guide: { id: string; content: string } | null;
  samples: Sample[];
  analyses: Analysis[];
}

const T = {
  panel: 'rgba(12,22,40,0.72)',
  fg: '#c8dde8',
  fgDim: '#8ba4b8',
  fgFaint: '#5e7387',
  teal: '#5aadaf',
  olive: '#b8c84a',
  blue: '#5b8ab8',
  borderDim: 'rgba(200,221,232,0.08)',
  mono: "'JetBrains Mono', monospace",
  serif: "'DM Serif Display', serif",
};

const STATUS_COLORS: Record<string, string> = {
  draft: '#5e7387',
  active: '#b8c84a',
  evolving: '#5aadaf',
};

function unesc(s: string | undefined | null): string {
  return (s ?? '').replace(/\\n/g, '\n');
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

/**
 * Voice profile panel: living style guide + writing samples (own vs
 * aspirational) + agent-as-linguist analyses.
 */
export function VoiceProfilePanel({ data }: { data: ProfileData | null }) {
  const [openAnalysis, setOpenAnalysis] = useState<string | null>(null);

  if (!data || !data.profile) {
    return (
      <div
        style={{
          color: T.fgFaint,
          fontFamily: T.mono,
          fontSize: '12px',
          padding: '16px',
          textAlign: 'center',
        }}
      >
        No voice profile yet. Create one with{' '}
        <code style={{ color: T.teal }}>scribe.py create-profile</code>.
      </div>
    );
  }

  const { profile, style_guide, samples, analyses } = data;
  const ownSamples = samples.filter((s) => s.kind === 'own');
  const aspirational = samples.filter((s) => s.kind === 'aspirational');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Profile header */}
      <div
        style={{
          background: T.panel,
          border: `1px solid ${T.borderDim}`,
          borderRadius: '3px',
          padding: '16px 20px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px' }}>
          <span style={{ fontFamily: T.serif, fontSize: '20px', color: T.fg }}>{profile.name}</span>
          <span
            style={{
              fontFamily: T.mono,
              fontSize: '9px',
              color: STATUS_COLORS[profile.status] ?? T.fgFaint,
              background: `${STATUS_COLORS[profile.status] ?? T.fgFaint}15`,
              borderRadius: '2px',
              padding: '1px 6px',
              textTransform: 'uppercase',
            }}
          >
            {profile.status}
          </span>
          {profile.genre && (
            <span style={{ fontFamily: T.mono, fontSize: '10px', color: T.fgDim }}>
              genre: {profile.genre}
            </span>
          )}
        </div>
        {profile.description && (
          <div style={{ fontSize: '12px', color: T.fgDim, marginTop: '8px' }}>
            {profile.description}
          </div>
        )}
      </div>

      {/* Style guide */}
      <div>
        <SectionLabel>Living Style Guide</SectionLabel>
        {style_guide?.content ? (
          <div
            style={{
              background: T.panel,
              border: `1px solid ${T.borderDim}`,
              borderRadius: '3px',
              padding: '20px 24px',
              fontSize: '13px',
              color: T.fg,
              lineHeight: 1.7,
            }}
          >
            <div className="prose prose-sm prose-invert max-w-none">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{unesc(style_guide.content)}</ReactMarkdown>
            </div>
          </div>
        ) : (
          <div style={{ color: T.fgFaint, fontFamily: T.mono, fontSize: '12px', padding: '12px' }}>
            No style guide yet. Merge sample analyses into one with{' '}
            <code style={{ color: T.teal }}>scribe.py update-profile --guide-file</code>.
          </div>
        )}
      </div>

      {/* Samples */}
      <div>
        <SectionLabel>
          Writing Samples ({ownSamples.length} own · {aspirational.length} aspirational)
        </SectionLabel>
        {samples.length === 0 ? (
          <div style={{ color: T.fgFaint, fontFamily: T.mono, fontSize: '12px', padding: '12px' }}>
            No samples linked. A profile without samples is a guess — add the operator&apos;s best
            writing with <code style={{ color: T.teal }}>scribe.py add-sample --profile</code>.
          </div>
        ) : (
          <div style={{ border: `1px solid ${T.borderDim}`, borderRadius: '3px', overflow: 'hidden' }}>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '90px 1.4fr 110px 2fr',
                padding: '6px 12px',
                background: T.panel,
                fontFamily: T.mono,
                fontSize: '10px',
                textTransform: 'uppercase',
                color: T.fgFaint,
                letterSpacing: '0.5px',
              }}
            >
              <span>Kind</span>
              <span>Sample</span>
              <span>Doc Type</span>
              <span>Why It Works</span>
            </div>
            {samples.map((s) => (
              <div
                key={s.id}
                style={{
                  display: 'grid',
                  gridTemplateColumns: '90px 1.4fr 110px 2fr',
                  padding: '7px 12px',
                  borderTop: `1px solid ${T.borderDim}`,
                  fontSize: '12px',
                  alignItems: 'baseline',
                }}
              >
                <span
                  style={{
                    fontFamily: T.mono,
                    fontSize: '9px',
                    color: s.kind === 'own' ? T.olive : T.blue,
                    textTransform: 'uppercase',
                  }}
                >
                  {s.kind}
                </span>
                <span style={{ color: T.fg }}>{s.name}</span>
                <span style={{ fontFamily: T.mono, fontSize: '10px', color: T.fgFaint }}>
                  {s.doc_type ?? ''}
                </span>
                <span style={{ color: T.fgDim, fontSize: '11px' }}>{s.why_it_works ?? ''}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Linguist analyses */}
      <div>
        <SectionLabel>Linguist Analyses ({analyses.length})</SectionLabel>
        {analyses.length === 0 ? (
          <div style={{ color: T.fgFaint, fontFamily: T.mono, fontSize: '12px', padding: '12px' }}>
            No analyses yet. Ask the agent to analyze the samples as a linguist (rhythm, sentence
            structure, rhetorical preferences).
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {analyses.map((a) => (
              <div
                key={a.id}
                style={{
                  background: T.panel,
                  border: `1px solid ${T.borderDim}`,
                  borderRadius: '3px',
                }}
              >
                <button
                  onClick={() => setOpenAnalysis(openAnalysis === a.id ? null : a.id)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    background: 'transparent',
                    border: 'none',
                    padding: '10px 14px',
                    cursor: 'pointer',
                    fontFamily: T.mono,
                    fontSize: '11px',
                    color: T.teal,
                  }}
                >
                  {openAnalysis === a.id ? '▾' : '▸'} {a.name || 'Linguist Analysis'}
                  {a.created_at ? ` — ${String(a.created_at).slice(0, 10)}` : ''}
                </button>
                {openAnalysis === a.id && (
                  <div
                    style={{
                      padding: '0 20px 16px',
                      fontSize: '13px',
                      color: T.fg,
                      lineHeight: 1.7,
                    }}
                  >
                    <div className="prose prose-sm prose-invert max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{unesc(a.content)}</ReactMarkdown>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
