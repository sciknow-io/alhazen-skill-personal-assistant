import { NextResponse } from 'next/server';
import { getToday } from '@/lib/ops';

export async function GET() {
  try {
    const data = await getToday();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Today error:', error);
    return NextResponse.json({ error: 'Failed to fetch today snapshot' }, { status: 500 });
  }
}
