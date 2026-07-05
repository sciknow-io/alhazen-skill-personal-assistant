#!/usr/bin/env python3
"""
Career Notebook CLI - Manage the career graph: people, collaborators, projects,
and potential new positions on top of the opportunity pipeline.

This script handles INGESTION and QUERIES. Claude handles SENSEMAKING via the SKILL.md.

Usage:
    python .claude/skills/career/career.py <command> [options]

Commands:
    # Ingestion (script fetches, stores raw content)
    ingest-job          Fetch job posting URL and store raw content as artifact
    add-company         Add a company to track
    add-position        Add a position manually

    # Your Skill Profile
    add-skill           Add/update a skill in your profile
    list-skills         Show your skill profile

    # Artifacts (for Claude's sensemaking)
    list-artifacts      List artifacts pending analysis
    show-artifact       Get artifact content for Claude to read

    # Application Tracking
    update-status       Update application status
    add-note            Create a note about any entity
    add-resource        Add a learning resource
    add-requirement     Add a requirement to a position
    link-resource       Link resource to a skill requirement
    link-collection     Link paper collection to skill requirement(s)
    link-background     Link paper collection to opportunity as background reading
    list-background     List paper collections linked to an opportunity
    link-paper          Link learning resource to a paper

    # Career Graph (people, collaborators, projects)
    add-person          Add a person to the career graph
    list-people         List people with collaboration/contact counts
    show-person         Person detail: contact roles, collaborations, notes
    add-project         Add a career project (open-source, paper, product)
    list-projects       List projects with collaborators
    update-project      Update project role/status/url/priority
    link-collaborator   Link a person to a project or opportunity
    list-collaborators  List collaborations by person or target

    # Legacy migration
    migrate-from-jobhunt  One-shot copy of jhunt-* data into career-* types

    # Queries
    list-pipeline       Show your application pipeline
    show-position       Get position details with all notes
    show-company        Get company details
    show-gaps           Identify skill gaps across applications
    learning-plan       Show prioritized learning resources
    tag                 Tag an entity
    search-tag          Search by tag

    # Cache
    cache-stats         Show cache statistics

Examples:
    # Ingest a job posting (stores raw content for Claude to analyze)
    python .claude/skills/career/career.py ingest-job --url "https://example.com/jobs/123"

    # Add your skills for gap analysis
    python .claude/skills/career/career.py add-skill --name "Python" --level "strong"
    python .claude/skills/career/career.py add-skill --name "Distributed Systems" --level "some"

    # List artifacts needing analysis
    python .claude/skills/career/career.py list-artifacts --status raw

    # Show artifact content (for Claude to read and extract)
    python .claude/skills/career/career.py show-artifact --id "artifact-abc123"

    # Show pipeline
    python .claude/skills/career/career.py list-pipeline --status interviewing

Environment:
    TYPEDB_HOST       TypeDB server host (default: localhost)
    TYPEDB_PORT       TypeDB server port (default: 1729)
    TYPEDB_DATABASE   Database name (default: alhazen_notebook)
    ALHAZEN_CACHE_DIR File cache directory (default: ~/.alhazen/cache)
"""

import argparse
import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup

    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print(
        "Warning: requests/beautifulsoup4 not installed. Install with: pip install requests beautifulsoup4",
        file=sys.stderr,
    )

try:
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB

    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print(
        "Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=3.8.0'",
        file=sys.stderr,
    )

# ---------------------------------------------------------------------------
# Cache utilities (inlined — no external package needed)
# ---------------------------------------------------------------------------

_CACHE_THRESHOLD = 50 * 1024  # 50KB

_MIME_TYPE_MAP = {
    "text/html": ("html", "html"),
    "application/xhtml+xml": ("html", "html"),
    "application/pdf": ("pdf", "pdf"),
    "image/png": ("image", "png"),
    "image/jpeg": ("image", "jpg"),
    "image/gif": ("image", "gif"),
    "image/webp": ("image", "webp"),
    "image/svg+xml": ("image", "svg"),
    "application/json": ("json", "json"),
    "text/plain": ("text", "txt"),
    "text/markdown": ("text", "md"),
    "text/csv": ("text", "csv"),
    "application/xml": ("text", "xml"),
    "text/xml": ("text", "xml"),
}


def get_cache_dir():
    cache_env = os.getenv("ALHAZEN_CACHE_DIR")
    cache_dir = Path(cache_env).expanduser() if cache_env else Path.home() / ".alhazen" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def should_cache(content):
    if isinstance(content, str):
        content = content.encode("utf-8")
    return len(content) >= _CACHE_THRESHOLD


def save_to_cache(artifact_id, content, mime_type):
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = content
    type_dir, ext = _MIME_TYPE_MAP.get(mime_type, ("other", "bin"))
    cache_dir = get_cache_dir()
    type_path = cache_dir / type_dir
    type_path.mkdir(parents=True, exist_ok=True)
    filename = f"{artifact_id}.{ext}"
    full_path = type_path / filename
    full_path.write_bytes(content_bytes)
    return {
        "cache_path": f"{type_dir}/{filename}",
        "file_size": len(content_bytes),
        "content_hash": hashlib.sha256(content_bytes).hexdigest(),
        "full_path": str(full_path),
    }


def load_from_cache_text(cache_path, encoding="utf-8"):
    return (get_cache_dir() / cache_path).read_bytes().decode(encoding)


def get_cache_stats():
    cache_dir = get_cache_dir()
    stats = {"cache_dir": str(cache_dir), "total_files": 0, "total_size": 0, "by_type": {}}
    if not cache_dir.exists():
        return stats
    for type_dir in cache_dir.iterdir():
        if type_dir.is_dir():
            type_stats = {"count": 0, "size": 0}
            for f in type_dir.iterdir():
                if f.is_file():
                    type_stats["count"] += 1
                    type_stats["size"] += f.stat().st_size
            if type_stats["count"] > 0:
                stats["by_type"][type_dir.name] = type_stats
                stats["total_files"] += type_stats["count"]
                stats["total_size"] += type_stats["size"]
    return stats


def format_size(size_bytes):
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


CACHE_AVAILABLE = True


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


def get_attr(entity: dict, attr_name: str, default=None):
    """Safely extract attribute value from TypeDB 3.x fetch result.

    TypeDB 3.x fetch returns plain Python dicts directly.
    """
    return entity.get(attr_name, default)


