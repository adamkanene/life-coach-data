#!/usr/bin/env python3
"""
Strava -> GitHub daily sync.

Pulls the last 8 days of Strava activities for the authenticated athlete and
upserts them into data/health-daily.json (an array of daily health records),
adding any workouts that aren't already present (matched by strava_id).

Stdlib only — no third-party dependencies, so this runs in a bare GitHub
Actions Python container with no pip install step.

Required environment variables:
  STRAVA_CLIENT_ID
  STRAVA_CLIENT_SECRET
  STRAVA_REFRESH_TOKEN

Exit code is always 0 on a "normal" run (including "no new activities") —
this script only raises/exits non-zero on a hard failure (bad credentials,
network error, etc.) so the workflow surfaces real problems clearly.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

TOKEN_URL = "https://www.strava.com/oauth/token"
ACTIVITIES_URL = "https://www.strava.com/api/v3/athlete/activities"
DATA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "health-daily.json",
)
LOOKBACK_DAYS = 8


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def http_post_form(url, fields):
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        fail(f"POST {url} failed with HTTP {e.code}: {detail}")
    except urllib.error.URLError as e:
        fail(f"POST {url} failed: {e.reason}")


def http_get_json(url, headers):
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        fail(f"GET {url} failed with HTTP {e.code}: {detail}")
    except urllib.error.URLError as e:
        fail(f"GET {url} failed: {e.reason}")


def refresh_access_token():
    client_id = os.environ.get("STRAVA_CLIENT_ID")
    client_secret = os.environ.get("STRAVA_CLIENT_SECRET")
    refresh_token = os.environ.get("STRAVA_REFRESH_TOKEN")

    if not client_id or not client_secret or not refresh_token:
        fail(
            "Missing one or more required env vars: "
            "STRAVA_CLIENT_ID, STRAVA_CLIENT_SECRET, STRAVA_REFRESH_TOKEN"
        )

    resp = http_post_form(
        TOKEN_URL,
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )

    access_token = resp.get("access_token")
    if not access_token:
        fail(f"Token refresh response did not contain an access_token: {resp}")

    new_refresh_token = resp.get("refresh_token")
    if new_refresh_token and new_refresh_token != refresh_token:
        # Strava sometimes rotates the refresh token. In this read-only,
        # single-app usage pattern the previously stored refresh token
        # keeps working, so we do NOT fail — just log a notice in case
        # Adam wants to update the GitHub secret at some point.
        print(
            "NOTICE: Strava returned a new refresh_token. The stored "
            "STRAVA_REFRESH_TOKEN secret still works for now, but you may "
            "want to update it in GitHub repo secrets to stay current."
        )

    return access_token


def fetch_recent_activities(access_token):
    after_dt = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    after_epoch = int(after_dt.timestamp())

    query = urllib.parse.urlencode({"after": after_epoch, "per_page": 100})
    url = f"{ACTIVITIES_URL}?{query}"
    headers = {"Authorization": f"Bearer {access_token}"}

    activities = http_get_json(url, headers)
    if not isinstance(activities, list):
        fail(f"Unexpected activities response (expected a list): {activities}")

    return activities


def local_date_from_activity(activity):
    # Strava gives start_date_local like "2026-07-08T06:15:00Z" — the "Z"
    # suffix is a quirk of their API (it's already local time despite the
    # zone marker), so we just take the date portion as-is.
    start_local = activity.get("start_date_local") or activity.get("start_date")
    if not start_local:
        return None
    return start_local[:10]


def round_or_none(value, ndigits=None):
    if value is None:
        return None
    try:
        if ndigits is None:
            return round(value)
        return round(value, ndigits)
    except (TypeError, ValueError):
        return None


def map_activity_to_workout(activity):
    moving_time = activity.get("moving_time") or 0
    minutes = round(moving_time / 60) if moving_time else 0

    calories = activity.get("calories")
    kilojoules = activity.get("kilojoules")
    if calories is not None:
        kcal = round_or_none(calories)
    elif kilojoules is not None:
        kcal = round_or_none(kilojoules * 1.05)
    else:
        kcal = None

    distance = activity.get("distance")
    distance_km = round_or_none(distance / 1000, 2) if distance else None

    avg_hr = activity.get("average_heartrate")
    avg_hr = round_or_none(avg_hr) if avg_hr is not None else None

    return {
        "type": activity.get("sport_type") or activity.get("type"),
        "minutes": minutes,
        "kcal": kcal,
        "distance_km": distance_km,
        "avg_hr": avg_hr,
        "strava_id": activity.get("id"),
    }


def load_existing_records():
    if not os.path.exists(DATA_PATH):
        print(f"NOTICE: {DATA_PATH} does not exist yet — starting from an empty array.")
        return []

    with open(DATA_PATH, "r", encoding="utf-8") as f:
        raw = f.read().strip()

    if not raw:
        print(f"NOTICE: {DATA_PATH} is empty — starting from an empty array.")
        return []

    try:
        records = json.loads(raw)
    except json.JSONDecodeError as e:
        fail(f"{DATA_PATH} contains invalid JSON: {e}")

    if not isinstance(records, list):
        fail(f"{DATA_PATH} must contain a JSON array at the top level.")

    return records


def blank_record(date):
    return {
        "date": date,
        "sleep_hours": None,
        "sleep_quality": None,
        "active_kcal": None,
        "resting_kcal": None,
        "steps": None,
        "workouts": [],
        "resting_hr": None,
        "hrv": None,
    }


def upsert(records, activities):
    by_date = {r.get("date"): r for r in records if isinstance(r, dict) and r.get("date")}
    added_count = 0
    skipped_count = 0

    for activity in activities:
        date = local_date_from_activity(activity)
        if not date:
            continue

        workout = map_activity_to_workout(activity)

        record = by_date.get(date)
        if record is None:
            record = blank_record(date)
            record["workouts"] = [workout]
            records.append(record)
            by_date[date] = record
            added_count += 1
            continue

        existing_ids = {
            w.get("strava_id") for w in record.get("workouts", []) if isinstance(w, dict)
        }
        if workout["strava_id"] in existing_ids:
            skipped_count += 1
            continue

        record.setdefault("workouts", [])
        record["workouts"].append(workout)
        added_count += 1

    records.sort(key=lambda r: r.get("date", ""))
    return records, added_count, skipped_count


def main():
    access_token = refresh_access_token()
    activities = fetch_recent_activities(access_token)

    print(f"Fetched {len(activities)} activities from Strava (last {LOOKBACK_DAYS} days).")

    existing_records = load_existing_records()
    original_json = json.dumps(existing_records, indent=2, sort_keys=False)

    updated_records, added_count, skipped_count = upsert(existing_records, activities)
    updated_json = json.dumps(updated_records, indent=2, sort_keys=False)

    if updated_json != original_json:
        os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
        with open(DATA_PATH, "w", encoding="utf-8") as f:
            f.write(updated_json)
            f.write("\n")
        print(
            f"SUMMARY: added {added_count} workout(s), skipped {skipped_count} "
            f"already-present workout(s). {DATA_PATH} updated."
        )
    else:
        print(
            f"SUMMARY: added {added_count} workout(s), skipped {skipped_count} "
            f"already-present workout(s). No changes to write."
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
