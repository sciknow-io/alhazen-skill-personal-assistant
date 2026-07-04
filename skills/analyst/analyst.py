#!/usr/bin/env python3
"""
Analyst CLI - The AI research analyst: decision-framed research missions,
multi-thread "wisdom of the crowd" runs, consensus aggregation, independent
verification, the three-question gate, and deliverables beyond walls of text.

This script handles STORAGE and QUERIES. Claude handles SENSEMAKING via SKILL.md.

Usage:
    uv run python skills/analyst/analyst.py <command> [options]

Commands:
    # Mission lifecycle
    create-mission      Create a research mission (stores --primer as a primer note)
    add-interview       Record the operator interview as an interview note
    add-plan            Record the approved research plan as a plan note
    update-mission      Update mission status / priority / framing attributes
    list-missions       List missions (optionally by status)
    show-mission        Full mission detail: runs, findings, notes, gate, deliverables

    # Parallel research runs
    add-run             Register a research thread (one model/session)
    complete-run        Mark a run completed or failed

    # Findings & evidence
    add-finding         Record one discrete claim from a run
    link-source         Attach an evidence source to a finding
    list-findings       List findings (--divergent, --unverified, --mission filters)

    # Consensus, verification, gate
    record-consensus    Store agent-supplied claim groupings (consensus-count/divergent)
    verify-finding      Record fresh-thread verification of a finding
    record-gate         Store the three-question gate answers + pass/fail

    # Output
    add-deliverable     Attach a deliverable to a mission
    report-mission      Markdown report of a mission

    # Quality
    audit               Run quality-checks.yaml rules against the database

Examples:
    uv run python skills/analyst/analyst.py create-mission \
        --name "EU battery market entry" \
        --decision-context "Whether to open an EU manufacturing line in 2027" \
        --time-horizon "2026-2029" \
        --primer "Messy brain dump from the operator..."

    uv run python skills/analyst/analyst.py add-run --mission mission-abc123 \
        --model "claude-opus"

    uv run python skills/analyst/analyst.py add-finding --run run-def456 \
        --claim "EU battery demand grows ~30% CAGR through 2028" --confidence high

    uv run python skills/analyst/analyst.py record-consensus \
        --findings finding-a1 finding-b2 finding-c3 --agree 3

Environment:
    TYPEDB_HOST       TypeDB server host (default: localhost)
    TYPEDB_PORT       TypeDB server port (default: 1729)
    TYPEDB_DATABASE   Database name (default: alh_personal)
"""

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB

    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print(
        "Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=3.8.0'",
        file=sys.stderr,
    )

# Configuration
TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alh_personal")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")

MISSION_STATUSES = [
    "briefing",
    "planning",
    "running",
    "aggregating",
    "verifying",
    "gated",
    "delivered",
]

VERIFICATION_STATUSES = ["unverified", "confirmed", "refuted", "needs-work"]

DELIVERABLE_FORMATS = ["brief", "dashboard", "infographic", "interactive-page", "audio-summary"]


def get_driver():
    """Get TypeDB driver connection."""
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


def generate_id(prefix: str) -> str:
    """Generate a unique ID with prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def escape_string(s: str) -> str:
    """Escape special characters for TypeQL."""
    if s is None:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


def get_timestamp() -> str:
    """Get current timestamp for TypeDB."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def resolve_content(args):
    """Resolve content from --content or --content-file. Mutually exclusive."""
    if getattr(args, "content_file", None):
        with open(args.content_file, "r") as f:
            return f.read()
    return getattr(args, "content", None)


def parse_date(date_str: str) -> str:
    """Parse various date formats to TypeDB datetime."""
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    # If no format works, assume it's already in correct format
    return date_str


# =============================================================================
# SHARED HELPERS
# =============================================================================


def _entity_exists(tx, type_name: str, entity_id: str) -> bool:
    """Check whether an entity of the given type and id exists."""
    r = list(
        tx.query(
            f'match $e isa {type_name}, has id "{escape_string(entity_id)}"; '
            f'fetch {{ "id": $e.id }};'
        ).resolve()
    )
    return bool(r)


def _insert_note(driver, note_type: str, about_id: str, content: str,
                 name: str = None, extra_attrs: str = "", id_prefix: str = "note"):
    """Insert a note of the given type and link it to a subject via alh-aboutness."""
    note_id = generate_id(id_prefix)
    timestamp = get_timestamp()

    query = f'''insert $n isa {note_type},
        has id "{note_id}",
        has content "{escape_string(content)}",
        has created-at {timestamp}'''
    if name:
        query += f', has name "{escape_string(name)}"'
    if extra_attrs:
        query += extra_attrs
    query += ";"

    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(query).resolve()
        tx.commit()

    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(f'''match
            $n isa {note_type}, has id "{note_id}";
            $s isa alh-identifiable-entity, has id "{escape_string(about_id)}";
        insert (note: $n, subject: $s) isa alh-aboutness;''').resolve()
        tx.commit()

    return note_id


def _replace_attr(driver, type_name: str, entity_id: str, attr: str, value_clause: str):
    """Delete any existing values of attr on entity, then insert value_clause.

    value_clause is the TypeQL literal (already quoted/escaped for strings).
    """
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        try:
            tx.query(
                f'match $e isa {type_name}, has id "{escape_string(entity_id)}", '
                f'has {attr} $old; delete has $old of $e;'
            ).resolve()
        except Exception:
            pass
        tx.query(
            f'match $e isa {type_name}, has id "{escape_string(entity_id)}"; '
            f'insert $e has {attr} {value_clause};'
        ).resolve()
        tx.commit()


