#!/usr/bin/env python3
"""
Scribe CLI - The communication expert: voice profiles, audience personas,
review loops, and dimension-scored feedback.

This script handles STORAGE and QUERIES. Claude handles SENSEMAKING
(linguist analysis, drafting in voice, persona role-play, scoring) via SKILL.md.

Usage:
    uv run python skills/scribe/scribe.py <command> [options]

Commands:
    # Voice profiling
    add-sample          Store a writing sample (own or aspirational)
    list-samples        List writing samples
    create-profile      Create a voice profile (+ optional style guide)
    update-profile      Update profile status/genre or overwrite the style guide
    show-profile        Profile + style guide + samples + analysis notes
    add-analysis        Store a linguist analysis note about a profile/sample

    # Audience personas
    add-persona         Create a detailed reader persona
    list-personas       List personas

    # Piece production
    create-piece        Open a piece (stores --primer as a primer note)
    add-note            Attach a primer/interview/plan/general note to anything
    add-draft           Store a draft (auto-increments version per piece)
    add-review          Persona review of a draft (--persona, --draft)
    add-scores          Dimension scores 0-10 for a draft
    update-piece        Update piece status/goal/deadline/targets
    list-pieces         List pieces (--status, --type)
    show-piece          Piece + drafts + reviews + score trajectory (JSON)
    report-piece        Piece report (Markdown)

    # Quality
    audit               Run quality-checks.yaml audit rules

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
    import yaml

    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

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

PIECE_STATUSES = ["planning", "drafting", "persona-review", "operator-review", "final", "shipped"]
PROFILE_STATUSES = ["draft", "active", "evolving"]
SAMPLE_KINDS = ["own", "aspirational"]
SCORE_DIMENSIONS = [
    ("clarity", "scribe-clarity-score"),
    ("concision", "scribe-concision-score"),
    ("voice", "scribe-voice-score"),
    ("persuasion", "scribe-persuasion-score"),
    ("overall", "scribe-overall-score"),
]


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
    return date_str


def resolve_content(args, attr="content", file_attr="content_file"):
    """Resolve content from --content or --content-file. Mutually exclusive."""
    if getattr(args, file_attr, None):
        with open(getattr(args, file_attr), "r") as f:
            return f.read()
    return getattr(args, attr, None)


def fail(msg: str):
    print(json.dumps({"success": False, "error": msg}))
    sys.exit(0)


# =============================================================================
# SHARED HELPERS
# =============================================================================


def _entity_exists(tx, etype: str, eid: str) -> bool:
    r = list(tx.query(
        f'match $e isa {etype}, has id "{escape_string(eid)}"; fetch {{ "id": $e.id }};'
    ).resolve())
    return bool(r)


def _replace_attr(driver, etype: str, eid: str, attr: str, literal: str):
    """Delete old attribute value (if any) then insert the new one.

    `literal` must already be a TypeQL literal (quoted string or bare datetime/int).
    """
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        try:
            tx.query(
                f'match $e isa {etype}, has id "{escape_string(eid)}", has {attr} $old; '
                f"delete has $old of $e;"
            ).resolve()
        except Exception:
            pass
        tx.commit()
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(
            f'match $e isa {etype}, has id "{escape_string(eid)}"; '
            f"insert $e has {attr} {literal};"
        ).resolve()
        tx.commit()


def _create_note(driver, note_type: str, content: str, about_id: str,
                 name: str = None, extra: str = "") -> str:
    """Insert a note of the given type and attach it to a subject via alh-aboutness."""
    note_id = generate_id("note")
    timestamp = get_timestamp()
    query = f'''insert $n isa {note_type},
        has id "{note_id}",
        has content "{escape_string(content)}",
        has created-at {timestamp}'''
    if name:
        query += f', has name "{escape_string(name)}"'
    query += extra + ";"

    with get_driver_or(driver) as d:
        with d.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()
        with d.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $n isa alh-note, has id "{note_id}";
                $s isa alh-identifiable-entity, has id "{escape_string(about_id)}";
            insert (note: $n, subject: $s) isa alh-aboutness;''').resolve()
            tx.commit()
    return note_id


class _KeepOpen:
    """Wrap an existing driver so `with` blocks don't close it."""

    def __init__(self, driver):
        self._driver = driver

    def __enter__(self):
        return self._driver

    def __exit__(self, *exc):
        return False


def get_driver_or(driver):
    """Reuse an open driver if given, otherwise open a new one."""
    return _KeepOpen(driver) if driver is not None else get_driver()


def _notes_about(tx, subject_id: str, note_type: str):
    """Fetch notes of a given type attached to a subject."""
    try:
        return list(tx.query(f'''match
            $s isa alh-identifiable-entity, has id "{escape_string(subject_id)}";
            (note: $n, subject: $s) isa alh-aboutness;
            $n isa {note_type};
        fetch {{
            "id": $n.id,
            "name": $n.name,
            "content": $n.content,
            "created_at": $n.created-at
        }};''').resolve())
    except Exception:
        return []


# =============================================================================
# VOICE PROFILING COMMANDS
# =============================================================================


