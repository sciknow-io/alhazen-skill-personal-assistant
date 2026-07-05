#!/usr/bin/env python3
"""
Ops Notebook CLI - The operational powerhouse: briefs, stakeholder CRM,
meeting prep, commitments, and monitors.

This script handles STORAGE and QUERIES. Claude handles SENSEMAKING via SKILL.md.

Usage:
    uv run python skills/ops/ops.py <command> [options]

Commands:
    # Brief specs (manual-before-automate lifecycle is ENFORCED here)
    add-spec            Design a recurring brief/report (with --primer and --dream)
    list-specs          List brief specs with trial progress
    log-brief           Log a produced brief instance (--manual increments trial runs;
                        --automated is REFUSED while spec is designed/trial)
    list-briefs         List produced brief instances (optionally per spec)
    promote-spec        Promote trial -> active (fails unless trial-runs >= trial-target)
    retire-spec         Retire a spec (briefs nobody reads should die)

    # Stakeholder CRM
    add-person          Thin helper: find-or-create an alh-person
    add-dossier         Create a stakeholder dossier for a person
    list-stakeholders   CRM table: dossiers + last touchpoint + open commitments
    show-stakeholder    The pre-meeting context pull: dossier + touchpoints + commitments
    log-touchpoint      Log an interaction WITH the undercurrent
    prep-meeting        Assemble stakeholder context JSON (agent writes the prep)
    save-prep           Store the agent-written prep pack

    # Commitments
    add-commitment      Record who owes what by when
    update-commitment   Change status/due date
    list-commitments    Filter by --due / --owed-by / --status / --person

    # Monitors
    add-monitor         Add a standing visibility question
    list-monitors       List monitors
    update-monitor      Update status / mark checked

    # Synthesis
    today               JSON morning snapshot: briefs due, commitments, preps, stale monitors
    report-today        Markdown morning brief
    add-note            Attach a primer/interview/general note to any ops entity
    audit               Run declarative quality checks from quality-checks.yaml

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
from datetime import datetime, timedelta, timezone
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

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    print(
        "Warning: pyyaml not installed. Install with: pip install pyyaml (needed for audit)",
        file=sys.stderr,
    )

# Configuration
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

SPEC_STATUSES = ["designed", "trial", "active", "retired"]
COMMITMENT_STATUSES = ["open", "done", "dropped", "overdue"]
MONITOR_STATUSES = ["active", "paused", "retired"]
OBJECTIVE_STATUSES = ["draft", "active", "at-risk", "met", "missed", "dropped"]
KR_STATUSES = ["on-track", "at-risk", "off-track", "met", "missed"]
WORKITEM_KINDS = ["story", "task", "subtask"]
WORKITEM_STATUSES = ["not-started", "in-progress", "blocked", "done", "dropped"]
DEFAULT_TRIAL_TARGET = 7
STALE_MONITOR_DAYS = 7
UPCOMING_PREP_DAYS = 7


def get_driver():
    """Get TypeDB driver connection.

    Compatible with typedb-driver 3.8-3.10 (DriverOptions(is_tls_enabled=...))
    and >= 3.11 (DriverOptions(DriverTlsConfig.disabled())).
    """
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


def generate_id(prefix: str) -> str:
    """Generate a unique ID with prefix (<type>-<hash12>)."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def escape_string(s: str) -> str:
    """Escape special characters for TypeQL."""
    if s is None:
        return ""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")


def get_timestamp() -> str:
    """Get current timestamp for TypeDB."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def parse_date(date_str: str) -> str:
    """Parse various date formats to TypeDB datetime."""
    for fmt in ["%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%Y"]:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%Y-%m-%dT%H:%M:%S")
        except ValueError:
            continue
    return date_str


def to_dt(value):
    """Coerce a fetch result value (str or datetime) into a naive datetime, or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    s = str(value).replace("Z", "").split("+")[0]
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def resolve_content(args):
    """Resolve content from --content or --content-file. Mutually exclusive."""
    if getattr(args, "content_file", None):
        with open(args.content_file, "r") as f:
            return f.read()
    return getattr(args, "content", None)


def replace_attr(tx, etype: str, eid: str, attr: str, value_literal: str):
    """Delete any existing value of attr on the entity, then insert value_literal.

    value_literal must already be TypeQL-formatted (quoted string, bare int/bool/datetime).
    """
    try:
        tx.query(
            f'match $e isa {etype}, has id "{eid}", has {attr} $old; delete has $old of $e;'
        ).resolve()
    except Exception:
        pass
    tx.query(
        f'match $e isa {etype}, has id "{eid}"; insert $e has {attr} {value_literal};'
    ).resolve()


def fetch_one(tx, query: str):
    results = list(tx.query(query).resolve())
    return results[0] if results else None


def resolve_person(tx, ident: str):
    """Resolve a person by id first, then by (case-insensitive) name.

    Returns {"id": ..., "name": ...} or None.
    """
    r = fetch_one(
        tx,
        f'match $p isa alh-person, has id "{escape_string(ident)}", has name $n;'
        f' fetch {{ "id": $p.id, "name": $n }};',
    )
    if r:
        return r
    everyone = list(
        tx.query('match $p isa alh-person, has id $id, has name $n; fetch { "id": $id, "name": $n };').resolve()
    )
    for p in everyone:
        if str(p.get("name", "")).lower() == ident.lower():
            return p
    return None


def link_note_about(driver, note_id: str, subject_id: str):
    """Link a note to a subject via alh-aboutness."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(f'''match
            $n isa alh-note, has id "{note_id}";
            $s isa alh-identifiable-entity, has id "{subject_id}";
        insert (note: $n, subject: $s) isa alh-aboutness;''').resolve()
        tx.commit()


def add_primer_note(driver, subject_id: str, primer_text: str) -> str:
    """Store the operator's messy brain dump as an ops-primer-note about the subject."""
    note_id = generate_id("primer")
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(f'''insert $n isa ops-primer-note,
            has id "{note_id}",
            has name "primer",
            has content "{escape_string(primer_text)}",
            has created-at {get_timestamp()};''').resolve()
        tx.commit()
    link_note_about(driver, note_id, subject_id)
    return note_id


def get_spec(tx, spec_id: str):
    return fetch_one(
        tx,
        f'''match $s isa ops-brief-spec, has id "{escape_string(spec_id)}";
        fetch {{
            "id": $s.id,
            "name": $s.name,
            "description": $s.description,
            "ops-cadence": $s.ops-cadence,
            "ops-sections": $s.ops-sections,
            "ops-sources": $s.ops-sources,
            "ops-spec-status": $s.ops-spec-status,
            "ops-trial-runs": $s.ops-trial-runs,
            "ops-trial-target": $s.ops-trial-target,
            "ops-dream-rationale": $s.ops-dream-rationale
        }};''',
    )


def cadence_days(cadence: str) -> int:
    """Heuristic conversion of a cadence string to a day interval."""
    c = (cadence or "daily").lower()
    if "biweek" in c or "fortnight" in c:
        return 14
    if "quarter" in c:
        return 90
    if "month" in c:
        return 30
    if "week" in c:  # weekly, weekdays -> weekdays still means a brief every day M-F
        return 1 if "weekday" in c else 7
    for token in c.split():
        if token.isdigit():
            return int(token)
    return 1  # daily and anything unrecognized


# =============================================================================
# BRIEF SPEC COMMANDS
# =============================================================================


def cmd_add_spec(args):
    """Design a recurring brief/report spec (status starts at 'designed')."""
    spec_id = generate_id("briefspec")
    timestamp = get_timestamp()
    trial_target = args.trial_target or DEFAULT_TRIAL_TARGET

    query = f'''insert $s isa ops-brief-spec,
        has id "{spec_id}",
        has name "{escape_string(args.name)}",
        has ops-spec-status "designed",
        has ops-trial-runs 0,
        has ops-trial-target {trial_target},
        has created-at {timestamp}'''
    if args.cadence:
        query += f', has ops-cadence "{escape_string(args.cadence)}"'
    if args.sections:
        query += f', has ops-sections "{escape_string(args.sections)}"'
    if args.sources:
        query += f', has ops-sources "{escape_string(args.sources)}"'
    if args.dream:
        query += f', has ops-dream-rationale "{escape_string(args.dream)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'
    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        primer_note_id = None
        if args.primer:
            primer_note_id = add_primer_note(driver, spec_id, args.primer)

    print(json.dumps({
        "success": True,
        "spec_id": spec_id,
        "name": args.name,
        "status": "designed",
        "trial_target": trial_target,
        "primer_note_id": primer_note_id,
        "message": (
            "Spec designed. Next: interview the operator (add-note --type interview), "
            f"then run it MANUALLY {trial_target} times (log-brief --manual) before promote-spec."
        ),
    }))


