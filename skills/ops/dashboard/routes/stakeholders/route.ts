import { NextResponse } from 'next/server';
import { listStakeholders } from '@/lib/ops';

export async function GET() {
  try {
    const data = await listStakeholders();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Stakeholders error:', error);
    return NextResponse.json({ error: 'Failed to fetch stakeholders' }, { status: 500 });
  }
}
