'use client';

import { useState, useEffect, use } from 'react';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface PersonDetail {
  person: {
    id: string;
    name: string;
    description?: string;
    'created-at'?: string;
    'alh-email-address'?: string;
    'alh-linkedin-url'?: string;
  };
  contact_roles: Array<{ opportunity_id: string; opportunity_name: string; role?: string }>;
  collaborations: Array<{ work_id: string; work_name: string; role?: string; strength?: string; since?: string }>;
  notes: Array<{ id: string; name?: string; content?: string; 'created-at'?: string; is_relationship_note?: boolean }>;
  roles: Array<{ id: string; name: string }>;
}

const MONO = "'JetBrains Mono', monospace";

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div style={{
      fontFamily: MONO,
      fontSize: '10px',
      color: '#5e7387',
      textTransform: 'uppercase',
      letterSpacing: '1.4px',
      margin: '24px 0 10px',
    }}>
      {children}
    </div>
  );
}

const STRENGTH_COLORS: Record<string, string> = {
  strong: '#b8c84a',
  working: '#5aadaf',
  weak: '#5e7387',
};

export default function PersonPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [data, setData] = useState<PersonDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/career/person/${id}`)
      .then(r => {
        if (!r.ok) throw new Error('Failed to load person');
        return r.json();
      })
      .then(d => setData(d))
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div style={{ minHeight: '100vh', backgroundColor: '#070d1c', padding: '32px', color: '#5e7387', fontFamily: MONO, fontSize: '12px' }}>
        Loading...
      </div>
    );
  }

  if (error || !data || !data.person) {
    return (
      <div style={{ minHeight: '100vh', backgroundColor: '#070d1c', padding: '32px', color: '#c96a6a', fontFamily: MONO, fontSize: '12px' }}>
        {error || 'Person not found'}
      </div>
    );
  }

  const { person, contact_roles, collaborations, notes, roles } = data;
  const relationshipNotes = (notes || []).filter(n => n.is_relationship_note);
  const otherNotes = (notes || []).filter(n => !n.is_relationship_note);

  return (
    <div style={{
      minHeight: '100vh',
      backgroundColor: '#070d1c',
      fontFamily: "'DM Sans', sans-serif",
      color: '#c8dde8',
      padding: '24px 32px 64px',
      maxWidth: '900px',
    }}>
      <Link href="/career" style={{ fontFamily: MONO, fontSize: '11px', color: '#5e7387', textDecoration: 'none' }}>
        &larr; career
      </Link>

      <h1 style={{
        fontFamily: "'DM Serif Display', serif",
        fontSize: '28px',
        margin: '12px 0 4px',
        color: '#c8dde8',
      }}>
        {person.name}
      </h1>

      <div style={{ display: 'flex', gap: '16px', flexWrap: 'wrap', fontFamily: MONO, fontSize: '11px', color: '#8ba4b8' }}>
        {person['alh-email-address'] && <span>{person['alh-email-address']}</span>}
        {person['alh-linkedin-url'] && (
          <a href={person['alh-linkedin-url']} style={{ color: '#5aadaf' }} target="_blank" rel="noreferrer">LinkedIn</a>
        )}
        {roles && roles.length > 0 && roles.map(r => (
          <span key={r.id} style={{
            color: '#b8c84a',
            border: '1px solid rgba(184, 200, 74, 0.3)',
            borderRadius: '10px',
            padding: '1px 8px',
          }}>
            {r.name}
          </span>
        ))}
      </div>

      {person.description && (
        <p style={{ color: '#8ba4b8', fontSize: '14px', marginTop: '16px', lineHeight: 1.6 }}>
          {person.description}
        </p>
      )}

      {/* Collaborations */}
      <SectionLabel>Collaborations ({(collaborations || []).length})</SectionLabel>
      {(collaborations || []).length === 0 ? (
        <div style={{ color: '#5e7387', fontFamily: MONO, fontSize: '12px' }}>
          No collaborations recorded. Use <code style={{ color: '#5aadaf' }}>career.py link-collaborator</code>.
        </div>
      ) : (
        <div style={{ border: '1px solid rgba(200, 221, 232, 0.08)', borderRadius: '3px', overflow: 'hidden' }}>
          {(collaborations || []).map(c => (
            <div key={c.work_id} style={{
              display: 'grid',
              gridTemplateColumns: '2fr 120px 100px 120px',
              padding: '8px 12px',
              borderTop: '1px solid rgba(200, 221, 232, 0.08)',
              fontSize: '12px',
              alignItems: 'center',
            }}>
              <Link href={`/career/opportunity/${c.work_id}`} style={{ color: '#5aadaf', textDecoration: 'none' }}>
                {c.work_name}
              </Link>
              <span style={{ color: '#8ba4b8', fontFamily: MONO, fontSize: '11px' }}>{c.role || '—'}</span>
              <span style={{ color: STRENGTH_COLORS[c.strength || ''] || '#5e7387', fontFamily: MONO, fontSize: '11px' }}>
                {c.strength || '—'}
              </span>
              <span style={{ color: '#5e7387', fontFamily: MONO, fontSize: '11px' }}>{c.since || ''}</span>
            </div>
          ))}
        </div>
      )}

      {/* Contact roles */}
      <SectionLabel>Contact For ({(contact_roles || []).length})</SectionLabel>
      {(contact_roles || []).length === 0 ? (
        <div style={{ color: '#5e7387', fontFamily: MONO, fontSize: '12px' }}>
          Not a contact on any opportunity.
        </div>
      ) : (
        <div style={{ border: '1px solid rgba(200, 221, 232, 0.08)', borderRadius: '3px', overflow: 'hidden' }}>
          {(contact_roles || []).map(cr => (
            <div key={cr.opportunity_id} style={{
              display: 'grid',
              gridTemplateColumns: '2fr 160px',
              padding: '8px 12px',
              borderTop: '1px solid rgba(200, 221, 232, 0.08)',
              fontSize: '12px',
            }}>
              <Link href={`/career/opportunity/${cr.opportunity_id}`} style={{ color: '#5aadaf', textDecoration: 'none' }}>
                {cr.opportunity_name}
              </Link>
              <span style={{ color: '#8ba4b8', fontFamily: MONO, fontSize: '11px' }}>{cr.role || 'contact'}</span>
            </div>
          ))}
        </div>
      )}

      {/* Relationship notes */}
      <SectionLabel>Relationship Notes ({relationshipNotes.length})</SectionLabel>
      {relationshipNotes.length === 0 ? (
        <div style={{ color: '#5e7387', fontFamily: MONO, fontSize: '12px' }}>
          No relationship notes. Use <code style={{ color: '#5aadaf' }}>career.py add-note --type relationship</code>.
        </div>
      ) : (
        relationshipNotes.map(n => (
          <div key={n.id} style={{
            border: '1px solid rgba(200, 221, 232, 0.08)',
            borderRadius: '3px',
            padding: '12px 16px',
            marginBottom: '10px',
            background: 'rgba(12, 22, 40, 0.72)',
          }}>
            <div style={{ fontFamily: MONO, fontSize: '10px', color: '#5e7387', marginBottom: '6px' }}>
              {n['created-at'] ? String(n['created-at']).slice(0, 10) : ''}
            </div>
            <div style={{ fontSize: '13px', color: '#a9c0d0', lineHeight: 1.6 }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {(n.content || '').replace(/\\n/g, '\n')}
              </ReactMarkdown>
            </div>
          </div>
        ))
      )}

      {/* Other notes */}
      {otherNotes.length > 0 && (
        <>
          <SectionLabel>Other Notes ({otherNotes.length})</SectionLabel>
          {otherNotes.map(n => (
            <div key={n.id} style={{
              border: '1px solid rgba(200, 221, 232, 0.08)',
              borderRadius: '3px',
              padding: '12px 16px',
              marginBottom: '10px',
            }}>
              <div style={{ fontFamily: MONO, fontSize: '10px', color: '#5e7387', marginBottom: '6px' }}>
                {n.name || 'note'} · {n['created-at'] ? String(n['created-at']).slice(0, 10) : ''}
              </div>
              <div style={{ fontSize: '13px', color: '#8ba4b8', lineHeight: 1.6 }}>
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {(n.content || '').replace(/\\n/g, '\n')}
                </ReactMarkdown>
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
