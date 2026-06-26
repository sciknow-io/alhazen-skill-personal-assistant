#!/usr/bin/env python3
"""
Health Coach Notebook CLI - Personal health & fitness monitoring skill.

This script handles INGESTION and QUERIES. Claude handles SENSEMAKING via the SKILL.md.

Usage:
    python coach.py <command> [options]

Commands:
    # Pipeline / Ingestion
    ingest-daily        Parse a daily Health Auto Export JSON into TypeDB
    pipeline-status     Show last export/ingest dates, record counts, staleness

    # Queries
    latest              Latest reading for each tracked metric
    trends              7d/30d deltas for key metrics
    sleep-summary       Sleep breakdown for last N nights
    workout-history     Recent workouts with stats
    show-metric         One metric type over time

    # Goals
    add-goal            Define a health goal (metric, target, direction, period)
    list-goals          Show active goals with progress
    update-goal         Update goal status or target

    # Appointments
    add-appointment     Track a health appointment
    list-appointments   Show upcoming appointments
    update-appointment  Change status or add prep notes

    # Providers
    add-provider        Add a healthcare provider
    list-providers      Show providers with cadence info

    # Recommendations
    add-recommendation  Create an actionable recommendation
    list-recommendations Show active recommendations
    update-recommendation Change status (done/dismissed)

    # Profile
    set-profile         Create or update health-seeker profile
    show-profile        Display profile with baselines and goals

    # Utility
    tag                 Tag any entity
    search-tag          Search by tag

Environment:
    TYPEDB_HOST       TypeDB server host (default: localhost)
    TYPEDB_PORT       TypeDB server port (default: 1729)
    TYPEDB_DATABASE   Database name (default: alhazen_notebook)
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import uuid
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    from typedb.driver import Credentials, DriverOptions, TransactionType, TypeDB

    TYPEDB_AVAILABLE = True
except ImportError:
    TYPEDB_AVAILABLE = False
    print(
        "Warning: typedb-driver not installed. Install with: pip install 'typedb-driver>=3.8.0'",
        file=sys.stderr,
    )

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

TYPEDB_HOST = os.getenv("TYPEDB_HOST", "localhost")
TYPEDB_PORT = int(os.getenv("TYPEDB_PORT", "1729"))
TYPEDB_DATABASE = os.getenv("TYPEDB_DATABASE", "alh_personal")
TYPEDB_USERNAME = os.getenv("TYPEDB_USERNAME", "admin")
TYPEDB_PASSWORD = os.getenv("TYPEDB_PASSWORD", "password")

# Metrics that use SUM aggregation (hourly readings -> daily total)
SUM_METRICS = {
    "step_count", "active_energy", "basal_energy_burned",
    "apple_exercise_time", "apple_stand_time", "apple_stand_hour",
    "walking_running_distance", "flights_climbed",
}

# Metrics that use AVG aggregation (multiple readings -> daily average)
AVG_METRICS = {
    "heart_rate", "heart_rate_variability", "blood_oxygen_saturation",
    "respiratory_rate", "walking_speed", "walking_step_length",
    "walking_double_support_percentage", "physical_effort",
    "environmental_audio_exposure",
}

# Key metrics for dashboard display
KEY_METRICS = [
    "heart_rate", "heart_rate_variability", "step_count",
    "active_energy", "walking_running_distance",
    "blood_oxygen_saturation", "respiratory_rate",
    "apple_exercise_time",
]


# ---------------------------------------------------------------------------
# Cache utilities (inlined — no external package needed)
# ---------------------------------------------------------------------------

_CACHE_THRESHOLD = 50 * 1024  # 50KB

_MIME_TYPE_MAP = {
    "application/json": ("json", "json"),
    "text/json": ("json", "json"),
    "text/csv": ("text", "csv"),
    "application/zip": ("json", "zip"),
    "application/pdf": ("pdf", "pdf"),
    "text/plain": ("text", "txt"),
}


def get_cache_dir():
    cache_env = os.getenv("ALHAZEN_CACHE_DIR")
    cache_dir = Path(cache_env).expanduser() if cache_env else Path.home() / ".alhazen" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def save_to_cache(artifact_id, content, mime_type):
    if isinstance(content, str):
        content_bytes = content.encode("utf-8")
    else:
        content_bytes = content
    type_dir, ext = _MIME_TYPE_MAP.get(mime_type, ("other", "bin"))
    cache_dir = get_cache_dir()
    type_path = cache_dir / type_dir
    type_path.mkdir(parents=True, exist_ok=True)
    filename = f"{artifact_id}.{ext}"
    full_path = type_path / filename
    full_path.write_bytes(content_bytes)
    return {
        "cache_path": f"{type_dir}/{filename}",
        "file_size": len(content_bytes),
        "content_hash": hashlib.sha256(content_bytes).hexdigest(),
        "full_path": str(full_path),
    }


def _create_export_artifact(driver, file_path, mime_type):
    """Create a coach-health-export artifact in the cache and TypeDB. Returns artifact_id."""
    content = file_path.read_bytes()
    artifact_id = generate_id("coach-export")
    cache_result = save_to_cache(artifact_id, content, mime_type)
    now = get_timestamp()

    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(
            f'insert $a isa coach-health-export'
            f', has id "{artifact_id}"'
            f', has name "HealthKit Export {escape_string(file_path.name)}"'
            f', has source-uri "{escape_string(file_path.name)}"'
            f', has cache-path "{cache_result["cache_path"]}"'
            f', has mime-type "{escape_string(mime_type)}"'
            f', has file-size {cache_result["file_size"]}'
            f', has content-hash "{cache_result["content_hash"]}"'
            f', has created-at {now};'
        ).resolve()
        tx.commit()

    return artifact_id, cache_result


def _link_entities_to_artifact(driver, artifact_id, entity_ids):
    """Batch-link ingested entities to their source artifact via alh-representation."""
    for eid in entity_ids:
        try:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(
                    f'match $a isa coach-health-export, has id "{artifact_id}";'
                    f' $e isa alh-domain-thing, has id "{escape_string(eid)}";'
                    f' insert (alh-artifact: $a, referent: $e) isa alh-representation;'
                ).resolve()
                tx.commit()
        except Exception:
            pass  # skip if already linked or entity not found


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def get_driver():
    """Get TypeDB driver connection."""
    return TypeDB.driver(
        f"{TYPEDB_HOST}:{TYPEDB_PORT}",
        Credentials(TYPEDB_USERNAME, TYPEDB_PASSWORD),
        DriverOptions(is_tls_enabled=False),
    )


def generate_id(prefix: str) -> str:
    """Generate a unique ID with prefix."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def escape_string(s: str) -> str:
    """Escape special characters for TypeQL."""
    if s is None:
        return ""
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )


def get_timestamp() -> str:
    """Get current timestamp in TypeDB datetime format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def parse_date(date_str: str) -> str:
    """Parse various date formats into TypeDB datetime format."""
    # Handle 'YYYY-MM-DD HH:MM:SS -TZTZ' format from HealthKit
    if " -" in date_str or " +" in date_str:
        # Strip timezone offset for TypeDB (store as UTC-naive)
        parts = date_str.rsplit(" ", 1)
        date_str = parts[0]
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            dt = datetime.fromisoformat(date_str.replace("T", " "))
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def extract_date_only(date_str: str) -> str:
    """Extract just the date portion as YYYY-MM-DDT00:00:00."""
    parsed = parse_date(date_str)
    return parsed[:10] + "T00:00:00"


def output_json(data):
    """Print JSON to stdout."""
    print(json.dumps(data, indent=2, default=str))


# ---------------------------------------------------------------------------
# INGEST COMMANDS
# ---------------------------------------------------------------------------

def cmd_ingest_daily(args):
    """Parse a daily Health Auto Export JSON file into TypeDB daily metrics."""
    file_path = Path(args.file)
    if not file_path.exists():
        output_json({"success": False, "error": f"File not found: {file_path}"})
        return

    with open(file_path) as f:
        data = json.load(f)

    metrics_data = data.get("data", {}).get("metrics", [])
    if not metrics_data:
        output_json({"success": False, "error": "No metrics found in file"})
        return

    driver = get_driver()
    inserted = 0
    skipped = 0
    sleep_inserted = 0
    all_entity_ids = []  # collect for provenance linking

    # Create source artifact
    artifact_id, cache_result = _create_export_artifact(driver, file_path, "application/json")

    try:
        for metric_block in metrics_data:
            metric_name = metric_block.get("name", "")
            units = metric_block.get("units", "")
            readings = metric_block.get("data", [])

            if not readings:
                continue

            # Handle sleep_analysis separately
            if metric_name == "sleep_analysis":
                for reading in readings:
                    date_val = extract_date_only(reading.get("date", ""))
                    sleep_id = f"coach-sleep-{date_val[:10]}"

                    total_sleep = reading.get("totalSleep") or reading.get("total_sleep_hrs")
                    deep = reading.get("deep") or reading.get("deep_hrs")
                    core = reading.get("core") or reading.get("core_hrs")
                    rem = reading.get("rem") or reading.get("rem_hrs")
                    awake = reading.get("awake") or reading.get("awake_hrs")
                    in_bed = reading.get("inBed") or reading.get("in_bed_hrs")
                    asleep = reading.get("asleep") or reading.get("asleep_hrs")

                    query_parts = [
                        f'insert $s isa coach-sleep-record, has id "{sleep_id}"',
                        f', has name "Sleep {date_val[:10]}"',
                        f', has coach-date {date_val}',
                    ]
                    if total_sleep is not None:
                        query_parts.append(f", has coach-asleep-hrs {float(total_sleep)}")
                    if deep is not None:
                        query_parts.append(f", has coach-deep-hrs {float(deep)}")
                    if core is not None:
                        query_parts.append(f", has coach-core-hrs {float(core)}")
                    if rem is not None:
                        query_parts.append(f", has coach-rem-hrs {float(rem)}")
                    if awake is not None:
                        query_parts.append(f", has coach-awake-hrs {float(awake)}")
                    if in_bed is not None:
                        query_parts.append(f", has coach-in-bed-hrs {float(in_bed)}")
                    if asleep is not None:
                        query_parts.append(f", has coach-asleep-hrs {float(asleep)}")
                    query_parts.append(f', has coach-source "Health Auto Export"')
                    query_parts.append(";")

                    query = "".join(query_parts)

                    try:
                        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                            tx.query(query).resolve()
                            tx.commit()
                        sleep_inserted += 1
                        all_entity_ids.append(sleep_id)
                    except Exception:
                        skipped += 1
                continue

            # Aggregate hourly readings into daily summary
            daily_data = {}
            for reading in readings:
                date_key = extract_date_only(reading.get("date", ""))[:10]
                qty = reading.get("qty")
                if qty is None:
                    continue
                qty = float(qty)

                if date_key not in daily_data:
                    daily_data[date_key] = {"values": [], "source": reading.get("source", "")}
                daily_data[date_key]["values"].append(qty)

            for date_key, day_info in daily_data.items():
                values = day_info["values"]
                source = escape_string(day_info["source"].replace("\xa0", " "))
                date_val = f"{date_key}T00:00:00"
                metric_id = f"coach-metric-{metric_name}-{date_key}"

                # Compute aggregates based on metric type
                if metric_name in SUM_METRICS:
                    primary_value = sum(values)
                else:
                    primary_value = sum(values) / len(values)

                min_val = min(values)
                max_val = max(values)
                avg_val = sum(values) / len(values)

                query = (
                    f'insert $m isa coach-daily-metric'
                    f', has id "{metric_id}"'
                    f', has name "{escape_string(metric_name)} {date_key}"'
                    f', has coach-metric-type "{escape_string(metric_name)}"'
                    f', has coach-date {date_val}'
                    f', has coach-value {primary_value}'
                    f', has coach-min-value {min_val}'
                    f', has coach-max-value {max_val}'
                    f', has coach-avg-value {avg_val}'
                    f', has coach-units "{escape_string(units)}"'
                    f', has coach-source "{source}";'
                )

                try:
                    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                        tx.query(query).resolve()
                        tx.commit()
                    inserted += 1
                    all_entity_ids.append(metric_id)
                except Exception:
                    skipped += 1

        # Ingest workouts (present in full JSON exports, not daily)
        workouts_data = data.get("data", {}).get("workouts", [])
        workouts_inserted = 0
        for w in workouts_data:
            w_name = w.get("name", "Workout")
            w_start = w.get("start", "")
            if not w_start:
                continue
            w_date = parse_date(w_start)
            w_date_key = w_date[:10]
            w_duration = w.get("duration")  # seconds
            duration_min = round(w_duration / 60, 1) if w_duration else None

            # Extract summary fields
            active_e = w.get("activeEnergyBurned", {}).get("qty")
            distance_km = w.get("distance", {}).get("qty")
            distance_mi = round(distance_km * 0.621371, 2) if distance_km else None
            avg_hr_val = w.get("heartRate", {}).get("avg", {}).get("qty") or w.get("avgHeartRate", {}).get("qty")
            max_hr_val = w.get("heartRate", {}).get("max", {}).get("qty") or w.get("maxHeartRate", {}).get("qty")
            step_count_val = None
            sc_list = w.get("stepCount", [])
            if isinstance(sc_list, list) and sc_list:
                step_count_val = int(sum(s.get("qty", 0) for s in sc_list))

            wid = f"coach-workout-{w_name.lower().replace(' ', '-')}-{w_start[:10].replace('-', '')}"
            wquery = (
                f'insert $w isa coach-workout'
                f', has id "{escape_string(wid)}"'
                f', has name "{escape_string(w_name)} {w_date_key}"'
                f', has coach-workout-type "{escape_string(w_name)}"'
                f', has coach-date {w_date}'
            )
            if duration_min is not None:
                wquery += f", has coach-duration-min {duration_min}"
            if active_e is not None:
                wquery += f", has coach-active-energy-kcal {round(active_e, 1)}"
            if distance_mi is not None:
                wquery += f", has coach-distance-mi {distance_mi}"
            if avg_hr_val is not None:
                wquery += f", has coach-avg-hr {round(float(avg_hr_val), 1)}"
            if max_hr_val is not None:
                wquery += f", has coach-max-hr {round(float(max_hr_val), 1)}"
            if step_count_val is not None:
                wquery += f", has coach-step-count {step_count_val}"
            wquery += f', has coach-source "Health Auto Export";'

            try:
                with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                    tx.query(wquery).resolve()
                    tx.commit()
                workouts_inserted += 1
                all_entity_ids.append(wid)
            except Exception:
                skipped += 1

        # Link all ingested entities to the source artifact
        _link_entities_to_artifact(driver, artifact_id, all_entity_ids)

        # Update pipeline status
        _update_pipeline_status(driver, inserted + sleep_inserted + workouts_inserted)

    finally:
        driver.close()

    output_json({
        "success": True,
        "file": str(file_path),
        "artifact_id": artifact_id,
        "cache_path": cache_result["cache_path"],
        "metrics_inserted": inserted,
        "sleep_inserted": sleep_inserted,
        "workouts_inserted": workouts_inserted,
        "skipped_duplicates": skipped,
    })


def _update_pipeline_status(driver, records_count):
    """Update the singleton pipeline status entity."""
    now = get_timestamp()
    status_id = "coach-pipeline-status-singleton"

    # Try to delete existing, then insert fresh
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(
                f'match $p isa coach-pipeline-status, has id "{status_id}"; delete $p;'
            ).resolve()
            tx.commit()
    except Exception:
        pass

    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
        tx.query(
            f'insert $p isa coach-pipeline-status'
            f', has id "{status_id}"'
            f', has name "Pipeline Status"'
            f', has coach-last-ingest-date {now}'
            f', has coach-records-count {records_count}'
            f', has coach-pipeline-health "healthy";'
        ).resolve()
        tx.commit()


# ---------------------------------------------------------------------------
# CSV / ZIP INGEST
# ---------------------------------------------------------------------------

# Map CSV column names → (metric_name, units)
# Only columns we care about — skip nutrition, obscure metrics, etc.
CSV_METRIC_MAP = {
    "Active Energy (kcal)":                    ("active_energy", "kcal"),
    "Apple Exercise Time (min)":               ("apple_exercise_time", "min"),
    "Apple Sleeping Wrist Temperature (degF)": ("apple_sleeping_wrist_temperature", "degF"),
    "Apple Stand Hour (count)":                ("apple_stand_hour", "count"),
    "Apple Stand Time (min)":                  ("apple_stand_time", "min"),
    "Blood Oxygen Saturation (%)":             ("blood_oxygen_saturation", "%"),
    "Environmental Audio Exposure (dBASPL)":   ("environmental_audio_exposure", "dBASPL"),
    "Flights Climbed (count)":                 ("flights_climbed", "count"),
    "Headphone Audio Exposure (dBASPL)":       ("headphone_audio_exposure", "dBASPL"),
    "Heart Rate [Min] (count/min)":            ("heart_rate_min", "bpm"),
    "Heart Rate [Max] (count/min)":            ("heart_rate_max", "bpm"),
    "Heart Rate [Avg] (count/min)":            ("heart_rate", "bpm"),
    "Heart Rate Variability (ms)":             ("heart_rate_variability", "ms"),
    "Mindful Minutes (min)":                   ("mindful_minutes", "min"),
    "Physical Effort (kcal/hr·kg)":            ("physical_effort", "kcal/hr*kg"),
    "Respiratory Rate (count/min)":            ("respiratory_rate", "breaths/min"),
    "Resting Energy (kcal)":                   ("basal_energy_burned", "kcal"),
    "Resting Heart Rate (count/min)":          ("resting_heart_rate", "bpm"),
    "Six-Minute Walking Test Distance (m)":    ("six_minute_walking_test_distance", "m"),
    "Stair Speed: Down (ft/s)":                ("stair_speed_down", "ft/s"),
    "Stair Speed: Up (ft/s)":                  ("stair_speed_up", "ft/s"),
    "Step Count (count)":                      ("step_count", "count"),
    "Time in Daylight (min)":                  ("time_in_daylight", "min"),
    "VO2 Max (ml/(kg·min))":                   ("vo2_max", "ml/kg/min"),
    "Walking + Running Distance (mi)":         ("walking_running_distance", "mi"),
    "Walking Asymmetry Percentage (%)":        ("walking_asymmetry_percentage", "%"),
    "Walking Double Support Percentage (%)":   ("walking_double_support_percentage", "%"),
    "Walking Heart Rate Average (count/min)":  ("walking_heart_rate_average", "bpm"),
    "Walking Speed (mi/hr)":                   ("walking_speed", "mi/hr"),
    "Walking Step Length (in)":                ("walking_step_length", "in"),
    "Weight (lb)":                             ("weight_body_mass", "lb"),
    # Sleep columns
    "Sleep Analysis [Asleep] (hr)":            ("_sleep_asleep", "hr"),
    "Sleep Analysis [In Bed] (hr)":            ("_sleep_in_bed", "hr"),
    "Sleep Analysis [Core] (hr)":              ("_sleep_core", "hr"),
    "Sleep Analysis [Deep] (hr)":              ("_sleep_deep", "hr"),
    "Sleep Analysis [REM] (hr)":               ("_sleep_rem", "hr"),
    "Sleep Analysis [Awake] (hr)":             ("_sleep_awake", "hr"),
    "Sleep Analysis [Total] (hr)":             ("_sleep_total", "hr"),
}


def cmd_ingest_csv(args):
    """Ingest a Health Auto Export CSV (daily summary rows) into TypeDB."""
    file_path = Path(args.file)
    if not file_path.exists():
        output_json({"success": False, "error": f"File not found: {file_path}"})
        return

    driver = get_driver()
    inserted = 0
    skipped = 0
    sleep_inserted = 0
    all_entity_ids = []

    # Create source artifact
    artifact_id, cache_result = _create_export_artifact(driver, file_path, "text/csv")

    try:
        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                date_str = row.get("Date/Time", "").strip()
                if not date_str:
                    continue
                date_key = date_str[:10]  # YYYY-MM-DD
                date_val = f"{date_key}T00:00:00"

                # Extract sleep data
                sleep_data = {}
                metric_data = {}

                for col_name, (metric_name, units) in CSV_METRIC_MAP.items():
                    raw = row.get(col_name, "").strip()
                    if not raw:
                        continue
                    try:
                        val = float(raw)
                    except ValueError:
                        continue

                    if metric_name.startswith("_sleep_"):
                        sleep_data[metric_name] = val
                    else:
                        metric_data[metric_name] = (val, units)

                # Insert metrics
                for metric_name, (val, units) in metric_data.items():
                    metric_id = f"coach-metric-{metric_name}-{date_key}"
                    query = (
                        f'insert $m isa coach-daily-metric'
                        f', has id "{metric_id}"'
                        f', has name "{escape_string(metric_name)} {date_key}"'
                        f', has coach-metric-type "{escape_string(metric_name)}"'
                        f', has coach-date {date_val}'
                        f', has coach-value {val}'
                        f', has coach-avg-value {val}'
                        f', has coach-min-value {val}'
                        f', has coach-max-value {val}'
                        f', has coach-units "{escape_string(units)}"'
                        f', has coach-source "Health Auto Export CSV";'
                    )
                    try:
                        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                            tx.query(query).resolve()
                            tx.commit()
                        inserted += 1
                        all_entity_ids.append(metric_id)
                    except Exception:
                        skipped += 1

                # Insert sleep record
                if sleep_data:
                    sleep_id = f"coach-sleep-{date_key}"
                    parts = [
                        f'insert $s isa coach-sleep-record, has id "{sleep_id}"',
                        f', has name "Sleep {date_key}"',
                        f', has coach-date {date_val}',
                    ]
                    if "_sleep_asleep" in sleep_data:
                        parts.append(f", has coach-asleep-hrs {sleep_data['_sleep_asleep']}")
                    if "_sleep_in_bed" in sleep_data:
                        parts.append(f", has coach-in-bed-hrs {sleep_data['_sleep_in_bed']}")
                    if "_sleep_core" in sleep_data:
                        parts.append(f", has coach-core-hrs {sleep_data['_sleep_core']}")
                    if "_sleep_deep" in sleep_data:
                        parts.append(f", has coach-deep-hrs {sleep_data['_sleep_deep']}")
                    if "_sleep_rem" in sleep_data:
                        parts.append(f", has coach-rem-hrs {sleep_data['_sleep_rem']}")
                    if "_sleep_awake" in sleep_data:
                        parts.append(f", has coach-awake-hrs {sleep_data['_sleep_awake']}")
                    parts.append(f', has coach-source "Health Auto Export CSV";')

                    try:
                        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                            tx.query("".join(parts)).resolve()
                            tx.commit()
                        sleep_inserted += 1
                        all_entity_ids.append(sleep_id)
                    except Exception:
                        skipped += 1

        # Link all ingested entities to source artifact
        _link_entities_to_artifact(driver, artifact_id, all_entity_ids)

        _update_pipeline_status(driver, inserted + sleep_inserted)

    finally:
        driver.close()

    output_json({
        "success": True,
        "file": str(file_path),
        "artifact_id": artifact_id,
        "cache_path": cache_result["cache_path"],
        "metrics_inserted": inserted,
        "sleep_inserted": sleep_inserted,
        "skipped_duplicates": skipped,
    })


def cmd_ingest_workouts(args):
    """Ingest a Health Auto Export workouts CSV into TypeDB."""
    file_path = Path(args.file)
    if not file_path.exists():
        output_json({"success": False, "error": f"File not found: {file_path}"})
        return

    driver = get_driver()
    inserted = 0
    skipped = 0
    all_entity_ids = []

    # Create source artifact
    artifact_id, cache_result = _create_export_artifact(driver, file_path, "text/csv")

    try:
        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                workout_type = row.get("Workout Type", "").strip()
                start = row.get("Start", "").strip()
                if not start or not workout_type:
                    continue

                date_key = start[:10]
                date_val = parse_date(start)
                # Generate deterministic ID from type + start time
                wid = f"coach-workout-{workout_type.lower().replace(' ', '-')}-{start.replace(' ', '-').replace(':', '')}"

                duration_str = row.get("Duration", "")
                duration_min = None
                if duration_str:
                    # Parse HH:MM:SS
                    parts = duration_str.split(":")
                    if len(parts) == 3:
                        duration_min = int(parts[0]) * 60 + int(parts[1]) + int(parts[2]) / 60

                def safe_float(key):
                    v = row.get(key, "").strip()
                    if not v:
                        return None
                    try:
                        return float(v)
                    except ValueError:
                        return None

                active_energy = safe_float("Active Energy (kcal)")
                max_hr = safe_float("Max. Heart Rate (count/min)")
                avg_hr = safe_float("Avg. Heart Rate (count/min)")
                distance_km = safe_float("Distance (km)")
                distance_mi = distance_km * 0.621371 if distance_km else None
                step_count = safe_float("Step Count")

                query = (
                    f'insert $w isa coach-workout'
                    f', has id "{escape_string(wid)}"'
                    f', has name "{escape_string(workout_type)} {date_key}"'
                    f', has coach-workout-type "{escape_string(workout_type)}"'
                    f', has coach-date {date_val}'
                )
                if duration_min is not None:
                    query += f", has coach-duration-min {round(duration_min, 1)}"
                if active_energy is not None:
                    query += f", has coach-active-energy-kcal {round(active_energy, 1)}"
                if distance_mi is not None:
                    query += f", has coach-distance-mi {round(distance_mi, 2)}"
                if avg_hr is not None:
                    query += f", has coach-avg-hr {round(avg_hr, 1)}"
                if max_hr is not None:
                    query += f", has coach-max-hr {round(max_hr, 1)}"
                if step_count is not None:
                    query += f", has coach-step-count {int(step_count)}"
                query += f', has coach-source "Health Auto Export CSV";'

                try:
                    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                        tx.query(query).resolve()
                        tx.commit()
                    inserted += 1
                    all_entity_ids.append(wid)
                except Exception:
                    skipped += 1

        # Link all ingested entities to source artifact
        _link_entities_to_artifact(driver, artifact_id, all_entity_ids)

    finally:
        driver.close()

    output_json({
        "success": True,
        "file": str(file_path),
        "artifact_id": artifact_id,
        "cache_path": cache_result["cache_path"],
        "workouts_inserted": inserted,
        "skipped_duplicates": skipped,
    })


def cmd_ingest_zip(args):
    """Ingest a full Health Auto Export ZIP (metrics CSV + workouts CSV)."""
    zip_path = Path(args.file)
    if not zip_path.exists():
        output_json({"success": False, "error": f"File not found: {zip_path}"})
        return

    import tempfile
    tmpdir = Path(tempfile.mkdtemp(prefix="coach-ingest-"))

    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tmpdir)

        # Find the main metrics CSV and workouts CSV
        metrics_csv = None
        workouts_csv = None
        for f in tmpdir.iterdir():
            name = f.name
            if name.startswith("HealthAutoExport-") and name.endswith(".csv"):
                metrics_csv = f
            elif name.startswith("Workouts-") and name.endswith(".csv"):
                workouts_csv = f

        results = {}

        if metrics_csv:
            # Temporarily set args.file for reuse
            args.file = str(metrics_csv)
            # Capture stdout
            import io
            old_stdout = sys.stdout
            sys.stdout = buf = io.StringIO()
            cmd_ingest_csv(args)
            sys.stdout = old_stdout
            results["metrics"] = json.loads(buf.getvalue())
        else:
            results["metrics"] = {"success": False, "error": "No HealthAutoExport-*.csv found in ZIP"}

        if workouts_csv:
            args.file = str(workouts_csv)
            old_stdout = sys.stdout
            sys.stdout = buf = io.StringIO()
            cmd_ingest_workouts(args)
            sys.stdout = old_stdout
            results["workouts"] = json.loads(buf.getvalue())
        else:
            results["workouts"] = {"success": False, "error": "No Workouts-*.csv found in ZIP"}

        output_json({
            "success": True,
            "zip": str(zip_path),
            "metrics": results["metrics"],
            "workouts": results["workouts"],
        })

    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# LAB PDF INGEST
# ---------------------------------------------------------------------------

def cmd_ingest_lab_pdf(args):
    """Ingest a lab report PDF: cache as artifact, create bare panel for Claude sensemaking."""
    file_path = Path(args.file)
    if not file_path.exists():
        output_json({"success": False, "error": f"File not found: {file_path}"})
        return

    driver = get_driver()
    try:
        # Cache the PDF as artifact
        artifact_id, cache_result = _create_export_artifact(driver, file_path, "application/pdf")

        # Create bare lab panel entity (Claude fills in results during sensemaking)
        panel_id = generate_id("coach-lab-panel")
        panel_date = args.date or get_timestamp()[:10]
        date_val = f"{panel_date}T00:00:00"
        now = get_timestamp()

        panel_query = (
            f'insert $p isa coach-lab-panel'
            f', has id "{panel_id}"'
            f', has name "Lab Panel {panel_date}"'
            f', has coach-date {date_val}'
            f', has created-at {now}'
        )
        if args.provider:
            panel_query += f', has coach-lab-provider "{escape_string(args.provider)}"'
        if args.physician:
            panel_query += f', has coach-lab-physician "{escape_string(args.physician)}"'
        panel_query += f', has coach-source "Lab PDF";'

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(panel_query).resolve()
            tx.commit()

        # Link panel to artifact
        _link_entities_to_artifact(driver, artifact_id, [panel_id])

    finally:
        driver.close()

    output_json({
        "success": True,
        "file": str(file_path),
        "artifact_id": artifact_id,
        "cache_path": cache_result["cache_path"],
        "panel_id": panel_id,
        "panel_date": panel_date,
        "message": f"PDF cached. Run sensemaking: read the PDF at ~/.alhazen/cache/{cache_result['cache_path']} and use add-lab-result to create structured results.",
    })


def cmd_add_lab_result(args):
    """Add a single lab result to a panel (called by Claude during sensemaking)."""
    driver = get_driver()
    try:
        result_id = generate_id("coach-lab-result")
        now = get_timestamp()

        rquery = (
            f'insert $r isa coach-lab-result'
            f', has id "{result_id}"'
            f', has name "{escape_string(args.test)}"'
            f', has coach-lab-test-name "{escape_string(args.test)}"'
        )
        if args.value is not None:
            rquery += f', has coach-lab-value {float(args.value)}'
        if args.value_text:
            rquery += f', has coach-lab-value-text "{escape_string(args.value_text)}"'
        if args.flag:
            rquery += f', has coach-lab-flag "{escape_string(args.flag)}"'
        if args.units:
            rquery += f', has coach-units "{escape_string(args.units)}"'
        if args.reference_range:
            rquery += f', has coach-lab-reference-range "{escape_string(args.reference_range)}"'
        if args.panel_name:
            rquery += f', has coach-lab-panel-name "{escape_string(args.panel_name)}"'
        rquery += f', has created-at {now};'

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(rquery).resolve()
            tx.commit()

        # Link result to panel
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(
                f'match $p isa coach-lab-panel, has id "{escape_string(args.panel_id)}";'
                f' $r isa coach-lab-result, has id "{result_id}";'
                f' insert (panel: $p, lab-result: $r) isa coach-lab-result-in-panel;'
            ).resolve()
            tx.commit()

        output_json({"success": True, "id": result_id, "test": args.test, "panel_id": args.panel_id})
    finally:
        driver.close()


def cmd_list_labs(args):
    """List all lab panels."""
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            panels = list(tx.query(
                'match $p isa coach-lab-panel;'
                ' fetch {'
                ' "id": $p.id,'
                ' "name": $p.name,'
                ' "date": $p.coach-date,'
                ' "provider": $p.coach-lab-provider,'
                ' "physician": $p.coach-lab-physician'
                ' };'
            ).resolve())

        # Count results and flags per panel
        for panel in panels:
            pid = panel["id"]
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                results = list(tx.query(
                    f'match $r isa coach-lab-result;'
                    f' (panel: $p, lab-result: $r) isa coach-lab-result-in-panel;'
                    f' $p has id "{pid}";'
                    f' fetch {{ "flag": $r.coach-lab-flag }};'
                ).resolve())
            panel["result_count"] = len(results)
            panel["flagged_count"] = len([r for r in results if r.get("flag")])

        output_json({"success": True, "panels": panels, "count": len(panels)})
    finally:
        driver.close()


def cmd_show_lab(args):
    """Show full results for one lab panel."""
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Get panel
            panels = list(tx.query(
                f'match $p isa coach-lab-panel, has id "{escape_string(args.id)}";'
                f' fetch {{'
                f' "id": $p.id, "name": $p.name, "date": $p.coach-date,'
                f' "provider": $p.coach-lab-provider, "physician": $p.coach-lab-physician'
                f' }};'
            ).resolve())

            if not panels:
                output_json({"success": False, "error": f"Panel not found: {args.id}"})
                return

            # Get results
            results = list(tx.query(
                f'match $r isa coach-lab-result;'
                f' (panel: $p, lab-result: $r) isa coach-lab-result-in-panel;'
                f' $p has id "{escape_string(args.id)}";'
                f' fetch {{'
                f' "id": $r.id, "test": $r.coach-lab-test-name,'
                f' "value": $r.coach-lab-value, "value_text": $r.coach-lab-value-text,'
                f' "flag": $r.coach-lab-flag, "units": $r.coach-units,'
                f' "reference_range": $r.coach-lab-reference-range,'
                f' "panel_name": $r.coach-lab-panel-name'
                f' }};'
            ).resolve())

        output_json({
            "success": True,
            "panel": panels[0],
            "results": results,
            "count": len(results),
        })
    finally:
        driver.close()


def cmd_lab_trends(args):
    """Show historical values for a specific lab test across all panels."""
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                f'match $r isa coach-lab-result, has coach-lab-test-name "{escape_string(args.test)}";'
                f' (panel: $p, lab-result: $r) isa coach-lab-result-in-panel;'
                f' fetch {{'
                f' "date": $p.coach-date, "value": $r.coach-lab-value,'
                f' "flag": $r.coach-lab-flag, "reference_range": $r.coach-lab-reference-range'
                f' }};'
            ).resolve())

        sorted_results = sorted(results, key=lambda r: str(r.get("date", "")))
        output_json({
            "success": True,
            "test": args.test,
            "readings": sorted_results,
            "count": len(sorted_results),
        })
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# NUTRITION COMMANDS
# ---------------------------------------------------------------------------

def cmd_ingest_nutrition_csv(args):
    """Ingest a MyFitnessPal or Cronometer CSV export into TypeDB."""
    file_path = Path(args.file)
    if not file_path.exists():
        output_json({"success": False, "error": f"File not found: {file_path}"})
        return

    driver = get_driver()
    days_inserted = 0
    meals_inserted = 0
    skipped = 0
    all_entity_ids = []

    # Cache source as artifact
    mime = "text/csv"
    artifact_id, cache_result = _create_export_artifact(driver, file_path, mime)

    try:
        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []

            # Detect format: MFP has "Meal" column, Cronometer has "Food Name" at top level
            is_mfp = "Meal" in fieldnames and "Food Name" in fieldnames
            is_cronometer = "Food Name" in fieldnames and "Energy (kcal)" in fieldnames

            # Aggregate by date
            daily_totals = {}  # date -> {calories, protein, carbs, fat, ...}
            meals = []  # individual meal entries

            for row in reader:
                date_str = (row.get("Date") or row.get("Day") or "").strip()
                if not date_str:
                    continue
                # Normalize date
                date_key = date_str[:10]

                # Parse macros (handle both MFP and Cronometer column names)
                def get_float(keys):
                    for k in keys:
                        v = row.get(k, "").strip()
                        if v:
                            try:
                                return float(v.replace(",", ""))
                            except ValueError:
                                pass
                    return None

                cal = get_float(["Calories", "Energy (kcal)", "Dietary Energy (kcal)"])
                protein = get_float(["Protein (g)", "Protein"])
                carbs = get_float(["Carbohydrates (g)", "Carbs (g)", "Total Carbs (g)"])
                fat = get_float(["Fat (g)", "Total Fat (g)"])
                fiber = get_float(["Fiber (g)", "Fiber"])
                sugar = get_float(["Sugar (g)", "Sugars (g)", "Sugar"])
                sodium = get_float(["Sodium (mg)", "Sodium"])
                water = get_float(["Water (fl_oz_us)", "Water (mL)"])

                # Accumulate daily totals
                if date_key not in daily_totals:
                    daily_totals[date_key] = {
                        "calories": 0, "protein": 0, "carbs": 0, "fat": 0,
                        "fiber": 0, "sugar": 0, "sodium": 0, "water": 0,
                    }
                dt = daily_totals[date_key]
                if cal: dt["calories"] += cal
                if protein: dt["protein"] += protein
                if carbs: dt["carbs"] += carbs
                if fat: dt["fat"] += fat
                if fiber: dt["fiber"] += fiber
                if sugar: dt["sugar"] += sugar
                if sodium: dt["sodium"] += sodium
                if water: dt["water"] += water

                # Store individual meal if MFP format
                meal_type = (row.get("Meal") or "").strip().lower()
                food_name = (row.get("Food Name") or "").strip()
                if meal_type and food_name and cal:
                    meals.append({
                        "date": date_key, "meal_type": meal_type,
                        "food_name": food_name,
                        "serving_size": (row.get("Servings") or row.get("Amount") or "").strip(),
                        "calories": cal, "protein": protein, "carbs": carbs, "fat": fat,
                    })

            # Insert daily summaries
            for date_key, dt in daily_totals.items():
                day_id = f"coach-nutrition-{date_key}"
                date_val = f"{date_key}T00:00:00"
                query = (
                    f'insert $d isa coach-nutrition-day'
                    f', has id "{day_id}"'
                    f', has name "Nutrition {date_key}"'
                    f', has coach-date {date_val}'
                    f', has coach-calories {round(dt["calories"], 1)}'
                    f', has coach-protein-g {round(dt["protein"], 1)}'
                    f', has coach-carbs-g {round(dt["carbs"], 1)}'
                    f', has coach-fat-g {round(dt["fat"], 1)}'
                )
                if dt["fiber"]: query += f', has coach-fiber-g {round(dt["fiber"], 1)}'
                if dt["sugar"]: query += f', has coach-sugar-g {round(dt["sugar"], 1)}'
                if dt["sodium"]: query += f', has coach-sodium-mg {round(dt["sodium"], 1)}'
                if dt["water"]: query += f', has coach-water-oz {round(dt["water"], 1)}'
                query += f', has coach-source "Nutrition CSV";'

                try:
                    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                        tx.query(query).resolve()
                        tx.commit()
                    days_inserted += 1
                    all_entity_ids.append(day_id)
                except Exception:
                    skipped += 1

            # Insert individual meals and link to day
            for m in meals:
                meal_id = generate_id("coach-meal")
                date_val = f"{m['date']}T00:00:00"
                mquery = (
                    f'insert $m isa coach-meal'
                    f', has id "{meal_id}"'
                    f', has name "{escape_string(m["food_name"][:80])}"'
                    f', has coach-date {date_val}'
                    f', has coach-meal-type "{escape_string(m["meal_type"])}"'
                    f', has coach-food-name "{escape_string(m["food_name"])}"'
                )
                if m.get("serving_size"):
                    mquery += f', has coach-serving-size "{escape_string(m["serving_size"])}"'
                if m["calories"]:
                    mquery += f', has coach-calories {round(m["calories"], 1)}'
                if m.get("protein"):
                    mquery += f', has coach-protein-g {round(m["protein"], 1)}'
                if m.get("carbs"):
                    mquery += f', has coach-carbs-g {round(m["carbs"], 1)}'
                if m.get("fat"):
                    mquery += f', has coach-fat-g {round(m["fat"], 1)}'
                mquery += f', has coach-source "Nutrition CSV";'

                try:
                    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                        tx.query(mquery).resolve()
                        tx.commit()
                    meals_inserted += 1
                    all_entity_ids.append(meal_id)

                    # Link meal to day
                    day_id = f"coach-nutrition-{m['date']}"
                    with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                        tx.query(
                            f'match $d isa coach-nutrition-day, has id "{day_id}";'
                            f' $m isa coach-meal, has id "{meal_id}";'
                            f' insert (nutrition-day: $d, meal: $m) isa coach-meal-in-day;'
                        ).resolve()
                        tx.commit()
                except Exception:
                    skipped += 1

        _link_entities_to_artifact(driver, artifact_id, all_entity_ids)

    finally:
        driver.close()

    output_json({
        "success": True,
        "file": str(file_path),
        "artifact_id": artifact_id,
        "cache_path": cache_result["cache_path"],
        "days_inserted": days_inserted,
        "meals_inserted": meals_inserted,
        "skipped_duplicates": skipped,
    })


def cmd_add_meal(args):
    """Add a single meal entry (Claude sensemaking)."""
    driver = get_driver()
    try:
        meal_id = generate_id("coach-meal")
        date_val = f"{args.date}T00:00:00" if args.date else get_timestamp()
        now = get_timestamp()

        query = (
            f'insert $m isa coach-meal'
            f', has id "{meal_id}"'
            f', has name "{escape_string(args.food[:80])}"'
            f', has coach-date {date_val}'
            f', has coach-meal-type "{escape_string(args.type)}"'
            f', has coach-food-name "{escape_string(args.food)}"'
            f', has created-at {now}'
        )
        if args.calories: query += f', has coach-calories {float(args.calories)}'
        if args.protein: query += f', has coach-protein-g {float(args.protein)}'
        if args.carbs: query += f', has coach-carbs-g {float(args.carbs)}'
        if args.fat: query += f', has coach-fat-g {float(args.fat)}'
        query += f', has coach-source "manual";'

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        output_json({"success": True, "id": meal_id, "food": args.food})
    finally:
        driver.close()


def cmd_add_nutrition_day(args):
    """Add a daily nutrition summary manually."""
    driver = get_driver()
    try:
        day_id = f"coach-nutrition-{args.date}"
        date_val = f"{args.date}T00:00:00"
        now = get_timestamp()

        query = (
            f'insert $d isa coach-nutrition-day'
            f', has id "{day_id}"'
            f', has name "Nutrition {args.date}"'
            f', has coach-date {date_val}'
            f', has coach-calories {float(args.calories)}'
            f', has created-at {now}'
        )
        if args.protein: query += f', has coach-protein-g {float(args.protein)}'
        if args.carbs: query += f', has coach-carbs-g {float(args.carbs)}'
        if args.fat: query += f', has coach-fat-g {float(args.fat)}'
        if args.fiber: query += f', has coach-fiber-g {float(args.fiber)}'
        query += f', has coach-source "manual";'

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        output_json({"success": True, "id": day_id, "date": args.date})
    finally:
        driver.close()


def cmd_nutrition_summary(args):
    """Daily calorie/macro summary for last N days."""
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                'match $d isa coach-nutrition-day;'
                ' fetch {'
                ' "id": $d.id, "date": $d.coach-date,'
                ' "calories": $d.coach-calories,'
                ' "protein": $d.coach-protein-g,'
                ' "carbs": $d.coach-carbs-g,'
                ' "fat": $d.coach-fat-g,'
                ' "fiber": $d.coach-fiber-g,'
                ' "sugar": $d.coach-sugar-g'
                ' };'
            ).resolve())

        sorted_results = sorted(results, key=lambda r: str(r.get("date", "")), reverse=True)
        days = args.days or 7
        recent = sorted_results[:days]

        # Compute averages
        if recent:
            avg_cal = sum(float(r.get("calories") or 0) for r in recent) / len(recent)
            avg_protein = sum(float(r.get("protein") or 0) for r in recent) / len(recent)
            avg_carbs = sum(float(r.get("carbs") or 0) for r in recent) / len(recent)
            avg_fat = sum(float(r.get("fat") or 0) for r in recent) / len(recent)
        else:
            avg_cal = avg_protein = avg_carbs = avg_fat = 0

        output_json({
            "success": True,
            "days": recent,
            "count": len(recent),
            "averages": {
                "calories": round(avg_cal, 0),
                "protein_g": round(avg_protein, 1),
                "carbs_g": round(avg_carbs, 1),
                "fat_g": round(avg_fat, 1),
            },
        })
    finally:
        driver.close()


def cmd_show_nutrition(args):
    """Show one day's nutrition with meals."""
    driver = get_driver()
    try:
        date_val = f"{args.date}T00:00:00"
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            # Day summary
            days = list(tx.query(
                f'match $d isa coach-nutrition-day, has coach-date {date_val};'
                f' fetch {{'
                f' "id": $d.id, "calories": $d.coach-calories,'
                f' "protein": $d.coach-protein-g, "carbs": $d.coach-carbs-g,'
                f' "fat": $d.coach-fat-g, "fiber": $d.coach-fiber-g'
                f' }};'
            ).resolve())

            # Meals for that day
            meals = list(tx.query(
                f'match $m isa coach-meal, has coach-date {date_val};'
                f' fetch {{'
                f' "id": $m.id, "food": $m.coach-food-name,'
                f' "meal_type": $m.coach-meal-type,'
                f' "calories": $m.coach-calories,'
                f' "protein": $m.coach-protein-g,'
                f' "carbs": $m.coach-carbs-g,'
                f' "fat": $m.coach-fat-g'
                f' }};'
            ).resolve())

        output_json({
            "success": True,
            "date": args.date,
            "summary": days[0] if days else None,
            "meals": meals,
            "meal_count": len(meals),
        })
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# ASSESSMENT COMMANDS
# ---------------------------------------------------------------------------