def get_timestamp() -> str:
    """Get current timestamp for TypeDB."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def resolve_content(args):
    """Resolve content from --content or --content-file. Mutually exclusive."""
    if getattr(args, 'content_file', None):
        with open(args.content_file, "r") as f:
            return f.read()
    return getattr(args, 'content', None)


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


def fetch_url_content(url: str) -> tuple[str, str]:
    """
    Fetch URL and return (title, text_content).

    Returns basic parsed content - Claude will do the intelligent extraction.
    """
    if not REQUESTS_AVAILABLE:
        return "", ""

    headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        title = soup.title.string if soup.title else ""

        # Get text content
        text = soup.get_text(separator="\n", strip=True)

        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)

        # Limit content size
        if len(text) > 50000:
            text = text[:50000] + "\n... [truncated]"

        return title, text

    except Exception as e:
        print(f"Error fetching URL: {e}", file=sys.stderr)
        return "", ""


def extract_company_from_url(url: str) -> str:
    """Try to extract company name from URL domain."""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    # Remove common prefixes
    for prefix in ["www.", "jobs.", "careers.", "boards.greenhouse.io", "jobs.lever.co"]:
        if domain.startswith(prefix):
            domain = domain[len(prefix) :]

    # Extract main domain part
    parts = domain.split(".")
    if len(parts) >= 2:
        return parts[0].title()
    return domain.title()


# =============================================================================
# COMMAND IMPLEMENTATIONS
# =============================================================================


def cmd_ingest_job(args):
    """
    Ingest a job position — from a URL or manually.

    With --url: fetches the posting, stores raw content as artifact, creates position.
    With --title (no URL): creates position manually without fetching.

    In both cases: links company, sets initial status,
    adds tags, links to seeker pipeline, and embeds into Qdrant.
    """
    url = getattr(args, 'url', None)
    title_arg = getattr(args, 'title', None)

    if not url and not title_arg:
        print(json.dumps({"success": False, "error": "Either --url or --title is required"}))
        return

    # --- URL fetch (if provided) ---
    content = None
    fetched_title = None
    artifact_id = None
    cache_result = None

    if url:
        if not REQUESTS_AVAILABLE:
            print(json.dumps({"success": False, "error": "requests/beautifulsoup4 not installed"}))
            return
        fetched_title, content = fetch_url_content(url)
        if not content:
            print(json.dumps({"success": False, "error": "Could not fetch URL content"}))
            return
        artifact_id = generate_id("artifact")

    # --- Determine position name ---
    position_name = title_arg or fetched_title or (f"Job posting from {url[:50]}" if url else "Untitled Position")

    # --- Generate IDs ---
    position_id = getattr(args, 'id', None) or generate_id("position")
    timestamp = get_timestamp()

    with get_driver() as driver:
        # --- Create position entity ---
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            position_query = f'''insert $p isa career-position,
                has id "{position_id}",
                has name "{escape_string(position_name)}",
                has career-opportunity-status "researching",
                has created-at {timestamp}'''

            if url:
                position_query += f', has career-job-url "{escape_string(url)}"'
            if args.priority:
                position_query += f', has career-priority-level "{args.priority}"'
            if getattr(args, 'location', None):
                position_query += f', has alh-location "{escape_string(args.location)}"'
            if getattr(args, 'remote_policy', None):
                position_query += f', has career-remote-policy "{args.remote_policy}"'
            if getattr(args, 'salary', None):
                position_query += f', has career-salary-range "{escape_string(args.salary)}"'
            if getattr(args, 'deadline', None):
                position_query += f", has career-deadline {parse_date(args.deadline)}"

            position_query += ";"
            tx.query(position_query).resolve()
            tx.commit()

        # --- Create artifact (URL mode only) ---
        if url and content and artifact_id:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                if CACHE_AVAILABLE and should_cache(content):
                    cache_result = save_to_cache(
                        artifact_id=artifact_id,
                        content=content,
                        mime_type="text/html",
                    )
                    artifact_query = f'''insert $a isa career-job-description,
                        has id "{artifact_id}",
                        has name "Job Description: {escape_string(position_name)}",
                        has cache-path "{cache_result['cache_path']}",
                        has mime-type "text/html",
                        has file-size {cache_result['file_size']},
                        has content-hash "{cache_result['content_hash']}",
                        has source-uri "{escape_string(url)}",
                        has created-at {timestamp};'''
                else:
                    artifact_query = f'''insert $a isa career-job-description,
                        has id "{artifact_id}",
                        has name "Job Description: {escape_string(position_name)}",
                        has content "{escape_string(content)}",
                        has source-uri "{escape_string(url)}",
                        has created-at {timestamp};'''
                tx.query(artifact_query).resolve()
                tx.commit()

            # Link artifact to position
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $a isa career-job-description, has id "{artifact_id}";
                    $p isa career-position, has id "{position_id}";
                insert (alh-artifact: $a, referent: $p) isa alh-representation;''').resolve()
                tx.commit()

        # --- Link to company (find-or-create) ---
        if getattr(args, 'company', None):
            company_name = args.company.strip()
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                existing = list(tx.query(f'''match
                    $c isa career-company, has id $cid, has name $cn;
                fetch {{ "id": $cid, "name": $cn }};''').resolve())

                company_id_linked = None
                for co in existing:
                    if co["name"].lower() == company_name.lower():
                        company_id_linked = co["id"]
                        break

                if not company_id_linked:
                    company_id_linked = generate_id("company")
                    tx.query(f'''insert $c isa career-company,
                        has id "{company_id_linked}",
                        has name "{escape_string(company_name)}",
                        has created-at {timestamp};''').resolve()

                tx.query(f'''match
                    $p isa career-position, has id "{position_id}";
                    $c isa career-company, has id "{company_id_linked}";
                insert (position: $p, employer: $c) isa career-position-at-company;''').resolve()
                tx.commit()

        # --- Set initial opportunity status ---
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match $p isa career-position, has id "{position_id}";
            insert $p has career-opportunity-status "researching";''').resolve()
            tx.commit()

        # --- Add tags ---
        if getattr(args, 'tags', None):
            for tag_name in args.tags:
                tag_id = generate_id("tag")
                with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                    existing_tag = list(tx.query(
                        f'match $t isa alh-tag, has name "{tag_name}"; fetch {{ "id": $t.id }};'
                    ).resolve())

                if not existing_tag:
                    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                        tx.query(
                            f'insert $t isa alh-tag, has id "{tag_id}", has name "{tag_name}";'
                        ).resolve()
                        tx.commit()

                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(f'''match
                        $p isa career-position, has id "{position_id}";
                        $t isa alh-tag, has name "{tag_name}";
                    insert (tagged-entity: $p, tag: $t) isa alh-tagging;''').resolve()
                    tx.commit()

    # --- Prepare output ---
    output = {
        "success": True,
        "position_id": position_id,
        "message": "Position created.",
    }

    if artifact_id:
        output["artifact_id"] = artifact_id
        output["url"] = url
        output["content_length"] = len(content)
        output["status"] = "raw"
        output["message"] = "Job posting ingested. Artifact stored - ask Claude to 'analyze this job posting' for sensemaking."
        if cache_result:
            output["storage"] = "cache"
            output["cache_path"] = cache_result["cache_path"]
        else:
            output["storage"] = "inline"

    # --- Link to active job-seeker role ---
    try:
        with get_driver() as d:
            _link_opportunity_to_seeker(d, position_id)
    except Exception:
        pass  # seeker role may not exist yet

    # --- Auto-embed into Qdrant ---
    try:
        import subprocess
        subprocess.run(
            ["uv", "run", "python", os.path.join(os.path.dirname(__file__), "embedding_map.py"), "embed"],
            capture_output=True, cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            timeout=30,
        )
    except Exception:
        pass  # embedding is non-critical

    print(json.dumps(output, indent=2))


def cmd_add_company(args):
    """Add a company to track."""
    company_id = args.id or generate_id("company")
    timestamp = get_timestamp()

    query = f'''insert $c isa career-company,
        has id "{company_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.url:
        query += f', has alh-company-url "{escape_string(args.url)}"'
    if args.linkedin:
        query += f', has alh-linkedin-url "{escape_string(args.linkedin)}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'
    if args.location:
        query += f', has alh-location "{escape_string(args.location)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

    print(json.dumps({"success": True, "company_id": company_id, "name": args.name}))


def cmd_add_position(args):
    """Deprecated — redirects to ingest-job."""
    # Map add-position args to ingest-job args
    args.url = getattr(args, 'url', None)
    args.tags = None
    args.remote_policy = getattr(args, 'career_remote_policy', None)
    if not args.url and not getattr(args, 'title', None):
        print(json.dumps({"success": False, "error": "Either --url or --title is required"}))
        return
    cmd_ingest_job(args)


def cmd_update_status(args):
    """Update application status for a position."""

    with get_driver() as driver:
        # Update status attribute directly on the position
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            # Remove old status if present
            try:
                tx.query(
                    f'match $p isa career-position, has id "{args.position}", has career-opportunity-status $old; delete has $old of $p;'
                ).resolve()
            except Exception:
                pass
            tx.query(
                f'match $p isa career-position, has id "{args.position}"; insert $p has career-opportunity-status "{args.status}";'
            ).resolve()
            # Set applied date if provided
            if args.date:
                try:
                    tx.query(
                        f'match $p isa career-position, has id "{args.position}", has career-applied-date $old; delete has $old of $p;'
                    ).resolve()
                except Exception:
                    pass
                tx.query(
                    f'match $p isa career-position, has id "{args.position}"; insert $p has career-applied-date {parse_date(args.date)};'
                ).resolve()
            tx.commit()

    print(
        json.dumps(
            {
                "success": True,
                "position_id": args.position,
                "status": args.status,
            }
        )
    )


def cmd_set_short_name(args):
    """Set short display name for a position."""
    with get_driver() as driver:
        # Check if position exists and if it already has a career-short-name
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            check_query = f'''match
                $p isa career-position, has id "{args.position}";
            fetch {{ "career-short-name": $p.career-short-name }};'''
            existing = list(tx.query(check_query).resolve())

        if not existing:
            print(json.dumps({"success": False, "error": "Position not found"}))
            return

        has_existing = bool(existing[0].get("career-short-name"))

        if has_existing:
            # Delete old career-short-name and add new one
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                delete_query = f'''match
                    $p isa career-position, has id "{args.position}", has career-short-name $sn;
                delete $p has $sn;'''
                tx.query(delete_query).resolve()
                tx.commit()

        # Add new career-short-name
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            insert_query = f'''match
                $p isa career-position, has id "{args.position}";
            insert $p has career-short-name "{escape_string(args.name)}";'''
            tx.query(insert_query).resolve()
            tx.commit()

    print(
        json.dumps(
            {
                "success": True,
                "position_id": args.position,
                "short_name": args.name,
            }
        )
    )


def cmd_add_note(args):
    """Create a note about any entity."""
    content = resolve_content(args)
    if not content:
        print(json.dumps({"success": False, "error": "Provide either --content or --content-file"}))
        return

    note_id = args.id or generate_id("note")
    timestamp = get_timestamp()

    # Map note type to TypeDB type
    type_map = {
        "research": "career-research-note",
        "interview": "career-interview-note",
        "strategy": "career-strategy-note",
        "skill-gap": "career-skill-gap-note",
        "fit-analysis": "career-fit-analysis-note",
        "interaction": "career-interaction-note",
        "opp-summary": "career-opp-summary-note",
        "primer": "career-primer-note",
        "relationship": "career-relationship-note",
        "general": "note",
    }

    note_type = type_map.get(args.type, "note")

    query = f'''insert $n isa {note_type},
        has id "{note_id}",
        has content "{escape_string(content)}",
        has created-at {timestamp}'''

    if args.name:
        query += f', has name "{escape_string(args.name)}"'
    if args.confidence:
        query += f", has confidence {args.confidence}"

    # Type-specific attributes
    if args.type == "interaction":
        if getattr(args, 'alh_interaction_type', None):
            query += f', has alh-interaction-type "{args.alh_interaction_type}"'
        if getattr(args, 'alh_interaction_date', None):
            query += f", has alh-interaction-date {parse_date(args.alh_interaction_date)}"

    if args.type == "interview" and getattr(args, 'career_interview_date', None):
        query += f", has career-interview-date {parse_date(args.career_interview_date)}"

    if args.type == "fit-analysis":
        if getattr(args, 'career_fit_score', None):
            query += f", has career-fit-score {args.career_fit_score}"
        if getattr(args, 'career_fit_summary', None):
            query += f', has career-fit-summary "{escape_string(args.career_fit_summary)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Link to subject
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            about_query = f'''match
                $n isa alh-note, has id "{note_id}";
                $s isa alh-identifiable-entity, has id "{args.about}";
            insert (note: $n, subject: $s) isa alh-aboutness;'''
            tx.query(about_query).resolve()
            tx.commit()

        # Add tags
        if args.tags:
            for tag_name in args.tags:
                tag_id = generate_id("tag")
                with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                    tag_check = f'match $t isa alh-tag, has name "{tag_name}"; fetch {{ "id": $t.id }};'
                    existing_tag = list(tx.query(tag_check).resolve())

                if not existing_tag:
                    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                        tx.query(
                            f'insert $t isa alh-tag, has id "{tag_id}", has name "{tag_name}";'
                        ).resolve()
                        tx.commit()

                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(f'''match
                        $n isa alh-note, has id "{note_id}";
                        $t isa alh-tag, has name "{tag_name}";
                    insert (tagged-entity: $n, tag: $t) isa alh-tagging;''').resolve()
                    tx.commit()

    print(json.dumps({"success": True, "note_id": note_id, "about": args.about, "type": args.type}))


def cmd_upsert_summary(args):
    """Create or overwrite the opportunity summary."""
    content = resolve_content(args)
    if not content:
        print(json.dumps({"success": False, "error": "Provide either --content or --content-file"}))
        return

    timestamp = get_timestamp()

    with get_driver() as driver:
        # Check for existing brief
        existing_id = None
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            r = list(tx.query(f'''match
                $s isa alh-identifiable-entity, has id "{args.about}";
                (note: $n, subject: $s) isa alh-aboutness;
                $n isa career-opp-summary-note, has id $nid;
            fetch {{ "nid": $nid }};''').resolve())
            if r:
                existing_id = r[0]["nid"]

        if existing_id:
            # Delete old content, insert new
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $n isa career-opp-summary-note, has id "{existing_id}", has content $c;
                delete has $c of $n;''').resolve()
                tx.commit()
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match $n isa career-opp-summary-note, has id "{existing_id}";
                insert $n has content "{escape_string(content)}";''').resolve()
                tx.commit()
            # Update created-at to track last update
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $n isa career-opp-summary-note, has id "{existing_id}", has created-at $t;
                delete has $t of $n;''').resolve()
                tx.commit()
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match $n isa career-opp-summary-note, has id "{existing_id}";
                insert $n has created-at {timestamp};''').resolve()
                tx.commit()
            note_id = existing_id
            action = "updated"
        else:
            # Create new brief
            note_id = generate_id("oppsummary")
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''insert $n isa career-opp-summary-note,
                    has id "{note_id}",
                    has name "brief",
                    has content "{escape_string(content)}",
                    has created-at {timestamp};''').resolve()
                tx.commit()
            # Link to subject
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $n isa career-opp-summary-note, has id "{note_id}";
                    $s isa alh-identifiable-entity, has id "{args.about}";
                insert (note: $n, subject: $s) isa alh-aboutness;''').resolve()
                tx.commit()
            action = "created"

    print(json.dumps({"success": True, "note_id": note_id, "about": args.about, "action": action}))


def cmd_regenerate_summary(args):
    """Fetch all notes + metadata for an opportunity so the agent can write a summary."""
    opp_id = args.about

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Determine opportunity type
            opp_meta = None
            for otype in ["career-position", "career-engagement", "career-venture", "career-lead", "career-project"]:
                r = list(tx.query(f'''match $o isa {otype}, has id "{opp_id}", has name $n;
                    fetch {{ "name": $n }};''').resolve())
                if r:
                    opp_meta = {"id": opp_id, "type": otype.replace("career-", ""), "name": r[0]["name"]}
                    break

            if not opp_meta:
                print(json.dumps({"success": False, "error": f"Opportunity {opp_id} not found"}))
                return

            otype_full = f"career-{opp_meta['type']}"

            # Fetch optional attributes
            for attr, key in [("career-short-name", "short_name"), ("career-priority-level", "priority"),
                              ("created-at", "created_at"), ("career-job-url", "job_url"),
                              ("career-salary-range", "salary"), ("location", "location"),
                              ("career-remote-policy", "remote_policy")]:
                try:
                    r = list(tx.query(f'match $o isa {otype_full}, has id "{opp_id}", has {attr} $v; fetch {{ "v": $v }};').resolve())
                    if r:
                        opp_meta[key] = str(r[0]["v"])
                except:
                    pass

            # Status
            try:
                s = list(tx.query(f'match $o isa {otype_full}, has id "{opp_id}", has career-opportunity-status $s; fetch {{ "s": $s }};').resolve())
                if s:
                    opp_meta["status"] = s[0]["s"]
            except:
                pass

            # Company
            try:
                for rel in ["career-position-at-company", "career-opportunity-at-organization"]:
                    role = "employer" if "position" in rel else "organization"
                    co = list(tx.query(f'''match $o isa {otype_full}, has id "{opp_id}";
                        ({rel.split("-")[0]}: $o, {role}: $c) isa {rel};
                    fetch {{ "name": $c.name }};''').resolve())
                    if co:
                        opp_meta["company"] = co[0]["name"]
                        break
            except:
                pass

            # All notes (grouped by type)
            notes = {}
            note_types = [
                ("career-research-note", "research"),
                ("career-fit-analysis-note", "fit-analysis"),
                ("career-strategy-note", "strategy"),
                ("career-skill-gap-note", "skill-gap"),
                ("career-interview-note", "interview"),
                ("career-interaction-note", "interaction"),
                ("career-opp-summary-note", "current-summary"),
                ("note", "general"),
            ]
            for ntype, label in note_types:
                try:
                    results = list(tx.query(f'''match
                        $o isa {otype_full}, has id "{opp_id}";
                        (note: $n, subject: $o) isa alh-aboutness;
                        $n isa {ntype}, has content $c;
                    fetch {{ "content": $c }};''').resolve())
                    if results:
                        notes[label] = [r["content"] for r in results]
                except:
                    pass

            # Contacts linked to this opportunity
            contacts = []
            try:
                contact_r = list(tx.query(f'''match
                    $o isa {otype_full}, has id "{opp_id}";
                    (note: $n, subject: $o) isa alh-aboutness;
                    $n isa career-interaction-note, has content $c;
                fetch {{ "content": $c }};''').resolve())
                # Also try direct interaction links
            except:
                pass

    result = {
        "success": True,
        "opportunity": opp_meta,
        "notes": notes,
        "note_count": sum(len(v) for v in notes.values()),
    }
    print(json.dumps(result, default=str))


def cmd_add_resource(args):
    """Add a learning resource."""
    resource_id = args.id or generate_id("resource")
    timestamp = get_timestamp()

    query = f'''insert $r isa career-learning-resource,
        has id "{resource_id}",
        has name "{escape_string(args.name)}",
        has career-resource-type "{args.type}",
        has career-completion-status "not-started",
        has created-at {timestamp}'''

    if args.url:
        query += f', has career-resource-url "{escape_string(args.url)}"'
    if args.hours:
        query += f", has career-estimated-hours {args.hours}"
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Tag with skills
        if args.skills:
            for skill in args.skills:
                tag_id = generate_id("tag")
                tag_name = f"skill:{skill}"

                with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                    tag_check = f'match $t isa alh-tag, has name "{tag_name}"; fetch {{ "id": $t.id }};'
                    existing_tag = list(tx.query(tag_check).resolve())

                if not existing_tag:
                    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                        tx.query(
                            f'insert $t isa alh-tag, has id "{tag_id}", has name "{tag_name}";'
                        ).resolve()
                        tx.commit()

                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(f'''match
                        $r isa career-learning-resource, has id "{resource_id}";
                        $t isa alh-tag, has name "{tag_name}";
                    insert (tagged-entity: $r, tag: $t) isa alh-tagging;''').resolve()
                    tx.commit()

    print(
        json.dumps(
            {"success": True, "resource_id": resource_id, "name": args.name, "type": args.type}
        )
    )


def cmd_link_resource(args):
    """Link a learning resource to a skill requirement."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            link_query = f'''match
                $r isa career-learning-resource, has id "{args.resource}";
                $req isa career-requirement, has id "{args.requirement}";
            insert (resource: $r, requirement: $req) isa career-addresses-requirement;'''
            tx.query(link_query).resolve()
            tx.commit()

    print(json.dumps({"success": True, "resource": args.resource, "requirement": args.requirement}))


def cmd_link_collection(args):
    """Link a paper collection to skill requirement(s).

    Bridges scilit collections to career skill gaps via career-addresses-requirement.
    Use --requirement for a specific requirement, or --skill to link to all
    matching requirements across positions.
    """
    with get_driver() as driver:
        if args.requirement:
            # Link to specific requirement
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                link_query = f'''match
                    $c isa alh-collection, has id "{args.collection}";
                    $req isa career-requirement, has id "{args.requirement}";
                insert (resource: $c, requirement: $req) isa career-addresses-requirement;'''
                tx.query(link_query).resolve()
                tx.commit()
            print(json.dumps({
                "success": True,
                "collection": args.collection,
                "requirement": args.requirement,
            }))

        elif args.skill:
            # Link to all requirements matching skill name
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                find_query = f'''match
                    $req isa career-requirement, has career-skill-name "{escape_string(args.skill)}";
                fetch {{ "id": $req.id }};'''
                reqs = list(tx.query(find_query).resolve())

            if not reqs:
                print(json.dumps({
                    "success": False,
                    "error": f"No requirements found with career-skill-name '{args.skill}'",
                }))
                return

            linked = []
            for r in reqs:
                req_id = r.get("id", "")
                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    link_query = f'''match
                        $c isa alh-collection, has id "{args.collection}";
                        $req isa career-requirement, has id "{req_id}";
                    insert (resource: $c, requirement: $req) isa career-addresses-requirement;'''
                    tx.query(link_query).resolve()
                    tx.commit()
                linked.append(req_id)

            print(json.dumps({
                "success": True,
                "collection": args.collection,
                "skill": args.skill,
                "linked_requirements": linked,
                "count": len(linked),
            }))
        else:
            print(json.dumps({
                "success": False,
                "error": "Must specify either --requirement or --skill",
            }))


def cmd_link_background(args):
    """Link a paper collection to a job opportunity as background reading."""
    collection_id = args.collection
    opportunity_id = args.opportunity
    description = getattr(args, "description", "") or ""

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            cols = list(tx.query(f'''
                match $c isa alh-collection, has id "{collection_id}";
                fetch {{ "id": $c.id, "name": $c.name }};
            ''').resolve())
            if not cols:
                print(json.dumps({"success": False, "error": f"Collection '{collection_id}' not found"}))
                return

            opps = list(tx.query(f'''
                match $o isa career-opportunity, has id "{opportunity_id}";
                fetch {{ "id": $o.id, "name": $o.name }};
            ''').resolve())
            if not opps:
                print(json.dumps({"success": False, "error": f"Opportunity '{opportunity_id}' not found"}))
                return

        ts = get_timestamp()
        desc_clause = f', has description "{escape_string(description)}"' if description else ""
        prov_clause = ', has provenance "link-background"'

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''
                match $o isa career-opportunity, has id "{opportunity_id}";
                      $c isa alh-collection, has id "{collection_id}";
                insert (opportunity: $o, reading-material: $c) isa career-background-reading,
                    has created-at {ts}{desc_clause}{prov_clause};
            ''').resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "opportunity_id": opportunity_id,
        "collection_id": collection_id,
        "description": description,
        "message": f"Linked collection '{cols[0]['name']}' to opportunity '{opps[0]['name']}' as background reading",
    }))


