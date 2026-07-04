import { NextRequest, NextResponse } from 'next/server';
import { listFindings, verifyFinding } from '@/lib/analyst';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const mission = searchParams.get('mission') || undefined;
  const divergent = searchParams.get('divergent') === 'true';
  const unverified = searchParams.get('unverified') === 'true';

  try {
    const data = await listFindings({ mission, divergent, unverified });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Findings error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch findings' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { id, status, content } = body;
    if (!id || !status) {
      return NextResponse.json(
        { error: 'id and status are required' },
        { status: 400 }
      );
    }
    const data = await verifyFinding(id, status, content);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Finding verification error:', error);
    return NextResponse.json(
      { error: 'Failed to verify finding' },
      { status: 500 }
    );
  }
}