def cmd_gather_assessment_data(args):
    """Gather all current health data for Claude to write an assessment.

    Returns structured JSON with profile, latest metrics, trends, sleep,
    recent workouts, lab results, goals, and active recommendations.
    Claude reads this and writes a narrative assessment via save-assessment.
    """
    driver = get_driver()
    try:
        data = {}

        # Profile
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            profiles = list(tx.query(
                'match $p isa coach-health-seeker;'
                ' fetch { "name": $p.name, "timezone": $p.coach-timezone,'
                ' "baseline_rhr": $p.coach-baseline-rhr, "baseline_hrv": $p.coach-baseline-hrv,'
                ' "sleep_target": $p.coach-sleep-target-hrs, "step_goal": $p.coach-step-goal,'
                ' "weight_goal": $p.coach-weight-goal,'
                ' "calorie_goal": $p.coach-calorie-goal, "protein_goal": $p.coach-protein-goal-g,'
                ' "carbs_goal": $p.coach-carbs-goal-g, "fat_goal": $p.coach-fat-goal-g };'
            ).resolve())
        data["profile"] = profiles[0] if profiles else None

        # Goals
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            goals = list(tx.query(
                'match $g isa coach-health-goal;'
                ' fetch { "name": $g.name, "metric": $g.coach-goal-metric,'
                ' "target": $g.coach-goal-target, "direction": $g.coach-goal-direction,'
                ' "status": $g.coach-goal-status };'
            ).resolve())
        data["goals"] = goals

        # Latest metrics (all)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            metrics = list(tx.query(
                'match $m isa coach-daily-metric;'
                ' fetch { "type": $m.coach-metric-type, "date": $m.coach-date,'
                ' "value": $m.coach-value, "units": $m.coach-units };'
            ).resolve())
        # Keep only latest per metric type
        by_type = {}
        for m in metrics:
            mt = m.get("type")
            if mt not in by_type or str(m.get("date", "")) > str(by_type[mt].get("date", "")):
                by_type[mt] = m
        data["latest_metrics"] = list(by_type.values())

        # Sleep (last 7 nights)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            sleep = list(tx.query(
                'match $s isa coach-sleep-record;'
                ' fetch { "date": $s.coach-date, "asleep_hrs": $s.coach-asleep-hrs,'
                ' "deep_hrs": $s.coach-deep-hrs, "rem_hrs": $s.coach-rem-hrs,'
                ' "awake_hrs": $s.coach-awake-hrs };'
            ).resolve())
        sleep_sorted = sorted(sleep, key=lambda r: str(r.get("date", "")), reverse=True)[:7]
        data["recent_sleep"] = sleep_sorted

        # Recent workouts (last 5)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            workouts = list(tx.query(
                'match $w isa coach-workout;'
                ' fetch { "type": $w.coach-workout-type, "date": $w.coach-date,'
                ' "duration_min": $w.coach-duration-min, "avg_hr": $w.coach-avg-hr };'
            ).resolve())
        workouts_sorted = sorted(workouts, key=lambda r: str(r.get("date", "")), reverse=True)[:5]
        data["recent_workouts"] = workouts_sorted

        # Lab results (most recent panel)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            panels = list(tx.query(
                'match $p isa coach-lab-panel;'
                ' fetch { "id": $p.id, "date": $p.coach-date, "provider": $p.coach-lab-provider };'
            ).resolve())
        if panels:
            latest_panel = sorted(panels, key=lambda p: str(p.get("date", "")), reverse=True)[0]
            pid = latest_panel["id"]
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                lab_results = list(tx.query(
                    f'match $r isa coach-lab-result;'
                    f' (panel: $p, lab-result: $r) isa coach-lab-result-in-panel;'
                    f' $p has id "{pid}";'
                    f' fetch {{ "test": $r.coach-lab-test-name, "value": $r.coach-lab-value,'
                    f' "flag": $r.coach-lab-flag, "units": $r.coach-units,'
                    f' "reference_range": $r.coach-lab-reference-range }};'
                ).resolve())
            data["lab_panel"] = {
                "date": latest_panel.get("date"),
                "provider": latest_panel.get("provider"),
                "results": lab_results,
                "flagged": [r for r in lab_results if r.get("flag")],
            }
        else:
            data["lab_panel"] = None

        # Nutrition (last 7 days)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            nutrition = list(tx.query(
                'match $d isa coach-nutrition-day;'
                ' fetch { "date": $d.coach-date, "calories": $d.coach-calories,'
                ' "protein": $d.coach-protein-g, "carbs": $d.coach-carbs-g,'
                ' "fat": $d.coach-fat-g };'
            ).resolve())
        nutrition_sorted = sorted(nutrition, key=lambda r: str(r.get("date", "")), reverse=True)[:7]
        data["recent_nutrition"] = nutrition_sorted

        output_json({"success": True, "data": data})
    finally:
        driver.close()


