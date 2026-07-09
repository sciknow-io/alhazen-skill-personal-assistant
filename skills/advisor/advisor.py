#!/usr/bin/env python3
"""
Advisor CLI - Board of advisors, decision workflow, bias checks, scenario
stress-tests, and the decision journal.

This script handles STORAGE and QUERIES. Claude handles SENSEMAKING (writing
takes in each advisor's voice, running the debate, surfacing biases) via SKILL.md.

Usage:
    uv run python skills/advisor/advisor.py <command> [options]

Commands:
    # Board management
    add-advisor         Add a persona seat to the board
    list-advisors       List board seats (active by default)
    retire-advisor      Retire a seat (kept for history, excluded from debates)

    # Personal context system
    add-context         Add a context doc (role, company, ecosystem, ...)
    list-context        List context docs (optionally by kind)

    # Decision workflow
    open-decision       Open a decision (stores the primer brain dump)
    add-note            Attach a note (interview, primer, general) to any entity
    add-take            Store one advisor's independent take
    add-debate          Store the challenge-then-converge debate synthesis
    add-bias-check      Store the bias check note (moves decision to 'deciding')
    add-scenario        Store a scenario stress-test for a decision
    decide              Record the outcome + journal note + review date
    review-decision     Close the loop on the review date

    # Queries & reports
    list-decisions      List decisions (--status, --stakes, --review-due, --journal)
    show-decision       Full detail: takes, debate, bias check, scenarios, journal
    report-decision     Markdown report for one decision
    report-board        Markdown report of the board roster + decision stats
    audit               Run declarative quality checks from quality-checks.yaml

Examples:
    uv run python skills/advisor/advisor.py add-advisor \
        --name "The Operator" --archetype operator \
        --decision-style "execution-first" --pushback firm \
        --inspiration "My first COO mentor" \
        --charter "Can we actually execute this with the team we have?"

    uv run python skills/advisor/advisor.py open-decision \
        --question "Do we enter the EU market next quarter?" \
        --stakes high --operator-style pushback-then-space \
        --primer "Messy brain dump text..."

    uv run python skills/advisor/advisor.py list-decisions --review-due

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

try:
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False
    print(
        "Warning: pyyaml not installed. Install with: pip install 'pyyaml>=6.0.0'",
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

DEFAULT_BOARD_NAME = "Board of Advisors"

DECISION_STATUSES = ["framing", "debating", "deciding", "decided", "reviewed"]
STAKES_LEVELS = ["low", "medium", "high", "irreversible"]
PUSHBACK_LEVELS = ["gentle", "firm", "relentless"]
CONTEXT_KINDS = ["role", "company", "ecosystem", "competitive-stance", "priorities", "past-decision"]


def get_driver():
    """Get TypeDB driver connection."""
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
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
    # If no format works, assume it's already in correct format
    return date_str


def resolve_content(args, attr="content", file_attr="content_file"):
    """Resolve content from --content or --content-file. Mutually exclusive."""
    if getattr(args, file_attr, None):
        with open(getattr(args, file_attr), "r") as f:
            return f.read()
    return getattr(args, attr, None)


def fail(message: str):
    """Print an error JSON object and return."""
    print(json.dumps({"success": False, "error": message}))


def entity_exists(tx, entity_type: str, entity_id: str) -> bool:
    """Check whether an entity of the given type with the given id exists."""
    results = list(tx.query(
        f'match $e isa {entity_type}, has id "{escape_string(entity_id)}"; '
        f'fetch {{ "id": $e.id }};'
    ).resolve())
    return bool(results)


def replace_attr(driver, entity_type: str, entity_id: str, attr: str, value: str, quote=True):
    """Replace a single-valued attribute on an entity (delete old, insert new)."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        try:
            tx.query(
                f'match $e isa {entity_type}, has id "{escape_string(entity_id)}", '
                f'has {attr} $old; delete has $old of $e;'
            ).resolve()
        except Exception:
            pass
        val = f'"{escape_string(value)}"' if quote else value
        tx.query(
            f'match $e isa {entity_type}, has id "{escape_string(entity_id)}"; '
            f'insert $e has {attr} {val};'
        ).resolve()
        tx.commit()


def insert_note(driver, note_type: str, content: str, about_id: str,
                name: str = None, extra_attr_clauses: str = "") -> str:
    """Insert a note of the given type and link it to a subject via alh-aboutness."""
    note_id = generate_id("note")
    timestamp = get_timestamp()

    query = f'''insert $n isa {note_type},
        has id "{note_id}",
        has content "{escape_string(content)}",
        has created-at {timestamp}'''
    if name:
        query += f', has name "{escape_string(name)}"'
    query += extra_attr_clauses
    query += ";"

    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(query).resolve()
        tx.commit()

    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(f'''match
            $n isa alh-note, has id "{note_id}";
            $s isa alh-identifiable-entity, has id "{escape_string(about_id)}";
        insert (note: $n, subject: $s) isa alh-aboutness;''').resolve()
        tx.commit()

    return note_id


