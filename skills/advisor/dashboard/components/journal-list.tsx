'use client';

import Link from 'next/link';
import type { Decision } from './decisions-board';

interface JournalListProps {
  decisions: Decision[];
}

const STATUS_COLORS: Record<string, string> = {
  decided: '#5aadaf',
  reviewed: '#62c4bc',
};

export function JournalList({ decisions }: JournalListProps) {
  if (decisions.length === 0) {
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
        No decided decisions yet. The journal fills as decisions close.
      </div>
    );
  }

  const sorted = [...decisions].sort((a, b) => {
    // Overdue reviews first, then by review date ascending, undated last
    if (!!a.review_due !== !!b.review_due) return a.review_due ? -1 : 1;
    const ad = a.review_date ? String(a.review_date) : '9999';
    const bd = b.review_date ? String(b.review_date) : '9999';
    return ad.localeCompare(bd);
  });

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
          gridTemplateColumns: '2fr 2fr 90px 110px',
          padding: '6px 12px',
          background: 'rgba(12, 22, 40, 0.72)',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '10px',
          textTransform: 'uppercase',
          color: '#5e7387',
          letterSpacing: '0.5px',
        }}
      >
        <span>Decision</span>
        <span>Outcome</span>
        <span>Status</span>
        <span>Review</span>
      </div>
      {sorted.map((d) => {
        const statusColor = STATUS_COLORS[d.status ?? ''] ?? '#5e7387';
        return (
          <div
            key={d.id}
            style={{
              display: 'grid',
              gridTemplateColumns: '2fr 2fr 90px 110px',
              padding: '8px 12px',
              borderTop: '1px solid rgba(200, 221, 232, 0.08)',
              fontSize: '12px',
              alignItems: 'baseline',
              background: d.review_due ? 'rgba(224, 85, 85, 0.06)' : 'transparent',
            }}
          >
            <Link
              href={`/advisor/decision/${d.id}`}
              style={{
                color: '#5aadaf',
                textDecoration: 'underline',
                textUnderlineOffset: '2px',
                paddingRight: '10px',
              }}
            >
              {d.name}
            </Link>
            <span
              style={{
                color: '#8ba4b8',
                fontSize: '11px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
                paddingRight: '10px',
              }}
            >
              {d.outcome ?? ''}
            </span>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '9px',
                color: statusColor,
                textTransform: 'uppercase',
              }}
            >
              {d.status}
            </span>
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '10px',
                color: d.review_due ? '#e05555' : '#5e7387',
              }}
            >
              {d.review_date ? String(d.review_date).slice(0, 10) : '—'}
              {d.review_due ? ' DUE' : ''}
            </span>
          </div>
        );
      })}
    </div>
  );
}
