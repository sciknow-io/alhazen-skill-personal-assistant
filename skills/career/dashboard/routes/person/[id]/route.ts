import { NextRequest, NextResponse } from 'next/server';
import { getPerson } from '@/lib/career';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const data = await getPerson(id);
    if (!data) {
      return NextResponse.json(
        { error: 'Person not found' },
        { status: 404 }
      );
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error('Person fetch error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch person' },
      { status: 500 }
    );
  }
}
