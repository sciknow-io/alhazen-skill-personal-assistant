---
name: scribe
description: Use when drafting board updates, emails, LinkedIn posts, or talks in the operator's voice, building or evolving a voice profile from their best writing, audience-testing a draft against reader personas, or iterating on a piece with dimension-scored feedback
triggers:
  - draft this / write this for me / help me write
  - board update / team email / linkedin post / talk / essay
  - build my voice profile / style guide / analyze my writing
  - add a writing sample / aspirational sample
  - audience persona / would my reader act on this
  - review this draft / score this draft / iterate on this piece
read_strategy: |
  On first use: read Quick Start + Voice Profiling Workflow.
  Building a profile: read Voice Profiling Workflow.
  Defining readers: read Audience Personas.
  Writing something: read Piece Workflow + Feedback Rules.
  Full command reference and data model: read on demand.
prerequisites:
  - TypeDB running (provisioned by SessionStart hook)
  - uv available
---

# Scribe — The Communication Expert

Writing in *your* voice for *your* audience is the widest gap between basic and
advanced AI use. Scribe closes it with three assets: a **voice profile** built
from your best writing plus aspirational samples, **audience personas** that
review every draft, and **dimension-scored feedback** instead of "I don't like
it". The bar is "sounds exactly like you"; the failure mode is
generic-pleasant-forgettable.

**Key principle:** the script stores and queries; Claude does the sensemaking —
the linguist analysis, the drafting in voice, the persona role-play, and the
scoring. Follow [operating-principles.md](../../docs/operating-principles.md):
primer notes, interview-first, plan/execute split, and explicit
⏸ OPERATOR CHECKPOINT moments.

---

## 1. Quick Start

```bash
# All commands: uv run python skills/scribe/scribe.py <command> --flags
CLI="uv run python skills/scribe/scribe.py"

# Store your best writing
$CLI add-sample --name "Q3 board update" --kind own --doc-type board-update \
    --content-file q3-update.md --why-it-works "Landed a hard message without spin"

# Create the voice profile
$CLI create-profile --name "Default Voice"

# Define a reader persona
$CLI add-persona --name "Skeptical board member" \
    --cares-about "runway, focus, evidence over narrative" \
    --skeptical-of "hockey-stick projections, adjectives without numbers" \
    --action-drivers "a clear ask with a deadline" \
    --reading-context "board packet, 20 pieces to read, 90 seconds each"

# Open a piece — ALWAYS capture the primer
$CLI create-piece --name "Series B announcement email" --type team-email \
    --goal "Team feels momentum, nobody worries about dilution" \
    --primer "ok so the thing I keep coming back to is..." \
    --targets persona-abc123 persona-def456

# Draft → review → score → iterate
$CLI add-draft --piece piece-xyz --content-file draft1.md
$CLI add-review --draft draft-1a2b --persona persona-abc123 --would-act no \
    --content "Clear until para 3. I'd stop at the dilution hand-wave. Missing: the number."
$CLI add-scores --draft draft-1a2b --clarity 7 --concision 5 --voice 8 --persuasion 6 --overall 6 \
    --content "Structure is right. Paras 3-4 hedge; cut 40% and state the dilution number plainly."
```

**Command output pattern:** every command emits a single JSON object to stdout;
`report-piece` emits Markdown. `uv run` emits a `VIRTUAL_ENV` warning to stderr —
always use `2>/dev/null` when piping output to a JSON parser, never `2>&1`.

---

## 2. Voice Profiling Workflow

The goal: a living style guide that captures how the operator actually writes —
and how they *want* to write.

**⏸ OPERATOR CHECKPOINT — collect the corpus.** Ask the operator for their best
writing across doc types: board updates, team emails, LinkedIn posts, talks,
essays. "Best" means *they* are proud of it, not that it performed well. Store
each with `add-sample --kind own --doc-type ... --why-it-works ...`. Ask why
each one works — that answer is data.

**Agent-as-linguist analysis.** Read every `own` sample and write an analysis
that names the patterns the operator cannot articulate about themselves:

- **Rhythm** — sentence length variance, where they punch short, where they run long
- **Sentence structure** — fronting habits, clause stacking, fragment tolerance
- **Rhetorical preferences** — how they open, how they land an ask, humor register,
  concrete-vs-abstract ratio, favorite pivots ("but here's the thing")
- **Tells** — words and constructions that make text unmistakably theirs

Store it: `add-analysis --about <profile-or-sample-id> --content-file analysis.md`.

**Aspirational samples.** Ask which writers the operator admires and store
excerpts with `--kind aspirational`. This is not copying — it's augmentation
toward how they *want* to sound. Analyze what the admired writing does that the
operator's doesn't yet.