def _mission_notes(tx, mission_id: str) -> dict:
    """All notes attached to a mission, grouped by type."""
    notes = {}
    note_types = [
        ("anlst-primer-note", "primer"),
        ("anlst-interview-note", "interview"),
        ("anlst-plan-note", "plan"),
        ("anlst-synthesis-note", "synthesis"),
        ("anlst-gate-note", "gate"),
    ]
    for ntype, label in note_types:
        try:
            results = list(tx.query(f'''match
                $m isa anlst-mission, has id "{escape_string(mission_id)}";
                (note: $n, subject: $m) isa alh-aboutness;
                $n isa {ntype}, has id $nid, has content $c, has created-at $t;
            fetch {{ "id": $nid, "content": $c, "created_at": $t }};''').resolve())
            if results:
                notes[label] = results
        except Exception:
            pass
    return notes


def _mission_gate(tx, mission_id: str):
    """Latest gate note (three answers + pass/fail) for a mission, or None."""
    try:
        results = list(tx.query(f'''match
            $m isa anlst-mission, has id "{escape_string(mission_id)}";
            (note: $n, subject: $m) isa alh-aboutness;
            $n isa anlst-gate-note;
        fetch {{
            "id": $n.id,
            "grounded": $n.anlst-gate-grounded,
            "missing": $n.anlst-gate-missing,
            "name_on_it": $n.anlst-gate-name-on-it,
            "passed": $n.anlst-gate-passed,
            "content": $n.content,
            "created_at": $n.created-at
        }};''').resolve())
    except Exception:
        return None
    if not results:
        return None
    results.sort(key=lambda r: str(r.get("created_at") or ""))
    return results[-1]


def _mission_runs(tx, mission_id: str) -> list:
    """All runs of a mission."""
    return list(tx.query(f'''match
        $m isa anlst-mission, has id "{escape_string(mission_id)}";
        (mission: $m, run: $r) isa anlst-mission-run;
    fetch {{
        "id": $r.id,
        "model": $r.anlst-model-name,
        "status": $r.anlst-run-status,
        "started_at": $r.anlst-started-at,
        "completed_at": $r.anlst-completed-at
    }};''').resolve())


def _mission_findings(tx, mission_id: str) -> list:
    """All findings across a mission's runs, each with the run ids that yielded it."""
    rows = list(tx.query(f'''match
        $m isa anlst-mission, has id "{escape_string(mission_id)}";
        (mission: $m, run: $r) isa anlst-mission-run;
        (run: $r, finding: $f) isa anlst-run-yielded;
        $r has id $rid;
    fetch {{
        "run_id": $rid,
        "id": $f.id,
        "claim": $f.anlst-claim,
        "confidence": $f.anlst-confidence-level,
        "consensus_count": $f.anlst-consensus-count,
        "divergent": $f.anlst-divergent,
        "verification_status": $f.anlst-verification-status,
        "content": $f.content,
        "created_at": $f.created-at
    }};''').resolve())

    findings = {}
    for row in rows:
        fid = row["id"]
        if fid not in findings:
            f = dict(row)
            run_id = f.pop("run_id")
            f["run_ids"] = [run_id]
            findings[fid] = f
        else:
            if row["run_id"] not in findings[fid]["run_ids"]:
                findings[fid]["run_ids"].append(row["run_id"])
    return list(findings.values())


def _finding_sources(tx, finding_id: str) -> list:
    """Sources evidencing a finding."""
    return list(tx.query(f'''match
        $f isa anlst-finding, has id "{escape_string(finding_id)}";
        (finding: $f, source: $s) isa anlst-finding-source;
    fetch {{
        "id": $s.id,
        "name": $s.name,
        "url": $s.anlst-source-url,
        "kind": $s.anlst-source-kind,
        "reliability": $s.anlst-reliability
    }};''').resolve())


def _mission_deliverables(tx, mission_id: str) -> list:
    """Deliverables produced by a mission."""
    return list(tx.query(f'''match
        $m isa anlst-mission, has id "{escape_string(mission_id)}";
        (mission: $m, deliverable: $d) isa anlst-mission-deliverable;
    fetch {{
        "id": $d.id,
        "name": $d.name,
        "format": $d.anlst-deliverable-format,
        "created_at": $d.created-at
    }};''').resolve())


# =============================================================================
# COMMAND IMPLEMENTATIONS - Mission lifecycle
# =============================================================================


