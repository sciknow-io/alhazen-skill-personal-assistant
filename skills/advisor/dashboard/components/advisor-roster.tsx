'use client';

export interface Advisor {
  id: string;
  name: string;
  archetype: string | null;
  decision_style: string | null;
  pushback: string | null;
  inspiration: string | null;
  charter: string | null;
  status: string | null;
  board?: string | null;
}

interface AdvisorRosterProps {
  advisors: Advisor[];
}

const PUSHBACK_COLORS: Record<string, string> = {
  gentle: '#62c4bc',
  firm: '#b8c84a',
  relentless: '#e05555',
};

export function AdvisorRoster({ advisors }: AdvisorRosterProps) {
  if (advisors.length === 0) {
    return (
      <div
        style={{
          color: '#5e7387',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '12px',
          padding: '24px',
          textAlign: 'center',
        }}
      >
        No advisors seated yet. Use <code style={{ color: '#5aadaf' }}>advisor.py add-advisor</code>{' '}
        to build your board.
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
      {advisors.map((advisor) => {
        const pushbackColor = PUSHBACK_COLORS[advisor.pushback ?? ''] ?? '#5e7387';
        const retired = advisor.status === 'retired';
        return (
          <div
            key={advisor.id}
            style={{
              background: 'rgba(12, 22, 40, 0.72)',
              border: '1px solid rgba(200, 221, 232, 0.08)',
              borderRadius: '3px',
              padding: '14px 16px',
              opacity: retired ? 0.5 : 1,
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
              <span style={{ fontFamily: "'DM Serif Display', serif", fontSize: '17px', color: '#c8dde8' }}>
                {advisor.name}
              </span>
              {advisor.pushback && (
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: '9px',
                    color: pushbackColor,
                    background: `${pushbackColor}18`,
                    borderRadius: '2px',
                    padding: '1px 6px',
                    textTransform: 'uppercase',
                    letterSpacing: '0.5px',
                  }}
                >
                  {advisor.pushback}
                </span>
              )}
              {retired && (
                <span
                  style={{
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: '9px',
                    color: '#5e7387',
                    textTransform: 'uppercase',
                  }}
                >
                  retired
                </span>
              )}
            </div>
            <div
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '10px',
                color: '#5aadaf',
                marginBottom: '8px',
              }}
            >
              {[advisor.archetype, advisor.decision_style].filter(Boolean).join(' · ')}
            </div>
            {advisor.charter && (
              <div style={{ fontSize: '12px', color: '#8ba4b8', lineHeight: 1.5, marginBottom: '6px' }}>
                {advisor.charter}
              </div>
            )}
            {advisor.inspiration && (
              <div
                style={{
                  fontSize: '11px',
                  color: '#5e7387',
                  fontStyle: 'italic',
                }}
              >
                channels: {advisor.inspiration}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
