'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { AlertTriangle } from 'lucide-react';

export interface FindingRow {
  id: string;
  claim: string | null;
  mission_id: string;
  mission_name: string;
  confidence: string | null;
  consensus_count: number | null;
  divergent: boolean | null;
  verification_status: string | null;
  run_ids: string[];
}

interface FindingsTableProps {
  findings: FindingRow[];
  showMissionColumn?: boolean;
}

const VERIFICATION_COLORS: Record<string, string> = {
  unverified: 'bg-slate-100 text-slate-800',
  confirmed: 'bg-green-100 text-green-800',
  refuted: 'bg-red-100 text-red-800',
  'needs-work': 'bg-amber-100 text-amber-800',
};

const CONFIDENCE_COLORS: Record<string, string> = {
  high: 'bg-green-100 text-green-800',
  medium: 'bg-amber-100 text-amber-800',
  low: 'bg-red-100 text-red-800',
};

export function FindingsTable({ findings, showMissionColumn = true }: FindingsTableProps) {
  const [divergentOnly, setDivergentOnly] = useState(false);
  const [unverifiedOnly, setUnverifiedOnly] = useState(false);

  const filtered = findings.filter((f) => {
    if (divergentOnly && f.divergent !== true) return false;
    if (unverifiedOnly && (f.verification_status || 'unverified') !== 'unverified') return false;
    return true;
  });

  return (
    <div>
      <div className="flex items-center gap-2 mb-2">
        <Button
          variant={divergentOnly ? 'default' : 'outline'}
          size="sm"
          className="h-6 text-xs"
          onClick={() => setDivergentOnly(!divergentOnly)}
        >
          <AlertTriangle className="h-3 w-3 mr-1" />
          Divergent only
        </Button>
        <Button
          variant={unverifiedOnly ? 'default' : 'outline'}
          size="sm"
          className="h-6 text-xs"
          onClick={() => setUnverifiedOnly(!unverifiedOnly)}
        >
          Unverified only
        </Button>
        <span className="text-xs text-muted-foreground ml-auto">
          {filtered.length} of {findings.length} findings
        </span>
      </div>

      {filtered.length === 0 ? (
        <p className="text-xs text-muted-foreground py-4">No findings match the filters.</p>
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b text-left">
              <th className="py-1.5 pr-2 font-medium">Claim</th>
              {showMissionColumn && <th className="py-1.5 px-2 font-medium">Mission</th>}
              <th className="py-1.5 px-2 font-medium text-center">Runs</th>
              <th className="py-1.5 px-2 font-medium text-center">Consensus</th>
              <th className="py-1.5 px-2 font-medium text-center">Divergent</th>
              <th className="py-1.5 px-2 font-medium text-center">Verification</th>
              <th className="py-1.5 px-2 font-medium text-center">Confidence</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((f) => (
              <tr
                key={f.id}
                className={`border-b last:border-0 ${f.divergent ? 'bg-amber-50' : ''}`}
              >
                <td className="py-1.5 pr-2 max-w-md">
                  <span className="line-clamp-2" title={f.claim || ''}>
                    {f.claim}
                  </span>
                </td>
                {showMissionColumn && (
                  <td className="py-1.5 px-2">
                    <Link
                      href={`/analyst/mission/${f.mission_id}`}
                      className="text-primary hover:underline"
                    >
                      {f.mission_name}
                    </Link>
                  </td>
                )}
                <td className="py-1.5 px-2 text-center">{f.run_ids.length}</td>
                <td className="py-1.5 px-2 text-center">{f.consensus_count ?? '-'}</td>
                <td className="py-1.5 px-2 text-center">
                  {f.divergent === true ? (
                    <Badge variant="outline" className="text-[10px] border-amber-400 text-amber-700">
                      divergent
                    </Badge>
                  ) : f.divergent === false ? (
                    <span className="text-muted-foreground">no</span>
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </td>
                <td className="py-1.5 px-2 text-center">
                  <Badge
                    variant="secondary"
                    className={`text-[10px] ${VERIFICATION_COLORS[f.verification_status || 'unverified']}`}
                  >
                    {f.verification_status || 'unverified'}
                  </Badge>
                </td>
                <td className="py-1.5 px-2 text-center">
                  {f.confidence ? (
                    <Badge
                      variant="secondary"
                      className={`text-[10px] ${CONFIDENCE_COLORS[f.confidence] || ''}`}
                    >
                      {f.confidence}
                    </Badge>
                  ) : (
                    <span className="text-muted-foreground">-</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