def cmd_list_background(args):
    """List paper collections linked to a job opportunity as background reading."""
    opportunity_id = args.opportunity

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''
                match $o isa career-opportunity, has id "{opportunity_id}";
                      $c isa alh-collection;
                      (opportunity: $o, reading-material: $c) isa career-background-reading;
                fetch {{
                    "collection-id": $c.id,
                    "collection-name": $c.name
                }};
            ''').resolve())

    print(json.dumps({
        "success": True,
        "opportunity_id": opportunity_id,
        "collections": results,
        "count": len(results),
    }))


def cmd_link_paper(args):
    """Record that a learning resource cites a scilit-paper, as a SOFT reference.

    The paper lives in the alh_deep_research database (scientific-literature);
    TypeDB relations cannot cross databases, so instead of an alh-citation-reference
    relation we store the paper id on the resource (career-cited-paper-id) plus an
    optional human-readable ref (career-cited-paper-ref, e.g. DOI/title). Resolve
    the id against alh_deep_research in the app/dashboard layer.
    """
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            exists = list(tx.query(
                f'match $res isa career-learning-resource, has id "{escape_string(args.resource)}";'
                f' reduce $c = count;').resolve())[0].get("c").try_get_integer()
        if not exists:
            print(json.dumps({"success": False, "error": f"learning resource not found: {args.resource}"}))
            return
        ref = getattr(args, "ref", None)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            # replace any prior soft-ref, then set the new one
            tx.query(f'match $res isa career-learning-resource, has id "{escape_string(args.resource)}",'
                     f' has career-cited-paper-id $old; delete has $old of $res;').resolve()
            set_q = (f'match $res isa career-learning-resource, has id "{escape_string(args.resource)}";'
                     f' insert $res has career-cited-paper-id "{escape_string(args.paper)}"')
            if ref:
                set_q += f', has career-cited-paper-ref "{escape_string(ref)}"'
            tx.query(set_q + ";").resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "resource": args.resource,
        "paper": args.paper,
        "note": "soft reference (paper lives in alh_deep_research; no cross-db relation)",
    }))


def cmd_delete_position(args):
    """Delete a position and all its related data."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            check = list(tx.query(f'''match $p isa career-position, has id "{args.id}";
            fetch {{ "name": $p.name }};''').resolve())
        if not check:
            print(json.dumps({"success": False, "error": "Position not found"}))
            return

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            # Delete the position entity (TypeDB cascades owned attributes)
            tx.query(f'''match $p isa career-position, has id "{args.id}";
            delete $p;''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "deleted": args.id}))


# =============================================================================
# OPPORTUNITY MODEL COMMANDS
# =============================================================================


def _link_opportunity_to_company(driver, opportunity_id, company_id):
    """Link an opportunity to a company via career-opportunity-at-organization."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        rel_query = f'''match
            $o isa career-opportunity, has id "{opportunity_id}";
            $c isa career-company, has id "{company_id}";
        insert (opportunity: $o, organization: $c) isa career-opportunity-at-organization;'''
        tx.query(rel_query).resolve()
        tx.commit()


def _link_opportunity_to_seeker(driver, opportunity_id):
    """Link an opportunity to the active job-seeker role via career-seeker-pipeline."""
    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(f'''match
            $role isa career-agent-role, has alh-role-status "active";
            $opp isa career-opportunity, has id "{escape_string(opportunity_id)}";
        insert (seeker: $role, opportunity: $opp) isa career-seeker-pipeline;''').resolve()
        tx.commit()


def cmd_add_engagement(args):
    """Add a consulting/service engagement opportunity."""
    engagement_id = args.id or generate_id("engagement")
    timestamp = get_timestamp()

    query = f'''insert $e isa career-engagement,
        has id "{engagement_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.type:
        query += f', has career-engagement-type "{args.type}"'
    if args.rate:
        query += f', has career-rate-info "{escape_string(args.rate)}"'
    if args.status:
        query += f', has career-opportunity-status "{args.status}"'
    if args.priority:
        query += f', has career-priority-level "{args.priority}"'
    if args.deadline:
        query += f', has career-deadline {parse_date(args.deadline)}'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        if args.company_id:
            _link_opportunity_to_company(driver, engagement_id, args.company_id)

        try:
            _link_opportunity_to_seeker(driver, engagement_id)
        except Exception:
            pass

    print(json.dumps({"success": True, "engagement_id": engagement_id, "name": args.name}))


def cmd_add_venture(args):
    """Add a startup/advisory/equity venture opportunity."""
    venture_id = args.id or generate_id("venture")
    timestamp = get_timestamp()

    query = f'''insert $v isa career-venture,
        has id "{venture_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.stage:
        query += f', has career-venture-stage "{args.stage}"'
    if args.equity_type:
        query += f', has career-equity-type "{args.equity_type}"'
    if args.status:
        query += f', has career-opportunity-status "{args.status}"'
    if args.priority:
        query += f', has career-priority-level "{args.priority}"'
    if args.deadline:
        query += f', has career-deadline {parse_date(args.deadline)}'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        if args.company_id:
            _link_opportunity_to_company(driver, venture_id, args.company_id)

        try:
            _link_opportunity_to_seeker(driver, venture_id)
        except Exception:
            pass

    print(json.dumps({"success": True, "venture_id": venture_id, "name": args.name}))


def cmd_add_lead(args):
    """Add an early-stage networking lead."""
    lead_id = args.id or generate_id("lead")
    timestamp = get_timestamp()

    query = f'''insert $l isa career-lead,
        has id "{lead_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.status:
        query += f', has career-opportunity-status "{args.status}"'
    if args.priority:
        query += f', has career-priority-level "{args.priority}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        try:
            _link_opportunity_to_seeker(driver, lead_id)
        except Exception:
            pass

    print(json.dumps({"success": True, "lead_id": lead_id, "name": args.name}))


def cmd_update_opportunity(args):
    """Update status, stage, or priority of any opportunity."""
    updates = []
    if args.status:
        updates.append(("career-opportunity-status", args.status))
    if args.stage:
        updates.append(("career-venture-stage", args.stage))
    if args.priority:
        updates.append(("career-priority-level", args.priority))

    if not updates:
        print(json.dumps({"success": False, "error": "No updates specified"}))
        return

    with get_driver() as driver:
        for attr, value in updates:
            # Check if attribute already exists
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                check = list(tx.query(f'''match
                    $o isa career-opportunity, has id "{args.id}", has {attr} $v;
                fetch {{ "v": $v.{attr} }};''').resolve())

            if check:
                # Delete old value then insert new
                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(f'''match
                        $o isa career-opportunity, has id "{args.id}", has {attr} $v;
                    delete has $v of $o;''').resolve()
                    tx.commit()

            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $o isa career-opportunity, has id "{args.id}";
                insert $o has {attr} "{value}";''').resolve()
                tx.commit()

    print(json.dumps({"success": True, "id": args.id, "updates": dict(updates)}))


def cmd_show_opportunity(args):
    """Show details for any opportunity subtype."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Try each subtype in order
            opp = None
            opp_type = None
            for otype in ["career-position", "career-engagement", "career-venture", "career-lead", "career-project"]:
                q = f'''match $o isa {otype}, has id "{args.id}";
                fetch {{
                    "id": $o.id,
                    "name": $o.name,
                    "description": $o.description,
                    "career-opportunity-status": $o.career-opportunity-status,
                    "career-priority-level": $o.career-priority-level,
                    "deadline": $o.career-deadline
                }};'''
                results = list(tx.query(q).resolve())
                if results:
                    opp = results[0]
                    opp_type = otype
                    break

            if not opp:
                print(json.dumps({"success": False, "error": "Opportunity not found"}))
                return

            # Type-specific attributes
            if opp_type == "career-position":
                extra_q = f'''match $o isa career-position, has id "{args.id}";
                fetch {{
                    "career-job-url": $o.career-job-url,
                    "career-short-name": $o.career-short-name,
                    "career-salary-range": $o.career-salary-range,
                    "location": $o.alh-location,
                    "career-remote-policy": $o.career-remote-policy
                }};'''
                extras = list(tx.query(extra_q).resolve())
                if extras:
                    opp.update(extras[0])

            elif opp_type == "career-engagement":
                extra_q = f'''match $o isa career-engagement, has id "{args.id}";
                fetch {{
                    "career-short-name": $o.career-short-name,
                    "career-engagement-type": $o.career-engagement-type,
                    "career-rate-info": $o.career-rate-info
                }};'''
                extras = list(tx.query(extra_q).resolve())
                if extras:
                    opp.update(extras[0])

            elif opp_type == "career-venture":
                extra_q = f'''match $o isa career-venture, has id "{args.id}";
                fetch {{
                    "career-short-name": $o.career-short-name,
                    "career-venture-stage": $o.career-venture-stage,
                    "career-equity-type": $o.career-equity-type
                }};'''
                extras = list(tx.query(extra_q).resolve())
                if extras:
                    opp.update(extras[0])

            elif opp_type == "career-lead":
                extra_q = f'''match $o isa career-lead, has id "{args.id}";
                fetch {{ "career-short-name": $o.career-short-name }};'''
                extras = list(tx.query(extra_q).resolve())
                if extras:
                    opp.update(extras[0])

            elif opp_type == "career-project":
                extra_q = f'''match $o isa career-project, has id "{args.id}";
                fetch {{
                    "career-short-name": $o.career-short-name,
                    "career-project-role": $o.career-project-role,
                    "career-project-status": $o.career-project-status,
                    "career-project-url": $o.career-project-url
                }};'''
                extras = list(tx.query(extra_q).resolve())
                if extras:
                    opp.update(extras[0])

            # Get linked company via career-opportunity-at-organization
            company_results = []
            # Try opportunity-at-organization first
            try:
                company_q = f'''match
                    $o isa career-opportunity, has id "{args.id}";
                    (opportunity: $o, organization: $c) isa career-opportunity-at-organization;
                fetch {{ "id": $c.id, "name": $c.name }};'''
                company_results = list(tx.query(company_q).resolve())
            except Exception:
                pass
            # Fall back to position-at-company
            if not company_results:
                try:
                    company_q = f'''match
                        $p isa career-position, has id "{args.id}";
                        (position: $p, employer: $c) isa career-position-at-company;
                    fetch {{ "id": $c.id, "name": $c.name }};'''
                    company_results = list(tx.query(company_q).resolve())
                except Exception:
                    pass

            # Get notes
            notes_q = f'''match
                $o isa career-opportunity, has id "{args.id}";
                (note: $n, subject: $o) isa alh-aboutness;
            fetch {{ "id": $n.id, "name": $n.name, "content": $n.content }};'''
            notes_results = list(tx.query(notes_q).resolve())

            # Get background reading collections
            bg_cols = list(tx.query(f'''
                match $o isa career-opportunity, has id "{args.id}";
                      $c isa alh-collection;
                      (opportunity: $o, reading-material: $c) isa career-background-reading;
                fetch {{ "collection-id": $c.id, "collection-name": $c.name }};
            ''').resolve())

            # Fetch descriptions — anon relation + has avoids $var naming issues
            bg_descs = {r["collection-id"]: r["description"]
                        for r in tx.query(f'''
                match $o isa career-opportunity, has id "{args.id}";
                      $c isa alh-collection, has id $cid;
                      (opportunity: $o, reading-material: $c) isa career-background-reading,
                          has description $desc;
                fetch {{ "collection-id": $cid, "description": $desc }};
            ''').resolve()}

            background_reading = []
            for col in bg_cols:
                cid = col["collection-id"]
                item = {"collection-id": cid, "collection-name": col["collection-name"]}
                if cid in bg_descs:
                    item["description"] = bg_descs[cid]
                background_reading.append(item)

            # Get collaborators (career graph)
            collaborators = []
            try:
                collaborators = list(tx.query(f'''match
                    $o isa career-opportunity, has id "{args.id}";
                    (collaborator: $p, work: $o) isa career-collaboration;
                fetch {{ "id": $p.id, "name": $p.name }};''').resolve())
                role_overlay = {r["id"]: r["role"] for r in tx.query(f'''match
                    $o isa career-opportunity, has id "{args.id}";
                    $p isa alh-person, has id $pid;
                    (collaborator: $p, work: $o) isa career-collaboration,
                        has career-collab-role $role;
                fetch {{ "id": $pid, "role": $role }};''').resolve()}
                for c in collaborators:
                    if c["id"] in role_overlay:
                        c["role"] = role_overlay[c["id"]]
            except Exception:
                pass

    print(json.dumps({
        "success": True,
        "type": opp_type,
        "opportunity": opp,
        "company": company_results[0] if company_results else None,
        "notes": notes_results,
        "background_reading": background_reading,
        "collaborators": collaborators,
    }, indent=2, default=str))


def cmd_list_opportunities(args):
    """List opportunities, optionally filtered by type and status."""
    opp_type = args.type or "all"

    type_map = {
        "position": ["career-position"],
        "engagement": ["career-engagement"],
        "venture": ["career-venture"],
        "lead": ["career-lead"],
        "project": ["career-project"],
        "all": ["career-position", "career-engagement", "career-venture", "career-lead", "career-project"],
    }
    types_to_query = type_map.get(opp_type, ["career-position"])

    results = []
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            for otype in types_to_query:
                match_clause = f"match $o isa {otype};"
                if hasattr(args, 'person') and args.person:
                    match_clause += f'''
                    (seeker: $seeker, opportunity: $o) isa career-seeker-pipeline;
                    (bearer: $person, borne-role: $seeker) isa alh-role-bearing;
                    $person has id "{escape_string(args.person)}";'''
                if args.status:
                    match_clause += f'\n$o has career-opportunity-status "{args.status}";'
                if args.priority:
                    match_clause += f'\n$o has career-priority-level "{args.priority}";'

                q = match_clause + """
                fetch {
                    "id": $o.id,
                    "name": $o.name,
                    "career-short-name": $o.career-short-name,
                    "career-opportunity-status": $o.career-opportunity-status,
                    "career-priority-level": $o.career-priority-level
                };"""
                rows = list(tx.query(q).resolve())
                for r in rows:
                    r["_type"] = otype
                results.extend(rows)

            # Get company links for all
            for r in results:
                oid = r.get("id", "")
                if not oid:
                    continue
                # Try both company relation types (positions use position-at-company,
                # other opportunity types use opportunity-at-organization)
                company_name = ""
                for cq in [
                    f'match $o has id "{oid}"; (opportunity: $o, organization: $c) isa career-opportunity-at-organization; fetch {{ "name": $c.name }};',
                    f'match $o has id "{oid}"; (position: $o, employer: $c) isa career-position-at-company; fetch {{ "name": $c.name }};',
                ]:
                    try:
                        cresults = list(tx.query(cq).resolve())
                        if cresults:
                            company_name = cresults[0].get("name", "")
                            break
                    except Exception:
                        continue
                r["company"] = company_name

    opportunities = []
    for r in results:
        opportunities.append({
            "id": r.get("id", ""),
            "type": r.get("_type", "").replace("career-", ""),
            "name": r.get("name", ""),
            "short_name": r.get("career-short-name", ""),
            "status": r.get("career-opportunity-status", ""),
            "priority": r.get("career-priority-level", ""),
            "company": r.get("company", ""),
        })

    print(json.dumps({
        "success": True,
        "opportunities": opportunities,
        "count": len(opportunities),
    }, indent=2))


# =============================================================================
# CAREER GRAPH - PEOPLE, COLLABORATORS, PROJECTS
# =============================================================================


