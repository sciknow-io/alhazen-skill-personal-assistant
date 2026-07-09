#!/usr/bin/env python3
"""
Chief of Staff CLI - Read-only cross-view over the executive AI team.

Not a task assistant: a cross-view of decisions (advisor), communications
(scribe), research (analyst), operations (ops), and career moves (career).
This script only READS other skills' namespaces; it defines no schema of its
own. Claude does the sensemaking and the orchestration.

Usage:
    uv run python skills/chief-of-staff/chief_of_staff.py <command>

Commands:
    daily-agenda     JSON cross-skill agenda: ops today + advisor reviews due +
                     scribe pieces awaiting review + analyst gates pending +
                     career deadlines
    weekly-review    JSON cross-skill week-in-review rollup
    report-agenda    Markdown daily agenda
    report-week      Markdown weekly review

Environment:
    TYPEDB_HOST       TypeDB server host (default: localhost)
    TYPEDB_PORT       TypeDB server port (default: 1729)
    TYPEDB_DATABASE   Database name (default: alh_personal)

Each section degrades gracefully: if a team member's skill (and therefore its
namespace) is not installed, that section reports `available: false` instead
of failing the whole agenda.
"""

import argparse
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timedelta, timezone

try:
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB

    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print(
        "Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=3.8.0'",
        file=sys.stderr,
    )

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
# This skill's data lives in alh_personal (see .standalone-db). The marker wins
# over an ambient TYPEDB_DATABASE so shared runtimes (e.g. the skill gateway,
# whose global env targets alhazen_notebook) still hit the right database.
# TYPEDB_DATABASE_OVERRIDE forces a specific database for testing/migration.
_MARKER_DB = "alh_personal" if (Path(__file__).resolve().parent / ".standalone-db").exists() else None
TYPEDB_DATABASE = (
    os.getenv("TYPEDB_DATABASE_OVERRIDE")
    or _MARKER_DB
    or os.getenv("TYPEDB_DATABASE", "alh_personal")
)
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")


def get_driver():
    """Get TypeDB driver connection (compatible with typedb-driver 3.8+)."""
    try:
        options = DriverOptions(is_tls_enabled=False)
    except TypeError:
        from typedb.driver import DriverTlsConfig

        options = DriverOptions(DriverTlsConfig.disabled())
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        options,
    )


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def try_fetch(tx, query: str):
    """Run a fetch query; return (True, rows) or (False, []) if the namespace
    is absent (skill not installed) or the query fails."""
    try:
        return True, list(tx.query(query).resolve())
    except Exception:
        return False, []


# ---------------------------------------------------------------------------
# Section collectors — one per team member, all read-only
# ---------------------------------------------------------------------------


def collect_ops(tx):
    """Active objectives, overdue work items, open commitments, active brief specs, upcoming preps."""
    section = {"available": False, "objectives": [], "overdue_items": [],
               "open_commitments": [], "active_specs": [], "upcoming_preps": []}
    ok, rows = try_fetch(tx, '''match
        $c isa ops-commitment, has ops-commitment-status $s;
        { $s == "open"; } or { $s == "overdue"; };
    fetch { "id": $c.id, "name": $c.name, "status": $s,
            "owed_by": $c.ops-owed-by, "due": $c.ops-due-date };''')
    if not ok:
        return section
    section["available"] = True
    section["open_commitments"] = rows

    # OKR spine: active / at-risk objectives (the primary planning element)
    _, objectives = try_fetch(tx, '''match
        $o isa ops-objective, has ops-objective-status $st;
        { $st == "active"; } or { $st == "at-risk"; };
    fetch { "id": $o.id, "name": $o.name, "status": $st,
            "period": $o.ops-objective-period };''')
    section["objectives"] = objectives

    # Overdue leaf work: target date past, not done/dropped
    now = now_utc().isoformat()
    _, overdue = try_fetch(tx, f'''match
        $w isa ops-workitem, has ops-target-date $d, has ops-workitem-status $s;
        $d < {json.dumps(now)};
        not {{ $s == "done"; }};
        not {{ $s == "dropped"; }};
    fetch {{ "id": $w.id, "name": $w.name, "status": $s,
             "kind": $w.ops-workitem-kind, "due": $d }};''')
    section["overdue_items"] = overdue

    _, specs = try_fetch(tx, '''match
        $sp isa ops-brief-spec, has ops-spec-status $st;
        { $st == "trial"; } or { $st == "active"; };
    fetch { "id": $sp.id, "name": $sp.name, "status": $st,
            "cadence": $sp.ops-cadence, "trial_runs": $sp.ops-trial-runs,
            "trial_target": $sp.ops-trial-target };''')
    section["active_specs"] = specs

    horizon = (now_utc() + timedelta(days=7)).isoformat()
    _, preps = try_fetch(tx, f'''match
        $p isa ops-meeting-prep, has ops-meeting-date $d;
        $d <= {json.dumps(horizon)};
    fetch {{ "id": $p.id, "title": $p.ops-meeting-title, "date": $d }};''')
    section["upcoming_preps"] = preps
    return section


