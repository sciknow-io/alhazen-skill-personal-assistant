import { NextRequest, NextResponse } from 'next/server';
import { getDecision } from '@/lib/advisor';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const data = await getDecision(id);
    if (!data) {
      return NextResponse.json(
        { error: 'Decision not found' },
        { status: 404 }
      );
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error('Decision fetch error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch decision' },
      { status: 500 }
    );
  }
}