def cmd_add_person(args):
    """Add a person to the career graph (shared alh-person, deliberate synergy with ops)."""
    person_id = args.id or generate_id("person")
    timestamp = get_timestamp()

    query = f'''insert $p isa alh-person,
        has id "{person_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    warnings = []
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Optional identity attributes — attempted separately so a core schema
        # that lacks one of them does not lose the whole insert
        for flag, attr in [("email", "alh-email-address"), ("linkedin", "alh-linkedin-url")]:
            value = getattr(args, flag, None)
            if not value:
                continue
            try:
                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(f'''match
                        $p isa alh-person, has id "{person_id}";
                    insert $p has {attr} "{escape_string(value)}";''').resolve()
                    tx.commit()
            except Exception as e:
                warnings.append(f"{attr}: {e}")

    result = {"success": True, "person_id": person_id, "name": args.name}
    if warnings:
        result["warnings"] = warnings
    print(json.dumps(result))


def cmd_list_people(args):
    """List people in the career graph with collaboration/contact counts."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            rows = list(tx.query('''match $p isa alh-person;
            fetch {
                "id": $p.id,
                "name": $p.name,
                "description": $p.description
            };''').resolve())

            for r in rows:
                pid = r.get("id", "")
                if not pid:
                    continue
                for key, q in [
                    ("collaborations", f'match $p isa alh-person, has id "{pid}"; (collaborator: $p, work: $w) isa career-collaboration; fetch {{ "id": $w.id }};'),
                    ("contact_roles", f'match $p isa alh-person, has id "{pid}"; (contact: $p, opportunity: $o) isa career-contact-for-opportunity; fetch {{ "id": $o.id }};'),
                ]:
                    try:
                        r[key] = len(list(tx.query(q).resolve()))
                    except Exception:
                        r[key] = 0

    people = [{
        "id": r.get("id", ""),
        "name": r.get("name", ""),
        "description": r.get("description", ""),
        "collaborations": r.get("collaborations", 0),
        "contact_roles": r.get("contact_roles", 0),
    } for r in rows]

    print(json.dumps({"success": True, "people": people, "count": len(people)}, indent=2))


def cmd_show_person(args):
    """Show a person: contact roles, collaborations, and relationship notes."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(f'''match $p isa alh-person, has id "{escape_string(args.id)}";
            fetch {{
                "id": $p.id,
                "name": $p.name,
                "description": $p.description,
                "created-at": $p.created-at
            }};''').resolve())

            if not results:
                print(json.dumps({"success": False, "error": "Person not found"}))
                return
            person = results[0]

            # Optional identity attrs (core schema may not own them)
            for attr in ["alh-email-address", "alh-linkedin-url"]:
                try:
                    extra = list(tx.query(f'''match
                        $p isa alh-person, has id "{escape_string(args.id)}", has {attr} $v;
                    fetch {{ "v": $v }};''').resolve())
                    if extra:
                        person[attr] = extra[0]["v"]
                except Exception:
                    pass

            # Contact roles on opportunities
            contact_roles = []
            try:
                contact_roles = list(tx.query(f'''match
                    $p isa alh-person, has id "{escape_string(args.id)}";
                    (contact: $p, opportunity: $o) isa career-contact-for-opportunity;
                fetch {{ "opportunity_id": $o.id, "opportunity_name": $o.name }};''').resolve())
                role_labels = {r["opportunity_id"]: r["role"] for r in tx.query(f'''match
                    $p isa alh-person, has id "{escape_string(args.id)}";
                    $o isa career-opportunity, has id $oid;
                    (contact: $p, opportunity: $o) isa career-contact-for-opportunity,
                        has career-contact-role $role;
                fetch {{ "opportunity_id": $oid, "role": $role }};''').resolve()}
                for cr in contact_roles:
                    if cr["opportunity_id"] in role_labels:
                        cr["role"] = role_labels[cr["opportunity_id"]]
            except Exception:
                pass

            # Collaborations on projects/opportunities
            collaborations = []
            try:
                collaborations = list(tx.query(f'''match
                    $p isa alh-person, has id "{escape_string(args.id)}";
                    (collaborator: $p, work: $w) isa career-collaboration;
                fetch {{ "work_id": $w.id, "work_name": $w.name }};''').resolve())
                for attr, key in [
                    ("career-collab-role", "role"),
                    ("career-collab-strength", "strength"),
                    ("career-collab-since", "since"),
                ]:
                    overlay = {r["work_id"]: r["v"] for r in tx.query(f'''match
                        $p isa alh-person, has id "{escape_string(args.id)}";
                        $w isa career-opportunity, has id $wid;
                        (collaborator: $p, work: $w) isa career-collaboration, has {attr} $v;
                    fetch {{ "work_id": $wid, "v": $v }};''').resolve()}
                    for c in collaborations:
                        if c["work_id"] in overlay:
                            c[key] = overlay[c["work_id"]]
            except Exception:
                pass

            # Notes about this person (relationship notes flagged)
            notes = []
            try:
                notes = list(tx.query(f'''match
                    $p isa alh-person, has id "{escape_string(args.id)}";
                    (note: $n, subject: $p) isa alh-aboutness;
                fetch {{ "id": $n.id, "name": $n.name, "content": $n.content, "created-at": $n.created-at }};''').resolve())
                rel_ids = {r["id"] for r in tx.query(f'''match
                    $p isa alh-person, has id "{escape_string(args.id)}";
                    $n isa career-relationship-note, has id $nid;
                    (note: $n, subject: $p) isa alh-aboutness;
                fetch {{ "id": $nid }};''').resolve()}
                for n in notes:
                    n["is_relationship_note"] = n.get("id") in rel_ids
            except Exception:
                pass

            # Roles borne by this person (e.g. career-agent-role)
            roles = []
            try:
                roles = list(tx.query(f'''match
                    $p isa alh-person, has id "{escape_string(args.id)}";
                    (bearer: $p, borne-role: $r) isa alh-role-bearing;
                fetch {{ "id": $r.id, "name": $r.name }};''').resolve())
            except Exception:
                pass

    print(json.dumps({
        "success": True,
        "person": person,
        "contact_roles": contact_roles,
        "collaborations": collaborations,
        "notes": notes,
        "roles": roles,
    }, indent=2, default=str))


def cmd_add_project(args):
    """Add a career project (open-source, paper, product, community effort)."""
    project_id = args.id or generate_id("project")
    timestamp = get_timestamp()

    query = f'''insert $pr isa career-project,
        has id "{project_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.role:
        query += f', has career-project-role "{args.role}"'
    if args.status:
        query += f', has career-project-status "{args.status}"'
    if args.url:
        query += f', has career-project-url "{escape_string(args.url)}"'
    if args.priority:
        query += f', has career-priority-level "{args.priority}"'
    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        if args.company_id:
            _link_opportunity_to_company(driver, project_id, args.company_id)

        try:
            _link_opportunity_to_seeker(driver, project_id)
        except Exception:
            pass

    print(json.dumps({"success": True, "project_id": project_id, "name": args.name}))


def cmd_list_projects(args):
    """List career projects with their collaborators."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            match_clause = "match $pr isa career-project;"
            if args.status:
                match_clause += f'\n$pr has career-project-status "{args.status}";'
            if args.role:
                match_clause += f'\n$pr has career-project-role "{args.role}";'

            rows = list(tx.query(match_clause + '''
            fetch {
                "id": $pr.id,
                "name": $pr.name,
                "career-short-name": $pr.career-short-name,
                "career-project-role": $pr.career-project-role,
                "career-project-status": $pr.career-project-status,
                "career-project-url": $pr.career-project-url,
                "career-priority-level": $pr.career-priority-level,
                "description": $pr.description
            };''').resolve())

            for r in rows:
                pid = r.get("id", "")
                collaborators = []
                if pid:
                    try:
                        collaborators = list(tx.query(f'''match
                            $pr isa career-project, has id "{pid}";
                            (collaborator: $p, work: $pr) isa career-collaboration;
                        fetch {{ "id": $p.id, "name": $p.name }};''').resolve())
                    except Exception:
                        pass
                r["collaborators"] = collaborators

    projects = [{
        "id": r.get("id", ""),
        "name": r.get("name", ""),
        "short_name": r.get("career-short-name", ""),
        "role": r.get("career-project-role", ""),
        "status": r.get("career-project-status", ""),
        "url": r.get("career-project-url", ""),
        "priority": r.get("career-priority-level", ""),
        "description": r.get("description", ""),
        "collaborators": r.get("collaborators", []),
    } for r in rows]

    print(json.dumps({"success": True, "projects": projects, "count": len(projects)}, indent=2))


def cmd_update_project(args):
    """Update role, status, url, or priority of a career project."""
    updates = []
    if args.role:
        updates.append(("career-project-role", args.role))
    if args.status:
        updates.append(("career-project-status", args.status))
    if args.url:
        updates.append(("career-project-url", args.url))
    if args.priority:
        updates.append(("career-priority-level", args.priority))

    if not updates:
        print(json.dumps({"success": False, "error": "No updates specified"}))
        return

    with get_driver() as driver:
        for attr, value in updates:
            # Check if attribute already exists
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                check = list(tx.query(f'''match
                    $pr isa career-project, has id "{args.id}", has {attr} $v;
                fetch {{ "v": $v.{attr} }};''').resolve())

            if check:
                # Delete old value then insert new
                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(f'''match
                        $pr isa career-project, has id "{args.id}", has {attr} $v;
                    delete has $v of $pr;''').resolve()
                    tx.commit()

            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $pr isa career-project, has id "{args.id}";
                insert $pr has {attr} "{escape_string(value)}";''').resolve()
                tx.commit()

    print(json.dumps({"success": True, "id": args.id, "updates": dict(updates)}))


def cmd_link_collaborator(args):
    """Link a person to a project or opportunity via career-collaboration."""
    rel_attrs = f'has career-collab-role "{args.role}"'
    if args.strength:
        rel_attrs += f', has career-collab-strength "{args.strength}"'
    if args.since:
        rel_attrs += f', has career-collab-since {parse_date(args.since)}'

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $p isa alh-person, has id "{escape_string(args.person)}";
                $w isa career-opportunity, has id "{escape_string(args.target)}";
            insert (collaborator: $p, work: $w) isa career-collaboration,
                {rel_attrs};''').resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "person_id": args.person,
        "target_id": args.target,
        "role": args.role,
    }))


def cmd_list_collaborators(args):
    """List collaborations for a person or for a project/opportunity."""
    if not args.person and not args.target:
        print(json.dumps({"success": False, "error": "Provide --person or --target"}))
        return

    if args.person:
        anchor = f'$p isa alh-person, has id "{escape_string(args.person)}";'
    else:
        anchor = f'$w isa career-opportunity, has id "{escape_string(args.target)}";'

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            rows = list(tx.query(f'''match
                {anchor}
                (collaborator: $p, work: $w) isa career-collaboration;
            fetch {{
                "person_id": $p.id, "person_name": $p.name,
                "target_id": $w.id, "target_name": $w.name
            }};''').resolve())

            for attr, key in [
                ("career-collab-role", "role"),
                ("career-collab-strength", "strength"),
                ("career-collab-since", "since"),
            ]:
                try:
                    overlay = {(r["person_id"], r["target_id"]): r["v"] for r in tx.query(f'''match
                        {anchor}
                        $p isa alh-person, has id $pid;
                        $w isa career-opportunity, has id $wid;
                        (collaborator: $p, work: $w) isa career-collaboration, has {attr} $v;
                    fetch {{ "person_id": $pid, "target_id": $wid, "v": $v }};''').resolve()}
                    for r in rows:
                        k = (r["person_id"], r["target_id"])
                        if k in overlay:
                            r[key] = overlay[k]
                except Exception:
                    pass

    print(json.dumps({
        "success": True,
        "collaborations": rows,
        "count": len(rows),
    }, indent=2, default=str))


def cmd_list_pipeline(args):
    """List positions in the pipeline."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Build query - fetch positions with their status
            match_clause = """match
                    $p isa career-position, has career-opportunity-status $status;"""

            if hasattr(args, 'person') and args.person:
                match_clause += f'''
                    (seeker: $seeker, opportunity: $p) isa career-seeker-pipeline;
                    (bearer: $person, borne-role: $seeker) isa alh-role-bearing;
                    $person has id "{escape_string(args.person)}";'''

            if args.status:
                match_clause = match_clause.replace(
                    "has career-opportunity-status $status", f'has career-opportunity-status "{args.status}"'
                )

            if args.priority:
                match_clause += f'\n                    $p has career-priority-level "{args.priority}";'

            fetch_status = "$status" if not args.status else f'"{args.status}"'
            query = match_clause + f"""
                fetch {{
                    "id": $p.id,
                    "name": $p.name,
                    "career-short-name": $p.career-short-name,
                    "career-job-url": $p.career-job-url,
                    "location": $p.alh-location,
                    "career-remote-policy": $p.career-remote-policy,
                    "career-salary-range": $p.career-salary-range,
                    "career-priority-level": $p.career-priority-level,
                    "status": $p.career-opportunity-status
                }};"""

            results = list(tx.query(query).resolve())

            # Separately fetch company info for each position
            for r in results:
                pos_id = r.get("id")
                if pos_id:
                    company_query = f'''match
                        $p isa career-position, has id "{pos_id}";
                        (position: $p, employer: $c) isa career-position-at-company;
                    fetch {{ "name": $c.name }};'''
                    try:
                        company_results = list(tx.query(company_query).resolve())
                        if company_results:
                            r["company_name"] = company_results[0].get("name", "")
                    except Exception:
                        r["company_name"] = ""

            # If filtering by tag, we need a separate query
            if args.tag:
                tag_query = f'''match
                    $p isa career-position;
                    $t isa alh-tag, has name "{args.tag}";
                    (tagged-entity: $p, tag: $t) isa alh-tagging;
                fetch {{ "id": $p.id }};'''
                tagged = list(tx.query(tag_query).resolve())
                tagged_ids = {r.get("id") for r in tagged}
                results = [r for r in results if r.get("id") in tagged_ids]

    # Format output
    positions = []
    for r in results:
        pos = {
            "id": r.get("id"),
            "title": r.get("name"),
            "short_name": r.get("career-short-name"),
            "url": r.get("career-job-url"),
            "location": r.get("location"),
            "remote_policy": r.get("career-remote-policy"),
            "salary": r.get("career-salary-range"),
            "priority": r.get("career-priority-level"),
            "status": r.get("status"),
            "company": r.get("company_name", ""),
        }
        positions.append(pos)

    print(json.dumps({"success": True, "positions": positions, "count": len(positions)}, indent=2))
