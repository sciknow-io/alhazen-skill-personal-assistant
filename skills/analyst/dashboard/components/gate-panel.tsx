'use client';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ShieldCheck, ShieldAlert, ShieldQuestion } from 'lucide-react';

export interface GateRecord {
  id: string;
  grounded: string | null;
  missing: string | null;
  name_on_it: string | null;
  passed: boolean | null;
  created_at: string | null;
}

interface GatePanelProps {
  gate: GateRecord | null;
  missionStatus: string;
}

const QUESTIONS: Array<{ key: keyof GateRecord; label: string }> = [
  { key: 'grounded', label: '1. Grounded in real sources, or pattern-matching?' },
  { key: 'missing', label: "2. What's missing that I didn't think to ask?" },
  { key: 'name_on_it', label: '3. Would I put my name on this?' },
];

export function GatePanel({ gate, missionStatus }: GatePanelProps) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm flex items-center gap-2">
          Three-Question Gate
          {gate ? (
            gate.passed ? (
              <Badge className="bg-teal-100 text-teal-800" variant="secondary">
                <ShieldCheck className="h-3 w-3 mr-1" />
                PASSED
              </Badge>
            ) : (
              <Badge className="bg-red-100 text-red-800" variant="secondary">
                <ShieldAlert className="h-3 w-3 mr-1" />
                FAILED
              </Badge>
            )
          ) : (
            <Badge className="bg-slate-100 text-slate-800" variant="secondary">
              <ShieldQuestion className="h-3 w-3 mr-1" />
              NOT RECORDED
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent>
        {gate ? (
          <div className="space-y-2">
            {QUESTIONS.map((q) => (
              <div key={q.key}>
                <p className="text-xs font-medium">{q.label}</p>
                <p className="text-xs text-muted-foreground whitespace-pre-wrap">
                  {(gate[q.key] as string | null) || '-'}
                </p>
              </div>
            ))}
            {gate.created_at && (
              <p className="text-[10px] text-muted-foreground pt-1">
                Recorded {String(gate.created_at)}
              </p>
            )}
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">
            {missionStatus === 'delivered'
              ? 'This mission was delivered WITHOUT a gate - an audit violation. Record the gate retroactively or move the mission back to verifying.'
              : 'Not yet gated. Before delivery, the operator answers: grounded in real sources? what is missing? would I put my name on it?'}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
