'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

export interface MapItem {
  id: string;
  short_name: string;
  company: string;
  status: string;
  priority: string | null;
  type: string;
  x: number;
  y: number;
  notes_count?: number;
  name?: string;
  created_at?: string | null;
}

interface OpportunityListProps {
  items: MapItem[];
  visibleIds: Set<string>;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onFilterChange?: (filteredIds: Set<string>) => void;
  onCheckedChange?: (ids: Set<string>) => void;
  resetKey?: number;
}

const PRIORITY_ORDER: Record<string, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

const STATUS_ORDER: Record<string, number> = {
  // position
  researching: 0, applied: 1, interviewing: 2, offer: 3, accepted: 4, rejected: 5, withdrawn: 6,
  // engagement
  proposal: 0, /* active: 1, paused: 2, closed: 3 */
  // venture
  seed: 0, 'series-a': 1, 'series-b': 2, growth: 3, /* closed: 4 */
  // lead
  'first-contact': 0, /* active: 1, inactive: 2, closed: 3 */
  // shared
  active: 1, paused: 2, inactive: 2, closed: 3,
};

const PRIORITY_COLORS: Record<string, string> = {
  high: '#e05555',
  medium: '#d4a843',
  low: '#5aadaf',
};

const TYPE_LABELS: Record<string, string> = {
  position: 'POS',
  engagement: 'ENG',
  venture: 'VEN',
  lead: 'LED',
};

const STATUS_COLORS: Record<string, string> = {
  // position
  interviewing: '#5aadaf',
  applied: '#5b8ab8',
  researching: '#8ba4b8',
  withdrawn: '#5e7387',
  rejected: '#5e7387',
  offer: '#b8c84a',
  accepted: '#4caf7d',
  // engagement
  proposal: '#d4a843',
  // venture
  seed: '#8ba4b8',
  'series-a': '#5b8ab8',
  'series-b': '#5aadaf',
  growth: '#b8c84a',
  // lead
  'first-contact': '#d4a843',
  inactive: '#5e7387',
  // shared
  active: '#5aadaf',
  paused: '#d4a843',
  closed: '#5e7387',
};

function getPrioritySort(p: string | null): number {
  if (!p) return 3;
  return PRIORITY_ORDER[p] ?? 3;
}

function getStatusSort(s: string): number {
  return STATUS_ORDER[s] ?? 3;
}

const TYPE_COLORS: Record<string, string> = {
  position: '#5aadaf',
  engagement: '#5b8ab8',
  venture: '#b8c84a',
  lead: '#62c4bc',
};

// Per-type status pipelines
const TYPE_STATUSES: Record<string, string[]> = {
  position: ['researching', 'applied', 'interviewing', 'offer', 'accepted', 'rejected', 'withdrawn'],
  engagement: ['proposal', 'active', 'paused', 'closed'],
  venture: ['seed', 'series-a', 'series-b', 'growth', 'closed'],
  lead: ['first-contact', 'active', 'inactive', 'closed'],
};

// Default status for items with null status (first stage in the pipeline)
const TYPE_DEFAULT_STATUS: Record<string, string> = {
  position: 'researching',
  engagement: 'proposal',
  venture: 'seed',
  lead: 'first-contact',
};

function effectiveStatus(item: MapItem): string {
  return item.status || TYPE_DEFAULT_STATUS[item.type] || 'researching';
}

// Per-type default-off statuses
const TYPE_DEFAULT_OFF: Record<string, Set<string>> = {
  position: new Set(['withdrawn', 'rejected']),
  engagement: new Set(['closed']),
  venture: new Set(['closed']),
  lead: new Set(['inactive', 'closed']),
};

