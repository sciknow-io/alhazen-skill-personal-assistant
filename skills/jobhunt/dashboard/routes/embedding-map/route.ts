import { NextResponse } from 'next/server';
import { getEmbeddingMap } from '@/lib/jobhunt';

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const excludeParam = searchParams.get('exclude');
    const excludeIds = excludeParam ? excludeParam.split(',') : undefined;
    const data = await getEmbeddingMap(excludeIds);
    return NextResponse.json(data);
  } catch (error) {
    console.error('Failed to get embedding map:', error);
    return NextResponse.json(
      { success: false, error: 'Failed to compute embedding map' },
      { status: 500 }
    );
  }
}
