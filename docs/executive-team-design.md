# Executive AI Team — Design Spec

This repo implements a "digital executive team" of Alhazen skills, all sharing the
`alh_personal` TypeDB database. The roster follows the four AI team members every
leader should hire, plus the pivoted career skill and the existing health coach:

| Skill | Team member | Namespace | Dashboard path |
|-------|-------------|-----------|----------------|
| **analyst** | Research analyst — decision-framed research, multi-thread consensus, verification | `anlst-` | `/analyst` |
| **advisor** | Strategic thought partner — board of advisor personas, debates, bias checks, scenario stress-tests | `advsr-` | `/advisor` |
| **scribe** | Communication expert — voice profiles, audience personas, review loops, dimension scoring | `scribe-` | `/scribe` |
| **ops** | Operational powerhouse — briefs, stakeholder CRM, meeting prep, commitments, monitors | `ops-` | `/ops` |
| **career** | (pivot of jobhunt) — people, collaborators, projects, and potential new positions | `career-` | `/career` |
| **coach** | Health & fitness monitoring (pre-existing) | `coach-` | `/coach` |

Capstone: a **chief-of-staff** orchestration layer (docs + thin skill) that reads
across all namespaces — earned only after each individual team member has mileage.

All skills obey [operating-principles.md](operating-principles.md). Recurring
structural commitments:

1. **Primer notes** — every create-workflow stores the operator's messy initial
   brain dump as a `<ns>-primer-note`.
2. **Interview notes** — every complex workflow starts with the agent interviewing
   the operator; recorded as `<ns>-interview-note`.
3. **Plan/execute split** — work-in-flight entities carry a status that includes a
   planning state before an executing state; plans stored as `<ns>-plan-note`.
4. **Operator checkpoints** — SKILL.md workflows mark ⏸ OPERATOR CHECKPOINT
   steps; everything else is agent work.

## Repo conventions (all skills MUST follow)

Every skill directory `skills/<name>/` contains:

```
schema.tql                  # TypeDB 3.x schema, single namespace prefix, subtypes of alh-* core types
<name>.py                   # CLI: argparse subcommands, JSON to stdout, same driver bootstrap as jobhunt.py/coach.py
SKILL.md                    # frontmatter (name, description, triggers, read_strategy) + workflow doc
skill.yaml                  # metadata manifest (pattern of skills/jobhunt/skill.yaml)
pyproject.toml              # uv project, typedb-driver>=3.8.0 (+ only deps actually used)
.python-version             # 3.12
.standalone-db              # marker file (copy from jobhunt, same text)
.claude-plugin/plugin.json  # deps on alhazen-core + typedb-notebook @ skillful-alhazen
hooks/hooks.json            # SessionStart hook loading schema.tql into alh_personal (copy jobhunt's verbatim)
quality-checks.yaml         # declarative audit rules (jobhunt pattern) where meaningful
dashboard/
  views/hub.yaml            # declarative hub spec (tabs, filters, components) — jobhunt/coach pattern
  views/<entity>.yaml       # per-entity detail view specs as needed
  lib.ts                    # CLI wrapper (skill-gateway first, execFile uv fallback) — jobhunt lib.ts pattern
  components/*.tsx          # React components referenced by views
  routes/**/route.ts        # Next.js API routes wrapping lib.ts functions
  pages/<name>/page.tsx     # hub page (+ detail pages with [id] where needed)
```

Core `alh-*` types available (defined in skillful-alhazen core schema):
`alh-person`, `alh-organization`, `alh-role`, `alh-domain-thing`, `alh-artifact`,
`alh-fragment`, `alh-note`, `alh-collection`, `alh-aboutness` (note→subject),
`alh-role-bearing` (role→person), plus common attributes (`name`, `description`,
`created-at`, `provenance`, `alh-location`, `alh-interaction-type`,
`alh-interaction-date`, `confidence`, tags). Follow jobhunt/coach usage precisely;
do not invent new core types — extend within your namespace.

CLI conventions: `uv run python skills/<name>/<name>.py <command> --flags`;
commands emit a single JSON object; Markdown `report-*` variants for human
display; `--about <id>` notes attach via `alh-aboutness`; ids are
`<type>-<hash12>`. Keep the "script stores/queries, Claude does sensemaking"
division exactly as jobhunt does.

