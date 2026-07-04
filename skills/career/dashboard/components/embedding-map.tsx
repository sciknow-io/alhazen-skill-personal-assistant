'use client';

import { useRef, useEffect, useCallback, useState } from 'react';
import * as Plot from '@observablehq/plot';

export interface MapItem {
  id: string;
  short_name: string;
  company: string;
  status: string;
  priority: string | null;
  type: string;
  x: number;
  y: number;
  notes_count?: number;
  created_at?: string | null;
  name?: string;
  summary_text?: string | null;
}

interface EmbeddingMapProps {
  items: MapItem[];
  selectedIds: Set<string>;
  onSelect: (ids: string[]) => void;
}

const TYPE_COLORS: Record<string, string> = {
  position: '#5aadaf',
  engagement: '#5b8ab8',
  venture: '#b8c84a',
  lead: '#62c4bc',
};

function getTypeColor(type: string): string {
  return TYPE_COLORS[type] || '#5e7387';
}

function getPriorityRadius(priority: string | null): number {
  switch (priority) {
    case 'high': return 8;
    case 'medium': return 5;
    case 'low': return 3;
    default: return 4;
  }
}

export function EmbeddingMap({ items, selectedIds, onSelect }: EmbeddingMapProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [dragCurrent, setDragCurrent] = useState<{ x: number; y: number } | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const plotRef = useRef<SVGSVGElement | null>(null);

  useEffect(() => {
    if (!containerRef.current || items.length === 0) return;

    // Clean up old SVG
    const container = containerRef.current;
    while (container.firstChild && container.firstChild !== container.querySelector('.selection-rect')) {
      container.removeChild(container.firstChild);
    }

    // Compute domain with padding so all points are visible and centered
    const xVals = items.map(d => d.x);
    const yVals = items.map(d => d.y);
    const xMin = Math.min(...xVals);
    const xMax = Math.max(...xVals);
    const yMin = Math.min(...yVals);
    const yMax = Math.max(...yVals);
    const xPad = (xMax - xMin) * 0.12 || 1;
    const yPad = (yMax - yMin) * 0.12 || 1;

    const plot = Plot.plot({
      width: container.clientWidth,
      height: container.clientHeight - 4,
      style: {
        background: 'transparent',
        color: '#c8dde8',
      },
      x: { axis: null, domain: [xMin - xPad, xMax + xPad] },
      y: { axis: null, domain: [yMin - yPad, yMax + yPad] },
      marks: [
        Plot.dot(items, {
          x: 'x',
          y: 'y',
          fill: (d: MapItem) => getTypeColor(d.type),
          r: (d: MapItem) => getPriorityRadius(d.priority),
          stroke: (d: MapItem) => selectedIds.has(d.id) ? '#b8c84a' : 'none',
          strokeWidth: (d: MapItem) => selectedIds.has(d.id) ? 2 : 0,
          opacity: 0.85,
          title: (d: MapItem) => {
            const header = `${d.short_name}\n${d.company || ''}\n${d.status || ''} · ${d.priority || ''}\n${d.created_at ? d.created_at.slice(0, 10) : ''}`;
            if (!d.summary_text) return header;
            const plain = d.summary_text.replace(/^#{1,3}\s+/gm, '').replace(/\*\*/g, '').slice(0, 500);
            return `${header}\n---\n${plain}`;
          },
        }),
        Plot.text(items, {
          x: 'x',
          y: 'y',
          text: 'short_name',
          fontSize: 9,
          fill: '#c8dde8',
          dy: 14,
        }),
        Plot.text(items, {
          x: 'x',
          y: 'y',
          text: (d: MapItem) => d.company ? `(${d.company})` : '',
          fontSize: 8,
          fill: '#5e7387',
          dy: 24,
        }),
      ],
    });

    plotRef.current = plot as unknown as SVGSVGElement;
    container.insertBefore(plot, container.firstChild);

    return () => {
      if (container.contains(plot)) {
        container.removeChild(plot);
      }
    };
  }, [items, selectedIds]);

  const getRelativeCoords = useCallback((e: React.MouseEvent) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return { x: e.clientX - rect.left, y: e.clientY - rect.top };
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    const coords = getRelativeCoords(e);
    setDragStart(coords);
    setDragCurrent(coords);
    setIsDragging(true);
  }, [getRelativeCoords]);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging) return;
    setDragCurrent(getRelativeCoords(e));
  }, [isDragging, getRelativeCoords]);

  const handleMouseUp = useCallback(() => {
    if (!isDragging || !dragStart || !dragCurrent || !containerRef.current || !plotRef.current) {
      setIsDragging(false);
      setDragStart(null);
      setDragCurrent(null);
      return;
    }

    const container = containerRef.current;
    const svgRect = container.getBoundingClientRect();
    const plotEl = plotRef.current as unknown as SVGSVGElement;

    // Get the plot's data domain from the SVG viewBox or dimensions
    const plotWidth = plotEl.clientWidth || svgRect.width;
    const plotHeight = plotEl.clientHeight || svgRect.height;

    // Selection bounds in pixel space
    const selLeft = Math.min(dragStart.x, dragCurrent.x);
    const selRight = Math.max(dragStart.x, dragCurrent.x);
    const selTop = Math.min(dragStart.y, dragCurrent.y);
    const selBottom = Math.max(dragStart.y, dragCurrent.y);

    // Only select if drag was meaningful (> 5px)
    if (Math.abs(selRight - selLeft) < 5 && Math.abs(selBottom - selTop) < 5) {
      setIsDragging(false);
      setDragStart(null);
      setDragCurrent(null);
      return;
    }

    // Map pixel bounds to data coordinates
    const xExtent = [Math.min(...items.map(d => d.x)), Math.max(...items.map(d => d.x))];
    const yExtent = [Math.min(...items.map(d => d.y)), Math.max(...items.map(d => d.y))];
    const xPad = (xExtent[1] - xExtent[0]) * 0.05 || 1;
    const yPad = (yExtent[1] - yExtent[0]) * 0.05 || 1;
    const xMin = xExtent[0] - xPad;
    const xMax = xExtent[1] + xPad;
    const yMin = yExtent[0] - yPad;
    const yMax = yExtent[1] + yPad;

    // Approximate margin (Observable Plot default margins)
    const marginLeft = 40;
    const marginRight = 20;
    const marginTop = 20;
    const marginBottom = 30;

    const dataLeft = xMin + ((selLeft - marginLeft) / (plotWidth - marginLeft - marginRight)) * (xMax - xMin);
    const dataRight = xMin + ((selRight - marginLeft) / (plotWidth - marginLeft - marginRight)) * (xMax - xMin);
    const dataTop = yMax - ((selTop - marginTop) / (plotHeight - marginTop - marginBottom)) * (yMax - yMin);
    const dataBottom = yMax - ((selBottom - marginTop) / (plotHeight - marginTop - marginBottom)) * (yMax - yMin);

    const minDataX = Math.min(dataLeft, dataRight);
    const maxDataX = Math.max(dataLeft, dataRight);
    const minDataY = Math.min(dataTop, dataBottom);
    const maxDataY = Math.max(dataTop, dataBottom);

    const selected = items
      .filter(d => d.x >= minDataX && d.x <= maxDataX && d.y >= minDataY && d.y <= maxDataY)
      .map(d => d.id);

    onSelect(selected);

    setIsDragging(false);
    setDragStart(null);
    setDragCurrent(null);
  }, [isDragging, dragStart, dragCurrent, items, onSelect]);

  const selectionStyle: React.CSSProperties | null =
    isDragging && dragStart && dragCurrent
      ? {
          position: 'absolute' as const,
          left: Math.min(dragStart.x, dragCurrent.x),
          top: Math.min(dragStart.y, dragCurrent.y),
          width: Math.abs(dragCurrent.x - dragStart.x),
          height: Math.abs(dragCurrent.y - dragStart.y),
          border: '1px solid #b8c84a',
          backgroundColor: 'rgba(184, 200, 74, 0.1)',
          pointerEvents: 'none' as const,
          zIndex: 10,
        }
      : null;

  return (
    <div
      ref={containerRef}
      style={{
        position: 'relative',
        width: '100%',
        height: '100%',
        cursor: isDragging ? 'crosshair' : 'default',
        userSelect: 'none',
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    >
      {selectionStyle && <div style={selectionStyle} />}
    </div>
  );
}
