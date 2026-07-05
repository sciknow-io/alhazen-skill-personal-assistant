#!/usr/bin/env python3
"""
GLAV mapping runner — standalone, schema_mapper.py-compatible.

Executes declarative GLAV rules (source_match fetch -> target_insert) between
two TypeDB databases, or within one database (source-db == target-db), as used
for the jhunt-* -> career-* migration.

This is a self-contained mirror of skillful-alhazen's
`src/skillful_alhazen/utils/schema_mapper.py` runner so the migration can run
from a plugin install without the main repo checked out. Same CLI shape:

    uv run python skills/career/mapping/glav_runner.py run \
        --source-db alh_personal \
        --target-db alh_personal \
        --rules-dir skills/career/mapping/rules \
        [--rule <name>] [--dry-run]

Rule format (superset of the dismech mapping rules):

    name: positions                  # rule id, used by depends_on
    description: ...
    depends_on: [companies]          # must appear earlier in filename order
    idempotent: true                 # target_check consulted per row
    skolem_prefix: position          # entity rules: fresh id prefix
    skolem_keys: [id]                # fields hashed into $skolem_id
    datetime_attrs: [career-applied-date]   # target attrs inserted unquoted
    source_match: |                  # fetch over SOURCE db; keys become $vars
      match ... fetch { "id": $p.id, ... };
    target_check: |                  # fetch over TARGET db; rows > 0 => skip
      match $x isa career-position, has career-legacy-id $id; fetch {"id": $x.id};
    target_insert: |                 # (match+)insert over TARGET db
      insert $tp isa career-position, has id $skolem_id, has career-legacy-id $id;
    optional_attrs:                  # fetched key -> target attribute; appended
      short_name: career-short-name  #   to the first insert statement when the
      ...                            #   value is present (lists repeat)

Environment: TYPEDB_HOST / TYPEDB_PORT / TYPEDB_USERNAME / TYPEDB_PASSWORD.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: pyyaml required (pip install pyyaml)", file=sys.stderr)
    sys.exit(1)

try:
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB
except ImportError:
    print("ERROR: typedb-driver required (pip install 'typedb-driver>=3.7.0')", file=sys.stderr)
    sys.exit(1)

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")


def get_driver():
    """Compatible with typedb-driver 3.7-3.10 and >= 3.11."""
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


def escape_string(s: str) -> str:
    return (
        s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "")
    )


def to_datetime_literal(value) -> str:
    """Normalize a value to an unquoted TypeQL datetime literal."""
    if isinstance(value, (datetime, date)):
        value = value.isoformat()
    s = str(value).strip()
    s = re.sub(r"(Z|[+-]\d{2}:\d{2})$", "", s)  # TypeQL datetime is offset-free
    if "T" not in s:
        s += "T00:00:00"
    return s


def to_literal(value, is_datetime=False) -> str:
    if is_datetime:
        return to_datetime_literal(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    return f'"{escape_string(str(value))}"'


def skolemize(prefix: str, keys, row) -> str:
    basis = "|".join(str(row.get(k, "")) for k in keys)
    return f"{prefix}-{hashlib.sha1(basis.encode()).hexdigest()[:12]}"


def substitute(template: str, values: dict) -> str:
    """Replace $<key> tokens with pre-rendered literal strings.

    Single-pass with a lambda replacement: re.sub replacement STRINGS would
    reprocess backslash escapes (turning an escaped \\n back into a raw
    newline inside a TypeQL string literal), and value text containing
    $-prefixed words must never be rescanned as tokens.
    """
    if not values:
        return template
    pattern = r"\$(" + "|".join(re.escape(k) for k in sorted(values, key=len, reverse=True)) + r")\b"
    return re.sub(pattern, lambda m: values[m.group(1)], template)


def render_literals(rule: dict, row: dict, skolem_id=None) -> dict:
    """Pre-render every fetched value (and $skolem_id) as a TypeQL literal."""
    lits = {k: to_literal(v) for k, v in row.items() if v is not None}
    if skolem_id is not None:
        lits["skolem_id"] = to_literal(skolem_id)
    return lits


def build_insert(rule: dict, row: dict, skolem_id) -> str:
    """Splice optional-attr placeholders into the RAW template (before any
    literal text exists, so a ';' inside a value string can never be mistaken
    for the statement terminator), then substitute all literals at once."""
    template = rule["target_insert"]
    optional = rule.get("optional_attrs") or {}
    dt_attrs = set(rule.get("datetime_attrs") or [])
    lits = render_literals(rule, row, skolem_id)

    extras = []
    for key, attr in optional.items():
        value = row.get(key)
        if value is None or value == "" or value == []:
            continue
        items = value if isinstance(value, list) else [value]
        for i, item in enumerate(items):
            placeholder = f"{key}__{i}"
            lits[placeholder] = to_literal(item, is_datetime=attr in dt_attrs)
            extras.append(f"has {attr} ${placeholder}")
    if extras:
        idx = template.find("insert")
        semi = template.find(";", idx)
        if semi == -1:
            raise ValueError("target_insert has no terminating ';'")
        template = template[:semi] + ",\n      " + ",\n      ".join(extras) + template[semi:]
    return substitute(template, lits)


def unresolved_vars(query: str) -> list:
    """$vars still present after substitution (excluding declared insert/match
    concept vars like $tp, $tn, $ts — heuristically, vars used after 'isa' or
    declared on the left of 'isa'/relation tuples are fine; what must NOT
    remain are value placeholders, i.e. vars right after 'has <attr>' or
    inside relation parens as role-player ids). We simply flag vars that were
    fetched-key-shaped (contain '_' or are 'id')."""
    return [v for v in set(re.findall(r"\$([a-z][a-z0-9_]*)\b", query)) if "_" in v or v == "id"]


def load_rules(rules_dir: Path):
    rules = []
    for path in sorted(rules_dir.glob("*.yaml")):
        with open(path) as fh:
            rule = yaml.safe_load(fh)
        rule["_file"] = path.name
        rules.append(rule)
    seen = set()
    for rule in rules:
        for dep in rule.get("depends_on") or []:
            if dep not in seen:
                print(
                    f"WARNING: rule '{rule['name']}' depends on '{dep}' which does not "
                    f"appear earlier in filename order",
                    file=sys.stderr,
                )
        seen.add(rule["name"])
    return rules


def run_rule(driver, rule, source_db, target_db, dry_run):
    result = {"rule": rule["name"], "file": rule["_file"], "source_rows": 0,
              "inserted": 0, "skipped_existing": 0, "errors": []}

    try:
        with driver.transaction(source_db, TransactionType.READ) as tx:
            rows = list(tx.query(rule["source_match"]).resolve())
    except Exception as e:
        # Source types absent (fresh install with no legacy schema) => no-op.
        result["note"] = f"source query failed — treated as no legacy data: {str(e)[:200]}"
        return result
    result["source_rows"] = len(rows)
    if not rows:
        return result

    tx_type = TransactionType.READ if dry_run else TransactionType.WRITE
    with driver.transaction(target_db, tx_type) as tx:
        for row in rows:
            try:
                skolem_id = None
                if rule.get("skolem_prefix"):
                    skolem_id = skolemize(rule["skolem_prefix"], rule.get("skolem_keys") or ["id"], row)

                if rule.get("idempotent", True) and rule.get("target_check"):
                    check_q = substitute(rule["target_check"], render_literals(rule, row, skolem_id))
                    if list(tx.query(check_q).resolve()):
                        result["skipped_existing"] += 1
                        continue

                insert_q = build_insert(rule, row, skolem_id)
                leftover = unresolved_vars(insert_q)
                if leftover:
                    raise ValueError(f"unresolved value vars {leftover} (missing required field?)")
                if not dry_run:
                    tx.query(insert_q).resolve()
                result["inserted"] += 1
            except Exception as e:
                result["errors"].append(str(e)[:300])
                if len(result["errors"]) >= 10:
                    result["errors"].append("...further errors suppressed")
                    break
        if not dry_run:
            tx.commit()
    return result


def cmd_run(args):
    rules = load_rules(Path(args.rules_dir))
    if args.rule:
        rules = [r for r in rules if r["name"] == args.rule]
        if not rules:
            print(json.dumps({"success": False, "error": f"rule '{args.rule}' not found"}))
            sys.exit(1)

    results = []
    with get_driver() as driver:
        for rule in rules:
            results.append(run_rule(driver, rule, args.source_db, args.target_db, args.dry_run))

    ok = all(not r["errors"] for r in results)
    print(json.dumps({
        "success": ok,
        "dry_run": args.dry_run,
        "source_db": args.source_db,
        "target_db": args.target_db,
        "rules": results,
        "totals": {
            "source_rows": sum(r["source_rows"] for r in results),
            "inserted": sum(r["inserted"] for r in results),
            "skipped_existing": sum(r["skipped_existing"] for r in results),
            "errors": sum(len(r["errors"]) for r in results),
        },
    }, indent=2))
    sys.exit(0 if ok else 1)


def main():
    parser = argparse.ArgumentParser(description="GLAV mapping runner (schema_mapper-compatible)")
    sub = parser.add_subparsers(dest="command", required=True)
    runp = sub.add_parser("run", help="Run mapping rules")
    runp.add_argument("--source-db", required=True)
    runp.add_argument("--target-db", required=True)
    runp.add_argument("--rules-dir", required=True)
    runp.add_argument("--rule", help="Run a single rule by name")
    runp.add_argument("--dry-run", action="store_true", help="Report without writing")
    args = parser.parse_args()
    cmd_run(args)


if __name__ == "__main__":
    main()