def cmd_create_mission(args):
    """Create a research mission; store the primer brain dump as a primer note."""
    mission_id = args.id or generate_id("mission")
    timestamp = get_timestamp()

    query = f'''insert $m isa anlst-mission,
        has id "{mission_id}",
        has name "{escape_string(args.name)}",
        has anlst-mission-status "briefing",
        has created-at {timestamp}'''

    if args.decision_context:
        query += f', has anlst-decision-context "{escape_string(args.decision_context)}"'
    if args.time_horizon:
        query += f', has anlst-time-horizon "{escape_string(args.time_horizon)}"'
    if args.source_policy:
        query += f', has anlst-source-policy "{escape_string(args.source_policy)}"'
    if args.exclusions:
        query += f', has anlst-exclusions "{escape_string(args.exclusions)}"'
    if args.priority:
        query += f', has anlst-priority-level "{args.priority}"'
    if args.deadline:
        query += f", has anlst-deadline {parse_date(args.deadline)}"
    if args.decision_ref:
        query += f', has anlst-decision-ref "{escape_string(args.decision_ref)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        primer_note_id = None
        if args.primer:
            primer_note_id = _insert_note(
                driver, "anlst-primer-note", mission_id, args.primer,
                name="primer", id_prefix="primer",
            )

    output = {
        "success": True,
        "mission_id": mission_id,
        "name": args.name,
        "status": "briefing",
    }
    if primer_note_id:
        output["primer_note_id"] = primer_note_id
    if not args.decision_context:
        output["warning"] = (
            "No --decision-context provided. Research must serve a decision - "
            "add one with update-mission before planning."
        )
    print(json.dumps(output, indent=2))


def cmd_add_interview(args):
    """Record the operator interview as an interview note on the mission."""
    content = resolve_content(args)
    if not content:
        print(json.dumps({"success": False, "error": "Provide either --content or --content-file"}))
        return

    with get_driver() as driver:
        note_id = _insert_note(
            driver, "anlst-interview-note", args.mission, content,
            name="operator interview", id_prefix="interview",
        )

    print(json.dumps({"success": True, "note_id": note_id, "mission_id": args.mission}))


def cmd_add_plan(args):
    """Record the approved research plan as a plan note on the mission."""
    content = resolve_content(args)
    if not content:
        print(json.dumps({"success": False, "error": "Provide either --content or --content-file"}))
        return

    with get_driver() as driver:
        note_id = _insert_note(
            driver, "anlst-plan-note", args.mission, content,
            name="research plan", id_prefix="plan",
        )

    print(json.dumps({"success": True, "note_id": note_id, "mission_id": args.mission}))


def cmd_update_mission(args):
    """Update mission status / priority / framing attributes."""
    string_updates = []
    if args.status:
        string_updates.append(("anlst-mission-status", args.status))
    if args.priority:
        string_updates.append(("anlst-priority-level", args.priority))
    if args.decision_context:
        string_updates.append(("anlst-decision-context", args.decision_context))
    if args.time_horizon:
        string_updates.append(("anlst-time-horizon", args.time_horizon))
    if args.source_policy:
        string_updates.append(("anlst-source-policy", args.source_policy))
    if args.exclusions:
        string_updates.append(("anlst-exclusions", args.exclusions))
    if args.decision_ref:
        string_updates.append(("anlst-decision-ref", args.decision_ref))

    if not string_updates and not args.deadline:
        print(json.dumps({"success": False, "error": "No updates specified"}))
        return

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not _entity_exists(tx, "anlst-mission", args.id):
                print(json.dumps({"success": False, "error": f"Mission {args.id} not found"}))
                return

        for attr, value in string_updates:
            _replace_attr(driver, "anlst-mission", args.id, attr, f'"{escape_string(value)}"')
        if args.deadline:
            _replace_attr(driver, "anlst-mission", args.id, "anlst-deadline", parse_date(args.deadline))

    updates = dict(string_updates)
    if args.deadline:
        updates["anlst-deadline"] = args.deadline
    print(json.dumps({"success": True, "mission_id": args.id, "updates": updates}))


