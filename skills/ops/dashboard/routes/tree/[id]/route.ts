import { NextRequest, NextResponse } from 'next/server';
import { showObjectiveTree } from '@/lib/ops';

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  try {
    const data = await showObjectiveTree(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Objective tree error:', error);
    return NextResponse.json({ error: 'Failed to fetch objective tree' }, { status: 500 });
  }
}
