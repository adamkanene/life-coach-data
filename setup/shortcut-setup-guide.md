# Daily Health Sync — iOS Shortcut Setup Guide

This guide walks you through building an iOS Shortcut called **"Daily Health Sync"** that runs automatically every night at 11:00 PM, pulls your day's Health data (sleep, calories, steps, workouts, resting heart rate, HRV) off your iPhone/Apple Watch, and appends it as a new JSON record to a file living in your GitHub repo (`adamkanene/life-coach-data`, file `data/health-daily.json`).

It also includes a bonus mini-shortcut, **"Log Weight"**, that does the same thing for a manually-entered weight number into `data/weight-log.json`.

You do not need to write any code. Everything below happens inside the Shortcuts app on your iPhone.

---

## 0. Before you start

- You need the **Shortcuts** app (pre-installed on iOS).
- You need your **fine-grained GitHub PAT** (Personal Access Token) with **read + write** access to the `Contents` permission on the `adamkanene/life-coach-data` repo. You said you already have this — keep it handy, you'll paste it into one Text action.
- The repo must already contain a file at `data/health-daily.json` with valid JSON in it — an empty array `[]` is fine as a starting point. Create that file directly on GitHub.com if it doesn't exist yet (Add file → Create new file → path `data/health-daily.json` → content `[]` → commit).
- Make sure Shortcuts has permission to read Health data. The first time a "Find Health Samples" action runs, iOS will pop up a permission sheet — approve all the categories listed in Step 2.

### A note on safety

**Your GitHub token will live inside this shortcut in plain text (inside a Text action).** Do NOT use the Shortcuts "Share" button to send this shortcut to anyone, and do NOT upload it to the public Shortcuts gallery. If you ever need to share the shortcut for troubleshooting, delete the token from the Text action first, or delete/replace it after export. Treat the token like a password. If it ever leaks, revoke it immediately in GitHub → Settings → Developer settings → Fine-grained tokens.

---

## 1. Create the shortcut shell

