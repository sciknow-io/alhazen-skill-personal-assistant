'use client';

import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Button } from '@/components/ui/button';
import { MoreVertical, Eye } from 'lucide-react';

export interface Piece {
  id: string;
  name: string;
  type: string | null;
  status: string;
  goal: string | null;
  audience_summary: string | null;
  deadline: string | null;
  draft_count: number;
  latest_version: number;
  targets: string[];
}

interface PiecesBoardProps {
  pieces: Piece[];
  onStatusChange: (pieceId: string, newStatus: string) => void;
}

const STATUS_ORDER = [
  'planning',
  'drafting',
  'persona-review',
  'operator-review',
  'final',
  'shipped',
];

const STATUS_COLORS: Record<string, string> = {
  planning: 'bg-slate-100 text-slate-800',
  drafting: 'bg-blue-100 text-blue-800',
  'persona-review': 'bg-purple-100 text-purple-800',
  'operator-review': 'bg-amber-100 text-amber-800',
  final: 'bg-teal-100 text-teal-800',
  shipped: 'bg-green-100 text-green-800',
};

const STATUS_ACTIONS: Array<{ label: string; value: string }> = [
  { label: 'Start Drafting', value: 'drafting' },
  { label: 'Persona Review', value: 'persona-review' },
  { label: 'Operator Review', value: 'operator-review' },
  { label: 'Mark Final', value: 'final' },
  { label: 'Shipped', value: 'shipped' },
];

function PieceCard({
  piece,
  onStatusChange,
}: {
  piece: Piece;
  onStatusChange: (pieceId: string, newStatus: string) => void;
}) {
  return (
    <Card className="mb-1.5 hover:shadow-sm transition-shadow group">
      <CardContent className="p-2">
        <div className="flex items-center justify-between gap-1">
          <Link href={`/scribe/piece/${piece.id}`} className="flex-1 min-w-0 cursor-pointer">
            <div className="flex flex-col gap-0.5">
              <span
                className="text-xs font-medium group-hover:text-primary transition-colors truncate"
                title={piece.name}
              >
                {piece.name}
              </span>
              <span className="text-[10px] text-muted-foreground truncate">
                {piece.type || 'piece'}
                {piece.draft_count > 0 && ` · v${piece.latest_version} (${piece.draft_count} drafts)`}
                {piece.targets.length > 0 && ` · ${piece.targets.length} personas`}
              </span>
            </div>
          </Link>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" className="h-5 w-5 flex-shrink-0">
                <MoreVertical className="h-3 w-3" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem asChild>
                <Link href={`/scribe/piece/${piece.id}`}>
                  <Eye className="w-4 h-4 mr-2" />
                  View Details
                </Link>
              </DropdownMenuItem>
              {STATUS_ACTIONS.filter((a) => a.value !== piece.status).map((action) => (
                <DropdownMenuItem
                  key={action.value}
                  onClick={() => onStatusChange(piece.id, action.value)}
                >
                  {action.label}
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </CardContent>
    </Card>
  );
}

export function PiecesBoard({ pieces, onStatusChange }: PiecesBoardProps) {
  const grouped = STATUS_ORDER.reduce((acc, status) => {
    acc[status] = pieces.filter((p) => p.status === status);
    return acc;
  }, {} as Record<string, Piece[]>);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-6 gap-4">
      {STATUS_ORDER.map((status) => (
        <div key={status} className="min-w-0">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center justify-between">
                <span className="capitalize">{status.replace('-', ' ')}</span>
                <Badge variant="secondary" className={STATUS_COLORS[status]}>
                  {grouped[status]?.length || 0}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              {grouped[status]?.length > 0 ? (
                grouped[status].map((piece) => (
                  <PieceCard key={piece.id} piece={piece} onStatusChange={onStatusChange} />
                ))
              ) : (
                <p className="text-xs text-muted-foreground text-center py-4">No pieces</p>
              )}
            </CardContent>
          </Card>
        </div>
      ))}
    </div>
  );
}
