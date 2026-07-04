'use client';

import Link from 'next/link';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Users } from 'lucide-react';

export interface Person {
  id: string;
  name: string;
  description: string;
  collaborations: number;
  contact_roles: number;
}

interface PeopleTableProps {
  people: Person[];
}

export function PeopleTable({ people }: PeopleTableProps) {
  return (
    <div className="space-y-4">
      {/* Summary */}
      <div className="flex items-center gap-4 p-4 bg-muted rounded-lg">
        <Users className="w-5 h-5 text-muted-foreground" />
        <div className="flex-1">
          <div className="text-sm font-medium">People</div>
          <div className="text-xs text-muted-foreground">
            The career graph: contacts, mentors, sponsors, references, and collaborators
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold">{people.length}</div>
          <div className="text-xs text-muted-foreground">people</div>
        </div>
      </div>

      {/* Table */}
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Context</TableHead>
            <TableHead>Collaborations</TableHead>
            <TableHead>Contact Roles</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {people.map((p) => (
            <TableRow key={p.id}>
              <TableCell className="font-medium">
                <Link
                  href={`/career/person/${p.id}`}
                  className="text-primary hover:underline"
                >
                  {p.name}
                </Link>
              </TableCell>
              <TableCell className="text-sm text-muted-foreground max-w-md truncate">
                {p.description || '-'}
              </TableCell>
              <TableCell>
                {p.collaborations > 0 ? (
                  <Badge className="bg-green-100 text-green-800">{p.collaborations}</Badge>
                ) : (
                  <span className="text-muted-foreground text-sm">-</span>
                )}
              </TableCell>
              <TableCell>
                {p.contact_roles > 0 ? (
                  <Badge className="bg-blue-100 text-blue-800">{p.contact_roles}</Badge>
                ) : (
                  <span className="text-muted-foreground text-sm">-</span>
                )}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>

      {people.length === 0 && (
        <div className="text-center py-8 text-muted-foreground">
          No people yet. Add contacts and collaborators with career.py add-person.
        </div>
      )}
    </div>
  );
}
