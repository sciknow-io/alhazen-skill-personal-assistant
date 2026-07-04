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
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alh_personal")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")

SPEC_STATUSES = ["designed", "trial", "active", "retired"]
COMMITMENT_STATUSES = ["open", "done", "dropped", "overdue"]
MONITOR_STATUSES = ["active", "paused", "retired"]
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
