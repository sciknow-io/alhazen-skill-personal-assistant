---
name: career
description: Manage your career graph — people, collaborators, projects, and potential new positions — plus the opportunity pipeline, skill gaps, and learning plan
read_strategy: |
  On first use: read Quick Start + Career Agent Profile.
  When working with people/projects: read People & Collaborators + Projects sections.
  When searching: read Discovery section (agent-driven search missions).
  When ingesting: read Ingestion + Sensemaking sections.
  When analyzing: read Analysis section.
  Full command reference: read Commands section on demand.
triggers:
  - add job / ingest job / new position
  - add person / add collaborator / add project
  - who do I know at / show my network / career graph
  - search for jobs / run a search mission
  - analyze this job posting / make sense of
  - show my pipeline / skill gaps / learning plan
  - update status / career move / job search
  - create career profile / set up job search
prerequisites:
  - TypeDB running (make db-start)
  - make build-skills
---

# Career Notebook Skill

Use this skill to manage your career as a knowledge graph — not just a job search. The graph holds **people** (contacts, mentors, sponsors, references), **collaborators** (who works with you on what), **projects** (the bodies of work that build career capital), and **potential new positions**, all layered on top of the opportunity pipeline (position / engagement / venture / lead). Claude acts as the career agent — browsing job boards, evaluating postings against the operator's profile, mapping relationships, and building structured understanding of positions, companies, people, and fit over time.

**Key principle:** The agent does the sensemaking. Scripts are tools that search APIs, store data, and run queries. The agent decides what's relevant, writes the rationale, and manages the pipeline.

**Primer principle (see docs/operating-principles.md):** every new opportunity or project gets the operator's messy initial brain dump stored as a primer note (`add-note --type primer`). Never require the operator to pre-structure it — capture first, organize later.

**Role model:** The career agent is a BFO/UFO *role* (`career-agent-role`) that inheres in a person — it is the person's active career role, and job-seeking is just one mode of it. One person can have multiple roles (career agent, author, evaluator). The role holds career-campaign data; the person holds identity data.

---

## 1. Quick Start

### Prerequisites

- TypeDB must be running: `make db-start`
- Dependencies installed: `uv sync --all-extras` (from project root)
- Schema loaded: run `make build-db` after `make build-skills`

> **Path note:** Replace `.claude/skills/career` below with your installation directory:
> - **Claude plugin install:** `${CLAUDE_PLUGIN_ROOT}/skills/career` (self-contained bundle at `plugins/career/`)
> - **skillful-alhazen project:** `.claude/skills/career`
>
> When installed as a plugin, TypeDB starts automatically on session start (no manual init required).

### Environment Variables

- `TYPEDB_HOST`: TypeDB server (default: localhost)
- `TYPEDB_PORT`: TypeDB port (default: 1729)
- `TYPEDB_DATABASE`: Database name (default: alhazen_notebook)

### Essential Commands

```bash
# Ingest a job posting from URL
uv run python .claude/skills/career/career.py ingest-job \
    --url "https://boards.greenhouse.io/anthropic/jobs/123456" \
    --priority high

# List your pipeline
uv run python .claude/skills/career/career.py list-pipeline

# Show position details
uv run python .claude/skills/career/career.py show-position --id "position-abc123"

# Add a note to any entity
uv run python .claude/skills/career/career.py add-note \
    --about "position-abc123" --type research \
    --content "Strong AI safety focus, good culture fit"
```

### Command Output Pattern

`uv run` emits a `VIRTUAL_ENV` warning to stderr. Always use `2>/dev/null` when piping output to a JSON parser -- never `2>&1`, which merges the warning into stdout and breaks JSON parsing.

---

## 2. Career Agent Profile

The career agent is modeled as a **role** (`career-agent-role`, BFO/UFO pattern) that inheres in a person — the person's active career role, with job-seeking being one mode of it. The role holds career-campaign data (target role, industries, salary expectations) while the person entity holds identity data (name, email, linkedin).

### Create a Seeker Profile

```bash
uv run python .claude/skills/career/career.py create-seeker-profile \
    --person op-f25ab4b15b0f \
    --target-role "Principal AI Architect" \
    --industries "AI, Biotech, Scientific Computing" \
    --salary "200k-250k" \
    --location "Remote / SF Bay Area" \
    --focus "TypeDB-powered knowledge systems, AI for science"
```

This creates a `career-agent-role` entity linked to the person via `alh-role-bearing`. All pipeline data (opportunities, skills, candidates) scopes to this role.

### Build the Skill Profile

Skills are owned by the seeker role, derived from real evidence, and use a simplified Bloom's taxonomy for proficiency levels.

**Proficiency levels:**
| Level | Meaning | Evidence type | Interview readiness |
|-------|---------|---------------|-------------------|
| `expert` | Can design/teach | Publications, architected systems, led teams | Can whiteboard, critique alternatives |
| `practiced` | Hands-on experience | Projects, production use, coursework | Can walk through how you used it |
| `aware` | Conceptual knowledge | Read papers/docs, attended talks | Can answer "what is X" questions |
| `none` | Not known | No evidence | Cannot discuss |

#### Step 1: Ingest Profile Artifacts

The agent ingests the seeker's professional artifacts as sources of evidence. Each artifact is stored and linked to the seeker via `alh-aboutness` so skills can trace back to their proof.