def cmd_save_assessment(args):
    """Save a Claude-written health assessment."""
    driver = get_driver()
    try:
        assessment_id = generate_id("coach-assessment")
        date_val = f"{args.date}T00:00:00" if args.date else get_timestamp()
        now = get_timestamp()

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(
                f'insert $a isa coach-assessment-note'
                f', has id "{assessment_id}"'
                f', has name "Health Assessment {args.date or now[:10]}"'
                f', has content "{escape_string(args.content)}"'
                f', has coach-date {date_val}'
                f', has created-at {now};'
            ).resolve()
            tx.commit()

        output_json({"success": True, "id": assessment_id, "date": args.date or now[:10]})
    finally:
        driver.close()


def cmd_list_assessments(args):
    """List all health assessments."""
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                'match $a isa coach-assessment-note;'
                ' fetch { "id": $a.id, "name": $a.name, "date": $a.coach-date };'
            ).resolve())

        sorted_results = sorted(results, key=lambda r: str(r.get("date", "")), reverse=True)
        output_json({"success": True, "assessments": sorted_results, "count": len(sorted_results)})
    finally:
        driver.close()


def cmd_show_assessment(args):
    """Show one assessment's full content."""
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                f'match $a isa coach-assessment-note, has id "{escape_string(args.id)}";'
                f' fetch {{ "id": $a.id, "name": $a.name, "date": $a.coach-date,'
                f' "content": $a.content }};'
            ).resolve())

        if results:
            output_json({"success": True, "assessment": results[0]})
        else:
            output_json({"success": False, "error": f"Assessment not found: {args.id}"})
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# SUPPORT TEAM COMMANDS
# ---------------------------------------------------------------------------

