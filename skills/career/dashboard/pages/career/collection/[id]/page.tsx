'use client';

import { use } from 'react';
import Link from 'next/link';

export default function CollectionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);

  return (
    <div style={{ minHeight: '100vh', background: '#070d1c', color: '#c8dde8', fontFamily: "'DM Sans', system-ui, sans-serif" }}>
      <div style={{ maxWidth: 960, margin: '0 auto', padding: '48px 24px' }}>
        <Link href="/career" style={{ color: '#5aadaf', textDecoration: 'none', fontSize: 13 }}>
          &larr; mission control
        </Link>
        <h1 style={{ fontSize: 24, fontWeight: 700, margin: '24px 0 12px' }}>Collection</h1>
        <p style={{ color: '#8ba3b8', fontSize: 14 }}>Collection ID: {id}</p>
        <p style={{ color: '#5e7387', fontSize: 13, marginTop: 24 }}>
          Collection detail view coming soon.
        </p>
      </div>
    </div>
  );
}
