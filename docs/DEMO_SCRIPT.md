# assisted-by: IBM Bob 2.0 final-polish — demo script, task 2026-09-25
# PreFlight — Demo Video Script (3 minutes)

Total runtime: 3 minutes. Narration lines are in *italic*. On-screen actions are
in **bold**. Timestamps are minimum-to-maximum for each segment.

---

## 0:00 – 0:30 · The Problem

**[Screen: a Git diff of a real-looking Python file, then a spreadsheet with a
manual release checklist visible]**

*Before you ship a new version you have to review every changed file, check
that new migrations have matching model code, confirm that new environment
variables are documented, and verify that every new function has a test. That's
10 to 30 minutes of careful work for a medium-sized release — and humans still
miss things.*

**[Screen: cut to a post-mortem incident card: "v1.1.0 broke the orders API in
production — total_cents field was renamed but clients weren't notified"]**

*One missed breaking change. One undocumented env var. One schema migration with
no code. Any of these can take down a production service. PreFlight catches all
of them in seconds.*

---

## 0:30 – 2:15 · Live Dashboard Demo

### 0:30 · Start the server

**[Screen: terminal on Windows]**

```
run.bat
```

*One command installs dependencies and starts the server on
localhost port 8000. No cloud services, no API keys.*

**[Browser opens to http://127.0.0.1:8000]**

### 0:45 · Choose tags and run

**[Screen: PreFlight dashboard, tag selector controls in focus]**

*From is pre-set to the oldest tag, v1.0.0. To is pre-set to the newest,
v1.1.0. That's our sample Orders API with four deliberately planted issues.*

**[Click "Run Analysis" button]**

*One second. The report is back.*

### 0:55 · Risk score

**[Screen: large "82 — CRITICAL" gauge at the top of the report]**

*Risk score 82 out of 100 — critical. This release needs attention before it
ships.*

### 1:00 · Score drivers

**[Screen: Risk Drivers section, two rows highlighted — "breaking change:
app/schemas.py", "breaking change: app/routes/orders.py"]**

*The two biggest drivers are both breaking changes — a renamed and retype'd
field in the response schema. That's 50 risk points right there.*

### 1:10 · Changed files

**[Screen: Changed Files table, scroll to app/schemas.py row]**

*Changed Files shows each file's risk level and the reason. Here:
"New public function(s) added: OrderResponse" — and the schema change is
flagged breaking.*

**[Hover over app/routes/orders.py row]**

*The route file is also breaking — because it exposes the schema that changed.*

### 1:25 · Coverage gap

**[Screen: Coverage Gaps section, app/pricing.py row highlighted]**

*Coverage Gaps identifies that calculate\_total\_cents() was added in
app/pricing.py, but tests/test\_pricing.py exists and never calls it. The
suggested test stub is right there to copy in.*

### 1:38 · Sentinel findings

**[Screen: Sentinel Findings section, three rows visible]**

*Sentinel found three issues. First: a migration file — migrations/0003 adds a
discount\_code column — but no matching model change was detected. That's a
schema-code mismatch.*

**[Scroll to second row]**

*Second: the API response field total was renamed to total\_cents and changed
type from float to int. That's a breaking change with no version bump.*

**[Scroll to third row]**

*Third: the environment variable DISCOUNT\_RATE is used in app/pricing.py but
it's not in .env.example. Any new deployment will fail silently at runtime.*

### 1:55 · Release notes and pre-release fixes

**[Screen: Release Notes card]**

*PreFlight auto-drafts the release notes from the git commit messages, grouped
by type: Features, Breaking Changes, Database migrations. Ready to paste into
your changelog.*

**[Screen: Fix Before Release card]**

*And here's the pre-release fix list — three action items that must be resolved
before this release is safe to ship: document DISCOUNT\_RATE in .env.example,
add a test for calculate\_total\_cents, and version-bump the API.*

### 2:07 · Rollback plan

**[Screen: Rollback Plan card]**

*If you do ship and need to roll back: step 1 revert the migration, step 2 git
checkout v1.0.0, step 3 redeploy, step 4 verify. Concrete, ordered, no guessing.*

---

## 2:15 – 3:00 · How IBM Bob Was Used

**[Screen: split — left side BOB_USAGE.md open, right side a Bob chat session
screenshot from bob_sessions/]**

*PreFlight was built entirely in IBM Bob 2.0 — a local AI engineering assistant
— over one day. Here's what that looked like.*

**[Screen: bob_sessions/ivane_task02_planning_summary.png.png]**

*It started in Plan mode. Bob read the requirements and produced the full
architecture — module layout, data flow diagram, report schema, and a
parallel-build strategy — before a single line of code was written.*

**[Screen: bob_sessions/ivane_task03_sample_repo_and_parallel_build_summary.png]**

*Then in Agent mode, Bob wrote the foundation files and launched three subagents
in parallel: one for the diff engine, one for the coverage mapper, one for the
sentinel. All three returned passing tests.*

*A second round of parallelism built the drafter and the dashboard
simultaneously. 80 tests passed at that milestone.*

**[Screen: bob_sessions/ivane_task04_quality_fixes_summary.png]**

*Bob then identified its own gaps — wrong heuristic direction, missing edge
cases, a hardcoded risk cap — and ran targeted fix tasks without being asked.
The test count grew from 80 to 117.*

*Total: 121 tests, five analysis modules, zero external services. And you just
saw all four planted issues caught in under two minutes.*

*PreFlight — ship with confidence.*