def cmd_add_support_member(args):
    """Add a person to the health support team with a role."""
    driver = get_driver()
    try:
        now = get_timestamp()

        # Check if person already exists
        person_id = args.person_id
        if not person_id:
            # Create new person
            person_id = generate_id("person")
            pquery = (
                f'insert $p isa alh-person'
                f', has id "{person_id}"'
                f', has name "{escape_string(args.name)}"'
                f', has created-at {now}'
            )
            if args.email:
                pquery += f', has alh-email-address "{escape_string(args.email)}"'
            if args.phone:
                pquery += f', has alh-phone-number "{escape_string(args.phone)}"'
            if args.title:
                pquery += f', has alh-title "{escape_string(args.title)}"'
            pquery += ";"
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(pquery).resolve()
                tx.commit()

        # Create support role
        role_id = generate_id("coach-support-role")
        rquery = (
            f'insert $r isa coach-support-role'
            f', has id "{role_id}"'
            f', has name "{escape_string(args.role)} - {escape_string(args.name)}"'
            f', has coach-support-role-type "{escape_string(args.role)}"'
            f', has alh-role-status "active"'
            f', has created-at {now};'
        )
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(rquery).resolve()
            tx.commit()

        # Link role to person via alh-role-bearing
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(
                f'match $p isa alh-person, has id "{person_id}";'
                f' $r isa coach-support-role, has id "{role_id}";'
                f' insert (bearer: $p, borne-role: $r) isa alh-role-bearing;'
            ).resolve()
            tx.commit()

        # Link role to seeker via coach-support-team
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(
                f'match $s isa coach-health-seeker;'
                f' $r isa coach-support-role, has id "{role_id}";'
                f' insert (seeker: $s, support-role: $r) isa coach-support-team;'
            ).resolve()
            tx.commit()

        output_json({
            "success": True,
            "person_id": person_id,
            "role_id": role_id,
            "name": args.name,
            "role": args.role,
        })
    finally:
        driver.close()