**Merge into the living style guide.** Synthesize own-analysis + aspirational
gaps into a style guide (concrete rules with examples, not adjectives) and save
it with `create-profile --guide-file` or `update-profile --guide-file`.

**⏸ OPERATOR CHECKPOINT — approve the guide.** Walk the operator through it.
When they say "yes, that's me / that's who I want to be", set
`update-profile --status active`. The guide is *living*: after pieces ship,
fold in what the operator edited by hand (`--status evolving` while reworking).

---

## 3. Audience Personas

Every piece is written *for someone*. Build detailed reader personas — not
demographics, but decision psychology:

- `--cares-about` — what this reader actually cares about
- `--skeptical-of` — what triggers their doubt
- `--action-drivers` — what makes them act rather than nod
- `--reading-context` — where/when/how they read (phone at 11pm; board packet
  among 20 others; LinkedIn feed at half-attention)

Interview the operator to build these — they know their readers; the personas
make that knowledge executable. Reuse personas across pieces via
`--targets` / `--add-target`.

---

## 4. Piece Workflow

Statuses: `planning → drafting → persona-review → operator-review → final → shipped`.

1. **Create (⏸ OPERATOR CHECKPOINT — primer).** `create-piece --primer "..."`.
   The primer is the operator's messy brain dump — voice-dictated is ideal.
   Never require structure; never skip it. Link `--targets` personas.

2. **Interview.** Grill the operator before writing a word: What must this
   accomplish? What does the reader already believe? What are you avoiding
   saying? What happens if this lands badly? Record with
   `add-note --type interview --about <piece-id>`.

3. **Plan.** Structure, key moves, tone, length — store with
   `add-note --type plan`. Then `update-piece --status drafting`.

4. **Draft in voice.** Load the style guide (`show-profile`) and write the
   draft *as the operator*, checking against the guide's concrete rules.
   `add-draft --piece <id>` (version auto-increments). Set status
   `persona-review`.

5. **Persona review — EVERY target persona reviews the draft.** For each
   persona, genuinely role-play them (their cares, skepticism, reading context)
   and answer four questions: **Is the message clear? Would I act? What's
   missing? Where would I stop reading?** Record each with
   `add-review --draft <id> --persona <id> --would-act yes|no`. Only
   would-act is a structured flag; write the other three answers, labeled,
   in the review's `--content`.

6. **Dimension scores against targets.** Score the draft 0-10 on clarity,
   concision, voice-match, persuasion, overall (`add-scores`). Compare to the
   piece's targets (agree targets with the operator in the plan; default: 8+
   on every dimension and every persona at `would-act yes`).

7. **Iterate.** Revise → new draft → repeat steps 5-6. Iterations are
   unlimited and feedback stays pointed — unlike human reviewers, personas
   don't fatigue, soften, or get bored on round six. Stop when scores hit
   target or plateau.

8. **⏸ OPERATOR CHECKPOINT — operator review.** Set status `operator-review`
   and present: latest draft, score trajectory across versions
   (`show-piece` / `report-piece`), and persona verdicts. The operator edits or
   approves → `final` → `shipped`. Feed their hand-edits back into the style
   guide.

---

## 5. Feedback Rules

Never "I don't like this." Models are goal-driven and need
**distance-to-target**:

- **Score dimensions 0-10** — clarity 9, wit 5, concision 7 — so the next
  iteration knows exactly which gap to close and by how much.
- **Qualitative feedback must be concrete.** Diagnose the layer: is it
  **structure** (order, missing sections), **phrasing** (rhythm, word choice,
  hedging), or **ideas** (weak argument, missing evidence)? "Para 3 hedges —
  state the number" beats "make it punchier".
- Persona reviews must answer all four questions, including the uncomfortable
  ones ("I'd stop reading at line 2").
- When the operator gives vague feedback ("something's off"), interview them
  until it becomes a dimension delta or a concrete diagnosis — then iterate.

---

## 6. Command Reference