def get_decision_status(driver, decision_id: str):
    """Return the current decision status, or None if decision not found."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        results = list(tx.query(f'''match
            $d isa advsr-decision, has id "{escape_string(decision_id)}";
        fetch {{ "status": $d.advsr-decision-status }};''').resolve())
    if not results:
        return None
    return results[0].get("status") or "framing"


def advance_status(driver, decision_id: str, new_status: str, only_from=None):
    """Move a decision to new_status. If only_from is given, only advance when
    the current status is in that list. Returns the resulting status."""
    current = get_decision_status(driver, decision_id)
    if current is None:
        return None
    if only_from is not None and current not in only_from:
        return current
    replace_attr(driver, "advsr-decision", decision_id, "advsr-decision-status", new_status)
    return new_status


def find_or_create_board(driver, board_name: str) -> str:
    """Find a board by name (case-insensitive) or create it. Returns its id."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        existing = list(tx.query(
            'match $b isa advsr-board, has id $bid, has name $bn; '
            'fetch { "id": $bid, "name": $bn };'
        ).resolve())
    for b in existing:
        if b["name"].lower() == board_name.lower():
            return b["id"]

    board_id = generate_id("board")
    timestamp = get_timestamp()
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(f'''insert $b isa advsr-board,
            has id "{board_id}",
            has name "{escape_string(board_name)}",
            has created-at {timestamp};''').resolve()
        tx.commit()
    return board_id


# =============================================================================
# BOARD MANAGEMENT COMMANDS
# =============================================================================