```bash
# Ingest LinkedIn profile (save page HTML or use Playwright MCP to capture)
uv run python .claude/skills/career/career.py ingest-job \
    --url "https://linkedin.com/in/username"

# Ingest resume (PDF or text)
# Upload or paste resume content, agent stores as career-resume artifact

# Ingest ORCID profile
# Agent fetches via WebFetch and stores key publications/experience

# Ingest Google Scholar page
# Agent fetches and extracts publication list, h-index, citation metrics
```

The agent should fetch each source, extract the content, and store it as an artifact linked to the seeker role via `alh-aboutness`. This creates the evidence chain: artifact → seeker → skill.

#### Step 2: Sensemaking Interview

The agent reads the ingested artifacts and conducts a structured interview with the seeker:
- "Tell me about your TypeDB experience — what have you built?"
- "How deep is your AWS knowledge — have you architected solutions or followed tutorials?"
- "What's your biomedical ontology experience — which ones have you used?"

For each skill identified, the agent assesses the proficiency level based on the evidence and discussion.

#### Step 3: Create Skills with Evidence

```bash
uv run python .claude/skills/career/career.py add-skill \
    --name "Knowledge Graphs" --level "expert" \
    --evidence "Built 5000+ entity TypeDB production KG, BFO/UFO ontology design" \
    --recency "daily 2026" \
    --description "TypeDB 3.x, TypeQL, schema evolution, GLAV mapping"

uv run python .claude/skills/career/career.py add-skill \
    --name "RAG Pipelines" --level "expert" \
    --evidence "Voyage AI + Qdrant in production, hybrid ontology-filtered retrieval" \
    --recency "daily 2026"

uv run python .claude/skills/career/career.py add-skill \
    --name "Pharma Experience" --level "none" \
    --description "No direct pharma industry experience. Biomedical informatics at CZI."
```

Each skill is linked to the seeker via `career-seeker-has-skill`. The `--evidence` field should reference the ingested artifacts where possible.

#### Step 4: Gap Analysis

Once skills are populated, gap analysis joins seeker skills against position requirements:
- Position requires "RAG Pipelines" at "required" level → seeker has it at "expert" → no gap
- Position requires "Pharma Experience" at "preferred" level → seeker has "none" → gap

```bash
uv run python .claude/skills/career/career.py show-gaps
```

### View Your Skills

```bash
uv run python .claude/skills/career/career.py list-skills
```

---

## 3. People & Collaborators

People are `alh-person` entities — deliberately shared with the ops skill's stakeholder dossiers (same `alh_personal` database, deliberate synergy). The career skill layers career-specific structure on top:

- **Contact roles** — a person serving as recruiter/hiring-manager/referrer for an opportunity (`career-contact-for-opportunity` relation, `career-contact-role` attribute).
- **Collaborations** — a person working with you on a project or opportunity (`career-collaboration` relation) with a `career-collab-role` (collaborator | mentor | sponsor | reference | co-author), `career-collab-since` date, and `career-collab-strength` (weak | working | strong).
- **Relationship notes** — narrative context about the relationship (`career-relationship-note`), attached to the person via `add-note --type relationship`.

### Add and Browse People

```bash
# Add a person to the career graph
uv run python .claude/skills/career/career.py add-person \
    --name "Jane Smith" \
    --email "jane@example.com" \
    --linkedin "https://linkedin.com/in/janesmith" \
    --description "Met at ML Summit 2025; leads knowledge-graph team at BigCo"

# List everyone (with collaboration/contact counts)
uv run python .claude/skills/career/career.py list-people

# Full person view: contact roles, collaborations, relationship notes, borne roles
uv run python .claude/skills/career/career.py show-person --id "person-abc123"
```

### Link Collaborators

```bash
# Link a person to a project or any opportunity
uv run python .claude/skills/career/career.py link-collaborator \
    --person "person-abc123" \
    --target "project-def456" \
    --role co-author \
    --since 2024-06-01 \
    --strength strong

# Who collaborates on this project?
uv run python .claude/skills/career/career.py list-collaborators --target "project-def456"

# What does this person collaborate on?
uv run python .claude/skills/career/career.py list-collaborators --person "person-abc123"
```

### Capture Relationship Context

After any meaningful interaction, capture the messy context — it is the most valuable input the graph can get:

```bash
uv run python .claude/skills/career/career.py add-note \
    --about "person-abc123" --type relationship \
    --content "Jane is skeptical of pure-LLM approaches; owes me an intro to her VP. Prefers async email over calls."
```

---

## 4. Projects

A `career-project` (sub `career-opportunity`) is a body of work that builds career capital — an open-source project, a paper, a product, a community effort. Projects carry your role (`lead | contributor | advisor`), a lifecycle status (`exploring | active | paused | shipped | sunset`), and a URL, and share everything opportunities have (notes, priority, company link, collaborators).

### Manage Projects

```bash
# Create a project
uv run python .claude/skills/career/career.py add-project \
    --name "Alhazen Knowledge Notebook" \
    --role lead \
    --status active \
    --url "https://github.com/example/alhazen" \
    --priority high \
    --description "TypeDB-backed knowledge notebook framework"

# ALWAYS capture the operator's primer right after creation (operating principle #5)
uv run python .claude/skills/career/career.py add-note \
    --about "project-abc123" --type primer \
    --content "Raw brain dump: why this project matters, who cares about it, what winning looks like..."

# List projects (board data: status, role, collaborators)
uv run python .claude/skills/career/career.py list-projects
uv run python .claude/skills/career/career.py list-projects --status active

# Update lifecycle
uv run python .claude/skills/career/career.py update-project \
    --id "project-abc123" --status shipped
```

