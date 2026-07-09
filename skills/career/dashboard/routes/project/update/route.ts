import { NextRequest, NextResponse } from 'next/server';
import { updateProject } from '@/lib/career';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { id, role, status, url, priority } = body;

    if (!id) {
      return NextResponse.json(
        { error: 'id is required' },
        { status: 400 }
      );
    }

    const data = await updateProject(id, { role, status, url, priority });
    return NextResponse.json(data);
  } catch (error) {
    console.error('Project update error:', error);
    return NextResponse.json(
      { error: 'Failed to update project' },
      { status: 500 }
    );
  }
}
