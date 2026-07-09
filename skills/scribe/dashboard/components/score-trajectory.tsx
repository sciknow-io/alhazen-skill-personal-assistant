'use client';

import { useEffect, useRef } from 'react';

export interface TrajectoryPoint {
  version: number;
  clarity: number | null;
  concision: number | null;
  voice: number | null;
  persuasion: number | null;
  overall: number | null;
  would_act: number;
  reviews: number;
}

const DIMENSIONS = ['clarity', 'concision', 'voice', 'persuasion', 'overall'] as const;

const DIM_COLORS: Record<string, string> = {
  clarity: '#5aadaf',
  concision: '#5b8ab8',
  voice: '#b8c84a',
  persuasion: '#c87a4a',
  overall: '#c8dde8',
};

/**
 * Score trajectory chart: one line per dimension (0-10) across draft
 * versions, so the iteration loop can see distance-to-target closing.
 */
export function ScoreTrajectory({ trajectory }: { trajectory: TrajectoryPoint[] }) {
  const chartRef = useRef<HTMLDivElement>(null);

  const scored = trajectory.filter((t) =>
    DIMENSIONS.some((d) => t[d] !== null && t[d] !== undefined)
  );

  useEffect(() => {
    if (!chartRef.current || scored.length === 0) return;

    import('@observablehq/plot').then((Plot) => {
      // Long format: one row per (version, dimension, score)
      const data: Array<{ version: number; dimension: string; score: number }> = [];
      for (const point of scored) {
        for (const dim of DIMENSIONS) {
          const score = point[dim];
          if (score !== null && score !== undefined) {
            data.push({ version: point.version, dimension: dim, score });
          }
        }
      }

      const chart = Plot.plot({
        width: chartRef.current!.clientWidth,
        height: 260,
        marginLeft: 40,
        marginRight: 90,
        style: {
          background: 'transparent',
          color: '#c8dde8',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '11px',
        },
        x: { label: 'Draft version', tickFormat: (d: number) => `v${d}`, ticks: scored.length },
        y: { label: 'Score', domain: [0, 10], grid: true },
        color: {
          domain: [...DIMENSIONS],
          range: DIMENSIONS.map((d) => DIM_COLORS[d]),
          legend: true,
        },
        marks: [
          Plot.line(data, {
            x: 'version',
            y: 'score',
            stroke: 'dimension',
            strokeWidth: 2,
            curve: 'monotone-x',
          }),
          Plot.dot(data, { x: 'version', y: 'score', fill: 'dimension', r: 3, tip: true }),
          Plot.ruleY([8], { stroke: '#5e7387', strokeDasharray: '4,4' }),
        ],
      });

      chartRef.current!.innerHTML = '';
      chartRef.current!.appendChild(chart);
    });
  }, [scored]);

  if (scored.length === 0) {
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
        No dimension scores yet. Score drafts with{' '}
        <code style={{ color: '#5aadaf' }}>scribe.py add-scores</code> to see the trajectory.
      </div>
    );
  }

  return (
    <div>
      <div
        ref={chartRef}
        style={{
          background: 'rgba(12, 22, 40, 0.72)',
          border: '1px solid rgba(200, 221, 232, 0.08)',
          borderRadius: '3px',
          padding: '12px',
        }}
      />
      {/* Would-act ratio per version */}
      <div
        style={{
          display: 'flex',
          gap: '12px',
          marginTop: '8px',
          fontFamily: "'JetBrains Mono', monospace",
          fontSize: '10px',
          color: '#8ba4b8',
          flexWrap: 'wrap',
        }}
      >
        {trajectory.map((t) => (
          <span key={t.version}>
            v{t.version}:{' '}
            <span style={{ color: t.reviews > 0 && t.would_act === t.reviews ? '#b8c84a' : '#c87a4a' }}>
              {t.would_act}/{t.reviews} would act
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
