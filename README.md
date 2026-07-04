# alhazen-skill-personal-assistant

An **executive AI team** built as personal-assistant skills for the
[Alhazen](https://github.com/sciknow-io/skillful-alhazen) TypeDB-powered
notebook. All skills **share one TypeDB database, `alh_personal`** — one
knowledge graph where the people in your career network are the same people in
your stakeholder CRM.

The roster implements the four "digital team members every leader should hire"
— a research analyst, a strategic thought partner, a communication expert, and
an operational powerhouse — plus a career graph, a health coach, and a
chief-of-staff capstone. Design rationale lives in
[docs/executive-team-design.md](docs/executive-team-design.md); the five
operating principles every skill follows (speak-don't-type, habitual brain
dumps, AI-interviews-you-first, plan/execute separation, deliberate
intervention points) live in
[docs/operating-principles.md](docs/operating-principles.md).

## The Team

| Skill | Team member | Namespace | Dashboard |
|-------|-------------|-----------|-----------|
| **analyst** | Research analyst: decision-framed missions, multi-thread consensus, independent verification, the three-question gate | `anlst-` | `/analyst` |
| **advisor** | Strategic thought partner: board of advisor personas, calibrated pushback, bias checks, scenario stress-tests, decision journal | `advsr-` | `/advisor` |
| **scribe** | Communication expert: voice profiles, audience personas, review loops, dimension-scored feedback | `scribe-` | `/scribe` |
| **ops** | Operational powerhouse: recurring briefs (manual-before-automate), stakeholder CRM with undercurrents, meeting prep, commitments, monitors | `ops-` | `/ops` |
| **career** | Career graph: people, collaborators, projects, and potential new positions on top of the opportunity pipeline *(pivot of the former jobhunt skill)* | `career-` | `/career` |
| **coach** | Health & fitness: HealthKit metrics, goals, regressions, appointments | `coach-` | `/coach` |
| **chief-of-staff** | Capstone: read-only daily agenda / weekly review across the whole team | *(none)* | `/chief` |

**Start with one team member, earn the capstone.** The chief-of-staff only
pays off after the individual skills hold real data.

## Install

Requires the Alhazen base pair from the
[`skillful-alhazen`](https://github.com/sciknow-io/skillful-alhazen)
marketplace (`alhazen-core` + `typedb-notebook`), which install automatically
as cross-marketplace dependencies.

```
/plugin marketplace add sciknow-io/skillful-alhazen
/plugin marketplace add sciknow-io/alhazen-skill-personal-assistant
/plugin install analyst@alhazen-personal-assistant
/plugin install advisor@alhazen-personal-assistant
/plugin install scribe@alhazen-personal-assistant
/plugin install ops@alhazen-personal-assistant
/plugin install career@alhazen-personal-assistant
```

Each plugin's SessionStart hook provisions `alh_personal` and loads its
schema; skills work independently but compound when installed together (the
chief-of-staff reads whatever namespaces exist and skips the rest).

## Migrating from jobhunt

The former **jobhunt** skill is now **career** (`jhunt-*` → `career-*`). If you
have legacy jobhunt data in `alh_personal`, run the one-shot migration:

```
uv run python skills/career/career.py migrate-from-jobhunt
```

See `skills/career/SKILL.md` § Migration for details.
