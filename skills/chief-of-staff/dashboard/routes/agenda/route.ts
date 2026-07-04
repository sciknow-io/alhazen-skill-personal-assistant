import { NextResponse } from 'next/server';
import { getDailyAgenda } from '@/lib/chief-of-staff';

export async function GET() {
  try {
    const data = await getDailyAgenda();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Agenda error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch daily agenda' },
      { status: 500 }
    );
  }
}