---

## analyst — the research analyst you always wanted

**Purpose:** research is always run *with a decision in mind*, briefed like an
analyst (not queried like a search engine): constrain time horizon, source
priority, exclusions, reliability standards. Multi-thread "wisdom of the crowd"
runs, consensus aggregation, independent verification, the three-question gate,
and deliverables beyond walls of text.

**Entities** (sub `alh-domain-thing` unless noted):
- `anlst-mission` — the research engagement. Attrs: `anlst-decision-context`
  (what decision this serves), `anlst-time-horizon`, `anlst-source-policy`,
  `anlst-exclusions`, `anlst-mission-status`
  (`briefing | planning | running | aggregating | verifying | gated | delivered`),
  `anlst-priority-level`, deadline.
- `anlst-run` — one research thread (one model/session). Attrs: `anlst-model-name`,
  `anlst-run-status`, `anlst-started-at`, `anlst-completed-at`.
- `anlst-finding` (sub `alh-fragment`) — one discrete claim. Attrs: `anlst-claim`,
  `anlst-confidence-level`, `anlst-consensus-count`, `anlst-divergent` (boolean),
  `anlst-verification-status` (`unverified | confirmed | refuted | needs-work`).
- `anlst-source` (sub `alh-artifact`) — evidence. Attrs: `anlst-source-url`,
  `anlst-source-kind`, `anlst-reliability`.
- `anlst-deliverable` (sub `alh-artifact`) — output. Attrs: `anlst-deliverable-format`
  (`brief | dashboard | infographic | interactive-page | audio-summary`).
- Notes: `anlst-primer-note`, `anlst-interview-note`, `anlst-plan-note`,
  `anlst-verification-note`, `anlst-gate-note` (three answers + pass/fail),
  `anlst-synthesis-note`.

**Relations:** `anlst-mission-run` (mission↔run), `anlst-run-yielded`
(run↔finding), `anlst-finding-source` (finding↔source),
`anlst-mission-deliverable`, `anlst-mission-for-decision` (mission↔`advsr-decision`
declared cross-namespace in advisor's schema? NO — soft string ref
`anlst-decision-ref` instead; no cross-plugin schema deps).

**CLI:** `create-mission` (with `--primer`), `add-interview`, `add-plan`,
`add-run`, `complete-run`, `add-finding` (`--run`), `link-source`,
`record-consensus` (recompute consensus-count/divergent across runs by claim
match — agent supplies groupings), `verify-finding`, `record-gate`,
`add-deliverable`, `update-mission`, `list-missions`, `show-mission`,
`list-findings` (`--divergent`, `--unverified`), `report-mission`, `audit`.

**SKILL.md workflow:** brief→interview (⏸)→plan (⏸ approve)→fan out 3+ parallel
runs (Agent tool / separate sessions; same prompt each run)→record findings per
run→consensus pass (100% consensus ≈ factual; single-thread claims → re-research)
→verification in a *fresh* thread→three-question gate (⏸)→deliverable choice.

**Dashboard tabs:** Missions (board by mission-status) · Mission detail
(consensus matrix: findings × runs, verification badges, gate status) · Findings
(table, filters: divergent/unverified) · Deliverables.

---

## advisor — the strategic thought partner / board of advisors

