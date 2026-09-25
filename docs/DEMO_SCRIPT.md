<!-- assisted-by: IBM Bob 2.0 final-polish (first draft); revised by the developer -->
# PreFlight — Demo Video Script (3 minutes maximum)

Rules from the hackathon: maximum 3 minutes, at least 90 seconds of the solution running on screen,
narration, and a clear demonstration of how IBM Bob was used. Lines marked **SAY** are the narration
(about 350 words, roughly 2.5 minutes at a calm pace, leaving time for screen actions).

Before recording: run `run.bat`, open http://127.0.0.1:8000, zoom the browser to 100% or 110%,
close other windows, and do one practice take.

---

## 0:00 – 0:20 · The problem

**SCREEN:** a terminal running `git -C sample-repo diff v1.0.0 v1.1.0 --stat`, showing ten changed files.

**SAY:** "Before every release, someone has to review every changed file. Does each migration have
matching code? Is every new environment variable documented? Does every new function have a test?
Doing that by hand is slow, and things get missed. PreFlight does it in a second."

## 0:20 – 2:15 · Live demo (115 seconds on screen)

### 0:20 · Start
**SCREEN:** Windows terminal, type `run.bat`, then the browser opens the dashboard.

**SAY:** "One command starts everything locally: no cloud, no API keys. This is a sample orders API
with four problems planted between version 1.0.0 and 1.1.0."

### 0:35 · Run
**SCREEN:** the tag boxes (From v1.0.0, To v1.1.0), click **Run Analysis**.

**SAY:** "From is the older tag, To the newer one. Run analysis. The report is ready in under a second."

### 0:45 · Risk score
**SCREEN:** the Risk Score card: 82, CRITICAL, and the list of drivers.

**SAY:** "Risk score: 82, critical. The drivers explain why: the renamed total field is a breaking
change, plus a migration with no code and an undocumented environment variable."

### 1:00 · Changed files
**SCREEN:** the Changed Files card; point at `app/config.py` (safe) and `app/pricing.py` (risky).

**SAY:** "Every changed file is classified breaking, risky or safe, with a reason. The docstring-only
change to config is correctly safe, and the pricing module is flagged for a new public function."

### 1:15 · Coverage
**SCREEN:** the Coverage card; open the `tests/test_pricing.py` stub.

**SAY:** "Coverage gaps: calculate_total_cents was added to pricing, but the existing pricing tests
never call it. PreFlight even generates the test to add."

### 1:30 · Sentinel
**SCREEN:** the Sentinel Findings card, three HIGH items; click "Show evidence" on one.

**SAY:** "Sentinel found three high-severity problems. One: the migration adds a discount_code
column, but no code uses it. Two: the response field total was removed, which breaks existing API
clients. Three: the payment webhook secret is read from the environment, but missing from dot-env example."

### 1:55 · Notes, fixes, rollback
**SCREEN:** scroll through Release Notes, Fix Before Release and Rollback Plan.

**SAY:** "It drafts release notes from the commit messages, lists what to fix before release, and gives
an ordered rollback plan: revert the migration, revert the code, redeploy the previous tag, verify."

---

## 2:15 – 3:00 · How IBM Bob was used

**SCREEN:** the Bob IDE, then two or three screenshots from `bob_sessions/` (planning summary, parallel build summary, quality fixes summary), then the terminal showing `python -m pytest tests -q` with 121 passed.

**SAY:** "I built PreFlight with IBM Bob 2.0. In Plan mode, Bob designed the architecture. In Agent mode it
built the sample repo, then ran three subagents in parallel for the diff engine, coverage mapper and
sentinel, and later two more for the drafter and the dashboard. After each phase I reviewed the output,
found problems, like a wrong coverage reason and a risk score stuck at 100, and had Bob fix them.
The result: 121 passing tests and zero external services. PreFlight: ship with confidence."

---

## Recording tips

- Speak slowly, and pause while something loads. Trim silence when editing.
- Keep the total under 3:00. Judges will not watch past that.
- Show your voice and screen only; appearing on camera is optional.
- Export as MP4.
