'use client';

import { useState, useEffect, useMemo, use } from 'react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

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
  border: 'rgba(90,173,175,0.18)',
  borderDim: 'rgba(200,221,232,0.08)',
  mono: "'JetBrains Mono', monospace",
  serif: "'DM Serif Display', serif",
  sans: "'DM Sans', sans-serif",
};

/* ── Markdown components ── */
const MD_COMPONENTS = {
  p: ({ children }: { children?: React.ReactNode }) => <p style={{ margin: '4px 0' }}>{children}</p>,
  h2: ({ children }: { children?: React.ReactNode }) => <h2 style={{ fontSize: 15, fontWeight: 700, color: T.fg, margin: '14px 0 4px' }}>{children}</h2>,
  h3: ({ children }: { children?: React.ReactNode }) => <h3 style={{ fontSize: 14, fontWeight: 600, color: T.fg, margin: '10px 0 4px' }}>{children}</h3>,
  ul: ({ children }: { children?: React.ReactNode }) => <ul style={{ paddingLeft: 18, margin: '4px 0' }}>{children}</ul>,
  ol: ({ children }: { children?: React.ReactNode }) => <ol style={{ paddingLeft: 18, margin: '4px 0' }}>{children}</ol>,
  li: ({ children }: { children?: React.ReactNode }) => <li style={{ margin: '2px 0' }}>{children}</li>,
  a: ({ href, children }: { href?: string; children?: React.ReactNode }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: T.teal, textDecoration: 'underline', textUnderlineOffset: 3 }}>{children}</a>
  ),
  code: ({ children }: { children?: React.ReactNode }) => (
    <code style={{ fontFamily: T.mono, fontSize: 12, background: T.bgRaised, padding: '1px 5px', borderRadius: 3, color: T.olive }}>{children}</code>
  ),
  blockquote: ({ children }: { children?: React.ReactNode }) => (
    <blockquote style={{ borderLeft: `3px solid ${T.border}`, paddingLeft: 12, margin: '8px 0', color: T.fgFaint }}>{children}</blockquote>
  ),
  table: ({ children }: { children?: React.ReactNode }) => (
    <table style={{ borderCollapse: 'collapse', fontSize: 12, margin: '8px 0', width: '100%' }}>{children}</table>
  ),
  th: ({ children }: { children?: React.ReactNode }) => (
    <th style={{ border: `1px solid ${T.border}`, padding: '4px 8px', textAlign: 'left', fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>{children}</th>
  ),
  td: ({ children }: { children?: React.ReactNode }) => (
    <td style={{ border: `1px solid ${T.borderDim}`, padding: '4px 8px' }}>{children}</td>
  ),
};

/* ── Helpers ── */

function unesc(s: string | undefined | null): string {
  let text = (s ?? '').replace(/\\n/g, '\n');
  text = text.replace(
    /(?<!\]\()(?<!\()(?<![<"'])(https?:\/\/[^\s)>\]"']+)/g,
    '[$1]($1)'
  );
  text = text.replace(
    /(?<!\]\()(?<!\()(?<![<"'])(?:^|(?<=\s))(\/(?:tech-recon|career|dismech|agentic-memory|coach|skill-builder)\/[^\s)>\]"']+)/gm,
    '[$1]($1)'
  );
  return text;
}

function getValue(attr: unknown): string | null {
  if (attr === null || attr === undefined) return null;
  if (typeof attr === 'string') {
    return attr.replace(/\\\\n/g, '\n').replace(/\\n/g, '\n')
              .replace(/\\\\t/g, '\t').replace(/\\t/g, '\t');
  }
  if (typeof attr === 'number') return String(attr);
  if (Array.isArray(attr) && attr.length > 0 && attr[0]?.value !== undefined) {
    return getValue(attr[0].value);
  }
  return null;
}

function getNumber(attr: unknown): number | null {
  if (attr === null || attr === undefined) return null;
  if (typeof attr === 'number') return attr;
  if (typeof attr === 'string') { const n = Number(attr); return isNaN(n) ? null : n; }
  if (Array.isArray(attr) && attr.length > 0 && attr[0]?.value !== undefined) {
    return getNumber(attr[0].value);
  }
  return null;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getNoteType(n: any): string {
  const raw = typeof n.type === 'string' ? n.type : n.type?.label;
  return (raw || '').replace('career-', '').replace('-note', '') || 'general';
}

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

function formatShortDate(dateStr: string | null): string {
  if (!dateStr) return '';
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

/* ── Config maps ── */

const NOTE_TYPES: Record<string, { label: string; short: string; color: string }> = {
  'fit-analysis': { label: 'Fit Analysis', short: 'FIT', color: T.mint },
  'strategy':     { label: 'Strategy',     short: 'STRAT', color: T.fgDim },
  'interaction':  { label: 'Interaction',  short: 'TALK', color: T.blue },
  'research':     { label: 'Research',     short: 'RES', color: T.fgDim },
  'interview':    { label: 'Interview',    short: 'INT', color: T.blue },
  'skill-gap':    { label: 'Skill Gap',    short: 'GAP', color: T.rust },
  'application':  { label: 'Application',  short: 'APP', color: T.teal },
  'general':      { label: 'General',      short: 'GEN', color: T.fgFaint },
};

function noteTypeMeta(type: string) {
  return NOTE_TYPES[type] || { label: type, short: '?', color: T.fgDim };
}

const SECTION_ORDER = [
  'fit-analysis', 'research', 'strategy', 'interaction',
  'interview', 'skill-gap', 'application', 'general',
];

const STATUS_COLORS: Record<string, string> = {
  researching: T.fgDim,
  applied: T.teal,
  'phone-screen': T.blue,
  interviewing: T.olive,
  offer: T.mint,
  accepted: T.mint,
  rejected: T.rust,
  withdrawn: T.fgFaint,
};

const PRIORITY_COLORS: Record<string, string> = {
  high: T.olive,
  medium: T.teal,
  low: T.fgDim,
};

const LEVEL_COLORS: Record<string, string> = {
  strong: T.mint,
  expert: T.mint,
  some: T.olive,
  practiced: T.olive,
  learning: T.rust,
  aware: T.rust,
  none: T.fgFaint,
};

/* ── Inline component helpers ── */

function Chip({ label, color }: { label: string; color: string }) {
  return (
    <span style={{
      fontFamily: T.mono, fontSize: 10, fontWeight: 700, letterSpacing: 1,
      color, background: `${color}18`, borderRadius: 3, padding: '2px 8px',
      textTransform: 'uppercase',
    }}>
      {label}
    </span>
  );
}

function Label({ children }: { children: React.ReactNode }) {
  return (
    <span style={{
      fontFamily: T.mono, fontSize: 10, color: T.fgFaint,
      textTransform: 'uppercase', letterSpacing: 0.8,
    }}>
      {children}
    </span>
  );
}

/* ── Page ── */

interface PositionPageProps {
  params: Promise<{ id: string }>;
}

export default function PositionPage({ params }: PositionPageProps) {
  const { id } = use(params);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNote, setSelectedNote] = useState<string>('overview');

  useEffect(() => {
    async function fetchPosition() {
      setLoading(true);
      setError(null);
      try {
        const [posRes, skillsRes] = await Promise.all([
          fetch(`/api/career/position/${id}`),
          fetch('/api/career/skills'),
        ]);
        if (!posRes.ok) throw new Error('Failed to fetch position');
        const json = await posRes.json();
        if (skillsRes.ok) {
          const skillsData = await skillsRes.json();
          const mySkills: Record<string, string> = {};
          for (const s of (skillsData.skills ?? [])) {
            mySkills[s.name.toLowerCase()] = s.level;
          }
          if (json.requirements) {
            for (const req of json.requirements) {
              const skillName = req['career-skill-name'] || req['slog-skill-name'] || '';
              req['_seeker_level'] = mySkills[skillName.toLowerCase()] || 'none';
            }
          }
        }
        setData(json);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    }
    fetchPosition();
  }, [id]);

  const groupedNotes = useMemo(() => {
    if (!data?.notes) return {};
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const groups: Record<string, any[]> = {};
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    for (const note of data.notes) {
      const type = getNoteType(note);
      if (!groups[type]) groups[type] = [];
      groups[type].push(note);
    }
    for (const g of Object.values(groups)) {
      g.sort((a, b) => {
        const da = getValue(a['created-at']) || '';
        const db = getValue(b['created-at']) || '';
        return db.localeCompare(da);
      });
    }
    return groups;
  }, [data?.notes]);

  const selectedNoteObj = useMemo(() => {
    if (selectedNote === 'overview' || !data?.notes) return null;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    return data.notes.find((n: any) => n.id === selectedNote) || null;
  }, [selectedNote, data?.notes]);

  /* Loading */
  if (loading) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <span style={{ fontFamily: T.mono, fontSize: 13, color: T.fgDim }}>Loading...</span>
      </div>
    );
  }

  /* Error */
  if (error || !data) {
    return (
      <div style={{ padding: 32 }}>
        <Link href="/career" style={{ fontFamily: T.mono, fontSize: 13, color: T.teal, textDecoration: 'none' }}>
          &larr; career
        </Link>
        <div style={{
          marginTop: 16, padding: '12px 16px', borderRadius: 6,
          background: `${T.rust}15`, border: `1px solid ${T.rust}33`, color: T.rust,
          fontFamily: T.mono, fontSize: 12,
        }}>
          Error: {error || 'Position not found'}
        </div>
      </div>
    );
  }

  const position = data.position;
  const company = data.company;
  const notes = data.notes || [];
  const requirements = data.requirements || [];
  const jobDescription = data.job_description;
  const tags = data.tags || [];
  const backgroundReading = data.background_reading || [];

  const title = getValue(position?.name) || 'Unknown Position';
  const url = getValue(position?.['career-job-url']);
  const location = getValue(position?.location);
  const salary = getValue(position?.['career-salary-range']);
  const remotePolicy = getValue(position?.['career-remote-policy']);
  const priority = getValue(position?.['career-priority-level']);

  const companyName = getValue(company?.name);
  const companyUrl = getValue(company?.['alh-company-url']);
  const companyDescription = getValue(company?.description);

  const status = getValue(position?.['career-opportunity-status']) || 'researching';

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const fitNote = notes.find((n: any) => getNoteType(n) === 'fit-analysis');
  const fitScore = getNumber(fitNote?.['career-fit-score']);
  const fitSummary = getValue(fitNote?.['career-fit-summary']);

  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', fontFamily: T.sans }}>
      {/* Header */}
      <header style={{
        flexShrink: 0, padding: '14px 20px',
        borderBottom: `1px solid ${T.border}`,
        background: T.bgRaised,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
          <Link href="/career" style={{ fontFamily: T.mono, fontSize: 13, color: T.teal, textDecoration: 'none' }}>
            &larr; career
          </Link>
          {companyName && (
            <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>
              {companyName}
            </span>
          )}
          <div style={{ flex: 1 }} />
          {url && (
            <a href={url} target="_blank" rel="noopener noreferrer" style={{
              fontFamily: T.mono, fontSize: 11, color: T.fgDim,
              border: `1px solid ${T.borderDim}`, borderRadius: 4,
              padding: '3px 10px', textDecoration: 'none',
              transition: 'color 0.15s, border-color 0.15s',
            }}>
              Posting &rarr;
            </a>
          )}
          {companyUrl && (
            <a href={companyUrl} target="_blank" rel="noopener noreferrer" style={{
              fontFamily: T.mono, fontSize: 11, color: T.fgDim,
              border: `1px solid ${T.borderDim}`, borderRadius: 4,
              padding: '3px 10px', textDecoration: 'none',
              transition: 'color 0.15s, border-color 0.15s',
            }}>
              Company &rarr;
            </a>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, flexWrap: 'wrap' }}>
          <h1 style={{ fontFamily: T.serif, fontSize: 22, color: T.fg, margin: 0, fontWeight: 400 }}>
            {title}
          </h1>
          <Chip label={status.replace('-', ' ')} color={STATUS_COLORS[status] || T.fgDim} />
          {priority && <Chip label={priority} color={PRIORITY_COLORS[priority] || T.fgDim} />}
          {fitScore !== null && (
            <span style={{ fontFamily: T.mono, fontSize: 11, color: T.mint }}>
              {Math.round(fitScore * 100)}% fit
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginTop: 6, flexWrap: 'wrap' }}>
          {location && (
            <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>{location}</span>
          )}
          {salary && (
            <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>{salary}</span>
          )}
          {remotePolicy && (
            <span style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint }}>{remotePolicy}</span>
          )}
          {tags.length > 0 && tags.map((tag: string) => (
            <span key={tag} style={{
              fontFamily: T.mono, fontSize: 10, color: T.fgDim,
              border: `1px solid ${T.borderDim}`, borderRadius: 10,
              padding: '1px 8px',
            }}>
              {tag}
            </span>
          ))}
        </div>
      </header>

      {/* Main: sidebar + reading pane */}
      <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>

        {/* Sidebar */}
        <nav style={{
          width: 240, minWidth: 240, flexShrink: 0,
          borderRight: `1px solid ${T.border}`,
          overflowY: 'auto', padding: 10,
          background: `${T.bgRaised}cc`,
        }}>
          {/* Overview */}
          <button
            onClick={() => setSelectedNote('overview')}
            style={{
              width: '100%', textAlign: 'left', border: 'none', cursor: 'pointer',
              fontFamily: T.mono, fontSize: 11, letterSpacing: 0.5,
              padding: '7px 10px', borderRadius: 4,
              background: selectedNote === 'overview' ? `${T.teal}18` : 'transparent',
              color: selectedNote === 'overview' ? T.teal : T.fgDim,
              transition: 'color 0.15s, background 0.15s',
            }}
          >
            Overview
          </button>

          <div style={{ borderTop: `1px solid ${T.borderDim}`, margin: '6px 0' }} />

          {/* Note sections */}
          {SECTION_ORDER.map(type => {
            const typeNotes = groupedNotes[type];
            if (!typeNotes?.length) return null;
            const m = noteTypeMeta(type);
            return (
              <details key={type} open style={{ marginBottom: 2 }}>
                <summary style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '5px 10px', cursor: 'pointer',
                  fontFamily: T.mono, fontSize: 10, letterSpacing: 0.5,
                  color: T.fgFaint, textTransform: 'uppercase',
                  listStyle: 'none', userSelect: 'none',
                }}>
                  <span style={{ fontSize: 8, color: m.color }}>&#9679;</span>
                  {m.label}
                  <span style={{ marginLeft: 'auto', fontSize: 9, color: T.fgFaint }}>{typeNotes.length}</span>
                </summary>
                <div style={{ marginLeft: 12, borderLeft: `1px solid ${T.borderDim}`, paddingLeft: 8 }}>
                  {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                  {typeNotes.map((note: any) => {
                    const noteId = note.id;
                    const noteName = getValue(note.name) || 'Untitled';
                    const createdAt = getValue(note['created-at']);
                    const isSelected = selectedNote === noteId;
                    return (
                      <button
                        key={noteId}
                        onClick={() => setSelectedNote(noteId)}
                        style={{
                          width: '100%', textAlign: 'left', border: 'none', cursor: 'pointer',
                          fontFamily: T.sans, fontSize: 11,
                          padding: '4px 8px', borderRadius: 3, marginBottom: 1,
                          background: isSelected ? `${T.teal}18` : 'transparent',
                          color: isSelected ? T.teal : T.fgDim,
                          transition: 'color 0.15s, background 0.15s',
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}
                      >
                        {noteName}
                        {createdAt && (
                          <span style={{ fontFamily: T.mono, fontSize: 9, opacity: 0.5, marginLeft: 4 }}>
                            {formatShortDate(createdAt)}
                          </span>
                        )}
                      </button>
                    );
                  })}
                </div>
              </details>
            );
          })}

          {/* Job Description nav item */}
          {jobDescription && (
            <>
              <div style={{ borderTop: `1px solid ${T.borderDim}`, margin: '6px 0' }} />
              <button
                onClick={() => setSelectedNote('job-description')}
                style={{
                  width: '100%', textAlign: 'left', border: 'none', cursor: 'pointer',
                  fontFamily: T.mono, fontSize: 11, letterSpacing: 0.5,
                  padding: '7px 10px', borderRadius: 4,
                  background: selectedNote === 'job-description' ? `${T.teal}18` : 'transparent',
                  color: selectedNote === 'job-description' ? T.teal : T.fgDim,
                  transition: 'color 0.15s, background 0.15s',
                }}
              >
                Job Description
              </button>
            </>
          )}
        </nav>

        {/* Reading pane */}
        <main style={{ flex: 1, overflowY: 'auto', padding: '24px 32px' }}>
          <div style={{ maxWidth: 800 }}>
            {selectedNote === 'overview' && (
              <OverviewPane
                fitNote={fitNote} fitScore={fitScore} fitSummary={fitSummary}
                requirements={requirements} company={company}
                companyName={companyName} companyUrl={companyUrl}
                companyDescription={companyDescription} tags={tags}
                backgroundReading={backgroundReading}
                location={location} salary={salary} remotePolicy={remotePolicy}
              />
            )}
            {selectedNote === 'job-description' && jobDescription && (
              <div>
                <h2 style={{ fontFamily: T.serif, fontSize: 18, color: T.fg, marginBottom: 14 }}>Job Description</h2>
                <div style={{ borderTop: `1px solid ${T.borderDim}`, marginBottom: 14 }} />
                <pre style={{
                  whiteSpace: 'pre-wrap', fontSize: 12, fontFamily: T.sans,
                  color: T.fgDim, lineHeight: 1.7,
                  background: T.panel, border: `1px solid ${T.borderDim}`,
                  borderRadius: 6, padding: 16,
                }}>
                  {getValue(jobDescription.content)}
                </pre>
              </div>
            )}
            {selectedNote !== 'overview' && selectedNote !== 'job-description' && selectedNoteObj && (
              <NotePane note={selectedNoteObj} />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}

/* ── Overview Pane ── */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function OverviewPane({ fitNote, fitScore, fitSummary, requirements, company, companyName, companyUrl, companyDescription, tags, backgroundReading, location, salary, remotePolicy }: any) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* Quick Info */}
      {(location || salary || remotePolicy || fitScore !== null) && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: 10 }}>
          {location && (
            <div style={{ padding: '10px 14px', background: T.panel, border: `1px solid ${T.borderDim}`, borderRadius: 6 }}>
              <Label>Location</Label>
              <div style={{ fontSize: 13, color: T.fg, marginTop: 3 }}>{location}</div>
            </div>
          )}
          {salary && (
            <div style={{ padding: '10px 14px', background: T.panel, border: `1px solid ${T.borderDim}`, borderRadius: 6 }}>
              <Label>Salary</Label>
              <div style={{ fontSize: 13, color: T.fg, marginTop: 3 }}>{salary}</div>
            </div>
          )}
          {remotePolicy && (
            <div style={{ padding: '10px 14px', background: T.panel, border: `1px solid ${T.borderDim}`, borderRadius: 6 }}>
              <Label>Remote</Label>
              <div style={{ fontSize: 13, color: T.fg, marginTop: 3 }}>{remotePolicy}</div>
            </div>
          )}
          {fitScore !== null && (
            <div style={{ padding: '10px 14px', background: T.panel, border: `1px solid ${T.borderDim}`, borderRadius: 6 }}>
              <Label>Fit Score</Label>
              <div style={{ fontSize: 13, color: T.mint, marginTop: 3, fontFamily: T.mono }}>{Math.round(fitScore * 100)}%</div>
            </div>
          )}
        </div>
      )}

      {/* Fit Analysis */}
      {fitNote && (
        <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 8, padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
            <h2 style={{ fontFamily: T.serif, fontSize: 18, color: T.fg, margin: 0 }}>Fit Analysis</h2>
            {fitScore !== null && (
              <span style={{ fontFamily: T.mono, fontSize: 12, color: T.mint, marginLeft: 'auto' }}>
                {Math.round(fitScore * 100)}%
              </span>
            )}
          </div>
          {fitSummary && (
            <p style={{ fontSize: 13, color: T.fg, fontWeight: 500, marginBottom: 12 }}>{fitSummary}</p>
          )}
          {getValue(fitNote?.content) && (
            <div style={{ fontSize: 13, color: T.fgDim, lineHeight: 1.7 }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
                {unesc(getValue(fitNote?.content))}
              </ReactMarkdown>
            </div>
          )}
        </div>
      )}

      {/* Requirements */}
      {requirements.length > 0 && (
        <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 8, padding: 20 }}>
          <h2 style={{ fontFamily: T.serif, fontSize: 18, color: T.fg, margin: '0 0 14px' }}>
            Requirements ({requirements.length})
          </h2>
          {/* Header row */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 80px 80px',
            padding: '6px 0', marginBottom: 4,
            fontFamily: T.mono, fontSize: 10, textTransform: 'uppercase',
            letterSpacing: 0.5, color: T.fgFaint,
          }}>
            <span>Skill</span>
            <span>Required</span>
            <span>You</span>
          </div>
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          {requirements.map((req: any, idx: number) => {
            const skill = getValue(req['career-skill-name']) || getValue(req['slog-skill-name']) || '';
            const level = getValue(req['career-skill-level']) || getValue(req['requirement-level']) || 'required';
            const yourLevel = req['_seeker_level'] || getValue(req['career-your-level']) || 'none';

            const levelValue: Record<string, number> = { none: 0, aware: 1, learning: 1, practiced: 2, some: 2, expert: 3, strong: 3 };
            const threshold: Record<string, number> = { required: 2, preferred: 1, 'nice-to-have': 0 };
            const myVal = levelValue[yourLevel] ?? 0;
            const reqVal = threshold[level ?? 'required'] ?? 1;
            const match = myVal >= reqVal ? 'match' : myVal > 0 ? 'partial' : 'gap';
            const dotColor = match === 'match' ? T.mint : match === 'partial' ? T.olive : T.rust;

            return (
              <div key={idx} style={{
                display: 'grid', gridTemplateColumns: '1fr 80px 80px',
                gap: 4, padding: '6px 0', alignItems: 'center',
                borderTop: idx > 0 ? `1px solid ${T.borderDim}` : 'none',
              }}>
                <span style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: T.fg }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%', background: dotColor, flexShrink: 0,
                  }} />
                  {skill}
                </span>
                <Chip label={level} color={T.fgFaint} />
                <Chip label={yourLevel} color={LEVEL_COLORS[yourLevel] || T.fgFaint} />
              </div>
            );
          })}
        </div>
      )}

      {/* Company */}
      {company && (
        <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 8, padding: 20 }}>
          <h2 style={{ fontFamily: T.serif, fontSize: 18, color: T.fg, margin: '0 0 14px' }}>
            About {companyName}
          </h2>
          {companyDescription && (
            <div style={{ fontSize: 13, color: T.fgDim, lineHeight: 1.7 }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
                {unesc(companyDescription)}
              </ReactMarkdown>
            </div>
          )}
          {companyUrl && (
            <a href={companyUrl} target="_blank" rel="noopener noreferrer"
               style={{ fontFamily: T.mono, fontSize: 12, color: T.teal, textDecoration: 'underline', textUnderlineOffset: 3, marginTop: 8, display: 'inline-block' }}>
              {companyUrl}
            </a>
          )}
        </div>
      )}

      {/* Background Reading */}
      {backgroundReading.length > 0 && (
        <div style={{ background: T.panel, border: `1px solid ${T.border}`, borderRadius: 8, padding: 20 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 }}>
            <h2 style={{ fontFamily: T.serif, fontSize: 18, color: T.fg, margin: 0 }}>Background Reading</h2>
            <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, marginLeft: 'auto' }}>{backgroundReading.length}</span>
          </div>
          {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
          {backgroundReading.map((col: any, idx: number) => {
            const colName = getValue(col['collection-name']) || col['collection-name'];
            const colDesc = getValue(col.description) || col.description;
            return (
              <div key={idx} style={{
                padding: '8px 0',
                borderTop: idx > 0 ? `1px solid ${T.borderDim}` : 'none',
              }}>
                <Link
                  href={`/career/collection/${col['collection-id']}`}
                  style={{ fontFamily: T.mono, fontSize: 12, color: T.teal, textDecoration: 'underline', textUnderlineOffset: 3 }}
                >
                  {colName}
                </Link>
                {colDesc && (
                  <p style={{ fontSize: 12, color: T.fgDim, marginTop: 3 }}>{colDesc}</p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ── Note Pane ── */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function NotePane({ note }: { note: any }) {
  const content = getValue(note.content);
  const createdAt = getValue(note['created-at']);
  const noteName = getValue(note.name) || 'Untitled';
  const noteType = getNoteType(note);
  const m = noteTypeMeta(noteType);
  const interactionType = getValue(note['alh-interaction-type']);
  const interactionDate = getValue(note['alh-interaction-date']);
  const interviewDate = getValue(note['career-interview-date']);

  return (
    <div>
      {/* Note header */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
          <Chip label={m.short} color={m.color} />
          {interactionType && <Chip label={interactionType} color={T.blue} />}
          <a
            href={`/agentic-memory?entity=${note.id}`}
            style={{ fontFamily: T.mono, fontSize: 10, color: T.teal, textDecoration: 'none', opacity: 0.6, transition: 'opacity 0.15s' }}
            onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; }}
            onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.6'; }}
            title="View in Knowledge Graph"
          >
            graph &rarr;
          </a>
          {createdAt && (
            <span style={{ fontFamily: T.mono, fontSize: 10, color: T.fgFaint, marginLeft: 'auto' }}>
              {formatDate(createdAt)}
            </span>
          )}
        </div>
        <h2 style={{ fontFamily: T.serif, fontSize: 20, color: T.fg, margin: 0 }}>{noteName}</h2>
        {(interactionDate || interviewDate) && (
          <p style={{ fontFamily: T.mono, fontSize: 11, color: T.fgFaint, marginTop: 4 }}>
            {interactionDate && <>Event: {formatDate(interactionDate)}</>}
            {interviewDate && <>Interview: {formatDate(interviewDate)}</>}
          </p>
        )}
      </div>

      <div style={{ borderTop: `1px solid ${T.borderDim}`, marginBottom: 20 }} />

      {/* Note content */}
      {content ? (
        <div style={{ fontSize: 13, color: T.fgDim, lineHeight: 1.7 }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
            {unesc(content)}
          </ReactMarkdown>
        </div>
      ) : (
        <p style={{ fontFamily: T.mono, fontSize: 12, color: T.fgFaint, fontStyle: 'italic' }}>No content</p>
      )}
    </div>
  );
}
