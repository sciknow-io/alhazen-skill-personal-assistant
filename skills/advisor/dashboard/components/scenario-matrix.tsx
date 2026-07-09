'use client';

export interface Scenario {
  id: string;
  condition: string | null;
  impact: string | null;
  likelihood: string | null;
  created_at?: string | null;
}

interface ScenarioMatrixProps {
  scenarios: Scenario[];
}

const LIKELIHOOD_COLORS: Record<string, string> = {
  low: '#5e7387',
  medium: '#b8c84a',
  high: '#c87a4a',
};

const LIKELIHOOD_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 };

export function ScenarioMatrix({ scenarios }: ScenarioMatrixProps) {
  if (scenarios.length === 0) {
    return (
      <div
        style={{
          color: '#5e7387',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '12px',
          padding: '16px',
          textAlign: 'center',
        }}
      >
        No scenario stress-tests yet. A decision should survive multiple futures,
        not just the hoped-for one.
      </div>
    );
  }

  const sorted = [...scenarios].sort(
    (a, b) =>
      (LIKELIHOOD_ORDER[a.likelihood ?? ''] ?? 3) -
      (LIKELIHOOD_ORDER[b.likelihood ?? ''] ?? 3)
  );

  return (
    <div
      style={{
        border: '1px solid rgba(200, 221, 232, 0.08)',
        borderRadius: '3px',
        overflow: 'hidden',
      }}
    >
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '2fr 90px 3fr',
          padding: '6px 12px',
          background: 'rgba(12, 22, 40, 0.72)',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '10px',
          textTransform: 'uppercase',
          color: '#5e7387',
          letterSpacing: '0.5px',
        }}
      >
        <span>What if...</span>
        <span>Likelihood</span>
        <span>Impact on the decision</span>
      </div>
      {sorted.map((s) => {
        const color = LIKELIHOOD_COLORS[s.likelihood ?? ''] ?? '#5e7387';
        return (
          <div
            key={s.id}
            style={{
              display: 'grid',
              gridTemplateColumns: '2fr 90px 3fr',
              padding: '8px 12px',
              borderTop: '1px solid rgba(200, 221, 232, 0.08)',
              fontSize: '12px',
              alignItems: 'baseline',
            }}
          >
            <span style={{ color: '#c8dde8', paddingRight: '10px', lineHeight: 1.4 }}>
              {s.condition}
            </span>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '9px',
                color,
                background: `${color}15`,
                borderRadius: '2px',
                padding: '1px 6px',
                textAlign: 'center',
                textTransform: 'uppercase',
                justifySelf: 'start',
              }}
            >
              {s.likelihood ?? '?'}
            </span>
            <span style={{ color: '#8ba4b8', fontSize: '11px', lineHeight: 1.4 }}>
              {s.impact ?? ''}
            </span>
          </div>
        );
      })}
    </div>
  );
}
