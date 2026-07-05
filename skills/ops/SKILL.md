---
name: ops
description: Use when the operator wants a morning brief, meeting prep, stakeholder context before a meeting, commitment tracking, a new recurring report/monitor designed, or status synthesis across channels — the operational powerhouse you never had headcount for.
triggers: morning brief, daily brief, meeting prep, prep me for, who is, stakeholder, before my meeting with, commitments, who owes what, follow-ups, recurring report, monitor, status synthesis, what's on today
read_strategy:
  briefs: "SKILL.md § Brief lifecycle"
  crm: "SKILL.md § Stakeholder CRM"
  prep: "SKILL.md § Meeting prep workflow"
  commitments: "SKILL.md § Commitments"
  reference: "SKILL.md § Command Reference"
---

# Ops — The Operational Powerhouse

Not "automate what I already do" but **"what would I build with unlimited headcount?"**
Recurring briefs with a manual-before-automate iron rule, a personal stakeholder CRM
that holds the intangibles no official CRM will, personalized meeting prep, commitment
tracking in both directions, and standing monitors.

Script stores/queries (`ops.py`, JSON to stdout); Claude does the sensemaking.
All data lives in the shared `alh_personal` TypeDB database — people (`alh-person`)
are shared with the career skill deliberately.

## Quick Start

```bash
CLI="uv run --project skills/ops python skills/ops/ops.py"

# Morning ritual
$CLI report-today                       # Markdown morning brief
$CLI today                              # same data as JSON

# Design a brief (dream-first, primer captured)
$CLI add-spec --name "Morning cross-project overview" \
  --cadence daily --sections "wins,risks,decisions-needed,numbers" \
  --sources "slack:#eng,#sales; linear; stripe dashboard" \
  --dream "A chief of staff who reads 10 channels before I wake up" \
  --primer "<operator's messy voice-dictated brain dump>"

# Run it manually during the trial
$CLI log-brief --spec <spec-id> --manual --content-file brief.md

# Stakeholder flow
$CLI add-person --name "Dana Kim"
$CLI add-dossier --person "Dana Kim" --relationship "board member" \
  --current-state "supportive but pressing on burn rate"
$CLI log-touchpoint --person "Dana Kim" --type meeting \
  --content "Q2 review, pushed on hiring plan" \
  --undercurrent "Tense when CFO spoke; checked phone during roadmap — losing patience?"
$CLI show-stakeholder --person "Dana Kim"   # the pre-meeting context pull
```

## Dream-first design

⏸ **OPERATOR CHECKPOINT** — before designing anything, ask the operator:
**"What would you build with unlimited headcount?"** Not "what can I automate?"
Examples of the right altitude:

- A daily cross-department overview nobody currently compiles.
- A morning P&L-style analysis in your inbox before coffee.
- A stakeholder relationship tracker that briefs you before every meeting.
- Status synthesis across 10 Slack channels you never manage to read.

Don't just automate what you already do — build what you never could. Record the
answer in the spec's `--dream` (ops-dream-rationale) so every brief remembers the
wish it fulfils. Always capture the operator's messy brain dump with `--primer`
(voice-dictated is ideal; the agent structures it, never the operator), then
interview the operator (`add-note --type interview --about <spec-id>`): who consumes
this? at what moment of the day? what decision does each section serve? what sources
exist? what's missing?

## Brief lifecycle — THE IRON RULE

**Never automate a brief before running it manually for one to two weeks and
consuming the output.** The lifecycle is `designed → trial → active → retired`,
and the CLI enforces it: **`log-brief --automated` is rejected while the spec is
in `designed` or `trial` status** — you will get an error explaining the rule.

1. **Design** — `add-spec` with `--primer` and `--dream`; interview the operator;
   spec starts as `designed` with `trial-runs 0` and `trial-target 7` (override
   with `--trial-target` for a two-week trial: 10–14). The target counts
   **manual runs logged**, not calendar days.
2. **TRIAL** — every day (or per cadence), the agent + operator produce the brief
   *manually*: agent gathers from the spec's sources, writes the brief, operator
   reads it, then `log-brief --spec <id> --manual --content-file brief.md`. The
   first manual run flips the spec to `trial`; each manual run increments
   `trial-runs`. ⏸ **OPERATOR CHECKPOINT** after each run: did you actually read
   it? Which sections earned their place? Refine `--sections`/`--sources` as you
   learn (edit via a new spec or note the changes in an interview note).
3. **Promote** — `promote-spec` succeeds only when `trial-runs >= trial-target`.
   ⏸ **OPERATOR CHECKPOINT**: only promote if the brief proved its worth. If you
   stopped reading it during the trial, `retire-spec` instead — that is a success
   of the process, not a failure.
