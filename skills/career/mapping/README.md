# jobhunt -> career Mapping Rules

GLAV mapping from the legacy `jhunt-*` namespace to `career-*` types **within
the same database** (`alh_personal`). Same rule format and runner CLI as the
dismech mapping in skillful-alhazen; a standalone runner (`glav_runner.py`) is
bundled so the migration works from a plugin install without the main repo.

Every migrated copy gets a fresh deterministic id (`$skolem_id`, sha1 of the
source id) and records its source id in **`career-legacy-id`** — the natural
key that relation rules use to resolve foreign keys, and that `target_check`
uses for idempotency. Reruns are safe.

## Rule Phases

**Phase 1 — Standalone entities:**
- `01_companies` — jhunt-company -> career-company
- `02_skill_concepts` — jhunt-skill-concept -> career-skill-concept (multi-valued alt-labels)
- `03_your_skills` — jhunt-your-skill -> career-your-skill
- `04_search_sources` — jhunt-search-source -> career-search-source
- `05_learning_resources` — jhunt-learning-resource -> career-learning-resource
- `06_agent_role` — jhunt-job-seeker-role -> career-agent-role
- `07_candidates` — jhunt-candidate -> career-candidate

**Phase 2 — Opportunities:**
- `10_positions`, `11_ventures`, `12_leads`, `13_engagements`

**Phase 3 — Fragments, artifacts, notes:**
- `15_requirements` — jhunt-requirement -> career-requirement
- `20_job_descriptions` — jhunt-job-description -> career-job-description
- `21`–`28` — research / interview / strategy / skill-gap / fit-analysis /
  interaction / opp-summary / dashboard-state notes

**Phase 4 — Relations (matched through career-legacy-id):**
- `30_position_at_company`, `31_opportunity_at_organization`,
  `32_requirement_for`, `33_skill_hierarchy`, `34_source_provides`,
  `35_seeker_pipeline`, `36_seeker_has_skill`
- `40_aboutness` — re-links migrated notes to migrated subjects (rows whose
  endpoints were not migrated match nothing and insert nothing)
- `41_representation` — re-links job-description artifacts to positions

Zero-instance legacy types (cc-brief / cc-feedback / learning-plan notes,
resume / cover-letter / company-page / proposal artifacts, skill-definition /
addresses-requirement / contact-for-opportunity / background-reading
relations) have no rules; add them alongside these if such data ever appears
in a legacy database. `13_engagements` is included as the template to copy.

## Running

Prerequisite: the career schema (including `career-legacy-id`) must be loaded
into the target database.

```bash
# Preferred (skillful-alhazen checkout):
uv run python src/skillful_alhazen/utils/schema_mapper.py run \
  --source-db alh_personal --target-db alh_personal \
  --rules-dir skills/career/mapping/rules --dry-run

# Standalone (bundled runner, same CLI):
uv run python skills/career/mapping/glav_runner.py run \
  --source-db alh_personal --target-db alh_personal \
  --rules-dir skills/career/mapping/rules --dry-run
```

Drop `--dry-run` to write; `--rule <name>` runs a single rule. `career.py
migrate-from-jobhunt` is a convenience wrapper over the bundled runner.

Accounting note: for the match-guarded relation rules, `inserted` counts rows
*attempted*; a row whose endpoints were not migrated inserts nothing. Compare
target relation counts against source counts to verify (see SKILL.md § Migration).
