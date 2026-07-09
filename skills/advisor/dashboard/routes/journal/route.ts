import { NextResponse } from 'next/server';
import { listJournal } from '@/lib/advisor';

export async function GET() {
  try {
    const data = await listJournal();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Journal error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch journal' },
      { status: 500 }
    );
  }
}