def cmd_list_support_team(args):
    """List the health support team."""
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                'match $s isa coach-health-seeker;'
                ' (seeker: $s, support-role: $r) isa coach-support-team;'
                ' (bearer: $p, borne-role: $r) isa alh-role-bearing;'
                ' fetch {'
                ' "person_id": $p.id, "person_name": $p.name,'
                ' "title": $p.alh-title, "email": $p.alh-email-address,'
                ' "phone": $p.alh-phone-number,'
                ' "role_id": $r.id, "role_type": $r.coach-support-role-type,'
                ' "status": $r.alh-role-status };'
            ).resolve())

        output_json({"success": True, "team": results, "count": len(results)})
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# QUERY COMMANDS
# ---------------------------------------------------------------------------

def cmd_latest(args):
    """Show latest reading for each tracked metric (or a specific one)."""
    driver = get_driver()
    try:
        metric_filter = ""
        if args.metric:
            metric_filter = f', has coach-metric-type "{escape_string(args.metric)}"'

        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                f'match $m isa coach-daily-metric{metric_filter};'
                f' fetch {{'
                f' "type": $m.coach-metric-type,'
                f' "date": $m.coach-date,'
                f' "value": $m.coach-value,'
                f' "units": $m.coach-units'
                f' }};'
            ).resolve())

        # Group by metric type, keep latest date
        by_type = {}
        for r in results:
            mt = r.get("type")
            if mt not in by_type or str(r.get("date", "")) > str(by_type[mt].get("date", "")):
                by_type[mt] = r

        output_json({
            "success": True,
            "metrics": list(by_type.values()),
            "count": len(by_type),
        })
    finally:
        driver.close()


def cmd_trends(args):
    """Compute 7d/30d deltas for key metrics."""
    driver = get_driver()
    try:
        now = datetime.now(timezone.utc)
        date_7d = (now - timedelta(days=7)).strftime("%Y-%m-%dT00:00:00")
        date_30d = (now - timedelta(days=30)).strftime("%Y-%m-%dT00:00:00")

        trends = []
        for metric_type in KEY_METRICS:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
                results = list(tx.query(
                    f'match $m isa coach-daily-metric'
                    f', has coach-metric-type "{metric_type}"'
                    f', has coach-date $d'
                    f', has coach-value $v;'
                    f' fetch {{ "date": $d, "value": $v }};'
                ).resolve())

            if not results:
                continue

            # Sort by date
            sorted_results = sorted(results, key=lambda r: str(r.get("date", "")))
            if not sorted_results:
                continue

            latest = sorted_results[-1]
            latest_val = float(latest.get("value", 0))

            # Compute 7d average
            recent_7d = [
                float(r.get("value", 0)) for r in sorted_results
                if str(r.get("date", "")) >= date_7d
            ]
            avg_7d = sum(recent_7d) / len(recent_7d) if recent_7d else latest_val

            # Compute 30d average
            recent_30d = [
                float(r.get("value", 0)) for r in sorted_results
                if str(r.get("date", "")) >= date_30d
            ]
            avg_30d = sum(recent_30d) / len(recent_30d) if recent_30d else latest_val

            # Delta = latest - period_avg (positive = above average)
            delta_7d = latest_val - avg_7d
            delta_30d = latest_val - avg_30d

            # Direction
            if abs(delta_7d) < 0.01 * latest_val:
                direction = "stable"
            elif delta_7d > 0:
                direction = "improving" if metric_type in SUM_METRICS else "regressing"
            else:
                direction = "regressing" if metric_type in SUM_METRICS else "improving"

            trends.append({
                "metric_type": metric_type,
                "latest_value": latest_val,
                "latest_date": str(latest.get("date", "")),
                "avg_7d": round(avg_7d, 2),
                "avg_30d": round(avg_30d, 2),
                "delta_7d": round(delta_7d, 2),
                "delta_30d": round(delta_30d, 2),
                "direction": direction,
            })

        output_json({"success": True, "trends": trends, "count": len(trends)})
    finally:
        driver.close()


def cmd_sleep_summary(args):
    """Sleep analysis for last N nights."""
    driver = get_driver()
    days = args.days or 7
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                f'match $s isa coach-sleep-record;'
                f' fetch {{'
                f' "id": $s.id,'
                f' "date": $s.coach-date,'
                f' "asleep_hrs": $s.coach-asleep-hrs,'
                f' "deep_hrs": $s.coach-deep-hrs,'
                f' "core_hrs": $s.coach-core-hrs,'
                f' "rem_hrs": $s.coach-rem-hrs,'
                f' "awake_hrs": $s.coach-awake-hrs,'
                f' "in_bed_hrs": $s.coach-in-bed-hrs'
                f' }};'
            ).resolve())

        # Sort by date descending, take last N
        sorted_results = sorted(results, key=lambda r: str(r.get("date", "")), reverse=True)
        recent = sorted_results[:days]

        # Compute averages
        if recent:
            avg_sleep = sum(float(r.get("asleep_hrs") or 0) for r in recent) / len(recent)
            avg_deep = sum(float(r.get("deep_hrs") or 0) for r in recent) / len(recent)
            avg_rem = sum(float(r.get("rem_hrs") or 0) for r in recent) / len(recent)
        else:
            avg_sleep = avg_deep = avg_rem = 0

        output_json({
            "success": True,
            "nights": recent,
            "count": len(recent),
            "averages": {
                "sleep_hrs": round(avg_sleep, 2),
                "deep_hrs": round(avg_deep, 2),
                "rem_hrs": round(avg_rem, 2),
            },
        })
    finally:
        driver.close()


def cmd_workout_history(args):
    """List recent workouts."""
    driver = get_driver()
    limit = args.limit or 10
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                f'match $w isa coach-workout;'
                f' fetch {{'
                f' "id": $w.id,'
                f' "name": $w.name,'
                f' "type": $w.coach-workout-type,'
                f' "date": $w.coach-date,'
                f' "duration_min": $w.coach-duration-min,'
                f' "distance_mi": $w.coach-distance-mi,'
                f' "avg_hr": $w.coach-avg-hr,'
                f' "max_hr": $w.coach-max-hr,'
                f' "active_energy_kcal": $w.coach-active-energy-kcal'
                f' }};'
            ).resolve())

        sorted_results = sorted(results, key=lambda r: str(r.get("date", "")), reverse=True)
        output_json({
            "success": True,
            "workouts": sorted_results[:limit],
            "count": len(sorted_results),
        })
    finally:
        driver.close()


def cmd_show_metric(args):
    """Show one metric type over time."""
    driver = get_driver()
    days = args.days or 30
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00")

        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                f'match $m isa coach-daily-metric'
                f', has coach-metric-type "{escape_string(args.type)}"'
                f', has coach-date $d; $d >= {cutoff};'
                f' fetch {{'
                f' "date": $m.coach-date,'
                f' "value": $m.coach-value,'
                f' "min": $m.coach-min-value,'
                f' "max": $m.coach-max-value,'
                f' "avg": $m.coach-avg-value'
                f' }};'
            ).resolve())

        sorted_results = sorted(results, key=lambda r: str(r.get("date", "")))
        output_json({
            "success": True,
            "metric_type": args.type,
            "days": days,
            "readings": sorted_results,
            "count": len(sorted_results),
        })
    finally:
        driver.close()


def cmd_pipeline_status(args):
    """Show pipeline health."""
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                f'match $p isa coach-pipeline-status;'
                f' fetch {{'
                f' "last_ingest_date": $p.coach-last-ingest-date,'
                f' "records_count": $p.coach-records-count,'
                f' "health": $p.coach-pipeline-health'
                f' }};'
            ).resolve())

        if results:
            output_json({"success": True, "pipeline": results[0]})
        else:
            output_json({"success": True, "pipeline": None, "message": "No pipeline status recorded yet"})
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# GOAL COMMANDS
# ---------------------------------------------------------------------------

def cmd_add_goal(args):
    """Add a health goal."""
    driver = get_driver()
    goal_id = generate_id("coach-goal")
    now = get_timestamp()

    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(
                f'insert $g isa coach-health-goal'
                f', has id "{goal_id}"'
                f', has name "{escape_string(args.name)}"'
                f', has coach-goal-metric "{escape_string(args.metric)}"'
                f', has coach-goal-target {float(args.target)}'
                f', has coach-goal-direction "{escape_string(args.direction)}"'
                f', has coach-goal-period "{escape_string(args.period or "daily")}"'
                f', has coach-goal-status "active"'
                f', has created-at {now};'
            ).resolve()
            tx.commit()

        output_json({"success": True, "id": goal_id, "name": args.name})
    finally:
        driver.close()


def cmd_list_goals(args):
    """List active goals."""
    driver = get_driver()
    try:
        status_filter = ""
        if args.status:
            status_filter = f', has coach-goal-status "{escape_string(args.status)}"'

        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                f'match $g isa coach-health-goal{status_filter};'
                f' fetch {{'
                f' "id": $g.id,'
                f' "name": $g.name,'
                f' "metric": $g.coach-goal-metric,'
                f' "target": $g.coach-goal-target,'
                f' "direction": $g.coach-goal-direction,'
                f' "period": $g.coach-goal-period,'
                f' "status": $g.coach-goal-status'
                f' }};'
            ).resolve())

        output_json({"success": True, "goals": results, "count": len(results)})
    finally:
        driver.close()


def cmd_update_goal(args):
    """Update a goal's status or target."""
    driver = get_driver()
    try:
        updates = []
        if args.status:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(
                    f'match $g isa coach-health-goal, has id "{escape_string(args.id)}"'
                    f', has coach-goal-status $old;'
                    f' delete has $old of $g;'
                    f' insert $g has coach-goal-status "{escape_string(args.status)}";'
                ).resolve()
                tx.commit()
            updates.append("status")

        if args.target:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(
                    f'match $g isa coach-health-goal, has id "{escape_string(args.id)}"'
                    f', has coach-goal-target $old;'
                    f' delete has $old of $g;'
                    f' insert $g has coach-goal-target {float(args.target)};'
                ).resolve()
                tx.commit()
            updates.append("target")

        output_json({"success": True, "id": args.id, "updated": updates})
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# APPOINTMENT COMMANDS
# ---------------------------------------------------------------------------

