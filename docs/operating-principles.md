# Operating Principles for the Executive AI Team

These five non-negotiables apply to **every** skill in this repo (analyst, advisor,
scribe, ops, career, coach). They separate mediocre output from exceptional results,
and every SKILL.md workflow in this repo is built around them. They are
tool-agnostic: they matter more than any specific feature of any specific model.

## 1. Speak, don't type — capture messy thinking

Typing filters thinking; speaking lets intuitive, non-linear thought through.
Modern frontier models handle unstructured, spiral input extremely well, and the
operator's messy thinking is the *most valuable input* the system can get.

**In practice:** every skill accepts free-form "primer" text (voice-dictated brain
dumps are ideal). Never require the operator to pre-structure their input; the
agent structures it.

## 2. Brain-dump habitually — capture undocumented context

Executives carry enormous undocumented context: relationship dynamics, meeting
undercurrents, half-formed intuitions, things said before the recording started,
a look on someone's face. AI gives mediocre answers without this context.

**In practice:** every skill stores primer notes and touchpoint/undercurrent notes
even when there is no immediate use for them. Reduce capture friction to near zero
(`add-note`, `log-touchpoint`, `--primer` flags). Capture first, organize later.

## 3. Let the AI interview you first

The more senior the operator, the more unknown-unknowns they carry. Before any
complex task — research, decision, communication — the agent grills the operator:
What assumptions are you making? What haven't you considered? What context should
you provide?

**In practice:** every "create" workflow (research mission, decision, piece, brief
spec) begins with a structured interview step, recorded as an interview note.
Surface blind spots *before* producing results.

## 4. Separate planning from execution

The more critical the task, the more planning and execution must be split. Don't
jump straight to output: converse to plan the approach (what information, what
order, what does success look like), refine the plan, *then* execute — often in a
separate conversation or tool.

**In practice:** missions/decisions/pieces have explicit `planning` states before
`executing`/`drafting` states. The plan is stored (plan note) so execution can be
audited against it.

## 5. Be intentional about intervention points — and always capture primers

The more judgment-heavy the work, the less it should be fully offloaded. Design
workflows so AI handles everything else and the operator steps in only at the
strategic moments — always at the beginning, and at a few defined checkpoints.
Leaders never come to a task with a blank slate: existing assumptions, premises,
and formed opinions are the operator's advantage. Offload them at the start, even
messy and unstructured, so output reflects *their* thinking rather than generic
results.

**In practice:** every entity that represents work-in-flight records a primer note
at creation, and SKILL.md workflows mark explicit operator checkpoints
(⏸ OPERATOR CHECKPOINT) where judgment is required. Everything between
checkpoints is agent work.

---

## Corollaries used across skills

- **Wisdom of the crowd (analyst):** never trust one model/thread; run the same
  research in parallel threads, aggregate agreement, investigate divergence, and
  fact-check with a *separate* thread — AI verifies better than it generates.
- **Three-question gate (analyst):** before acting on any research: (1) grounded in
  real sources or pattern-matching? (2) what's missing that I didn't think to ask?
  (3) would I put my name on this?
- **Calibrated pushback (advisor):** not a devil's advocate for sport, not
  sycophancy — challenge, then converge on a better decision.
- **Dimension scoring (scribe):** feedback as scored dimensions (clarity 9/10,
  wit 5/10), never "I don't like this" — models are goal-driven and need distance-
  to-target.
- **Manual before automated (ops):** never automate a brief/report before running
  it manually for one to two weeks and consuming the output; only then commit.
- **Don't automate what you do — build what you never could:** the question is not
  "what can I automate?" but "what would I build with unlimited headcount?"
