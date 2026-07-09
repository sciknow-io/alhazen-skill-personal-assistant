import { NextRequest, NextResponse } from 'next/server';
import { getMission } from '@/lib/analyst';

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const data = await getMission(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Mission detail error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch mission' },
      { status: 500 }
    );
  }
}
