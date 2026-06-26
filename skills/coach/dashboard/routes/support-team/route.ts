import { NextResponse } from "next/server";
import { getSupportTeam } from "@/lib/coach";

export async function GET() {
  try {
    const data = await getSupportTeam() as Record<string, unknown>;
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { success: false, error: String(error) },
      { status: 500 }
    );
  }
}
