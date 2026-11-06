"""Build a shareable weekly workout summary from the lift log and food log.

Runs in the Saturday-night GitHub Action right before generate_week.py and writes
data/weekly-summary.json. It summarizes the week that is ending: the Sunday-to-
Saturday week before the one that contains "tomorrow" (America/Chicago), so it
picks the right week whether the cron fires at 11:30 PM Sat or 12:30 AM Sun.

Usage: python scripts/weekly_summary.py [--week-start YYYY-MM-DD]
"""
import argparse, json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "weekly-summary.json"
MAIN_LIFTS = {"squat": "Squat", "bench": "Bench", "deadlift": "Deadlift", "ohp": "OHP", "incline": "Incline bench"}


def load(name, fallback):
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else fallback


def e1rm(w, r):  # Epley
    return w * (1 + r / 30)


def keytel_kcal(avg_hr, minutes, weight_lb, age):
    """Gross kcal from average HR (Keytel 2005, male). Fallback when Strava has no calories."""
    per_min = (-55.0969 + 0.6309 * avg_hr + 0.1988 * weight_lb * 0.4536 + 0.2017 * age) / 4.184
    return max(per_min, 0) * minutes


def fmt_range(a, b):
    if a.month == b.month:
        return f"{a:%b} {a.day}–{b.day}"
    return f"{a:%b} {a.day}–{b:%b} {b.day}"


def summarize(program, lift_log, food_log, health, profile, week_start):
    week_end = week_start + timedelta(days=6)
    start = date.fromisoformat(program["start_date"])
    idx = (week_start - start).days // 7 + 1
    total = program["weeks_total"]
    in_week = lambda d: week_start.isoformat() <= d <= week_end.isoformat()

    lifts = [e for e in lift_log if in_week(e.get("date", "")) and e.get("weight_lb") and e.get("reps")]

    # Workouts = distinct program sessions with at least one logged set.
    sessions = {(e.get("week"), e.get("session")) for e in lifts if e.get("session")}
    workouts = len(sessions) if sessions else len({e["date"] for e in lifts})

    # Best lift = main-lift set with the highest estimated 1RM relative to that lift's max.
    maxes = program["maxes_lb"]
    best = None
    for e in lifts:
        ex = e["exercise"]
        if ex not in MAIN_LIFTS or ex not in maxes:
            continue
        score = e1rm(e["weight_lb"], e["reps"]) / maxes[ex]
        if best is None or score > best["score"] + 1e-9:
            best = {"exercise": ex, "weight_lb": e["weight_lb"], "reps": e["reps"], "score": score}
    if best:
        best["sets"] = sum(1 for e in lifts if e["exercise"] == best["exercise"]
                           and e["weight_lb"] == best["weight_lb"] and e["reps"] == best["reps"])
        best["pct_of_max"] = round(best.pop("score") * 100)

    # Protein = average over days that have any food logged (partial logging is called out).
    by_day = {}
    for f in food_log:
        if in_week(f.get("date", "")):
            by_day[f["date"]] = by_day.get(f["date"], 0) + (f.get("protein_g") or 0)
    days_logged = len(by_day)
    avg_protein = round(sum(by_day.values()) / days_logged) if days_logged else None
    phase = profile.get("current_phase") if profile else None
    protein_goal = profile["phases"][phase]["targets"]["protein_g"] if phase else None

    # Calories burned = Strava activities this week; HR estimate only where Strava has none.
    kcal_total, n_acts, n_est = 0, 0, 0
    for day in health:
        if not in_week(day.get("date", "")):
            continue
        for wo in day.get("workouts") or []:
            n_acts += 1
            if wo.get("kcal") is not None:
                kcal_total += wo["kcal"]
            elif wo.get("avg_hr") and wo.get("minutes") and profile:
                kcal_total += keytel_kcal(wo["avg_hr"], wo["minutes"], profile["weight_lb"], profile["age"])
                n_est += 1
    kcal_total = round(kcal_total)

    weeks_left = max(total - idx, 0)
    lines = ["💪 Welcome to Adam's Weekly Workout Summary!",
             f"Week {idx} of {total} · {fmt_range(week_start, week_end)}", ""]
    lines.append(f"✅ Workouts: {workouts} of 4")
    if best:
        sets = f" ({best['sets']} sets)" if best["sets"] > 1 else ""
        lines.append(f"🔥 Best lift: {MAIN_LIFTS[best['exercise']]} {best['weight_lb']} × {best['reps']}{sets}")
    else:
        lines.append("🔥 Best lift: nothing logged this week")
    if n_acts:
        approx = "~" if n_est else ""
        lines.append(f"⚡ Calories burned: {approx}{kcal_total:,} kcal across {n_acts} "
                     f"activit{'y' if n_acts == 1 else 'ies'}")
    else:
        lines.append("⚡ Calories burned: no Strava activities this week")
    if avg_protein is not None:
        goal = f", goal {protein_goal}" if protein_goal else ""
        partial = f" · logged {days_logged} of 7 days" if days_logged < 7 else ""
        lines.append(f"🥩 Avg protein: {avg_protein} g/day{goal}{partial}")
    else:
        lines.append("🥩 Avg protein: no food logged this week")
    if weeks_left > 1:
        lines.append(f"⏳ {weeks_left} weeks until max-out day")
    elif weeks_left == 1:
        lines.append("⏳ 1 week until max-out day")
    else:
        lines.append("🎯 Max-out day is next!")
    lines += ["", "See you next week 🫡", "", "— Delivered by Claude"]

    return {"week_start": week_start.isoformat(), "week_end": week_end.isoformat(), "week": idx,
            "weeks_total": total, "workouts": workouts, "best_lift": best,
            "avg_protein_g": avg_protein, "protein_goal_g": protein_goal, "protein_days_logged": days_logged,
            "weeks_until_max": weeks_left,
            "kcal_burned": kcal_total, "strava_activities": n_acts, "kcal_estimated_activities": n_est,
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "text": "\n".join(lines)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--week-start")
    args = ap.parse_args()
    program = load("lift-program.json", None)
    if args.week_start:
        ws = date.fromisoformat(args.week_start)
    else:
        tomorrow = datetime.now(ZoneInfo(program.get("timezone", "America/Chicago"))).date() + timedelta(days=1)
        ws = tomorrow - timedelta(days=(tomorrow.weekday() + 1) % 7) - timedelta(days=7)
    start = date.fromisoformat(program["start_date"])
    if not (0 <= (ws - start).days // 7 < program["weeks_total"]):
        print(f"{ws} is outside the program block; no summary written.")
        return
    s = summarize(program, load("lift-log.json", []), load("food-log.json", []), load("health-daily.json", []), load("profile.json", None), ws)
    out = load("weekly-summary.json", {"weeks": {}})
    out["weeks"][s["week_start"]] = s
    out["latest_week_start"] = s["week_start"]
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    print(s["text"])


if __name__ == "__main__":
    main()
