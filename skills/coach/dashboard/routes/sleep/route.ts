import { NextResponse } from "next/server";
import { getSleepSummary } from "@/lib/coach";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const days = parseInt(searchParams.get("days") || "7", 10);
    const data = await getSleepSummary(days) as Record<string, unknown>;
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { success: false, error: String(error) },
      { status: 500 }
    );
  }
}