4. **Automate** — only now wire up automation via Claude Code triggers/cron/
   scheduled sessions. Concrete example — a scheduled session (cron trigger,
   weekdays 6:30am) whose prompt is:

   > Run `uv run --project skills/ops python skills/ops/ops.py report-today`,
   > then produce the "Morning cross-project overview" brief per its spec
   > (sections/sources from `list-specs`), and store it with
   > `log-brief --spec <id> --automated --content-file brief.md`.

   Or a SessionStart hook that runs `report-today` so every morning session opens
   with the ops snapshot. Automated instances are logged with `--automated`
   (`ops-produced-manually false`) so the audit can prove the rule held.

## Stakeholder CRM

One `ops-dossier` per person who matters: relationship, current state, history
summary. The dossier holds what the official CRM never will.

**Log a touchpoint after every meaningful interaction** — and always capture the
**undercurrent**: what the transcript won't show. Mood. Hesitation. The look on
someone's face when the budget came up. What was conspicuously *not* said. This is
brain-dump territory (operating principle #2): capture even when there's no
immediate use, reduce friction to near zero, speak-don't-type. The undercurrents
are precisely what make future meeting prep non-generic.

```bash
$CLI log-touchpoint --person <id|name> --type call \
  --content "..." \
  --undercurrent "Sounded flat; usually jokes. Something's up with her team." \
  --commitments-made "I promised intro to Sam by Friday; she'll send the deck"
```

If `--commitments-made` is set, harvest each promise into a tracked commitment
(see below) — the CLI reminds you.

## Meeting prep workflow

1. `show-stakeholder --person <X>` — the pre-meeting context pull (dossier +
   touchpoints + open commitments + last prep). Use for a quick glance. If the
   person isn't in the graph yet, run `add-person` (and `add-dossier`) first.
2. `prep-meeting --person <X> [<Y> ...] --title "..." --date YYYY-MM-DD` —
   assembles full context JSON for every attendee.
3. **Agent writes the personalized prep pack**: relationship state, undercurrents
   from recent touchpoints, open commitments in both directions ("you owe Dana
   the intro to Sam — it's overdue"), suggested talking points, landmines to
   avoid. Not a transcript summary — a *briefing*.
4. `save-prep --person <X> --title "..." --date ... --content-file prep.md`
5. ⏸ **OPERATOR CHECKPOINT** — the operator reviews the prep before the meeting
   and corrects anything the record got wrong (corrections become a touchpoint or
   dossier update).

## Commitments

Who owes what by when, in both directions (`--owed-by me|them`). Harvest them
from touchpoints (`--from-touchpoint <id>` records provenance). Statuses:
`open | done | dropped | overdue`. `today`/`report-today` surface overdue and
due-soon commitments every morning; `list-commitments --owed-by me --due
<friday>` answers "what do I owe people this week?". Nothing silently drops.

## Monitors

Standing visibility questions ("Are any key customers going quiet?", "Is team
sentiment in #eng drifting?") with sources to check. `update-monitor --checked`
stamps the check; monitors unchecked for 7+ days show up as **stale** in `today`.
Monitors follow the same manual-first spirit: answer the question by hand a few
times before considering any automation.

## OKRs — the primary planning element

Work is planned and executed **through objectives**. An `ops-objective` is a
primary data element (like a brief spec or a dossier), not a sub-item of another
skill. Everything else descends from it:

```
ops-objective            the goal (period, status)           ← PRIMARY
  └─ ops-key-result      measurable outcome (metric, target-date, current)
       └─ ops-workitem   execution: kind = story → task → subtask (nests to any depth)
            └─ ops-commitment   the dated, person-owed leaf (bridged, shows in the daily agenda)
```

Build a tree top-down: `add-objective` → `add-kr --objective` →
`add-workitem --kr` (root) or `add-workitem --parent` (nested). Assign an
`--owner` (an `alh-person`, shared with career) at any level. Bridge a leaf to a
real commitment with `link-commitment` so "who owes what by when" surfaces in
`chief-of-staff`. `show-tree --objective` renders the tree with rolled-up
progress (done leaves / total).

**External data comes in as artifacts, never notes.** Emails, calendar meetings,
and documents are captured with `add-email` / `add-event` / (docs) and linked to
the plan as *evidence* (`--evidence-for <id>` or `link-evidence`), and to people
(`--party` / `--attendee`). The agent's *thinking* about them stays in notes
(`ops-meeting-prep`, `ops-touchpoint`); the raw external thing is the artifact.

Objectives are standalone; use `--serves <subject-id>` to optionally tie one to a
`career-project` or an advisor decision.

## Tracker integration — pull-first (Jira / Monday / GitHub)

The team manages the work in their own tracker; **alhazen imports leaf items** so
your personal OKR view stays honest without double-entry. alhazen is the *why*
(objectives, KRs, decision context, evidence); the tracker is the *execution*.

The CLI only stores/queries the reference + mapped status — **the agent fetches
the live item through the provider's MCP server** (GitHub Projects MCP, Atlassian
Rovo MCP, or the monday Platform MCP) and calls these commands to persist it:

- `import-item --provider github --url <issue-url> --title … --external-id … --external-status "In Progress" --kr <id>`
  → creates a work item **from** a tracker issue, mapping its status.
- `link-tracker --workitem <id> --provider … --url … [--external-status …]`
  → attach an existing work item to a tracker item.
- `sync-status --workitem <id> --external-status "Done"` → a refresh pull; re-maps
  status and stamps `ops-last-synced` (provider inferred from the stored link).
- `list-tracker-links [--provider …]` → downstream check: what's linked, the raw
  tracker status, and how fresh the sync is.

**Status mapping** (raw → `ops-workitem-status`; unknown → in-progress):

| Provider | not-started | in-progress | blocked | done |
|---|---|---|---|---|
| github | Todo / Backlog / (open→in-progress) | In Progress / In Review | Blocked | Done / closed |
| jira | To Do / Backlog / New | In Progress / In Review | Blocked | Done |
| monday | Not Started / (blank) | Working on it | Stuck | Done |

**Typical loop:** manage OKR execution in the team tool → periodically ask the
agent to *pull*: it lists the relevant issues via the tracker MCP, `import-item`s
new ones under the right KR and `sync-status`es the rest → `show-tree` and
`chief-of-staff` now reflect real execution. Objectives and KRs stay in
alhazen (your private framing); only leaf work items carry a tracker link.

Imported items keep a `↗ provider` deep-link in the dashboard with a "synced Nd
ago" freshness badge.

## Command Reference

| Command | Purpose | Key flags |
|---|---|---|
| `add-spec` | Design a recurring brief | `--name --cadence --sections --sources --dream --primer --trial-target` |
| `list-specs` | Specs + trial progress | `--status` |
| `log-brief` | Log a produced brief | `--spec --manual/--automated --content/--content-file --date` |
| `list-briefs` | Produced instances | `--spec --limit` |
| `promote-spec` | trial → active (enforced) | `--spec` |
| `retire-spec` | Kill briefs nobody reads | `--spec` |
| `add-person` | Find-or-create alh-person | `--name --email` |
| `add-dossier` | Stakeholder dossier | `--person --relationship --current-state --history --primer` |
| `list-stakeholders` | CRM table | |
| `show-stakeholder` | Pre-meeting context pull | `--person` |
| `log-touchpoint` | Interaction + undercurrent | `--person --type --date --undercurrent --commitments-made` |
| `prep-meeting` | Context JSON for prep | `--person (multi) --title --date` |
| `save-prep` | Store prep pack | `--person (multi) --title --date --content-file` |
| `add-commitment` | Who owes what by when | `--person --what --owed-by --due --from-touchpoint` |
| `update-commitment` | Change status/due | `--id --status --due` |
| `list-commitments` | Filterable list | `--due --owed-by --status --person` |
| `add-monitor` | Standing question | `--question --sources --name` |
| `list-monitors` | List monitors | `--status` |
| `update-monitor` | Status / mark checked | `--id --status --checked` |
| `today` | Morning snapshot (JSON) | |
| `report-today` | Morning brief (Markdown) | |
| `add-note` | Primer/interview/general note | `--about --type --content` |
| `audit` | Quality checks | |
| `add-objective` | Create an objective (primary) | `--name --period --status --owner --serves --primer` |
| `add-kr` | Key result under an objective | `--objective --name --metric --baseline --current --status --target-date --owner` |
| `add-workitem` | story/task/subtask | `--kind --name --kr\|--parent --owner --target-date --order --status` |
| `update-objective` | Update objective | `--id --status --period --name` |
| `update-kr` | Update key result | `--id --current --status --target-date` |
| `update-workitem` | Update work item | `--id --status --name --target-date` |
| `link-commitment` | Bridge a leaf to a commitment | `--workitem --commitment` |
| `show-tree` | Objective → KRs → work items + progress | `--objective` |
| `list-objectives` | List objectives | `--status --serves` |
| `add-email` | Capture an email (artifact) | `--subject --sent-at --content/-file --uri --party --evidence-for` |
| `add-event` | Capture a calendar meeting (artifact) | `--title --start --end --content/-file --uri --attendee --evidence-for` |
| `link-evidence` | Link an artifact to a plan element | `--artifact --subject` |
| `import-item` | Create a work item FROM a tracker item | `--provider --url --title --external-id --external-status --kind --kr\|--parent` |
| `link-tracker` | Link an existing work item to a tracker item | `--workitem --provider --url --external-id --external-status` |
| `sync-status` | Pull a linked item's status from the tracker | `--workitem --external-status [--provider]` |
| `list-tracker-links` | Linked items + freshness (downstream check) | `--provider` |

## Data Model

Entities (sub `alh-domain-thing`):

| Type | Key attributes |
|---|---|
| `ops-brief-spec` | ops-cadence, ops-sections, ops-sources, ops-spec-status (designed/trial/active/retired), ops-trial-runs, ops-trial-target (default 7), ops-dream-rationale |
| `ops-dossier` | ops-relationship, ops-current-state, ops-history-summary |
| `ops-commitment` | ops-owed-by (me/them), ops-due-date, ops-commitment-status (open/done/dropped/overdue) |
| `ops-monitor` | ops-question, ops-monitor-sources, ops-monitor-status, ops-last-checked |
| `ops-objective` | **PRIMARY.** ops-objective-period, ops-objective-status (draft/active/at-risk/met/missed/dropped) |
| `ops-key-result` | ops-kr-metric, ops-kr-baseline, ops-kr-current, ops-kr-status (on-track/at-risk/off-track/met/missed), ops-target-date |
| `ops-workitem` | ops-workitem-kind (story/task/subtask), ops-workitem-status (not-started/in-progress/blocked/done/dropped), ops-target-date, ops-order; tracker link: ops-external-provider (github/jira/monday), ops-external-id, ops-external-uri, ops-external-status, ops-last-synced |

Artifacts (sub `alh-artifact`, raw external data):

| Type | Key attributes |
|---|---|
| `ops-email` | ops-sent-at, ops-external-uri (+ inherited content) |
| `ops-calendar-event` | ops-event-start, ops-event-end, ops-meeting-title, ops-external-uri |
| `ops-external-doc` | ops-external-uri |

Notes (sub `alh-note`):

| Type | Key attributes |
|---|---|
| `ops-brief` | ops-brief-date, ops-produced-manually |
| `ops-touchpoint` | alh-interaction-type, alh-interaction-date, ops-undercurrent, ops-commitments-made |
| `ops-meeting-prep` | ops-meeting-date, ops-meeting-title |
| `ops-primer-note`, `ops-interview-note` | (content only; linked via alh-aboutness) |

Relations:

| Relation | Roles |
|---|---|
| `ops-dossier-about` | dossier ↔ person (alh-person) |
| `ops-touchpoint-with` | touchpoint ↔ person |
| `ops-prep-for` | prep ↔ person(s) |
| `ops-spec-produced` | spec ↔ brief |
| `ops-commitment-with` | commitment ↔ person |
| `ops-objective-kr` | objective ↔ key-result |
| `ops-kr-work` | key-result ↔ workitem (tree root) |
| `ops-workitem-tree` | parent ↔ child (recursive breakdown) |
| `ops-workitem-commitment` | workitem ↔ commitment (bridge to the dated leaf) |
| `ops-owned` | objective/KR/workitem ↔ owner (alh-person) |
| `ops-objective-serves` | objective ↔ subject (optional soft link, e.g. a career-project) |
| `ops-evidence` | artifact ↔ subject (email/meeting/doc → a plan element) |
| `ops-email-party` / `ops-event-attendee` | artifact ↔ person |

IDs are `<type>-<hash12>`. Notes attach to entities via `alh-aboutness`
(`add-note --about <id>`).

## Common Mistakes

- **Automating before the manual trial.** The whole point of the trial is that
  you *consume* the output daily and refine it. The CLI refuses
  `log-brief --automated` during designed/trial — don't work around it by lying
  with `--manual` on an automated run.
- **Generic meeting prep = summarize-the-last-transcript.** If the prep pack
  reads like meeting minutes, it failed. The dossier's current-state, the
  undercurrents, and open commitments are what make it a briefing.
- **Losing the intangibles.** Skipping `--undercurrent` because "the notes cover
  it" — the notes never cover it. Mood, hesitation, the look on someone's face:
  capture within hours or lose it forever.
- **Briefs nobody reads.** A brief that stopped earning its read is operational
  debt. Watch for it in the trial (don't promote) and after (retire-spec). The
  dream-rationale tells you what it was supposed to do; if it doesn't, kill it.
- **Commitments left in touchpoints.** `--commitments-made` text is raw capture,
  not tracking. Harvest each promise into `add-commitment` or it will never
  surface in `today`.