def cmd_add_sample(args):
    """Store a writing sample (own or aspirational)."""
    content = resolve_content(args)
    if not content:
        fail("Provide either --content or --content-file")
    if args.kind not in SAMPLE_KINDS:
        fail(f"--kind must be one of: {', '.join(SAMPLE_KINDS)}")

    sample_id = args.id or generate_id("sample")
    timestamp = get_timestamp()

    query = f'''insert $s isa scribe-writing-sample,
        has id "{sample_id}",
        has name "{escape_string(args.name)}",
        has scribe-sample-kind "{args.kind}",
        has content "{escape_string(content)}",
        has created-at {timestamp}'''
    if args.doc_type:
        query += f', has scribe-doc-type "{escape_string(args.doc_type)}"'
    if args.why_it_works:
        query += f', has scribe-why-it-works "{escape_string(args.why_it_works)}"'
    if args.source_uri:
        query += f', has source-uri "{escape_string(args.source_uri)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'
    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        linked_profile = None
        if args.profile:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $s isa scribe-writing-sample, has id "{sample_id}";
                    $p isa scribe-voice-profile, has id "{escape_string(args.profile)}";
                insert (sample: $s, voice-profile: $p) isa scribe-sample-informs;''').resolve()
                tx.commit()
            linked_profile = args.profile

    print(json.dumps({
        "success": True,
        "sample_id": sample_id,
        "name": args.name,
        "kind": args.kind,
        "doc_type": args.doc_type,
        "linked_profile": linked_profile,
    }))


def cmd_list_samples(args):
    """List writing samples, optionally filtered by kind/doc-type."""
    constraints = ""
    if args.kind:
        constraints += f', has scribe-sample-kind "{escape_string(args.kind)}"'
    if args.doc_type:
        constraints += f', has scribe-doc-type "{escape_string(args.doc_type)}"'

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            samples = list(tx.query(f'''match
                $s isa scribe-writing-sample{constraints};
            fetch {{
                "id": $s.id,
                "name": $s.name,
                "kind": $s.scribe-sample-kind,
                "doc_type": $s.scribe-doc-type,
                "why_it_works": $s.scribe-why-it-works,
                "created_at": $s.created-at
            }};''').resolve())

            # Which profile does each sample inform?
            links = {}
            try:
                for r in tx.query('''match
                    (sample: $s, voice-profile: $p) isa scribe-sample-informs;
                fetch { "sample_id": $s.id, "profile_id": $p.id };''').resolve():
                    links[r["sample_id"]] = r["profile_id"]
            except Exception:
                pass

    for s in samples:
        s["profile_id"] = links.get(s["id"])
    print(json.dumps({"success": True, "samples": samples, "count": len(samples)}, default=str))


def cmd_create_profile(args):
    """Create a voice profile, optionally with an initial style guide artifact."""
    status = args.status or "draft"
    if status not in PROFILE_STATUSES:
        fail(f"--status must be one of: {', '.join(PROFILE_STATUSES)}")

    profile_id = args.id or generate_id("profile")
    timestamp = get_timestamp()

    query = f'''insert $p isa scribe-voice-profile,
        has id "{profile_id}",
        has name "{escape_string(args.name)}",
        has scribe-profile-status "{status}",
        has created-at {timestamp}'''
    if args.genre:
        query += f', has scribe-genre "{escape_string(args.genre)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'
    query += ";"

    guide_content = resolve_content(args, attr="guide", file_attr="guide_file")
    guide_id = None

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        if guide_content:
            guide_id = _upsert_style_guide(driver, profile_id, guide_content)

    print(json.dumps({
        "success": True,
        "profile_id": profile_id,
        "name": args.name,
        "status": status,
        "genre": args.genre,
        "guide_id": guide_id,
    }))


def _find_style_guide(tx, profile_id: str):
    """Find the style guide artifact linked to a profile via alh-representation."""
    try:
        r = list(tx.query(f'''match
            $p isa scribe-voice-profile, has id "{escape_string(profile_id)}";
            (alh-artifact: $g, referent: $p) isa alh-representation;
            $g isa scribe-style-guide;
        fetch {{ "id": $g.id, "content": $g.content, "created_at": $g.created-at }};''').resolve())
        return r[0] if r else None
    except Exception:
        return None


def _upsert_style_guide(driver, profile_id: str, content: str) -> str:
    """Create or overwrite the style guide artifact for a profile."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        existing = _find_style_guide(tx, profile_id)

    timestamp = get_timestamp()
    if existing:
        guide_id = existing["id"]
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            try:
                tx.query(f'''match
                    $g isa scribe-style-guide, has id "{guide_id}", has content $c;
                delete has $c of $g;''').resolve()
            except Exception:
                pass
            tx.commit()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match $g isa scribe-style-guide, has id "{guide_id}";
            insert $g has content "{escape_string(content)}";''').resolve()
            tx.commit()
    else:
        guide_id = generate_id("guide")
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''insert $g isa scribe-style-guide,
                has id "{guide_id}",
                has name "Style Guide",
                has content "{escape_string(content)}",
                has created-at {timestamp};''').resolve()
            tx.commit()
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $g isa scribe-style-guide, has id "{guide_id}";
                $p isa scribe-voice-profile, has id "{escape_string(profile_id)}";
            insert (alh-artifact: $g, referent: $p) isa alh-representation;''').resolve()
            tx.commit()
    return guide_id