**Purpose:** the 24/7 no-ego sounding board for the loneliness at the top —
decisions you can't yet take to the board or the team. Persona-based board of
advisors that debate then converge, calibrated pushback (no sycophancy, no
devil's-advocate-for-sport), bias surfacing, scenario stress-tests, and a
decision journal. Context is everything: a personal context system feeds every
conversation.

**Entities:**
- `advsr-advisor` — a persona seat on the board. Attrs: `advsr-archetype`,
  `advsr-decision-style`, `advsr-pushback-level` (`gentle | firm | relentless`),
  `advsr-inspiration` (real mentor / public figure whose thinking it channels),
  `advsr-charter` (what this seat is for).
- `advsr-decision` — a decision in flight. Attrs: `advsr-question`,
  `advsr-decision-status` (`framing | debating | deciding | decided | reviewed`),
  `advsr-stakes` (`low | medium | high | irreversible`), `advsr-operator-style`
  (how THIS operator decides: options-menu / bottom-line / pushback-then-space),
  `advsr-outcome`, `advsr-review-date`.
- `advsr-context-doc` (sub `alh-artifact`) — personal context system entries:
  role, company, ecosystem, competitive stance, priorities, past decisions and
  how they turned out. Attr: `advsr-context-kind`.
- `advsr-scenario` (sub `alh-fragment`) — stress-test. Attrs: `advsr-scenario-condition`
  ("market shifts to X", "competitor does Y", "team pushes back on Z"),
  `advsr-scenario-impact`, `advsr-scenario-likelihood`.
- Notes: `advsr-primer-note`, `advsr-interview-note`, `advsr-take-note`
  (one advisor's position; owns `advsr-stance`), `advsr-debate-note`
  (the challenge-then-converge synthesis), `advsr-bias-note` (my biases / AI's
  biases / what my position blinds me to), `advsr-journal-note` (what was
  decided, why, revisit date).
- **Relations:** `advsr-board-seat` (advisor↔operator role — use
  `nbmem-operator`/person via aboutness instead if simpler: keep
  `advsr-seat-on-board` advisor↔`advsr-board` collection), `advsr-take-by`
  (take-note↔advisor), `advsr-scenario-for` (scenario↔decision). Decisions link
  notes via `alh-aboutness`.

**CLI:** `add-advisor`, `list-advisors`, `retire-advisor`, `open-decision`
(`--primer`, `--stakes`, `--operator-style`), `add-context`, `list-context`,
`add-take` (`--advisor`), `add-debate`, `add-bias-check`, `add-scenario`,
`decide` (records outcome + journal note + review date), `review-decision`,
`list-decisions`, `show-decision`, `report-decision`, `report-board`, `audit`.

**SKILL.md workflow:** open (primer ⏸)→interview→load context docs→each advisor
writes an independent take→board debates (challenge then converge; calibrate
pushback per seat)→bias check (operator's, AI's, positional blind spots)→
⏸ operator decides (matched to their decision style)→scenario stress-tests under
multiple futures→journal + review date. Review workflow on the review date closes
the loop (what happened vs expected — feeds context docs).

**Dashboard tabs:** Decisions (board by decision-status; stakes badge) · Decision
detail (takes per advisor, debate, bias check, scenario matrix, journal) ·
Board roster (advisor cards) · Journal (decided list w/ review dates due).

---

## scribe — the communication expert

**Purpose:** writing in *your* voice for *your* audience — the widest gap between
basic and advanced use. Style profiling from your best writing + aspirational
samples; audience personas that review drafts; unlimited iteration with pointed
feedback; dimension-scored feedback instead of "I don't like it".

**Entities:**
- `scribe-voice-profile` — the living style guide. Attrs:
  `scribe-profile-status` (`draft | active | evolving`), content stored as linked
  `scribe-style-guide` artifact. One per operator, plus optional per-genre
  profiles (`scribe-genre`).
- `scribe-writing-sample` (sub `alh-artifact`) — operator's best writing or
  aspirational samples from writers they admire. Attrs: `scribe-sample-kind`
  (`own | aspirational`), `scribe-doc-type` (board-update, team-email, linkedin,
  talk, essay), `scribe-why-it-works`.
- `scribe-persona` — a detailed reader persona. Attrs: `scribe-cares-about`,
  `scribe-skeptical-of`, `scribe-action-drivers`, `scribe-reading-context`.
- `scribe-piece` — a communication in flight. Attrs: `scribe-piece-type`,
  `scribe-goal`, `scribe-piece-status`
  (`planning | drafting | persona-review | operator-review | final | shipped`),
  `scribe-audience-summary`, deadline.
- `scribe-draft` (sub `alh-artifact`) — versioned draft. Attr: `scribe-version`.
- Notes: `scribe-primer-note`, `scribe-interview-note`, `scribe-analysis-note`
  (AI's linguist analysis of samples: rhythm, sentence structure, rhetorical
  preferences), `scribe-review-note` (persona review: is it clear? would I act?
  what's missing? where would I stop reading? owns `scribe-would-act` boolean),
  `scribe-score-note` (owns `scribe-clarity-score`, `scribe-concision-score`,
  `scribe-voice-score`, `scribe-persuasion-score`, `scribe-overall-score` —
  integers 0–10 — plus concrete qualitative content).
- **Relations:** `scribe-sample-informs` (sample↔voice-profile),
  `scribe-draft-of` (draft↔piece), `scribe-piece-targets` (piece↔persona),
  `scribe-review-by` (review-note↔persona).

**CLI:** `add-sample`, `list-samples`, `create-profile`, `update-profile`,
`show-profile`, `add-analysis`, `add-persona`, `list-personas`, `create-piece`
(`--primer`), `add-draft`, `add-review` (`--persona`, `--draft`), `add-scores`
(`--draft`, per-dimension flags), `update-piece`, `list-pieces`, `show-piece`,
`report-piece`, `audit`.

**SKILL.md workflow:** profile-building (collect best samples per doc-type →
agent linguist analysis names patterns operator can't articulate → merge with
aspirational samples into style guide ⏸) · piece production (primer ⏸ →
interview → plan → draft in voice → every target persona reviews → dimension
scores vs target → iterate → ⏸ operator review; "sounds exactly like you" is the
bar, generic-pleasant-forgettable is the failure mode).

**Dashboard tabs:** Pieces (board by piece-status) · Piece detail (drafts with
score trajectory chart across versions, persona verdicts) · Voice profile
(guide + samples + analysis) · Personas.

---

## ops — the operational powerhouse

**Purpose:** the operational visibility you never had headcount for. Not
"automate what I do" but "what would I build with unlimited headcount": daily
cross-department overviews, morning P&L-style briefs, stakeholder relationship
tracker with pre-meeting context, status synthesis across channels. Personalized
meeting prep (undercurrents included). Iron rule: manual trial before automation.

**Entities:**
- `ops-brief-spec` — a designed recurring brief/report. Attrs: `ops-cadence`,
  `ops-sections`, `ops-sources` (where data comes from — connectors, channels),
  `ops-spec-status` (`designed | trial | active | retired`), `ops-trial-runs`
  (integer), `ops-trial-target` (default 7 — manual runs required before
  promotion), `ops-dream-rationale` (the unlimited-headcount wish it fulfils).
- `ops-brief` (sub `alh-note`) — one produced instance. Attrs: `ops-brief-date`,
  `ops-produced-manually` (boolean).
- `ops-dossier` — stakeholder relationship record (personal CRM; the intangibles
  no official CRM holds). Attrs: `ops-relationship`, `ops-current-state`,
  `ops-history-summary`. Linked to `alh-person` via `ops-dossier-about`.
- `ops-touchpoint` (sub `alh-note`) — interaction log. Attrs: uses
  `alh-interaction-type`/`alh-interaction-date`, plus `ops-undercurrent`
  (what the transcript won't show: mood, looks, unspoken tension),
  `ops-commitments-made`.
- `ops-meeting-prep` (sub `alh-note`) — personalized prep pack. Attrs:
  `ops-meeting-date`, `ops-meeting-title`.
- `ops-commitment` — who owes what by when. Attrs: `ops-owed-by`
  (`me | them`), `ops-due-date`, `ops-commitment-status`
  (`open | done | dropped | overdue`).
- `ops-monitor` — a standing visibility question. Attrs: `ops-question`,
  `ops-monitor-sources`, `ops-monitor-status`.
- Notes: `ops-primer-note`, `ops-interview-note`.
- **Relations:** `ops-dossier-about` (dossier↔person), `ops-touchpoint-with`
  (touchpoint↔person), `ops-prep-for` (prep↔person(s) attending — plus soft
  meeting ref), `ops-spec-produced` (spec↔brief), `ops-commitment-with`
  (commitment↔person).

**CLI:** `add-spec` (`--primer`, `--dream`), `list-specs`, `log-brief`
(`--manual/--automated`; increments trial counter; refuses `--automated` while
spec is in trial — the manual-before-automate rule is *enforced in code*),
`promote-spec` (fails if `trial-runs < trial-target`), `retire-spec`,
`add-dossier`, `show-stakeholder` (dossier + touchpoints + open commitments —
the pre-meeting context pull), `log-touchpoint`, `add-commitment`,
`update-commitment`, `list-commitments` (`--due`, `--owed-by`), `prep-meeting`
(assembles stakeholder context JSON for the agent to write the prep note),
`save-prep`, `add-monitor`, `list-monitors`, `today` (briefs due, commitments
due, meetings prepped, monitors stale), `report-today`, `audit`.

**SKILL.md workflow:** dream-first design (⏸ what would you build with unlimited
headcount?) → spec + interview → manual trial period (run it yourself daily,
consume it, refine) → promote to active only after trial target → automation via
Claude Code triggers/cron. Stakeholder flow: dossier → touchpoints with
undercurrents after every meaningful interaction → `show-stakeholder` before any
meeting → prep note. Commitments harvested from touchpoints.

**Dashboard tabs:** Today (briefs due, commitments due/overdue, upcoming meeting
preps) · Briefs (specs with trial progress bars; instances) · Stakeholders (CRM
table → detail page w/ dossier, timeline, commitments) · Commitments (board by
status) · Monitors.

---

## career — pivot of jobhunt

**What changes:** the frame widens from "job applications" to a **career graph**:
people, collaborators, projects, and potential new positions, on top of the
existing opportunity pipeline (position / engagement / venture / lead).

**Mechanics of the pivot:**
- `skills/jobhunt/` → `skills/career/`; `jobhunt.py` → `career.py`;
  `job_forager.py` → `career_forager.py`; `jhunt-` → `career-` everywhere
  (schema, python, dashboards, views, docs); dashboard `/jobhunt` → `/career`;
  plugin name `career`; `jobhunt-*` doc aliases normalized to `career-*`.
- `jhunt-job-seeker-role` → `career-agent-role` (the person's active *career
  role*, seeker being one mode of it). Keep all existing attrs.
- Legacy data: schema renames orphan old `jhunt-*` data; SKILL.md documents a
  one-shot migration (`migrate-from-jobhunt` CLI command that copies jhunt-*
  instances into career-* types when the old types exist in the DB; no-op
  otherwise).

**New model — people, collaborators, projects:**
- People are `alh-person` (shared with ops dossiers — same database, deliberate
  synergy). New CLI: `add-person`, `list-people`, `show-person` (aggregates
  contact-roles, collaborations, touchpoint notes across the graph).
- `career-project` sub `career-opportunity` — a body of work (open-source
  project, paper, product, community effort) that builds career capital. Attrs:
  `career-project-role` (lead | contributor | advisor), `career-project-status`
  (`exploring | active | paused | shipped | sunset`), `career-project-url`.
- `career-collaboration` relation — person↔(project | opportunity), owns
  `career-collab-role` (collaborator | mentor | sponsor | reference | co-author),
  `career-collab-since`, `career-collab-strength` (`weak | working | strong`).
  This is the **collaborators** representation.
- `career-relationship-note` sub `alh-note` — narrative about a person
  relationship in career context.
- New commands: `add-project`, `list-projects`, `update-project`,
  `link-collaborator` (`--person --target --role`), `list-collaborators`
  (`--person` or `--target`).

**Dashboard:** existing tabs survive under `/career`; add **People** tab
(table → person detail: collaborations, roles, notes) and **Projects** tab
(board by project-status, collaborator chips).

---

## chief-of-staff (capstone, thin)

Not a task assistant — a cross-view over decisions (advisor), communications
(scribe), research (analyst), operations (ops), and career moves (career). Ships
as `skills/chief-of-staff/` with SKILL.md + `chief_of_staff.py` offering
read-only cross-namespace queries: `daily-agenda` (ops today + advisor reviews
due + scribe pieces in review + analyst gates pending + career deadlines) and
`weekly-review`. No new schema (reads other namespaces). Dashboard: single
`/chief` hub page aggregating the other skills' summary endpoints. SKILL.md
states the earn-it-first rule: build mileage with each team member before
orchestrating them.
