import { NextRequest, NextResponse } from 'next/server';
import { getPiece } from '@/lib/scribe';

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const data = await getPiece(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Piece detail error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch piece' },
      { status: 500 }
    );
  }
}
