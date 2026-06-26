# Health Coach Skill — Full Usage Reference

## Overview

The Health Coach skill implements an autonomous health monitoring pipeline following the Alhazen curation pattern. It ingests Apple HealthKit data exported via the "Health Auto Export" iOS app (daily JSON files on Google Drive), aggregates metrics into TypeDB for relational reasoning, and runs periodic heartbeat cycles to surface regressions and recommendations.

**Architecture:** Hybrid storage — TypeDB holds daily aggregates + the semantic layer (goals, recommendations, appointments, trends, providers). Raw time-series at sub-day granularity is handled by the ingest pipeline during aggregation.

---

## Data Model

### Entity Types

| Entity | Base | Purpose |
|--------|------|---------|
| `coach-health-seeker` | `alh-role` | User profile: baselines, timezone, goals |
| `coach-daily-metric` | `alh-domain-thing` | One record per metric-type per day |
| `coach-sleep-record` | `alh-domain-thing` | One record per night (stage breakdown) |
| `coach-workout` | `alh-domain-thing` | Formal workout session |
| `coach-appointment` | `alh-domain-thing` | Health appointment with prep tracking |
| `coach-provider` | `alh-domain-thing` | Healthcare provider with cadence |
| `coach-health-goal` | `alh-domain-thing` | Metric target (direction, period) |
| `coach-trend` | `alh-domain-thing` | Computed 7d/30d trend |
| `coach-pipeline-status` | `alh-domain-thing` | Ingest health tracker (singleton) |
| `coach-health-export` | `alh-artifact` | Raw JSON file record |
| `coach-recommendation-note` | `alh-note` | Actionable recommendation |
| `coach-heartbeat-note` | `alh-note` | Heartbeat cycle log |
| `coach-trend-note` | `alh-note` | Narrative trend analysis |

### Metric Aggregation

| Metric Category | Aggregation | Examples |
|-----------------|-------------|----------|
| Activity (SUM) | Daily total | step_count, active_energy, walking_running_distance |
| Cardiovascular (AVG) | Daily average | heart_rate, heart_rate_variability, blood_oxygen_saturation |
| Sleep | Per-night record | sleep_analysis (deep, core, REM, awake hours) |
| Workouts | Per-session | From full ZIP exports only |

---

## Curation Phase Mapping

| Phase | Implementation |
|-------|---------------|
| **Foraging** | Poll Google Drive `HealthExports/` folder for new JSON files since last ingest |
| **Ingestion** | `ingest-daily`: Parse JSON, aggregate hourly readings to daily, upsert into TypeDB |
| **Sensemaking** | Claude reads trend output, applies run detection heuristics, classifies anomalies |
| **Analysis** | Heartbeat cycle: compute deltas vs. baselines, generate 0-3 recommendations |
| **Reporting** | Weekly brief (Sunday), dashboard rendering, on-demand queries |

---

## Commands

### Pipeline / Ingestion

```bash
# Ingest a daily export JSON file
coach.py ingest-daily --file /path/to/2026-05-05.json

# Show pipeline health (last ingest, staleness)
coach.py pipeline-status
```

**Daily JSON format** (from Health Auto Export iOS app):
```json
{
  "data": {
    "metrics": [
      {
        "name": "step_count",
        "units": "count",
        "data": [
          {"date": "2026-05-05 08:00:00 -0700", "qty": 1234, "source": "Apple Watch"}
        ]
      }
    ]
  }
}
```

**Ingest behavior:**
- Hourly readings are aggregated to daily summaries (SUM for activity, AVG for vitals)
- `sleep_analysis` metric is extracted into `coach-sleep-record` entities
- Duplicate dates are skipped (idempotent re-ingest)
- Pipeline status singleton is updated after each ingest

### Queries

```bash
# Latest reading for each metric (or filter to one)
coach.py latest
coach.py latest --metric heart_rate

# Compute 7d/30d trend deltas for key metrics
coach.py trends

# Sleep breakdown for last N nights
coach.py sleep-summary --days 7

# Recent workouts
coach.py workout-history --limit 10

# One metric over time
coach.py show-metric --type step_count --days 30
```

### Goals

```bash
# Add a goal
coach.py add-goal --name "10K steps daily" --metric step_count --target 10000 --direction above --period daily

# List goals
coach.py list-goals
coach.py list-goals --status active

# Update goal
coach.py update-goal --id coach-goal-xxx --status achieved
coach.py update-goal --id coach-goal-xxx --target 12000
```

### Appointments

```bash
# Add appointment
coach.py add-appointment --name "Annual Physical" --type physical --date 2026-06-15 --provider "Dr. Smith" --prep "Fast 12h before, bring lab results"

# List upcoming
coach.py list-appointments

# Update status
coach.py update-appointment --id coach-appt-xxx --status completed
```

### Providers

```bash
# Add provider with visit cadence
coach.py add-provider --name "Dr. Smith" --type "PCP" --cadence 12
coach.py add-provider --name "Dr. Lee" --type "dentist" --cadence 6

# List providers
coach.py list-providers
```

### Recommendations

```bash
# Create a recommendation (auto-expires in 7 days)
coach.py add-recommendation --name "Increase step count" --content "Your 7d average dropped below 8K. Try a 20-min walk after lunch." --priority high

# List active recommendations
coach.py list-recommendations

# Mark done or dismiss
coach.py update-recommendation --id coach-rec-xxx --status done
```

### Profile

```bash
# Set up health-seeker profile
coach.py set-profile --name "Gully" --timezone "America/Los_Angeles" --birth-year 1975 --baseline-rhr 58 --baseline-hrv 42 --sleep-target 7.5 --step-goal 10000

# Show profile with active goals
coach.py show-profile
```