def cmd_add_advisor(args):
    """Add a persona seat to the board."""
    advisor_id = args.id or generate_id("advisor")
    timestamp = get_timestamp()

    query = f'''insert $a isa advsr-advisor,
        has id "{advisor_id}",
        has name "{escape_string(args.name)}",
        has advsr-seat-status "active",
        has created-at {timestamp}'''

    if args.archetype:
        query += f', has advsr-archetype "{escape_string(args.archetype)}"'
    if args.decision_style:
        query += f', has advsr-decision-style "{escape_string(args.decision_style)}"'
    if args.pushback:
        query += f', has advsr-pushback-level "{args.pushback}"'
    if args.inspiration:
        query += f', has advsr-inspiration "{escape_string(args.inspiration)}"'
    if args.charter:
        query += f', has advsr-charter "{escape_string(args.charter)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Seat the advisor on the board (find-or-create by name)
        board_id = find_or_create_board(driver, args.board or DEFAULT_BOARD_NAME)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $a isa advsr-advisor, has id "{advisor_id}";
                $b isa advsr-board, has id "{board_id}";
            insert (advisor: $a, board: $b) isa advsr-seat-on-board;''').resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "advisor_id": advisor_id,
        "name": args.name,
        "board_id": board_id,
    }))


def _fetch_advisors(tx):
    """Fetch all advisors with their attributes and board name."""
    advisors = list(tx.query('''match $a isa advsr-advisor, has id $id, has name $n;
    fetch {
        "id": $id,
        "name": $n,
        "archetype": $a.advsr-archetype,
        "decision_style": $a.advsr-decision-style,
        "pushback": $a.advsr-pushback-level,
        "inspiration": $a.advsr-inspiration,
        "charter": $a.advsr-charter,
        "status": $a.advsr-seat-status,
        "created_at": $a.created-at
    };''').resolve())

    boards = {}
    try:
        for row in tx.query('''match
            $a isa advsr-advisor, has id $aid;
            (advisor: $a, board: $b) isa advsr-seat-on-board;
        fetch { "advisor_id": $aid, "board": $b.name, "board_id": $b.id };''').resolve():
            boards[row["advisor_id"]] = {"board": row["board"], "board_id": row["board_id"]}
    except Exception:
        pass

    for a in advisors:
        a["status"] = a.get("status") or "active"
        b = boards.get(a["id"])
        if b:
            a.update(b)
    return advisors


def cmd_list_advisors(args):
    """List board seats (active by default)."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            advisors = _fetch_advisors(tx)

    if not args.include_retired:
        advisors = [a for a in advisors if a.get("status") != "retired"]

    advisors.sort(key=lambda a: str(a.get("created_at") or ""))
    print(json.dumps({"success": True, "advisors": advisors, "count": len(advisors)}, default=str))


def cmd_retire_advisor(args):
    """Retire a seat: kept for history, excluded from future debates."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not entity_exists(tx, "advsr-advisor", args.id):
                fail(f"Advisor not found: {args.id}")
                return
        replace_attr(driver, "advsr-advisor", args.id, "advsr-seat-status", "retired")

    print(json.dumps({"success": True, "advisor_id": args.id, "status": "retired"}))


# =============================================================================
# PERSONAL CONTEXT SYSTEM COMMANDS
# =============================================================================


def cmd_add_context(args):
    """Add a context doc to the personal context system."""
    content = resolve_content(args)
    if not content:
        fail("Provide either --content or --content-file")
        return

    context_id = args.id or generate_id("context")
    timestamp = get_timestamp()

    query = f'''insert $c isa advsr-context-doc,
        has id "{context_id}",
        has name "{escape_string(args.name)}",
        has advsr-context-kind "{escape_string(args.kind)}",
        has content "{escape_string(content)}",
        has created-at {timestamp}'''
    if args.description:
        query += f', has description "{escape_string(args.description)}"'
    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "context_id": context_id,
        "name": args.name,
        "kind": args.kind,
    }))


def cmd_list_context(args):
    """List context docs, optionally filtered by kind."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            docs = list(tx.query('''match $c isa advsr-context-doc, has id $id, has name $n;
            fetch {
                "id": $id,
                "name": $n,
                "kind": $c.advsr-context-kind,
                "description": $c.description,
                "content": $c.content,
                "created_at": $c.created-at
            };''').resolve())

    if args.kind:
        docs = [d for d in docs if (d.get("kind") or "") == args.kind]
    if not args.full:
        for d in docs:
            content = d.get("content") or ""
            if len(content) > 200:
                d["content"] = content[:200] + "..."

    docs.sort(key=lambda d: (str(d.get("kind") or ""), str(d.get("name") or "")))
    print(json.dumps({"success": True, "context_docs": docs, "count": len(docs)}, default=str))


# =============================================================================
# DECISION WORKFLOW COMMANDS
# =============================================================================


def cmd_open_decision(args):
    """Open a decision in 'framing' status and store the primer brain dump."""
    primer = resolve_content(args, attr="primer", file_attr="primer_file")

    decision_id = args.id or generate_id("decision")
    timestamp = get_timestamp()
    name = args.name or (args.question if len(args.question) <= 80 else args.question[:77] + "...")

    query = f'''insert $d isa advsr-decision,
        has id "{decision_id}",
        has name "{escape_string(name)}",
        has advsr-question "{escape_string(args.question)}",
        has advsr-decision-status "framing",
        has created-at {timestamp}'''
    if args.stakes:
        query += f', has advsr-stakes "{args.stakes}"'
    if args.operator_style:
        query += f', has advsr-operator-style "{escape_string(args.operator_style)}"'
    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        primer_note_id = None
        if primer:
            primer_note_id = insert_note(
                driver, "advsr-primer-note", primer, decision_id, name="Primer")

    output = {
        "success": True,
        "decision_id": decision_id,
        "question": args.question,
        "status": "framing",
        "stakes": args.stakes,
    }
    if primer_note_id:
        output["primer_note_id"] = primer_note_id
    else:
        output["warning"] = ("No primer captured. Operating principle: always store the "
                             "operator's messy brain dump at open time (--primer / --primer-file).")
    print(json.dumps(output))


def cmd_add_note(args):
    """Attach a note (interview, primer, debate, bias, journal, general) to any entity."""
    content = resolve_content(args)
    if not content:
        fail("Provide either --content or --content-file")
        return

    type_map = {
        "primer": "advsr-primer-note",
        "interview": "advsr-interview-note",
        "debate": "advsr-debate-note",
        "bias": "advsr-bias-note",
        "journal": "advsr-journal-note",
        "general": "note",
    }
    note_type = type_map.get(args.type, "note")

    with get_driver() as driver:
        note_id = insert_note(driver, note_type, content, args.about, name=args.name)

    print(json.dumps({"success": True, "note_id": note_id, "about": args.about, "type": args.type}))


def cmd_add_take(args):
    """Store one advisor's independent take on a decision."""
    content = resolve_content(args)
    if not content:
        fail("Provide either --content or --content-file")
        return

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not entity_exists(tx, "advsr-decision", args.decision):
                fail(f"Decision not found: {args.decision}")
                return
            advisor_rows = list(tx.query(f'''match
                $a isa advsr-advisor, has id "{escape_string(args.advisor)}", has name $n;
            fetch {{ "name": $n, "status": $a.advsr-seat-status }};''').resolve())
            if not advisor_rows:
                fail(f"Advisor not found: {args.advisor}")
                return

        extra = ""
        if args.stance:
            extra = f', has advsr-stance "{escape_string(args.stance)}"'
        note_id = insert_note(
            driver, "advsr-take-note", content, args.decision,
            name=f"Take: {advisor_rows[0]['name']}", extra_attr_clauses=extra)

        # Attribute the take to its advisor
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $t isa advsr-take-note, has id "{note_id}";
                $a isa advsr-advisor, has id "{escape_string(args.advisor)}";
            insert (take: $t, advisor: $a) isa advsr-take-by;''').resolve()
            tx.commit()

        # First take moves the decision from framing to debating
        status = advance_status(driver, args.decision, "debating", only_from=["framing"])

    output = {
        "success": True,
        "take_note_id": note_id,
        "decision_id": args.decision,
        "advisor_id": args.advisor,
        "advisor": advisor_rows[0]["name"],
        "stance": args.stance,
        "decision_status": status,
    }
    if advisor_rows[0].get("status") == "retired":
        output["warning"] = "This advisor seat is retired."
    print(json.dumps(output))


