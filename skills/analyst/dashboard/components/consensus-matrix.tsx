'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Check, AlertTriangle } from 'lucide-react';

export interface Run {
  id: string;
  model: string | null;
  status: string | null;
}

export interface Finding {
  id: string;
  claim: string | null;
  confidence: string | null;
  consensus_count: number | null;
  divergent: boolean | null;
  verification_status: string | null;
  run_ids: string[];
}

interface ConsensusMatrixProps {
  findings: Finding[];
  runs: Run[];
}

const VERIFICATION_COLORS: Record<string, string> = {
  unverified: 'bg-slate-100 text-slate-800',
  confirmed: 'bg-green-100 text-green-800',
  refuted: 'bg-red-100 text-red-800',
  'needs-work': 'bg-amber-100 text-amber-800',
};

export function ConsensusMatrix({ findings, runs }: ConsensusMatrixProps) {
  const sorted = [...findings].sort(
    (a, b) => (b.consensus_count ?? b.run_ids.length) - (a.consensus_count ?? a.run_ids.length)
  );

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">
          Consensus Matrix
          <span className="ml-2 text-xs font-normal text-muted-foreground">
            {findings.length} findings x {runs.length} runs — 100% consensus is likely
            factual; single-thread claims need investigation
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {sorted.length === 0 ? (
          <p className="text-xs text-muted-foreground">No findings recorded yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b text-left">
                  <th className="py-1.5 pr-2 font-medium">Claim</th>
                  {runs.map((r) => (
                    <th key={r.id} className="py-1.5 px-2 font-medium text-center" title={r.id}>
                      {r.model || r.id}
                    </th>
                  ))}
                  <th className="py-1.5 px-2 font-medium text-center">Consensus</th>
                  <th className="py-1.5 px-2 font-medium text-center">Verification</th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((f) => (
                  <tr
                    key={f.id}
                    className={`border-b last:border-0 ${f.divergent ? 'bg-amber-50' : ''}`}
                  >
                    <td className="py-1.5 pr-2 max-w-md">
                      <div className="flex items-center gap-1">
                        {f.divergent && (
                          <AlertTriangle
                            className="h-3 w-3 text-amber-600 flex-shrink-0"
                            aria-label="divergent claim"
                          />
                        )}
                        <span className="truncate" title={f.claim || ''}>
                          {f.claim}
                        </span>
                      </div>
                    </td>
                    {runs.map((r) => (
                      <td key={r.id} className="py-1.5 px-2 text-center">
                        {f.run_ids.includes(r.id) ? (
                          <Check className="h-3.5 w-3.5 text-green-600 inline" />
                        ) : (
                          <span className="text-muted-foreground">·</span>
                        )}
                      </td>
                    ))}
                    <td className="py-1.5 px-2 text-center">
                      {f.consensus_count ?? f.run_ids.length}/{runs.length || 1}
                    </td>
                    <td className="py-1.5 px-2 text-center">
                      <Badge
                        variant="secondary"
                        className={`text-[10px] ${VERIFICATION_COLORS[f.verification_status || 'unverified']}`}
                      >
                        {f.verification_status || 'unverified'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