**Primer rule:** every new project *and* every new opportunity gets a `career-primer-note` via `add-note --type primer` capturing the operator's unfiltered initial thinking (voice-dictated is ideal). Do this at creation time, before any analysis.

---

## 5. Discovery — Agent-Driven Search Missions

Discovery is **agent-driven**: Claude browses job boards, reads postings, evaluates fit against the seeker profile, and adds good matches as candidates with a written rationale. No automated scoring or LLM triage — the agent IS the sensemaker.

### How a Search Mission Works

1. **Operator asks**: "Search Anthropic for ML roles that match my profile"
2. **Agent reads** the seeker profile (target role, industries, skills from TypeDB)
3. **Agent searches** using the best tool for the job:
   - Platform API (`search-source`) for bulk listing from Greenhouse/Lever boards
   - Playwright MCP (`search-source` on website sources) for browsing JS-rendered job sites like hiring.cafe
   - Web search (`web-search` skill) for ad-hoc browsing of careers pages or niche boards
4. **Agent reads** each posting and evaluates fit
5. **Agent adds** good matches as candidates with rationale:
   ```bash
   uv run python .claude/skills/career/career_forager.py add-candidate \
       --title "Research Scientist, AI for Science" \
       --url "https://boards.greenhouse.io/anthropic/jobs/123" \
       --location "San Francisco" \
       --relevance 0.85 \
       --reason "Strong fit: combines AI evaluation with scientific methodology"
   ```
6. **Agent writes** a search mission note summarizing what was found
7. **Operator reviews** candidates in the dashboard, promotes promising ones to positions

### Configure Search Sources

Three types of sources:

```bash
# Company recruiting pages (Greenhouse/Lever/Ashby) — API-based, returns all jobs
uv run python .claude/skills/career/career_forager.py add-source \
    --name "Anthropic" --platform greenhouse --token anthropic

# Job board aggregators (LinkedIn/Remotive/Adzuna) — API-based, keyword search
uv run python .claude/skills/career/career_forager.py add-source \
    --name "ML Jobs" --platform linkedin --query "machine learning" --location "San Francisco"

# Job websites (hiring.cafe, etc.) — browser-based via Playwright MCP
uv run python .claude/skills/career/career_forager.py add-source \
    --name "hiring.cafe" --platform website \
    --url "https://hiring.cafe" \
    --query "AI scientist knowledge graph biotech drug discovery"
```

| Platform | Type | Auth | Args |
|----------|------|------|------|
| `greenhouse` | Company board | None | `--token` (slug) |
| `lever` | Company board | None | `--token` (slug) |
| `ashby` | Company board | None | `--token` (slug) |
| `linkedin` | Aggregator | None | `--query`, `--location` |
| `remotive` | Aggregator | None | `--query`, `--location` |
| `adzuna` | Aggregator | API key | `--query`, `--location` |
| `website` | Job website | Playwright MCP | `--url`, `--query` |

### Search a Source (Raw Listings)

Returns all job listings from a source for the agent to evaluate:

```bash
uv run python .claude/skills/career/career_forager.py search-source --source "Anthropic"
# Returns: {jobs: [{title, url, location, external_id}, ...]}
```

The agent reads through these, fetches interesting postings via web-fetch, and adds good matches as candidates.

### Search a Website Source (Playwright MCP)

For `website` platform sources, `search-source` returns instructions instead of job listings.
The agent uses Playwright MCP tools to browse the site interactively:

1. **Get source info:** `search-source --source "hiring.cafe"` returns the URL and query
2. **Navigate:** `browser_navigate` to the source URL
3. **Search:** `browser_type` the query into the search box, submit
4. **Wait:** `browser_snapshot` or `browser_take_screenshot` to see rendered results
5. **Extract:** `browser_run_code_unsafe` to extract job URLs from the DOM, or read the snapshot
6. **Evaluate:** `WebFetch` each interesting job URL (individual pages usually render server-side)
7. **Add matches:** `add-candidate` with rationale for each good match

**Example: hiring.cafe**

hiring.cafe is a 41M+ job aggregator with AI-powered search. It uses client-side React rendering,
so API/curl cannot access search results — Playwright MCP is required.

The site auto-generates filters from natural language queries (Department, Industry, Tech Keywords).
Sometimes the auto-filters are too narrow and return zero results. If this happens, click "Reject All"
on the suggested filters and try a broader query, or remove specific filter chips.

Individual job pages (`/viewjob/{id}`) render server-side and can be fetched with WebFetch for full details.

### Semantic Search Across Candidates

Candidates are embedded in Qdrant on creation. Search by meaning:

```bash
uv run python .claude/skills/career/career_forager.py search-candidates \
    --query "knowledge graph engineering for science" --limit 10
```

### Manage Candidates

```bash
# List all candidates
uv run python .claude/skills/career/career_forager.py list-candidates

# List by status
uv run python .claude/skills/career/career_forager.py list-candidates --status reviewed

# Promote a candidate to a full position (creates career-position + application note)
uv run python .claude/skills/career/career_forager.py promote --id candidate-abc123
```

### Key Principle

The agent does the sensemaking. Scripts are tools — they search APIs, store data, and run queries. The agent decides what's relevant, writes the rationale, and manages the pipeline.

---

## 6. Ingestion

### From URL (ingest-job)

**Triggers:** "add job", "ingest job", "new position", "found a job posting", "here's a job"