def cmd_list_specs(args):
    """List brief specs with trial progress and brief counts."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            specs = list(tx.query('''match $s isa ops-brief-spec, has id $id;
            fetch {
                "id": $id,
                "name": $s.name,
                "ops-cadence": $s.ops-cadence,
                "ops-sections": $s.ops-sections,
                "ops-sources": $s.ops-sources,
                "ops-spec-status": $s.ops-spec-status,
                "ops-trial-runs": $s.ops-trial-runs,
                "ops-trial-target": $s.ops-trial-target,
                "ops-dream-rationale": $s.ops-dream-rationale
            };''').resolve())

            out = []
            for s in specs:
                status = s.get("ops-spec-status")
                if args.status and status != args.status:
                    continue
                briefs = list(tx.query(f'''match
                    $s isa ops-brief-spec, has id "{s['id']}";
                    (spec: $s, brief: $b) isa ops-spec-produced;
                    $b has ops-brief-date $d;
                fetch {{ "date": $d }};''').resolve())
                dates = sorted([to_dt(b["date"]) for b in briefs if to_dt(b["date"])])
                out.append({
                    "id": s["id"],
                    "name": s.get("name"),
                    "status": status,
                    "cadence": s.get("ops-cadence"),
                    "sections": s.get("ops-sections"),
                    "sources": s.get("ops-sources"),
                    "dream_rationale": s.get("ops-dream-rationale"),
                    "trial_runs": s.get("ops-trial-runs", 0),
                    "trial_target": s.get("ops-trial-target", DEFAULT_TRIAL_TARGET),
                    "brief_count": len(briefs),
                    "last_brief_date": dates[-1].isoformat() if dates else None,
                })

    print(json.dumps({"success": True, "specs": out, "count": len(out)}, default=str))


def cmd_log_brief(args):
    """Log a produced brief instance.

    ENFORCES the manual-before-automate rule: --automated is refused while the
    spec is in 'designed' or 'trial' status. Manual runs increment trial-runs.
    """
    if args.manual and args.automated:
        print(json.dumps({"success": False, "error": "Use --manual OR --automated, not both"}))
        return
    produced_manually = not args.automated  # default to manual (the safe path)

    content = resolve_content(args)
    if not content:
        print(json.dumps({"success": False, "error": "Provide either --content or --content-file"}))
        return

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            spec = get_spec(tx, args.spec)
        if not spec:
            print(json.dumps({"success": False, "error": f"Spec not found: {args.spec}"}))
            return

        status = spec.get("ops-spec-status") or "designed"
        trial_runs = spec.get("ops-trial-runs") or 0
        trial_target = spec.get("ops-trial-target") or DEFAULT_TRIAL_TARGET

        if not produced_manually and status in ("designed", "trial"):
            print(json.dumps({
                "success": False,
                "error": (
                    f"REFUSED: spec '{spec.get('name')}' has status '{status}'. "
                    "The manual-before-automate rule: a brief must be produced MANUALLY "
                    f"and consumed for at least {trial_target} runs ({trial_runs}/{trial_target} done) "
                    "before it may be automated. Log this run with --manual, refine the spec as "
                    "you consume the output, then run promote-spec once the trial target is met. "
                    "Only 'active' specs may log --automated briefs."
                ),
                "spec_id": spec["id"],
                "spec_status": status,
                "trial_runs": trial_runs,
                "trial_target": trial_target,
            }))
            return

        if status == "retired":
            print(json.dumps({
                "success": False,
                "error": f"Spec '{spec.get('name')}' is retired. Re-design a new spec if it is needed again.",
            }))
            return

        brief_id = generate_id("brief")
        timestamp = get_timestamp()
        brief_date = parse_date(args.date) if args.date else timestamp

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''insert $b isa ops-brief,
                has id "{brief_id}",
                has name "{escape_string(spec.get('name') or 'brief')} — {brief_date[:10]}",
                has content "{escape_string(content)}",
                has ops-brief-date {brief_date},
                has ops-produced-manually {"true" if produced_manually else "false"},
                has created-at {timestamp};''').resolve()
            tx.commit()

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $s isa ops-brief-spec, has id "{spec['id']}";
                $b isa ops-brief, has id "{brief_id}";
            insert (spec: $s, brief: $b) isa ops-spec-produced;''').resolve()
            tx.commit()

        new_status = status
        new_runs = trial_runs
        if produced_manually and status in ("designed", "trial"):
            new_runs = trial_runs + 1
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                replace_attr(tx, "ops-brief-spec", spec["id"], "ops-trial-runs", str(new_runs))
                if status == "designed":
                    replace_attr(tx, "ops-brief-spec", spec["id"], "ops-spec-status", '"trial"')
                    new_status = "trial"
                tx.commit()

    result = {
        "success": True,
        "brief_id": brief_id,
        "spec_id": spec["id"],
        "produced_manually": produced_manually,
        "spec_status": new_status,
        "trial_runs": new_runs,
        "trial_target": trial_target,
    }
    if new_status == "trial":
        if new_runs >= trial_target:
            result["message"] = (
                f"Trial target met ({new_runs}/{trial_target}). If the brief has proven its worth, "
                "run promote-spec to allow automation."
            )
        else:
            result["message"] = f"Trial progress: {new_runs}/{trial_target} manual runs."
    print(json.dumps(result))


def cmd_list_briefs(args):
    """List produced brief instances, optionally for one spec."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if args.spec:
                q = f'''match
                    $s isa ops-brief-spec, has id "{escape_string(args.spec)}";
                    (spec: $s, brief: $b) isa ops-spec-produced;
                    $b has id $bid;
                fetch {{
                    "id": $bid,
                    "name": $b.name,
                    "date": $b.ops-brief-date,
                    "produced_manually": $b.ops-produced-manually,
                    "content": $b.content,
                    "spec_id": $s.id,
                    "spec_name": $s.name
                }};'''
            else:
                q = '''match
                    (spec: $s, brief: $b) isa ops-spec-produced;
                    $b has id $bid;
                fetch {
                    "id": $bid,
                    "name": $b.name,
                    "date": $b.ops-brief-date,
                    "produced_manually": $b.ops-produced-manually,
                    "spec_id": $s.id,
                    "spec_name": $s.name
                };'''
            briefs = list(tx.query(q).resolve())

    briefs.sort(key=lambda b: str(b.get("date") or ""), reverse=True)
    limit = args.limit or 30
    print(json.dumps({"success": True, "briefs": briefs[:limit], "count": len(briefs)}, default=str))


def cmd_promote_spec(args):
    """Promote a spec to active. Fails unless trial-runs >= trial-target."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            spec = get_spec(tx, args.spec)
        if not spec:
            print(json.dumps({"success": False, "error": f"Spec not found: {args.spec}"}))
            return

        status = spec.get("ops-spec-status") or "designed"
        trial_runs = spec.get("ops-trial-runs") or 0
        trial_target = spec.get("ops-trial-target") or DEFAULT_TRIAL_TARGET

        if status == "active":
            print(json.dumps({"success": False, "error": "Spec is already active"}))
            return
        if status == "retired":
            print(json.dumps({"success": False, "error": "Spec is retired; design a new one instead"}))
            return
        if trial_runs < trial_target:
            print(json.dumps({
                "success": False,
                "error": (
                    f"Cannot promote: {trial_runs}/{trial_target} manual trial runs completed. "
                    f"Run the brief manually {trial_target - trial_runs} more time(s) "
                    "(log-brief --manual) and actually consume the output before automating."
                ),
                "trial_runs": trial_runs,
                "trial_target": trial_target,
            }))
            return

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            replace_attr(tx, "ops-brief-spec", spec["id"], "ops-spec-status", '"active"')
            tx.commit()

    print(json.dumps({
        "success": True,
        "spec_id": spec["id"],
        "status": "active",
        "message": (
            "Spec promoted to active. Automation is now allowed: wire a Claude Code "
            "trigger/cron/scheduled session that produces the brief and logs it with "
            "log-brief --automated."
        ),
    }))


def cmd_retire_spec(args):
    """Retire a spec (briefs nobody reads should die)."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            spec = get_spec(tx, args.spec)
        if not spec:
            print(json.dumps({"success": False, "error": f"Spec not found: {args.spec}"}))
            return
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            replace_attr(tx, "ops-brief-spec", spec["id"], "ops-spec-status", '"retired"')
            tx.commit()
    print(json.dumps({"success": True, "spec_id": spec["id"], "status": "retired"}))


# =============================================================================
# STAKEHOLDER CRM COMMANDS
# =============================================================================


