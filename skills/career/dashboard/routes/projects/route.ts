import { NextRequest, NextResponse } from 'next/server';
import { listProjects } from '@/lib/career';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const status = searchParams.get('status') || undefined;
  const role = searchParams.get('role') || undefined;

  try {
    const data = await listProjects({ status, role });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Projects error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch projects' },
      { status: 500 }
    );
  }
}
