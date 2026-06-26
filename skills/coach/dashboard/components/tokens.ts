// Starry Night design tokens — shared across all coach dashboard components
export const T = {
  bg:        '#070d1c',
  bgRaised:  '#0c1628',
  bgSunken:  '#050a16',
  panel:     'rgba(12, 22, 40, 0.72)',
  panelHi:   'rgba(20, 34, 58, 0.85)',
  border:    'rgba(90, 173, 175, 0.18)',
  borderHi:  'rgba(90, 173, 175, 0.42)',
  borderDim: 'rgba(200, 221, 232, 0.08)',
  fg:        '#c8dde8',
  fgDim:     '#8ba4b8',
  fgFaint:   '#5e7387',
  teal:      '#5aadaf',
  tealDim:   'rgba(90, 173, 175, 0.18)',
  blue:      '#5b8ab8',
  blueDim:   'rgba(91, 138, 184, 0.18)',
  olive:     '#b8c84a',
  oliveDim:  'rgba(184, 200, 74, 0.18)',
  mint:      '#62c4bc',
  rust:      '#c87a4a',
  rustDim:   'rgba(200, 122, 74, 0.18)',
  mono:      'ui-monospace, "JetBrains Mono", "SF Mono", Menlo, monospace',
  serif:     '"DM Serif Display", "Iowan Old Style", Georgia, serif',
  sans:      '"DM Sans", -apple-system, system-ui, sans-serif',
};

// Trend direction → color
export function trendColor(direction: string): string {
  if (direction === 'improving') return T.mint;
  if (direction === 'regressing') return T.rust;
  return T.fgDim;
}

// Trend direction → arrow
export function trendArrow(direction: string): string {
  if (direction === 'improving') return '▲';
  if (direction === 'regressing') return '▼';
  return '—';
}

// Format metric name: step_count → Step Count
export function fmtMetric(type: string): string {
  return type.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

// Format number with max 1 decimal
export function fmtNum(n: number | null | undefined): string {
  if (n == null) return '—';
  return n.toLocaleString(undefined, { maximumFractionDigits: 1 });
}

// Format date string to short date
export function fmtDate(d: string | null | undefined): string {
  if (!d) return '—';
  const s = String(d);
  // Handle TypeDB datetime format or ISO
  const date = new Date(s.replace(' ', 'T'));
  if (isNaN(date.getTime())) return s.slice(0, 10);
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}