def cmd_add_appointment(args):
    """Add a health appointment."""
    driver = get_driver()
    appt_id = generate_id("coach-appt")
    now = get_timestamp()

    try:
        appt_date = parse_date(args.date)
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            query = (
                f'insert $a isa coach-appointment'
                f', has id "{appt_id}"'
                f', has name "{escape_string(args.name)}"'
                f', has coach-appointment-type "{escape_string(args.type)}"'
                f', has coach-appointment-date {appt_date}'
                f', has coach-appointment-status "upcoming"'
                f', has created-at {now}'
            )
            if args.provider:
                query += f', has coach-provider-name "{escape_string(args.provider)}"'
            if args.prep:
                query += f', has coach-prep-action "{escape_string(args.prep)}"'
            query += ";"
            tx.query(query).resolve()
            tx.commit()

        output_json({"success": True, "id": appt_id, "name": args.name, "date": appt_date})
    finally:
        driver.close()


def cmd_list_appointments(args):
    """List upcoming appointments."""
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                f'match $a isa coach-appointment;'
                f' fetch {{'
                f' "id": $a.id,'
                f' "name": $a.name,'
                f' "type": $a.coach-appointment-type,'
                f' "date": $a.coach-appointment-date,'
                f' "status": $a.coach-appointment-status,'
                f' "provider": $a.coach-provider-name,'
                f' "prep": $a.coach-prep-action'
                f' }};'
            ).resolve())

        # Sort by date
        sorted_results = sorted(results, key=lambda r: str(r.get("date", "")))
        output_json({"success": True, "appointments": sorted_results, "count": len(sorted_results)})
    finally:
        driver.close()


def cmd_update_appointment(args):
    """Update appointment status or prep."""
    driver = get_driver()
    try:
        if args.status:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(
                    f'match $a isa coach-appointment, has id "{escape_string(args.id)}"'
                    f', has coach-appointment-status $old;'
                    f' delete has $old of $a;'
                    f' insert $a has coach-appointment-status "{escape_string(args.status)}";'
                ).resolve()
                tx.commit()

        if args.prep:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(
                    f'match $a isa coach-appointment, has id "{escape_string(args.id)}";'
                    f' insert $a has coach-prep-action "{escape_string(args.prep)}";'
                ).resolve()
                tx.commit()

        output_json({"success": True, "id": args.id})
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# PROVIDER COMMANDS
# ---------------------------------------------------------------------------

def cmd_add_provider(args):
    """Add a healthcare provider."""
    driver = get_driver()
    prov_id = generate_id("coach-provider")
    now = get_timestamp()

    try:
        query = (
            f'insert $p isa coach-provider'
            f', has id "{prov_id}"'
            f', has name "{escape_string(args.name)}"'
            f', has coach-appointment-type "{escape_string(args.type)}"'
            f', has created-at {now}'
        )
        if args.cadence:
            query += f", has coach-cadence-months {int(args.cadence)}"
        query += ";"

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        output_json({"success": True, "id": prov_id, "name": args.name})
    finally:
        driver.close()


def cmd_list_providers(args):
    """List providers."""
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                f'match $p isa coach-provider;'
                f' fetch {{'
                f' "id": $p.id,'
                f' "name": $p.name,'
                f' "type": $p.coach-appointment-type,'
                f' "cadence_months": $p.coach-cadence-months'
                f' }};'
            ).resolve())

        output_json({"success": True, "providers": results, "count": len(results)})
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# RECOMMENDATION COMMANDS
# ---------------------------------------------------------------------------

def cmd_add_recommendation(args):
    """Create a recommendation note."""
    driver = get_driver()
    rec_id = generate_id("coach-rec")
    now = get_timestamp()
    expires = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")

    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(
                f'insert $r isa coach-recommendation-note'
                f', has id "{rec_id}"'
                f', has name "{escape_string(args.name)}"'
                f', has content "{escape_string(args.content)}"'
                f', has coach-rec-status "new"'
                f', has coach-rec-priority "{escape_string(args.priority or "medium")}"'
                f', has coach-rec-expires-at {expires}'
                f', has created-at {now};'
            ).resolve()
            tx.commit()

        output_json({"success": True, "id": rec_id, "name": args.name, "expires_at": expires})
    finally:
        driver.close()


def cmd_list_recommendations(args):
    """List active recommendations."""
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                f'match $r isa coach-recommendation-note;'
                f' fetch {{'
                f' "id": $r.id,'
                f' "name": $r.name,'
                f' "content": $r.content,'
                f' "status": $r.coach-rec-status,'
                f' "priority": $r.coach-rec-priority,'
                f' "expires_at": $r.coach-rec-expires-at'
                f' }};'
            ).resolve())

        # Filter to active (not done/dismissed)
        active = [r for r in results if r.get("status") not in ("done", "dismissed")]
        output_json({"success": True, "recommendations": active, "count": len(active)})
    finally:
        driver.close()


def cmd_update_recommendation(args):
    """Update recommendation status."""
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(
                f'match $r isa coach-recommendation-note, has id "{escape_string(args.id)}"'
                f', has coach-rec-status $old;'
                f' delete has $old of $r;'
                f' insert $r has coach-rec-status "{escape_string(args.status)}";'
            ).resolve()
            tx.commit()

        output_json({"success": True, "id": args.id, "status": args.status})
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# PROFILE COMMANDS
# ---------------------------------------------------------------------------

def cmd_set_profile(args):
    """Create or update the health-seeker profile."""
    driver = get_driver()
    profile_id = "coach-seeker-profile"
    now = get_timestamp()

    try:
        # Delete existing profile if present
        try:
            with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
                tx.query(
                    f'match $p isa coach-health-seeker, has id "{profile_id}"; delete $p;'
                ).resolve()
                tx.commit()
        except Exception:
            pass

        # Build insert query
        query = (
            f'insert $p isa coach-health-seeker'
            f', has id "{profile_id}"'
            f', has name "{escape_string(args.name or "Health Seeker")}"'
            f', has created-at {now}'
        )
        if args.timezone:
            query += f', has coach-timezone "{escape_string(args.timezone)}"'
        if args.birth_year:
            query += f", has coach-birth-year {int(args.birth_year)}"
        if args.baseline_rhr:
            query += f", has coach-baseline-rhr {float(args.baseline_rhr)}"
        if args.baseline_hrv:
            query += f", has coach-baseline-hrv {float(args.baseline_hrv)}"
        if args.sleep_target:
            query += f", has coach-sleep-target-hrs {float(args.sleep_target)}"
        if args.step_goal:
            query += f", has coach-step-goal {int(args.step_goal)}"
        if args.weight_goal:
            query += f", has coach-weight-goal {float(args.weight_goal)}"
        query += ";"

        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(query).resolve()
            tx.commit()

        output_json({"success": True, "id": profile_id})
    finally:
        driver.close()


def cmd_show_profile(args):
    """Show the health-seeker profile."""
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                f'match $p isa coach-health-seeker;'
                f' fetch {{'
                f' "id": $p.id,'
                f' "name": $p.name,'
                f' "timezone": $p.coach-timezone,'
                f' "birth_year": $p.coach-birth-year,'
                f' "baseline_rhr": $p.coach-baseline-rhr,'
                f' "baseline_hrv": $p.coach-baseline-hrv,'
                f' "sleep_target_hrs": $p.coach-sleep-target-hrs,'
                f' "step_goal": $p.coach-step-goal,'
                f' "weight_goal": $p.coach-weight-goal'
                f' }};'
            ).resolve())

        # Also fetch goals
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            goals = list(tx.query(
                f'match $g isa coach-health-goal, has coach-goal-status "active";'
                f' fetch {{'
                f' "id": $g.id,'
                f' "name": $g.name,'
                f' "metric": $g.coach-goal-metric,'
                f' "target": $g.coach-goal-target,'
                f' "direction": $g.coach-goal-direction'
                f' }};'
            ).resolve())

        profile = results[0] if results else None
        output_json({
            "success": True,
            "profile": profile,
            "active_goals": goals,
        })
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# TAG COMMANDS
# ---------------------------------------------------------------------------

def cmd_tag(args):
    """Tag an entity."""
    driver = get_driver()
    tag_id = generate_id("tag")
    now = get_timestamp()

    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.WRITE) as tx:
            tx.query(
                f'match $e isa alh-identifiable-entity, has id "{escape_string(args.entity_id)}";'
                f' insert $t isa alh-tag, has id "{tag_id}", has name "{escape_string(args.tag)}"'
                f', has created-at {now};'
                f' (tagged-entity: $e, tag: $t) isa alh-tagging;'
            ).resolve()
            tx.commit()

        output_json({"success": True, "entity_id": args.entity_id, "tag": args.tag})
    finally:
        driver.close()


def cmd_search_tag(args):
    """Search entities by tag."""
    driver = get_driver()
    try:
        with driver.transaction(TYPEDB_DATABASE, TransactionType.READ) as tx:
            results = list(tx.query(
                f'match $t isa alh-tag, has name "{escape_string(args.tag)}";'
                f' (tagged-entity: $e, tag: $t) isa alh-tagging;'
                f' fetch {{ "id": $e.id, "name": $e.name }};'
            ).resolve())

        output_json({"success": True, "entities": results, "count": len(results)})
    finally:
        driver.close()


# ---------------------------------------------------------------------------
# ARGUMENT PARSER
# ---------------------------------------------------------------------------

