---
name: chief-of-staff
description: Use when the operator asks for a cross-cutting view of everything in flight — daily agenda, weekly review, "what needs me today", or orchestration across the analyst, advisor, scribe, ops, and career skills.
triggers: daily agenda, what needs me today, weekly review, chief of staff, everything in flight, cross-skill status, orchestrate, morning rollup
read_strategy:
  agenda: "SKILL.md § Daily Agenda"
  review: "SKILL.md § Weekly Review"
  orchestration: "SKILL.md § Orchestration Patterns"
---

# Chief of Staff — The Capstone

A cross-view over your executive AI team: decisions (advisor), communications
(scribe), research (analyst), operations (ops), and career moves (career).
**Not a task assistant** — an orchestrator with a synoptic view of your
priorities across every team member.

**Earn it first.** This skill only pays off after you have real mileage with
each individual team member. If the underlying namespaces are empty, the
agenda is empty. Build the habit with `analyst`, `advisor`, `scribe`, and
`ops` individually; graduate to the chief of staff when orchestration — not
capability — is your bottleneck.

`chief_of_staff.py` is **read-only**: it defines no schema and never writes.
It reads whichever team-member namespaces exist in `alh_personal` and degrades
gracefully (`available: false`) for skills you haven't installed.

## Prerequisites

- TypeDB running with the `alh_personal` database
- At least one team-member skill installed with real data

## Daily Agenda

```bash
CLI="uv run --project skills/chief-of-staff python skills/chief-of-staff/chief_of_staff.py"

$CLI daily-agenda      # JSON for the agent
$CLI report-agenda     # Markdown for the operator
```

What it pulls, per team member:

| Section | Source | What surfaces |
|---------|--------|---------------|
| Operations | `ops-` | open/overdue commitments, upcoming meeting preps, live brief specs |
| Decisions | `advsr-` | decisions in framing/debating/deciding, journal reviews past due |
| Communications | `scribe-` | pieces in persona-review / operator-review |
| Research | `anlst-` | missions running, missions awaiting the three-question gate |
| Career | `career-` | opportunity deadlines within 14 days, active projects |

**Agent workflow:** run `daily-agenda`, then *sensemake* — don't just relay the
JSON. Rank by stakes and dates, name the one or two items that genuinely need
the operator today (⏸ OPERATOR CHECKPOINT items from the other skills), and
propose which team member to engage for each.

## Weekly Review

```bash
$CLI weekly-review     # JSON rollup
$CLI report-week       # Markdown scaffold
```

The agent narrates the week: decisions closed and how they compare with what
the journal expected, research delivered vs still gated, pieces shipped,
commitments kept and dropped, career movement. Cross-reference the advisor's
journal notes and feed durable lessons back into the advisor's context docs.

## Orchestration Patterns

The chief of staff routes work; team members do it:

- **Decision needs evidence** → open an `analyst` mission with
  `--decision-context` pointing at the `advsr-decision` id (soft ref).
- **Decision made, needs announcing** → open a `scribe` piece whose primer is
  the advisor's journal note.
- **Meeting tomorrow with a stakeholder** → `ops show-stakeholder` then
  `prep-meeting`; pull any `career` collaborations with that person for
  context.
- **Research delivered** → if it changes a decision, reopen it with the
  advisor; if it changes a relationship, log it in the ops dossier.

One graph, one database: people (`alh-person`) are shared between `career`
collaborators and `ops` stakeholder dossiers by design.

## Command Reference

| Command | Output | Purpose |
|---------|--------|---------|
| `daily-agenda` | JSON | Cross-skill items needing attention today |
| `weekly-review` | JSON | Wider rollup for the weekly narrative |
| `report-agenda` | Markdown | Operator-facing daily agenda |
| `report-week` | Markdown | Weekly review scaffold |

### Command Output Pattern

`uv run` emits a `VIRTUAL_ENV` warning to stderr. Use `2>/dev/null` when piping
output to a JSON parser — never `2>&1`.

## Common Mistakes

- **Starting here.** With empty namespaces the agenda is noise. Build mileage
  with individual team members first.
- **Relaying JSON instead of judging.** The value is ranking and routing, not
  reporting.
- **Writing through the chief.** It is read-only by design; create and update
  entities through the owning skill's CLI so its workflows and audits apply.
