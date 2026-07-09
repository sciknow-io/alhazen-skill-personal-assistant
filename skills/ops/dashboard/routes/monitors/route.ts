import { NextRequest, NextResponse } from 'next/server';
import { listMonitors } from '@/lib/ops';

export async function GET(request: NextRequest) {
  const status = request.nextUrl.searchParams.get('status') || undefined;
  try {
    const data = await listMonitors(status);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Monitors error:', error);
    return NextResponse.json({ error: 'Failed to fetch monitors' }, { status: 500 });
  }
}