export function OpportunityList({ items, visibleIds, selectedId, onSelect, onFilterChange, onCheckedChange, resetKey }: OpportunityListProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [activeType, setActiveType] = useState<string>('all'); // 'all' or a specific type
  const [activeStatuses, setActiveStatuses] = useState<Set<string> | null>(null);
  const [checkedIds, setCheckedIds] = useState<Set<string>>(new Set());
  const [copyFeedback, setCopyFeedback] = useState(false);
  const router = useRouter();

  // Reset to 'all' when resetKey changes
  useEffect(() => {
    if (resetKey !== undefined && resetKey > 0) {
      setActiveType('all');
      setActiveStatuses(null);
      setCheckedIds(new Set());
    }
  }, [resetKey]);

  // Compute available types and statuses from visible items
  const visibleItems = items.filter(item => visibleIds.has(item.id));
  const types = Array.from(new Set(visibleItems.map(i => i.type))).sort();
  // Show pipeline statuses for the active type based on items of that type
  const isAll = activeType === 'all';
  const allStatusesForType = isAll ? [] : (TYPE_STATUSES[activeType] || TYPE_STATUSES.position);
  const defaultOffForType = isAll ? new Set<string>() : (TYPE_DEFAULT_OFF[activeType] || TYPE_DEFAULT_OFF.position);
  const typeItems = isAll ? visibleItems : visibleItems.filter(i => i.type === activeType);
  const presentStatuses = isAll ? [] : Array.from(new Set(typeItems.map(i => effectiveStatus(i))));
  const statuses = isAll ? [] : allStatusesForType.filter(s => presentStatuses.includes(s));

  // Initialize filters on first data load
  useEffect(() => {
    if (onFilterChange) {
      setTimeout(() => {
        if (isAll) {
          // All mode: show everything except per-type terminal statuses
          const ids = new Set(
            visibleItems
              .filter(item => {
                const off = TYPE_DEFAULT_OFF[item.type];
                return !off || !off.has(effectiveStatus(item));
              })
              .map(item => item.id)
          );
          onFilterChange(ids);
        } else if (activeStatuses === null && statuses.length > 0) {
          const initial = new Set(statuses.filter(s => !defaultOffForType.has(s)));
          setActiveStatuses(initial);
          const ids = new Set(
            visibleItems
              .filter(item => item.type === activeType)
              .filter(item => initial.has(effectiveStatus(item)))
              .map(item => item.id)
          );
          onFilterChange(ids);
        }
      }, 0);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [items.length]);

  const statusesOn = activeStatuses || new Set(statuses.filter(s => !defaultOffForType.has(s)));

  const filtered = visibleItems
    .filter(item => isAll ? true : item.type === activeType)
    .filter(item => {
      if (isAll) {
        // In all mode, hide per-type terminal statuses
        const off = TYPE_DEFAULT_OFF[item.type];
        return !off || !off.has(effectiveStatus(item));
      }
      return statusesOn.has(effectiveStatus(item));
    })
    .sort((a, b) => {
      const pDiff = getPrioritySort(a.priority) - getPrioritySort(b.priority);
      if (pDiff !== 0) return pDiff;
      return getStatusSort(effectiveStatus(a)) - getStatusSort(effectiveStatus(b));
    });

  const notifyFilter = (type: string, newStatuses: Set<string>) => {
    if (!onFilterChange) return;
    if (type === 'all') {
      // All mode: include items that pass their per-type default-off filter
      const ids = new Set(
        visibleItems
          .filter(item => {
            const off = TYPE_DEFAULT_OFF[item.type];
            return !off || !off.has(effectiveStatus(item));
          })
          .map(item => item.id)
      );
      onFilterChange(ids);
    } else {
      const ids = new Set(
        visibleItems
          .filter(item => item.type === type)
          .filter(item => newStatuses.has(effectiveStatus(item)))
          .map(item => item.id)
      );
      onFilterChange(ids);
    }
  };

  const selectType = (t: string) => {
    setActiveType(t);
    setCheckedIds(new Set());
    if (t === 'all') {
      setActiveStatuses(null);
      notifyFilter('all', new Set());
    } else {
      const newStatuses = TYPE_STATUSES[t] || TYPE_STATUSES.position;
      const newOff = TYPE_DEFAULT_OFF[t] || TYPE_DEFAULT_OFF.position;
      const newActive = new Set(newStatuses.filter(s => !newOff.has(s)));
      setActiveStatuses(newActive);
      notifyFilter(t, newActive);
    }
  };

  const toggleStatus = (s: string) => {
    const next = new Set(statusesOn);
    if (next.has(s)) { next.delete(s); } else { next.add(s); }
    setActiveStatuses(next);
    setCheckedIds(new Set()); // clear checkboxes on filter change
    notifyFilter(activeType, next);
  };

  const handleClick = (id: string) => {
    onSelect(id);
    setExpandedId(expandedId === id ? null : id);
  };

  const copyCheckedToClipboard = (ids: Set<string>) => {
    if (ids.size === 0) return;
    navigator.clipboard.writeText(Array.from(ids).join(', ')).then(() => {
      setCopyFeedback(true);
      setTimeout(() => setCopyFeedback(false), 1500);
    });
  };

  const toggleCheck = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const next = new Set(checkedIds);
    if (next.has(id)) { next.delete(id); } else { next.add(id); }
    setCheckedIds(next);
    copyCheckedToClipboard(next);
    onCheckedChange?.(next);
  };

  const toggleSelectAll = () => {
    const filteredIdSet = new Set(filtered.map(i => i.id));
    const allChecked = filtered.every(i => checkedIds.has(i.id));
    let next: Set<string>;
    if (allChecked) {
      next = new Set(checkedIds);
      filteredIdSet.forEach(id => next.delete(id));
    } else {
      next = new Set(checkedIds);
      filteredIdSet.forEach(id => next.add(id));
    }
    setCheckedIds(next);
    copyCheckedToClipboard(next);
    onCheckedChange?.(next);
  };

  const allFilteredChecked = filtered.length > 0 && filtered.every(i => checkedIds.has(i.id));
  const someFilteredChecked = filtered.some(i => checkedIds.has(i.id));

  return (
    <div style={{
      overflowY: 'auto',
      height: '100%',
      fontFamily: "'DM Sans', sans-serif",
    }}>
      {/* Filter toggles */}
      <div style={{
        padding: '8px 12px',
        borderBottom: '1px solid rgba(94, 115, 135, 0.2)',
        display: 'flex',
        flexWrap: 'wrap',
        gap: '4px',
        alignItems: 'center',
      }}>
        {/* Type selector (single select) */}
        <OptionButton
          key="all"
          label="ALL"
          selected={activeType === 'all'}
          onClick={() => selectType('all')}
          color="#8ba4b8"
          count={visibleItems.length}
        />
        {types.map(t => (
          <OptionButton
            key={t}
            label={TYPE_LABELS[t] || t}
            selected={activeType === t}
            onClick={() => selectType(t)}
            color={TYPE_COLORS[t] || '#8ba4b8'}
            count={visibleItems.filter(i => i.type === t).length}
          />
        ))}
        {/* Status toggles (hidden in all mode) */}
        {!isAll && statuses.length > 0 && (
          <>
            <span key="sep" style={{ width: '1px', height: '16px', background: 'rgba(94,115,135,0.3)', margin: '0 6px' }} />
            <span key="status-label" style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: '9px', color: '#5e7387', marginRight: '2px' }}>STATUS</span>
            {statuses.map(s => (
              <FilterChip
                key={`status-${s}`}
                label={s}
                active={statusesOn.has(s)}
                onClick={() => toggleStatus(s)}
                color={STATUS_COLORS[s] || '#8ba4b8'}
                count={typeItems.filter(i => effectiveStatus(i) === s).length}
              />
            ))}
          </>
        )}
      </div>

      <div style={{
        fontSize: '10px', color: '#5e7387', padding: '4px 12px',
        fontFamily: "'JetBrains Mono', monospace",
        display: 'flex', alignItems: 'center', gap: '8px',
      }}>
        <SelectCheckbox
          checked={allFilteredChecked}
          indeterminate={someFilteredChecked && !allFilteredChecked}
          onChange={toggleSelectAll}
        />
        <span>{filtered.length}{isAll ? ` active of ${visibleItems.length} total` : ` of ${typeItems.length} ${activeType}s`}</span>
        {checkedIds.size > 0 && (
          <span style={{ color: copyFeedback ? '#b8c84a' : '#8ba4b8' }}>
            {copyFeedback ? '✓ copied' : `${checkedIds.size} selected`}
          </span>
        )}
      </div>

      {filtered.length === 0 && (
        <div style={{
          color: '#5e7387',
          textAlign: 'center',
          padding: '40px 16px',
          fontSize: '13px',
        }}>
          No items visible
        </div>
      )}
      {filtered.map(item => {
        const isSelected = selectedId === item.id;
        const isExpanded = expandedId === item.id;
        const priorityColor = PRIORITY_COLORS[item.priority || ''] || '#5e7387';
        const typeLabel = TYPE_LABELS[item.type] || item.type?.toUpperCase()?.slice(0, 3) || '---';
        const itemStatus = effectiveStatus(item);
        const statusColor = STATUS_COLORS[itemStatus] || '#5e7387';

        return (
          <div
            key={item.id}
            onClick={() => handleClick(item.id)}
            style={{
              padding: '8px 12px',
              borderLeft: isSelected ? '2px solid #5aadaf' : '2px solid transparent',
              borderBottom: '1px solid rgba(94, 115, 135, 0.2)',
              cursor: 'pointer',
              backgroundColor: isSelected ? 'rgba(90, 173, 175, 0.06)' : 'transparent',
              transition: 'background-color 0.15s',
            }}
            onMouseEnter={(e) => {
              if (!isSelected) e.currentTarget.style.backgroundColor = 'rgba(90, 173, 175, 0.03)';
            }}
            onMouseLeave={(e) => {
              if (!isSelected) e.currentTarget.style.backgroundColor = 'transparent';
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              {/* Selection checkbox */}
              <SelectCheckbox
                checked={checkedIds.has(item.id)}
                onChange={(e) => toggleCheck(item.id, e as unknown as React.MouseEvent)}
              />

              {/* Priority dot */}
              <div style={{
                width: '7px',
                height: '7px',
                borderRadius: '50%',
                backgroundColor: priorityColor,
                flexShrink: 0,
              }} />

              {/* Type badge */}
              <span style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '9px',
                color: '#8ba4b8',
                border: '1px solid rgba(139, 164, 184, 0.3)',
                borderRadius: '3px',
                padding: '1px 4px',
                letterSpacing: '0.5px',
                flexShrink: 0,
              }}>
                {typeLabel}
              </span>

              {/* Short name */}
              <span style={{
                fontSize: '13px',
                color: '#c8dde8',
                fontFamily: "'DM Sans', sans-serif",
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                flex: 1,
              }}>
                {item.short_name}
              </span>

              {/* Company */}
              <span style={{
                fontSize: '12px',
                color: '#5e7387',
                fontFamily: "'DM Sans', sans-serif",
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                maxWidth: '120px',
                flexShrink: 0,
              }}>
                {item.company}
              </span>

              {/* Status badge */}
              <span style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '9px',
                color: statusColor,
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
                flexShrink: 0,
              }}>
                {itemStatus}
              </span>

              {/* Date */}
              {item.created_at && (
                <span style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: '9px',
                  color: '#5e7387',
                  flexShrink: 0,
                }}>
                  {item.created_at.slice(0, 10)}
                </span>
              )}

            </div>

            {/* Expanded detail */}
            {isExpanded && (
              <div style={{
                marginTop: '8px',
                paddingLeft: '15px',
                fontSize: '12px',
                color: '#8ba4b8',
                lineHeight: '1.6',
              }}>
                <div><span style={{ color: '#5e7387' }}>Full name:</span> {item.name || item.short_name}</div>
                <div><span style={{ color: '#5e7387' }}>Company:</span> {item.company}</div>
                <div><span style={{ color: '#5e7387' }}>Type:</span> {item.type}</div>
                {item.notes_count !== undefined && (
                  <div><span style={{ color: '#5e7387' }}>Notes:</span> {item.notes_count}</div>
                )}
                <div
                  onClick={(e) => {
                    e.stopPropagation();
                    router.push(item.type === 'position' ? `/career/position/${item.id}` : `/career/opportunity/${item.id}`);
                  }}
                  style={{
                    marginTop: '6px',
                    fontFamily: "'JetBrains Mono', monospace",
                    fontSize: '11px',
                    color: '#5aadaf',
                    cursor: 'pointer',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.color = '#b8c84a'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.color = '#5aadaf'; }}
                >
                  View dossier →
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function FilterChip({ label, active, onClick, color, count }: { label: string; active: boolean; onClick: () => void; color: string; count?: number }) {
  return (
    <button
      onClick={onClick}
      style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: '9.5px',
        letterSpacing: '0.4px',
        padding: '2px 7px',
        borderRadius: '3px',
        cursor: 'pointer',
        background: active ? color : 'transparent',
        color: active ? '#070d1c' : color,
        border: `1px solid ${active ? color : 'rgba(200,221,232,0.12)'}`,
        textTransform: 'lowercase',
        opacity: active ? 1 : 0.5,
      }}
    >
      {label}
      {count !== undefined && (
        <span style={{ opacity: 0.6, marginLeft: '3px' }}>{count}</span>
      )}
    </button>
  );
}

function SelectCheckbox({ checked, indeterminate, onChange }: {
  checked: boolean;
  indeterminate?: boolean;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}) {
  return (
    <div
      onClick={(e) => {
        e.stopPropagation();
        onChange(e as unknown as React.ChangeEvent<HTMLInputElement>);
      }}
      style={{
        width: '14px',
        height: '14px',
        borderRadius: '3px',
        border: `1.5px solid ${checked ? '#5aadaf' : indeterminate ? '#8ba4b8' : 'rgba(139,164,184,0.3)'}`,
        background: checked ? '#5aadaf' : indeterminate ? 'rgba(139,164,184,0.3)' : 'transparent',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        flexShrink: 0,
        transition: 'all 0.15s',
      }}
    >
      {checked && (
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M2 5L4 7L8 3" stroke="#070d1c" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      )}
      {indeterminate && !checked && (
        <div style={{ width: '8px', height: '2px', background: '#070d1c', borderRadius: '1px' }} />
      )}
    </div>
  );
}

function OptionButton({ label, selected, onClick, color, count }: {
  label: string; selected: boolean; onClick: () => void; color: string; count?: number;
}) {
  return (
    <button
      onClick={onClick}
      style={{
        fontFamily: "'JetBrains Mono', monospace",
        fontSize: '10px',
        letterSpacing: '0.6px',
        padding: '3px 10px',
        borderRadius: '3px',
        cursor: 'pointer',
        background: selected ? color : 'transparent',
        color: selected ? '#070d1c' : color,
        border: `1.5px solid ${color}`,
        textTransform: 'uppercase',
        fontWeight: selected ? 600 : 400,
        opacity: selected ? 1 : 0.6,
        transition: 'all 0.15s',
      }}
    >
      {label}
      {count !== undefined && (
        <span style={{ opacity: 0.6, marginLeft: '4px' }}>{count}</span>
      )}
    </button>
  );
}
