#!/usr/bin/env python3
"""
validate_views.py -- VPDMf view spec validator for the career dashboard.

Usage:
    python validate_views.py [--views-dir views/] [--schema ../schema.tql]

Checks:
  - primary_type / target_type in known entity types
  - via_relation in known relation types
  - via_role / target_role in known role names
  - target_view (for linked_list portals) has a matching YAML file
  - Coverage report: COVERED / INLINE ONLY / UNREACHABLE entity types
"""

import argparse
import os
import re
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML not installed. Run: pip install pyyaml", file=sys.stderr)
    sys.exit(1)

# ---------------------------------------------------------------------------
# Base-schema whitelists (types that exist in alhazen_notebook.tql but are not
# necessarily repeated in the career namespace schema.tql)
# ---------------------------------------------------------------------------
BASE_ENTITY_TYPES = {
    "identifiable-entity",
    "domain-thing",
    "collection",
    "information-content-entity",
    "artifact",
    "fragment",
    "note",
    "agent",
    "scilit-paper",   # from scientific-literature skill schema
}

BASE_RELATION_TYPES = {
    "aboutness",
    "containment",
    "provenance-of",
    "alh-role-bearing",   # core: person <-> role
}

BASE_ROLE_NAMES = {
    "note",
    "subject",
    "member",
    "container",
    "source",
    "target",
    "bearer",       # alh-role-bearing
    "borne-role",   # alh-role-bearing
}

KNOWN_COMPONENT_KINDS = {
    "special_panel",
    "table",
    "notes_group",
    "artifact_detail",
    "member_list",
}

# ---------------------------------------------------------------------------
# Schema parsing
# ---------------------------------------------------------------------------

def parse_schema(schema_path: Path):
    """Extract entity types, relation types, and role names from a .tql file."""
    entity_types = set(BASE_ENTITY_TYPES)
    relation_types = set(BASE_RELATION_TYPES)
    role_names = set(BASE_ROLE_NAMES)

    if not schema_path.exists():
        print(f"  WARNING: schema file not found: {schema_path} -- using base whitelist only")
        return entity_types, relation_types, role_names

    text = schema_path.read_text(encoding="utf-8")
    # Strip comments first: a comment ending in the word "entity"/"relation"
    # otherwise consumes the definition keyword on the following line.
    text = re.sub(r'#.*', '', text)

    # entity X sub Y  or  entity X @abstract sub Y
    for m in re.finditer(r'\bentity\s+([\w-]+)', text):
        entity_types.add(m.group(1))

    # relation X,  or  relation X sub relation,
    for m in re.finditer(r'\brelation\s+([\w-]+)', text):
        relation_types.add(m.group(1))

    # relates role-name  (optionally followed by as / , / ;)
    for m in re.finditer(r'\brelates\s+([\w-]+)', text):
        role_names.add(m.group(1))

    return entity_types, relation_types, role_names


# ---------------------------------------------------------------------------
# View validation helpers
# ---------------------------------------------------------------------------

