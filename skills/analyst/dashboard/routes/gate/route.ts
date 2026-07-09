import { NextRequest, NextResponse } from 'next/server';
import { listMissions, recordGate } from '@/lib/analyst';

interface MissionSummary {
  id: string;
  name: string;
  status: string;
  gate: { passed: boolean; recorded_at: string } | null;
}

// GET: missions at or past the gate stage, with their gate status.
export async function GET() {
  try {
    const data = (await listMissions()) as { missions?: MissionSummary[] };
    const missions = (data.missions || []).filter((m) =>
      ['verifying', 'gated', 'delivered'].includes(m.status)
    );
    return NextResponse.json({ success: true, missions });
  } catch (error) {
    console.error('Gate list error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch gate status' },
      { status: 500 }
    );
  }
}

// POST: record the three-question gate for a mission.
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { mission, grounded, missing, nameOnIt, passed } = body;
    if (!mission || !grounded || !missing || !nameOnIt || passed === undefined) {
      return NextResponse.json(
        { error: 'mission, grounded, missing, nameOnIt, and passed are required' },
        { status: 400 }
      );
    }
    const data = await recordGate(mission, { grounded, missing, nameOnIt, passed });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Gate record error:', error);
    return NextResponse.json(
      { error: 'Failed to record gate' },
      { status: 500 }
    );
  }
}
