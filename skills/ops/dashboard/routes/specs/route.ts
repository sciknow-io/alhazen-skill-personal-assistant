import { NextRequest, NextResponse } from 'next/server';
import { listSpecs } from '@/lib/ops';

export async function GET(request: NextRequest) {
  const status = request.nextUrl.searchParams.get('status') || undefined;
  try {
    const data = await listSpecs(status);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Specs error:', error);
    return NextResponse.json({ error: 'Failed to fetch brief specs' }, { status: 500 });
  }
}