```bash
uv run python .claude/skills/career/career.py ingest-job \
    --url "https://boards.greenhouse.io/anthropic/jobs/123456" \
    --priority high \
    --tags "ai" "ml" "safety"
```

**Options:**
- `--url` (required): Job posting URL
- `--priority`: Set priority (high/medium/low)
- `--tags`: Space-separated tags

**Returns:**
```json
{
  "success": true,
  "position_id": "position-abc123",
  "artifact_id": "artifact-xyz789",
  "status": "raw",
  "message": "Artifact stored - ask Claude to 'analyze this job posting' for sensemaking."
}
```

**What ingestion produces:**
- A `career-position` entity with status `researching`
- A `career-job-description` artifact containing the raw scraped page content
- An initial `career-application-note` tracking the application status

### Manual Position (add-position)

```bash
uv run python .claude/skills/career/career.py add-position \
    --title "Senior ML Engineer" \
    --company "Anthropic" \
    --priority high
```

### Add Company

```bash
uv run python .claude/skills/career/career.py add-company \
    --name "Anthropic" \
    --url "https://anthropic.com" \
    --description "AI safety research company"
```

### Add Engagement

```bash
uv run python .claude/skills/career/career.py add-engagement \
    --name "Acme Corp Data Consulting" \
    --company-id "company-abc123" \
    --type project \
    --rate "$200/hr" \
    --status active \
    --priority high
```

**Engagement types:** `hourly` | `project` | `retainer` | `advisory`

### Add Venture

```bash
uv run python .claude/skills/career/career.py add-venture \
    --name "Augura Health Advisory" \
    --stage proposal-sent \
    --equity-type advisor \
    --priority high
```

**Venture stages:** `exploring` | `proposal-sent` | `negotiating` | `active` | `paused` | `closed`
**Equity types:** `none` | `advisor` | `cofounder` | `investor`

### Add Lead

```bash
uv run python .claude/skills/career/career.py add-lead \
    --name "Jane Smith - BigCo" \
    --status warm \
    --priority medium \
    --description "Met at ML Summit, interested in consulting"
```

**Lead statuses:** `first-contact` | `active` | `inactive` | `closed`

---

## 7. Sensemaking

### Sensemaking Workflow

**When user says "analyze this job posting" or "make sense of [position]":**

1. **Get the artifact content**
   ```bash
   uv run python .claude/skills/career/career.py show-artifact --id "artifact-xyz"
   ```

2. **Read and comprehend the content**
   - Look for: company name, job title, location, salary, remote policy
   - Identify: requirements, responsibilities, qualifications
   - Note: team info, culture signals, growth opportunities

3. **Research the company and leadership online** (use the web-search skill)

   Search for: company mission, funding, recent news, and LinkedIn activity of key leaders.
   Focus on:
   - **Company:** founding story, funding/investors, mission statement, recent product launches
   - **Leadership:** CEO, CTO, relevant SVPs -- what are they posting about on LinkedIn?
   - **Role context:** Which leader is likely the hiring manager? What technical bets is the team making?
   - **Culture signals:** hiring pace, public talks, open-source releases, AI-in-residence programs

   Save findings as a research note attached to **both** the company and the position:
   ```bash
   # Company-level research (background, funding, mission)
   uv run python .claude/skills/career/career.py add-note \
       --about "company-xyz" \
       --type research \
       --content "Series C, $4B raised. Mission: X. CEO recently spoke at Y conference..."

   # Position-level research (leadership context, role fit signals, hiring manager)
   uv run python .claude/skills/career/career.py add-note \
       --about "position-abc123" \
       --type research \
       --content "Bo Wang (SVP Biomedical AI) is likely hiring manager. Very active on LinkedIn..."
   ```

4. **Create/update the company**
   ```bash
   uv run python .claude/skills/career/career.py add-company \
       --name "Anthropic" \
       --url "https://anthropic.com" \
       --description "AI safety research company"
   ```

5. **Extract requirements using the skill vocabulary**

   Before extracting requirements, load the skill concept vocabulary:
   ```bash
   uv run python .claude/skills/career/career.py list-concepts
   ```
   
   This returns the full vocabulary with your proficiency levels, alt-labels, and hierarchy.
   Use canonical concept names when creating requirements so they match your skill profile.
   
   For each skill in the posting:
   - Look up the vocabulary for a matching concept (check alt-labels too)
   - If match exists: use the canonical name from the vocabulary
   - If no match: create a new concept first, then use it
   - If the skill is **not in your profile** (shows as "?" in list-concepts):
     **ASK THE USER to self-assess their level for this skill.**
     Don't guess — the user knows their own capabilities. Ask:
     "The posting requires [skill]. I don't have this in your profile yet.
     How would you rate your proficiency: expert, practiced, aware, or none?"
     Then create the skill with their assessment.
   
   ```bash
   # Create a new concept if needed
   uv run python .claude/skills/career/career.py add-concept \
       --name "Molecular Simulation" \
       --alt-labels "MD,Molecular Dynamics,Force Fields"
   
   # Add the user's self-assessed skill
   uv run python .claude/skills/career/career.py add-skill \
       --name "Molecular Simulation" --level "aware" \
       --evidence "Read papers, understand concepts, no hands-on" \
       --recency "reading 2026"
   
   # Then add the requirement (using the canonical concept name)
   uv run python .claude/skills/career/career.py add-requirement \
       --position "position-abc123" \
       --skill "Molecular Simulation" \
       --level "required"
   ```
   
   **Key principle:** Never assume the user's skill level. If a requirement mentions
   a skill not in their profile, ask them. Their self-assessment + evidence is the
   ground truth, not the agent's inference.