| Command | Description | Key Args |
|---------|-------------|----------|
| `add-sample` | Store a writing sample | `--name`, `--kind own\|aspirational`, `--doc-type`, `--content/-file`, `--why-it-works`, `--profile` |
| `list-samples` | List samples | `--kind`, `--doc-type` |
| `create-profile` | Create voice profile (+ optional guide) | `--name`, `--status`, `--genre`, `--guide/-file` |
| `update-profile` | Update status/genre, overwrite guide | `--id`, `--status`, `--genre`, `--guide/-file` |
| `show-profile` | Profile + guide + samples + analyses | `--id` (default: first) |
| `add-analysis` | Store linguist analysis note | `--about`, `--content/-file` |
| `add-persona` | Create reader persona | `--name`, `--cares-about`, `--skeptical-of`, `--action-drivers`, `--reading-context` |
| `list-personas` | List personas | |
| `create-piece` | Open a piece (status `planning`) | `--name`, `--type`, `--goal`, `--audience-summary`, `--deadline`, `--primer/-file`, `--targets` |
| `add-note` | Attach primer/interview/plan/general note | `--about`, `--type`, `--content/-file` |
| `add-draft` | Store a draft, version auto-increments | `--piece`, `--content/-file` |
| `add-review` | Persona review of a draft | `--draft`, `--persona`, `--would-act yes\|no`, `--content/-file` |
| `add-scores` | Dimension scores 0-10 + qualitative | `--draft`, `--clarity`, `--concision`, `--voice`, `--persuasion`, `--overall`, `--content/-file` |
| `update-piece` | Update piece attrs, add targets | `--id`, `--status`, `--goal`, `--deadline`, `--add-target` |
| `list-pieces` | List pieces | `--status`, `--type` |
| `show-piece` | Drafts + reviews + score trajectory (JSON) | `--id` |
| `report-piece` | Piece report (Markdown) | `--id` |
| `audit` | Run quality-checks.yaml rules | |

---

## 7. Data Model

### Entities

| Type | Sub | Key attributes |
|------|-----|----------------|
| `scribe-voice-profile` | alh-domain-thing | `scribe-profile-status` (draft\|active\|evolving), `scribe-genre` |
| `scribe-style-guide` | alh-artifact | `content` (linked to profile via `alh-representation`) |
| `scribe-writing-sample` | alh-artifact | `scribe-sample-kind` (own\|aspirational), `scribe-doc-type`, `scribe-why-it-works` |
| `scribe-persona` | alh-domain-thing | `scribe-cares-about`, `scribe-skeptical-of`, `scribe-action-drivers`, `scribe-reading-context` |
| `scribe-piece` | alh-domain-thing | `scribe-piece-type`, `scribe-goal`, `scribe-piece-status`, `scribe-audience-summary`, `scribe-deadline` |
| `scribe-draft` | alh-artifact | `scribe-version` (integer, auto-increment) |

### Notes (attach via `alh-aboutness`)

| Type | Purpose |
|------|---------|
| `scribe-primer-note` | Operator's messy brain dump at piece creation |
| `scribe-interview-note` | Pre-writing interview record |
| `scribe-plan-note` | Approved plan (plan/execute split) |
| `scribe-analysis-note` | Agent-as-linguist analysis of samples |
| `scribe-review-note` | Persona review; owns `scribe-would-act` (boolean) |
| `scribe-score-note` | Owns `scribe-clarity-score`, `scribe-concision-score`, `scribe-voice-score`, `scribe-persuasion-score`, `scribe-overall-score` (0-10 integers) |

### Relations

| Relation | Roles |
|----------|-------|
| `scribe-sample-informs` | sample ↔ voice-profile |
| `scribe-draft-of` | draft ↔ piece |
| `scribe-piece-targets` | piece ↔ persona |
| `scribe-review-by` | review ↔ persona |

---

## 8. Common Mistakes

- **Generic-pleasant-forgettable prose** — text that sounds like everyone and
  no one. People can tell lazy AI writing, and it costs credibility. The
  distance between "I can tell this is AI" and "sounds exactly like you" is
  entirely steering: the voice profile, the samples, the analyses. If you
  drafted without loading `show-profile`, you made this mistake.
- **Skipping persona review.** A draft the operator likes but the reader
  bounces off is a failed draft. Every target persona reviews every draft —
  no exceptions before `operator-review`.
- **Vague feedback loops** that end in frustrated rewrites. "Make it better"
  produces random-walk revisions. Convert every reaction into dimension deltas
  (concision 5 → target 8) plus a concrete diagnosis (structure vs phrasing vs
  ideas) before redrafting.
- **Profile without samples** — a style guide invented from a conversation is
  a guess. It must be grounded in stored `own` samples and analyses (the
  `profile-without-samples` audit flags this).
- **Shipping without the loop.** Pieces marked `shipped` with no persona
  reviews defeat the whole system (the `pieces-shipped-without-persona-review`
  audit flags this).

---

## 9. Dashboard

- **Pieces** (`/scribe`) — board by `scribe-piece-status`
- **Voice Profile** (`/scribe`, tab) — style guide + samples + analyses
- **Personas** (`/scribe`, tab) — persona cards
- **Piece detail** (`/scribe/piece/{id}`) — drafts, score trajectory across
  versions, persona verdicts

Internal organization: `dashboard/views/*.yaml` (declarative specs),
`dashboard/lib.ts` (gateway-first CLI wrapper, `SCRIBE_SKILL_ROOT` env),
`dashboard/components/*.tsx`, `dashboard/routes/**/route.ts`,
`dashboard/pages/scribe/`.
