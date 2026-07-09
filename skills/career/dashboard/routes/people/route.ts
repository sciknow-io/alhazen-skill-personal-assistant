import { NextResponse } from 'next/server';
import { listPeople } from '@/lib/career';

export async function GET() {
  try {
    const data = await listPeople();
    return NextResponse.json(data);
  } catch (error) {
    console.error('People error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch people' },
      { status: 500 }
    );
  }
}
