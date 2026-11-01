"""Generate next week's 4 lifting sessions from data/lift-program.json.

Runs every Saturday night (GitHub Action) and writes data/weekly-workouts.json.
The target week is the one that contains "tomorrow" in America/Chicago, so a
Saturday-night run builds the week that starts on Sunday.

Usage: python scripts/generate_week.py [--date YYYY-MM-DD]
  --date: build the week containing this date instead.
"""
import argparse, json, math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
PROGRAM = ROOT / "data" / "lift-program.json"
OUT = ROOT / "data" / "weekly-workouts.json"


def round_to(x, step):
    return int(math.floor(x / step + 0.5) * step)


def in_range(key, week):
    if key == "all":
        return True
    if "-" in key:
        a, b = key.split("-")
        return int(a) <= week <= int(b)
    return int(key) == week


def pick(by_range, week):
    exact = [k for k in by_range if k not in ("all",) and in_range(k, week)]
    if exact:
        return by_range[exact[0]]
    return by_range.get("all", [])


def build_week(program, week_start):
    start = date.fromisoformat(program["start_date"])
    idx = (week_start - start).days // 7 + 1
    total = program["weeks_total"]
    week_end = week_start + timedelta(days=6)
    base = {"week_start": week_start.isoformat(), "week_end": week_end.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if idx < 1 or idx > total:
        base.update({"week": idx, "status": "outside_block",
                     "message": ("Block finished. Update your maxes in data/lift-program.json "
                                 "and set a new start_date to start the next block.") if idx > total
                     else "Block has not started yet."})
        return base

    wk = next(w for w in program["weeks"] if w["week"] == idx)
    maxes, step = program["maxes_lb"], program.get("round_to_lb", 5)
    sessions = []
    for sid in ["1", "2", "3", "4"]:
        tpl = program["sessions"][sid]
        mains = []
        for b in wk["sessions"][sid]:
            rows = []
            for r in b["rows"]:
                lb = round_to(maxes[b["lift"]] * r["pct"] / 100, step) if r.get("pct") is not None else None
                rows.append({**r, "lb": lb})
            mains.append({**b, "rows": rows, "max_lb": maxes[b["lift"]]})
        sessions.append({"id": int(sid), "title": f"Session {sid} — {tpl['title']}", "focus": tpl["focus"],
                         "main": mains, "accessories": pick(tpl["accessories"], idx),
                         "finisher": tpl["finisher"]})
    base.update({"week": idx, "weeks_total": total, "theme": wk["theme"], "status": "active",
                 "maxes_lb": maxes, "rules": program["rules"],
                 "conditioning": program["conditioning"], "sessions": sessions})
    return base


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date")
    args = ap.parse_args()
    program = json.loads(PROGRAM.read_text())
    if args.date:
        target = date.fromisoformat(args.date)
    else:
        target = datetime.now(ZoneInfo(program.get("timezone", "America/Chicago"))).date() + timedelta(days=1)
    week_start = target - timedelta(days=(target.weekday() + 1) % 7)  # back to Sunday

    out = json.loads(OUT.read_text()) if OUT.exists() else {"weeks": {}}
    out["program"] = program["name"]
    out["weeks"][week_start.isoformat()] = build_week(program, week_start)
    out["latest_week_start"] = week_start.isoformat()
    OUT.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    w = out["weeks"][week_start.isoformat()]
    print(f"Wrote week {w['week']} ({w['week_start']} to {w['week_end']}): {w.get('theme', w.get('status'))}")


if __name__ == "__main__":
    main()
