import { NextRequest, NextResponse } from 'next/server';
import { listBriefs } from '@/lib/ops';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const spec = searchParams.get('spec') || undefined;
  const limitParam = searchParams.get('limit');
  const limit = limitParam ? parseInt(limitParam, 10) : undefined;
  try {
    const data = await listBriefs(spec, limit);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Briefs error:', error);
    return NextResponse.json({ error: 'Failed to fetch briefs' }, { status: 500 });
  }
}