---

## Heartbeat Protocol

The heartbeat cycle runs every ~12 hours (or on-demand via Claude). It is the skill's "analysis" phase — the autonomous decision-making loop.

### Task Sequence

1. **Check pipeline health**
   - When was last ingest? If >7 days: flag as BROKEN
   - Are there new files on Drive since last ingest?

2. **Ingest new data** (if available)
   ```bash
   coach.py ingest-daily --file <new-file>
   ```

3. **Compute trends**
   ```bash
   coach.py trends
   ```

4. **Load profile + goals**
   ```bash
   coach.py show-profile
   ```

5. **Generate recommendations** (0-3 per cycle)
   Apply escalation rules (see below). Create recommendation notes for any triggers.

6. **Check appointments**
   ```bash
   coach.py list-appointments
   ```
   Flag any appointment within 7 days that lacks prep notes.

7. **Log heartbeat**
   Create a `coach-heartbeat-note` recording what was checked and any actions taken.

### Escalation Rules

| Trigger | Threshold | Action |
|---------|-----------|--------|
| RHR regression | +5 bpm over 7d avg vs. baseline | Recommend: "RHR elevated — check stress, sleep, hydration" |
| Weight spike | +3 lbs in 7 days | Recommend: check diet, hydration, scale consistency |
| Sleep deficit | <6h avg over 7 nights | Recommend: earlier bedtime, reduce screen time |
| Step decline | <50% of goal for 7d avg | Recommend: specific walk suggestion |
| HRV crash | -20% vs. 30d baseline | Recommend: recovery day, check illness |
| Pipeline stale | No new data for >7 days | Alert: "HealthKit pipeline broken — check Health Auto Export" |
| Appointment proximity | Within 7 days, no prep | Recommend: add prep notes |
| Overdue cadence | Provider cadence exceeded | Recommend: "Schedule [type] appointment" |

### Posting Rules (Silent on Green)

- **DO post:** When a trigger fires (metric regression, appointment proximity, pipeline broken)
- **DO post:** Sunday weekly brief (always)
- **DO NOT post:** When all metrics are stable and within goals
- **Format:** Numbers + one action. No cheerleading, no verbose summaries.

---

## Run Detection Heuristics

A day is a **confirmed run** if 3+ of these fire:
- Single-hour step_count > 5,000
- apple_exercise_time SUM > 30 min
- active_energy SUM > 400 kcal
- heart_rate MAX > 110 bpm in any hour
- physical_effort MAX > 4.5 in any hour
- walking_running_distance SUM > 2.5 mi

**Probable walk** if:
- Max HR < 110 bpm
- Max steps/hr < 4,000
- Distance spread across many hours

---

## Sensemaking Workflow

When Claude analyzes health data:

1. **Load profile** (call FIRST — never ask the user for baselines)
   ```bash
   coach.py show-profile
   ```

2. **Get current trends**
   ```bash
   coach.py trends
   ```

3. **Identify anomalies:**
   - Any metric regressing vs. 7d or 30d average?
   - Any metric outside goal range?
   - Sleep quality declining?
   - Activity dropping?

4. **Cross-reference:**
   - Did a workout yesterday explain elevated RHR today?
   - Is travel (from calendar) explaining step decline?
   - Is a pattern forming over multiple days?

5. **Generate recommendations** (max 3):
   - Be specific ("walk 20 min after lunch" not "exercise more")
   - Include the number that triggered it
   - Set appropriate priority

6. **Report to user** (only if something actionable)

---

## Weekly Brief Template

Generated every Sunday. Structure:

```
## Weekly Health Brief (YYYY-MM-DD)

### Key Metrics (7-day avg)
- RHR: XX bpm (delta vs. baseline)
- HRV: XX ms (delta)
- Steps: XX,XXX/day (vs. goal)
- Sleep: X.Xh/night (vs. target)
- Active Energy: XXX kcal/day

### Highlights
- [Notable workout or achievement]
- [Positive trend]

### Concerns
- [Any regression or missed goal]

### This Week
- [Upcoming appointments]
- [Recommendations]
```

---

## Known Gotchas

1. **MIME type:** Health Auto Export files are `text/json`, not `application/json`
2. **Step counts:** Stored hourly — must SUM for daily total (handled by ingest)
3. **Sleep location:** Lives in `metrics[]` as `sleep_analysis`, NOT in `data.sleep[]` (always empty)
4. **Workouts:** NOT in daily JSON — only in full ZIP exports
5. **Sleep dates:** Date = morning the sleep ends, not when sleep started
6. **HRV outliers:** Single readings can spike to 150+ ms — daily AVG smooths this
7. **Non-breaking space:** Apple Watch source name contains `\xa0` (non-breaking space) — normalized on ingest

---

## Dashboard

### Overview Page (`/coach`)
- Metric cards (RHR, HRV, Sleep, Steps, Weight) with sparkline + trend arrow
- Active goals with progress bars
- Pipeline health indicator (green/yellow/red)
- Upcoming appointments (next 7 days)
- Active recommendations (0-3)

### Trends Page (`/coach/trends`)
- Line charts per metric (7d/30d/90d toggles)
- Goal overlay lines
- Trend direction badges

### Sleep Page (`/coach/sleep`)
- Stacked bar chart (deep/core/REM/awake)
- Rolling 7-day average line
- Sleep regularity indicator

### Workouts Page (`/coach/workouts`)
- Calendar heatmap (days with workouts)
- Per-workout cards (type, duration, HR, distance)
- Weekly volume summary

### Appointments Page (`/coach/appointments`)
- Timeline (upcoming + recent)
- Provider list with cadence status
- Overdue alerts
