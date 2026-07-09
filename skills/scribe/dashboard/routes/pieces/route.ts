import { NextRequest, NextResponse } from 'next/server';
import { listPieces, updatePiece } from '@/lib/scribe';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const status = searchParams.get('status') || undefined;
  const type = searchParams.get('type') || undefined;

  try {
    const data = await listPieces({ status, type });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Pieces error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch pieces' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { id, status, goal, deadline } = body;
    if (!id) {
      return NextResponse.json({ error: 'id is required' }, { status: 400 });
    }
    const data = await updatePiece(id, { status, goal, deadline });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Piece update error:', error);
    return NextResponse.json(
      { error: 'Failed to update piece' },
      { status: 500 }
    );
  }
}