def cmd_list_missions(args):
    """List missions, optionally filtered by status, with run/finding/deliverable rollups."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            missions = list(tx.query('''match
                $m isa anlst-mission;
            fetch {
                "id": $m.id,
                "name": $m.name,
                "status": $m.anlst-mission-status,
                "decision_context": $m.anlst-decision-context,
                "time_horizon": $m.anlst-time-horizon,
                "priority": $m.anlst-priority-level,
                "deadline": $m.anlst-deadline,
                "decision_ref": $m.anlst-decision-ref,
                "created_at": $m.created-at
            };''').resolve())

            if args.status:
                missions = [m for m in missions if m.get("status") == args.status]

            for m in missions:
                runs = _mission_runs(tx, m["id"])
                findings = _mission_findings(tx, m["id"])
                deliverables = _mission_deliverables(tx, m["id"])
                gate = _mission_gate(tx, m["id"])
                m["run_count"] = len(runs)
                m["finding_count"] = len(findings)
                m["divergent_count"] = sum(1 for f in findings if f.get("divergent") is True)
                m["unverified_count"] = sum(
                    1 for f in findings if f.get("verification_status") == "unverified"
                )
                m["deliverables"] = deliverables
                m["gate"] = (
                    {"passed": gate.get("passed"), "recorded_at": str(gate.get("created_at"))}
                    if gate else None
                )

    print(json.dumps({"success": True, "missions": missions, "count": len(missions)}, default=str))


def cmd_show_mission(args):
    """Full mission detail: attributes, notes, runs, findings, gate, deliverables."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''match
                $m isa anlst-mission, has id "{escape_string(args.id)}";
            fetch {{
                "id": $m.id,
                "name": $m.name,
                "description": $m.description,
                "status": $m.anlst-mission-status,
                "decision_context": $m.anlst-decision-context,
                "time_horizon": $m.anlst-time-horizon,
                "source_policy": $m.anlst-source-policy,
                "exclusions": $m.anlst-exclusions,
                "priority": $m.anlst-priority-level,
                "deadline": $m.anlst-deadline,
                "decision_ref": $m.anlst-decision-ref,
                "created_at": $m.created-at
            }};''').resolve())

            if not results:
                print(json.dumps({"success": False, "error": f"Mission {args.id} not found"}))
                return

            mission = results[0]
            runs = _mission_runs(tx, args.id)
            findings = _mission_findings(tx, args.id)
            for f in findings:
                f["sources"] = _finding_sources(tx, f["id"])
                # Verification notes about this finding
                try:
                    f["verification_notes"] = list(tx.query(f'''match
                        $f isa anlst-finding, has id "{f['id']}";
                        (note: $n, subject: $f) isa alh-aboutness;
                        $n isa anlst-verification-note, has content $c;
                    fetch {{ "content": $c }};''').resolve())
                except Exception:
                    f["verification_notes"] = []

    print(json.dumps({
        "success": True,
        "mission": mission,
        "notes": _notes_for_output(mission["id"]),
        "runs": runs,
        "findings": findings,
        "gate": _gate_for_output(mission["id"]),
        "deliverables": _deliverables_for_output(mission["id"]),
    }, default=str))


def _notes_for_output(mission_id):
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            return _mission_notes(tx, mission_id)


def _gate_for_output(mission_id):
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            return _mission_gate(tx, mission_id)


def _deliverables_for_output(mission_id):
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            return _mission_deliverables(tx, mission_id)


# =============================================================================
# COMMAND IMPLEMENTATIONS - Runs
# =============================================================================


def cmd_add_run(args):
    """Register a research thread (one model/session) on a mission."""
    run_id = args.id or generate_id("run")
    timestamp = get_timestamp()

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not _entity_exists(tx, "anlst-mission", args.mission):
                print(json.dumps({"success": False, "error": f"Mission {args.mission} not found"}))
                return

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            query = f'''insert $r isa anlst-run,
                has id "{run_id}",
                has name "run: {escape_string(args.model)}",
                has anlst-model-name "{escape_string(args.model)}",
                has anlst-run-status "running",
                has anlst-started-at {timestamp},
                has created-at {timestamp};'''
            tx.query(query).resolve()
            tx.commit()

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $m isa anlst-mission, has id "{escape_string(args.mission)}";
                $r isa anlst-run, has id "{run_id}";
            insert (mission: $m, run: $r) isa anlst-mission-run;''').resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "run_id": run_id,
        "mission_id": args.mission,
        "model": args.model,
        "status": "running",
    }))


def cmd_complete_run(args):
    """Mark a run completed or failed."""
    timestamp = get_timestamp()

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not _entity_exists(tx, "anlst-run", args.run):
                print(json.dumps({"success": False, "error": f"Run {args.run} not found"}))
                return

        _replace_attr(driver, "anlst-run", args.run, "anlst-run-status", f'"{args.status}"')
        _replace_attr(driver, "anlst-run", args.run, "anlst-completed-at", timestamp)

    print(json.dumps({"success": True, "run_id": args.run, "status": args.status}))


# =============================================================================
# COMMAND IMPLEMENTATIONS - Findings & evidence
# =============================================================================


def cmd_add_finding(args):
    """Record one discrete claim from a run."""
    finding_id = args.id or generate_id("finding")
    timestamp = get_timestamp()

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not _entity_exists(tx, "anlst-run", args.run):
                print(json.dumps({"success": False, "error": f"Run {args.run} not found"}))
                return

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            query = f'''insert $f isa anlst-finding,
                has id "{finding_id}",
                has anlst-claim "{escape_string(args.claim)}",
                has anlst-verification-status "unverified",
                has created-at {timestamp}'''
            if args.confidence:
                query += f', has anlst-confidence-level "{args.confidence}"'
            if args.content:
                query += f', has content "{escape_string(args.content)}"'
            query += ";"
            tx.query(query).resolve()
            tx.commit()

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $r isa anlst-run, has id "{escape_string(args.run)}";
                $f isa anlst-finding, has id "{finding_id}";
            insert (run: $r, finding: $f) isa anlst-run-yielded;''').resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "finding_id": finding_id,
        "run_id": args.run,
        "claim": args.claim,
        "verification_status": "unverified",
    }))


def cmd_link_source(args):
    """Attach an evidence source to a finding (create the source or link an existing one)."""
    timestamp = get_timestamp()

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not _entity_exists(tx, "anlst-finding", args.finding):
                print(json.dumps({"success": False, "error": f"Finding {args.finding} not found"}))
                return

        if args.source:
            source_id = args.source
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                if not _entity_exists(tx, "anlst-source", source_id):
                    print(json.dumps({"success": False, "error": f"Source {source_id} not found"}))
                    return
            created = False
        else:
            if not args.url and not args.name:
                print(json.dumps({
                    "success": False,
                    "error": "Provide --source (existing id) or --url/--name to create a source",
                }))
                return
            source_id = generate_id("source")
            source_name = args.name or args.url
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                query = f'''insert $s isa anlst-source,
                    has id "{source_id}",
                    has name "{escape_string(source_name)}",
                    has created-at {timestamp}'''
                if args.url:
                    query += f', has anlst-source-url "{escape_string(args.url)}"'
                if args.kind:
                    query += f', has anlst-source-kind "{args.kind}"'
                if args.reliability:
                    query += f', has anlst-reliability "{args.reliability}"'
                query += ";"
                tx.query(query).resolve()
                tx.commit()
            created = True

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $f isa anlst-finding, has id "{escape_string(args.finding)}";
                $s isa anlst-source, has id "{escape_string(source_id)}";
            insert (finding: $f, source: $s) isa anlst-finding-source;''').resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "finding_id": args.finding,
        "source_id": source_id,
        "created": created,
    }))