def collect_strings(obj, key):
    """Walk a nested dict/list and yield every string value for the given key."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key and isinstance(v, str):
                yield v
            else:
                yield from collect_strings(v, key)
    elif isinstance(obj, list):
        for item in obj:
            yield from collect_strings(item, key)


def validate_hub(data, view_slugs, errors, warnings):
    """Validate hub.yaml (no primary_type; just check tab entity_view references)."""
    for tab in data.get("tabs", []):
        ev = tab.get("entity_view")
        if ev and ev not in view_slugs:
            errors.append(f"  tab '{tab.get('id')}': entity_view '{ev}' has no corresponding view YAML")
    return errors, warnings


def validate_view(slug, data, entity_types, relation_types, role_names, view_slugs,
                  errors, warnings):
    """Validate a single view YAML file."""

    # primary_type
    pt = data.get("primary_type")
    if pt and pt not in entity_types:
        errors.append(f"  primary_type '{pt}' not in known entity types")

    # Walk all via_relation / target_type / via_role / target_role / target_view
    for rel in collect_strings(data, "via_relation"):
        if rel not in relation_types:
            errors.append(f"  via_relation '{rel}' not in known relation types")

    for tt in collect_strings(data, "target_type"):
        if tt not in entity_types:
            errors.append(f"  target_type '{tt}' not in known entity types")

    for role in collect_strings(data, "via_role"):
        if role not in role_names:
            errors.append(f"  via_role '{role}' not in known role names")

    for role in collect_strings(data, "target_role"):
        if role not in role_names:
            errors.append(f"  target_role '{role}' not in known role names")

    for tv in collect_strings(data, "target_view"):
        if tv not in view_slugs:
            errors.append(f"  target_view '{tv}' has no corresponding view YAML")

    # Check component kinds
    for col_key in ("main_column", "side_column"):
        for component in data.get("detail", {}).get(col_key, []):
            kind = component.get("kind")
            if kind and kind not in KNOWN_COMPONENT_KINDS:
                warnings.append(f"  component kind '{kind}' is not in known kinds (may be intentional)")

    # Attribute field checking deferred to v2
    warnings.append("  attribute field name checking deferred to v2 (not validated)")

    return errors, warnings


# ---------------------------------------------------------------------------
# Coverage report
# ---------------------------------------------------------------------------

def coverage_report(all_views, entity_types):
    """Categorise all known entity types into COVERED / INLINE ONLY / UNREACHABLE."""
    covered = set()           # has own view YAML
    inline_only = set()       # appears only as target_type in portals/components
    all_target_types = set()

    for slug, data in all_views.items():
        if slug == "hub":
            continue
        pt = data.get("primary_type")
        if pt:
            covered.add(pt)
        for tt in collect_strings(data, "target_type"):
            all_target_types.add(tt)

    inline_only = all_target_types - covered

    # Career-specific entity types (filter to just career-* + a few core ones)
    career_types = {t for t in entity_types if t.startswith("career-") or t == "collection"}
    unreachable = career_types - covered - inline_only

    return covered, inline_only, unreachable


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Validate VPDMf view spec YAML files")
    parser.add_argument("--views-dir", default="views/", help="Directory containing view YAML files")
    parser.add_argument("--schema", default="../schema.tql", help="Path to schema.tql")
    args = parser.parse_args()

    views_dir = Path(args.views_dir)
    schema_path = Path(args.schema)

    if not views_dir.exists():
        print(f"ERROR: views directory not found: {views_dir}", file=sys.stderr)
        sys.exit(1)

    # Parse schema
    print(f"Parsing schema: {schema_path}")
    entity_types, relation_types, role_names = parse_schema(schema_path)
    print(f"  Found {len(entity_types)} entity types, {len(relation_types)} relation types, "
          f"{len(role_names)} role names")
    print()

    # Load all YAML files
    yaml_files = sorted(views_dir.glob("*.yaml"))
    if not yaml_files:
        print(f"ERROR: no YAML files found in {views_dir}", file=sys.stderr)
        sys.exit(1)

    all_views = {}
    for yf in yaml_files:
        with open(yf) as f:
            data = yaml.safe_load(f)
        # Determine slug: hub.yaml uses 'hub' key; view YAMLs use 'view' key
        slug = data.get("view") or data.get("hub") or yf.stem
        all_views[slug] = data

    view_slugs = set(all_views.keys())
    print(f"Loaded {len(all_views)} view files: {', '.join(sorted(view_slugs))}")
    print()

    # Validate each file
    total_errors = 0
    total_warnings = 0

    for slug, data in sorted(all_views.items()):
        errors = []
        warnings = []

        if slug == "career" or "hub" in data:
            validate_hub(data, view_slugs, errors, warnings)
            label = "hub.yaml"
        else:
            validate_view(slug, data, entity_types, relation_types, role_names,
                          view_slugs, errors, warnings)
            is_stub = "NOT YET BUILT" in (data.get("notes") or "")
            label = f"{slug}.yaml" + (" (stub)" if is_stub else "")

        if errors:
            print(f"  FAIL  {label}")
            for e in errors:
                print(f"    ERROR: {e}")
            total_errors += len(errors)
        else:
            print(f"  OK    {label}")

        for w in warnings:
            print(f"    WARNING: {w}")
            total_warnings += 1

    print()

    # Coverage report
    print("=" * 60)
    print("COVERAGE REPORT")
    print("=" * 60)

    covered, inline_only, unreachable = coverage_report(all_views, entity_types)

    print(f"\nCOVERED ({len(covered)}) -- entity types with their own view page:")
    for t in sorted(covered):
        print(f"  {t}")

    print(f"\nINLINE ONLY ({len(inline_only)}) -- appear only as portal/component targets:")
    for t in sorted(inline_only):
        print(f"  {t}")

    print(f"\nUNREACHABLE ({len(unreachable)}) -- in schema but not referenced in any view:")
    for t in sorted(unreachable):
        print(f"  {t}")

    print()
    print("=" * 60)
    if total_errors == 0:
        print(f"PASSED -- 0 errors, {total_warnings} warnings")
    else:
        print(f"FAILED -- {total_errors} errors, {total_warnings} warnings")
        sys.exit(1)


if __name__ == "__main__":
    main()
