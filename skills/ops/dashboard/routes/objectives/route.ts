import { NextRequest, NextResponse } from 'next/server';
import { listObjectives } from '@/lib/ops';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const status = searchParams.get('status') || undefined;
  try {
    const data = await listObjectives(status);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Objectives error:', error);
    return NextResponse.json({ error: 'Failed to fetch objectives' }, { status: 500 });
  }
}