def cmd_list_findings(args):
    """List findings with mission/run context; filter by --mission, --divergent, --unverified."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            rows = list(tx.query('''match
                $f isa anlst-finding;
                (run: $r, finding: $f) isa anlst-run-yielded;
                (mission: $m, run: $r) isa anlst-mission-run;
                $r has id $rid;
                $m has id $mid;
                $m has name $mname;
            fetch {
                "run_id": $rid,
                "mission_id": $mid,
                "mission_name": $mname,
                "id": $f.id,
                "claim": $f.anlst-claim,
                "confidence": $f.anlst-confidence-level,
                "consensus_count": $f.anlst-consensus-count,
                "divergent": $f.anlst-divergent,
                "verification_status": $f.anlst-verification-status,
                "created_at": $f.created-at
            };''').resolve())

    findings = {}
    for row in rows:
        fid = row["id"]
        if fid not in findings:
            f = dict(row)
            run_id = f.pop("run_id")
            f["run_ids"] = [run_id]
            findings[fid] = f
        elif row["run_id"] not in findings[fid]["run_ids"]:
            findings[fid]["run_ids"].append(row["run_id"])

    result = list(findings.values())
    if args.mission:
        result = [f for f in result if f.get("mission_id") == args.mission]
    if args.divergent:
        result = [f for f in result if f.get("divergent") is True]
    if args.unverified:
        result = [f for f in result if f.get("verification_status") == "unverified"]

    print(json.dumps({"success": True, "findings": result, "count": len(result)}, default=str))


# =============================================================================
# COMMAND IMPLEMENTATIONS - Consensus, verification, gate
# =============================================================================


def cmd_record_consensus(args):
    """Store an agent-supplied claim grouping: consensus-count + divergent flag.

    The agent matches claims across runs (semantic matching is sensemaking, not
    scripting) and calls this once per claim group. --agree is the number of
    runs asserting the claim (defaults to the number of findings in the group).
    A claim asserted by a single run is marked divergent unless overridden.
    """
    agree = args.agree if args.agree is not None else len(args.findings)
    if args.divergent:
        divergent = True
    elif args.not_divergent:
        divergent = False
    else:
        divergent = agree <= 1

    updated = []
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            for fid in args.findings:
                if not _entity_exists(tx, "anlst-finding", fid):
                    print(json.dumps({"success": False, "error": f"Finding {fid} not found"}))
                    return

        for fid in args.findings:
            _replace_attr(driver, "anlst-finding", fid, "anlst-consensus-count", str(agree))
            _replace_attr(driver, "anlst-finding", fid, "anlst-divergent",
                          "true" if divergent else "false")
            updated.append(fid)

    output = {
        "success": True,
        "findings": updated,
        "consensus_count": agree,
        "divergent": divergent,
    }
    if divergent:
        output["note"] = (
            "Single-thread/contested claim - investigate or re-research before trusting it."
        )
    print(json.dumps(output))


def cmd_verify_finding(args):
    """Record fresh-thread verification of a finding (status + optional note)."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not _entity_exists(tx, "anlst-finding", args.finding):
                print(json.dumps({"success": False, "error": f"Finding {args.finding} not found"}))
                return

        _replace_attr(driver, "anlst-finding", args.finding,
                      "anlst-verification-status", f'"{args.status}"')

        note_id = None
        content = resolve_content(args)
        if content:
            note_id = _insert_note(
                driver, "anlst-verification-note", args.finding, content,
                name=f"verification: {args.status}", id_prefix="verification",
            )

    output = {"success": True, "finding_id": args.finding, "verification_status": args.status}
    if note_id:
        output["note_id"] = note_id
    print(json.dumps(output))


def cmd_record_gate(args):
    """Store the three-question gate: three answers + pass/fail, as a gate note."""
    passed = bool(args.passed)
    content = resolve_content(args) or (
        f"Q1 Grounded in real sources or pattern-matching? {args.grounded}\n"
        f"Q2 What's missing that I didn't think to ask? {args.missing}\n"
        f"Q3 Would I put my name on this? {args.name_on_it}\n"
        f"Gate: {'PASSED' if passed else 'FAILED'}"
    )

    extra = (
        f', has anlst-gate-grounded "{escape_string(args.grounded)}"'
        f', has anlst-gate-missing "{escape_string(args.missing)}"'
        f', has anlst-gate-name-on-it "{escape_string(args.name_on_it)}"'
        f", has anlst-gate-passed {'true' if passed else 'false'}"
    )

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not _entity_exists(tx, "anlst-mission", args.mission):
                print(json.dumps({"success": False, "error": f"Mission {args.mission} not found"}))
                return

        note_id = _insert_note(
            driver, "anlst-gate-note", args.mission, content,
            name="three-question gate", extra_attrs=extra, id_prefix="gate",
        )

        if passed:
            _replace_attr(driver, "anlst-mission", args.mission,
                          "anlst-mission-status", '"gated"')

    print(json.dumps({
        "success": True,
        "note_id": note_id,
        "mission_id": args.mission,
        "passed": passed,
        "mission_status": "gated" if passed else "unchanged (gate failed - go back and fix)",
    }))


