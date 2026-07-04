---
name: analyst
description: Use when researching a question that serves a decision, running market/competitive/internal research, verifying AI-generated research, or aggregating multi-model consensus on contested claims
triggers:
  - research this / look into / find out about (with a decision at stake)
  - market research / competitive analysis / landscape scan
  - start a research mission / brief the analyst
  - verify these findings / fact-check this research
  - consensus across models / wisdom of the crowd
  - three-question gate / is this research trustworthy
read_strategy: |
  On first use: read Quick Start + The Workflow.
  When briefing/interviewing: read Workflow steps 1-3.
  When fanning out runs: read Workflow steps 4-5 (parallel runs, findings).
  When aggregating/verifying: read Workflow steps 6-7 (consensus, fresh-thread verification).
  When delivering: read Workflow steps 8-9 (gate, deliverable formats).
  Full command reference / data model: read those sections on demand.
---

# Analyst — the research analyst you always wanted

Use this skill to run research the way an executive briefs an analyst, not the way
people query a search engine. Every mission is framed by a **decision**, constrained
by time horizon / source policy / exclusions, executed as **3+ parallel research
runs** ("wisdom of the crowd"), aggregated into consensus, **verified in a fresh
thread**, and passed through the **three-question gate** before anything is
delivered.

**Key principle:** the script stores and queries; Claude does the sensemaking
(interviewing, researching, matching claims across runs, verifying, synthesizing).

