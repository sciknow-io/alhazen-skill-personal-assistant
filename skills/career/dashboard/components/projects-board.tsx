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
import { MoreVertical, ExternalLink, Eye } from 'lucide-react';

interface Collaborator {
  id: string;
  name: string;
}

interface Project {
  id: string;
  name: string;
  short_name: string | null;
  role: string;
  status: string;
  url: string;
  priority: string;
  description: string;
  collaborators: Collaborator[];
}

interface ProjectsBoardProps {
  projects: Project[];
  onStatusChange: (projectId: string, newStatus: string) => void;
}

const STATUS_ORDER = [
  'exploring',
  'active',
  'paused',
  'shipped',
  'sunset',
];

const STATUS_COLORS: Record<string, string> = {
  exploring: 'bg-slate-100 text-slate-800',
  active: 'bg-green-100 text-green-800',
  paused: 'bg-amber-100 text-amber-800',
  shipped: 'bg-blue-100 text-blue-800',
  sunset: 'bg-gray-100 text-gray-800',
};

const PRIORITY_COLORS: Record<string, string> = {
  high: 'bg-red-500',
  medium: 'bg-yellow-500',
  low: 'bg-green-500',
};

function ProjectCard({
  project,
  onStatusChange,
}: {
  project: Project;
  onStatusChange: (projectId: string, newStatus: string) => void;
}) {
  return (
    <Card className="mb-1.5 hover:shadow-sm transition-shadow group">
      <CardContent className="p-2">
        <div className="flex items-center justify-between gap-1">
          <Link href={`/career/project/${project.id}`} className="flex-1 min-w-0 cursor-pointer">
            <div className="flex items-center gap-1.5">
              {project.priority === 'high' && (
                <div
                  className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${PRIORITY_COLORS[project.priority]}`}
                  title={`${project.priority} priority`}
                />
              )}
              <span className="text-xs font-medium group-hover:text-primary transition-colors truncate" title={project.name}>
                {project.short_name || project.name}
              </span>
              {project.role && (
                <Badge variant="outline" className="text-[10px] px-1 py-0 flex-shrink-0">
                  {project.role}
                </Badge>
              )}
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
                <Link href={`/career/project/${project.id}`}>
                  <Eye className="w-4 h-4 mr-2" />
                  View Details
                </Link>
              </DropdownMenuItem>
              {project.url && (
                <DropdownMenuItem asChild>
                  <a href={project.url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="w-4 h-4 mr-2" />
                    View Project
                  </a>
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onClick={() => onStatusChange(project.id, 'exploring')}>
                Exploring
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onStatusChange(project.id, 'active')}>
                Active
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onStatusChange(project.id, 'paused')}>
                Paused
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => onStatusChange(project.id, 'shipped')}>
                Shipped
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => onStatusChange(project.id, 'sunset')}
                className="text-red-600"
              >
                Sunset
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>

        {/* Collaborator chips */}
        {project.collaborators?.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1.5">
            {project.collaborators.map((c) => (
              <Link key={c.id} href={`/career/person/${c.id}`}>
                <Badge
                  variant="secondary"
                  className="text-[10px] px-1.5 py-0 hover:bg-primary/10 cursor-pointer"
                >
                  {c.name}
                </Badge>
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function ProjectsBoard({ projects, onStatusChange }: ProjectsBoardProps) {
  // Group projects by status
  const grouped = STATUS_ORDER.reduce((acc, status) => {
    acc[status] = projects.filter((p) => p.status === status);
    return acc;
  }, {} as Record<string, Project[]>);

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
      {STATUS_ORDER.map((status) => (
        <div key={status} className="min-w-0">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-sm font-medium flex items-center justify-between">
                <span className="capitalize">{status}</span>
                <Badge
                  variant="secondary"
                  className={STATUS_COLORS[status]}
                >
                  {grouped[status]?.length || 0}
                </Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              {grouped[status]?.length > 0 ? (
                grouped[status].map((project) => (
                  <ProjectCard
                    key={project.id}
                    project={project}
                    onStatusChange={onStatusChange}
                  />
                ))
              ) : (
                <p className="text-xs text-muted-foreground text-center py-4">
                  No projects
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      ))}
    </div>
  );
}
