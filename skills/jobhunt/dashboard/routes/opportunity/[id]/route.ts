import { NextRequest, NextResponse } from 'next/server';
import { getOpportunity } from '@/lib/jobhunt';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;

  try {
    const data = await getOpportunity(id);
    if (!data) {
      return NextResponse.json(
        { error: 'Opportunity not found' },
        { status: 404 }
      );
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error('Opportunity fetch error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch opportunity' },
      { status: 500 }
    );
  }
}