def cmd_add_person(args):
    """Thin helper: find-or-create an alh-person (career skill may be absent)."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            existing = resolve_person(tx, args.name)
        if existing:
            print(json.dumps({
                "success": True,
                "person_id": existing["id"],
                "name": existing["name"],
                "created": False,
                "message": "Person already exists; reusing.",
            }))
            return

        person_id = generate_id("person")
        query = f'''insert $p isa alh-person,
            has id "{person_id}",
            has name "{escape_string(args.name)}",
            has created-at {get_timestamp()}'''
        if args.description:
            query += f', has description "{escape_string(args.description)}"'
        if args.email:
            query += f', has alh-email-address "{escape_string(args.email)}"'
        query += ";"
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

    print(json.dumps({"success": True, "person_id": person_id, "name": args.name, "created": True}))


def cmd_add_dossier(args):
    """Create a stakeholder dossier linked to a person."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            person = resolve_person(tx, args.person)
        if not person:
            print(json.dumps({
                "success": False,
                "error": f"Person not found: {args.person}. Create one first with add-person --name.",
            }))
            return

        dossier_id = generate_id("dossier")
        query = f'''insert $d isa ops-dossier,
            has id "{dossier_id}",
            has name "Dossier: {escape_string(person['name'])}",
            has created-at {get_timestamp()}'''
        if args.relationship:
            query += f', has ops-relationship "{escape_string(args.relationship)}"'
        if args.current_state:
            query += f', has ops-current-state "{escape_string(args.current_state)}"'
        if args.history:
            query += f', has ops-history-summary "{escape_string(args.history)}"'
        query += ";"

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $d isa ops-dossier, has id "{dossier_id}";
                $p isa alh-person, has id "{person['id']}";
            insert (dossier: $d, person: $p) isa ops-dossier-about;''').resolve()
            tx.commit()

        primer_note_id = None
        if args.primer:
            primer_note_id = add_primer_note(driver, dossier_id, args.primer)

    print(json.dumps({
        "success": True,
        "dossier_id": dossier_id,
        "person_id": person["id"],
        "person_name": person["name"],
        "primer_note_id": primer_note_id,
    }))


def _person_touchpoints(tx, person_id: str):
    tps = list(tx.query(f'''match
        $p isa alh-person, has id "{person_id}";
        (touchpoint: $t, person: $p) isa ops-touchpoint-with;
        $t has id $tid;
    fetch {{
        "id": $tid,
        "name": $t.name,
        "content": $t.content,
        "interaction_type": $t.alh-interaction-type,
        "interaction_date": $t.alh-interaction-date,
        "undercurrent": $t.ops-undercurrent,
        "commitments_made": $t.ops-commitments-made,
        "created_at": $t.created-at
    }};''').resolve())
    tps.sort(key=lambda t: str(t.get("interaction_date") or t.get("created_at") or ""), reverse=True)
    return tps


def _person_commitments(tx, person_id: str, statuses=None):
    rows = list(tx.query(f'''match
        $p isa alh-person, has id "{person_id}";
        (commitment: $c, person: $p) isa ops-commitment-with;
        $c has id $cid;
    fetch {{
        "id": $cid,
        "name": $c.name,
        "description": $c.description,
        "owed_by": $c.ops-owed-by,
        "due_date": $c.ops-due-date,
        "status": $c.ops-commitment-status
    }};''').resolve())
    if statuses:
        rows = [r for r in rows if r.get("status") in statuses]
    now = datetime.now()
    for r in rows:
        due = to_dt(r.get("due_date"))
        r["overdue"] = bool(due and due < now and r.get("status") == "open")
    rows.sort(key=lambda r: str(r.get("due_date") or "9999"))
    return rows


def _person_dossier(tx, person_id: str):
    return fetch_one(tx, f'''match
        $p isa alh-person, has id "{person_id}";
        (dossier: $d, person: $p) isa ops-dossier-about;
    fetch {{
        "id": $d.id,
        "name": $d.name,
        "relationship": $d.ops-relationship,
        "current_state": $d.ops-current-state,
        "history_summary": $d.ops-history-summary
    }};''')


def _person_preps(tx, person_id: str):
    preps = list(tx.query(f'''match
        $p isa alh-person, has id "{person_id}";
        (prep: $mp, person: $p) isa ops-prep-for;
        $mp has id $mpid;
    fetch {{
        "id": $mpid,
        "meeting_title": $mp.ops-meeting-title,
        "meeting_date": $mp.ops-meeting-date,
        "content": $mp.content
    }};''').resolve())
    preps.sort(key=lambda x: str(x.get("meeting_date") or ""), reverse=True)
    return preps


def cmd_list_stakeholders(args):
    """CRM table: every dossier with person, last touchpoint, open commitments."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            rows = list(tx.query('''match
                $d isa ops-dossier, has id $did;
                (dossier: $d, person: $p) isa ops-dossier-about;
                $p has id $pid, has name $pn;
            fetch {
                "dossier_id": $did,
                "person_id": $pid,
                "person_name": $pn,
                "relationship": $d.ops-relationship,
                "current_state": $d.ops-current-state
            };''').resolve())

            out = []
            for r in rows:
                tps = _person_touchpoints(tx, r["person_id"])
                open_commitments = _person_commitments(tx, r["person_id"], statuses=["open", "overdue"])
                last_tp = tps[0] if tps else None
                out.append({
                    **r,
                    "touchpoint_count": len(tps),
                    "last_touchpoint_date": (
                        str(last_tp.get("interaction_date") or last_tp.get("created_at")) if last_tp else None
                    ),
                    "last_undercurrent": last_tp.get("undercurrent") if last_tp else None,
                    "open_commitments": len(open_commitments),
                    "overdue_commitments": sum(1 for c in open_commitments if c["overdue"] or c.get("status") == "overdue"),
                })

    out.sort(key=lambda r: str(r.get("last_touchpoint_date") or ""), reverse=True)
    print(json.dumps({"success": True, "stakeholders": out, "count": len(out)}, default=str))


def cmd_show_stakeholder(args):
    """The pre-meeting context pull: dossier + touchpoints + open commitments + preps."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            person = resolve_person(tx, args.person)
            if not person:
                print(json.dumps({"success": False, "error": f"Person not found: {args.person}"}))
                return
            dossier = _person_dossier(tx, person["id"])
            touchpoints = _person_touchpoints(tx, person["id"])
            commitments = _person_commitments(tx, person["id"])
            preps = _person_preps(tx, person["id"])

    print(json.dumps({
        "success": True,
        "person": person,
        "dossier": dossier,
        "touchpoints": touchpoints,
        "commitments": commitments,
        "open_commitments": [c for c in commitments if c.get("status") in ("open", "overdue")],
        "meeting_preps": preps[:5],
    }, default=str))


def cmd_log_touchpoint(args):
    """Log an interaction with a person — always capture the undercurrent."""
    content = resolve_content(args)
    if not content:
        print(json.dumps({"success": False, "error": "Provide either --content or --content-file"}))
        return

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            person = resolve_person(tx, args.person)
        if not person:
            print(json.dumps({"success": False, "error": f"Person not found: {args.person}"}))
            return

        tp_id = generate_id("touchpoint")
        timestamp = get_timestamp()
        interaction_date = parse_date(args.date) if args.date else timestamp

        query = f'''insert $t isa ops-touchpoint,
            has id "{tp_id}",
            has name "Touchpoint: {escape_string(person['name'])} — {interaction_date[:10]}",
            has content "{escape_string(content)}",
            has alh-interaction-date {interaction_date},
            has created-at {timestamp}'''
        if args.type:
            query += f', has alh-interaction-type "{escape_string(args.type)}"'
        if args.undercurrent:
            query += f', has ops-undercurrent "{escape_string(args.undercurrent)}"'
        if args.commitments_made:
            query += f', has ops-commitments-made "{escape_string(args.commitments_made)}"'
        query += ";"

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $t isa ops-touchpoint, has id "{tp_id}";
                $p isa alh-person, has id "{person['id']}";
            insert (touchpoint: $t, person: $p) isa ops-touchpoint-with;''').resolve()
            tx.commit()

    result = {
        "success": True,
        "touchpoint_id": tp_id,
        "person_id": person["id"],
        "person_name": person["name"],
    }
    if not args.undercurrent:
        result["warning"] = (
            "No --undercurrent recorded. The undercurrent (mood, hesitation, what was NOT said) "
            "is what makes future meeting prep non-generic — add it while memory is fresh."
        )
    if args.commitments_made:
        result["message"] = (
            "Commitments were made — harvest them into tracked commitments with "
            f"add-commitment --person {person['id']} --from-touchpoint {tp_id}."
        )
    print(json.dumps(result))