def cmd_add_debate(args):
    """Store the challenge-then-converge debate synthesis for a decision."""
    content = resolve_content(args)
    if not content:
        fail("Provide either --content or --content-file")
        return

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not entity_exists(tx, "advsr-decision", args.decision):
                fail(f"Decision not found: {args.decision}")
                return
        note_id = insert_note(driver, "advsr-debate-note", content, args.decision, name="Debate")
        status = advance_status(driver, args.decision, "debating", only_from=["framing"])

    print(json.dumps({
        "success": True,
        "debate_note_id": note_id,
        "decision_id": args.decision,
        "decision_status": status,
    }))


def cmd_add_bias_check(args):
    """Store the bias check note; moves the decision to 'deciding'."""
    content = resolve_content(args)
    if not content:
        fail("Provide either --content or --content-file")
        return

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not entity_exists(tx, "advsr-decision", args.decision):
                fail(f"Decision not found: {args.decision}")
                return
        note_id = insert_note(driver, "advsr-bias-note", content, args.decision, name="Bias Check")
        status = advance_status(
            driver, args.decision, "deciding", only_from=["framing", "debating"])

    print(json.dumps({
        "success": True,
        "bias_note_id": note_id,
        "decision_id": args.decision,
        "decision_status": status,
    }))


def cmd_add_scenario(args):
    """Store a scenario stress-test for a decision."""
    scenario_id = args.id or generate_id("scenario")
    timestamp = get_timestamp()

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not entity_exists(tx, "advsr-decision", args.decision):
                fail(f"Decision not found: {args.decision}")
                return

        name = args.condition if len(args.condition) <= 80 else args.condition[:77] + "..."
        query = f'''insert $s isa advsr-scenario,
            has id "{scenario_id}",
            has name "{escape_string(name)}",
            has advsr-scenario-condition "{escape_string(args.condition)}",
            has created-at {timestamp}'''
        if args.impact:
            query += f', has advsr-scenario-impact "{escape_string(args.impact)}"'
        if args.likelihood:
            query += f', has advsr-scenario-likelihood "{args.likelihood}"'
        query += ";"

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $s isa advsr-scenario, has id "{scenario_id}";
                $d isa advsr-decision, has id "{escape_string(args.decision)}";
            insert (scenario: $s, decision: $d) isa advsr-scenario-for;''').resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "scenario_id": scenario_id,
        "decision_id": args.decision,
        "condition": args.condition,
        "likelihood": args.likelihood,
    }))


def cmd_decide(args):
    """Record the operator's decision: outcome + journal note + review date."""
    journal = resolve_content(args, attr="journal", file_attr="journal_file")

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not entity_exists(tx, "advsr-decision", args.decision):
                fail(f"Decision not found: {args.decision}")
                return

        replace_attr(driver, "advsr-decision", args.decision, "advsr-outcome", args.outcome)
        replace_attr(driver, "advsr-decision", args.decision,
                     "advsr-decision-status", "decided")

        review_date = None
        if args.review_date:
            review_date = parse_date(args.review_date)
            replace_attr(driver, "advsr-decision", args.decision,
                         "advsr-review-date", review_date, quote=False)

        journal_note_id = None
        if journal:
            journal_note_id = insert_note(
                driver, "advsr-journal-note", journal, args.decision, name="Decision Journal")

    output = {
        "success": True,
        "decision_id": args.decision,
        "status": "decided",
        "outcome": args.outcome,
        "review_date": review_date,
    }
    if journal_note_id:
        output["journal_note_id"] = journal_note_id
    else:
        output["warning"] = ("No journal entry stored. Record what was decided, why, and what "
                             "you expect to happen (--journal / --journal-file).")
    if not review_date:
        output.setdefault("warning", "")
        output["warning"] = (output["warning"] + " No review date set: the loop never closes "
                             "without one (--review-date YYYY-MM-DD).").strip()
    print(json.dumps(output))


def cmd_review_decision(args):
    """Close the loop: what happened vs expected. Marks the decision 'reviewed'."""
    content = resolve_content(args)
    if not content:
        fail("Provide either --content or --content-file (what happened vs what you expected)")
        return

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not entity_exists(tx, "advsr-decision", args.decision):
                fail(f"Decision not found: {args.decision}")
                return
        note_id = insert_note(
            driver, "advsr-journal-note", content, args.decision, name="Review")
        replace_attr(driver, "advsr-decision", args.decision,
                     "advsr-decision-status", "reviewed")

    print(json.dumps({
        "success": True,
        "review_note_id": note_id,
        "decision_id": args.decision,
        "status": "reviewed",
        "next": ("Feed what you learned back into the context system: "
                 "add-context --kind past-decision"),
    }))


# =============================================================================
# QUERY COMMANDS
# =============================================================================


def _fetch_decisions(tx):
    """Fetch all decisions with their attributes."""
    return list(tx.query('''match $d isa advsr-decision, has id $id, has name $n;
    fetch {
        "id": $id,
        "name": $n,
        "question": $d.advsr-question,
        "status": $d.advsr-decision-status,
        "stakes": $d.advsr-stakes,
        "operator_style": $d.advsr-operator-style,
        "outcome": $d.advsr-outcome,
        "review_date": $d.advsr-review-date,
        "created_at": $d.created-at
    };''').resolve())


def _is_review_due(decision) -> bool:
    """A decided (not yet reviewed) decision whose review date has passed."""
    if (decision.get("status") or "") != "decided":
        return False
    rd = decision.get("review_date")
    if not rd:
        return False
    try:
        due = datetime.fromisoformat(str(rd).replace("Z", ""))
        return due <= datetime.now()
    except ValueError:
        return False


def cmd_list_decisions(args):
    """List decisions with optional filters."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            decisions = _fetch_decisions(tx)

    if args.status:
        decisions = [d for d in decisions if (d.get("status") or "") == args.status]
    if args.stakes:
        decisions = [d for d in decisions if (d.get("stakes") or "") == args.stakes]
    if args.journal:
        decisions = [d for d in decisions if (d.get("status") or "") in ("decided", "reviewed")]
    if args.review_due:
        decisions = [d for d in decisions if _is_review_due(d)]
    else:
        for d in decisions:
            d["review_due"] = _is_review_due(d)

    decisions.sort(key=lambda d: str(d.get("created_at") or ""), reverse=True)
    print(json.dumps({"success": True, "decisions": decisions, "count": len(decisions)}, default=str))


NOTE_TYPES = [
    ("advsr-primer-note", "primer"),
    ("advsr-interview-note", "interview"),
    ("advsr-debate-note", "debate"),
    ("advsr-bias-note", "bias_check"),
    ("advsr-journal-note", "journal"),
]


def _fetch_decision_detail(tx, decision_id: str):
    """Fetch full decision detail: attrs, notes, takes, scenarios."""
    rows = list(tx.query(f'''match $d isa advsr-decision, has id "{escape_string(decision_id)}";
    fetch {{
        "id": $d.id,
        "name": $d.name,
        "question": $d.advsr-question,
        "status": $d.advsr-decision-status,
        "stakes": $d.advsr-stakes,
        "operator_style": $d.advsr-operator-style,
        "outcome": $d.advsr-outcome,
        "review_date": $d.advsr-review-date,
        "created_at": $d.created-at
    }};''').resolve())
    if not rows:
        return None
    decision = rows[0]
    decision["review_due"] = _is_review_due(decision)

    # Notes grouped by type
    notes = {}
    for ntype, label in NOTE_TYPES:
        try:
            results = list(tx.query(f'''match
                $d isa advsr-decision, has id "{escape_string(decision_id)}";
                (note: $n, subject: $d) isa alh-aboutness;
                $n isa {ntype};
            fetch {{ "id": $n.id, "name": $n.name, "content": $n.content,
                     "created_at": $n.created-at }};''').resolve())
            if results:
                results.sort(key=lambda r: str(r.get("created_at") or ""))
                notes[label] = results
        except Exception:
            pass

    # Takes with advisor attribution
    takes = []
    try:
        takes = list(tx.query(f'''match
            $d isa advsr-decision, has id "{escape_string(decision_id)}";
            (note: $t, subject: $d) isa alh-aboutness;
            $t isa advsr-take-note;
            (take: $t, advisor: $a) isa advsr-take-by;
        fetch {{ "id": $t.id, "content": $t.content, "stance": $t.advsr-stance,
                 "created_at": $t.created-at,
                 "advisor_id": $a.id, "advisor": $a.name,
                 "archetype": $a.advsr-archetype,
                 "pushback": $a.advsr-pushback-level }};''').resolve())
        takes.sort(key=lambda r: str(r.get("created_at") or ""))
    except Exception:
        pass

    # Scenario stress-tests
    scenarios = []
    try:
        scenarios = list(tx.query(f'''match
            $d isa advsr-decision, has id "{escape_string(decision_id)}";
            (scenario: $s, decision: $d) isa advsr-scenario-for;
        fetch {{ "id": $s.id,
                 "condition": $s.advsr-scenario-condition,
                 "impact": $s.advsr-scenario-impact,
                 "likelihood": $s.advsr-scenario-likelihood,
                 "created_at": $s.created-at }};''').resolve())
        scenarios.sort(key=lambda r: str(r.get("created_at") or ""))
    except Exception:
        pass

    return {"decision": decision, "notes": notes, "takes": takes, "scenarios": scenarios}


def cmd_show_decision(args):
    """Show full decision detail: all takes, notes, and scenarios."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            detail = _fetch_decision_detail(tx, args.id)

    if detail is None:
        fail(f"Decision not found: {args.id}")
        return

    detail["success"] = True
    print(json.dumps(detail, default=str))


# =============================================================================
# REPORT COMMANDS (Markdown output for human display)
# =============================================================================


def _unescape_md(s):
    return str(s or "").replace("\\n", "\n")


def cmd_report_decision(args):
    """Markdown report for one decision."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            detail = _fetch_decision_detail(tx, args.id)

    if detail is None:
        print(f"Decision not found: {args.id}")
        return

    d = detail["decision"]
    lines = [f"# Decision: {d.get('name')}", ""]
    lines.append(f"**Question:** {d.get('question') or '—'}")
    lines.append(f"**Status:** {d.get('status') or 'framing'}  |  "
                 f"**Stakes:** {d.get('stakes') or '—'}  |  "
                 f"**Operator style:** {d.get('operator_style') or '—'}")
    if d.get("outcome"):
        lines.append(f"**Outcome:** {d['outcome']}")
    if d.get("review_date"):
        due = "  (REVIEW DUE)" if d.get("review_due") else ""
        lines.append(f"**Review date:** {d['review_date']}{due}")
    lines.append("")

    for label, heading in [("primer", "Primer"), ("interview", "Interview")]:
        for n in detail["notes"].get(label, []):
            lines += [f"## {heading}", "", _unescape_md(n.get("content")), ""]

    if detail["takes"]:
        lines.append("## Independent Takes")
        lines.append("")
        for t in detail["takes"]:
            stance = f" — *{t['stance']}*" if t.get("stance") else ""
            lines.append(f"### {t.get('advisor')} ({t.get('archetype') or 'advisor'}){stance}")
            lines.append("")
            lines.append(_unescape_md(t.get("content")))
            lines.append("")

    for label, heading in [("debate", "Debate (challenge → converge)"),
                           ("bias_check", "Bias Check")]:
        for n in detail["notes"].get(label, []):
            lines += [f"## {heading}", "", _unescape_md(n.get("content")), ""]

    if detail["scenarios"]:
        lines.append("## Scenario Stress-Tests")
        lines.append("")
        lines.append("| Condition | Likelihood | Impact |")
        lines.append("|---|---|---|")
        for s in detail["scenarios"]:
            lines.append(f"| {s.get('condition') or ''} | {s.get('likelihood') or ''} "
                         f"| {s.get('impact') or ''} |")
        lines.append("")

    journal = detail["notes"].get("journal", [])
    if journal:
        lines.append("## Journal")
        lines.append("")
        for n in journal:
            lines.append(f"### {n.get('name') or 'Entry'} ({n.get('created_at')})")
            lines.append("")
            lines.append(_unescape_md(n.get("content")))
            lines.append("")

    print("\n".join(lines))


def cmd_report_board(args):
    """Markdown report of the board roster and decision stats."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            advisors = _fetch_advisors(tx)
            decisions = _fetch_decisions(tx)

    lines = ["# Board of Advisors", ""]

    active = [a for a in advisors if a.get("status") != "retired"]
    retired = [a for a in advisors if a.get("status") == "retired"]

    if not advisors:
        lines.append("_No advisors seated yet. Use `add-advisor` to build your board._")
    else:
        lines.append("| Seat | Archetype | Decision style | Pushback | Inspiration |")
        lines.append("|---|---|---|---|---|")
        for a in active:
            lines.append(f"| {a.get('name')} | {a.get('archetype') or ''} "
                         f"| {a.get('decision_style') or ''} | {a.get('pushback') or ''} "
                         f"| {a.get('inspiration') or ''} |")
        lines.append("")
        for a in active:
            if a.get("charter"):
                lines.append(f"- **{a.get('name')}** — {a['charter']}")
        if retired:
            lines.append("")
            lines.append(f"_Retired seats: {', '.join(a.get('name') or '' for a in retired)}_")

    lines.append("")
    lines.append("## Decisions")
    lines.append("")
    by_status = {}
    for d in decisions:
        by_status.setdefault(d.get("status") or "framing", []).append(d)
    for status in DECISION_STATUSES:
        ds = by_status.get(status, [])
        if ds:
            lines.append(f"**{status.capitalize()} ({len(ds)}):**")
            for d in ds:
                due = " — REVIEW DUE" if _is_review_due(d) else ""
                lines.append(f"- {d.get('name')} [{d.get('stakes') or '?'}]{due}")
            lines.append("")

    due = [d for d in decisions if _is_review_due(d)]
    if due:
        lines.append(f"⚠ {len(due)} decision(s) past their review date — run the review workflow.")

    print("\n".join(lines))


# =============================================================================
# AUDIT COMMAND
# =============================================================================


def cmd_audit(args):
    """Run declarative quality checks from quality-checks.yaml."""
    if not YAML_AVAILABLE:
        fail("pyyaml not installed")
        return

    checks_path = Path(__file__).parent / "quality-checks.yaml"
    if not checks_path.exists():
        fail(f"quality-checks.yaml not found at {checks_path}")
        return

    with open(checks_path) as f:
        spec = yaml.safe_load(f)

    now = get_timestamp()
    results = []
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            for check in spec.get("checks", []):
                entry = {
                    "name": check.get("name"),
                    "severity": check.get("severity"),
                    "description": check.get("description"),
                }
                query = (check.get("find_violations") or "").replace("{{now}}", now)
                try:
                    violations = list(tx.query(query).resolve())
                    entry["violations"] = violations
                    entry["count"] = len(violations)
                except Exception as e:
                    entry["error"] = str(e)
                total_q = check.get("count_total")
                if total_q:
                    try:
                        entry["total"] = len(list(tx.query(total_q).resolve()))
                    except Exception:
                        pass
                results.append(entry)

    failed = [r for r in results if r.get("count")]
    print(json.dumps({
        "success": True,
        "checks_run": len(results),
        "checks_with_violations": len(failed),
        "results": results,
    }, default=str))


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Advisor CLI - board of advisors, decisions, bias checks, scenarios, journal")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- Board management ---
    p = subparsers.add_parser("add-advisor", help="Add a persona seat to the board")
    p.add_argument("--name", required=True, help="Seat name, e.g. 'The Operator'")
    p.add_argument("--archetype", help="operator | financier | contrarian | technologist | ...")
    p.add_argument("--decision-style", dest="decision_style",
                   help="How this persona reasons (first-principles, risk-first, ...)")
    p.add_argument("--pushback", choices=PUSHBACK_LEVELS, help="gentle | firm | relentless")
    p.add_argument("--inspiration", help="Real mentor / public figure this seat channels")
    p.add_argument("--charter", help="What this seat is for (its standing brief)")
    p.add_argument("--description", help="Longer persona description")
    p.add_argument("--board", help=f"Board name (default: '{DEFAULT_BOARD_NAME}')")
    p.add_argument("--id", help="Explicit id (default: generated)")
    p.set_defaults(func=cmd_add_advisor)

    p = subparsers.add_parser("list-advisors", help="List board seats")
    p.add_argument("--include-retired", action="store_true", help="Include retired seats")
    p.set_defaults(func=cmd_list_advisors)

    p = subparsers.add_parser("retire-advisor", help="Retire a seat")
    p.add_argument("--id", required=True, help="Advisor id")
    p.set_defaults(func=cmd_retire_advisor)

    # --- Personal context system ---
    p = subparsers.add_parser("add-context", help="Add a context doc")
    p.add_argument("--name", required=True, help="Doc name, e.g. 'My role & mandate'")
    p.add_argument("--kind", required=True,
                   help="role | company | ecosystem | competitive-stance | priorities | past-decision")
    p.add_argument("--content", help="Doc content (inline)")
    p.add_argument("--content-file", dest="content_file", help="Doc content from file")
    p.add_argument("--description", help="One-line summary")
    p.add_argument("--id", help="Explicit id")
    p.set_defaults(func=cmd_add_context)

    p = subparsers.add_parser("list-context", help="List context docs")
    p.add_argument("--kind", help="Filter by context kind")
    p.add_argument("--full", action="store_true", help="Include full content (no truncation)")
    p.set_defaults(func=cmd_list_context)

    # --- Decision workflow ---
    p = subparsers.add_parser("open-decision", help="Open a decision (framing)")
    p.add_argument("--question", required=True, help="The decision question, stated crisply")
    p.add_argument("--name", help="Short display name (default: from question)")
    p.add_argument("--primer", help="Operator's messy brain dump (inline)")
    p.add_argument("--primer-file", dest="primer_file", help="Primer from file")
    p.add_argument("--stakes", choices=STAKES_LEVELS, help="low | medium | high | irreversible")
    p.add_argument("--operator-style", dest="operator_style",
                   help="options-menu | bottom-line | pushback-then-space")
    p.add_argument("--id", help="Explicit id")
    p.set_defaults(func=cmd_open_decision)

    p = subparsers.add_parser("add-note", help="Attach a note to any entity")
    p.add_argument("--about", required=True, help="Subject entity id")
    p.add_argument("--type", default="general",
                   choices=["primer", "interview", "debate", "bias", "journal", "general"])
    p.add_argument("--name", help="Note name")
    p.add_argument("--content", help="Note content (inline)")
    p.add_argument("--content-file", dest="content_file", help="Note content from file")
    p.set_defaults(func=cmd_add_note)

    p = subparsers.add_parser("add-take", help="Store one advisor's independent take")
    p.add_argument("--decision", required=True, help="Decision id")
    p.add_argument("--advisor", required=True, help="Advisor id")
    p.add_argument("--stance", help="for | against | conditional | reframe")
    p.add_argument("--content", help="The take (inline)")
    p.add_argument("--content-file", dest="content_file", help="The take from file")
    p.set_defaults(func=cmd_add_take)

    p = subparsers.add_parser("add-debate", help="Store the debate synthesis")
    p.add_argument("--decision", required=True, help="Decision id")
    p.add_argument("--content", help="Debate synthesis (inline)")
    p.add_argument("--content-file", dest="content_file", help="Debate synthesis from file")
    p.set_defaults(func=cmd_add_debate)

    p = subparsers.add_parser("add-bias-check", help="Store the bias check (-> deciding)")
    p.add_argument("--decision", required=True, help="Decision id")
    p.add_argument("--content", help="Bias check content (inline)")
    p.add_argument("--content-file", dest="content_file", help="Bias check from file")
    p.set_defaults(func=cmd_add_bias_check)

    p = subparsers.add_parser("add-scenario", help="Store a scenario stress-test")
    p.add_argument("--decision", required=True, help="Decision id")
    p.add_argument("--condition", required=True,
                   help='e.g. "Market shifts to X" / "Competitor does Y"')
    p.add_argument("--impact", help="What happens to the decision under this future")
    p.add_argument("--likelihood", choices=["low", "medium", "high"], help="Likelihood")
    p.add_argument("--id", help="Explicit id")
    p.set_defaults(func=cmd_add_scenario)

    p = subparsers.add_parser("decide", help="Record outcome + journal + review date")
    p.add_argument("--decision", required=True, help="Decision id")
    p.add_argument("--outcome", required=True, help="What was decided")
    p.add_argument("--journal", help="Journal entry: what, why, expected results (inline)")
    p.add_argument("--journal-file", dest="journal_file", help="Journal entry from file")
    p.add_argument("--review-date", dest="review_date", help="When to revisit (YYYY-MM-DD)")
    p.set_defaults(func=cmd_decide)

    p = subparsers.add_parser("review-decision", help="Close the loop on the review date")
    p.add_argument("--decision", required=True, help="Decision id")
    p.add_argument("--content", help="What happened vs expected (inline)")
    p.add_argument("--content-file", dest="content_file", help="Review from file")
    p.set_defaults(func=cmd_review_decision)

    # --- Queries & reports ---
    p = subparsers.add_parser("list-decisions", help="List decisions")
    p.add_argument("--status", choices=DECISION_STATUSES, help="Filter by status")
    p.add_argument("--stakes", choices=STAKES_LEVELS, help="Filter by stakes")
    p.add_argument("--review-due", dest="review_due", action="store_true",
                   help="Only decided decisions past their review date")
    p.add_argument("--journal", action="store_true",
                   help="Only decided/reviewed decisions (the journal view)")
    p.set_defaults(func=cmd_list_decisions)

    p = subparsers.add_parser("show-decision", help="Full decision detail")
    p.add_argument("--id", required=True, help="Decision id")
    p.set_defaults(func=cmd_show_decision)

    p = subparsers.add_parser("report-decision", help="Decision report (Markdown)")
    p.add_argument("--id", required=True, help="Decision id")
    p.set_defaults(func=cmd_report_decision)

    p = subparsers.add_parser("report-board", help="Board roster report (Markdown)")
    p.set_defaults(func=cmd_report_board)

    p = subparsers.add_parser("audit", help="Run quality checks from quality-checks.yaml")
    p.set_defaults(func=cmd_audit)

    args = parser.parse_args()

    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        sys.exit(1)

    try:
        args.func(args)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        sys.exit(1)


if __name__ == "__main__":
    main()
