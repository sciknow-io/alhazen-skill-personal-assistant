import { NextRequest, NextResponse } from 'next/server';
import { updateOpportunity } from '@/lib/jobhunt';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { id, status, stage, priority } = body;

    if (!id) {
      return NextResponse.json(
        { error: 'id is required' },
        { status: 400 }
      );
    }

    const data = await updateOpportunity(id, { status, stage, priority });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Opportunity update error:', error);
    return NextResponse.json(
      { error: 'Failed to update opportunity' },
      { status: 500 }
    );
  }
}