This skill operationalizes the repo's [operating principles](../../docs/operating-principles.md):
primer notes (speak, don't type), interview-first, plan/execute split, explicit
⏸ OPERATOR CHECKPOINT moments, wisdom-of-the-crowd, and the three-question gate.

---

## Quick Start

### Prerequisites

- TypeDB running with the `alh_personal` database (provisioned by this skill's
  SessionStart hook when installed as a plugin)
- `uv` available; run commands from the skill directory or with `--project`

### Environment Variables

- `TYPEDB_HOST`: TypeDB server (default: localhost)
- `TYPEDB_PORT`: TypeDB port (default: 1729)
- `TYPEDB_DATABASE`: Database name (default: alh_personal)

### Essential Commands

```bash
# Open a mission (always capture the operator's messy primer)
uv run python skills/analyst/analyst.py create-mission \
    --name "EU battery market entry" \
    --decision-context "Whether to open an EU manufacturing line in 2027" \
    --time-horizon "2026-2029" --priority high \
    --primer "Voice-dictated brain dump, unedited..."

# Fan out parallel runs
uv run python skills/analyst/analyst.py add-run --mission mission-abc123 --model "claude-opus"

# Record a discrete claim from a run
uv run python skills/analyst/analyst.py add-finding --run run-def456 \
    --claim "EU battery demand grows ~30% CAGR through 2028" --confidence high

# Aggregate consensus for one claim group (agent matches the claims)
uv run python skills/analyst/analyst.py record-consensus \
    --findings finding-a1 finding-b2 finding-c3 --agree 3

# See what needs attention
uv run python skills/analyst/analyst.py list-findings --divergent
uv run python skills/analyst/analyst.py report-mission --id mission-abc123
```

### Command Output Pattern

`uv run` emits a `VIRTUAL_ENV` warning to stderr. Always use `2>/dev/null` when
piping output to a JSON parser -- never `2>&1`, which merges the warning into
stdout and breaks JSON parsing.

---

## The Workflow

Everything between checkpoints is agent work. The operator steps in only at the
⏸ OPERATOR CHECKPOINT moments.

### 1. Brief — capture the primer  ⏸ OPERATOR CHECKPOINT

Ask the operator for their messy, unstructured brain dump (voice dictation is
ideal): what decision is at stake, what they already believe, hunches, constraints,
politics, prior attempts. Do NOT ask them to structure it — you structure it.

```bash
analyst.py create-mission --name "..." --decision-context "..." --primer "<verbatim dump>"
```

A mission without `--decision-context` triggers a warning: research without a
decision in mind is a search-engine query, not an analyst brief.

### 2. Interview — surface unknown-unknowns  ⏸ OPERATOR CHECKPOINT

Before planning, interview the operator like a senior analyst taking a brief:

- What decision will this research change, and when is it made?
- Time horizon? Which sources count (and which are banned)? What is out of scope?
- What assumptions are you already making? What would change your mind?
- What haven't you considered? What context should you give me that I can't find?

Record the full Q&A: `analyst.py add-interview --mission <id> --content-file qa.md`,
then `analyst.py update-mission --id <id> --status planning`.

### 3. Plan — separate planning from execution  ⏸ OPERATOR CHECKPOINT (approve plan)

Draft the research plan: questions to answer, source strategy, how many parallel
runs (minimum 3), what a "finding" looks like, success criteria. Present it to the
operator; iterate until approved. Only then execute.

```bash
analyst.py add-plan --mission <id> --content-file plan.md
analyst.py update-mission --id <id> --status running
```

### 4. Fan out 3+ parallel research runs (wisdom of the crowd)

Never trust one model/thread. Register at least three runs and execute them
**independently with the SAME research prompt** (built from the brief + plan):

- Use your subagent/Task tooling to dispatch parallel research agents, or separate
  sessions if subagents are unavailable.
- Use different models or at least different instances/sessions when available
  (e.g. `--model claude-opus`, `--model gpt-5`, `--model claude-opus-session-2`).
- Do not share intermediate results between runs — independence is the point.

```bash
analyst.py add-run --mission <id> --model "claude-opus"
analyst.py add-run --mission <id> --model "gpt-5"
analyst.py add-run --mission <id> --model "gemini"
```

### 5. Record findings per run

As each run completes, decompose its output into **discrete claims** — one
`add-finding` per claim, with sources:

```bash
analyst.py add-finding --run <run-id> --claim "..." --confidence high --content "supporting detail"
analyst.py link-source --finding <finding-id> --url "https://..." --kind academic --reliability high
analyst.py complete-run --run <run-id>
```

Then `analyst.py update-mission --id <id> --status aggregating`.

### 6. Consensus aggregation

You (the agent) match claims across runs semantically — the script just stores your
groupings. For each claim group, call `record-consensus` with all the finding ids
that assert the same claim and how many runs agree:

```bash
analyst.py record-consensus --findings f-a1 f-b2 f-c3 --agree 3   # all runs agree
analyst.py record-consensus --findings f-a9 --agree 1              # single-thread claim
```

Interpretation:

- **100% consensus ≈ likely factual** — still verify the load-bearing ones.
- **Single-thread claims are marked divergent** — investigate or re-research them
  (a targeted follow-up run) before they appear in any deliverable.

Write the cross-run synthesis as a synthesis note (`--type` is implicit in the
command): store it via a deliverable draft or attach with the notebook's note
tooling; the consensus narrative belongs in the mission record. Then
`update-mission --status verifying`.

### 7. Verification — in a FRESH thread

AI verifies better than it generates, but **never in the thread that generated the
claims** (it will defend its own work). Open a fresh session/subagent with no
generation context, hand it only the claims + sources, and ask it to confirm,
refute, or flag each:

```bash
analyst.py list-findings --mission <id> --unverified   # the verification worklist
analyst.py verify-finding --finding <id> --status confirmed --content "checked against primary source X"
analyst.py verify-finding --finding <id> --status refuted --content "source does not say this"
```

Refuted findings never reach the deliverable. `needs-work` findings go back to
step 6 (re-research).

### 8. Three-question gate  ⏸ OPERATOR CHECKPOINT

Before acting on or delivering ANY research, the operator answers the gate:

1. Is this grounded in real sources, or is it pattern-matching?
2. What's missing that I didn't think to ask?
3. Would I put my name on this?

```bash
analyst.py record-gate --mission <id> \
    --grounded "All load-bearing claims verified against primary sources" \
    --missing "No pricing data from APAC competitors - flagged as open question" \
    --name-on-it "Yes, with the APAC caveat stated" \
    --passed
```

A passing gate moves the mission to `gated`. A failing gate (`--failed`) leaves
status unchanged — go back to the step the answers point at.

### 9. Deliverable  ⏸ OPERATOR CHECKPOINT (choose format)

Don't default to a wall of text. Ask what would actually get used:

| Format | When |
|--------|------|
| `brief` | Operator wants a tight written summary |
| `dashboard` | Ongoing decision — numbers that update |
| `infographic` | Sharing with others; one-glance story |
| `interactive-page` | Exploration — let the operator drill in |
| `audio-summary` | Operator consumes on the move |

```bash
analyst.py add-deliverable --mission <id> --name "EU entry brief" --format infographic --uri "path/or/url"
analyst.py update-mission --id <id> --status delivered
```

---

## Command Reference

All commands: `uv run python skills/analyst/analyst.py <command> --flags`.
JSON to stdout (except `report-mission`, which prints Markdown).

| Command | Purpose | Key flags |
|---------|---------|-----------|
| `create-mission` | Open a research mission | `--name` (req), `--decision-context`, `--primer`, `--time-horizon`, `--source-policy`, `--exclusions`, `--priority`, `--deadline`, `--decision-ref` |
| `add-interview` | Store operator interview note | `--mission` (req), `--content`/`--content-file` |
| `add-plan` | Store approved plan note | `--mission` (req), `--content`/`--content-file` |
| `update-mission` | Update status/framing | `--id` (req), `--status`, `--priority`, `--decision-context`, `--time-horizon`, `--source-policy`, `--exclusions`, `--deadline`, `--decision-ref` |
| `list-missions` | List missions + rollups | `--status` |
| `show-mission` | Full detail (runs, findings, gate, deliverables) | `--id` (req) |
| `add-run` | Register a research thread | `--mission` (req), `--model` (req) |
| `complete-run` | Finish a run | `--run` (req), `--status completed\|failed` |
| `add-finding` | One discrete claim from a run | `--run` (req), `--claim` (req), `--confidence`, `--content` |
| `link-source` | Evidence for a finding | `--finding` (req), `--url`/`--source`, `--name`, `--kind`, `--reliability` |
| `list-findings` | Query findings | `--mission`, `--divergent`, `--unverified` |
| `record-consensus` | Store one claim group | `--findings id...` (req), `--agree N`, `--divergent`/`--not-divergent` |
| `verify-finding` | Fresh-thread verification | `--finding` (req), `--status confirmed\|refuted\|needs-work` (req), `--content` |
| `record-gate` | Three answers + pass/fail | `--mission` (req), `--grounded`, `--missing`, `--name-on-it` (all req), `--passed`/`--failed` (req) |
| `add-deliverable` | Attach output | `--mission` (req), `--name` (req), `--format` (req), `--content`/`--content-file`, `--uri` |
| `report-mission` | Markdown mission report | `--id` (req) |
| `audit` | Run quality-checks.yaml | `--severity` |

---

## Data Model

Namespace `anlst-`, subtypes of the `alh-*` core types. IDs are `<type>-<hash12>`.
Notes attach to subjects via `alh-aboutness`.

### Entities

| Type | Sub | Key attributes |
|------|-----|----------------|
| `anlst-mission` | `alh-domain-thing` | `anlst-decision-context`, `anlst-time-horizon`, `anlst-source-policy`, `anlst-exclusions`, `anlst-mission-status`, `anlst-priority-level`, `anlst-deadline`, `anlst-decision-ref` (soft ref to an advisor decision) |
| `anlst-run` | `alh-domain-thing` | `anlst-model-name`, `anlst-run-status`, `anlst-started-at`, `anlst-completed-at` |
| `anlst-finding` | `alh-fragment` | `anlst-claim`, `anlst-confidence-level`, `anlst-consensus-count`, `anlst-divergent`, `anlst-verification-status` |
| `anlst-source` | `alh-artifact` | `anlst-source-url`, `anlst-source-kind`, `anlst-reliability` |
| `anlst-deliverable` | `alh-artifact` | `anlst-deliverable-format` |

### Notes (all sub `alh-note`, attached via `alh-aboutness`)

| Type | Holds |
|------|-------|
| `anlst-primer-note` | Operator's messy initial brain dump |
| `anlst-interview-note` | The agent-interviews-operator Q&A |
| `anlst-plan-note` | The approved research plan |
| `anlst-verification-note` | Fresh-thread verification rationale (about a finding) |
| `anlst-gate-note` | `anlst-gate-grounded`, `anlst-gate-missing`, `anlst-gate-name-on-it`, `anlst-gate-passed` |
| `anlst-synthesis-note` | Cross-run consensus narrative |

### Relations

| Relation | Roles |
|----------|-------|
| `anlst-mission-run` | mission, run |
| `anlst-run-yielded` | run, finding |
| `anlst-finding-source` | finding, source |
| `anlst-mission-deliverable` | mission, deliverable |

### Status values

- Mission: `briefing → planning → running → aggregating → verifying → gated → delivered`
- Run: `running | completed | failed`
- Verification: `unverified | confirmed | refuted | needs-work`
- Deliverable format: `brief | dashboard | infographic | interactive-page | audio-summary`

---

## Quality checklist

Before calling a mission done, confirm (or just run `analyst.py audit`):

- [ ] Mission has a decision-context (research serves a decision)
- [ ] Primer, interview, and plan notes exist (checkpoints were real, not skipped)
- [ ] 3+ runs, same prompt, independent execution
- [ ] Every load-bearing finding has at least one linked source
- [ ] Consensus recorded for every claim group; divergent claims investigated or re-researched
- [ ] Verification done in a fresh thread; no refuted claims in the deliverable
- [ ] Gate recorded with three real answers, and it passed
- [ ] Deliverable format chosen deliberately (not a default wall of text)

---

## Common Mistakes

1. **Asking like a search engine instead of briefing an analyst.** "What's the EU
   battery market like?" is a query. A brief has a decision, a time horizon, a
   source policy, and exclusions. If the operator gives you a query, interview
   them until it becomes a brief.
2. **Trusting one thread.** A single run's output is one sample, not an answer.
   Always fan out 3+ independent runs and aggregate. A confident single-thread
   claim is exactly the thing most likely to be confabulated.
3. **Verifying in the same thread that generated.** The generating thread will
   rationalize its own claims. Verification gets a fresh session with no
   generation context — claims and sources only.
4. **Skipping the gate.** "Looks good" is not a gate. The three questions are
   answered explicitly and stored (`record-gate`); `delivered` without a gate note
   is an audit violation.