def cmd_update_profile(args):
    """Update a voice profile's status/genre and/or overwrite its style guide."""
    updated = {}
    guide_content = resolve_content(args, attr="guide", file_attr="guide_file")

    if not (args.status or args.genre or guide_content):
        fail("Nothing to update: provide --status, --genre, --guide, or --guide-file")
    if args.status and args.status not in PROFILE_STATUSES:
        fail(f"--status must be one of: {', '.join(PROFILE_STATUSES)}")

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not _entity_exists(tx, "scribe-voice-profile", args.id):
                fail(f"Voice profile not found: {args.id}")

        if args.status:
            _replace_attr(driver, "scribe-voice-profile", args.id,
                          "scribe-profile-status", f'"{args.status}"')
            updated["status"] = args.status
        if args.genre:
            _replace_attr(driver, "scribe-voice-profile", args.id,
                          "scribe-genre", f'"{escape_string(args.genre)}"')
            updated["genre"] = args.genre
        if guide_content:
            updated["guide_id"] = _upsert_style_guide(driver, args.id, guide_content)

    print(json.dumps({"success": True, "profile_id": args.id, "updated": updated}))


def cmd_show_profile(args):
    """Show a voice profile: guide + samples + linguist analyses."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if args.id:
                profiles = list(tx.query(f'''match
                    $p isa scribe-voice-profile, has id "{escape_string(args.id)}";
                fetch {{
                    "id": $p.id, "name": $p.name, "description": $p.description,
                    "status": $p.scribe-profile-status, "genre": $p.scribe-genre,
                    "created_at": $p.created-at
                }};''').resolve())
            else:
                profiles = list(tx.query('''match
                    $p isa scribe-voice-profile;
                fetch {
                    "id": $p.id, "name": $p.name, "description": $p.description,
                    "status": $p.scribe-profile-status, "genre": $p.scribe-genre,
                    "created_at": $p.created-at
                };''').resolve())

            if not profiles:
                fail("No voice profile found" + (f": {args.id}" if args.id else ""))

            profile = profiles[0]
            pid = profile["id"]

            guide = _find_style_guide(tx, pid)

            samples = list(tx.query(f'''match
                $p isa scribe-voice-profile, has id "{pid}";
                (sample: $s, voice-profile: $p) isa scribe-sample-informs;
            fetch {{
                "id": $s.id, "name": $s.name,
                "kind": $s.scribe-sample-kind, "doc_type": $s.scribe-doc-type,
                "why_it_works": $s.scribe-why-it-works
            }};''').resolve())

            analyses = _notes_about(tx, pid, "scribe-analysis-note")

    print(json.dumps({
        "success": True,
        "profile": profile,
        "style_guide": guide,
        "samples": samples,
        "analyses": analyses,
        "all_profiles": [p["id"] for p in profiles] if not args.id else None,
    }, default=str))


def cmd_add_analysis(args):
    """Store a linguist analysis note about a profile or sample."""
    content = resolve_content(args)
    if not content:
        fail("Provide either --content or --content-file")

    with get_driver() as driver:
        note_id = _create_note(driver, "scribe-analysis-note", content, args.about,
                               name=args.name or "Linguist Analysis")
    print(json.dumps({"success": True, "note_id": note_id, "about": args.about,
                      "type": "analysis"}))


# =============================================================================
# PERSONA COMMANDS
# =============================================================================


def cmd_add_persona(args):
    """Create a detailed reader persona."""
    persona_id = args.id or generate_id("persona")
    timestamp = get_timestamp()

    query = f'''insert $p isa scribe-persona,
        has id "{persona_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''
    if args.cares_about:
        query += f', has scribe-cares-about "{escape_string(args.cares_about)}"'
    if args.skeptical_of:
        query += f', has scribe-skeptical-of "{escape_string(args.skeptical_of)}"'
    if args.action_drivers:
        query += f', has scribe-action-drivers "{escape_string(args.action_drivers)}"'
    if args.reading_context:
        query += f', has scribe-reading-context "{escape_string(args.reading_context)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'
    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

    print(json.dumps({"success": True, "persona_id": persona_id, "name": args.name}))


def cmd_list_personas(args):
    """List all personas."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            personas = list(tx.query('''match
                $p isa scribe-persona;
            fetch {
                "id": $p.id, "name": $p.name, "description": $p.description,
                "cares_about": $p.scribe-cares-about,
                "skeptical_of": $p.scribe-skeptical-of,
                "action_drivers": $p.scribe-action-drivers,
                "reading_context": $p.scribe-reading-context,
                "created_at": $p.created-at
            };''').resolve())

            # How many pieces target each persona?
            targets = {}
            try:
                for r in tx.query('''match
                    (piece: $pc, persona: $p) isa scribe-piece-targets;
                fetch { "persona_id": $p.id, "piece_id": $pc.id };''').resolve():
                    targets.setdefault(r["persona_id"], []).append(r["piece_id"])
            except Exception:
                pass

    for p in personas:
        p["target_of_pieces"] = len(targets.get(p["id"], []))
    print(json.dumps({"success": True, "personas": personas, "count": len(personas)}, default=str))


# =============================================================================
# PIECE COMMANDS
# =============================================================================


def cmd_create_piece(args):
    """Open a communication piece. Stores --primer as a scribe-primer-note."""
    piece_id = args.id or generate_id("piece")
    timestamp = get_timestamp()

    query = f'''insert $p isa scribe-piece,
        has id "{piece_id}",
        has name "{escape_string(args.name)}",
        has scribe-piece-status "planning",
        has created-at {timestamp}'''
    if args.type:
        query += f', has scribe-piece-type "{escape_string(args.type)}"'
    if args.goal:
        query += f', has scribe-goal "{escape_string(args.goal)}"'
    if args.audience_summary:
        query += f', has scribe-audience-summary "{escape_string(args.audience_summary)}"'
    if args.deadline:
        query += f", has scribe-deadline {parse_date(args.deadline)}"
    if args.description:
        query += f', has description "{escape_string(args.description)}"'
    query += ";"

    primer_content = resolve_content(args, attr="primer", file_attr="primer_file")
    primer_note_id = None
    linked_targets = []

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        if primer_content:
            primer_note_id = _create_note(driver, "scribe-primer-note", primer_content,
                                          piece_id, name="Primer")

        for persona_id in (args.targets or []):
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $pc isa scribe-piece, has id "{piece_id}";
                    $pe isa scribe-persona, has id "{escape_string(persona_id)}";
                insert (piece: $pc, persona: $pe) isa scribe-piece-targets;''').resolve()
                tx.commit()
            linked_targets.append(persona_id)

    output = {
        "success": True,
        "piece_id": piece_id,
        "name": args.name,
        "status": "planning",
        "primer_note_id": primer_note_id,
        "targets": linked_targets,
    }
    if not primer_content:
        output["warning"] = ("No primer captured. Operating principle: always capture the "
                             "operator's messy initial brain dump (--primer / --primer-file).")
    print(json.dumps(output))


