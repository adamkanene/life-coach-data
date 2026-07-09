# Life Coach Data Repository

This repository serves as the JSON data store for Adam's Life Coach hub — a health-coaching system that tracks nutrition, weight, daily health metrics, and periodically generates coaching reports.

## Repository Structure

### Core Data Files

**`data/profile.json`**
- Profile metadata: name, age, anthropometrics (height, weight)
- Metabolic baselines: BMR, TDEE, activity factor
- Training goal and current phase
- Phase definitions with time windows, macro targets, and rate of change targets
- Single document (not append-only)

**`data/food-log.json`**
- Append-only array of food entries
- Schema: `{date: "YYYY-MM-DD", time: "HH:MM", description: string, kcal: number, protein_g: number, carbs_g: number, fat_g: number, source: "claude-estimate"}`

**`data/weight-log.json`**
- Append-only array of weight entries
- Schema: `{date: "YYYY-MM-DD", weight_lb: number}`

**`data/health-daily.json`**
- Append-only array of daily health snapshots
- Schema: `{date: "YYYY-MM-DD", sleep_hours: number, sleep_quality: number|null, active_kcal: number, resting_kcal: number, steps: number, workouts: [{type: string, minutes: number, kcal: number}], resting_hr: number, hrv: number}`

### Additional Files

**`index.html`**
- GitHub Pages dashboard displaying life-coach metrics and progress visualizations
- Consumes data files to render real-time health snapshots

**`/reports/`**
- Weekly coaching reports stored as `YYYY-WW.md` (year-week ISO format)
- Narrative coaching analysis, macro trends, and recommendations

## Important Guidelines for Contributors and Tools

1. **Append-only**: All log files (`*-log.json`, `health-daily.json`) are append-only. Never overwrite, delete, or modify existing entries.
2. **No tokens in commits**: Never commit sensitive credentials, API keys, or access tokens to this repository.
3. **Valid JSON**: All JSON files must be valid with 2-space indentation.
4. **Profile updates**: The `profile.json` file may be updated (not append-only) when phase transitions occur or baselines change.

## Usage

This data store is intended to be consumed by:
- The Life Coach hub's Claude coaching interface
- GitHub Pages dashboard for visualization
- Weekly report generation workflows
