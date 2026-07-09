'use client';

import Link from 'next/link';

export interface Decision {
  id: string;
  name: string;
  question: string | null;
  status: string | null;
  stakes: string | null;
  operator_style: string | null;
  outcome: string | null;
  review_date: string | null;
  review_due?: boolean;
  created_at: string | null;
}

interface DecisionsBoardProps {
  decisions: Decision[];
}

const STATUS_ORDER = ['framing', 'debating', 'deciding', 'decided', 'reviewed'];

const STATUS_COLORS: Record<string, string> = {
  framing: '#8ba4b8',
  debating: '#5b8ab8',
  deciding: '#b8c84a',
  decided: '#5aadaf',
  reviewed: '#62c4bc',
};

const STAKES_COLORS: Record<string, string> = {
  low: '#5e7387',
  medium: '#5b8ab8',
  high: '#c87a4a',
  irreversible: '#e05555',
};

function StakesBadge({ stakes }: { stakes: string | null }) {
  if (!stakes) return null;
  const color = STAKES_COLORS[stakes] ?? '#5e7387';
  return (
    <span
      style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: '9px',
        color,
        background: `${color}18`,
        border: `1px solid ${color}40`,
        borderRadius: '2px',
        padding: '1px 6px',
        textTransform: 'uppercase',
        letterSpacing: '0.5px',
        flexShrink: 0,
      }}
    >
      {stakes}
    </span>
  );
}

function DecisionCard({ decision }: { decision: Decision }) {
  return (
    <Link
      href={`/advisor/decision/${decision.id}`}
      style={{ textDecoration: 'none', display: 'block' }}
    >
      <div
        style={{
          background: 'rgba(12, 22, 40, 0.72)',
          border: `1px solid ${decision.review_due ? 'rgba(224, 85, 85, 0.5)' : 'rgba(200, 221, 232, 0.08)'}`,
          borderRadius: '3px',
          padding: '10px 12px',
          marginBottom: '8px',
          cursor: 'pointer',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '6px' }}>
          <span style={{ fontSize: '12px', color: '#c8dde8', lineHeight: 1.4 }}>
            {decision.name}
          </span>
          <StakesBadge stakes={decision.stakes} />
        </div>
        {decision.question && decision.question !== decision.name && (
          <div style={{ fontSize: '11px', color: '#8ba4b8', marginTop: '4px', lineHeight: 1.4 }}>
            {decision.question.length > 100 ? decision.question.slice(0, 97) + '...' : decision.question}
          </div>
        )}
        {decision.review_date && (
          <div
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '9px',
              color: decision.review_due ? '#e05555' : '#5e7387',
              marginTop: '6px',
            }}
          >
            review {String(decision.review_date).slice(0, 10)}
            {decision.review_due ? ' — DUE' : ''}
          </div>
        )}
      </div>
    </Link>
  );
}

export function DecisionsBoard({ decisions }: DecisionsBoardProps) {
  const grouped = STATUS_ORDER.reduce((acc, status) => {
    acc[status] = decisions.filter((d) => (d.status || 'framing') === status);
    return acc;
  }, {} as Record<string, Decision[]>);

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${STATUS_ORDER.length}, minmax(0, 1fr))`,
        gap: '12px',
      }}
    >
      {STATUS_ORDER.map((status) => (
        <div key={status} style={{ minWidth: 0 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '8px',
              paddingBottom: '6px',
              borderBottom: `2px solid ${STATUS_COLORS[status]}40`,
            }}
          >
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '10px',
                color: STATUS_COLORS[status],
                textTransform: 'uppercase',
                letterSpacing: '1px',
              }}
            >
              {status}
            </span>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '10px',
                color: '#5e7387',
              }}
            >
              {grouped[status]?.length || 0}
            </span>
          </div>
          {grouped[status]?.length > 0 ? (
            grouped[status].map((decision) => (
              <DecisionCard key={decision.id} decision={decision} />
            ))
          ) : (
            <p
              style={{
                fontSize: '11px',
                color: '#5e7387',
                textAlign: 'center',
                padding: '12px 0',
              }}
            >
              —
            </p>
          )}
        </div>
      ))}
    </div>
  );
}
