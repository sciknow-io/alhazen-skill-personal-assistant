import { NextRequest, NextResponse } from 'next/server';
import { listMissions, updateMission } from '@/lib/analyst';

export async function GET(request: NextRequest) {
  const status = request.nextUrl.searchParams.get('status') || undefined;

  try {
    const data = await listMissions(status);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Missions error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch missions' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { id, status, priority } = body;
    if (!id) {
      return NextResponse.json({ error: 'id is required' }, { status: 400 });
    }
    const data = await updateMission(id, { status, priority });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Mission update error:', error);
    return NextResponse.json(
      { error: 'Failed to update mission' },
      { status: 500 }
    );
  }
}