def cmd_add_note(args):
    """Attach a primer/interview/plan/analysis/general note to any entity."""
    content = resolve_content(args)
    if not content:
        fail("Provide either --content or --content-file")

    type_map = {
        "primer": "scribe-primer-note",
        "interview": "scribe-interview-note",
        "plan": "scribe-plan-note",
        "analysis": "scribe-analysis-note",
        "general": "note",
    }
    note_type = type_map.get(args.type)
    if not note_type:
        fail(f"--type must be one of: {', '.join(type_map)}")

    with get_driver() as driver:
        note_id = _create_note(driver, note_type, content, args.about, name=args.name)
    print(json.dumps({"success": True, "note_id": note_id, "about": args.about,
                      "type": args.type}))


def cmd_add_draft(args):
    """Store a draft for a piece; version auto-increments."""
    content = resolve_content(args)
    if not content:
        fail("Provide either --content or --content-file")

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not _entity_exists(tx, "scribe-piece", args.piece):
                fail(f"Piece not found: {args.piece}")
            existing = list(tx.query(f'''match
                $pc isa scribe-piece, has id "{escape_string(args.piece)}";
                (draft: $d, piece: $pc) isa scribe-draft-of;
            fetch {{ "version": $d.scribe-version }};''').resolve())

        versions = [r["version"] for r in existing if r.get("version") is not None]
        version = (max(versions) + 1) if versions else 1

        draft_id = args.id or generate_id("draft")
        timestamp = get_timestamp()
        name = args.name or f"Draft v{version}"

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''insert $d isa scribe-draft,
                has id "{draft_id}",
                has name "{escape_string(name)}",
                has scribe-version {version},
                has content "{escape_string(content)}",
                has created-at {timestamp};''').resolve()
            tx.commit()

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $d isa scribe-draft, has id "{draft_id}";
                $pc isa scribe-piece, has id "{escape_string(args.piece)}";
            insert (draft: $d, piece: $pc) isa scribe-draft-of;''').resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "draft_id": draft_id,
        "piece_id": args.piece,
        "version": version,
    }))