# =============================================================================
# COMMAND IMPLEMENTATIONS - Deliverables & reports
# =============================================================================


def cmd_add_deliverable(args):
    """Attach a deliverable artifact to a mission."""
    deliverable_id = args.id or generate_id("deliverable")
    timestamp = get_timestamp()
    content = resolve_content(args)

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not _entity_exists(tx, "anlst-mission", args.mission):
                print(json.dumps({"success": False, "error": f"Mission {args.mission} not found"}))
                return

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            query = f'''insert $d isa anlst-deliverable,
                has id "{deliverable_id}",
                has name "{escape_string(args.name)}",
                has anlst-deliverable-format "{args.format}",
                has created-at {timestamp}'''
            if content:
                query += f', has content "{escape_string(content)}"'
            if args.uri:
                query += f', has source-uri "{escape_string(args.uri)}"'
            query += ";"
            tx.query(query).resolve()
            tx.commit()

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $m isa anlst-mission, has id "{escape_string(args.mission)}";
                $d isa anlst-deliverable, has id "{deliverable_id}";
            insert (mission: $m, deliverable: $d) isa anlst-mission-deliverable;''').resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "deliverable_id": deliverable_id,
        "mission_id": args.mission,
        "format": args.format,
        "message": "Deliverable attached. Set mission status with update-mission --status delivered.",
    }))


def cmd_report_mission(args):
    """Markdown report of a mission for human display."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''match
                $m isa anlst-mission, has id "{escape_string(args.id)}";
            fetch {{
                "id": $m.id,
                "name": $m.name,
                "status": $m.anlst-mission-status,
                "decision_context": $m.anlst-decision-context,
                "time_horizon": $m.anlst-time-horizon,
                "source_policy": $m.anlst-source-policy,
                "exclusions": $m.anlst-exclusions,
                "priority": $m.anlst-priority-level,
                "deadline": $m.anlst-deadline
            }};''').resolve())

            if not results:
                print(f"Mission {args.id} not found")
                return

            mission = results[0]
            runs = _mission_runs(tx, args.id)
            findings = _mission_findings(tx, args.id)
            for f in findings:
                f["sources"] = _finding_sources(tx, f["id"])
            gate = _mission_gate(tx, args.id)
            deliverables = _mission_deliverables(tx, args.id)
            notes = _mission_notes(tx, args.id)

    lines = []
    lines.append(f"# Research Mission: {mission.get('name')}")
    lines.append("")
    lines.append(f"**Status:** {mission.get('status')}  |  **Priority:** {mission.get('priority') or '-'}")
    if mission.get("decision_context"):
        lines.append(f"**Decision this serves:** {mission['decision_context']}")
    if mission.get("time_horizon"):
        lines.append(f"**Time horizon:** {mission['time_horizon']}")
    if mission.get("source_policy"):
        lines.append(f"**Source policy:** {mission['source_policy']}")
    if mission.get("exclusions"):
        lines.append(f"**Exclusions:** {mission['exclusions']}")
    if mission.get("deadline"):
        lines.append(f"**Deadline:** {mission['deadline']}")
    lines.append("")

    lines.append(f"## Runs ({len(runs)})")
    lines.append("")
    if runs:
        lines.append("| Run | Model | Status | Started | Completed |")
        lines.append("|-----|-------|--------|---------|-----------|")
        for r in runs:
            lines.append(
                f"| {r.get('id')} | {r.get('model') or '-'} | {r.get('status') or '-'} "
                f"| {r.get('started_at') or '-'} | {r.get('completed_at') or '-'} |"
            )
    else:
        lines.append("_No runs yet. Fan out 3+ parallel runs with the same prompt._")
    lines.append("")

    lines.append(f"## Findings ({len(findings)})")
    lines.append("")
    if findings:
        lines.append("| Claim | Consensus | Divergent | Verification | Confidence | Sources |")
        lines.append("|-------|-----------|-----------|--------------|------------|---------|")
        for f in sorted(findings, key=lambda x: -(x.get("consensus_count") or 0)):
            divergent = "yes" if f.get("divergent") is True else "no"
            n_runs = len(f.get("run_ids", []))
            consensus = f.get("consensus_count")
            consensus_str = f"{consensus}" if consensus is not None else f"({n_runs} run{'s' if n_runs != 1 else ''})"
            claim = (f.get("claim") or "")[:90]
            lines.append(
                f"| {claim} | {consensus_str} | {divergent} "
                f"| {f.get('verification_status') or 'unverified'} "
                f"| {f.get('confidence') or '-'} | {len(f.get('sources', []))} |"
            )
    else:
        lines.append("_No findings recorded yet._")
    lines.append("")

    lines.append("## Three-Question Gate")
    lines.append("")
    if gate:
        lines.append(f"**Result: {'PASSED' if gate.get('passed') else 'FAILED'}**")
        lines.append("")
        lines.append(f"1. **Grounded in real sources or pattern-matching?** {gate.get('grounded') or '-'}")
        lines.append(f"2. **What's missing that I didn't think to ask?** {gate.get('missing') or '-'}")
        lines.append(f"3. **Would I put my name on this?** {gate.get('name_on_it') or '-'}")
    else:
        lines.append("_Gate not recorded yet. Do not deliver ungated research._")
    lines.append("")

    lines.append(f"## Deliverables ({len(deliverables)})")
    lines.append("")
    for d in deliverables:
        lines.append(f"- **{d.get('name')}** ({d.get('format') or 'brief'})")
    if not deliverables:
        lines.append("_None yet. Consider dashboard / infographic / audio-summary, not just text._")
    lines.append("")

    if notes:
        lines.append("## Notes")
        lines.append("")
        for label, items in notes.items():
            lines.append(f"### {label.title()} ({len(items)})")
            for n in items:
                content = (n.get("content") or "").replace("\\n", "\n")
                lines.append("")
                lines.append(content)
            lines.append("")

    print("\n".join(lines))