1. Open **Shortcuts** → tap **+** (top right) to create a new shortcut.
2. Tap the name at the top ("New Shortcut") and rename it to **Daily Health Sync**.
3. Tap the (i) settings icon → turn on **"Show in Widget"** off is fine, but turn OFF **"Show When Run"** later once tested (leave it ON for now while you're debugging — it'll show you each step's output).

We're going to build this in blocks. Add each action in the order given by tapping **+ Add Action** and searching for the action name in quotes.

---

## 2. Block A — Set up constants (token, date, URLs)

These go at the very top of the shortcut so there's exactly one place to update the token later.

1. **Add action: "Text"**
   Content: paste your GitHub PAT, e.g. `github_pat_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX`
   Tap the small "..." on this action's card and rename it (via the ⓘ) — actually, easier: after adding it, tap the action once, then tap the top-right "..." is not available for Text; instead just remember it as "the first Text action" — Shortcuts lets you reference any prior action's output as a **Magic Variable** by long-pressing/tapping the blue variable pill in a later field and picking it from the list, where it's labeled by its content preview. To make it easier to find later, keep this as the very first action in the shortcut so it's always at the top of the variable list.

2. **Add action: "Text"** (second one — this is your repo path constant)
   Content: `https://api.github.com/repos/adamkanene/life-coach-data/contents/data/health-daily.json`

3. **Add action: "Format Date"**
   Input: **Current Date** (tap the input field → it defaults to Current Date, or add a "Current Date" action right before this one and feed it in).
   Date Format: **Custom**
   Custom Format: `yyyy-MM-dd`
   This gives you today's date as `2026-07-08` style text. Rename this action's output mentally as "Today String" — you'll pick it later via its Magic Variable pill (it will preview as "2026-07-08" once run).

At this point your action list looks like:
```
1. Text → [PAT token]
2. Text → [GitHub Contents API URL]
3. Format Date → Today String (yyyy-MM-dd)
```

---

## 3. Block B — Pull today's Health data

We need six pieces of data: sleep hours, active kcal, resting kcal, steps, workouts (list), resting HR, and HRV. We'll do one "Find Health Samples" per metric, each followed by small math/format actions.

### 3.1 Sleep hours (sum of last night's sleep)

1. **Add action: "Find Health Samples where"**
   - Sample Type: tap it → choose **Sleep Analysis**.
   - Set the filter row to: **Start Date** is **in the last** `1` **Days** (this captures last night's sleep even if you're running at 11 PM before falling asleep tonight — it looks backward). If your sleep schedule means "last night" spans into "today," `1 Day` back is normally enough; if you go to bed very late, use `36 Hours` instead — tap the unit picker to change Days→Hours.
   - Sort: Start Date, Latest First. Limit: **All**.
   - This returns a **list of sleep sample items**, each with a value like "Core", "Deep", "REM", "Awake", "InBed".

2. **Add action: "Filter Files"** — actually for Health samples, use **"Filter"** (search "Filter", it works generically on lists). Configure: Filter **Sleep Analysis Samples** where **Sleep State** is not **In Bed** and not **Awake** (so we only sum actual asleep time — Core+Deep+REM). If "Sleep State" isn't a filterable property in your iOS version, skip this Filter step and instead rely on the fact that "Sleep Analysis" totals in the next action are close enough for coaching purposes.

3. **Add action: "Get Details of Health Sample"** run inside a loop, OR simpler — use the built-in aggregate:
   **Add action: "Health Sample Duration"** is not a real action name; instead do this reliable approach:
   - **Add action: "Repeat with Each"** with Input = the sleep samples list from step 3.1.
     - Inside the repeat: **Add action: "Get Details of Health Sample"** → Detail: **Duration**. This gives the duration of that one sample.
     - **Add action: "Get Numbers from Input"** on that duration (durations sometimes come through as text like "45 min").
   - **After** the Repeat block ends: **Add action: "Calculate Statistics"** → Operation: **Sum**, Input = the Magic Variable representing "Get Numbers from Input" results (Shortcuts automatically collects every loop iteration's output into a list when you reference it from outside the loop — pick the variable named after the "Get Numbers from Input" action, not "Repeat Results").
   - This Sum will be in **minutes** (Health durations are minutes). 
   - **Add action: "Calculate"** → `[Sum] / 60` → this is **sleep_hours**. Tap the operator to `÷`, first number = the Sum Magic Variable, second number = `60`.
   - **Add action: "Round"** → Round to 2 places, so you get e.g. `7.42` instead of `7.4166666`.

   Rename this final number's Magic Variable mentally as **"Sleep Hours"** — you'll recognize it as the output of the last Round action when picking variables later.

### 3.2 Active energy burned (kcal)

1. **Add action: "Find Health Samples where"**
   - Sample Type: **Active Energy**
   - Filter: Start Date is **Today** (use the "is today" relative date option, or "in the last 1 Days" — Today is cleaner and avoids double counting).
   - Sort: doesn't matter. Limit: All.
2. **Add action: "Calculate Statistics"** → Operation: **Sum** → Input: the list from step 1 (feed the Health Samples list directly — Shortcuts can sum sample quantities without a manual Get Numbers step, but if it errors, insert a "Get Numbers from Input" action first to force it to numeric).
3. **Add action: "Round"** → 0 decimal places. This is **active_kcal**.

### 3.3 Resting energy burned (kcal)

Repeat exactly the same three steps as 3.2, but Sample Type = **Resting Energy**. Output = **resting_kcal**.

### 3.4 Steps

Repeat the same pattern, Sample Type = **Steps**, Sum, Round 0 decimals. Output = **steps**.

### 3.5 Resting heart rate

1. **Add action: "Find Health Samples where"** → Sample Type: **Resting Heart Rate** → Start Date is **Today** → Sort **Latest First** → Limit **1** (resting HR is usually written once/day by watchOS, so grab the latest).
2. **Add action: "Get Details of Health Sample"** → Detail: **Quantity**.
3. **Add action: "Get Numbers from Input"** → Round if needed. Output = **resting_hr**.
   - If the list is empty on a given day (Limit 1 with no results), Shortcuts will pass through empty/nothing — the "Get Numbers from Input" will yield blank. See Troubleshooting for handling nulls.

### 3.6 HRV (Heart Rate Variability)

Same pattern as 3.5: Sample Type = **Heart Rate Variability (SDNN)** → Today → Sort Latest First → Limit 1 → Get Details → Quantity → Get Numbers from Input. Output = **hrv**. (HRV values come in milliseconds — that matches the schema's plain number field.)

### 3.7 Workouts today

1. **Add action: "Find Health Samples where"**
   - Sample Type: **Workouts**
   - Filter: Start Date is **Today**
   - Sort: Start Date, Latest First. Limit: All.
   - This returns a list of Workout items (could be zero, one, or several).

2. **Add action: "Repeat with Each"** → Input: the Workouts list.
   Inside the loop, build one dictionary per workout:
   - **Add action: "Get Details of Health Sample"** → Detail: **Workout Type** → this is a Magic Variable, call it mentally "Workout Type."
   - **Add action: "Get Details of Health Sample"** → Detail: **Duration** → then **"Get Numbers from Input"** to strip units → then **"Calculate"** if you want minutes rounded → mentally "Workout Minutes."
   - **Add action: "Get Details of Health Sample"** → Detail: **Total Active Energy** (this is the workout's own kcal burn) → **"Get Numbers from Input"** → mentally "Workout Kcal."
   - **Add action: "Dictionary"** → tap **+** twice to add three key/value rows:
     - key `type`, value = Workout Type variable
     - key `minutes`, value = Workout Minutes variable
     - key `kcal`, value = Workout Kcal variable
   - This Dictionary action's output is one workout object. Because it's inside the Repeat block, Shortcuts automatically accumulates one dictionary per loop iteration.

3. After the Repeat block ends, reference the Dictionary action's Magic Variable **from outside the loop** — Shortcuts will treat it as a **list of dictionaries** (this is the "aggregate" behavior: any variable produced inside a Repeat, when used outside, becomes the full collected list). This list is your **workouts** array. If zero workouts happened, this will correctly be an empty list `[]`.

---

## 4. Block C — Assemble today's record as a Dictionary

1. **Add action: "Dictionary"**. Build these key/value pairs, using the ⓘ "Add new field" and choosing **Text**, **Number**, **Array**, or **Dictionary** type per field as noted:
   - `date` → Text → Magic Variable = Today String (from Step 2.3)
   - `sleep_hours` → Number → Magic Variable = Sleep Hours (Step 3.1)
   - `sleep_quality` → for this field, tap the value type selector and choose **Text**, then leave it literally as the word `null` is wrong (that produces a string "null"). Instead: set this field's type to **Dictionary** is also wrong. The cleanest way to get a true JSON null with Shortcuts' Dictionary action is:
     - Set the field type to **Text** and put nothing in it, OR
     - Skip adding this key inside the Dictionary UI entirely, and instead build the whole record as a **raw JSON text template** (see the alternate method below) so you can type `null` literally.
   - `active_kcal` → Number → Active Kcal (Step 3.2)
   - `resting_kcal` → Number → Resting Kcal (Step 3.3)
   - `steps` → Number → Steps (Step 3.4)
   - `workouts` → Array → Magic Variable = the Workouts dictionary list (Step 3.7.3)
   - `resting_hr` → Number → Resting HR (Step 3.5)
   - `hrv` → Number → HRV (Step 3.6)

### Handling `sleep_quality: null` (Shortcuts UI quirk)

The Shortcuts "Dictionary" action cannot natively emit a JSON `null` literal — every field you add gets a real value type (Text/Number/Boolean/etc.), and an empty Text field serializes as `""`, not `null`. Two practical options:

- **Option A (recommended, simplest):** Just omit `sleep_quality` from the Dictionary entirely for now. Your JSON records simply won't have that key most days; add it manually later via the app/dashboard when you actually start rating sleep quality. Downstream code reading the file should already treat a missing key the same as null.
- **Option B (exact schema match):** Instead of the Dictionary action for the whole record, use a **"Text"** action containing a hand-typed JSON template with a Magic Variable dropped into each slot, e.g.:
  ```
  {"date":"[Today String]","sleep_hours":[Sleep Hours],"sleep_quality":null,"active_kcal":[Active Kcal],"resting_kcal":[Resting Kcal],"steps":[Steps],"workouts":[Workouts JSON],"resting_hr":[Resting HR],"hrv":[HRV]}
  ```
  To get `[Workouts JSON]` as inline JSON text (not Shortcuts' own list formatting), feed the Workouts dictionary list into a **"Get Contents of"** no — instead pipe it through **"Get Dictionary from Input"** in reverse isn't available; the practical route is: keep Block C's workouts as a proper **Dictionary/Array** built with the Dictionary action (per the main method above), then wrap only the *outer* record using the Text-template method for the `sleep_quality:null` field, and use **"Get Dictionary Value"** is not needed here — simplest is: build the Dictionary action for everything except `sleep_quality`, then don't worry about it (go with Option A). This avoids fighting the UI. The rest of this guide assumes **Option A**.

Result of Block C: one Dictionary action whose Magic Variable represents **today's health record**. Call this "Today's Record" in your head.

---

## 5. Block D — GET the current file, decode it, and prep the merge

1. **Add action: "Get Contents of URL"**
   - URL: the Magic Variable from Step 2.2 (your Contents API URL).
   - Method: **GET**
   - Headers: tap "Show More" → add a header:
     - Key: `Authorization`
     - Value: `Bearer ` followed immediately by the Magic Variable from Step 2.1 (your PAT Text action) — type the literal word `Bearer` plus a space, then insert the token variable right after it in the same field.
   - Add a second header: Key `Accept`, Value `application/vnd.github+json`.
   - This returns JSON like `{"content": "<base64>", "sha": "<sha>", ...}`.

2. **Add action: "Get Dictionary Value"** → Get Value for Key: `sha` → Dictionary: the "Get Contents of URL" Magic Variable. Output = **Current SHA** (you'll need this for the PUT).

3. **Add action: "Get Dictionary Value"** → Get Value for Key: `content` → Dictionary: same "Get Contents of URL" result. Output = **base64 content**.
   - Note: GitHub's API returns this base64 string with embedded newlines every 60 chars. Shortcuts' Base64 Decode handles that fine in practice, but if you get decode errors, add a **"Replace Text"** action first: find `\n` (enable "Regular Expression" toggle and use `\n` — or simplest, find literal newline by pasting an actual line break into the "Find" field), replace with nothing, to strip line breaks before decoding.

4. **Add action: "Base64 Decode"** → Input: the (cleaned) base64 content. Output = the raw JSON text of your current `health-daily.json` array, e.g. `[{"date":"2026-07-01",...}, {...}]`.

5. **Add action: "Get Dictionary from Input"** — actually since the decoded content is a **JSON array**, use **"Get Contents of"**? No — the right action is **"Get Dictionary from Input"** works for arrays too in Shortcuts (it parses any valid JSON, dict or array) — run it on the decoded text. Output = **Existing Records** (a Shortcuts List/Array object, not text).

---

## 6. Block E — Append today's record and re-encode

1. **Add action: "Add to Variable"** — actually simplest is: **Add action: "Combine Text"**? No — for combining a list + one new item, use:
   - **Add action: "List"** — skip this; instead:
   - Take the **Existing Records** array and use **"Add Item to List"** if available in your iOS version (search "Add Item"). If that exact action isn't present, use this reliable alternative:
   - **Add action: "Text"**: content = `[Existing Records JSON]` is what we need as text again. Since Get Dictionary from Input converted text→object, and now we want to append then convert back, the cleanest path in Shortcuts is actually to skip converting to a Dictionary object at all and do it as **text surgery**:

   **Simpler, more reliable approach (recommended):** Skip step 5.5 entirely. Instead, treat the decoded JSON array as text and splice in the new record just before the closing bracket:
   - **Add action: "Replace Text"**: 
     - Input: the Base64-decoded text (Step 5.4 output).
     - Find: `]` with **"Total Matches: Last"** — actually Replace Text replaces all matches by default; since a well-formed array's only closing `]` is at the very end (workouts arrays inside are also closed with `]`, which is a problem). To be safe:
     - Find (enable Regular Expression): `\]\s*$` (a `]` at the very end of the string, allowing trailing whitespace).
     - Replace: if the array is non-empty (normal case after day 1), use `,TODAY_RECORD_PLACEHOLDER]`; if the file might still be the initial empty `[]`, this same replace still works because `\]\s*$` matches the lone `]` in `[]` too, and comma-leading-into-empty-array (`[,{...}]`) is invalid JSON — so instead special-case it: add an **If** action checking whether the decoded text (trimmed) equals `[]`. 
       - **If** decoded text = `[]` → Replace it wholesale with `[TODAY_RECORD_PLACEHOLDER]`.
       - **Otherwise** → run the `\]\s*$` → `,TODAY_RECORD_PLACEHOLDER]` replace described above.
   - **Add action: "Replace Text"** (second one): Input = result of the above, Find = `TODAY_RECORD_PLACEHOLDER` (plain text, no regex), Replace = the Magic Variable of **Today's Record** (your Block C Dictionary action — Shortcuts will automatically render a Dictionary variable as its JSON text when dropped into a Text field like this). Output = **Updated File Text** — the complete new JSON array as a string.

2. **Add action: "Base64 Encode"** → Input: Updated File Text. Output = **Updated Base64**.

---

## 7. Block F — Build the PUT body and send it

1. **Add action: "Text"** (commit message) → content: `Daily health sync — ` followed by the Today String variable, e.g. `Daily health sync — 2026-07-08`.

2. **Add action: "Dictionary"** → three keys:
   - `message` → Text → the commit message variable from 7.1
   - `content` → Text → Updated Base64 (Step 6.2)
   - `sha` → Text → Current SHA (Step 5.2)

3. **Add action: "Get Contents of URL"**
   - URL: same Contents API URL variable (Step 2.2).
   - Method: **PUT**
   - Headers: same two headers as the GET (Authorization: Bearer <token variable>, Accept: application/vnd.github+json), plus `Content-Type: application/json`.
   - Request Body: tap **Request Body** → choose **JSON** → then instead of adding fields manually, toggle to use the Dictionary directly: set the body field to the Magic Variable from Step 7.2 (the whole Dictionary) — Shortcuts will serialize it as the JSON body automatically when Request Body type is set to JSON and you drop a Dictionary variable into it.
   - Turn on **"Show More"** → confirm **Method: PUT** is actually selected (Shortcuts defaults to GET — this is the single most common mistake).

This "Get Contents of URL" action's response is what GitHub sends back: on success, a 200/201-ish JSON with the new commit info; on failure, a JSON with a `message` field describing the error (e.g., `"Invalid request. ... sha ..."` for a 409, or `"Bad credentials"` for a 401).

---

## 8. Block G — Check success/failure and notify only on failure

GitHub's API doesn't give you a plain numeric status code as a separate first-class variable in older Shortcuts versions, but current Shortcuts exposes it: after "Get Contents of URL," tap the result Magic Variable's small ⓘ / long-press to reveal sub-properties, or simply add:

1. **Add action: "Get Dictionary Value"** → Get Value for Key: `content` — wait, that's for the GET step. For the PUT response, instead:
   - **Add action: "Get Details of"** isn't right either. The reliable way: Shortcuts' "Get Contents of URL" action, when you tap the returned variable in a later action's field, offers a variant called **"Status Code"** in some iOS versions via long-press → "Get Variable" details. If your version doesn't expose it directly, use this fallback:
   - **Add action: "Get Dictionary Value"** → Key: `message` → Dictionary: the PUT response. If the PUT succeeded, GitHub's success response has no top-level `message` key (or has an unrelated one nested under `commit`), so this will come back empty/absent. If it failed, `message` will contain the error text.

2. **Add action: "If"** 
   - Condition: the `message` value (from 8.1) **has any value** (Shortcuts condition: "has any value" / "is not empty").
   - **If true (there's an error message):**
     - **Add action: "Show Notification"** → Title: `Daily Health Sync Failed`, Body: the `message` variable's text (so you see the actual GitHub error, e.g. "Bad credentials" or the sha conflict text).
   - **Otherwise:**
     - Optionally add a quiet **"Show Notification"** → "Health data synced ✓" — or leave this branch empty if you don't want a nightly ping on success.

3. **Add action: "End If"** (Shortcuts adds this automatically when you close the If block).

---

## 9. Turn "Show When Run" off (optional, once tested)

Once you've manually tested the shortcut a few times and it works reliably (Section 11), go back into the (i) settings and you can leave "Show When Run" as-is — for an automation that fires at night while your phone is idle, Shortcuts will still run it silently in the background regardless of this toggle when triggered by Personal Automation with "Ask Before Running" turned off (next section). This toggle mainly affects manual taps from the Shortcuts app/widget.

---

## 10. Set up the 11:00 PM Personal Automation

1. Open **Shortcuts** → tap the **Automation** tab (bottom).
2. Tap **+** (top right) → **Create Personal Automation**.
3. Choose trigger type **Time of Day**.
4. Set the time to **11:00 PM**. Set **Repeat: Daily**.
5. Tap **Next**.
6. Tap **Add Action** → search for and choose **"Run Shortcut"** → tap "Shortcut" placeholder → select **Daily Health Sync**.
7. Tap **Next**.
8. **Critical step:** on the summary screen, tap **"Ask Before Running"** and switch it OFF, confirming **"Run Immediately"** (Shortcuts will show a warning that this runs silently without confirmation — that's what you want for a nightly hands-off sync).
9. Tap **Done**.

Your phone must be awake enough to fire the automation — Personal Automations of this "Time of Day" type run via the system scheduler even if the phone is locked/asleep, as long as it's not powered off and Shortcuts has background app refresh enabled (Settings → Shortcuts → Background App Refresh: On, and Settings → General → Background App Refresh: On globally).

---

## 11. Manual test procedure

Do this before trusting the automation:

1. Open **Shortcuts** → **My Shortcuts** → tap **Daily Health Sync** directly (this runs it immediately, same as the automation would).
2. Watch each step's output pop up (if "Show When Run" is on). Confirm:
   - Sleep Hours, Active Kcal, Resting Kcal, Steps, Resting HR, HRV all show sensible non-zero numbers (unless it's legitimately a rest day with e.g. zero workouts).
   - Workouts list shows the correct count for today (zero is fine if you didn't work out).
3. After it finishes, you should see either nothing (silent success) or a "Health data synced ✓" notification if you enabled that branch.
4. Go to **github.com** → `adamkanene/life-coach-data` → `data/health-daily.json` → confirm a new commit appeared (check the commit history / "History" button on the file) and that the file now ends with a new object matching today's date and your numbers.
5. Deliberately break it once to test the failure path: temporarily change one character in the PAT Text action, run the shortcut, confirm you get the **"Daily Health Sync Failed"** notification with a "Bad credentials" style message. Then fix the token back.
6. Run it twice in a row without changing anything else — confirm the second run does NOT fail (this checks that you're correctly grabbing a fresh `sha` on every GET, so back-to-back runs don't collide). Note: running it twice in one day will append two records for the same date, which is expected behavior for this simple version — the shortcut doesn't dedupe by date.

---

## 12. Troubleshooting

**401 Unauthorized / "Bad credentials"**
- Your PAT is wrong, expired, or was regenerated on GitHub. Re-copy the token from GitHub → Settings → Developer settings → Fine-grained tokens, and paste it into the single Text action from Step 2.1 (nowhere else needs to change).
- Confirm the header value is exactly `Bearer <token>` with one space and no quote marks, line breaks, or trailing spaces.
- Confirm the token's repository access includes `adamkanene/life-coach-data` and its permission includes **Contents: Read and write** (fine-grained PATs need this explicit permission checked).

**409 Conflict / sha mismatch (e.g. "does not match" in the message)**
- This means the file changed on GitHub between your GET and your PUT (e.g., you edited it manually on github.com, or the shortcut ran twice nearly simultaneously). 
- Fix: just run the shortcut again — it re-fetches a fresh `sha` on every run, so a second attempt should succeed as long as nothing is editing the file at that exact moment.
- If it persists, open the file on GitHub.com, confirm its content is valid JSON (a single well-formed array), and manually fix any corruption before retrying.

**Empty numbers / zeros everywhere despite having Health data**
- Almost always a Health **permissions** issue. Go to **Settings → Privacy & Security → Health → Shortcuts** and make sure every category you're reading (Sleep, Active Energy, Resting Energy, Steps, Workouts, Resting Heart Rate, Heart Rate Variability) is toggled **On** under "Turn On All" or individually.
- If Shortcuts isn't listed there at all, run the shortcut once manually — iOS only shows an app in that Health permissions list after it has requested access at least once, which happens the first time a "Find Health Samples" action executes.
- Also check the actual Apple Watch is syncing that data type at all (e.g., HRV and resting HR require several days of watch-wearing history to populate; if you just got the watch, those may legitimately be empty for the first week).

**"Get Contents of URL" fails immediately / generic network error**
- Check Wi-Fi/cellular connectivity on the phone at test time.
- Confirm the URL variable (Step 2.2) has no typos — the URL is case-sensitive: `https://api.github.com/repos/adamkanene/life-coach-data/contents/data/health-daily.json`.

**Base64 decode produces garbage or an error**
- GitHub's returned base64 has embedded newlines. Add the "Replace Text" newline-stripping action described in Step 5.3 before the "Base64 Decode" action.

**JSON ends up malformed after appending (e.g., double commas, missing bracket)**
- This usually means the `\]\s*$` regex in Step 6.1 matched an inner `]` instead of the final one, or the file wasnically pre-formatted with trailing whitespace/newline oddly. Open the file on GitHub, manually fix it back to a clean array (e.g. re-save as `[]` or trim it back to the last known-good record), and re-run.
- To reduce risk long-term, consider validating in a "Get Dictionary from Input" step after building "Updated File Text" and before encoding — if that action errors out, the JSON is invalid and the shortcut will stop before it corrupts your GitHub file (since Get Contents of URL/PUT never fires).

**Automation didn't run at all overnight**
- Check Settings → General → Background App Refresh is on (globally and for Shortcuts).
- Check Low Power Mode wasn't on overnight — it can delay background automations.
- Re-open the Automation and confirm "Ask Before Running" is still off — an iOS update occasionally resets this toggle back to asking for confirmation.

---

## 13. Optional add-on: "Log Weight" mini-shortcut

A second, much simpler shortcut for manually logging your weight whenever you step on the scale, using the same GET → decode → append → encode → PUT pattern against `data/weight-log.json`.

1. Create a new shortcut named **Log Weight**.
2. **Add action: "Text"** → your PAT (same token — you can copy/paste from the Daily Health Sync shortcut's Text action, or just retype it).
3. **Add action: "Text"** → URL: `https://api.github.com/repos/adamkanene/life-coach-data/contents/data/weight-log.json`
4. **Add action: "Format Date"** → Current Date → Custom → `yyyy-MM-dd` → Today String.
5. **Add action: "Ask for Input"** → Input Type: **Number** → Prompt: `What's your weight today (lb)?`. This pauses the shortcut with a numeric keypad when you run it, and its output is a Magic Variable ("Provided Input").
6. **Add action: "Dictionary"** → two keys:
   - `date` → Text → Today String
   - `weight_lb` → Number → Provided Input (from step 5)
7. Repeat the exact GET → decode → append → encode → PUT sequence from Sections 5–7 above, substituting:
   - The URL from step 3 of this section (weight-log.json, not health-daily.json).
   - "Today's Record" = the small Dictionary from step 6 of this section.
8. Add the same success/failure If-check and Show Notification from Section 8.
9. Skip the Automation setup — this one is meant to be run manually (tap it from the Shortcuts app, or add it to your Home Screen / Apple Watch face as a complication for one-tap logging right after you weigh yourself).
10. Test it the same way as Section 11: run once, check github.com for the new record, verify the JSON is well-formed.

You now have two independent, single-purpose shortcuts, each with its own copy of the token in its own Text action — if you ever rotate the PAT, remember to update it in **both** places.