def cmd_show_position(args):
    """Get full details for a position."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get position details
            pos_query = f'''match
                $p isa career-position, has id "{args.id}";
            fetch {{
                "id": $p.id,
                "name": $p.name,
                "career-job-url": $p.career-job-url,
                "location": $p.alh-location,
                "career-remote-policy": $p.career-remote-policy,
                "career-salary-range": $p.career-salary-range,
                "career-team-size": $p.career-team-size,
                "career-priority-level": $p.career-priority-level,
                "career-opportunity-status": $p.career-opportunity-status,
                "deadline": $p.career-deadline
            }};'''
            pos_result = list(tx.query(pos_query).resolve())

            if not pos_result:
                print(json.dumps({"success": False, "error": "Position not found"}))
                return

            # Get company
            company_query = f'''match
                $p isa career-position, has id "{args.id}";
                (position: $p, employer: $c) isa career-position-at-company;
            fetch {{
                "id": $c.id,
                "name": $c.name,
                "alh-company-url": $c.alh-company-url,
                "location": $c.alh-location
            }};'''
            company_result = list(tx.query(company_query).resolve())

            # Query each note subtype separately so we can return type
            # labels and type-specific attributes for the dashboard
            NOTE_TYPE_ATTRS = {
                "career-fit-analysis-note": ["id", "name", "content", "created-at", "career-fit-score", "career-fit-summary"],
                "career-interview-note": ["id", "name", "content", "created-at", "career-interview-date"],
                "career-interaction-note": ["id", "name", "content", "created-at", "alh-interaction-type", "alh-interaction-date"],
                "career-research-note": ["id", "name", "content", "created-at"],
                "career-strategy-note": ["id", "name", "content", "created-at"],
                "career-skill-gap-note": ["id", "name", "content", "created-at"],
            }
            notes_result = []
            for ntype, attr_list in NOTE_TYPE_ATTRS.items():
                attr_fetch = ", ".join(f'"{a}": $n.{a}' for a in attr_list)
                q = f'''match
                    $p isa career-position, has id "{args.id}";
                    (note: $n, subject: $p) isa alh-aboutness;
                    $n isa {ntype};
                fetch {{ {attr_fetch} }};'''
                for r in tx.query(q).resolve():
                    r["type"] = ntype
                    notes_result.append(r)

            # Get requirements
            req_query = f'''match
                $p isa career-position, has id "{args.id}";
                (requirement: $r, position: $p) isa career-requirement-for;
            fetch {{
                "id": $r.id,
                "career-skill-name": $r.career-skill-name,
                "career-skill-level": $r.career-skill-level,
                "career-your-level": $r.career-your-level,
                "content": $r.content
            }};'''
            req_result = list(tx.query(req_query).resolve())

            # Get job description artifact
            artifact_query = f'''match
                $p isa career-position, has id "{args.id}";
                (alh-artifact: $a, referent: $p) isa alh-representation;
                $a isa career-job-description;
            fetch {{ "id": $a.id, "content": $a.content }};'''
            artifact_result = list(tx.query(artifact_query).resolve())

            # Get tags
            tags_query = f'''match
                $p isa career-position, has id "{args.id}";
                (tagged-entity: $p, tag: $t) isa alh-tagging;
            fetch {{ "name": $t.name }};'''
            tags_result = list(tx.query(tags_query).resolve())

            # Get background reading collections
            bg_cols = list(tx.query(f'''
                match $p isa career-position, has id "{args.id}";
                      $c isa alh-collection;
                      (opportunity: $p, reading-material: $c) isa career-background-reading;
                fetch {{ "collection-id": $c.id, "collection-name": $c.name }};
            ''').resolve())

            # Fetch descriptions — anon relation + has avoids $var naming issues
            bg_descs = {r["collection-id"]: r["description"]
                        for r in tx.query(f'''
                match $p isa career-position, has id "{args.id}";
                      $c isa alh-collection, has id $cid;
                      (opportunity: $p, reading-material: $c) isa career-background-reading,
                          has description $desc;
                fetch {{ "collection-id": $cid, "description": $desc }};
            ''').resolve()}

            background_reading = []
            for col in bg_cols:
                cid = col["collection-id"]
                item = {"collection-id": cid, "collection-name": col["collection-name"]}
                if cid in bg_descs:
                    item["description"] = bg_descs[cid]
                background_reading.append(item)

    output = {
        "success": True,
        "position": pos_result[0] if pos_result else None,
        "company": company_result[0] if company_result else None,
        "notes": notes_result,
        "requirements": req_result,
        "job_description": artifact_result[0] if artifact_result else None,
        "tags": [t.get("name") for t in tags_result],
        "background_reading": background_reading,
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_show_company(args):
    """Get company details and positions."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get company
            company_query = f'''match
                $c isa career-company, has id "{args.id}";
            fetch {{
                "id": $c.id,
                "name": $c.name,
                "alh-company-url": $c.alh-company-url,
                "alh-linkedin-url": $c.alh-linkedin-url,
                "description": $c.description,
                "location": $c.alh-location
            }};'''
            company_result = list(tx.query(company_query).resolve())

            if not company_result:
                print(json.dumps({"success": False, "error": "Company not found"}))
                return

            # Get positions at company
            pos_query = f'''match
                $c isa career-company, has id "{args.id}";
                (position: $p, employer: $c) isa career-position-at-company;
            fetch {{
                "id": $p.id,
                "name": $p.name,
                "career-job-url": $p.career-job-url,
                "career-priority-level": $p.career-priority-level
            }};'''
            pos_result = list(tx.query(pos_query).resolve())

            # Get notes about company
            notes_query = f'''match
                $c isa career-company, has id "{args.id}";
                (note: $n, subject: $c) isa alh-aboutness;
            fetch {{
                "id": $n.id,
                "name": $n.name,
                "content": $n.content
            }};'''
            notes_result = list(tx.query(notes_query).resolve())

    output = {
        "success": True,
        "company": company_result[0] if company_result else None,
        "positions": pos_result,
        "notes": notes_result,
    }

    print(json.dumps(output, indent=2, default=str))


def cmd_show_gaps(args):
    """Compute candidate-to-market fit: seeker skills vs position requirements."""
    level_value = {"none": 0, "aware": 1, "learning": 1, "practiced": 2, "some": 2, "expert": 3, "strong": 3}
    req_threshold = {"required": 2, "preferred": 1, "nice-to-have": 0}
    req_weight = {"required": 2.0, "preferred": 1.0, "nice-to-have": 0.5}

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # 1. Get all seeker skills
            skills_query = """match $s isa career-your-skill, has career-skill-name $sn, has career-skill-level $sl;
                fetch { "name": $sn, "level": $sl };"""
            skill_results = list(tx.query(skills_query).resolve())

            # 2. Get all requirements for positions past researching
            # Default: exclude "researching" (show applied, interviewing, rejected, withdrawn)
            # --all: include everything
            include_all = hasattr(args, 'all') and args.all
            status_filter = '' if include_all else '''
                not { $status == "researching"; };'''
            req_query = f"""match
                $r isa career-requirement, has career-skill-name $sn, has career-skill-level $sl;
                (requirement: $r, position: $p) isa career-requirement-for;
                $p has career-opportunity-status $status;{status_filter}
            fetch {{
                "skill": $sn, "level": $sl,
                "pos-id": $p.id, "pos-name": $p.name
            }};"""
            req_results = list(tx.query(req_query).resolve())

            # 3. Get alt-labels for concept matching
            alt_query = """match $c isa career-skill-concept, has name $cn, has career-alt-label $alt;
                fetch { "name": $cn, "alt": $alt };"""
            try:
                alt_results = list(tx.query(alt_query).resolve())
            except Exception:
                alt_results = []

    # Build skill lookup (lowercase name -> level)
    my_skills = {}
    for s in skill_results:
        my_skills[s["name"].lower()] = s["level"]

    # Build alt-label -> canonical name lookup
    alt_to_canonical = {}
    for a in alt_results:
        canonical = a["name"].lower()
        alt = a["alt"].lower()
        alt_to_canonical[alt] = canonical

    def lookup_my_level(skill_name):
        """Find seeker's level for a skill, checking alt-labels."""
        key = skill_name.lower()
        # Direct match
        if key in my_skills:
            return my_skills[key]
        # Alt-label match: look up canonical name, then check skills
        canonical = alt_to_canonical.get(key)
        if canonical and canonical in my_skills:
            return my_skills[canonical]
        # Check if skill_name IS a canonical name for which we have alt matches
        for alt, canon in alt_to_canonical.items():
            if canon == key and alt in my_skills:
                return my_skills[alt]
        return "none"

    # Group requirements by position
    positions = {}
    for r in req_results:
        pid = r["pos-id"]
        if pid not in positions:
            positions[pid] = {"id": pid, "name": r["pos-name"], "requirements": []}
        positions[pid]["requirements"].append({
            "skill": r["skill"],
            "level": r["level"],
        })

    # Compute per-position fit scores
    position_fits = []
    all_gaps = {}  # skill -> {gap_impact, positions}

    for pid, pos in positions.items():
        total_weight = 0
        total_coverage = 0
        reqs_detail = []

        for req in pos["requirements"]:
            my_level = lookup_my_level(req["skill"])
            my_val = level_value.get(my_level, 0)
            threshold = req_threshold.get(req["level"], 1)
            weight = req_weight.get(req["level"], 1.0)

            coverage = min(1.0, my_val / max(threshold, 1))
            total_weight += weight
            total_coverage += coverage * weight

            reqs_detail.append({
                "skill": req["skill"],
                "required_level": req["level"],
                "my_level": my_level,
                "coverage": round(coverage, 2),
            })

            # Track gaps for learning priority
            if coverage < 1.0:
                gap_size = max(threshold - my_val, 0)
                skill_key = req["skill"]
                if skill_key not in all_gaps:
                    all_gaps[skill_key] = {"skill": skill_key, "current_level": my_level, "gap_impact": 0, "positions": []}
                all_gaps[skill_key]["gap_impact"] += gap_size * weight
                all_gaps[skill_key]["positions"].append(pos["name"][:40])

        fit_score = round(total_coverage / max(total_weight, 1), 2)
        covered = len([r for r in reqs_detail if r["coverage"] >= 1.0])
        gaps_count = len([r for r in reqs_detail if r["coverage"] < 1.0])

        position_fits.append({
            "id": pid,
            "name": pos["name"],
            "fit_score": fit_score,
            "total_requirements": len(reqs_detail),
            "covered": covered,
            "gaps": gaps_count,
            "requirements": reqs_detail,
        })

    # Sort positions by number of gaps (fewest gaps first)
    position_fits.sort(key=lambda x: (x["gaps"], -x["covered"]))

    # Learning priorities sorted by gap impact
    learning_priorities = sorted(all_gaps.values(), key=lambda x: x["gap_impact"], reverse=True)
    for lp in learning_priorities:
        lp["needed_for"] = len(lp["positions"])
        lp["gap_impact"] = round(lp["gap_impact"], 1)

    # Also include legacy skill_gaps format for backward compatibility
    legacy_gaps = []
    for lp in learning_priorities:
        legacy_gaps.append({
            "skill": lp["skill"],
            "level": "required",
            "your_level": lp["current_level"],
            "positions": [{"id": "", "title": p} for p in lp["positions"]],
        })

    print(json.dumps({
        "success": True,
        "seeker_skills": len(my_skills),
        "positions_analyzed": len(position_fits),
        "positions": position_fits,
        "learning_priorities": learning_priorities,
        "skill_gaps": legacy_gaps,
    }, indent=2, default=str))


def cmd_learning_plan(args):
    """Generate a prioritized learning plan based on skill gaps."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get all learning resources
            query = """match
                $res isa career-learning-resource;
            fetch {
                "id": $res.id,
                "name": $res.name,
                "career-resource-type": $res.career-resource-type,
                "career-resource-url": $res.career-resource-url,
                "career-estimated-hours": $res.career-estimated-hours,
                "career-completion-status": $res.career-completion-status
            };"""
            results = list(tx.query(query).resolve())

            # Get collections linked to skill requirements
            coll_query = """match
                $c isa alh-collection;
                (resource: $c, requirement: $req) isa career-addresses-requirement;
            fetch {
                "id": $c.id,
                "name": $c.name,
                "description": $c.description,
                "career-skill-name": $req.career-skill-name
            };"""
            coll_results = list(tx.query(coll_query).resolve())

            # Get papers referenced by learning resources via alh-citation-reference
            paper_query = """match
                $res isa career-learning-resource;
                (citing-item: $res, cited-item: $paper) isa alh-citation-reference;
            fetch {
                "res-id": $res.id,
                "res-name": $res.name,
                "paper-id": $paper.id,
                "paper-name": $paper.name
            };"""
            paper_results = list(tx.query(paper_query).resolve())

    # Format resources
    resources = []
    for r in results:
        res = {
            "id": r.get("id", ""),
            "name": r.get("name", ""),
            "type": r.get("career-resource-type", ""),
            "url": r.get("career-resource-url", ""),
            "hours": r.get("career-estimated-hours", ""),
            "status": r.get("career-completion-status", ""),
        }
        resources.append(res)

    # Remove duplicates
    seen = set()
    unique_resources = []
    for r in resources:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique_resources.append(r)

    # Format collections
    collections = []
    seen_colls = set()
    for cr in coll_results:
        coll_id = cr.get("id", "")
        skill = cr.get("career-skill-name", "")
        key = f"{coll_id}:{skill}"
        if key not in seen_colls:
            seen_colls.add(key)
            collections.append({
                "id": coll_id,
                "name": cr.get("name", ""),
                "description": cr.get("description", ""),
                "skill_name": skill,
            })

    # Format referenced papers
    referenced_papers = []
    for pr in paper_results:
        referenced_papers.append({
            "resource_id": pr.get("res-id", ""),
            "resource_name": pr.get("res-name", ""),
            "paper_id": pr.get("paper-id", ""),
            "paper_name": pr.get("paper-name", ""),
        })

    print(
        json.dumps(
            {
                "success": True,
                "learning_plan": unique_resources,
                "total_resources": len(unique_resources),
                "collections": collections,
                "referenced_papers": referenced_papers,
            },
            indent=2,
        )
    )


def cmd_tag(args):
    """Tag an entity."""
    tag_id = generate_id("tag")
    with get_driver() as driver:
        # Create tag if not exists
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            tag_check = f'match $t isa alh-tag, has name "{args.tag}"; fetch {{ "id": $t.id }};'
            existing_tag = list(tx.query(tag_check).resolve())

        if not existing_tag:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'insert $t isa alh-tag, has id "{tag_id}", has name "{args.tag}";').resolve()
                tx.commit()

        # Create tagging relation
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $e isa alh-identifiable-entity, has id "{args.entity}";
                $t isa alh-tag, has name "{args.tag}";
            insert (tagged-entity: $e, tag: $t) isa alh-tagging;''').resolve()
            tx.commit()

    print(json.dumps({"success": True, "entity": args.entity, "tag": args.tag}))


def cmd_search_tag(args):
    """Search entities by tag."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            query = f'''match
                $t isa alh-tag, has name "{args.tag}";
                (tagged-entity: $e, tag: $t) isa alh-tagging;
            fetch {{
                "id": $e.id,
                "name": $e.name
            }};'''
            results = list(tx.query(query).resolve())

    print(
        json.dumps(
            {
                "success": True,
                "tag": args.tag,
                "entities": results,
                "count": len(results),
            },
            indent=2,
            default=str,
        )
    )


def cmd_add_requirement(args):
    """Add a requirement to a position."""
    req_id = args.id or generate_id("requirement")
    timestamp = get_timestamp()

    query = f'''insert $r isa career-requirement,
        has id "{req_id}",
        has career-skill-name "{escape_string(args.skill)}",
        has created-at {timestamp}'''

    if args.level:
        query += f', has career-skill-level "{args.level}"'
    if args.career_your_level:
        query += f', has career-your-level "{args.career_your_level}"'
    if args.content:
        query += f', has content "{escape_string(args.content)}"'

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Link to position
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            rel_query = f'''match
                $r isa career-requirement, has id "{req_id}";
                $p isa career-position, has id "{args.position}";
            insert (requirement: $r, position: $p) isa career-requirement-for;'''
            tx.query(rel_query).resolve()
            tx.commit()

    print(
        json.dumps(
            {
                "success": True,
                "requirement_id": req_id,
                "skill": args.skill,
                "position": args.position,
            }
        )
    )


# =============================================================================
# YOUR SKILL PROFILE COMMANDS
# =============================================================================


def cmd_create_seeker_profile(args):
    """Create a job-seeker role for a person (BFO/UFO role pattern)."""
    role_id = args.id or generate_id("career-seeker")
    timestamp = get_timestamp()

    query = f'''insert $role isa career-agent-role,
        has id "{role_id}",
        has name "{escape_string(args.name or 'Job Search')}",
        has created-at {timestamp},
        has alh-role-status "active",
        has alh-role-started-on {timestamp}'''

    if args.target_role:
        query += f', has career-target-role "{escape_string(args.target_role)}"'
    if args.industries:
        query += f', has career-target-industries "{escape_string(args.industries)}"'
    if args.salary:
        query += f', has career-salary-expectations "{escape_string(args.salary)}"'
    if args.location:
        query += f', has career-location-preference "{escape_string(args.location)}"'
    if args.focus:
        query += f', has career-search-focus "{escape_string(args.focus)}"'

    query += ";"

    with get_driver() as driver:
        # Create the role entity
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Link role to person via alh-role-bearing
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(f'''match
                $person isa alh-person, has id "{escape_string(args.person)}";
                $role isa career-agent-role, has id "{role_id}";
            insert (bearer: $person, borne-role: $role) isa alh-role-bearing;''').resolve()
            tx.commit()

    print(json.dumps({
        "success": True,
        "role_id": role_id,
        "person_id": args.person,
        "message": f"Job-seeker profile created for {args.person}",
    }))


def cmd_add_skill(args):
    """
    Add or update a skill in your profile.

    Your skill profile is used during sensemaking to compare
    position requirements against your capabilities for gap analysis.
    """
    timestamp = get_timestamp()
    existing = []

    with get_driver() as driver:
        # Check if skill already exists
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            check_query = f'''match
                $s isa career-your-skill, has career-skill-name "{escape_string(args.name)}";
            fetch {{
                "career-skill-name": $s.career-skill-name,
                "career-skill-level": $s.career-skill-level
            }};'''
            existing = list(tx.query(check_query).resolve())

        if existing:
            # Update existing skill - delete and recreate
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $s isa career-your-skill, has career-skill-name "{escape_string(args.name)}";
                delete $s;''').resolve()
                tx.commit()

        # Create skill
        skill_id = generate_id("skill")
        skill_query = f'''insert $s isa career-your-skill,
            has id "{skill_id}",
            has career-skill-name "{escape_string(args.name)}",
            has career-skill-level "{args.level}",
            has career-last-updated {timestamp}'''

        if args.evidence:
            skill_query += f', has career-skill-evidence "{escape_string(args.evidence)}"'
        if args.recency:
            skill_query += f', has career-skill-recency "{escape_string(args.recency)}"'
        if args.description:
            skill_query += f', has description "{escape_string(args.description)}"'

        skill_query += ";"

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(skill_query).resolve()
            tx.commit()

        # Link skill to active job-seeker role
        try:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(f'''match
                    $role isa career-agent-role, has alh-role-status "active";
                    $skill isa career-your-skill, has id "{skill_id}";
                insert (seeker: $role, skill: $skill) isa career-seeker-has-skill;''').resolve()
                tx.commit()
        except Exception:
            pass  # seeker role may not exist

    action = "updated" if existing else "added"
    print(
        json.dumps(
            {
                "success": True,
                "action": action,
                "skill_name": args.name,
                "skill_level": args.level,
                "message": f"Skill '{args.name}' {action} as '{args.level}'",
            }
        )
    )


