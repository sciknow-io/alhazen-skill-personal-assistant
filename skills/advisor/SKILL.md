---
name: advisor
description: Use when facing a strategic or sensitive decision you can't yet take to the board or the team, when you need a no-ego sounding board, when you want a board-of-advisors debate on a question, when preparing for a real board conversation, or when keeping a decision journal and reviewing past calls.
triggers:
  - I need to think through a decision / help me decide
  - convene the board / ask my advisors / board of advisors
  - open a decision / decision journal
  - stress-test this decision / what could go wrong
  - bias check / what am I not seeing
  - review my decision / what's due for review
  - add an advisor / build my board
  - update my context / who I am / my priorities
read_strategy: |
  On first use: read Quick Start + Building Your Board.
  Before any decision work: read Personal Context System + Decision Workflow.
  On a review date: read Review Workflow.
  Full command list: read Command Reference on demand.
  Data model details: read Data Model tables on demand.
prerequisites:
  - TypeDB running with the alh_personal database (SessionStart hook provisions it)
  - uv run --project <skill-dir> python advisor.py <command>
---

# Advisor — Strategic Thought Partner / Board of Advisors

The 24/7 no-ego sounding board for the loneliness at the top: decisions you can't
yet take to the board or the team. A persona-based board of advisors debates the
question, then **converges**. Calibrated pushback — never sycophancy, never
devil's-advocate-for-sport. Bias surfacing, scenario stress-tests, and a decision
journal that closes the loop.

**Key principle:** the script stores and queries; Claude does the sensemaking —
writing each advisor's take in that seat's voice, running the debate, surfacing
biases, and drafting scenarios. The operator makes the call.

This skill obeys the repo's [operating principles](../../docs/operating-principles.md):
primer brain dumps at every open, interview-first, planning separated from
execution (the framing→debating→deciding states), and explicit
⏸ OPERATOR CHECKPOINT moments — everything between checkpoints is agent work.

---

## 1. Quick Start

```bash
# All commands: uv run --project skills/advisor python skills/advisor/advisor.py <command>

# Seat your first advisor
advisor.py add-advisor --name "The Operator" --archetype operator \
    --decision-style "execution-first" --pushback firm \
    --inspiration "Maria, my first COO" \
    --charter "Can we actually execute this with the team and cash we have?"

# Store personal context (do this once, keep it fresh)
advisor.py add-context --name "My role & mandate" --kind role \
    --content-file ~/context/role.md

# Open a decision with the primer brain dump
advisor.py open-decision \
    --question "Do we enter the EU market next quarter?" \
    --stakes high --operator-style pushback-then-space \
    --primer "Unfiltered thinking, exactly as spoken..."

# ... interview, takes, debate, bias check (see Decision Workflow) ...

# Record the call
advisor.py decide --decision decision-abc123 \
    --outcome "Enter EU, UK-first, 1 hire not 4" \
    --journal "What we decided, why, what we expect..." \
    --review-date 2026-10-01

# What's due for review?
advisor.py list-decisions --review-due
```

All commands emit a single JSON object on stdout; `report-decision` and
`report-board` emit Markdown for human display.

---

## 2. Building Your Board

A seat on the board is a **persona**, not a chatbot flavor. Build seats from:

- **Mentors you had** — the boss whose questions you still hear years later.
- **Mentors you wished for** — the seat you never had access to (a CFO who's
  seen three downturns, a founder who's sold a company).
- **Real thought-leaders as inspiration** — record who the seat channels in
  `--inspiration` ("thinks like Charlie Munger about incentives"). The
  inspiration anchors the voice; the **charter** defines the seat's job.

Give each seat:

| Field | What it does |
|---|---|
| `--archetype` | The seat's lens: operator, financier, contrarian, technologist, people-first, customer-champion... |
| `--decision-style` | How the persona reasons: first-principles, risk-first, pattern-matching from history, customer-back... |
| `--pushback` | `gentle` \| `firm` \| `relentless` — calibrated per seat |
| `--charter` | The standing question this seat always asks |

**Calibrating pushback.** This is the heart of the skill and the easiest thing
to get wrong in both directions:

- **Never sycophantic.** An advisor who agrees with the operator is dead weight;
  if a take amounts to "great idea, boss," rewrite it until it earns its seat.
- **Never devil's-advocate-for-sport.** Manufactured opposition that exists to
  perform rigor takes the wind out of good ideas and teaches the operator to
  stop bringing them. Pushback must be *in service of a better decision*.
- **Challenge, then CONVERGE.** Every debate ends with the board's converged
  recommendation (or a clearly-scoped disagreement the operator must resolve).
  A board that only argues has not done its job.

3–5 active seats is the sweet spot. Retire seats that stop earning their place
(`retire-advisor` — history is preserved, the seat leaves future debates).

⏸ OPERATOR CHECKPOINT — the operator names the seats, the inspirations, and the
pushback level for each. The agent drafts personas; the operator approves them.

---

## 3. Personal Context System

Context is everything. It is the difference between generic strategy advice and
an advisor who has worked with you for years.

Store context docs (`add-context --kind <kind>`):

| Kind | Contents |
|---|---|
| `role` | Your role, mandate, what you're accountable for, how you're measured |
| `company` | Stage, model, team shape, cash position, current constraints |
| `ecosystem` | Market, customers, partners, regulatory weather |
| `competitive-stance` | Who you're up against and how you win |
| `priorities` | This quarter's true priorities (not the official ones — the real ones) |
| `past-decision` | A previous decision and how it actually turned out |

Rules of use:

1. **Load context before every debate.** `list-context --full` and read the
   relevant docs before writing any take. Takes that ignore the operator's
   actual constraints are generic strategy content, not advice.
2. **Keep it fresh.** When the interview surfaces new context, offer to save it
   as a context doc immediately.
3. **Reviews feed context.** Every `review-decision` should produce or update a
   `past-decision` context doc — this is how the board accumulates judgment.

---

## 4. Decision Workflow

Status flow: `framing → debating → deciding → decided → reviewed`.
The CLI advances status automatically: the first take moves framing→debating,
the bias check moves →deciding, `decide` sets decided, `review-decision` sets
reviewed.

### Step 1 — Open ⏸ OPERATOR CHECKPOINT

The operator brain-dumps everything: the question, the pressure, the politics,
the half-formed intuitions, what was said before the recording started. Spoken,
messy, unstructured — do NOT ask them to organize it. Store it verbatim:

```bash
advisor.py open-decision --question "..." --stakes high \
    --operator-style pushback-then-space --primer "<verbatim dump>"
```

`--stakes` (`low | medium | high | irreversible`) scales the process: a `low`
decision may need two takes and no scenarios; `irreversible` gets the full
treatment and a relentless-pushback pass.

`--operator-style` records how THIS operator wants to receive the board's
output (see Step 7).

### Step 2 — Interview (agent work)

Grill the operator before producing anything: What assumptions are you making?
What would have to be true for the obvious answer to be wrong? Who loses if
this goes your way? What haven't you said out loud yet? What does "good" look
like in 12 months? Record it:

```bash
advisor.py add-note --about <decision-id> --type interview --content "<Q&A>"
```

### Step 3 — Load context (agent work)

`list-context --full` plus `show-decision` on any linked past decisions.
Re-read the primer. Only then start writing takes.

### Step 4 — Independent takes (agent work)

Each active advisor writes their take **without seeing the others** — write
each one from a clean framing of primer + interview + context only, never from
the previous takes. This is what makes the later debate real instead of an echo.
One take per seat, in that seat's voice, at that seat's pushback level:

```bash
advisor.py add-take --decision <id> --advisor <advisor-id> \
    --stance conditional --content "<the take, in persona voice>"
```

Stances: `for | against | conditional | reframe`.

### Step 5 — Debate note (agent work)

Now the seats see each other. Stage the debate: where takes collide, push each
position against the others' strongest points — then **converge**. The debate
note records the clash AND the landing: the board's recommendation, the
dissents worth preserving, and what would change the board's mind.

```bash
advisor.py add-debate --decision <id> --content "<challenge → converge synthesis>"
```

### Step 6 — Bias check (agent work)

Three questions, answered honestly:

1. **What biases might I (the operator) have?** Sunk cost, recency, social
   pressure from whoever asked last, attachment to a prior public position.
2. **What biases might the AI have?** Agreement bias toward the operator's
   framing, overweighting the articulate primer over unstated context,
   pattern-matching to generic startup advice.
3. **What am I not seeing because of my position?** What does the operator's
   seat structurally hide — what would the newest employee, the biggest
   customer, or the board chair see instantly?

```bash
advisor.py add-bias-check --decision <id> --content "<the three answers>"
```

This moves the decision to `deciding`.

### Step 7 — ⏸ OPERATOR CHECKPOINT — the operator decides

Present the board's output **matched to the operator's decision style**
(recorded at open):

- `options-menu` — 2–4 real options with trade-offs; the operator picks.
- `bottom-line` — the board's single recommendation up front, reasoning below.
- `pushback-then-space` — deliver the strongest challenge to the operator's
  leaning, then stop talking. No follow-up pressure; they decide in their own time.

The agent never records an outcome the operator hasn't stated.

### Step 8 — Scenario stress-tests (agent work, after the call)

Given the decision as made, stand behind it under multiple futures — not just
the hoped-for one: "what if the market shifts to X?", "what if the competitor
does Y?", "what if the team pushes back on Z?"

```bash
advisor.py add-scenario --decision <id> \
    --condition "Key competitor cuts price 30% in Q3" \
    --impact "Margin case breaks; decision survives only if we win on service" \
    --likelihood medium
```

3–5 scenarios spanning market, competitor, and internal futures. If the
decision only survives the hoped-for future, take that finding back to the
operator **before** journaling — it may reopen Step 7.

### Step 9 — Journal + review date

```bash
advisor.py decide --decision <id> --outcome "<what was decided>" \
    --journal "<what, why, expected results, what would prove us wrong>" \
    --review-date 2026-10-01
```

No journal or no review date ⇒ the CLI warns and the audit flags it. A decision
without a review date is a loop that never closes.

---

## 5. Review Workflow

On the review date (`list-decisions --review-due` surfaces them):

1. Pull the journal: `show-decision --id <id>` — what did we expect?
2. Interview the operator: what actually happened? What surprised us? Which
   advisor's take aged best? Which scenario materialized?
3. Record it: `review-decision --decision <id> --content "<happened vs expected>"`
   (sets status `reviewed`).
4. **Feed it back:** write or update a `past-decision` context doc so the next
   debate starts smarter:
   `add-context --kind past-decision --name "EU entry (2026)" --content "..."`

---

## 6. Command Reference

Run as `uv run --project skills/advisor python skills/advisor/advisor.py <command>`.

| Command | Purpose | Key flags |
|---|---|---|
| `add-advisor` | Seat a persona on the board | `--name` `--archetype` `--decision-style` `--pushback` `--inspiration` `--charter` `--board` |
| `list-advisors` | List seats | `--include-retired` |
| `retire-advisor` | Retire a seat | `--id` |
| `add-context` | Add a context doc | `--name` `--kind` `--content/--content-file` |
| `list-context` | List context docs | `--kind` `--full` |
| `open-decision` | Open a decision (framing) | `--question` `--primer/--primer-file` `--stakes` `--operator-style` |
| `add-note` | Attach a note to any entity | `--about` `--type` (primer/interview/debate/bias/journal/general) `--content` |
| `add-take` | One advisor's independent take | `--decision` `--advisor` `--stance` `--content` |
| `add-debate` | Challenge→converge synthesis | `--decision` `--content` |
| `add-bias-check` | Bias check (→ deciding) | `--decision` `--content` |
| `add-scenario` | Scenario stress-test | `--decision` `--condition` `--impact` `--likelihood` |
| `decide` | Outcome + journal + review date | `--decision` `--outcome` `--journal` `--review-date` |
| `review-decision` | Close the loop (→ reviewed) | `--decision` `--content` |
| `list-decisions` | List decisions | `--status` `--stakes` `--review-due` `--journal` |
| `show-decision` | Full detail (takes, notes, scenarios) | `--id` |
| `report-decision` | Markdown decision report | `--id` |
| `report-board` | Markdown roster + decision stats | — |
| `audit` | Run quality-checks.yaml | — |

---

## 7. Data Model

Namespace `advsr-`, extending the `alh-*` core types in the `alh_personal`
database. Ids are `<type>-<hash12>`. Notes attach to decisions via
`alh-aboutness`.

### Entities

| Type | Sub | Key attributes |
|---|---|---|
| `advsr-advisor` | `alh-domain-thing` | `advsr-archetype`, `advsr-decision-style`, `advsr-pushback-level` (gentle\|firm\|relentless), `advsr-inspiration`, `advsr-charter`, `advsr-seat-status` (active\|retired) |
| `advsr-decision` | `alh-domain-thing` | `advsr-question`, `advsr-decision-status` (framing\|debating\|deciding\|decided\|reviewed), `advsr-stakes` (low\|medium\|high\|irreversible), `advsr-operator-style`, `advsr-outcome`, `advsr-review-date` |
| `advsr-board` | `alh-collection` | `name` |
| `advsr-context-doc` | `alh-artifact` | `advsr-context-kind` (role\|company\|ecosystem\|competitive-stance\|priorities\|past-decision), `content` |
| `advsr-scenario` | `alh-fragment` | `advsr-scenario-condition`, `advsr-scenario-impact`, `advsr-scenario-likelihood` (low\|medium\|high) |

### Notes (all sub `alh-note`, linked via `alh-aboutness`)

| Type | Purpose |
|---|---|
| `advsr-primer-note` | Operator's messy brain dump at open |
| `advsr-interview-note` | Agent's interview of the operator |
| `advsr-take-note` | One advisor's independent position; owns `advsr-stance` (for\|against\|conditional\|reframe) |
| `advsr-debate-note` | Challenge-then-converge synthesis |
| `advsr-bias-note` | Operator's biases / AI's biases / positional blind spots |
| `advsr-journal-note` | Decision journal entries and reviews |

### Relations

| Relation | Roles |
|---|---|
| `advsr-seat-on-board` | `advisor` (advsr-advisor) ↔ `board` (advsr-board) |
| `advsr-take-by` | `take` (advsr-take-note) ↔ `advisor` (advsr-advisor) |
| `advsr-scenario-for` | `scenario` (advsr-scenario) ↔ `decision` (advsr-decision) |

---

## 8. Dashboard

`/advisor` hub (see `dashboard/views/hub.yaml`):

- **Decisions** — board by `advsr-decision-status` with stakes badges.
- **Board** — advisor roster cards (archetype, style, pushback, charter).
- **Journal** — decided/reviewed list with review dates; overdue reviews flagged.
- **Decision detail** (`/advisor/decision/[id]`) — takes per advisor, debate,
  bias check, scenario matrix, journal.

---

## 9. Common Mistakes

- **Using the AI as another yes-voice.** If every take supports the operator's
  leaning, the board has failed. At least one seat must hold a genuinely
  different position or explicitly explain why convergence is real, not polite.
- **Debate-for-sport.** Contrarianism that exists to look rigorous takes the
  wind out of ideas and erodes the operator's trust. Challenge only what the
  seat's charter genuinely disputes — then converge.
- **Skipping the bias check.** It feels optional; it is where the blind spots
  live. The workflow enforces it (status only reaches `deciding` through
  `add-bias-check`), and the audit flags decisions that skipped it.
- **No review date, so the loop never closes.** Undated decisions never get
  reviewed, reviews never feed context docs, and the board never gets smarter.
  `decide` warns; `list-decisions --review-due` and the `stale-reviews-due`
  audit check keep you honest.
- **Writing takes after reading the other takes.** That's one opinion wearing
  five hats. Independence first, debate second.
- **Skipping context.** A debate run without `list-context --full` produces
  generic strategy advice — exactly what this skill exists to avoid.