def build_parser():
    parser = argparse.ArgumentParser(
        description="Health Coach Notebook CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    # ingest-daily
    p = sub.add_parser("ingest-daily", help="Parse daily JSON export into TypeDB")
    p.add_argument("--file", required=True, help="Path to daily export JSON file")

    # ingest-csv
    p = sub.add_parser("ingest-csv", help="Parse Health Auto Export CSV into TypeDB")
    p.add_argument("--file", required=True, help="Path to main metrics CSV file")

    # ingest-workouts
    p = sub.add_parser("ingest-workouts", help="Parse workouts CSV into TypeDB")
    p.add_argument("--file", required=True, help="Path to Workouts-*.csv file")

    # ingest-zip
    p = sub.add_parser("ingest-zip", help="Parse full Health Auto Export ZIP")
    p.add_argument("--file", required=True, help="Path to HealthAutoExport_*.zip file")

    # ingest-lab-pdf
    p = sub.add_parser("ingest-lab-pdf", help="Cache lab PDF and create panel for sensemaking")
    p.add_argument("--file", required=True, help="Path to lab report PDF")
    p.add_argument("--date", help="Collection date (YYYY-MM-DD), extracted from PDF if omitted")
    p.add_argument("--provider", help="Lab provider (e.g., LabCorp, Quest)")
    p.add_argument("--physician", help="Ordering physician name")

    # add-lab-result
    p = sub.add_parser("add-lab-result", help="Add a lab result to a panel (sensemaking)")
    p.add_argument("--panel-id", required=True, help="Panel ID to add result to")
    p.add_argument("--test", required=True, help="Test name (e.g., 'Hemoglobin A1c')")
    p.add_argument("--value", type=float, help="Numeric result value")
    p.add_argument("--value-text", help="Non-numeric result (e.g., 'Canceled')")
    p.add_argument("--flag", choices=["High", "Low", ""], default="", help="Flag")
    p.add_argument("--units", help="Units (e.g., mg/dL, %%)")
    p.add_argument("--reference-range", help="Reference range (e.g., '70-99', '>59')")
    p.add_argument("--panel-name", help="Panel group name (e.g., 'Lipid Panel')")

    # list-labs
    sub.add_parser("list-labs", help="List all lab panels")

    # show-lab
    p = sub.add_parser("show-lab", help="Show one lab panel's results")
    p.add_argument("--id", required=True, help="Lab panel ID")

    # lab-trends
    p = sub.add_parser("lab-trends", help="Historical values for a specific lab test")
    p.add_argument("--test", required=True, help="Test name (e.g., 'Hemoglobin A1c')")

    # ingest-nutrition-csv
    p = sub.add_parser("ingest-nutrition-csv", help="Parse MFP/Cronometer CSV into TypeDB")
    p.add_argument("--file", required=True, help="Path to nutrition CSV file")

    # add-meal
    p = sub.add_parser("add-meal", help="Add a meal entry (sensemaking)")
    p.add_argument("--date", help="Date (YYYY-MM-DD)")
    p.add_argument("--type", required=True, choices=["breakfast", "lunch", "dinner", "snack"], help="Meal type")
    p.add_argument("--food", required=True, help="Food description")
    p.add_argument("--calories", type=float, help="Calories")
    p.add_argument("--protein", type=float, help="Protein (g)")
    p.add_argument("--carbs", type=float, help="Carbs (g)")
    p.add_argument("--fat", type=float, help="Fat (g)")

    # add-nutrition-day
    p = sub.add_parser("add-nutrition-day", help="Add daily nutrition summary")
    p.add_argument("--date", required=True, help="Date (YYYY-MM-DD)")
    p.add_argument("--calories", required=True, type=float, help="Total calories")
    p.add_argument("--protein", type=float, help="Protein (g)")
    p.add_argument("--carbs", type=float, help="Carbs (g)")
    p.add_argument("--fat", type=float, help="Fat (g)")
    p.add_argument("--fiber", type=float, help="Fiber (g)")

    # nutrition-summary
    p = sub.add_parser("nutrition-summary", help="Daily nutrition summary for last N days")
    p.add_argument("--days", type=int, default=7, help="Number of days")

    # show-nutrition
    p = sub.add_parser("show-nutrition", help="One day's nutrition with meals")
    p.add_argument("--date", required=True, help="Date (YYYY-MM-DD)")

    # gather-assessment-data
    sub.add_parser("gather-assessment-data", help="Gather all data for Claude to write an assessment")

    # save-assessment
    p = sub.add_parser("save-assessment", help="Save a Claude-written health assessment")
    p.add_argument("--date", help="Assessment date (YYYY-MM-DD)")
    p.add_argument("--content", required=True, help="Assessment content (markdown)")

    # list-assessments
    sub.add_parser("list-assessments", help="List all assessments")

    # show-assessment
    p = sub.add_parser("show-assessment", help="Show one assessment")
    p.add_argument("--id", required=True, help="Assessment ID")

    # add-support-member
    p = sub.add_parser("add-support-member", help="Add a person to the support team")
    p.add_argument("--name", required=True, help="Person name")
    p.add_argument("--role", required=True, help="Role type (PCP, PT, dentist, coach, nutritionist, specialist)")
    p.add_argument("--person-id", help="Existing person ID (skip creating new person)")
    p.add_argument("--email", help="Email address")
    p.add_argument("--phone", help="Phone number")
    p.add_argument("--title", help="Professional title (e.g., MD, DPT, RD)")

    # list-support-team
    sub.add_parser("list-support-team", help="List the health support team")

    # pipeline-status
    sub.add_parser("pipeline-status", help="Show pipeline health")

    # latest
    p = sub.add_parser("latest", help="Latest reading for each metric")
    p.add_argument("--metric", help="Filter to one metric type")

    # trends
    sub.add_parser("trends", help="7d/30d deltas for key metrics")

    # sleep-summary
    p = sub.add_parser("sleep-summary", help="Sleep breakdown for last N nights")
    p.add_argument("--days", type=int, default=7, help="Number of nights (default: 7)")

    # workout-history
    p = sub.add_parser("workout-history", help="Recent workouts")
    p.add_argument("--limit", type=int, default=10, help="Max workouts to show")

    # show-metric
    p = sub.add_parser("show-metric", help="One metric over time")
    p.add_argument("--type", required=True, help="Metric type name")
    p.add_argument("--days", type=int, default=30, help="Number of days")

    # add-goal
    p = sub.add_parser("add-goal", help="Add a health goal")
    p.add_argument("--name", required=True, help="Goal name")
    p.add_argument("--metric", required=True, help="Target metric type")
    p.add_argument("--target", required=True, type=float, help="Target value")
    p.add_argument("--direction", required=True, choices=["above", "below", "between"], help="Goal direction")
    p.add_argument("--period", default="daily", choices=["daily", "weekly", "monthly"])

    # list-goals
    p = sub.add_parser("list-goals", help="List goals")
    p.add_argument("--status", help="Filter by status")

    # update-goal
    p = sub.add_parser("update-goal", help="Update a goal")
    p.add_argument("--id", required=True, help="Goal ID")
    p.add_argument("--status", help="New status")
    p.add_argument("--target", type=float, help="New target value")

    # add-appointment
    p = sub.add_parser("add-appointment", help="Add appointment")
    p.add_argument("--name", required=True, help="Appointment name")
    p.add_argument("--type", required=True, help="Type (dentist, physical, PT, etc.)")
    p.add_argument("--date", required=True, help="Appointment date (YYYY-MM-DD)")
    p.add_argument("--provider", help="Provider name")
    p.add_argument("--prep", help="Prep action")

    # list-appointments
    sub.add_parser("list-appointments", help="List appointments")

    # update-appointment
    p = sub.add_parser("update-appointment", help="Update appointment")
    p.add_argument("--id", required=True, help="Appointment ID")
    p.add_argument("--status", help="New status")
    p.add_argument("--prep", help="Add prep note")

    # add-provider
    p = sub.add_parser("add-provider", help="Add provider")
    p.add_argument("--name", required=True, help="Provider name")
    p.add_argument("--type", required=True, help="Type (dentist, PCP, PT, etc.)")
    p.add_argument("--cadence", type=int, help="Visit cadence in months")

    # list-providers
    sub.add_parser("list-providers", help="List providers")

    # add-recommendation
    p = sub.add_parser("add-recommendation", help="Create recommendation")
    p.add_argument("--name", required=True, help="Short title")
    p.add_argument("--content", required=True, help="Recommendation text")
    p.add_argument("--priority", choices=["high", "medium", "low"], default="medium")

    # list-recommendations
    sub.add_parser("list-recommendations", help="List active recommendations")

    # update-recommendation
    p = sub.add_parser("update-recommendation", help="Update recommendation")
    p.add_argument("--id", required=True, help="Recommendation ID")
    p.add_argument("--status", required=True, choices=["new", "in-progress", "done", "dismissed"])

    # set-profile
    p = sub.add_parser("set-profile", help="Set health-seeker profile")
    p.add_argument("--name", help="Display name")
    p.add_argument("--timezone", help="Primary timezone")
    p.add_argument("--birth-year", type=int, help="Birth year")
    p.add_argument("--baseline-rhr", type=float, help="Baseline resting heart rate")
    p.add_argument("--baseline-hrv", type=float, help="Baseline HRV (ms)")
    p.add_argument("--sleep-target", type=float, help="Sleep target (hours)")
    p.add_argument("--step-goal", type=int, help="Daily step goal")
    p.add_argument("--weight-goal", type=float, help="Target weight (lbs)")

    # show-profile
    sub.add_parser("show-profile", help="Show profile")

    # tag
    p = sub.add_parser("tag", help="Tag an entity")
    p.add_argument("--entity-id", required=True, help="Entity ID to tag")
    p.add_argument("--tag", required=True, help="Tag value")

    # search-tag
    p = sub.add_parser("search-tag", help="Search by tag")
    p.add_argument("--tag", required=True, help="Tag to search for")

    return parser


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if not TYPEDB_AVAILABLE:
        output_json({"success": False, "error": "typedb-driver not installed"})
        sys.exit(1)

    commands = {
        "ingest-daily": cmd_ingest_daily,
        "ingest-csv": cmd_ingest_csv,
        "ingest-workouts": cmd_ingest_workouts,
        "ingest-zip": cmd_ingest_zip,
        "ingest-lab-pdf": cmd_ingest_lab_pdf,
        "add-lab-result": cmd_add_lab_result,
        "list-labs": cmd_list_labs,
        "show-lab": cmd_show_lab,
        "lab-trends": cmd_lab_trends,
        "ingest-nutrition-csv": cmd_ingest_nutrition_csv,
        "add-meal": cmd_add_meal,
        "add-nutrition-day": cmd_add_nutrition_day,
        "nutrition-summary": cmd_nutrition_summary,
        "show-nutrition": cmd_show_nutrition,
        "gather-assessment-data": cmd_gather_assessment_data,
        "save-assessment": cmd_save_assessment,
        "list-assessments": cmd_list_assessments,
        "show-assessment": cmd_show_assessment,
        "add-support-member": cmd_add_support_member,
        "list-support-team": cmd_list_support_team,
        "pipeline-status": cmd_pipeline_status,
        "latest": cmd_latest,
        "trends": cmd_trends,
        "sleep-summary": cmd_sleep_summary,
        "workout-history": cmd_workout_history,
        "show-metric": cmd_show_metric,
        "add-goal": cmd_add_goal,
        "list-goals": cmd_list_goals,
        "update-goal": cmd_update_goal,
        "add-appointment": cmd_add_appointment,
        "list-appointments": cmd_list_appointments,
        "update-appointment": cmd_update_appointment,
        "add-provider": cmd_add_provider,
        "list-providers": cmd_list_providers,
        "add-recommendation": cmd_add_recommendation,
        "list-recommendations": cmd_list_recommendations,
        "update-recommendation": cmd_update_recommendation,
        "set-profile": cmd_set_profile,
        "show-profile": cmd_show_profile,
        "tag": cmd_tag,
        "search-tag": cmd_search_tag,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        try:
            cmd_func(args)
        except Exception as e:
            output_json({"success": False, "error": str(e)})
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