def cmd_add_concept(args):
    """Add a skill concept to the controlled vocabulary."""
    concept_id = args.id or generate_id("concept")
    timestamp = get_timestamp()

    query = f'''insert $c isa career-skill-concept,
        has id "{concept_id}",
        has name "{escape_string(args.name)}",
        has created-at {timestamp}'''

    if args.description:
        query += f', has description "{escape_string(args.description)}"'

    # Add alt-labels
    alt_labels = []
    if args.alt_labels:
        for label in args.alt_labels.split(","):
            label = label.strip()
            if label:
                query += f', has career-alt-label "{escape_string(label)}"'
                alt_labels.append(label)

    query += ";"

    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        # Link to broader concept if specified
        if args.broader:
            try:
                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(f'''match
                        $broader isa career-skill-concept, has name "{escape_string(args.broader)}";
                        $narrower isa career-skill-concept, has id "{concept_id}";
                    insert (broader-skill: $broader, narrower-skill: $narrower) isa career-skill-hierarchy;''').resolve()
                    tx.commit()
            except Exception:
                pass  # broader concept may not exist

    print(json.dumps({
        "success": True,
        "concept_id": concept_id,
        "name": args.name,
        "alt_labels": alt_labels,
        "broader": args.broader,
    }))


def cmd_list_concepts(args):
    """List skill concepts with seeker proficiency levels (prompt-friendly format)."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get all concepts
            concept_query = """match $c isa career-skill-concept;
                fetch { "id": $c.id, "name": $c.name, "description": $c.description };"""
            concepts = list(tx.query(concept_query).resolve())

            # Get alt-labels per concept
            alt_query = """match $c isa career-skill-concept, has id $cid, has career-alt-label $alt;
                fetch { "id": $cid, "alt": $alt };"""
            alt_results = list(tx.query(alt_query).resolve())

            # Get seeker skills linked to concepts via skill-definition
            skill_query = """match
                $s isa career-your-skill, has career-skill-name $sn, has career-skill-level $sl;
                (concept: $c, defined-skill: $s) isa career-skill-definition;
                $c has id $cid;
                fetch { "concept_id": $cid, "skill_name": $sn, "level": $sl };"""
            try:
                skill_links = list(tx.query(skill_query).resolve())
            except Exception:
                skill_links = []

            # Get hierarchy
            hier_query = """match
                (broader-skill: $b, narrower-skill: $n) isa career-skill-hierarchy;
                $b has name $bn; $n has id $nid;
                fetch { "narrower_id": $nid, "broader": $bn };"""
            try:
                hier_results = list(tx.query(hier_query).resolve())
            except Exception:
                hier_results = []

    # Build lookup maps
    alt_map = {}
    for a in alt_results:
        cid = a.get("id", "")
        if cid not in alt_map:
            alt_map[cid] = []
        alt_map[cid].append(a.get("alt", ""))

    skill_level_map = {}
    for sl in skill_links:
        skill_level_map[sl.get("concept_id", "")] = sl.get("level", "")

    hier_map = {}
    for h in hier_results:
        hier_map[h.get("narrower_id", "")] = h.get("broader", "")

    # If no skill links exist, fall back to matching by name
    if not skill_links:
        # Get all seeker skills for name-based matching
        all_skills_query = """match $s isa career-your-skill, has career-skill-name $sn, has career-skill-level $sl;
            fetch { "name": $sn, "level": $sl };"""
        with get_driver() as driver:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                all_skills = list(tx.query(all_skills_query).resolve())
        skills_by_name = {s["name"].lower(): s["level"] for s in all_skills}
    else:
        skills_by_name = {}

    # Build output
    concept_list = []
    for c in concepts:
        cid = c.get("id", "")
        name = c.get("name", "")
        level = skill_level_map.get(cid, "")

        # Fallback: match by name if no concept link
        if not level and skills_by_name:
            level = skills_by_name.get(name.lower(), "")

        alts = alt_map.get(cid, [])
        broader = hier_map.get(cid, "")

        concept_list.append({
            "id": cid,
            "name": name,
            "description": c.get("description", ""),
            "level": level,
            "alt_labels": alts,
            "broader": broader,
        })

    # Sort by level then name
    level_order = {"expert": 0, "strong": 0, "practiced": 1, "some": 1,
                   "aware": 2, "learning": 2, "none": 3, "": 4}
    concept_list.sort(key=lambda x: (level_order.get(x["level"], 5), x["name"]))

    # Build compact prompt-friendly output
    level_icons = {"expert": "★", "strong": "★", "practiced": "●", "some": "●",
                   "aware": "○", "learning": "○", "none": "·", "": "?"}
    lines = []
    current_level = None
    level_labels = {"expert": "EXPERT", "strong": "EXPERT", "practiced": "PRACTICED",
                    "some": "PRACTICED", "aware": "AWARE", "learning": "AWARE",
                    "none": "NONE", "": "NOT IN PROFILE"}

    for c in concept_list:
        lvl = c["level"] or ""
        label = level_labels.get(lvl, "UNKNOWN")
        if label != current_level:
            current_level = label
            lines.append(f"\n{label}:")

        icon = level_icons.get(lvl, "?")
        alt_str = f" [alt: {', '.join(c['alt_labels'])}]" if c["alt_labels"] else ""
        broader_str = f" > {c['broader']}" if c["broader"] else ""
        lines.append(f"  {icon} {c['name']}{alt_str}{broader_str}")

    print(json.dumps({
        "success": True,
        "concepts": concept_list,
        "count": len(concept_list),
        "prompt_view": "\n".join(lines),
    }, indent=2))


def cmd_list_skills(args):
    """List your skill profile."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            query = """match
                $s isa career-your-skill;
            fetch {
                "career-skill-name": $s.career-skill-name,
                "career-skill-level": $s.career-skill-level,
                "career-skill-evidence": $s.career-skill-evidence,
                "career-skill-recency": $s.career-skill-recency,
                "description": $s.description,
                "career-last-updated": $s.career-last-updated
            };"""
            results = list(tx.query(query).resolve())

    # Format output
    skills = []
    for r in results:
        skill = {
            "name": r.get("career-skill-name", ""),
            "level": r.get("career-skill-level", ""),
            "evidence": r.get("career-skill-evidence", ""),
            "recency": r.get("career-skill-recency", ""),
            "description": r.get("description", ""),
            "last_updated": r.get("career-last-updated", ""),
        }
        skills.append(skill)

    # Sort by level (expert first, then practiced, aware, none)
    level_order = {"expert": 0, "practiced": 1, "aware": 2, "none": 3,
                   "strong": 0, "some": 1, "learning": 2}  # backward compat
    skills.sort(key=lambda x: (level_order.get(x["level"], 4), x["name"]))

    print(
        json.dumps(
            {
                "success": True,
                "skills": skills,
                "count": len(skills),
                "by_level": {
                    "expert": len([s for s in skills if s["level"] in ("expert", "strong")]),
                    "practiced": len([s for s in skills if s["level"] in ("practiced", "some")]),
                    "aware": len([s for s in skills if s["level"] in ("aware", "learning")]),
                    "none": len([s for s in skills if s["level"] == "none"]),
                },
            },
            indent=2,
        )
    )


# =============================================================================
# ARTIFACT COMMANDS (for Claude's sensemaking)
# =============================================================================


def cmd_list_artifacts(args):
    """
    List artifacts, optionally filtered by analysis status.

    Status:
    - 'raw': Artifacts with no notes (need sensemaking)
    - 'analyzed': Artifacts with at least one note
    - 'all': All artifacts
    """
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get all job description artifacts
            artifacts_query = """match
                $a isa career-job-description;
            fetch {
                "id": $a.id,
                "name": $a.name,
                "source-uri": $a.source-uri,
                "created-at": $a.created-at
            };"""
            artifacts = list(tx.query(artifacts_query).resolve())

            # For each artifact, check if it has associated notes
            # (via position -> aboutness -> note)
            results = []
            for art in artifacts:
                artifact_id = art.get("id", "")

                # Check for notes on the linked position
                notes_query = f'''match
                    $a isa career-job-description, has id "{artifact_id}";
                    (alh-artifact: $a, referent: $p) isa alh-representation;
                    (note: $n, subject: $p) isa alh-aboutness;
                fetch {{ "id": $n.id }};'''

                try:
                    notes = list(tx.query(notes_query).resolve())
                    has_notes = len(notes) > 0
                except Exception:
                    has_notes = False
                    notes = []

                status = "analyzed" if has_notes else "raw"

                # Apply filter
                if args.status and args.status != "all":
                    if args.status != status:
                        continue

                results.append(
                    {
                        "id": artifact_id,
                        "name": art.get("name", ""),
                        "source_url": art.get("source-uri", ""),
                        "created_at": art.get("created-at", ""),
                        "status": status,
                        "note_count": len(notes) if has_notes else 0,
                    }
                )

    print(
        json.dumps(
            {
                "success": True,
                "artifacts": results,
                "count": len(results),
                "filter": args.status or "all",
            },
            indent=2,
        )
    )


def cmd_show_artifact(args):
    """
    Get full artifact content for Claude to read during sensemaking.

    Returns the raw content stored during ingestion, along with
    metadata about the linked position. Content is loaded from cache
    if the artifact was stored externally.
    """
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get artifact - include cache-path and other cache attributes
            artifact_query = f'''match
                $a isa career-job-description, has id "{args.id}";
            fetch {{
                "id": $a.id,
                "name": $a.name,
                "content": $a.content,
                "cache-path": $a.cache-path,
                "mime-type": $a.mime-type,
                "file-size": $a.file-size,
                "source-uri": $a.source-uri,
                "created-at": $a.created-at
            }};'''
            artifact_result = list(tx.query(artifact_query).resolve())

            if not artifact_result:
                print(json.dumps({"success": False, "error": "Artifact not found"}))
                return

            # Get linked position (specifically career-position)
            position_query = f'''match
                $a isa career-job-description, has id "{args.id}";
                (alh-artifact: $a, referent: $p) isa alh-representation;
                $p isa career-position;
            fetch {{
                "id": $p.id,
                "name": $p.name,
                "career-job-url": $p.career-job-url,
                "location": $p.alh-location,
                "career-remote-policy": $p.career-remote-policy,
                "career-salary-range": $p.career-salary-range,
                "career-priority-level": $p.career-priority-level
            }};'''
            position_result = list(tx.query(position_query).resolve())

            # Get linked company (if any)
            company_result = []
            if position_result:
                pos_id = position_result[0].get("id", "")
                company_query = f'''match
                    $p isa career-position, has id "{pos_id}";
                    (position: $p, employer: $c) isa career-position-at-company;
                fetch {{
                    "id": $c.id,
                    "name": $c.name
                }};'''
                try:
                    company_result = list(tx.query(company_query).resolve())
                except Exception:
                    pass

    art = artifact_result[0]

    # Get content - either from inline content or from cache
    cache_path = art.get("cache-path", "")
    if cache_path and CACHE_AVAILABLE:
        # Load from cache
        try:
            content = load_from_cache_text(cache_path)
            storage = "cache"
        except FileNotFoundError:
            content = f"[ERROR: Cache file not found: {cache_path}]"
            storage = "cache_missing"
    else:
        # Get inline content
        content = art.get("content", "")
        storage = "inline"

    output = {
        "success": True,
        "artifact": {
            "id": art.get("id", ""),
            "name": art.get("name", ""),
            "source_url": art.get("source-uri", ""),
            "created_at": art.get("created-at", ""),
            "content": content,
            "storage": storage,
            "cache_path": cache_path,
            "mime_type": art.get("mime-type", ""),
            "file_size": art.get("file-size", ""),
        },
        "position": None,
        "company": None,
    }

    if position_result:
        pos = position_result[0]
        output["position"] = {
            "id": pos.get("id", ""),
            "name": pos.get("name", ""),
            "url": pos.get("career-job-url", ""),
            "location": pos.get("location", ""),
            "remote_policy": pos.get("career-remote-policy", ""),
            "salary": pos.get("career-salary-range", ""),
            "priority": pos.get("career-priority-level", ""),
        }

    if company_result:
        comp = company_result[0]
        output["company"] = {
            "id": comp.get("id", ""),
            "name": get_attr(comp, "name"),
        }

    print(json.dumps(output, indent=2))


def cmd_cache_stats(args):
    """Show cache statistics."""
    stats = get_cache_stats()

    if "error" in stats:
        print(json.dumps({"success": False, "error": stats["error"]}))
        return

    # Format sizes for readability
    output = {
        "success": True,
        "cache_dir": stats["cache_dir"],
        "total_files": stats["total_files"],
        "total_size": stats["total_size"],
        "total_size_human": format_size(stats["total_size"]),
        "by_type": {},
    }

    for type_name, type_stats in stats["by_type"].items():
        output["by_type"][type_name] = {
            "count": type_stats["count"],
            "size": type_stats["size"],
            "size_human": format_size(type_stats["size"]),
        }

    print(json.dumps(output, indent=2))


# =============================================================================
# REPORT COMMANDS (Markdown output for messaging apps)
# =============================================================================


STATUS_EMOJI = {
    "researching": "🔍",
    "applied": "📨",
    "phone-screen": "📞",
    "interviewing": "🎯",
    "offer": "🎉",
    "rejected": "❌",
    "withdrawn": "⏸️",
}

PRIORITY_EMOJI = {
    "high": "🔴",
    "medium": "🟡",
    "low": "🟢",
}


# =============================================================================
# LEGACY MIGRATION (jobhunt -> career) — GLAV mapping
# =============================================================================
# The migration is defined declaratively as GLAV rules in mapping/rules/
# (source_match over jhunt-* -> target_insert into career-*, with foreign keys
# resolved through the career-legacy-id natural key). This command is a thin
# wrapper over the bundled schema_mapper-compatible runner; see
# mapping/README.md for the rule catalog and standalone usage.


def cmd_migrate_from_jobhunt(args):
    """Run the GLAV mapping rules that copy legacy jhunt-* data into career-*.

    Delegates to mapping/glav_runner.py. A clean no-op when there is no
    legacy data: rules whose source types are absent match zero rows.
    """
    import subprocess

    skill_dir = Path(__file__).resolve().parent
    runner = skill_dir / "mapping" / "glav_runner.py"
    cmd = [
        sys.executable,
        str(runner),
        "run",
        "--source-db", TYPEDB_DATABASE,
        "--target-db", TYPEDB_DATABASE,
        "--rules-dir", str(skill_dir / "mapping" / "rules"),
    ]
    if getattr(args, "dry_run", False):
        cmd.append("--dry-run")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout, end="")
    elif result.returncode != 0:
        print(json.dumps({"success": False, "error": result.stderr[-500:]}))
    sys.exit(result.returncode)



def cmd_report_pipeline(args):
    """Generate pipeline report as formatted Markdown."""
    positions = _fetch_pipeline_data()

    # Group by status
    by_status = {}
    for p in positions:
        s = p["status"]
        by_status.setdefault(s, []).append(p)

    # Count stats
    total = len(positions)
    active = sum(1 for p in positions if p["status"] not in ("rejected", "withdrawn", "offer"))
    applied = sum(1 for p in positions if p["status"] == "applied")
    interviewing = sum(1 for p in positions if p["status"] in ("phone-screen", "interviewing"))

    # Build markdown
    lines = ["**📊 Job Search Pipeline**", ""]
    lines.append(f"Total: {total} | Active: {active} | Applied: {applied} | Interviewing: {interviewing}")
    lines.append("")

    status_order = ["interviewing", "phone-screen", "applied", "researching", "offer", "rejected", "withdrawn"]

    for status in status_order:
        group = by_status.get(status, [])
        if not group:
            continue
        emoji = STATUS_EMOJI.get(status, "•")
        lines.append(f"**{emoji} {status.replace('-', ' ').title()}** ({len(group)})")
        for p in group:
            display = p["short_name"] or p["name"][:40]
            pri = PRIORITY_EMOJI.get(p["priority"], "") + " " if p["priority"] else ""
            lines.append(f"  • {pri}{display}")
        lines.append("")

    print("\n".join(lines))


def cmd_report_position(args):
    """Generate position detail report as formatted Markdown."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            pid = args.id

            # Get position attributes
            pos_query = f"""
                match $p isa career-position, has id "{pid}";
                fetch {{
                    "id": $p.id,
                    "name": $p.name,
                    "career-short-name": $p.career-short-name,
                    "career-job-url": $p.career-job-url,
                    "career-salary-range": $p.career-salary-range,
                    "location": $p.alh-location,
                    "career-remote-policy": $p.career-remote-policy,
                    "career-priority-level": $p.career-priority-level
                }};
            """
            pos_results = list(tx.query(pos_query).resolve())
            if not pos_results:
                print(f"Position `{pid}` not found.")
                return

            attrs = pos_results[0]

            # Get notes content
            note_query = f"""
                match
                $p isa career-position, has id "{pid}";
                $note isa alh-note;
                (subject: $p, note: $note) isa alh-aboutness;
                fetch {{ "content": $note.content }};
            """
            try:
                all_notes = list(tx.query(note_query).resolve())
            except Exception:
                all_notes = []

            # Get opportunity status directly from position
            status_query = f"""
                match
                $p isa career-position, has id "{pid}", has career-opportunity-status $s;
                fetch {{ "status": $s }};
            """
            try:
                status_results = list(tx.query(status_query).resolve())
                if status_results:
                    attrs["career-opportunity-status"] = status_results[0].get("status")
            except Exception:
                pass

    # Build markdown
    title = attrs.get("career-short-name") or attrs.get("name", pid)
    status = attrs.get("career-opportunity-status", "unknown")
    status_emoji = STATUS_EMOJI.get(status, "•")

    lines = [f"**{title}**", ""]
    lines.append(f"Status: {status_emoji} {status}")
    if attrs.get("career-priority-level"):
        lines.append(f"Priority: {PRIORITY_EMOJI.get(attrs['career-priority-level'], '')} {attrs['career-priority-level']}")
    if attrs.get("career-job-url"):
        lines.append(f"URL: {attrs['career-job-url']}")
    if attrs.get("career-salary-range"):
        lines.append(f"Salary: {attrs['career-salary-range']}")
    if attrs.get("location"):
        lines.append(f"Location: {attrs['location']}")
    if attrs.get("career-remote-policy"):
        lines.append(f"Remote: {attrs['career-remote-policy']}")
    lines.append("")

    if all_notes:
        lines.append(f"**Notes** ({len(all_notes)})")
        lines.append("")
        for n in all_notes:
            note_content = n.get("content", "")
            if note_content:
                # Unescape literal \n sequences
                note_content = note_content.replace("\\n", "\n").replace("\\'", "'")
                # Truncate long notes for messaging
                if len(note_content) > 500:
                    note_content = note_content[:497] + "..."
                lines.append(f"{note_content}")
                lines.append("")
                lines.append("---")
                lines.append("")

    print("\n".join(lines))

