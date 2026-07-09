'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { DecisionsBoard, Decision } from '@/components/advisor/decisions-board';
import { AdvisorRoster, Advisor } from '@/components/advisor/advisor-roster';
import { JournalList } from '@/components/advisor/journal-list';

type TabKey = 'decisions' | 'board' | 'journal';

const STAKES_FILTERS = ['all', 'low', 'medium', 'high', 'irreversible'];

export default function AdvisorHub() {
  const [activeTab, setActiveTab] = useState<TabKey>('decisions');
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [advisors, setAdvisors] = useState<Advisor[]>([]);
  const [journal, setJournal] = useState<Decision[]>([]);
  const [stakesFilter, setStakesFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [loadedTabs, setLoadedTabs] = useState<Set<TabKey>>(new Set(['decisions']));

  useEffect(() => {
    fetch('/api/advisor/decisions')
      .then((r) => r.json())
      .then((data) => setDecisions(data.decisions ?? []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Lazy-load board and journal tabs on first switch
  useEffect(() => {
    if (activeTab === 'board' && !loadedTabs.has('board')) {
      setLoadedTabs((prev) => new Set(prev).add('board'));
      fetch('/api/advisor/advisors')
        .then((r) => r.json())
        .then((data) => setAdvisors(data.advisors ?? []))
        .catch(() => {});
    }
    if (activeTab === 'journal' && !loadedTabs.has('journal')) {
      setLoadedTabs((prev) => new Set(prev).add('journal'));
      fetch('/api/advisor/journal')
        .then((r) => r.json())
        .then((data) => setJournal(data.decisions ?? []))
        .catch(() => {});
    }
  }, [activeTab, loadedTabs]);

  const filteredDecisions =
    stakesFilter === 'all'
      ? decisions
      : decisions.filter((d) => d.stakes === stakesFilter);

  const reviewsDue = decisions.filter((d) => d.review_due).length;

  const TAB_ITEMS: { key: TabKey; label: string }[] = [
    { key: 'decisions', label: 'Decisions' },
    { key: 'board', label: 'Board' },
    { key: 'journal', label: 'Journal' },
  ];

  return (
    <div
      style={{
        width: '100vw',
        minHeight: '100vh',
        backgroundColor: '#070d1c',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: "'DM Sans', sans-serif",
      }}
    >
      {/* ── Global header ── */}
      <div style={{ padding: '12px 16px 0 16px', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Link
            href="/"
            style={{
              fontFamily: "'JetBrains Mono', monospace",
              fontSize: '11px',
              color: '#5e7387',
              textDecoration: 'none',
            }}
          >
            &larr; hub
          </Link>
          <h1
            style={{
              fontFamily: "'DM Serif Display', serif",
              fontSize: '24px',
              color: '#c8dde8',
              margin: 0,
              lineHeight: 1.2,
            }}
          >
            Board of Advisors
          </h1>
          {reviewsDue > 0 && (
            <span
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '10px',
                color: '#e05555',
                background: 'rgba(224, 85, 85, 0.12)',
                border: '1px solid rgba(224, 85, 85, 0.4)',
                borderRadius: '3px',
                padding: '2px 8px',
                letterSpacing: '0.5px',
              }}
            >
              {reviewsDue} review{reviewsDue > 1 ? 's' : ''} due
            </span>
          )}

          {/* Stakes filter (decisions tab only) */}
          {activeTab === 'decisions' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginLeft: 'auto' }}>
              <span
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: '10px',
                  color: '#5e7387',
                  textTransform: 'uppercase',
                  letterSpacing: '0.8px',
                }}
              >
                Stakes
              </span>
              <select
                value={stakesFilter}
                onChange={(e) => setStakesFilter(e.target.value)}
                style={{
                  fontFamily: "'JetBrains Mono', monospace",
                  fontSize: '12px',
                  color: '#c8dde8',
                  background: 'rgba(12, 22, 40, 0.72)',
                  border: '1px solid rgba(90, 173, 175, 0.18)',
                  borderRadius: '3px',
                  padding: '4px 10px',
                  cursor: 'pointer',
                  outline: 'none',
                }}
              >
                {STAKES_FILTERS.map((s) => (
                  <option key={s} value={s} style={{ background: '#0c1628' }}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* ── Tab bar ── */}
        <div
          style={{
            display: 'flex',
            gap: '0',
            marginTop: '10px',
            borderBottom: '1px solid rgba(94, 115, 135, 0.2)',
          }}
        >
          {TAB_ITEMS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              style={{
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '11px',
                letterSpacing: '0.5px',
                color: activeTab === tab.key ? '#c8dde8' : '#5e7387',
                backgroundColor: 'transparent',
                border: 'none',
                borderBottom:
                  activeTab === tab.key ? '2px solid #5aadaf' : '2px solid transparent',
                padding: '8px 16px',
                cursor: 'pointer',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab content ── */}
      <div style={{ flex: 1, overflow: 'auto', padding: '20px 24px' }}>
        {activeTab === 'decisions' &&
          (loading ? (
            <div
              style={{
                color: '#5e7387',
                fontFamily: "'JetBrains Mono', monospace",
                fontSize: '11px',
                textAlign: 'center',
                padding: '40px',
              }}
            >
              Loading...
            </div>
          ) : (
            <DecisionsBoard decisions={filteredDecisions} />
          ))}

        {activeTab === 'board' && <AdvisorRoster advisors={advisors} />}

        {activeTab === 'journal' && <JournalList decisions={journal} />}
      </div>
    </div>
  );
}
