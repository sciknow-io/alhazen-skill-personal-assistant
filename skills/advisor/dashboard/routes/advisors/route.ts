import { NextRequest, NextResponse } from 'next/server';
import { listAdvisors } from '@/lib/advisor';

export async function GET(request: NextRequest) {
  const includeRetired =
    request.nextUrl.searchParams.get('include_retired') === 'true';

  try {
    const data = await listAdvisors(includeRetired);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Advisors error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch advisors' },
      { status: 500 }
    );
  }
}