def collect_advisor(tx):
    """Decisions in flight and journal reviews that have come due."""
    section = {"available": False, "in_flight": [], "reviews_due": []}
    ok, rows = try_fetch(tx, '''match
        $d isa advsr-decision, has advsr-decision-status $s;
        { $s == "framing"; } or { $s == "debating"; } or { $s == "deciding"; };
    fetch { "id": $d.id, "name": $d.name, "status": $s,
            "question": $d.advsr-question, "stakes": $d.advsr-stakes };''')
    if not ok:
        return section
    section["available"] = True
    section["in_flight"] = rows

    today = now_utc().isoformat()
    _, due = try_fetch(tx, f'''match
        $d isa advsr-decision, has advsr-decision-status "decided",
            has advsr-review-date $r;
        $r <= {json.dumps(today)};
    fetch {{ "id": $d.id, "name": $d.name, "review_date": $r,
             "outcome": $d.advsr-outcome }};''')
    section["reviews_due"] = due
    return section


def collect_scribe(tx):
    """Pieces awaiting persona or operator review."""
    section = {"available": False, "awaiting_review": [], "in_draft": []}
    ok, rows = try_fetch(tx, '''match
        $p isa scribe-piece, has scribe-piece-status $s;
        { $s == "persona-review"; } or { $s == "operator-review"; };
    fetch { "id": $p.id, "name": $p.name, "status": $s,
            "type": $p.scribe-piece-type, "goal": $p.scribe-goal };''')
    if not ok:
        return section
    section["available"] = True
    section["awaiting_review"] = rows

    _, drafting = try_fetch(tx, '''match
        $p isa scribe-piece, has scribe-piece-status $s;
        { $s == "planning"; } or { $s == "drafting"; };
    fetch { "id": $p.id, "name": $p.name, "status": $s,
            "type": $p.scribe-piece-type };''')
    section["in_draft"] = drafting
    return section


def collect_analyst(tx):
    """Missions pending the three-question gate, and running missions."""
    section = {"available": False, "pending_gate": [], "running": []}
    ok, rows = try_fetch(tx, '''match
        $m isa anlst-mission, has anlst-mission-status $s;
        { $s == "aggregating"; } or { $s == "verifying"; };
    fetch { "id": $m.id, "name": $m.name, "status": $s,
            "decision_context": $m.anlst-decision-context };''')
    if not ok:
        return section
    section["available"] = True
    section["pending_gate"] = rows

    _, running = try_fetch(tx, '''match
        $m isa anlst-mission, has anlst-mission-status $s;
        { $s == "briefing"; } or { $s == "planning"; } or { $s == "running"; };
    fetch { "id": $m.id, "name": $m.name, "status": $s };''')
    section["running"] = running
    return section


def collect_career(tx):
    """Opportunities with approaching deadlines and active projects."""
    section = {"available": False, "deadlines": [], "active_projects": []}
    horizon = (now_utc() + timedelta(days=14)).isoformat()
    ok, rows = try_fetch(tx, f'''match
        $o isa career-opportunity, has career-deadline $d;
        $d <= {json.dumps(horizon)};
    fetch {{ "id": $o.id, "name": $o.name, "deadline": $d,
             "status": $o.career-opportunity-status }};''')
    # A missing deadline attribute is not proof the namespace is absent, so
    # probe the base type too before declaring unavailable.
    if not ok:
        ok, _ = try_fetch(tx, 'match $o isa career-opportunity; fetch { "id": $o.id };')
        if not ok:
            return section
    section["available"] = True
    section["deadlines"] = rows

    _, projects = try_fetch(tx, '''match
        $p isa career-project, has career-project-status "active";
    fetch { "id": $p.id, "name": $p.name,
            "role": $p.career-project-role };''')
    section["active_projects"] = projects
    return section


def build_agenda():
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            return {
                "success": True,
                "generated_at": now_utc().isoformat(),
                "ops": collect_ops(tx),
                "advisor": collect_advisor(tx),
                "scribe": collect_scribe(tx),
                "analyst": collect_analyst(tx),
                "career": collect_career(tx),
            }


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_daily_agenda(args):
    print(json.dumps(build_agenda(), indent=2, default=str))


def cmd_weekly_review(args):
    """Same collectors, wider lens: everything in flight is week-review input.
    The agent turns this JSON into the narrative weekly review."""
    agenda = build_agenda()
    agenda["mode"] = "weekly-review"
    print(json.dumps(agenda, indent=2, default=str))


