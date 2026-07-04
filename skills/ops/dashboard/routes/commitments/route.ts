import { NextRequest, NextResponse } from 'next/server';
import { listCommitments, updateCommitment } from '@/lib/ops';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const due = searchParams.get('due') || undefined;
  const owedBy = searchParams.get('owedBy') || undefined;
  const status = searchParams.get('status') || undefined;
  const person = searchParams.get('person') || undefined;
  try {
    const data = await listCommitments({ due, owedBy, status, person });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Commitments error:', error);
    return NextResponse.json({ error: 'Failed to fetch commitments' }, { status: 500 });
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { id, status, due } = body as { id?: string; status?: string; due?: string };
    if (!id || (!status && !due)) {
      return NextResponse.json(
        { error: 'id plus status and/or due are required' },
        { status: 400 }
      );
    }
    const data = await updateCommitment(id, { status, due });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Commitment update error:', error);
    return NextResponse.json({ error: 'Failed to update commitment' }, { status: 500 });
  }
}