6. **Create analysis notes**

   **Fit Analysis Note:**
   ```bash
   uv run python .claude/skills/career/career.py add-note \
       --about "position-abc123" \
       --type fit-analysis \
       --content "Strong fit for core requirements. Gap in distributed systems." \
       --fit-score 0.82 \
       --fit-summary "Strong technical fit, one gap to address"
   ```

   **Skill Gap Note:**
   ```bash
   uv run python .claude/skills/career/career.py add-note \
       --about "position-abc123" \
       --type skill-gap \
       --content "Distributed systems is required. Recommend: DDIA book, MIT 6.824 course."
   ```

7. **Flag uncertainties**
   ```bash
   uv run python .claude/skills/career/career.py tag \
       --entity "requirement-xyz" \
       --tag "uncertain"
   ```

8. **Report findings to user**: company overview, leadership signals, fit score breakdown, key gaps, suggested next steps (including who to follow on LinkedIn)

### List Artifacts Needing Analysis

```bash
uv run python .claude/skills/career/career.py list-artifacts --status raw
uv run python .claude/skills/career/career.py list-artifacts --status all
```

### Get Artifact Content

```bash
uv run python .claude/skills/career/career.py show-artifact --id "artifact-xyz789"
```

### Quality Checklist

Every opportunity MUST have after sensemaking:

- **Primer note** -- the operator's messy initial brain dump, stored via `add-note --type primer` at creation time (operating principle #5: always capture primers)
- **Clean title** -- strip "Job Application for", "| LinkedIn", "hiring", and other job-board boilerplate from the name
- **Short-name** -- a compact display label (3-4 words, e.g. "Sr ML Eng - Anthropic")
- **Company linked** -- via `--company` flag on add-position, auto-matched to existing `career-company` entities (do not create duplicates)
- **Salary/compensation researched** -- if not in the posting, search Levels.fyi or Glassdoor and record in `salary-range` attribute
- **At least one research note** -- company background, leadership, role context
- **Requirements extracted** -- as `career-requirement` entities via `add-requirement`
- **Fit analysis note** -- with `fit-score` (0.0-1.0) and `fit-summary`
- **Opportunity summary** -- a `career-opp-summary-note` synthesizing all notes. Regenerated after any note is added or updated.
- **Embedded in map** -- run `embedding_map.py embed-and-map` after saving the summary so the opportunity appears on Mission Control.

### Opportunity Summary

Every opportunity has exactly one `career-opp-summary-note` — a living markdown dossier that is overwritten each time notes change. This is the primary embedding text for the Mission Control map and the quick-read view for understanding any opportunity.

**Workflow — regenerate after any note update:**
```bash
# 1. Fetch all notes + metadata
uv run python .claude/skills/career/career.py regenerate-summary --about <opp-id>

# 2. Read the JSON output, write a markdown summary following the template below

# 3. Save the summary (creates or overwrites)
uv run python .claude/skills/career/career.py upsert-summary --about <opp-id> --content "@/tmp/summary.md"

# 4. Re-embed to update the Mission Control map
uv run python local_skills/career/embedding_map.py embed-and-map
```

**IMPORTANT:** Step 4 (re-embed) MUST be run after saving the summary. Without it, new or updated opportunities will not appear on the Mission Control map. This step re-computes embeddings for ALL opportunities and regenerates the 2D layout.

**Summary templates by type:**

**Position:**
```markdown
## Role
- Title, company, location/remote policy
- Key responsibilities (2-3 bullets)
- Salary range if known

## Fit
- Overall fit score and one-line assessment
- Top strengths (2-3 bullets with specifics)
- Key gaps (1-2 bullets)

## Company
- What they do, stage/size, why interesting
- Key people (hiring manager, contacts)

## Status
- Current application status
- Key dates, next steps, or outcome
```

**Engagement:**
```markdown
## Engagement
- Client, scope, type (consulting/contract/advisory)
- Rate/compensation if known

## Fit
- Why this is a good match
- Key deliverables

## Status
- Current stage (proposal/active/paused/closed)
```

**Venture:**
```markdown
## Overview
- What the venture is, stage
- Your role/involvement

## Opportunity
- Why it's interesting
- Key milestones or next steps

## Status
- Current stage (seed/series-a/series-b/growth/closed)
```

**Lead:**
```markdown
## Contact
- Who, title, organization
- How you met, when

## Context
- What the connection is about
- Potential opportunity or value

## Status
- Relationship state (first-contact/active/inactive/closed)
```

---

## 8. Application Tracking

### Update Status

```bash
uv run python .claude/skills/career/career.py update-status \
    --position "position-abc123" \
    --status "applied" \
    --date "2025-02-05"
```

**Status values:** `researching` | `applied` | `phone-screen` | `interviewing` | `offer` | `accepted` | `rejected` | `withdrawn`

(`accepted` marks an offer you have accepted — the terminal "won" state for a position.)

### Add Notes

```bash
# Interaction note
uv run python .claude/skills/career/career.py add-note \
    --about "position-abc123" \
    --type interaction \
    --content "Phone screen went well, moving to technical round." \
    --interaction-type "call" \
    --interaction-date "2025-02-05"

# Strategy note
uv run python .claude/skills/career/career.py add-note \
    --about "position-abc123" \
    --type strategy \
    --content "Lead with distributed systems experience from caching project."

# Claude Code brief (CC agent writes a brief for the next session)
uv run python .claude/skills/career/career.py add-note \
    --about "position-abc123" \
    --type cc-brief \
    --content "Next session: prep for technical interview on 2025-02-10. Focus on system design questions."

# Claude Code feedback (CC agent records feedback from completed interaction)
uv run python .claude/skills/career/career.py add-note \
    --about "position-abc123" \
    --type cc-feedback \
    --content "User reported phone screen went well. Interviewer asked about distributed caching. Move to next round."
```

