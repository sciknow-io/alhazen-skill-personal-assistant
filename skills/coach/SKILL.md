---
name: coach
description: Personal health & fitness monitoring — ingest HealthKit metrics, track goals, surface regressions, manage appointments
triggers: health metrics, fitness tracking, heartbeat cycle, sleep analysis, workout history, health goals, appointment prep
read_strategy:
  ingest: "USAGE.md § Ingestion"
  analysis: "USAGE.md § Heartbeat Protocol"
  dashboard: "USAGE.md § Dashboard"
---

# Health Coach Notebook Skill

Autonomous health monitoring agent that ingests Apple HealthKit exports (via Health Auto Export iOS app), computes daily metric aggregates in TypeDB, tracks goals and appointments, and surfaces actionable recommendations when metrics regress.

**When to use:** "ingest health data", "how am I doing", "run heartbeat", "show my trends", "add a health goal", "upcoming appointments", "sleep analysis", "track workout"

## Prerequisites

- TypeDB running with `alhazen_notebook` database
- Health Auto Export iOS app exporting daily JSON to Google Drive
- `uv run --project <skill-dir> python coach.py <command>`

## Quick Start

```bash
# Ingest a daily export
coach.py ingest-daily --file path/to/2026-05-05.json

# Show latest metrics
coach.py latest

# Compute trends
coach.py trends

# Sleep analysis
coach.py sleep-summary --days 7

# Set up profile with baselines
coach.py set-profile --name "Gully" --baseline-rhr 58 --sleep-target 7.5 --step-goal 10000
```

**Before executing commands, read USAGE.md for the complete reference.**
