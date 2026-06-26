'use client';

import Link from 'next/link';
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Briefcase, Rocket, Users, Compass, ArrowRight } from 'lucide-react';

export interface Opportunity {
  id: string;
  type: 'engagement' | 'venture' | 'lead';
  name: string;
  short_name: string | null;
  status: string | null;
  priority: string | null;
  company: string;
}

interface OpportunitiesBoardProps {
  opportunities: Opportunity[];
}

const PRIORITY_COLORS: Record<string, string> = {
  high: 'bg-red-500/20 text-red-400 border-red-500/30',
  medium: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  low: 'bg-green-500/20 text-green-400 border-green-500/30',
};

const STATUS_COLORS: Record<string, string> = {
  active: 'bg-green-500/20 text-green-400 border-green-500/30',
  warm: 'bg-green-500/20 text-green-400 border-green-500/30',
  hot: 'bg-green-500/20 text-green-400 border-green-500/30',
  exploring: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  researching: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  paused: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  stale: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
  cold: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  closed: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  done: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
};

function statusColor(status: string | null): string {
  if (!status) return 'bg-slate-500/20 text-slate-400 border-slate-500/30';
  return STATUS_COLORS[status.toLowerCase()] || 'bg-slate-500/20 text-slate-400 border-slate-500/30';
}

function OpportunityCard({ opp }: { opp: Opportunity }) {
  const displayName = opp.short_name || opp.name;

  return (
    <Card className="hover:shadow-md transition-shadow flex flex-col">
      <CardHeader className="pb-2">
        <div className="flex items-start justify-between gap-2">
          <CardTitle className="text-sm font-medium leading-tight">{displayName}</CardTitle>
          {opp.priority && (
            <Badge className={`text-xs flex-shrink-0 ${PRIORITY_COLORS[opp.priority]}`}>
              {opp.priority}
            </Badge>
          )}
        </div>
        {opp.company && (
          <p className="text-xs text-muted-foreground">{opp.company}</p>
        )}
      </CardHeader>
      <CardContent className="pb-2 flex-1">
        {opp.status && (
          <Badge className={`text-xs ${statusColor(opp.status)}`}>
            {opp.status}
          </Badge>
        )}
      </CardContent>
      <CardFooter className="pt-0">
        <Link
          href={`/jobhunt/opportunity/${opp.id}`}
          className="text-xs text-primary hover:underline flex items-center gap-1"
        >
          View <ArrowRight className="w-3 h-3" />
        </Link>
      </CardFooter>
    </Card>
  );
}

function Section({
  title,
  icon,
  items,
}: {
  title: string;
  icon: React.ReactNode;
  items: Opportunity[];
}) {
  if (items.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        {icon}
        <h3 className="font-medium">{title}</h3>
        <Badge variant="secondary">{items.length}</Badge>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {items.map((opp) => (
          <OpportunityCard key={opp.id} opp={opp} />
        ))}
      </div>
    </div>
  );
}

export function OpportunitiesBoard({ opportunities }: OpportunitiesBoardProps) {
  const engagements = opportunities.filter((o) => o.type === 'engagement');
  const ventures = opportunities.filter((o) => o.type === 'venture');
  const leads = opportunities.filter((o) => o.type === 'lead');

  if (opportunities.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground gap-3">
        <Compass className="w-10 h-10" />
        <p className="text-sm">No opportunities yet.</p>
        <p className="text-xs">Use the jobhunt skill to add engagements, ventures, or leads.</p>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Stat Cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <Briefcase className="w-5 h-5 text-indigo-400" />
            <div>
              <p className="text-xs text-muted-foreground">Engagements</p>
              <p className="text-2xl font-bold">{engagements.length}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <Rocket className="w-5 h-5 text-purple-400" />
            <div>
              <p className="text-xs text-muted-foreground">Ventures</p>
              <p className="text-2xl font-bold">{ventures.length}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="p-4 flex items-center gap-3">
            <Users className="w-5 h-5 text-emerald-400" />
            <div>
              <p className="text-xs text-muted-foreground">Leads</p>
              <p className="text-2xl font-bold">{leads.length}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Sections */}
      <Section
        title="Engagements"
        icon={<Briefcase className="w-4 h-4 text-indigo-400" />}
        items={engagements}
      />
      <Section
        title="Ventures"
        icon={<Rocket className="w-4 h-4 text-purple-400" />}
        items={ventures}
      />
      <Section
        title="Leads"
        icon={<Users className="w-4 h-4 text-emerald-400" />}
        items={leads}
      />
    </div>
  );
}