**Note types:** `research` | `strategy` | `interview` | `interaction` | `skill-gap` | `fit-analysis` | `primer` | `relationship` | `general` | `cc-brief` | `cc-feedback`

---

## 9. Analysis

### Skill Gap Analysis

```bash
uv run python .claude/skills/career/career.py show-gaps
```

### Learning Plan

```bash
uv run python .claude/skills/career/career.py learning-plan
```

### Add Learning Resources

```bash
uv run python .claude/skills/career/career.py add-resource \
    --name "Designing Data-Intensive Applications" \
    --type "book" \
    --url "https://dataintensive.net" \
    --hours 30 \
    --skills "distributed-systems" "system-design"
```

### Link Resource to Requirement

```bash
uv run python .claude/skills/career/career.py link-resource \
    --resource "<resource-id>" \
    --requirement "<requirement-id>"
```

### Cross-Skill Integration: Link Literature to Learning Plan

```bash
# Search for papers on a skill gap topic
uv run python .claude/skills/scientific-literature/scientific_literature.py search \
    --query "machine learning systems design" \
    --collection "ML Systems Reading List"

# Link collection to skill gap
uv run python .claude/skills/career/career.py link-collection \
    --collection "<collection-id>" \
    --skill "machine-learning"

# Link a specific paper to a learning resource
uv run python .claude/skills/career/career.py link-paper \
    --resource "<resource-id>" \
    --paper "<paper-id>"

# View updated plan
uv run python .claude/skills/career/career.py learning-plan
```

---

## 10. Reporting and Queries

### JSON Output (programmatic)

```bash
# All positions
uv run python .claude/skills/career/career.py list-pipeline

# Filter by status or priority
uv run python .claude/skills/career/career.py list-pipeline --status "interviewing"
uv run python .claude/skills/career/career.py list-pipeline --priority "high"

# All opportunity types
uv run python .claude/skills/career/career.py list-opportunities --type all
uv run python .claude/skills/career/career.py list-opportunities --type venture
uv run python .claude/skills/career/career.py list-opportunities --type engagement --status active

# Detail views
uv run python .claude/skills/career/career.py show-position --id "position-abc123"
uv run python .claude/skills/career/career.py show-opportunity --id "venture-abc123"
uv run python .claude/skills/career/career.py show-company --id "company-xyz"
uv run python .claude/skills/career/career.py show-gaps
uv run python .claude/skills/career/career.py learning-plan
```

### Markdown Output (for display to users)

```bash
uv run python .claude/skills/career/career.py report-pipeline   # Pipeline overview
uv run python .claude/skills/career/career.py report-stats      # Stats summary
uv run python .claude/skills/career/career.py report-gaps       # Skill gaps
uv run python .claude/skills/career/career.py report-position --id "position-xyz"  # Position detail
```

Use reports (Markdown) for displaying to users in chat. Use JSON commands (`list-pipeline`, `show-position`) for programmatic processing.

### Tagging

```bash
uv run python .claude/skills/career/career.py tag --entity "position-abc123" --tag "remote"
uv run python .claude/skills/career/career.py search-tag --tag "remote"
```

---

## 11. Opportunity Model

The career skill tracks multiple types of career opportunities via the `career-opportunity` hierarchy:

```
career-opportunity (base)
+-- career-position    -- formal employment application (has application-status pipeline)
+-- career-engagement  -- paid consulting/service work for a client
+-- career-venture     -- startup/advisory/equity opportunity
+-- career-lead        -- early-stage networking contact, role undefined
+-- career-project     -- body of work building career capital (open-source, paper, product)
```

All opportunity types share: `opportunity-status`, `priority-level`, `deadline`, and can be linked to a `career-company` via `opportunity-at-organization`.

All opportunity types work with `add-note --about <ID>` -- notes attach to any `identifiable-entity`.

### Update Any Opportunity

```bash
uv run python .claude/skills/career/career.py update-opportunity \
    --id "venture-abc123" \
    --status active \
    --stage negotiating \
    --priority high
```

### Modeling Guide

| Situation | Entity type | Key attributes |
|-----------|-------------|----------------|
| Own consulting business | `career-company` | name, description |
| Startup advisory role | `career-venture` | venture-stage, equity-type |
| Consulting engagement | `career-engagement` | engagement-type, rate-info |
| Networking contact (no role yet) | `career-lead` | opportunity-status, description |
| Formal job application | `career-position` | job-url, application-status pipeline |
| Open-source/paper/product work | `career-project` | project-role, project-status, project-url |

**Phylo strategy pattern:** Use an existing `career-position` as the anchor for all interactions. Add `career-interaction-note` entries for each meeting. Only create a separate `career-lead` if a genuinely new thread emerges from those conversations.

---

## 12. Data Model

### Entity Types