def cmd_prep_meeting(args):
    """Assemble stakeholder context JSON so the agent can write the prep pack."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            people = []
            missing = []
            for ident in args.person:
                person = resolve_person(tx, ident)
                if not person:
                    missing.append(ident)
                    continue
                people.append({
                    "person": person,
                    "dossier": _person_dossier(tx, person["id"]),
                    "recent_touchpoints": _person_touchpoints(tx, person["id"])[:10],
                    "open_commitments": _person_commitments(tx, person["id"], statuses=["open", "overdue"]),
                    "last_prep": (_person_preps(tx, person["id"]) or [None])[0],
                })

    print(json.dumps({
        "success": True,
        "meeting_title": args.title,
        "meeting_date": args.date,
        "attendees": people,
        "missing_people": missing,
        "instruction": (
            "Agent: write a personalized prep pack from this context — relationship state, "
            "undercurrents from recent touchpoints (mood, tensions, what was left unsaid), "
            "open commitments in BOTH directions (what I owe them, what they owe me), "
            "suggested talking points and landmines. Do NOT just summarize the last transcript. "
            "Store with save-prep; the operator reviews it before the meeting."
        ),
    }, default=str))


def cmd_save_prep(args):
    """Store the agent-written prep pack, linked to attending person(s)."""
    content = resolve_content(args)
    if not content:
        print(json.dumps({"success": False, "error": "Provide either --content or --content-file"}))
        return

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            people = []
            for ident in args.person:
                person = resolve_person(tx, ident)
                if not person:
                    print(json.dumps({"success": False, "error": f"Person not found: {ident}"}))
                    return
                people.append(person)

        prep_id = generate_id("prep")
        timestamp = get_timestamp()
        meeting_date = parse_date(args.date) if args.date else timestamp
        title = args.title or f"Meeting with {', '.join(p['name'] for p in people)}"

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''insert $mp isa ops-meeting-prep,
                has id "{prep_id}",
                has name "Prep: {escape_string(title)}",
                has content "{escape_string(content)}",
                has ops-meeting-title "{escape_string(title)}",
                has ops-meeting-date {meeting_date},
                has created-at {timestamp};''').resolve()
            tx.commit()

        for person in people:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $mp isa ops-meeting-prep, has id "{prep_id}";
                    $p isa alh-person, has id "{person['id']}";
                insert (prep: $mp, person: $p) isa ops-prep-for;''').resolve()
                tx.commit()

    print(json.dumps({
        "success": True,
        "prep_id": prep_id,
        "meeting_title": title,
        "people": [p["id"] for p in people],
        "message": "Prep saved. OPERATOR CHECKPOINT: review the prep pack before the meeting.",
    }))


# =============================================================================
# COMMITMENT COMMANDS
# =============================================================================


def cmd_add_commitment(args):
    """Record who owes what by when."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            person = resolve_person(tx, args.person)
        if not person:
            print(json.dumps({"success": False, "error": f"Person not found: {args.person}"}))
            return

        commitment_id = generate_id("commitment")
        query = f'''insert $c isa ops-commitment,
            has id "{commitment_id}",
            has name "{escape_string(args.what)}",
            has ops-owed-by "{args.owed_by}",
            has ops-commitment-status "open",
            has created-at {get_timestamp()}'''
        if args.due:
            query += f', has ops-due-date {parse_date(args.due)}'
        if args.description:
            query += f', has description "{escape_string(args.description)}"'
        if args.from_touchpoint:
            query += f', has provenance "touchpoint:{escape_string(args.from_touchpoint)}"'
        query += ";"

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $c isa ops-commitment, has id "{commitment_id}";
                $p isa alh-person, has id "{person['id']}";
            insert (commitment: $c, person: $p) isa ops-commitment-with;''').resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "commitment_id": commitment_id,
        "what": args.what,
        "owed_by": args.owed_by,
        "person_id": person["id"],
        "person_name": person["name"],
        "due": args.due,
    }))


def cmd_update_commitment(args):
    """Update a commitment's status and/or due date."""
    if not args.status and not args.due:
        print(json.dumps({"success": False, "error": "Provide --status and/or --due"}))
        return

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            existing = fetch_one(tx, f'''match $c isa ops-commitment, has id "{escape_string(args.id)}";
            fetch {{ "id": $c.id, "name": $c.name }};''')
        if not existing:
            print(json.dumps({"success": False, "error": f"Commitment not found: {args.id}"}))
            return

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            if args.status:
                replace_attr(tx, "ops-commitment", args.id, "ops-commitment-status", f'"{args.status}"')
            if args.due:
                replace_attr(tx, "ops-commitment", args.id, "ops-due-date", parse_date(args.due))
            tx.commit()

    print(json.dumps({
        "success": True,
        "commitment_id": args.id,
        "status": args.status,
        "due": args.due,
    }))


def _all_commitments(tx):
    rows = list(tx.query('''match
        $c isa ops-commitment, has id $cid;
        (commitment: $c, person: $p) isa ops-commitment-with;
        $p has id $pid, has name $pn;
    fetch {
        "id": $cid,
        "name": $c.name,
        "description": $c.description,
        "owed_by": $c.ops-owed-by,
        "due_date": $c.ops-due-date,
        "status": $c.ops-commitment-status,
        "person_id": $pid,
        "person_name": $pn
    };''').resolve())
    now = datetime.now()
    for r in rows:
        due = to_dt(r.get("due_date"))
        r["overdue"] = bool(due and due < now and r.get("status") == "open")
    return rows


def cmd_list_commitments(args):
    """List commitments with --due / --owed-by / --status / --person filters."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            rows = _all_commitments(tx)
            person = resolve_person(tx, args.person) if args.person else None

    if args.person:
        if not person:
            print(json.dumps({"success": False, "error": f"Person not found: {args.person}"}))
            return
        rows = [r for r in rows if r["person_id"] == person["id"]]
    if args.owed_by:
        rows = [r for r in rows if r.get("owed_by") == args.owed_by]
    if args.status:
        rows = [r for r in rows if r.get("status") == args.status]
    if args.due:
        cutoff = to_dt(parse_date(args.due))
        rows = [r for r in rows if to_dt(r.get("due_date")) and to_dt(r["due_date"]) <= cutoff]

    rows.sort(key=lambda r: str(r.get("due_date") or "9999"))
    print(json.dumps({"success": True, "commitments": rows, "count": len(rows)}, default=str))


# =============================================================================
# MONITOR COMMANDS
# =============================================================================


def cmd_add_monitor(args):
    """Add a standing visibility question."""
    monitor_id = generate_id("monitor")
    query = f'''insert $m isa ops-monitor,
        has id "{monitor_id}",
        has name "{escape_string(args.name or args.question[:60])}",
        has ops-question "{escape_string(args.question)}",
        has ops-monitor-status "{args.status}",
        has created-at {get_timestamp()}'''
    if args.sources:
        query += f', has ops-monitor-sources "{escape_string(args.sources)}"'
    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

    print(json.dumps({"success": True, "monitor_id": monitor_id, "question": args.question}))


def _all_monitors(tx):
    rows = list(tx.query('''match $m isa ops-monitor, has id $mid;
    fetch {
        "id": $mid,
        "name": $m.name,
        "question": $m.ops-question,
        "sources": $m.ops-monitor-sources,
        "status": $m.ops-monitor-status,
        "last_checked": $m.ops-last-checked
    };''').resolve())
    now = datetime.now()
    for r in rows:
        checked = to_dt(r.get("last_checked"))
        r["stale"] = bool(
            r.get("status") == "active"
            and (checked is None or (now - checked).days >= STALE_MONITOR_DAYS)
        )
    return rows


def cmd_list_monitors(args):
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            rows = _all_monitors(tx)
    if args.status:
        rows = [r for r in rows if r.get("status") == args.status]
    print(json.dumps({"success": True, "monitors": rows, "count": len(rows)}, default=str))


def cmd_update_monitor(args):
    """Update monitor status and/or mark it checked now."""
    if not args.status and not args.checked:
        print(json.dumps({"success": False, "error": "Provide --status and/or --checked"}))
        return
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            existing = fetch_one(tx, f'''match $m isa ops-monitor, has id "{escape_string(args.id)}";
            fetch {{ "id": $m.id }};''')
        if not existing:
            print(json.dumps({"success": False, "error": f"Monitor not found: {args.id}"}))
            return
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            if args.status:
                replace_attr(tx, "ops-monitor", args.id, "ops-monitor-status", f'"{args.status}"')
            if args.checked:
                replace_attr(tx, "ops-monitor", args.id, "ops-last-checked", get_timestamp())
            tx.commit()
    print(json.dumps({"success": True, "monitor_id": args.id, "status": args.status, "checked": bool(args.checked)}))


# =============================================================================
# SYNTHESIS COMMANDS
# =============================================================================


def _compute_today():
    """Everything the operator needs this morning, as one dict."""
    now = datetime.now()
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Briefs due by cadence (trial + active specs)
            specs = list(tx.query('''match $s isa ops-brief-spec, has id $sid;
            fetch {
                "id": $sid,
                "name": $s.name,
                "cadence": $s.ops-cadence,
                "status": $s.ops-spec-status,
                "trial_runs": $s.ops-trial-runs,
                "trial_target": $s.ops-trial-target
            };''').resolve())

            briefs_due = []
            for s in specs:
                if s.get("status") not in ("trial", "active"):
                    continue
                dates = list(tx.query(f'''match
                    $s isa ops-brief-spec, has id "{s['id']}";
                    (spec: $s, brief: $b) isa ops-spec-produced;
                    $b has ops-brief-date $d;
                fetch {{ "date": $d }};''').resolve())
                dts = sorted([to_dt(d["date"]) for d in dates if to_dt(d["date"])])
                last = dts[-1] if dts else None
                interval = cadence_days(s.get("cadence") or "daily")
                due = last is None or (now - last).days >= interval
                if due:
                    briefs_due.append({
                        "spec_id": s["id"],
                        "name": s.get("name"),
                        "cadence": s.get("cadence"),
                        "status": s.get("status"),
                        "trial_runs": s.get("trial_runs"),
                        "trial_target": s.get("trial_target"),
                        "last_brief": last.isoformat() if last else None,
                        "mode": "manual (trial)" if s.get("status") == "trial" else "automated allowed",
                    })

            # Commitments
            commitments = _all_commitments(tx)
            open_commitments = [c for c in commitments if c.get("status") == "open" and not c["overdue"]]
            overdue = [c for c in commitments if c["overdue"] or c.get("status") == "overdue"]
            due_soon = [
                c for c in open_commitments
                if to_dt(c.get("due_date")) and to_dt(c["due_date"]) <= now + timedelta(days=3)
            ]

            # Upcoming meeting preps
            preps = list(tx.query('''match $mp isa ops-meeting-prep, has id $mpid;
            fetch {
                "id": $mpid,
                "meeting_title": $mp.ops-meeting-title,
                "meeting_date": $mp.ops-meeting-date
            };''').resolve())
            upcoming_preps = []
            for p in preps:
                d = to_dt(p.get("meeting_date"))
                if d and now - timedelta(days=1) <= d <= now + timedelta(days=UPCOMING_PREP_DAYS):
                    upcoming_preps.append({**p, "meeting_date": d.isoformat()})
            upcoming_preps.sort(key=lambda p: p["meeting_date"])

            # Stale monitors
            monitors = _all_monitors(tx)
            stale_monitors = [m for m in monitors if m["stale"]]

    return {
        "success": True,
        "date": now.strftime("%Y-%m-%d"),
        "briefs_due": briefs_due,
        "overdue_commitments": overdue,
        "commitments_due_soon": due_soon,
        "open_commitments": open_commitments,
        "upcoming_meeting_preps": upcoming_preps,
        "stale_monitors": stale_monitors,
    }


def cmd_today(args):
    print(json.dumps(_compute_today(), default=str))


def cmd_report_today(args):
    """Markdown morning brief for human display."""
    t = _compute_today()
    lines = [f"# Ops Morning Brief — {t['date']}", ""]

    lines.append("## Briefs due")
    if t["briefs_due"]:
        for b in t["briefs_due"]:
            trial = ""
            if b["status"] == "trial":
                trial = f" — TRIAL {b.get('trial_runs', 0)}/{b.get('trial_target', DEFAULT_TRIAL_TARGET)} (run manually!)"
            lines.append(f"- **{b['name']}** ({b.get('cadence') or 'daily'}, last: {b['last_brief'] or 'never'}){trial}")
    else:
        lines.append("- None due.")
    lines.append("")

    lines.append("## Commitments")
    if t["overdue_commitments"]:
        lines.append("### Overdue")
        for c in t["overdue_commitments"]:
            who = "I owe" if c.get("owed_by") == "me" else f"{c['person_name']} owes me"
            lines.append(f"- ⚠ **{c['name']}** — {who}, due {str(c.get('due_date'))[:10]}")
    if t["commitments_due_soon"]:
        lines.append("### Due in the next 3 days")
        for c in t["commitments_due_soon"]:
            who = "I owe" if c.get("owed_by") == "me" else f"{c['person_name']} owes me"
            lines.append(f"- **{c['name']}** — {who}, due {str(c.get('due_date'))[:10]}")
    if not t["overdue_commitments"] and not t["commitments_due_soon"]:
        lines.append("- Nothing overdue or imminent.")
    lines.append("")

    lines.append("## Upcoming meetings with preps")
    if t["upcoming_meeting_preps"]:
        for p in t["upcoming_meeting_preps"]:
            lines.append(f"- {str(p['meeting_date'])[:10]}: **{p.get('meeting_title')}** (prep {p['id']})")
    else:
        lines.append("- No preps on file for the coming week. Any meetings that need one?")
    lines.append("")

    lines.append("## Stale monitors")
    if t["stale_monitors"]:
        for m in t["stale_monitors"]:
            lines.append(f"- **{m.get('name')}** — \"{m.get('question')}\" (last checked: {m.get('last_checked') or 'never'})")
    else:
        lines.append("- All monitors fresh.")

    print("\n".join(lines))


def cmd_add_note(args):
    """Attach a primer/interview/general note to any ops entity via alh-aboutness."""
    content = resolve_content(args)
    if not content:
        print(json.dumps({"success": False, "error": "Provide either --content or --content-file"}))
        return

    type_map = {
        "primer": "ops-primer-note",
        "interview": "ops-interview-note",
        "general": "note",
    }
    note_type = type_map.get(args.type, "note")
    note_id = generate_id("note" if note_type == "note" else args.type)

    query = f'''insert $n isa {note_type},
        has id "{note_id}",
        has content "{escape_string(content)}",
        has created-at {get_timestamp()}'''
    if args.name:
        query += f', has name "{escape_string(args.name)}"'
    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()
        link_note_about(driver, note_id, args.about)

    print(json.dumps({"success": True, "note_id": note_id, "about": args.about, "type": args.type}))


def cmd_audit(args):
    """Run declarative quality checks from quality-checks.yaml plus computed checks."""
    if not YAML_AVAILABLE:
        print(json.dumps({"success": False, "error": "pyyaml not installed (required for audit)"}))
        return

    checks_path = Path(__file__).parent / "quality-checks.yaml"
    if not checks_path.exists():
        print(json.dumps({"success": False, "error": f"quality-checks.yaml not found at {checks_path}"}))
        return

    spec = yaml.safe_load(checks_path.read_text())
    results = []
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            for check in spec.get("checks", []):
                entry = {
                    "name": check["name"],
                    "severity": check.get("severity"),
                    "description": check.get("description"),
                }
                try:
                    violations = list(tx.query(check["find_violations"]).resolve())
                    entry["violations"] = violations
                    entry["violation_count"] = len(violations)
                    if check.get("count_total"):
                        entry["total"] = len(list(tx.query(check["count_total"]).resolve()))
                except Exception as e:
                    entry["error"] = str(e)
                results.append(entry)

            # Computed check: open commitments past their due date (needs "now")
            past_due = [c for c in _all_commitments(tx) if c["overdue"]]
            results.append({
                "name": "open-commitments-past-due",
                "severity": "high",
                "description": "Open commitments whose due date has passed (computed; mark done/dropped or update-commitment --status overdue)",
                "violations": [{"id": c["id"], "name": c["name"], "due_date": str(c.get("due_date"))} for c in past_due],
                "violation_count": len(past_due),
            })

    total_violations = sum(r.get("violation_count", 0) for r in results)
    print(json.dumps({
        "success": True,
        "checks": results,
        "total_violations": total_violations,
    }, default=str))


# =============================================================================
# OKR SPINE - objectives (primary), key results, work items, evidence
# =============================================================================


def _link(driver, query: str):
    """Run a single write query in its own transaction and commit."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(query).resolve()
        tx.commit()


def link_owned(driver, item_id: str, person_id: str):
    """Link any planning element to its accountable person via ops-owned."""
    _link(driver, f'''match
        $i isa alh-identifiable-entity, has id "{item_id}";
        $p isa alh-person, has id "{person_id}";
    insert (item: $i, owner: $p) isa ops-owned;''')


def cmd_add_objective(args):
    """Create an objective - the PRIMARY planning element."""
    status = args.status or "draft"
    oid = generate_id("objective")
    query = f'''insert $o isa ops-objective,
        has id "{oid}",
        has name "{escape_string(args.name)}",
        has ops-objective-status "{status}",
        has created-at {get_timestamp()}'''
    if args.period:
        query += f', has ops-objective-period "{escape_string(args.period)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'
    query += ";"

    with get_driver() as driver:
        owner = None
        if args.owner:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                owner = resolve_person(tx, args.owner)
            if not owner:
                print(json.dumps({"success": False, "error": f"Person not found: {args.owner}"}))
                return
        _link(driver, query)
        if owner:
            link_owned(driver, oid, owner["id"])
        if args.serves:
            _link(driver, f'''match
                $o isa ops-objective, has id "{oid}";
                $s isa alh-identifiable-entity, has id "{escape_string(args.serves)}";
            insert (objective: $o, subject: $s) isa ops-objective-serves;''')
        primer = getattr(args, "primer", None)
        if primer:
            add_primer_note(driver, oid, primer)

    print(json.dumps({
        "success": True, "objective_id": oid, "name": args.name,
        "status": status, "owner": owner["name"] if owner else None,
        "serves": args.serves,
    }))


def cmd_add_kr(args):
    """Add a measurable key result under an objective."""
    status = args.status or "on-track"
    kid = generate_id("kr")
    query = f'''insert $k isa ops-key-result,
        has id "{kid}",
        has name "{escape_string(args.name)}",
        has ops-kr-status "{status}",
        has created-at {get_timestamp()}'''
    if args.metric:
        query += f', has ops-kr-metric "{escape_string(args.metric)}"'
    if args.baseline:
        query += f', has ops-kr-baseline "{escape_string(args.baseline)}"'
    if args.current:
        query += f', has ops-kr-current "{escape_string(args.current)}"'
    if args.target_date:
        query += f', has ops-target-date {parse_date(args.target_date)}'
    query += ";"

    with get_driver() as driver:
        # verify objective exists
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            obj = fetch_one(tx, f'match $o isa ops-objective, has id "{escape_string(args.objective)}"; fetch {{ "id": $o.id }};')
        if not obj:
            print(json.dumps({"success": False, "error": f"Objective not found: {args.objective}"}))
            return
        owner = None
        if args.owner:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                owner = resolve_person(tx, args.owner)
            if not owner:
                print(json.dumps({"success": False, "error": f"Person not found: {args.owner}"}))
                return
        _link(driver, query)
        _link(driver, f'''match
            $o isa ops-objective, has id "{escape_string(args.objective)}";
            $k isa ops-key-result, has id "{kid}";
        insert (objective: $o, key-result: $k) isa ops-objective-kr;''')
        if owner:
            link_owned(driver, kid, owner["id"])

    print(json.dumps({"success": True, "key_result_id": kid, "objective_id": args.objective, "name": args.name}))


def cmd_add_workitem(args):
    """Add a story/task/subtask under a key result (--kr) or another work item (--parent)."""
    if not args.kr and not args.parent:
        print(json.dumps({"success": False, "error": "Provide --kr (root work item) or --parent (nested)"}))
        return
    status = args.status or "not-started"
    wid = generate_id("workitem")
    query = f'''insert $w isa ops-workitem,
        has id "{wid}",
        has name "{escape_string(args.name)}",
        has ops-workitem-kind "{args.kind}",
        has ops-workitem-status "{status}",
        has created-at {get_timestamp()}'''
    if args.description:
        query += f', has description "{escape_string(args.description)}"'
    if args.target_date:
        query += f', has ops-target-date {parse_date(args.target_date)}'
    if args.order is not None:
        query += f', has ops-order {args.order}'
    query += ";"

    with get_driver() as driver:
        owner = None
        if args.owner:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                owner = resolve_person(tx, args.owner)
            if not owner:
                print(json.dumps({"success": False, "error": f"Person not found: {args.owner}"}))
                return
        _link(driver, query)
        if args.kr:
            _link(driver, f'''match
                $k isa ops-key-result, has id "{escape_string(args.kr)}";
                $w isa ops-workitem, has id "{wid}";
            insert (key-result: $k, workitem: $w) isa ops-kr-work;''')
        if args.parent:
            _link(driver, f'''match
                $p isa ops-workitem, has id "{escape_string(args.parent)}";
                $c isa ops-workitem, has id "{wid}";
            insert (parent: $p, child: $c) isa ops-workitem-tree;''')
        if owner:
            link_owned(driver, wid, owner["id"])

    print(json.dumps({"success": True, "workitem_id": wid, "kind": args.kind, "name": args.name,
                      "kr": args.kr, "parent": args.parent}))


def cmd_update_objective(args):
    """Update an objective's status / period / name."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            if args.status:
                replace_attr(tx, "ops-objective", args.id, "ops-objective-status", f'"{args.status}"')
            if args.period:
                replace_attr(tx, "ops-objective", args.id, "ops-objective-period", f'"{escape_string(args.period)}"')
            if args.name:
                replace_attr(tx, "ops-objective", args.id, "name", f'"{escape_string(args.name)}"')
            tx.commit()
    print(json.dumps({"success": True, "objective_id": args.id, "status": args.status}))


def cmd_update_kr(args):
    """Update a key result's current value / status / target date."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            if args.current:
                replace_attr(tx, "ops-key-result", args.id, "ops-kr-current", f'"{escape_string(args.current)}"')
            if args.status:
                replace_attr(tx, "ops-key-result", args.id, "ops-kr-status", f'"{args.status}"')
            if args.target_date:
                replace_attr(tx, "ops-key-result", args.id, "ops-target-date", parse_date(args.target_date))
            tx.commit()
    print(json.dumps({"success": True, "key_result_id": args.id, "current": args.current, "status": args.status}))


def cmd_update_workitem(args):
    """Update a work item's status / name / target date."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            if args.status:
                replace_attr(tx, "ops-workitem", args.id, "ops-workitem-status", f'"{args.status}"')
            if args.name:
                replace_attr(tx, "ops-workitem", args.id, "name", f'"{escape_string(args.name)}"')
            if args.target_date:
                replace_attr(tx, "ops-workitem", args.id, "ops-target-date", parse_date(args.target_date))
            tx.commit()
    print(json.dumps({"success": True, "workitem_id": args.id, "status": args.status}))


def cmd_link_commitment(args):
    """Bridge a leaf work item to a dated, person-owed ops-commitment."""
    with get_driver() as driver:
        _link(driver, f'''match
            $w isa ops-workitem, has id "{escape_string(args.workitem)}";
            $c isa ops-commitment, has id "{escape_string(args.commitment)}";
        insert (item: $w, commitment: $c) isa ops-workitem-commitment;''')
    print(json.dumps({"success": True, "workitem_id": args.workitem, "commitment_id": args.commitment}))


def _workitem_children(tx, wid: str):
    rows = list(tx.query(f'''match
        $p isa ops-workitem, has id "{wid}";
        (parent: $p, child: $c) isa ops-workitem-tree;
        $c has id $id, has name $n, has ops-workitem-kind $k, has ops-workitem-status $s;
    fetch {{ "id": $id, "name": $n, "kind": $k, "status": $s,
             "provider": $c.ops-external-provider, "uri": $c.ops-external-uri,
             "last_synced": $c.ops-last-synced }};''').resolve())
    return rows


def _build_workitem_tree(tx, wid: str, counts: dict):
    children = []
    for row in _workitem_children(tx, wid):
        counts["total"] += 1
        if row.get("status") == "done":
            counts["done"] += 1
        row["children"] = _build_workitem_tree(tx, row["id"], counts)
        children.append(row)
    return children


def cmd_show_tree(args):
    """Render an objective -> key results -> work item tree with rolled-up progress."""
    oid = escape_string(args.objective)
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            obj = fetch_one(tx, f'''match $o isa ops-objective, has id "{oid}", has name $n;
                fetch {{ "id": $o.id, "name": $n, "status": $o.ops-objective-status, "period": $o.ops-objective-period }};''')
            if not obj:
                print(json.dumps({"success": False, "error": f"Objective not found: {args.objective}"}))
                return
            counts = {"total": 0, "done": 0}
            krs = []
            kr_rows = list(tx.query(f'''match
                $o isa ops-objective, has id "{oid}";
                (objective: $o, key-result: $k) isa ops-objective-kr;
                $k has id $id, has name $n;
            fetch {{ "id": $id, "name": $n, "status": $k.ops-kr-status,
                     "metric": $k.ops-kr-metric, "current": $k.ops-kr-current,
                     "target_date": $k.ops-target-date }};''').resolve())
            for kr in kr_rows:
                roots = list(tx.query(f'''match
                    $k isa ops-key-result, has id "{kr['id']}";
                    (key-result: $k, workitem: $w) isa ops-kr-work;
                    $w has id $id, has name $n, has ops-workitem-kind $kind, has ops-workitem-status $s;
                fetch {{ "id": $id, "name": $n, "kind": $kind, "status": $s,
                         "provider": $w.ops-external-provider, "uri": $w.ops-external-uri,
                         "last_synced": $w.ops-last-synced }};''').resolve())
                for r in roots:
                    counts["total"] += 1
                    if r.get("status") == "done":
                        counts["done"] += 1
                    r["children"] = _build_workitem_tree(tx, r["id"], counts)
                kr["workitems"] = roots
                krs.append(kr)

    pct = round(100 * counts["done"] / counts["total"]) if counts["total"] else 0
    print(json.dumps({
        "success": True, "objective": obj, "key_results": krs,
        "progress": {"done": counts["done"], "total": counts["total"], "percent": pct},
    }, default=str))


def cmd_list_objectives(args):
    """List objectives (optionally filtered by status or the subject they serve)."""
    match = 'match $o isa ops-objective, has id $id, has name $n'
    if getattr(args, "status", None):
        match += f', has ops-objective-status "{args.status}"'
    if getattr(args, "serves", None):
        match += f'; (objective: $o, subject: $s) isa ops-objective-serves; $s has id "{escape_string(args.serves)}"'
    q = (match + '; fetch { "id": $id, "name": $n, "status": $o.ops-objective-status, '
         '"period": $o.ops-objective-period };')
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            rows = list(tx.query(q).resolve())
    print(json.dumps({"success": True, "objectives": rows, "count": len(rows)}, default=str))


# =============================================================================
# EXTERNAL DATA - emails, calendar meetings, docs as artifacts
# =============================================================================


def _link_evidence(driver, artifact_id: str, subject_id: str):
    _link(driver, f'''match
        $a isa alh-artifact, has id "{artifact_id}";
        $s isa alh-domain-thing, has id "{subject_id}";
    insert (artifact: $a, subject: $s) isa ops-evidence;''')


def cmd_add_email(args):
    """Capture an email as an artifact; link correspondents and (optionally) evidence."""
    eid = generate_id("email")
    content = resolve_content(args)
    query = f'''insert $e isa ops-email,
        has id "{eid}",
        has name "{escape_string(args.subject)}",
        has created-at {get_timestamp()}'''
    if content:
        query += f', has content "{escape_string(content)}"'
    if args.sent_at:
        query += f', has ops-sent-at {parse_date(args.sent_at)}'
    if args.uri:
        query += f', has ops-external-uri "{escape_string(args.uri)}"'
    query += ";"
    with get_driver() as driver:
        _link(driver, query)
        parties = []
        for ident in (args.party or []):
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                p = resolve_person(tx, ident)
            if p:
                _link(driver, f'''match $e isa ops-email, has id "{eid}"; $p isa alh-person, has id "{p['id']}";
                    insert (email: $e, person: $p) isa ops-email-party;''')
                parties.append(p["name"])
        if args.evidence_for:
            _link_evidence(driver, eid, escape_string(args.evidence_for))
    print(json.dumps({"success": True, "email_id": eid, "subject": args.subject,
                      "parties": parties, "evidence_for": args.evidence_for}))


def cmd_add_event(args):
    """Capture a calendar meeting as an artifact; link attendees and (optionally) evidence."""
    vid = generate_id("event")
    content = resolve_content(args)
    query = f'''insert $v isa ops-calendar-event,
        has id "{vid}",
        has name "{escape_string(args.title)}",
        has ops-meeting-title "{escape_string(args.title)}",
        has created-at {get_timestamp()}'''
    if content:
        query += f', has content "{escape_string(content)}"'
    if args.start:
        query += f', has ops-event-start {parse_date(args.start)}'
    if args.end:
        query += f', has ops-event-end {parse_date(args.end)}'
    if args.uri:
        query += f', has ops-external-uri "{escape_string(args.uri)}"'
    query += ";"
    with get_driver() as driver:
        _link(driver, query)
        attendees = []
        for ident in (args.attendee or []):
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                p = resolve_person(tx, ident)
            if p:
                _link(driver, f'''match $v isa ops-calendar-event, has id "{vid}"; $p isa alh-person, has id "{p['id']}";
                    insert (event: $v, person: $p) isa ops-event-attendee;''')
                attendees.append(p["name"])
        if args.evidence_for:
            _link_evidence(driver, vid, escape_string(args.evidence_for))
    print(json.dumps({"success": True, "event_id": vid, "title": args.title,
                      "attendees": attendees, "evidence_for": args.evidence_for}))


def cmd_link_evidence(args):
    """Link an existing external artifact to a planning element as evidence."""
    with get_driver() as driver:
        _link_evidence(driver, escape_string(args.artifact), escape_string(args.subject))
    print(json.dumps({"success": True, "artifact_id": args.artifact, "subject_id": args.subject}))


# =============================================================================
# TRACKER INTEGRATION (pull-first) — the team manages work in Jira/Monday/GitHub;
# we IMPORT leaf items into ops for personal OKR planning + downstream checking.
# ops.py only stores/queries the reference + mapped status; the AGENT fetches the
# live item via the provider's MCP server and calls these commands to persist.
# =============================================================================

TRACKER_PROVIDERS = ["github", "jira", "monday"]

# Raw tracker status -> ops-workitem-status. Case-insensitive; unknown -> in-progress.
_STATUS_MAP = {
    "github": {"open": "in-progress", "closed": "done", "todo": "not-started",
               "backlog": "not-started", "in progress": "in-progress",
               "in review": "in-progress", "done": "done", "blocked": "blocked"},
    "jira":   {"to do": "not-started", "backlog": "not-started", "new": "not-started",
               "selected for development": "not-started", "in progress": "in-progress",
               "in review": "in-progress", "indeterminate": "in-progress",
               "done": "done", "blocked": "blocked"},
    "monday": {"": "not-started", "not started": "not-started", "working on it": "in-progress",
               "stuck": "blocked", "done": "done"},
}


def map_status(provider, raw):
    """Map a raw tracker status to the ops-workitem-status enum."""
    if raw is None:
        return None
    return _STATUS_MAP.get(provider, {}).get(str(raw).strip().lower(), "in-progress")


def _stored_provider(driver, wid):
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        r = fetch_one(tx, f'match $w isa ops-workitem, has id "{wid}", has ops-external-provider $p; fetch {{ "p": $p }};')
    return r["p"] if r else None


def cmd_import_item(args):
    """Create a NEW work item FROM a tracker item — the pull-into-alhazen path."""
    if not args.kr and not args.parent:
        print(json.dumps({"success": False, "error": "Provide --kr or --parent to attach the imported item"}))
        return
    kind = args.kind or "task"
    status = map_status(args.provider, args.external_status) if args.external_status else "not-started"
    wid = generate_id("workitem")
    q = f'''insert $w isa ops-workitem,
        has id "{wid}",
        has name "{escape_string(args.title)}",
        has ops-workitem-kind "{kind}",
        has ops-workitem-status "{status}",
        has ops-external-provider "{args.provider}",
        has ops-external-uri "{escape_string(args.url)}",
        has ops-last-synced {get_timestamp()}'''
    if args.external_id:
        q += f', has ops-external-id "{escape_string(args.external_id)}"'
    if args.external_status:
        q += f', has ops-external-status "{escape_string(args.external_status)}"'
    q += ";"
    with get_driver() as driver:
        _link(driver, q)
        if args.kr:
            _link(driver, f'''match $k isa ops-key-result, has id "{escape_string(args.kr)}";
                $w isa ops-workitem, has id "{wid}";
            insert (key-result: $k, workitem: $w) isa ops-kr-work;''')
        if args.parent:
            _link(driver, f'''match $p isa ops-workitem, has id "{escape_string(args.parent)}";
                $c isa ops-workitem, has id "{wid}";
            insert (parent: $p, child: $c) isa ops-workitem-tree;''')
    print(json.dumps({"success": True, "workitem_id": wid, "provider": args.provider,
                      "status": status, "uri": args.url, "title": args.title}))


def cmd_link_tracker(args):
    """Attach an EXISTING work item to a tracker item (records the reference; maps status if given)."""
    wid = escape_string(args.workitem)
    mapped = map_status(args.provider, args.external_status) if args.external_status else None
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            replace_attr(tx, "ops-workitem", wid, "ops-external-provider", f'"{args.provider}"')
            replace_attr(tx, "ops-workitem", wid, "ops-external-uri", f'"{escape_string(args.url)}"')
            if args.external_id:
                replace_attr(tx, "ops-workitem", wid, "ops-external-id", f'"{escape_string(args.external_id)}"')
            if args.external_status:
                replace_attr(tx, "ops-workitem", wid, "ops-external-status", f'"{escape_string(args.external_status)}"')
                replace_attr(tx, "ops-workitem", wid, "ops-workitem-status", f'"{mapped}"')
            replace_attr(tx, "ops-workitem", wid, "ops-last-synced", get_timestamp())
            tx.commit()
    print(json.dumps({"success": True, "workitem_id": args.workitem, "provider": args.provider,
                      "uri": args.url, "status": mapped}))


def cmd_sync_status(args):
    """Refresh a linked work item's status from the tracker (a pull)."""
    wid = escape_string(args.workitem)
    with get_driver() as driver:
        provider = args.provider or _stored_provider(driver, wid) or "github"
        mapped = map_status(provider, args.external_status)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            replace_attr(tx, "ops-workitem", wid, "ops-external-status", f'"{escape_string(args.external_status)}"')
            if mapped:
                replace_attr(tx, "ops-workitem", wid, "ops-workitem-status", f'"{mapped}"')
            replace_attr(tx, "ops-workitem", wid, "ops-last-synced", get_timestamp())
            tx.commit()
    print(json.dumps({"success": True, "workitem_id": args.workitem, "provider": provider,
                      "external_status": args.external_status, "status": mapped}))


def cmd_list_tracker_links(args):
    """List work items linked to a tracker (downstream checking / audit)."""
    match = 'match $w isa ops-workitem, has id $id, has name $n, has ops-external-uri $uri'
    if getattr(args, "provider", None):
        match += f', has ops-external-provider "{args.provider}"'
    q = (match + ', has ops-external-provider $prov; fetch { "id": $id, "name": $n, '
         '"provider": $prov, "uri": $uri, "status": $w.ops-workitem-status, '
         '"external_status": $w.ops-external-status, "external_id": $w.ops-external-id, '
         '"last_synced": $w.ops-last-synced };')
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            rows = list(tx.query(q).resolve())
    print(json.dumps({"success": True, "links": rows, "count": len(rows)}, default=str))


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Ops Notebook CLI - briefs, stakeholder CRM, meeting prep, commitments, monitors"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # add-spec
    p = subparsers.add_parser("add-spec", help="Design a recurring brief/report spec")
    p.add_argument("--name", required=True, help="Brief name (e.g. 'Morning cross-project overview')")
    p.add_argument("--cadence", help="Cadence (daily, weekdays, weekly, biweekly, monthly, 'every 3 days')")
    p.add_argument("--sections", help="Sections the brief contains (comma/markdown list)")
    p.add_argument("--sources", help="Where the data comes from (connectors, channels, people)")
    p.add_argument("--dream", help="The unlimited-headcount wish this fulfils (ops-dream-rationale)")
    p.add_argument("--primer", help="Operator's messy brain dump (stored as ops-primer-note)")
    p.add_argument("--description", help="Description")
    p.add_argument("--trial-target", dest="trial_target", type=int,
                   help=f"Manual runs required before promotion (default {DEFAULT_TRIAL_TARGET})")

    # list-specs
    p = subparsers.add_parser("list-specs", help="List brief specs with trial progress")
    p.add_argument("--status", choices=SPEC_STATUSES, help="Filter by spec status")

    # log-brief
    p = subparsers.add_parser("log-brief", help="Log a produced brief instance")
    p.add_argument("--spec", required=True, help="Brief spec ID")
    p.add_argument("--content", help="Brief content (inline markdown)")
    p.add_argument("--content-file", help="Path to file containing the brief")
    p.add_argument("--manual", action="store_true", help="Produced manually (increments trial runs)")
    p.add_argument("--automated", action="store_true",
                   help="Produced by automation (REFUSED while spec is designed/trial)")
    p.add_argument("--date", help="Brief date (YYYY-MM-DD, default today)")

    # list-briefs
    p = subparsers.add_parser("list-briefs", help="List produced brief instances")
    p.add_argument("--spec", help="Filter to one spec ID")
    p.add_argument("--limit", type=int, help="Max briefs to return (default 30)")

    # promote-spec
    p = subparsers.add_parser("promote-spec", help="Promote a spec trial -> active")
    p.add_argument("--spec", required=True, help="Brief spec ID")

    # retire-spec
    p = subparsers.add_parser("retire-spec", help="Retire a spec")
    p.add_argument("--spec", required=True, help="Brief spec ID")

    # add-person
    p = subparsers.add_parser("add-person", help="Find-or-create an alh-person")
    p.add_argument("--name", required=True, help="Person name")
    p.add_argument("--email", help="Email address")
    p.add_argument("--description", help="Description")

    # add-dossier
    p = subparsers.add_parser("add-dossier", help="Create a stakeholder dossier for a person")
    p.add_argument("--person", required=True, help="Person ID or name")
    p.add_argument("--relationship", help="Relationship (e.g. 'board member', 'direct report')")
    p.add_argument("--current-state", dest="current_state", help="Where the relationship stands now")
    p.add_argument("--history", help="How we got here (history summary)")
    p.add_argument("--primer", help="Messy brain dump about this person (stored as primer note)")

    # list-stakeholders
    subparsers.add_parser("list-stakeholders", help="CRM table of all dossiers")

    # show-stakeholder
    p = subparsers.add_parser("show-stakeholder", help="Pre-meeting context pull for a person")
    p.add_argument("--person", required=True, help="Person ID or name")

    # log-touchpoint
    p = subparsers.add_parser("log-touchpoint", help="Log an interaction with the undercurrent")
    p.add_argument("--person", required=True, help="Person ID or name")
    p.add_argument("--content", help="What happened (inline)")
    p.add_argument("--content-file", help="Path to file with the interaction log")
    p.add_argument("--type", help="Interaction type (meeting, call, email, slack, hallway, dinner)")
    p.add_argument("--date", help="Interaction date (YYYY-MM-DD, default now)")
    p.add_argument("--undercurrent", help="What the transcript won't show: mood, hesitation, looks")
    p.add_argument("--commitments-made", dest="commitments_made", help="Raw text of promises made")

    # prep-meeting
    p = subparsers.add_parser("prep-meeting", help="Assemble stakeholder context for a prep pack")
    p.add_argument("--person", required=True, nargs="+", help="Person ID(s) or name(s) attending")
    p.add_argument("--title", help="Meeting title")
    p.add_argument("--date", help="Meeting date (YYYY-MM-DD)")

    # save-prep
    p = subparsers.add_parser("save-prep", help="Store the agent-written prep pack")
    p.add_argument("--person", required=True, nargs="+", help="Person ID(s) or name(s) attending")
    p.add_argument("--title", help="Meeting title")
    p.add_argument("--date", help="Meeting date (YYYY-MM-DD, default now)")
    p.add_argument("--content", help="Prep pack content (inline markdown)")
    p.add_argument("--content-file", help="Path to file with the prep pack")

    # add-commitment
    p = subparsers.add_parser("add-commitment", help="Record who owes what by when")
    p.add_argument("--person", required=True, help="Counterparty person ID or name")
    p.add_argument("--what", required=True, help="What is owed (short name)")
    p.add_argument("--owed-by", dest="owed_by", required=True, choices=["me", "them"],
                   help="Who owes it: me or them")
    p.add_argument("--due", help="Due date (YYYY-MM-DD)")
    p.add_argument("--description", help="Details")
    p.add_argument("--from-touchpoint", dest="from_touchpoint",
                   help="Touchpoint ID this was harvested from (recorded as provenance)")

    # update-commitment
    p = subparsers.add_parser("update-commitment", help="Update a commitment")
    p.add_argument("--id", required=True, help="Commitment ID")
    p.add_argument("--status", choices=COMMITMENT_STATUSES, help="New status")
    p.add_argument("--due", help="New due date (YYYY-MM-DD)")

    # list-commitments
    p = subparsers.add_parser("list-commitments", help="List commitments")
    p.add_argument("--due", help="Only commitments due on/before this date (YYYY-MM-DD)")
    p.add_argument("--owed-by", dest="owed_by", choices=["me", "them"], help="Filter by direction")
    p.add_argument("--status", choices=COMMITMENT_STATUSES, help="Filter by status")
    p.add_argument("--person", help="Filter by person ID or name")

    # add-monitor
    p = subparsers.add_parser("add-monitor", help="Add a standing visibility question")
    p.add_argument("--question", required=True, help="The question this monitor answers")
    p.add_argument("--sources", help="Where to look (channels, dashboards, people)")
    p.add_argument("--name", help="Short name (default: question prefix)")
    p.add_argument("--status", choices=MONITOR_STATUSES, default="active", help="Initial status")

    # list-monitors
    p = subparsers.add_parser("list-monitors", help="List monitors")
    p.add_argument("--status", choices=MONITOR_STATUSES, help="Filter by status")

    # update-monitor
    p = subparsers.add_parser("update-monitor", help="Update monitor status / mark checked")
    p.add_argument("--id", required=True, help="Monitor ID")
    p.add_argument("--status", choices=MONITOR_STATUSES, help="New status")
    p.add_argument("--checked", action="store_true", help="Mark checked now (sets ops-last-checked)")

    # today
    subparsers.add_parser("today", help="JSON morning snapshot")

    # report-today
    subparsers.add_parser("report-today", help="Markdown morning brief")

    # add-note
    p = subparsers.add_parser("add-note", help="Attach a note to any ops entity")
    p.add_argument("--about", required=True, help="Entity ID this note is about")
    p.add_argument("--type", required=True, choices=["primer", "interview", "general"], help="Note type")
    p.add_argument("--content", help="Note content (inline)")
    p.add_argument("--content-file", help="Path to file containing note content")
    p.add_argument("--name", help="Note title")

    # audit
    subparsers.add_parser("audit", help="Run quality checks from quality-checks.yaml")

    # --- OKR spine (plans live in ops; objectives are the primary element) ---
    p = subparsers.add_parser("add-objective", help="Create an objective (primary planning element)")
    p.add_argument("--name", required=True, help="Objective statement")
    p.add_argument("--description", help="Longer description")
    p.add_argument("--period", help="Timeframe, e.g. 2026-Q4 or first-90-days")
    p.add_argument("--status", choices=OBJECTIVE_STATUSES, help="Status (default draft)")
    p.add_argument("--owner", help="Accountable person (id or name)")
    p.add_argument("--serves", help="Optional subject id this objective serves (e.g. a career-project)")
    p.add_argument("--primer", help="Operator's messy brain dump, stored as a primer note")

    p = subparsers.add_parser("add-kr", help="Add a measurable key result under an objective")
    p.add_argument("--objective", required=True, help="Objective ID")
    p.add_argument("--name", required=True, help="Key result statement")
    p.add_argument("--metric", help="Measurable definition-of-done")
    p.add_argument("--baseline", help="Starting value")
    p.add_argument("--current", help="Latest observed value")
    p.add_argument("--status", choices=KR_STATUSES, help="Status (default on-track)")
    p.add_argument("--target-date", help="Target date (YYYY-MM-DD)")
    p.add_argument("--owner", help="Accountable person (id or name)")

    p = subparsers.add_parser("add-workitem", help="Add a story/task/subtask under a KR or work item")
    p.add_argument("--kind", required=True, choices=WORKITEM_KINDS, help="story | task | subtask")
    p.add_argument("--name", required=True, help="Work item title")
    p.add_argument("--description", help="Longer description")
    p.add_argument("--kr", help="Parent key result ID (for a root work item)")
    p.add_argument("--parent", help="Parent work item ID (for nesting)")
    p.add_argument("--status", choices=WORKITEM_STATUSES, help="Status (default not-started)")
    p.add_argument("--owner", help="Accountable person (id or name)")
    p.add_argument("--target-date", help="Target date (YYYY-MM-DD)")
    p.add_argument("--order", type=int, help="Sibling ordering")

    p = subparsers.add_parser("update-objective", help="Update an objective")
    p.add_argument("--id", required=True)
    p.add_argument("--status", choices=OBJECTIVE_STATUSES)
    p.add_argument("--period")
    p.add_argument("--name")

    p = subparsers.add_parser("update-kr", help="Update a key result")
    p.add_argument("--id", required=True)
    p.add_argument("--current")
    p.add_argument("--status", choices=KR_STATUSES)
    p.add_argument("--target-date")

    p = subparsers.add_parser("update-workitem", help="Update a work item")
    p.add_argument("--id", required=True)
    p.add_argument("--status", choices=WORKITEM_STATUSES)
    p.add_argument("--name")
    p.add_argument("--target-date")

    p = subparsers.add_parser("link-commitment", help="Bridge a work item to an ops-commitment")
    p.add_argument("--workitem", required=True)
    p.add_argument("--commitment", required=True)

    p = subparsers.add_parser("show-tree", help="Render objective -> KRs -> work items with rolled-up progress")
    p.add_argument("--objective", required=True)

    p = subparsers.add_parser("list-objectives", help="List objectives")
    p.add_argument("--status", choices=OBJECTIVE_STATUSES)
    p.add_argument("--serves", help="Filter to objectives serving this subject id")

    # --- External data as artifacts (emails, calendar meetings, docs) ---
    p = subparsers.add_parser("add-email", help="Capture an email as an artifact")
    p.add_argument("--subject", required=True, help="Email subject (name)")
    p.add_argument("--sent-at", help="Sent date (YYYY-MM-DD)")
    p.add_argument("--content", help="Email body (inline)")
    p.add_argument("--content-file", help="Path to file with the email body")
    p.add_argument("--uri", help="Source URI / message-id")
    p.add_argument("--party", nargs="*", help="Correspondent person id(s) or name(s)")
    p.add_argument("--evidence-for", help="Planning element id this email is evidence for")

    p = subparsers.add_parser("add-event", help="Capture a calendar meeting as an artifact")
    p.add_argument("--title", required=True, help="Meeting title (name)")
    p.add_argument("--start", help="Start (YYYY-MM-DD)")
    p.add_argument("--end", help="End (YYYY-MM-DD)")
    p.add_argument("--content", help="Notes/agenda (inline)")
    p.add_argument("--content-file", help="Path to file with agenda/notes")
    p.add_argument("--uri", help="Source URI / event-id")
    p.add_argument("--attendee", nargs="*", help="Attendee person id(s) or name(s)")
    p.add_argument("--evidence-for", help="Planning element id this meeting is evidence for")

    p = subparsers.add_parser("link-evidence", help="Link an external artifact to a planning element")
    p.add_argument("--artifact", required=True)
    p.add_argument("--subject", required=True)

    # --- Tracker integration (pull-first: import from Jira/Monday/GitHub) ---
    p = subparsers.add_parser("import-item", help="Create a work item FROM a tracker item (pull into alhazen)")
    p.add_argument("--provider", required=True, choices=TRACKER_PROVIDERS)
    p.add_argument("--url", required=True, help="Tracker item URL")
    p.add_argument("--title", required=True, help="Item title")
    p.add_argument("--external-id", help="Tracker id (issue node-id / key / item-id)")
    p.add_argument("--external-status", help="Raw status from the tracker")
    p.add_argument("--kind", choices=WORKITEM_KINDS, help="story|task|subtask (default task)")
    p.add_argument("--kr", help="Attach under this key result")
    p.add_argument("--parent", help="Attach under this work item")

    p = subparsers.add_parser("link-tracker", help="Link an existing work item to a tracker item")
    p.add_argument("--workitem", required=True)
    p.add_argument("--provider", required=True, choices=TRACKER_PROVIDERS)
    p.add_argument("--url", required=True)
    p.add_argument("--external-id")
    p.add_argument("--external-status")

    p = subparsers.add_parser("sync-status", help="Refresh a linked work item's status from the tracker")
    p.add_argument("--workitem", required=True)
    p.add_argument("--external-status", required=True, help="Raw status pulled from the tracker")
    p.add_argument("--provider", choices=TRACKER_PROVIDERS, help="Override; else uses the stored provider")

    p = subparsers.add_parser("list-tracker-links", help="List work items linked to a tracker")
    p.add_argument("--provider", choices=TRACKER_PROVIDERS)

    args = parser.parse_args()

    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        sys.exit(1)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        # Brief lifecycle
        "add-spec": cmd_add_spec,
        "list-specs": cmd_list_specs,
        "log-brief": cmd_log_brief,
        "list-briefs": cmd_list_briefs,
        "promote-spec": cmd_promote_spec,
        "retire-spec": cmd_retire_spec,
        # Stakeholder CRM
        "add-person": cmd_add_person,
        "add-dossier": cmd_add_dossier,
        "list-stakeholders": cmd_list_stakeholders,
        "show-stakeholder": cmd_show_stakeholder,
        "log-touchpoint": cmd_log_touchpoint,
        "prep-meeting": cmd_prep_meeting,
        "save-prep": cmd_save_prep,
        # Commitments
        "add-commitment": cmd_add_commitment,
        "update-commitment": cmd_update_commitment,
        "list-commitments": cmd_list_commitments,
        # Monitors
        "add-monitor": cmd_add_monitor,
        "list-monitors": cmd_list_monitors,
        "update-monitor": cmd_update_monitor,
        # Synthesis
        "today": cmd_today,
        "report-today": cmd_report_today,
        "add-note": cmd_add_note,
        "audit": cmd_audit,
        # OKR spine (plans live in ops; objectives are the primary element)
        "add-objective": cmd_add_objective,
        "add-kr": cmd_add_kr,
        "add-workitem": cmd_add_workitem,
        "update-objective": cmd_update_objective,
        "update-kr": cmd_update_kr,
        "update-workitem": cmd_update_workitem,
        "link-commitment": cmd_link_commitment,
        "show-tree": cmd_show_tree,
        "list-objectives": cmd_list_objectives,
        # External data as artifacts
        "add-email": cmd_add_email,
        "add-event": cmd_add_event,
        "link-evidence": cmd_link_evidence,
        # Tracker integration (pull-first)
        "import-item": cmd_import_item,
        "link-tracker": cmd_link_tracker,
        "sync-status": cmd_sync_status,
        "list-tracker-links": cmd_list_tracker_links,
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
