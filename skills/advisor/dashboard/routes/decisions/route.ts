import { NextRequest, NextResponse } from 'next/server';
import { listDecisions } from '@/lib/advisor';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const status = searchParams.get('status') || undefined;
  const stakes = searchParams.get('stakes') || undefined;
  const reviewDue = searchParams.get('review_due') === 'true';
  const journal = searchParams.get('journal') === 'true';

  try {
    const data = await listDecisions({ status, stakes, reviewDue, journal });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Decisions error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch decisions' },
      { status: 500 }
    );
  }
}