| Type | Description |
|------|-------------|
| `your-skill` | Your skills for gap analysis |
| `career-company` | An employer/client organization |
| `career-opportunity` | Base type for all opportunities |
| `career-position` | Formal job posting (sub opportunity) |
| `career-engagement` | Consulting engagement (sub opportunity) |
| `career-venture` | Startup/advisory venture (sub opportunity) |
| `career-lead` | Networking lead (sub opportunity) |
| `career-project` | Body of work building career capital (sub opportunity) |
| `alh-person` | A person in the career graph (shared with ops dossiers) |
| `career-agent-role` | The person's active career role (job-seeking is one mode) |
| `career-learning-resource` | Course, book, tutorial |
| `career-search-source` | Company board for forager |
| `career-candidate` | Discovered posting (forager) |

### Artifact Types

| Type | Description |
|------|-------------|
| `career-job-description` | Raw HTML/text from job posting URL |
| `career-resume` | Resume document |
| `career-cover-letter` | Cover letter |
| `career-company-page` | Company website snapshot |
| `career-proposal` | Proposal or pitch deck for engagement/venture |

### Note Types

| Type | Purpose |
|------|---------|
| `career-application-note` | Status tracking (positions) |
| `career-research-note` | Company/opportunity research |
| `career-interview-note` | Interview prep/feedback |
| `career-strategy-note` | Talking points, approach |
| `career-skill-gap-note` | Learning needs |
| `career-fit-analysis-note` | Fit assessment |
| `career-interaction-note` | Contact logs |
| `career-primer-note` | Operator's messy initial brain dump (every new opportunity/project) |
| `career-relationship-note` | Narrative about a person relationship in career context |
| `career-cc-brief-note` | Claude Code brief for next session |
| `career-cc-feedback-note` | Claude Code feedback from completed interaction |

### Relations

- `position-at-company` -- links position to employer
- `opportunity-at-organization` -- links any opportunity type to a company
- `career-collaboration` -- links a person to a project/opportunity (owns collab-role, collab-since, collab-strength)
- `career-contact-for-opportunity` -- a person serving as contact for an opportunity (owns contact-role)
- `aboutness` -- links notes to any entity (position, company, opportunity, person)
- `requirement-of` -- links requirements to positions

### Schema File

- **Career Schema:** `local_skills/career/schema.tql`
- **Core Schema:** `local_resources/typedb/alhazen_notebook.tql`

---

## 13. Command Reference

### career.py Commands

| Command | Description | Key Args |
|---------|-------------|----------|
| `ingest-job` | Fetch job URL, store raw | `--url` |
| `add-skill` | Add/update skill with Bloom's proficiency | `--name`, `--level` (expert/practiced/aware/none), `--evidence`, `--recency` |
| `list-skills` | Show your skills | |
| `list-artifacts` | List artifacts by status | `--status` |
| `show-artifact` | Get artifact content | `--id` |
| `add-company` | Add company | `--name` |
| `add-position` | Add position manually | `--title` |
| `add-engagement` | Add consulting engagement | `--name`, `--type`, `--rate` |
| `add-venture` | Add startup/advisory venture | `--name`, `--stage`, `--equity-type` |
| `add-lead` | Add networking lead | `--name`, `--status` |
| `update-opportunity` | Update any opportunity status/stage/priority | `--id` |
| `show-opportunity` | Show any opportunity details | `--id` |
| `list-opportunities` | List by type/status | `--type`, `--status`, `--priority` |
| `add-person` | Add a person to the career graph | `--name`, `--email`, `--linkedin` |
| `list-people` | List people with collaboration/contact counts | |
| `show-person` | Person detail: contact roles, collaborations, relationship notes | `--id` |
| `add-project` | Add a career project | `--name`, `--role`, `--status`, `--url` |
| `list-projects` | List projects with collaborators | `--status`, `--role` |
| `update-project` | Update project role/status/url/priority | `--id` |
| `link-collaborator` | Link person to project/opportunity | `--person`, `--target`, `--role`, `--since`, `--strength` |
| `list-collaborators` | List collaborations | `--person` or `--target` |
| `migrate-from-jobhunt` | One-shot copy of legacy jhunt-* data into career-* types | |
| `add-requirement` | Add skill requirement | `--position`, `--skill` |
| `update-status` | Change position application status | `--position`, `--status` |
| `add-note` | Create any note type | `--about`, `--type`, `--content` |
| `add-resource` | Add learning resource | `--name`, `--type` |
| `link-collection` | Link paper collection to skill gap | `--collection`, `--skill` |
| `link-resource` | Link resource to a skill requirement | `--resource`, `--requirement` |
| `link-paper` | Link learning resource to a paper | `--resource`, `--paper` |
| `create-seeker-profile` | Create the career-agent role for a person | `--person`, `--target-role`, `--industries` |
| `list-pipeline` | Show position pipeline | `--status`, `--priority`, `--person` |
| `show-position` | Position details | `--id` |
| `show-company` | Company details | `--id` |
| `show-gaps` | Skill gap analysis | |
| `learning-plan` | Prioritized study list | |
| `tag` | Tag an entity | `--entity`, `--tag` |
| `search-tag` | Find by tag | `--tag` |
| `report-pipeline` | Pipeline overview (Markdown) | |
| `report-stats` | Stats summary (Markdown) | |
| `report-gaps` | Skill gaps report (Markdown) | |
| `report-position` | Position detail (Markdown) | `--id` |

### career_forager.py Commands

| Command | Description | Key Args |
|---------|-------------|----------|
| `add-source` | Add a search source (company board or aggregator) | `--name`, `--platform`, `--token`/`--query` |
| `list-sources` | List configured search sources | |
| `remove-source` | Remove a source | `--id`, `--token`, or `--name` |
| `search-source` | Search one source (raw listings for agent review) | `--source` |
| `add-candidate` | Add a candidate with agent evaluation | `--title`, `--url`, `--relevance`, `--reason` |
| `search-candidates` | Semantic search across candidates (Qdrant) | `--query`, `--limit` |
| `list-candidates` | List candidates | `--status`, `--source` |
| `promote` | Promote candidate to full position | `--id` |