def cmd_add_review(args):
    """Store a persona review of a draft.

    Content should answer: is the message clear? would I act? what's missing?
    where would I stop reading? The would-act verdict is also stored as a boolean.
    """
    content = resolve_content(args)
    if not content:
        fail("Provide either --content or --content-file")

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not _entity_exists(tx, "scribe-draft", args.draft):
                fail(f"Draft not found: {args.draft}")
            if not _entity_exists(tx, "scribe-persona", args.persona):
                fail(f"Persona not found: {args.persona}")

        extra = ""
        if args.would_act is not None:
            extra = f", has scribe-would-act {'true' if args.would_act == 'yes' else 'false'}"

        note_id = _create_note(driver, "scribe-review-note", content, args.draft,
                               name=args.name or "Persona Review", extra=extra)

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $r isa scribe-review-note, has id "{note_id}";
                $pe isa scribe-persona, has id "{escape_string(args.persona)}";
            insert (review: $r, persona: $pe) isa scribe-review-by;''').resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "review_id": note_id,
        "draft_id": args.draft,
        "persona_id": args.persona,
        "would_act": args.would_act,
    }))


def cmd_add_scores(args):
    """Store dimension scores (0-10) plus qualitative content for a draft."""
    content = resolve_content(args)
    if not content:
        fail("Provide qualitative feedback via --content or --content-file "
             "(concrete: structure, phrasing, or ideas — never just numbers)")

    scores = {}
    extra = ""
    for dim, attr in SCORE_DIMENSIONS:
        val = getattr(args, dim, None)
        if val is not None:
            if not (0 <= val <= 10):
                fail(f"--{dim} must be an integer 0-10 (got {val})")
            scores[dim] = val
            extra += f", has {attr} {val}"

    if not scores:
        fail("Provide at least one dimension score "
             "(--clarity --concision --voice --persuasion --overall, 0-10)")

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not _entity_exists(tx, "scribe-draft", args.draft):
                fail(f"Draft not found: {args.draft}")

        note_id = _create_note(driver, "scribe-score-note", content, args.draft,
                               name=args.name or "Dimension Scores", extra=extra)

    print(json.dumps({
        "success": True,
        "score_note_id": note_id,
        "draft_id": args.draft,
        "scores": scores,
    }))


def cmd_update_piece(args):
    """Update piece status/type/goal/audience/deadline; add target personas."""
    updated = {}
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            if not _entity_exists(tx, "scribe-piece", args.id):
                fail(f"Piece not found: {args.id}")

        if args.status:
            if args.status not in PIECE_STATUSES:
                fail(f"--status must be one of: {', '.join(PIECE_STATUSES)}")
            _replace_attr(driver, "scribe-piece", args.id,
                          "scribe-piece-status", f'"{args.status}"')
            updated["status"] = args.status
        if args.type:
            _replace_attr(driver, "scribe-piece", args.id,
                          "scribe-piece-type", f'"{escape_string(args.type)}"')
            updated["type"] = args.type
        if args.goal:
            _replace_attr(driver, "scribe-piece", args.id,
                          "scribe-goal", f'"{escape_string(args.goal)}"')
            updated["goal"] = args.goal
        if args.audience_summary:
            _replace_attr(driver, "scribe-piece", args.id,
                          "scribe-audience-summary", f'"{escape_string(args.audience_summary)}"')
            updated["audience_summary"] = args.audience_summary
        if args.deadline:
            _replace_attr(driver, "scribe-piece", args.id,
                          "scribe-deadline", parse_date(args.deadline))
            updated["deadline"] = args.deadline

        added_targets = []
        for persona_id in (args.add_target or []):
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $pc isa scribe-piece, has id "{escape_string(args.id)}";
                    $pe isa scribe-persona, has id "{escape_string(persona_id)}";
                insert (piece: $pc, persona: $pe) isa scribe-piece-targets;''').resolve()
                tx.commit()
            added_targets.append(persona_id)
        if added_targets:
            updated["added_targets"] = added_targets

    if not updated:
        fail("Nothing to update")
    print(json.dumps({"success": True, "piece_id": args.id, "updated": updated}))


def cmd_list_pieces(args):
    """List pieces, optionally filtered by status/type."""
    constraints = ""
    if args.status:
        constraints += f', has scribe-piece-status "{escape_string(args.status)}"'
    if args.type:
        constraints += f', has scribe-piece-type "{escape_string(args.type)}"'

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            pieces = list(tx.query(f'''match
                $p isa scribe-piece{constraints};
            fetch {{
                "id": $p.id, "name": $p.name,
                "type": $p.scribe-piece-type,
                "status": $p.scribe-piece-status,
                "goal": $p.scribe-goal,
                "audience_summary": $p.scribe-audience-summary,
                "deadline": $p.scribe-deadline,
                "created_at": $p.created-at
            }};''').resolve())

            # Draft counts and latest version per piece
            draft_info = {}
            try:
                for r in tx.query('''match
                    (draft: $d, piece: $p) isa scribe-draft-of;
                fetch { "piece_id": $p.id, "version": $d.scribe-version };''').resolve():
                    info = draft_info.setdefault(r["piece_id"], {"drafts": 0, "latest_version": 0})
                    info["drafts"] += 1
                    v = r.get("version") or 0
                    if v > info["latest_version"]:
                        info["latest_version"] = v
            except Exception:
                pass

            # Target persona names per piece
            target_info = {}
            try:
                for r in tx.query('''match
                    (piece: $p, persona: $pe) isa scribe-piece-targets;
                fetch { "piece_id": $p.id, "persona": $pe.name };''').resolve():
                    target_info.setdefault(r["piece_id"], []).append(r["persona"])
            except Exception:
                pass

    for p in pieces:
        info = draft_info.get(p["id"], {"drafts": 0, "latest_version": 0})
        p["draft_count"] = info["drafts"]
        p["latest_version"] = info["latest_version"]
        p["targets"] = target_info.get(p["id"], [])
    print(json.dumps({"success": True, "pieces": pieces, "count": len(pieces)}, default=str))