def cmd_report_gaps(args):
    """Generate skill gaps report as formatted Markdown."""
    with get_driver() as driver:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get all requirements with your skill levels
            query = """
                match
                $req isa career-requirement;
                $p isa career-position;
                (position: $p, requirement: $req) isa career-requirement-for;
                fetch {
                    "skill": $req.career-skill-name,
                    "level": $req.career-skill-level,
                    "pos_name": $p.name
                };
            """
            results = list(tx.query(query).resolve())

            # Get your skills
            skill_query = """
                match $s isa career-your-skill;
                fetch { "name": $s.career-skill-name, "level": $s.career-skill-level };
            """
            try:
                skill_results = list(tx.query(skill_query).resolve())
            except Exception:
                skill_results = []

    my_skills = {}
    for s in skill_results:
        my_skills[s.get("name", "")] = s.get("level", "")

    # Group by skill
    gaps = {}
    for r in results:
        skill = r.get("skill", "")
        level = r.get("level", "")
        pos_name = r.get("pos_name", "")
        my_level = my_skills.get(skill, "none")

        if my_level in ("strong",):
            continue  # No gap

        gaps.setdefault(skill, {
            "required_level": level,
            "your_level": my_level,
            "positions": [],
        })
        gaps[skill]["positions"].append(pos_name[:30])

    # Build markdown
    lines = ["**Skill Gaps Analysis**", ""]

    if not gaps:
        lines.append("No significant skill gaps found!")
    else:
        # Sort: required gaps first, then by number of positions
        sorted_gaps = sorted(
            gaps.items(),
            key=lambda x: (0 if x[1]["required_level"] == "required" else 1, -len(x[1]["positions"]))
        )

        LEVEL_EMOJI = {"none": "[ ]", "some": "[~]", "learning": "[o]", "strong": "[x]"}

        for skill, info in sorted_gaps:
            level_e = LEVEL_EMOJI.get(info["your_level"], "[ ]")
            req_marker = "!" if info["required_level"] == "required" else "?"
            count = len(info["positions"])
            lines.append(f"{req_marker} **{skill}** {level_e} ({info['your_level']}) -> needed by {count} position(s)")

    lines.append("")
    lines.append("Legend: ! required ? preferred | [ ] none [o] learning [~] some [x] strong")

    print("\n".join(lines))

def cmd_report_stats(args):
    """Generate stats overview as formatted Markdown."""
    positions = _fetch_pipeline_data()

    total = len(positions)
    statuses = [p["status"] for p in positions]
    priorities = [p["priority"] for p in positions]

    active = sum(1 for s in statuses if s not in ("rejected", "withdrawn", "offer"))
    by_status = {}
    for s in statuses:
        by_status[s] = by_status.get(s, 0) + 1
    high_pri = sum(1 for p in priorities if p == "high")

    lines = ["**📈 Job Search Stats**", ""]
    lines.append(f"📋 **{total}** total positions")
    lines.append(f"🚀 **{active}** active applications")
    lines.append(f"🔴 **{high_pri}** high priority")
    lines.append("")
    lines.append("**By Status:**")

    status_order = ["interviewing", "phone-screen", "applied", "researching", "offer", "rejected", "withdrawn"]
    for s in status_order:
        count = by_status.get(s, 0)
        if count > 0:
            emoji = STATUS_EMOJI.get(s, "•")
            lines.append(f"  {emoji} {s.replace('-', ' ').title()}: {count}")

    print("\n".join(lines))


# =============================================================================
# MAIN
# =============================================================================