---

## 14. Quality Checks

Declarative audit rules for data quality are defined in `quality-checks.yaml`.

### Run Audits

```bash
# Check for violations
uv run python .claude/skills/career/career.py audit

# Auto-fix where possible
uv run python .claude/skills/career/career.py audit --fix

# Or use the generic audit runner
uv run python src/skillful_alhazen/utils/audit_runner.py run \
    --checks local_skills/career/quality-checks.yaml
```

### Current Checks

| Check | Severity | Description |
|-------|----------|-------------|
| `position-company-link` | high | Positions should be linked to a company via `position-at-company` |
| `ugly-titles` | medium | Position titles containing job-board boilerplate |
| `missing-short-name` | medium | Positions without a `short-name` for compact display |
| `missing-salary` | low | Positions without `salary-range` information |
| `positions-without-notes` | low | Positions with no notes at all |
| `duplicate-companies` | high | Multiple company entities with identical names |
| `orphaned-companies` | medium | Companies with no positions or opportunities linked |
| `projects-without-collaborators` | low | Projects with no linked collaborators |
| `people-without-context` | low | People with no notes, collaborations, or contact roles |

---

## 15. Dashboard

A Next.js dashboard is available for visualizing your job search pipeline. It runs in Docker (not `npm run dev`).

### Docker Build/Run

```bash
docker compose build --no-cache dashboard
docker compose up -d dashboard
# Dashboard available at http://localhost:3001
```

### Views

- **Pipeline Board** (`/career`) -- Kanban columns by application status
- **People** (`/career`, People tab) -- Table of the career graph's people with collaboration/contact counts
- **Projects** (`/career`, Projects tab) -- Board by project status with collaborator chips
- **Position Detail** (`/career/position/{id}`) -- Full position profile: requirements, notes, gap analysis, fit score
- **Person Detail** (`/career/person/{id}`) -- Contact roles, collaborations, relationship notes
- **Project Detail** (`/career/project/{id}`) -- Project profile with collaborators and notes
- **Collection Detail** (`/career/collection/{id}`) -- Notes and resources grouped by collection

### Internal Organization (for contributors)

- Pages: `dashboard/src/app/(career)/career/`
- Components: `dashboard/src/components/career/`
- API routes: `dashboard/src/app/api/career/`
- TypeScript wrapper: `dashboard/src/lib/career.ts`

---

## 16. Migration from jobhunt

The career skill is the pivot of the former **jobhunt** skill. The schema rename (`jhunt-*` → `career-*`) orphans any legacy `jhunt-*` instance data in an existing `alh_personal` database. The migration is defined declaratively as **GLAV mapping rules** in `mapping/rules/` (same framework and rule format as the dismech mapping in skillful-alhazen — `source_match` fetch → `target_insert`, with foreign keys resolved through the `career-legacy-id` natural key recorded on every migrated copy). See `mapping/README.md` for the rule catalog.

```bash
# Convenience wrapper (delegates to the bundled runner):
uv run python .claude/skills/career/career.py migrate-from-jobhunt --dry-run
uv run python .claude/skills/career/career.py migrate-from-jobhunt

# Or run the rules directly (schema_mapper-compatible CLI):
uv run python .claude/skills/career/mapping/glav_runner.py run \
    --source-db alh_personal --target-db alh_personal \
    --rules-dir .claude/skills/career/mapping/rules --dry-run
```

- Prerequisite: the career schema (including `career-legacy-id`) is loaded into the database — the SessionStart hook does this.
- Phase 1-3 rules copy entities (companies, opportunities, skills, concepts, sources, candidates, resources, requirements, artifacts, notes, the seeker role → `career-agent-role`) with fresh skolem ids + `career-legacy-id`. Phase 4 rules rebuild relations (company links, pipeline, requirements, skill hierarchy, forager links, aboutness, artifact representation) between the copies by matching legacy ids.
- Idempotent: reruns skip rows whose `career-legacy-id` already exists in the target (`target_check`).
- If no legacy types exist (fresh install), every rule reports a clean no-op.
- Legacy data is left in place — verify the `career-*` copies (compare counts per type against the rule report), then clean up manually. Tags on legacy entities are not copied.

---

## 17. Schema Gap Recognition

During sensemaking, if you encounter a concept, relationship, or entity type that has no place in the current TypeDB schema, that is a **schema gap** -- a signal for schema evolution, not a failure.

When you notice a schema gap:
1. Complete as much as possible with the current schema (partial knowledge > none)
2. Immediately file a gap issue:

```bash
uv run python local_resources/skilllog/skill_logger.py file-schema-gap \
  --skill career \
  --concept "<the concept you tried to represent>" \
  --missing "<which TypeDB entity/relation/attribute is absent>" \
  --suggested "<proposed TypeQL addition, or 'unknown' if unsure>"
```

**Examples of schema gaps:**
- A job posting mentions a work arrangement type that isn't in the schema
- A person has a relationship type not covered by `career-collab-role` (collaborator/mentor/sponsor/reference/co-author) or `career-contact-role`
- An opportunity has a compensation structure (e.g., revenue share) not covered by existing attributes

Use `--dry-run` first to review the issue before filing it.
