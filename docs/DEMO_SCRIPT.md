<!-- assisted-by: IBM Bob 2.0 final-polish (first draft); revised by the developer -->
# PreFlight — Demo Video Script (3 minutes maximum)

Hackathon rules: maximum 3 minutes, at least 90 seconds of the solution running on screen,
narration, and a clear demonstration of how IBM Bob was used.

Recorded as three clips, then joined:

| Clip | Time | What is on screen |
|------|------|-------------------|
| 1 | 0:00 – 0:20 | Terminal: list of changed files |
| 2 | 0:20 – 2:15 | Starting PreFlight and the dashboard, top to bottom |
| 3 | 2:15 – 3:00 | Bob IDE, session screenshots, tests passing |

Before recording: stop PreFlight if it is running, open a terminal in the project folder
(text enlarged with Ctrl and +), open the browser at 100% zoom, open Bob, open three screenshots
from `bob_sessions/` in Photos, close everything else and turn on Do Not Disturb.

---

## Clip 1 · 0:00 – 0:20 · The problem

**SCREEN:** in the terminal, type and run:

```
git -C sample-repo diff v1.0.0 v1.1.0 --stat
```

The list of 10 changed files stays on screen.

**SAY:** "Every release day, somebody reads through every changed file and asks the same questions
by hand. Does this migration actually have matching code? Is every new variable documented? Does
anything have a test? It's slow, and things slip through anyway. PreFlight does that whole check for you."

---

## Clip 2 · 0:20 – 2:15 · Live demo

### 0:20 · Start
**SCREEN:** in the terminal, type `.\run.bat` and press Enter. Wait for "Application startup complete"
(cut the waiting when editing). Open `http://127.0.0.1:8000` in the browser.

**SAY:** "Everything runs locally, one command. No cloud, no API keys. This is a sample orders API,
and I've planted four real problems between versions 1.0.0 and 1.1.0."

### 0:35 · Run
**SCREEN:** show From = v1.0.0 and To = v1.1.0, then click **Run Analysis**.

**SAY:** "Older tag in From, newer in To. Hit run... and the full report is ready in under a second."

### 0:45 · Risk score
**SCREEN:** the Risk Score card: 82, CRITICAL, and the list of risk drivers.

**SAY:** "Risk score 82, critical. And it tells you why. The renamed total field is a breaking change.
There's a migration that nothing uses. And an environment variable nobody documented."

### 1:00 · Changed files
**SCREEN:** scroll to the Changed Files card; point the mouse at `app/config.py` (SAFE), then at
`app/pricing.py` (RISKY).

**SAY:** "Every changed file gets classified as breaking, risky, or safe, always with a reason. That
docstring-only change in config? Correctly marked safe. The pricing module gets flagged for its new
public function."

### 1:15 · Coverage
**SCREEN:** scroll to the Coverage card; point at the `app/pricing.py` gap, then click
`tests/test_pricing.py` under Generated test stubs to open it.

**SAY:** "Coverage gaps. Calculate total cents was added, but the existing pricing tests never call it.
And PreFlight writes the missing test for you."

### 1:30 · Sentinel
**SCREEN:** scroll to the Sentinel Findings card (three HIGH findings). On the last sentence, click
**Show evidence** under one finding.

**SAY:** "Three high-severity findings. A discount code column that no code touches. A response field
that was removed, which would break every existing API client. And a webhook secret read from the
environment but missing from the example file. Let's open the evidence."

### 1:55 · Release notes, fixes, rollback
**SCREEN:** scroll slowly through Release Notes, Fix Before Release and Rollback Plan.

**SAY:** "Last section. Release notes drafted from the commit history, a short list of what to fix
before release, and a rollback plan you could literally follow step by step."

---

## Clip 3 · 2:15 – 3:00 · How IBM Bob was used

**SCREEN, in this order while speaking:**
1. The Bob IDE with the task list open (list icon at the top of the Bob panel).
2. `bob_sessions/ivane_task02_planning_summary.png` (Plan mode), a few seconds.
3. `bob_sessions/ivane_task03_sample_repo_and_parallel_build_summary.png` (parallel subagents), a few seconds.
4. `bob_sessions/ivane_task06_quality_fixes_2_summary.png` (fix round), a few seconds.
5. The terminal: press Ctrl+C, type S and Enter, then run `python -m pytest tests -q` and show "121 passed".

**SAY:** "One more thing. I built all of this with IBM Bob 2.0. Bob designed the architecture in Plan
mode, then built the sample repo and ran three subagents in parallel, one on the diff engine, one on
coverage, one on the sentinel checks. Two more joined later for the release notes and the dashboard.
I reviewed Bob's work after every phase and caught real problems, like a coverage reason that was
wrong and a risk score stuck at 100, and Bob fixed them. The result: 121 passing tests, zero external
services. PreFlight. Ship with confidence."

---

## Recording tips

- Speak calmly and pause briefly between sections; trim silences when editing.
- Keep the final video under 3:00.
- Screen and voice are enough; appearing on camera is optional.
- Export as MP4 (1080p).
