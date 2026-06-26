import { NextResponse } from 'next/server';
import { queryTypeQL } from '@/lib/agentic-memory';

export async function GET() {
  try {
    const result = await queryTypeQL(
      `match
        $role isa jhunt-job-seeker-role, has id $rid, has name $rname, has alh-role-status $st;
        (bearer: $p, borne-role: $role) isa alh-role-bearing;
        $p has id $pid, has name $pname;
      fetch {
        "role_id": $rid,
        "role_name": $rname,
        "status": $st,
        "person_id": $pid,
        "person_name": $pname
      };`,
      50
    );

    if (!result.success) {
      return NextResponse.json({ seekers: [] });
    }

    return NextResponse.json({ seekers: result.results });
  } catch (error) {
    console.error('seekers error:', error);
    return NextResponse.json({ seekers: [] });
  }
}
