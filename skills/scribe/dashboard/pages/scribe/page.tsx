'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { PiecesBoard, Piece } from '@/components/scribe/pieces-board';
import { PersonaCards, Persona } from '@/components/scribe/persona-cards';
import { VoiceProfilePanel, ProfileData } from '@/components/scribe/voice-profile-panel';

const T = {
  bg: '#070d1c',
  fg: '#c8dde8',
  fgDim: '#8ba4b8',
  fgFaint: '#5e7387',
  teal: '#5aadaf',
  mono: "'JetBrains Mono', monospace",
  serif: "'DM Serif Display', serif",
  sans: "'DM Sans', sans-serif",
};

type TabKey = 'pieces' | 'profile' | 'personas';

const TAB_ITEMS: { key: TabKey; label: string }[] = [
  { key: 'pieces', label: 'Pieces' },
  { key: 'profile', label: 'Voice Profile' },
  { key: 'personas', label: 'Personas' },
];

export default function ScribeDashboard() {
  const [activeTab, setActiveTab] = useState<TabKey>('pieces');

  const [pieces, setPieces] = useState<Piece[]>([]);
  const [loadingPieces, setLoadingPieces] = useState(true);

  const [profileData, setProfileData] = useState<ProfileData | null>(null);
  const [profileLoaded, setProfileLoaded] = useState(false);

  const [personas, setPersonas] = useState<Persona[]>([]);
  const [personasLoaded, setPersonasLoaded] = useState(false);

  const fetchPieces = useCallback(async () => {
    setLoadingPieces(true);
    try {
      const res = await fetch('/api/scribe/pieces');
      if (!res.ok) throw new Error('Failed to fetch pieces');
      const data = await res.json();
      setPieces(data.pieces ?? []);
    } catch (err) {
      console.error('Fetch error:', err);
    } finally {
      setLoadingPieces(false);
    }
  }, []);

  useEffect(() => {
    fetchPieces();
  }, [fetchPieces]);

  // Lazy-load Voice Profile and Personas tabs on first switch
  useEffect(() => {
    if (activeTab === 'profile' && !profileLoaded) {
      fetch('/api/scribe/profile')
        .then((r) => r.json())
        .then((data) => setProfileData(data.success ? data : null))
        .catch(() => {})
        .finally(() => setProfileLoaded(true));
    }
    if (activeTab === 'personas' && !personasLoaded) {
      fetch('/api/scribe/personas')
        .then((r) => r.json())
        .then((data) => setPersonas(data.personas ?? []))
        .catch(() => {})
        .finally(() => setPersonasLoaded(true));
    }
  }, [activeTab, profileLoaded, personasLoaded]);

  const handleStatusChange = useCallback(
    async (pieceId: string, newStatus: string) => {
      try {
        await fetch('/api/scribe/pieces', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ id: pieceId, status: newStatus }),
        });
        fetchPieces();
      } catch (err) {
        console.error('Status update error:', err);
      }
    },
    [fetchPieces]
  );

  return (
    <div
      style={{
        width: '100vw',
        minHeight: '100vh',
        backgroundColor: T.bg,
        display: 'flex',
        flexDirection: 'column',
        fontFamily: T.sans,
      }}
    >
      {/* Global header */}
      <div style={{ padding: '12px 16px 0 16px', flexShrink: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <Link
            href="/"
            style={{
              fontFamily: T.mono,
              fontSize: '11px',
              color: T.fgFaint,
              textDecoration: 'none',
            }}
          >
            &larr; hub
          </Link>
          <h1 style={{ fontFamily: T.serif, fontSize: '24px', color: T.fg, margin: 0, lineHeight: 1.2 }}>
            Scribe — Communication Expert
          </h1>
        </div>

        {/* Tab bar */}
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
                fontFamily: T.mono,
                fontSize: '11px',
                letterSpacing: '0.5px',
                color: activeTab === tab.key ? T.fg : T.fgFaint,
                backgroundColor: 'transparent',
                border: 'none',
                borderBottom: activeTab === tab.key ? `2px solid ${T.teal}` : '2px solid transparent',
                padding: '8px 16px',
                cursor: 'pointer',
                transition: 'color 0.15s, border-color 0.15s',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflow: 'auto', padding: '20px 24px' }}>
        {activeTab === 'pieces' &&
          (loadingPieces ? (
            <div style={{ color: T.fgFaint, fontFamily: T.mono, fontSize: '11px' }}>Loading...</div>
          ) : (
            <PiecesBoard pieces={pieces} onStatusChange={handleStatusChange} />
          ))}

        {activeTab === 'profile' &&
          (!profileLoaded ? (
            <div style={{ color: T.fgFaint, fontFamily: T.mono, fontSize: '11px' }}>Loading...</div>
          ) : (
            <VoiceProfilePanel data={profileData} />
          ))}

        {activeTab === 'personas' &&
          (!personasLoaded ? (
            <div style={{ color: T.fgFaint, fontFamily: T.mono, fontSize: '11px' }}>Loading...</div>
          ) : (
            <PersonaCards personas={personas} />
          ))}
      </div>
    </div>
  );
}