# =============================================================================
# COMMAND IMPLEMENTATIONS - Audit
# =============================================================================


def cmd_audit(args):
    """Run the declarative checks in quality-checks.yaml against the database."""
    try:
        import yaml
    except ImportError:
        print(json.dumps({"success": False, "error": "pyyaml not installed (uv sync)"}))
        return

    checks_path = Path(__file__).parent / "quality-checks.yaml"
    if not checks_path.exists():
        print(json.dumps({"success": False, "error": f"quality-checks.yaml not found at {checks_path}"}))
        return

    with open(checks_path) as f:
        spec = yaml.safe_load(f)

    results = []
    totals = {"high": 0, "medium": 0, "low": 0}

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            for check in spec.get("checks", []):
                entry = {
                    "name": check.get("name"),
                    "severity": check.get("severity"),
                    "description": check.get("description"),
                }
                if args.severity and check.get("severity") != args.severity:
                    continue
                try:
                    violations = list(tx.query(check["find_violations"]).resolve())
                    entry["violations"] = violations
                    entry["violation_count"] = len(violations)
                    if check.get("count_total"):
                        try:
                            total = list(tx.query(check["count_total"]).resolve())
                            entry["total"] = len(total)
                        except Exception:
                            pass
                    if violations:
                        sev = check.get("severity", "low")
                        totals[sev] = totals.get(sev, 0) + len(violations)
                except Exception as e:
                    entry["error"] = str(e)
                results.append(entry)

    print(json.dumps({
        "success": True,
        "skill": spec.get("skill", "analyst"),
        "checks": results,
        "violations_by_severity": totals,
        "clean": all(r.get("violation_count", 0) == 0 and "error" not in r for r in results),
    }, default=str))


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Analyst CLI - decision-framed research missions with multi-thread consensus"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # create-mission
    p = subparsers.add_parser("create-mission", help="Create a research mission")
    p.add_argument("--name", required=True, help="Mission name")
    p.add_argument("--decision-context", dest="decision_context",
                   help="The decision this research serves (strongly recommended)")
    p.add_argument("--primer", help="Operator's messy initial brain dump (stored as primer note)")
    p.add_argument("--time-horizon", dest="time_horizon", help="Time horizon constraint")
    p.add_argument("--source-policy", dest="source_policy",
                   help="Source priority / reliability standards")
    p.add_argument("--exclusions", help="What NOT to include")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Priority level")
    p.add_argument("--deadline", help="Deadline (YYYY-MM-DD)")
    p.add_argument("--decision-ref", dest="decision_ref",
                   help="Soft reference to an advsr-decision id (advisor skill)")
    p.add_argument("--description", help="Brief description")
    p.add_argument("--id", help="Specific mission ID")

    # add-interview
    p = subparsers.add_parser("add-interview", help="Record the operator interview")
    p.add_argument("--mission", required=True, help="Mission ID")
    p.add_argument("--content", help="Interview Q&A content (inline)")
    p.add_argument("--content-file", help="Path to file containing interview content")

    # add-plan
    p = subparsers.add_parser("add-plan", help="Record the approved research plan")
    p.add_argument("--mission", required=True, help="Mission ID")
    p.add_argument("--content", help="Plan content (inline)")
    p.add_argument("--content-file", help="Path to file containing plan content")

    # update-mission
    p = subparsers.add_parser("update-mission", help="Update mission attributes")
    p.add_argument("--id", required=True, help="Mission ID")
    p.add_argument("--status", choices=MISSION_STATUSES, help="New status")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Priority level")
    p.add_argument("--decision-context", dest="decision_context", help="Decision this serves")
    p.add_argument("--time-horizon", dest="time_horizon", help="Time horizon")
    p.add_argument("--source-policy", dest="source_policy", help="Source policy")
    p.add_argument("--exclusions", help="Exclusions")
    p.add_argument("--deadline", help="Deadline (YYYY-MM-DD)")
    p.add_argument("--decision-ref", dest="decision_ref", help="Soft advsr-decision reference")

    # list-missions
    p = subparsers.add_parser("list-missions", help="List missions")
    p.add_argument("--status", choices=MISSION_STATUSES, help="Filter by status")

    # show-mission
    p = subparsers.add_parser("show-mission", help="Full mission detail")
    p.add_argument("--id", required=True, help="Mission ID")

    # add-run
    p = subparsers.add_parser("add-run", help="Register a research thread")
    p.add_argument("--mission", required=True, help="Mission ID")
    p.add_argument("--model", required=True,
                   help="Model/session label (e.g. 'claude-opus', 'gpt-5', 'session-2')")
    p.add_argument("--id", help="Specific run ID")

    # complete-run
    p = subparsers.add_parser("complete-run", help="Mark a run completed or failed")
    p.add_argument("--run", required=True, help="Run ID")
    p.add_argument("--status", choices=["completed", "failed"], default="completed",
                   help="Final run status (default: completed)")

    # add-finding
    p = subparsers.add_parser("add-finding", help="Record one discrete claim from a run")
    p.add_argument("--run", required=True, help="Run ID that yielded this finding")
    p.add_argument("--claim", required=True, help="The discrete claim (one claim per finding)")
    p.add_argument("--confidence", choices=["high", "medium", "low"],
                   help="Run's confidence in the claim")
    p.add_argument("--content", help="Supporting detail / evidence excerpt")
    p.add_argument("--id", help="Specific finding ID")

    # link-source
    p = subparsers.add_parser("link-source", help="Attach an evidence source to a finding")
    p.add_argument("--finding", required=True, help="Finding ID")
    p.add_argument("--source", help="Existing source ID (skip creation)")
    p.add_argument("--url", help="Source URL (creates a new source)")
    p.add_argument("--name", help="Source name/title")
    p.add_argument("--kind", choices=["primary", "academic", "news", "vendor", "social", "other"],
                   help="Source kind")
    p.add_argument("--reliability", choices=["high", "medium", "low"], help="Reliability rating")

    # list-findings
    p = subparsers.add_parser("list-findings", help="List findings across missions")
    p.add_argument("--mission", help="Filter by mission ID")
    p.add_argument("--divergent", action="store_true", help="Only divergent (single-thread) claims")
    p.add_argument("--unverified", action="store_true", help="Only unverified findings")

    # record-consensus
    p = subparsers.add_parser("record-consensus",
                              help="Store an agent-supplied claim grouping across runs")
    p.add_argument("--findings", required=True, nargs="+",
                   help="Finding IDs asserting the SAME claim (one group per invocation)")
    p.add_argument("--agree", type=int,
                   help="Number of runs asserting the claim (default: number of findings given)")
    p.add_argument("--divergent", action="store_true", help="Force divergent = true")
    p.add_argument("--not-divergent", dest="not_divergent", action="store_true",
                   help="Force divergent = false")

    # verify-finding
    p = subparsers.add_parser("verify-finding", help="Record fresh-thread verification")
    p.add_argument("--finding", required=True, help="Finding ID")
    p.add_argument("--status", required=True, choices=["confirmed", "refuted", "needs-work"],
                   help="Verification outcome")
    p.add_argument("--content", help="Verification rationale (stored as verification note)")
    p.add_argument("--content-file", help="Path to file containing verification rationale")

    # record-gate
    p = subparsers.add_parser("record-gate", help="Store the three-question gate")
    p.add_argument("--mission", required=True, help="Mission ID")
    p.add_argument("--grounded", required=True,
                   help="Q1: grounded in real sources or pattern-matching?")
    p.add_argument("--missing", required=True,
                   help="Q2: what's missing that I didn't think to ask?")
    p.add_argument("--name-on-it", dest="name_on_it", required=True,
                   help="Q3: would I put my name on this?")
    gate_group = p.add_mutually_exclusive_group(required=True)
    gate_group.add_argument("--passed", action="store_true", help="Gate passed")
    gate_group.add_argument("--failed", dest="passed", action="store_false", help="Gate failed")
    p.add_argument("--content", help="Full gate discussion (optional; default composed from answers)")
    p.add_argument("--content-file", help="Path to file containing gate discussion")

    # add-deliverable
    p = subparsers.add_parser("add-deliverable", help="Attach a deliverable to a mission")
    p.add_argument("--mission", required=True, help="Mission ID")
    p.add_argument("--name", required=True, help="Deliverable name")
    p.add_argument("--format", required=True, choices=DELIVERABLE_FORMATS,
                   help="Deliverable format")
    p.add_argument("--content", help="Deliverable content (inline markdown)")
    p.add_argument("--content-file", help="Path to file containing deliverable content")
    p.add_argument("--uri", help="Where the deliverable lives (file path / URL)")
    p.add_argument("--id", help="Specific deliverable ID")

    # report-mission
    p = subparsers.add_parser("report-mission", help="Markdown report of a mission")
    p.add_argument("--id", required=True, help="Mission ID")

    # audit
    p = subparsers.add_parser("audit", help="Run quality-checks.yaml rules")
    p.add_argument("--severity", choices=["high", "medium", "low"], help="Only run this severity")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        sys.exit(1)

    commands = {
        # Mission lifecycle
        "create-mission": cmd_create_mission,
        "add-interview": cmd_add_interview,
        "add-plan": cmd_add_plan,
        "update-mission": cmd_update_mission,
        "list-missions": cmd_list_missions,
        "show-mission": cmd_show_mission,
        # Runs
        "add-run": cmd_add_run,
        "complete-run": cmd_complete_run,
        # Findings & evidence
        "add-finding": cmd_add_finding,
        "link-source": cmd_link_source,
        "list-findings": cmd_list_findings,
        # Consensus, verification, gate
        "record-consensus": cmd_record_consensus,
        "verify-finding": cmd_verify_finding,
        "record-gate": cmd_record_gate,
        # Output
        "add-deliverable": cmd_add_deliverable,
        "report-mission": cmd_report_mission,
        # Quality
        "audit": cmd_audit,
    }

    try:
        commands[args.command](args)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
