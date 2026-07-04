import { NextRequest, NextResponse } from 'next/server';
import { showProfile } from '@/lib/scribe';

export async function GET(request: NextRequest) {
  const id = request.nextUrl.searchParams.get('id') || undefined;

  try {
    const data = await showProfile(id);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Profile error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch voice profile' },
      { status: 500 }
    );
  }
}