def main():
    parser = argparse.ArgumentParser(
        description="Career Notebook CLI - Track applications and analyze opportunities"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # ingest-job
    p = subparsers.add_parser("ingest-job", help="Ingest a job posting (from URL or manual)")
    p.add_argument("--url", help="Job posting URL (omit for manual entry)")
    p.add_argument("--title", help="Position title (required if no --url)")
    p.add_argument("--company", help="Company name (matched to existing or created)")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Priority level")
    p.add_argument("--tags", nargs="+", help="Tags to apply")
    p.add_argument("--location", help="Job location")
    p.add_argument("--remote-policy", dest="remote_policy", choices=["remote", "hybrid", "onsite"], help="Remote policy")
    p.add_argument("--salary", help="Salary range")
    p.add_argument("--deadline", help="Application deadline (YYYY-MM-DD)")
    p.add_argument("--id", help="Specific position ID")

    # add-company
    p = subparsers.add_parser("add-company", help="Add a company")
    p.add_argument("--name", required=True, help="Company name")
    p.add_argument("--url", help="Company website")
    p.add_argument("--linkedin", help="LinkedIn company page")
    p.add_argument("--description", help="Brief description")
    p.add_argument("--location", help="Headquarters location")
    p.add_argument("--id", help="Specific ID")

    # add-position (deprecated — use ingest-job instead)
    p = subparsers.add_parser("add-position", help="[deprecated] Use ingest-job instead")
    p.add_argument("--title", required=True, help="Position title")
    p.add_argument("--company", help="Company name")
    p.add_argument("--url", help="Job posting URL")
    p.add_argument("--location", help="Job location")
    p.add_argument("--career-remote-policy", choices=["remote", "hybrid", "onsite"], help="Remote policy")
    p.add_argument("--salary", help="Salary range")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Priority level")
    p.add_argument("--deadline", help="Application deadline (YYYY-MM-DD)")
    p.add_argument("--id", help="Specific ID")

    # update-status
    p = subparsers.add_parser("update-status", help="Update application status")
    p.add_argument("--position", required=True, help="Position ID")
    p.add_argument(
        "--status",
        required=True,
        choices=[
            "researching",
            "applied",
            "phone-screen",
            "interviewing",
            "offer",
            "rejected",
            "withdrawn",
        ],
        help="New status",
    )
    p.add_argument("--date", help="Date of status change (YYYY-MM-DD)")

    # set-career-short-name
    p = subparsers.add_parser("set-career-short-name", help="Set short display name for a position")
    p.add_argument("--position", required=True, help="Position ID")
    p.add_argument("--name", required=True, help="Short name (e.g., 'anthropic', 'langchain')")

    # add-note
    p = subparsers.add_parser("add-note", help="Create a note")
    p.add_argument("--about", required=True, help="Entity ID this note is about")
    p.add_argument(
        "--type",
        required=True,
        choices=[
            "research",
            "interview",
            "strategy",
            "skill-gap",
            "fit-analysis",
            "interaction",
            "application",
            "primer",
            "relationship",
            "general",
        ],
        help="Note type",
    )
    p.add_argument("--content", help="Note content (inline)")
    p.add_argument("--content-file", help="Path to file containing note content")
    p.add_argument("--name", help="Note title")
    p.add_argument("--confidence", type=float, help="Confidence score (0.0-1.0)")
    p.add_argument("--tags", nargs="+", help="Tags to apply")
    p.add_argument("--alh-interaction-type", help="Type of interaction (for interaction notes)")
    p.add_argument("--alh-interaction-date", help="Date of interaction")
    p.add_argument("--career-interview-date", help="Date of interview")
    p.add_argument("--career-fit-score", type=float, help="Fit score (for fit-analysis notes)")
    p.add_argument("--career-fit-summary", help="Fit summary")
    p.add_argument("--id", help="Specific ID")

    # upsert-summary
    p = subparsers.add_parser("upsert-summary", help="Create or overwrite the opportunity summary")
    p.add_argument("--about", required=True, help="Opportunity ID")
    p.add_argument("--content", help="Summary content (inline markdown)")
    p.add_argument("--content-file", help="Path to file containing summary content")

    # regenerate-summary
    p = subparsers.add_parser("regenerate-summary", help="Fetch all notes for an opportunity (agent synthesizes summary)")
    p.add_argument("--about", required=True, help="Opportunity ID")

    # add-resource
    p = subparsers.add_parser("add-resource", help="Add a learning resource")
    p.add_argument("--name", required=True, help="Resource name")
    p.add_argument(
        "--type",
        required=True,
        choices=["course", "book", "tutorial", "project", "video"],
        help="Resource type",
    )
    p.add_argument("--url", help="Resource URL")
    p.add_argument("--hours", type=int, help="Estimated hours to complete")
    p.add_argument("--description", help="Description")
    p.add_argument("--skills", nargs="+", help="Skills this addresses")
    p.add_argument("--id", help="Specific ID")

    # link-resource
    p = subparsers.add_parser("link-resource", help="Link resource to requirement")
    p.add_argument("--resource", required=True, help="Resource ID")
    p.add_argument("--requirement", required=True, help="Requirement ID")

    # link-collection
    p = subparsers.add_parser("link-collection", help="Link paper collection to skill requirement(s)")
    p.add_argument("--collection", required=True, help="Collection ID")
    p.add_argument("--requirement", help="Specific requirement ID")
    p.add_argument("--skill", help="Skill name (links to all matching requirements)")

    # link-background
    p = subparsers.add_parser("link-background", help="Link paper collection to opportunity as background reading")
    p.add_argument("--opportunity", required=True, help="Opportunity ID (position, engagement, venture, lead)")
    p.add_argument("--collection", required=True, help="Collection ID (scilit-corpus, sltrend-thread, etc.)")
    p.add_argument("--description", help="Why this collection is relevant to the opportunity")

    # list-background
    p = subparsers.add_parser("list-background", help="List paper collections linked to an opportunity")
    p.add_argument("--opportunity", required=True, help="Opportunity ID")

    # link-paper
    p = subparsers.add_parser("link-paper", help="Soft-reference a scilit-paper (in alh_deep_research) from a learning resource")
    p.add_argument("--resource", required=True, help="Learning resource ID")
    p.add_argument("--paper", required=True, help="Paper ID (scilit-paper, lives in alh_deep_research)")
    p.add_argument("--ref", required=False, help="Optional human-readable reference (DOI/title)")

    # add-requirement
    p = subparsers.add_parser("add-requirement", help="Add a requirement to a position")
    p.add_argument("--position", required=True, help="Position ID")
    p.add_argument("--skill", required=True, help="Skill name")
    p.add_argument(
        "--level", choices=["required", "preferred", "nice-to-have"], help="Requirement level"
    )
    p.add_argument("--career-your-level", choices=["expert", "practiced", "aware", "none"], help="Your skill level (Bloom's: expert/practiced/aware/none)")
    p.add_argument("--content", help="Full requirement text")
    p.add_argument("--id", help="Specific ID")

    # add-skill (your profile)
    p = subparsers.add_parser("add-skill", help="Add/update a skill in your profile")
    p.add_argument(
        "--name", required=True, help="Skill name (e.g., 'Python', 'Distributed Systems')"
    )
    p.add_argument(
        "--level",
        required=True,
        choices=["expert", "practiced", "aware", "none"],
        help="Proficiency level (Bloom's): expert=can design/teach, practiced=hands-on, aware=conceptual, none=unknown",
    )
    p.add_argument("--evidence", help="What proves this level (project URL, publication, years)")
    p.add_argument("--recency", help="When last used (e.g., 'daily 2026', 'used 2019-2022')")
    p.add_argument("--description", help="Free text context about your experience")

    # list-skills
    subparsers.add_parser("list-skills", help="Show your skill profile")

    # add-concept
    p = subparsers.add_parser("add-concept", help="Add a skill concept to the vocabulary")
    p.add_argument("--name", required=True, help="Preferred label (canonical name)")
    p.add_argument("--alt-labels", dest="alt_labels", help="Comma-separated alternative labels")
    p.add_argument("--description", help="What this skill covers")
    p.add_argument("--broader", help="Name of broader concept (parent in hierarchy)")
    p.add_argument("--id", help="Specific ID")

    # list-concepts
    subparsers.add_parser("list-concepts", help="List skill concepts with proficiency levels (prompt-friendly)")

    # create-seeker-profile
    p = subparsers.add_parser("create-seeker-profile", help="Create a job-seeker role for a person")
    p.add_argument("--person", required=True, help="Person ID (e.g., op-f25ab4b15b0f)")
    p.add_argument("--name", help="Profile name (default: 'Job Search')")
    p.add_argument("--id", help="Custom role ID")
    p.add_argument("--target-role", dest="target_role", help="Target role title")
    p.add_argument("--industries", help="Target industries (comma-separated)")
    p.add_argument("--salary", help="Salary expectations (e.g., '180k-220k')")
    p.add_argument("--location", help="Location preference (e.g., 'Remote')")
    p.add_argument("--focus", help="Search focus (free text)")

    # list-artifacts
    p = subparsers.add_parser(
        "list-artifacts", help="List artifacts (job descriptions) with analysis status"
    )
    p.add_argument(
        "--status",
        choices=["raw", "analyzed", "all"],
        help="Filter: raw (needs sensemaking), analyzed (has notes), all",
    )

    # show-artifact
    p = subparsers.add_parser("show-artifact", help="Get artifact content for Claude to read")
    p.add_argument("--id", required=True, help="Artifact ID")

    # delete-position
    p = subparsers.add_parser("delete-position", help="Delete a position and all its related data")
    p.add_argument("--id", required=True, help="Position ID")

    # add-engagement
    p = subparsers.add_parser("add-engagement", help="Add a consulting/service engagement")
    p.add_argument("--name", required=True, help="Engagement name")
    p.add_argument("--company-id", dest="company_id", help="Company ID to link")
    p.add_argument("--type", choices=["hourly", "project", "retainer", "advisory"], help="Engagement type")
    p.add_argument("--rate", help="Rate info (e.g. '$200/hr', 'TBD', 'equity only')")
    p.add_argument("--status", choices=["proposal", "active", "paused", "closed"], help="Engagement status")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Priority level")
    p.add_argument("--deadline", help="Deadline (YYYY-MM-DD)")
    p.add_argument("--description", help="Description")
    p.add_argument("--id", help="Specific ID")

    # add-venture
    p = subparsers.add_parser("add-venture", help="Add a startup/advisory/equity venture")
    p.add_argument("--name", required=True, help="Venture name")
    p.add_argument("--company-id", dest="company_id", help="Company ID to link")
    p.add_argument("--stage", choices=["seed", "series-a", "series-b", "growth", "closed"], help="Venture stage")
    p.add_argument("--career-equity-type", dest="equity_type", choices=["none", "advisor", "cofounder", "investor"], help="Equity type")
    p.add_argument("--status", choices=["seed", "series-a", "series-b", "growth", "closed"], help="Venture status")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Priority level")
    p.add_argument("--deadline", help="Deadline (YYYY-MM-DD)")
    p.add_argument("--description", help="Description")
    p.add_argument("--id", help="Specific ID")

    # add-lead
    p = subparsers.add_parser("add-lead", help="Add an early-stage networking lead")
    p.add_argument("--name", required=True, help="Lead name/description")
    p.add_argument("--status", choices=["first-contact", "active", "inactive", "closed"], help="Lead status")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Priority level")
    p.add_argument("--description", help="Description")
    p.add_argument("--id", help="Specific ID")

    # update-opportunity
    p = subparsers.add_parser("update-opportunity", help="Update status/stage/priority of any opportunity")
    p.add_argument("--id", required=True, help="Opportunity ID")
    p.add_argument("--status", help="New opportunity status")
    p.add_argument("--stage", help="New venture stage")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="New priority")

    # show-opportunity
    p = subparsers.add_parser("show-opportunity", help="Show details for any opportunity")
    p.add_argument("--id", required=True, help="Opportunity ID")

    # list-opportunities
    p = subparsers.add_parser("list-opportunities", help="List opportunities by type/status")
    p.add_argument("--type", choices=["position", "engagement", "venture", "lead", "project", "all"], default="all", help="Opportunity type filter")
    p.add_argument("--status", help="Filter by opportunity status")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Filter by priority")
    p.add_argument("--person", help="Filter by person ID (via seeker-pipeline)")

    # add-person
    p = subparsers.add_parser("add-person", help="Add a person to the career graph")
    p.add_argument("--name", required=True, help="Person name")
    p.add_argument("--email", help="Email address (alh-email-address)")
    p.add_argument("--linkedin", help="LinkedIn profile URL")
    p.add_argument("--description", help="Who they are / how you know them")
    p.add_argument("--id", help="Specific ID")

    # list-people
    subparsers.add_parser("list-people", help="List people in the career graph")

    # show-person
    p = subparsers.add_parser("show-person", help="Show a person: contact roles, collaborations, relationship notes")
    p.add_argument("--id", required=True, help="Person ID")

    # add-project
    p = subparsers.add_parser("add-project", help="Add a career project (open-source, paper, product, community)")
    p.add_argument("--name", required=True, help="Project name")
    p.add_argument("--role", choices=["lead", "contributor", "advisor"], help="Your role on the project")
    p.add_argument("--status", choices=["exploring", "active", "paused", "shipped", "sunset"], help="Project status")
    p.add_argument("--url", help="Project URL (repo, paper, site)")
    p.add_argument("--company-id", dest="company_id", help="Organization ID to link")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Priority level")
    p.add_argument("--description", help="Description")
    p.add_argument("--id", help="Specific ID")

    # list-projects
    p = subparsers.add_parser("list-projects", help="List career projects with collaborators")
    p.add_argument("--status", choices=["exploring", "active", "paused", "shipped", "sunset"], help="Filter by project status")
    p.add_argument("--role", choices=["lead", "contributor", "advisor"], help="Filter by your project role")

    # update-project
    p = subparsers.add_parser("update-project", help="Update role/status/url/priority of a project")
    p.add_argument("--id", required=True, help="Project ID")
    p.add_argument("--role", choices=["lead", "contributor", "advisor"], help="New project role")
    p.add_argument("--status", choices=["exploring", "active", "paused", "shipped", "sunset"], help="New project status")
    p.add_argument("--url", help="New project URL")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="New priority")

    # link-collaborator
    p = subparsers.add_parser("link-collaborator", help="Link a person to a project or opportunity")
    p.add_argument("--person", required=True, help="Person ID")
    p.add_argument("--target", required=True, help="Project or opportunity ID")
    p.add_argument("--role", required=True, choices=["collaborator", "mentor", "sponsor", "reference", "co-author"], help="Collaboration role")
    p.add_argument("--since", help="Collaboration start date (YYYY-MM-DD)")
    p.add_argument("--strength", choices=["weak", "working", "strong"], help="Relationship strength")

    # list-collaborators
    p = subparsers.add_parser("list-collaborators", help="List collaborations by person or by project/opportunity")
    p.add_argument("--person", help="Person ID")
    p.add_argument("--target", help="Project or opportunity ID")

    # migrate-from-jobhunt
    p = subparsers.add_parser("migrate-from-jobhunt", help="Run the GLAV mapping rules copying legacy jhunt-* data into career-* types (no-op if no legacy data)")
    p.add_argument("--dry-run", action="store_true", help="Report what would be migrated without writing")

    # list-pipeline
    p = subparsers.add_parser("list-pipeline", help="Show application pipeline")
    p.add_argument("--status", help="Filter by status")
    p.add_argument("--priority", choices=["high", "medium", "low"], help="Filter by priority")
    p.add_argument("--tag", help="Filter by tag")
    p.add_argument("--person", help="Filter by person ID (via seeker-pipeline)")

    # show-position
    p = subparsers.add_parser("show-position", help="Get position details")
    p.add_argument("--id", required=True, help="Position ID")

    # show-company
    p = subparsers.add_parser("show-company", help="Get company details")
    p.add_argument("--id", required=True, help="Company ID")

    # show-gaps
    p = subparsers.add_parser("show-gaps", help="Show skill gaps")
    p.add_argument(
        "--priority", choices=["high", "medium", "low"], help="Filter by position priority"
    )
    p.add_argument(
        "--all", action="store_true", help="Include researching positions (default: only past researching)"
    )

    # learning-plan
    subparsers.add_parser("learning-plan", help="Show prioritized learning plan")

    # tag
    p = subparsers.add_parser("tag", help="Tag an entity")
    p.add_argument("--entity", required=True, help="Entity ID")
    p.add_argument("--tag", required=True, help="Tag name")

    # search-tag
    p = subparsers.add_parser("search-tag", help="Search by tag")
    p.add_argument("--tag", required=True, help="Tag to search for")

    # cache-stats
    subparsers.add_parser("cache-stats", help="Show cache statistics")

    # report commands (Markdown output for messaging apps)
    p = subparsers.add_parser("report-pipeline", help="Pipeline report (Markdown)")
    p = subparsers.add_parser("report-stats", help="Stats overview (Markdown)")
    p = subparsers.add_parser("report-gaps", help="Skill gaps report (Markdown)")
    p = subparsers.add_parser("report-position", help="Position detail report (Markdown)")
    p.add_argument("--id", required=True, help="Position ID")

    args = parser.parse_args()

    if not TYPEDB_AVAILABLE:
        print(json.dumps({"success": False, "error": "typedb-driver not installed"}))
        sys.exit(1)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        # Ingestion
        "ingest-job": cmd_ingest_job,
        "add-company": cmd_add_company,
        "add-position": cmd_add_position,
        # Your skill profile
        "add-skill": cmd_add_skill,
        "add-concept": cmd_add_concept,
        "list-concepts": cmd_list_concepts,
        "list-skills": cmd_list_skills,
        "create-seeker-profile": cmd_create_seeker_profile,
        # Artifacts (for sensemaking)
        "list-artifacts": cmd_list_artifacts,
        "show-artifact": cmd_show_artifact,
        # Application tracking
        "update-status": cmd_update_status,
        "set-career-short-name": cmd_set_short_name,
        "add-note": cmd_add_note,
        "upsert-summary": cmd_upsert_summary,
        "regenerate-summary": cmd_regenerate_summary,
        "add-resource": cmd_add_resource,
        "link-resource": cmd_link_resource,
        "link-collection": cmd_link_collection,
        "link-background": cmd_link_background,
        "list-background": cmd_list_background,
        "link-paper": cmd_link_paper,
        "add-requirement": cmd_add_requirement,
        # Delete
        "delete-position": cmd_delete_position,
        # Opportunity model
        "add-engagement": cmd_add_engagement,
        "add-venture": cmd_add_venture,
        "add-lead": cmd_add_lead,
        "update-opportunity": cmd_update_opportunity,
        "show-opportunity": cmd_show_opportunity,
        "list-opportunities": cmd_list_opportunities,
        # Career graph (people, collaborators, projects)
        "add-person": cmd_add_person,
        "list-people": cmd_list_people,
        "show-person": cmd_show_person,
        "add-project": cmd_add_project,
        "list-projects": cmd_list_projects,
        "update-project": cmd_update_project,
        "link-collaborator": cmd_link_collaborator,
        "list-collaborators": cmd_list_collaborators,
        # Legacy migration
        "migrate-from-jobhunt": cmd_migrate_from_jobhunt,
        # Queries
        "list-pipeline": cmd_list_pipeline,
        "show-position": cmd_show_position,
        "show-company": cmd_show_company,
        "show-gaps": cmd_show_gaps,
        "learning-plan": cmd_learning_plan,
        "tag": cmd_tag,
        "search-tag": cmd_search_tag,
        # Cache
        "cache-stats": cmd_cache_stats,
        # Reports (Markdown)
        "report-pipeline": cmd_report_pipeline,
        "report-stats": cmd_report_stats,
        "report-gaps": cmd_report_gaps,
        "report-position": cmd_report_position,
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
