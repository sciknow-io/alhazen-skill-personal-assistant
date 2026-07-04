'use client';

export interface Persona {
  id: string;
  name: string;
  description: string | null;
  cares_about: string | null;
  skeptical_of: string | null;
  action_drivers: string | null;
  reading_context: string | null;
  target_of_pieces: number;
}

const T = {
  panel: 'rgba(12,22,40,0.72)',
  fg: '#c8dde8',
  fgDim: '#8ba4b8',
  fgFaint: '#5e7387',
  teal: '#5aadaf',
  olive: '#b8c84a',
  rust: '#c87a4a',
  blue: '#5b8ab8',
  borderDim: 'rgba(200,221,232,0.08)',
  mono: "'JetBrains Mono', monospace",
  serif: "'DM Serif Display', serif",
};

function Trait({ label, value, color }: { label: string; value: string | null; color: string }) {
  if (!value) return null;
  return (
    <div style={{ marginBottom: '8px' }}>
      <div
        style={{
          fontFamily: T.mono,
          fontSize: '9px',
          color,
          textTransform: 'uppercase',
          letterSpacing: '0.8px',
          marginBottom: '2px',
        }}
      >
        {label}
      </div>
      <div style={{ fontSize: '12px', color: T.fg, lineHeight: 1.5 }}>{value}</div>
    </div>
  );
}

/**
 * Persona cards: one card per reader persona, showing the decision
 * psychology that drives draft reviews.
 */
export function PersonaCards({ personas }: { personas: Persona[] }) {
  if (personas.length === 0) {
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
        No personas yet. Create one with <code style={{ color: T.teal }}>scribe.py add-persona</code>.
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
        gap: '12px',
      }}
    >
      {personas.map((p) => (
        <div
          key={p.id}
          style={{
            background: T.panel,
            border: `1px solid ${T.borderDim}`,
            borderRadius: '3px',
            padding: '14px 16px',
          }}
        >
          <div
            style={{
              display: 'flex',
              alignItems: 'baseline',
              justifyContent: 'space-between',
              marginBottom: '10px',
            }}
          >
            <span style={{ fontFamily: T.serif, fontSize: '17px', color: T.fg }}>{p.name}</span>
            <span style={{ fontFamily: T.mono, fontSize: '9px', color: T.fgFaint }}>
              {p.target_of_pieces} piece{p.target_of_pieces === 1 ? '' : 's'}
            </span>
          </div>
          {p.description && (
            <div style={{ fontSize: '11px', color: T.fgDim, marginBottom: '10px', lineHeight: 1.5 }}>
              {p.description}
            </div>
          )}
          <Trait label="Cares About" value={p.cares_about} color={T.teal} />
          <Trait label="Skeptical Of" value={p.skeptical_of} color={T.rust} />
          <Trait label="Action Drivers" value={p.action_drivers} color={T.olive} />
          <Trait label="Reading Context" value={p.reading_context} color={T.blue} />
        </div>
      ))}
    </div>
  );
}
