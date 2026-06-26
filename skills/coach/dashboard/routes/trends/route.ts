import { NextResponse } from "next/server";
import { getTrends } from "@/lib/coach";

export async function GET() {
  try {
    const data = await getTrends() as Record<string, unknown>;
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { success: false, error: String(error) },
      { status: 500 }
    );
  }
}