def _gather_piece(driver, piece_id: str):
    """Assemble the full piece dossier: attrs, targets, drafts, reviews, scores."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
        pieces = list(tx.query(f'''match
            $p isa scribe-piece, has id "{escape_string(piece_id)}";
        fetch {{
            "id": $p.id, "name": $p.name, "description": $p.description,
            "type": $p.scribe-piece-type,
            "status": $p.scribe-piece-status,
            "goal": $p.scribe-goal,
            "audience_summary": $p.scribe-audience-summary,
            "deadline": $p.scribe-deadline,
            "created_at": $p.created-at
        }};''').resolve())
        if not pieces:
            return None
        piece = pieces[0]

        targets = list(tx.query(f'''match
            $p isa scribe-piece, has id "{escape_string(piece_id)}";
            (piece: $p, persona: $pe) isa scribe-piece-targets;
        fetch {{
            "id": $pe.id, "name": $pe.name,
            "cares_about": $pe.scribe-cares-about,
            "skeptical_of": $pe.scribe-skeptical-of,
            "action_drivers": $pe.scribe-action-drivers,
            "reading_context": $pe.scribe-reading-context
        }};''').resolve())

        drafts = list(tx.query(f'''match
            $p isa scribe-piece, has id "{escape_string(piece_id)}";
            (draft: $d, piece: $p) isa scribe-draft-of;
        fetch {{
            "id": $d.id, "name": $d.name, "version": $d.scribe-version,
            "content": $d.content, "created_at": $d.created-at
        }};''').resolve())
        drafts.sort(key=lambda d: d.get("version") or 0)

        trajectory = []
        for draft in drafts:
            did = draft["id"]

            # Persona reviews of this draft (+ reviewer name via scribe-review-by)
            reviews = []
            try:
                reviews = list(tx.query(f'''match
                    $d isa scribe-draft, has id "{did}";
                    (note: $r, subject: $d) isa alh-aboutness;
                    $r isa scribe-review-note;
                fetch {{
                    "id": $r.id, "content": $r.content,
                    "would_act": $r.scribe-would-act,
                    "created_at": $r.created-at
                }};''').resolve())
            except Exception:
                pass
            reviewer_names = {}
            try:
                for r in tx.query(f'''match
                    $d isa scribe-draft, has id "{did}";
                    (note: $rn, subject: $d) isa alh-aboutness;
                    $rn isa scribe-review-note;
                    (review: $rn, persona: $pe) isa scribe-review-by;
                fetch {{ "review_id": $rn.id, "persona_id": $pe.id, "persona": $pe.name }};''').resolve():
                    reviewer_names[r["review_id"]] = {"persona_id": r["persona_id"],
                                                      "persona": r["persona"]}
            except Exception:
                pass
            for rv in reviews:
                who = reviewer_names.get(rv["id"], {})
                rv["persona_id"] = who.get("persona_id")
                rv["persona"] = who.get("persona")
            draft["reviews"] = reviews

            # Dimension scores
            score_notes = []
            try:
                score_notes = list(tx.query(f'''match
                    $d isa scribe-draft, has id "{did}";
                    (note: $s, subject: $d) isa alh-aboutness;
                    $s isa scribe-score-note;
                fetch {{
                    "id": $s.id, "content": $s.content,
                    "clarity": $s.scribe-clarity-score,
                    "concision": $s.scribe-concision-score,
                    "voice": $s.scribe-voice-score,
                    "persuasion": $s.scribe-persuasion-score,
                    "overall": $s.scribe-overall-score,
                    "created_at": $s.created-at
                }};''').resolve())
            except Exception:
                pass
            draft["scores"] = score_notes

            latest = score_notes[-1] if score_notes else {}
            trajectory.append({
                "version": draft.get("version"),
                "clarity": latest.get("clarity"),
                "concision": latest.get("concision"),
                "voice": latest.get("voice"),
                "persuasion": latest.get("persuasion"),
                "overall": latest.get("overall"),
                "would_act": sum(1 for rv in reviews if rv.get("would_act") is True),
                "reviews": len(reviews),
            })

        notes = {}
        for ntype, label in [
            ("scribe-primer-note", "primer"),
            ("scribe-interview-note", "interview"),
            ("scribe-plan-note", "plan"),
        ]:
            found = _notes_about(tx, piece_id, ntype)
            if found:
                notes[label] = found

    return {
        "piece": piece,
        "targets": targets,
        "drafts": drafts,
        "score_trajectory": trajectory,
        "notes": notes,
    }


def cmd_show_piece(args):
    """Piece detail: drafts, persona reviews, score trajectory (JSON)."""
    with get_driver() as driver:
        data = _gather_piece(driver, args.id)
    if not data:
        fail(f"Piece not found: {args.id}")
    data["success"] = True
    print(json.dumps(data, default=str))


def cmd_report_piece(args):
    """Piece report (Markdown, for human display)."""
    with get_driver() as driver:
        data = _gather_piece(driver, args.id)
    if not data:
        fail(f"Piece not found: {args.id}")

    p = data["piece"]
    lines = [f"# {p.get('name', '(untitled)')}", ""]
    meta = []
    if p.get("type"):
        meta.append(f"**Type:** {p['type']}")
    meta.append(f"**Status:** {p.get('status', '?')}")
    if p.get("deadline"):
        meta.append(f"**Deadline:** {p['deadline']}")
    lines.append(" · ".join(meta))
    if p.get("goal"):
        lines += ["", f"**Goal:** {p['goal']}"]
    if p.get("audience_summary"):
        lines += ["", f"**Audience:** {p['audience_summary']}"]

    if data["targets"]:
        lines += ["", "## Target Personas", ""]
        for t in data["targets"]:
            lines.append(f"- **{t.get('name')}** — cares about: {t.get('cares_about') or '?'}; "
                         f"skeptical of: {t.get('skeptical_of') or '?'}")

    if data["score_trajectory"]:
        lines += ["", "## Score Trajectory", "",
                  "| Version | Clarity | Concision | Voice | Persuasion | Overall | Would Act |",
                  "|---------|---------|-----------|-------|------------|---------|-----------|"]
        for t in data["score_trajectory"]:
            def s(v):
                return str(v) if v is not None else "—"
            lines.append(f"| v{t['version']} | {s(t['clarity'])} | {s(t['concision'])} "
                         f"| {s(t['voice'])} | {s(t['persuasion'])} | {s(t['overall'])} "
                         f"| {t['would_act']}/{t['reviews']} |")

    for draft in data["drafts"]:
        lines += ["", f"## Draft v{draft.get('version')} ({draft.get('id')})", ""]
        if draft.get("reviews"):
            for rv in draft["reviews"]:
                verdict = ""
                if rv.get("would_act") is True:
                    verdict = " — WOULD ACT"
                elif rv.get("would_act") is False:
                    verdict = " — would NOT act"
                lines.append(f"**{rv.get('persona') or 'Persona'}**{verdict}:")
                content = (rv.get("content") or "").replace("\\n", "\n")
                lines.append(f"> {content[:600]}")
                lines.append("")
        if draft.get("scores"):
            latest = draft["scores"][-1]
            content = (latest.get("content") or "").replace("\\n", "\n")
            lines.append(f"**Score feedback:** {content[:600]}")

    for label, ns in data["notes"].items():
        lines += ["", f"## {label.title()} Notes", ""]
        for n in ns:
            content = (n.get("content") or "").replace("\\n", "\n")
            lines.append(f"- {content[:400]}")

    print("\n".join(lines))


# =============================================================================
# AUDIT
# =============================================================================


def cmd_audit(args):
    """Run the declarative audit rules in quality-checks.yaml."""
    if not YAML_AVAILABLE:
        fail("pyyaml not installed. Install with: pip install pyyaml")

    checks_path = Path(__file__).parent / "quality-checks.yaml"
    if not checks_path.exists():
        fail(f"quality-checks.yaml not found at {checks_path}")

    with open(checks_path) as f:
        spec = yaml.safe_load(f)

    results = []
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            for check in spec.get("checks", []):
                entry = {
                    "name": check["name"],
                    "severity": check.get("severity", "medium"),
                    "description": check.get("description", ""),
                }
                try:
                    violations = list(tx.query(check["find_violations"]).resolve())
                    entry["violations"] = violations
                    entry["violation_count"] = len(violations)
                    if check.get("count_total"):
                        total = list(tx.query(check["count_total"]).resolve())
                        entry["total"] = len(total)
                except Exception as e:
                    entry["error"] = str(e)
                results.append(entry)

    total_violations = sum(r.get("violation_count", 0) for r in results)
    print(json.dumps({
        "success": True,
        "skill": spec.get("skill", "scribe"),
        "checks": results,
        "total_violations": total_violations,
    }, default=str))


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Scribe - communication expert CLI (storage/queries; Claude does sensemaking)"
    )
    subparsers = parser.add_subparsers(dest="command")

    # --- Voice profiling ---
    p = subparsers.add_parser("add-sample", help="Store a writing sample")
    p.add_argument("--name", required=True, help="Sample title")
    p.add_argument("--kind", required=True, choices=SAMPLE_KINDS,
                   help="own (operator's best) | aspirational (admired writer)")
    p.add_argument("--doc-type", help="board-update | team-email | linkedin | talk | essay | ...")
    p.add_argument("--content", help="Sample text")
    p.add_argument("--content-file", help="Read sample text from file")
    p.add_argument("--why-it-works", help="Why this sample earned its place")
    p.add_argument("--source-uri", help="Where the sample came from")
    p.add_argument("--description", help="Optional description")
    p.add_argument("--profile", help="Voice profile ID to link (scribe-sample-informs)")
    p.add_argument("--id", help="Explicit ID (default: generated)")

    p = subparsers.add_parser("list-samples", help="List writing samples")
    p.add_argument("--kind", choices=SAMPLE_KINDS, help="Filter by kind")
    p.add_argument("--doc-type", help="Filter by doc type")

    p = subparsers.add_parser("create-profile", help="Create a voice profile")
    p.add_argument("--name", required=True, help="Profile name (e.g. 'Default Voice')")
    p.add_argument("--status", choices=PROFILE_STATUSES, help="draft | active | evolving (default draft)")
    p.add_argument("--genre", help="Optional per-genre profile (board-update, linkedin, ...)")
    p.add_argument("--description", help="Optional description")
    p.add_argument("--guide", help="Initial style guide markdown")
    p.add_argument("--guide-file", help="Read style guide from file")
    p.add_argument("--id", help="Explicit ID")

    p = subparsers.add_parser("update-profile", help="Update profile / overwrite style guide")
    p.add_argument("--id", required=True, help="Profile ID")
    p.add_argument("--status", choices=PROFILE_STATUSES)
    p.add_argument("--genre")
    p.add_argument("--guide", help="New style guide markdown (overwrites)")
    p.add_argument("--guide-file", help="Read style guide from file")

    p = subparsers.add_parser("show-profile", help="Profile + guide + samples + analyses")
    p.add_argument("--id", help="Profile ID (default: first profile found)")

    p = subparsers.add_parser("add-analysis", help="Store a linguist analysis note")
    p.add_argument("--about", required=True, help="Profile or sample ID")
    p.add_argument("--content", help="Analysis text")
    p.add_argument("--content-file", help="Read analysis from file")
    p.add_argument("--name", help="Note title")

    # --- Personas ---
    p = subparsers.add_parser("add-persona", help="Create a reader persona")
    p.add_argument("--name", required=True, help="Persona name (e.g. 'Skeptical board member')")
    p.add_argument("--cares-about", help="What this reader cares about")
    p.add_argument("--skeptical-of", help="What this reader is skeptical of")
    p.add_argument("--action-drivers", help="What drives this reader to act")
    p.add_argument("--reading-context", help="Where/how/when they read")
    p.add_argument("--description", help="Fuller persona description")
    p.add_argument("--id", help="Explicit ID")

    subparsers.add_parser("list-personas", help="List personas")

    # --- Pieces ---
    p = subparsers.add_parser("create-piece", help="Open a communication piece (status: planning)")
    p.add_argument("--name", required=True, help="Piece title")
    p.add_argument("--type", help="board-update | team-email | linkedin | talk | essay | ...")
    p.add_argument("--goal", help="What this piece must accomplish")
    p.add_argument("--audience-summary", help="One-line audience description")
    p.add_argument("--deadline", help="Deadline (YYYY-MM-DD)")
    p.add_argument("--description", help="Optional description")
    p.add_argument("--primer", help="Operator's messy brain dump (ALWAYS capture this)")
    p.add_argument("--primer-file", help="Read primer from file")
    p.add_argument("--targets", nargs="*", help="Persona IDs this piece must land with")
    p.add_argument("--id", help="Explicit ID")

    p = subparsers.add_parser("add-note", help="Attach a note to any entity")
    p.add_argument("--about", required=True, help="Subject entity ID")
    p.add_argument("--type", required=True,
                   choices=["primer", "interview", "plan", "analysis", "general"])
    p.add_argument("--content", help="Note text")
    p.add_argument("--content-file", help="Read note text from file")
    p.add_argument("--name", help="Note title")

    p = subparsers.add_parser("add-draft", help="Store a draft (auto-increments version)")
    p.add_argument("--piece", required=True, help="Piece ID")
    p.add_argument("--content", help="Draft text")
    p.add_argument("--content-file", help="Read draft text from file")
    p.add_argument("--name", help="Draft title (default: 'Draft vN')")
    p.add_argument("--id", help="Explicit ID")

    p = subparsers.add_parser("add-review", help="Persona review of a draft")
    p.add_argument("--draft", required=True, help="Draft ID")
    p.add_argument("--persona", required=True, help="Reviewing persona ID")
    p.add_argument("--would-act", choices=["yes", "no"],
                   help="Persona verdict: would I act on this?")
    p.add_argument("--content",
                   help="Review answering: clear? would I act? missing? where would I stop reading?")
    p.add_argument("--content-file", help="Read review from file")
    p.add_argument("--name", help="Note title")

    p = subparsers.add_parser("add-scores", help="Dimension scores 0-10 for a draft")
    p.add_argument("--draft", required=True, help="Draft ID")
    p.add_argument("--clarity", type=int, help="Clarity 0-10")
    p.add_argument("--concision", type=int, help="Concision 0-10")
    p.add_argument("--voice", type=int, help="Voice-match 0-10")
    p.add_argument("--persuasion", type=int, help="Persuasion 0-10")
    p.add_argument("--overall", type=int, help="Overall 0-10")
    p.add_argument("--content", help="Concrete qualitative feedback (structure/phrasing/ideas)")
    p.add_argument("--content-file", help="Read feedback from file")
    p.add_argument("--name", help="Note title")

    p = subparsers.add_parser("update-piece", help="Update piece attrs / add targets")
    p.add_argument("--id", required=True, help="Piece ID")
    p.add_argument("--status", choices=PIECE_STATUSES)
    p.add_argument("--type")
    p.add_argument("--goal")
    p.add_argument("--audience-summary")
    p.add_argument("--deadline")
    p.add_argument("--add-target", nargs="*", help="Persona IDs to add as targets")

    p = subparsers.add_parser("list-pieces", help="List pieces")
    p.add_argument("--status", choices=PIECE_STATUSES, help="Filter by status")
    p.add_argument("--type", help="Filter by piece type")

    p = subparsers.add_parser("show-piece", help="Piece detail with score trajectory (JSON)")
    p.add_argument("--id", required=True, help="Piece ID")

    p = subparsers.add_parser("report-piece", help="Piece report (Markdown)")
    p.add_argument("--id", required=True, help="Piece ID")

    # --- Quality ---
    subparsers.add_parser("audit", help="Run quality-checks.yaml audit rules")

    args = parser.parse_args()

    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        sys.exit(1)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        # Voice profiling
        "add-sample": cmd_add_sample,
        "list-samples": cmd_list_samples,
        "create-profile": cmd_create_profile,
        "update-profile": cmd_update_profile,
        "show-profile": cmd_show_profile,
        "add-analysis": cmd_add_analysis,
        # Personas
        "add-persona": cmd_add_persona,
        "list-personas": cmd_list_personas,
        # Pieces
        "create-piece": cmd_create_piece,
        "add-note": cmd_add_note,
        "add-draft": cmd_add_draft,
        "add-review": cmd_add_review,
        "add-scores": cmd_add_scores,
        "update-piece": cmd_update_piece,
        "list-pieces": cmd_list_pieces,
        "show-piece": cmd_show_piece,
        "report-piece": cmd_report_piece,
        # Quality
        "audit": cmd_audit,
    }

    try:
        commands[args.command](args)
    except SystemExit:
        raise
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}))
        import traceback

        traceback.print_exc(file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