def _md_section(title, lines):
    out = [f"## {title}", ""]
    if lines:
        out.extend(lines)
    else:
        out.append("_Nothing pending._")
    out.append("")
    return out


def cmd_report_agenda(args):
    a = build_agenda()
    md = [f"# Daily Agenda — {a['generated_at'][:10]}", ""]

    ops = a["ops"]
    if ops["available"]:
        okr_lines = [
            f"- 🎯 **{o.get('name', o.get('id'))}** — {o.get('status')}"
            + (f" ({o.get('period')})" if o.get("period") else "")
            for o in ops.get("objectives", [])
        ] + [
            f"- ⚠️ Overdue {w.get('kind', 'item')}: **{w.get('name', w.get('id'))}**"
            + (f" — was due {str(w.get('due'))[:10]}" if w.get("due") else "")
            for w in ops.get("overdue_items", [])
        ]
        if okr_lines:
            md += _md_section("Objectives (OKRs)", okr_lines)

        lines = [
            f"- ⏰ **{c.get('name', c.get('id'))}** — {c.get('status')}, owed by {c.get('owed_by', '?')}"
            + (f", due {str(c.get('due'))[:10]}" if c.get("due") else "")
            for c in ops["open_commitments"]
        ] + [
            f"- 📋 Prep: **{p.get('title', p.get('id'))}** on {str(p.get('date'))[:10]}"
            for p in ops["upcoming_preps"]
        ]
        md += _md_section("Operations — commitments & preps", lines)
    else:
        md += _md_section("Operations", ["_ops skill not installed._"])

    adv = a["advisor"]
    if adv["available"]:
        lines = [
            f"- ⚖️ **{d.get('name', d.get('id'))}** ({d.get('stakes', '?')} stakes) — {d.get('status')}"
            for d in adv["in_flight"]
        ] + [
            f"- 🔁 Review due: **{d.get('name', d.get('id'))}** (since {str(d.get('review_date'))[:10]})"
            for d in adv["reviews_due"]
        ]
        md += _md_section("Decisions — in flight & reviews due", lines)
    else:
        md += _md_section("Decisions", ["_advisor skill not installed._"])

    scr = a["scribe"]
    if scr["available"]:
        lines = [
            f"- ✍️ **{p.get('name', p.get('id'))}** — {p.get('status')}"
            for p in scr["awaiting_review"]
        ]
        md += _md_section("Communications — awaiting review", lines)
    else:
        md += _md_section("Communications", ["_scribe skill not installed._"])

    ana = a["analyst"]
    if ana["available"]:
        lines = [
            f"- 🔬 **{m.get('name', m.get('id'))}** — {m.get('status')}"
            + (f" (for: {m.get('decision_context')})" if m.get("decision_context") else "")
            for m in ana["pending_gate"] + ana["running"]
        ]
        md += _md_section("Research — missions", lines)
    else:
        md += _md_section("Research", ["_analyst skill not installed._"])

    car = a["career"]
    if car["available"]:
        lines = [
            f"- 🎯 **{o.get('name', o.get('id'))}** — deadline {str(o.get('deadline'))[:10]} ({o.get('status', '?')})"
            for o in car["deadlines"]
        ] + [
            f"- 🛠 Project: **{p.get('name', p.get('id'))}** ({p.get('role', '?')})"
            for p in car["active_projects"]
        ]
        md += _md_section("Career — deadlines & projects", lines)
    else:
        md += _md_section("Career", ["_career skill not installed._"])

    print("\n".join(md))


def cmd_report_week(args):
    a = build_agenda()
    md = [
        f"# Week in Review — {a['generated_at'][:10]}",
        "",
        "Cross-skill snapshot for the agent to narrate. Sections mirror the",
        "daily agenda; the agent should compare against last week's journal",
        "notes and write the narrative review.",
        "",
        "```json",
        json.dumps(
            {k: v for k, v in a.items() if k not in ("success",)},
            indent=2,
            default=str,
        ),
        "```",
    ]
    print("\n".join(md))


def main():
    parser = argparse.ArgumentParser(
        description="Chief of Staff CLI - read-only cross-view over the executive AI team"
    )
    sub = parser.add_subparsers(dest="command", required=True, help="Command to run")

    sub.add_parser("daily-agenda", help="JSON cross-skill agenda")
    sub.add_parser("weekly-review", help="JSON cross-skill weekly rollup")
    sub.add_parser("report-agenda", help="Markdown daily agenda")
    sub.add_parser("report-week", help="Markdown weekly review scaffold")

    args = parser.parse_args()

    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        sys.exit(1)

    commands = {
        "daily-agenda": cmd_daily_agenda,
        "weekly-review": cmd_weekly_review,
        "report-agenda": cmd_report_agenda,
        "report-week": cmd_report_week,
    }
    try:
        commands[args.command](args)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
