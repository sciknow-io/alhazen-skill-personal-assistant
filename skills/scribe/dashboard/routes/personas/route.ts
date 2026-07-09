import { NextResponse } from 'next/server';
import { listPersonas } from '@/lib/scribe';

export async function GET() {
  try {
    const data = await listPersonas();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Personas error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch personas' },
      { status: 500 }
    );
  }
}
