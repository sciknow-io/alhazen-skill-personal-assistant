import { NextRequest, NextResponse } from 'next/server';
import { listOpportunities } from '@/lib/jobhunt';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const type = searchParams.get('type') || 'all';
  const status = searchParams.get('status') || undefined;
  const priority = searchParams.get('priority') || undefined;

  try {
    const data = await listOpportunities({ type, status, priority });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Opportunities error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch opportunities' },
      { status: 500 }
    );
  }
}
