import { NextRequest, NextResponse } from 'next/server';
import { showStakeholder } from '@/lib/ops';

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  try {
    const data = await showStakeholder(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Stakeholder error:', error);
    return NextResponse.json({ error: 'Failed to fetch stakeholder' }, { status: 500 });
  }
}
