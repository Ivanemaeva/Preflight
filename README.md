# assisted-by: IBM Bob 2.0 final-polish — README, task 2026-09-25
# PreFlight — Release Risk Auditor

![PreFlight dashboard](docs/dashboard.png)

**PreFlight** is a local release risk tool. Give it two git tags and it tells
you exactly what changed, what tests are missing, what config or migration
hazards were introduced, and whether the release is safe to ship — in seconds,
with zero cloud services.

---

## The Problem

Release reviews are slow and error-prone. Before shipping a new tag, engineers
must manually compare diffs, check that every migration has matching code,
confirm that new env vars are documented, and verify that every new function has
a test. Doing this by hand takes hours, misses things, and creates anxiety.
PreFlight automates the tedious parts so reviewers can focus on judgment calls.

---

## How It Works

PreFlight runs five analysis steps in sequence when you request a report:

| Step | Module | What it does |
|------|--------|--------------|
| **Diff engine** | `app/diff_engine.py` | Classifies every changed file as `breaking`, `risky`, or `safe` using Python AST diffing and heuristics. Rule 0a: test files are safe unless deleted. Rule 0b: docstring/comment-only changes are safe. Rule 4b: new public functions are flagged by name. |
| **Coverage mapper** | `app/coverage.py` | For each changed Python source file, finds the corresponding test file by naming convention and import scan, then checks that every new public function is called by at least one test. Generates skeleton stub content when gaps are found. |
| **Sentinel** | `app/sentinel.py` | Detects migration files added without matching model changes, new environment variables absent from `.env.example`, and breaking API signature changes. |
| **Drafter** | `app/drafter.py` | Builds human-readable release notes (grouped by conventional-commit type), a changelog, a list of pre-release fixes, and ordered rollback steps from real git commits and findings. |
| **Orchestrator** | `app/report.py` | Merges all findings, de-duplicates overlapping signals, and computes a 0–100 risk score using diminishing returns (`score = round(100 * (1 - exp(-raw/80)))`). Level bands: 0–24 low · 25–49 medium · 50–74 high · 75+ critical. |

The FastAPI backend (`app/main.py`) exposes two endpoints:

- `GET /api/tags` — returns the list of git tags (newest first).
- `GET /api/report?from=<tag>&to=<tag>` — runs the full analysis and returns a
  JSON report.

The frontend (`app/static/index.html`) is a single-file HTML/JS dashboard with
no build step. It fetches the JSON, renders the risk gauge, changed-files table,
coverage gaps, sentinel findings, release notes, and rollback plan.

---

## Running on Windows

```bat
run.bat
```

If `sample-repo/` does not exist, the script clones it from `sample-repo.bundle`
before starting the server.

Optional: pass an alternative repo path as the first argument:

```bat
run.bat C:\path\to\your-repo
```

---

## Running on Linux / macOS

```bash
chmod +x run.sh
./run.sh
```

Same behaviour: clones from `sample-repo.bundle` if `sample-repo/` is absent.

Optional:

```bash
./run.sh /path/to/your-repo
```

---

## Using PreFlight

1. Start the server (see above). It will install dependencies and launch on
   `http://127.0.0.1:8000`.
2. Open `http://127.0.0.1:8000` in your browser.
3. Choose a **From** tag (older release) and a **To** tag (newer release).
4. Click **Run Analysis**.
5. The dashboard renders the risk score, ranked change drivers, changed files
   with risk classification, coverage gaps, sentinel findings, release notes,
   pre-release fix checklist, and rollback plan.

---

## The Four Planted Issues in `sample-repo`

The included `sample-repo` is a realistic FastAPI Orders API with exactly four
deliberate problems in the `v1.0.0 → v1.1.0` diff. PreFlight catches all four:

| Issue | What it is | Where PreFlight catches it |
|-------|-----------|---------------------------|
| **Schema migration without code** | `migrations/0003_add_discount_code.sql` adds a `discount_code` column but no model field was added. | Sentinel · `migration_no_code` finding |
| **Breaking API rename** | `OrderResponse.total` was renamed to `total_cents` and changed type from `float` to `int` — no version bump. | Diff engine · `breaking` · Sentinel · `api_breaking` |
| **Undocumented env var** | `DISCOUNT_RATE` is used in `app/pricing.py` but not listed in `.env.example`. | Sentinel · `env_undocumented` |
| **Untested pricing change** | `calculate_total_cents()` was added in `app/pricing.py` with no test calling it, despite `tests/test_pricing.py` existing. | Coverage mapper · gap with function-level reason |

---

## Report JSON Schema (short form)

```jsonc
{
  "range":    { "from": "v1.0.0", "to": "v1.1.0", "commits": 12, "files_changed": 7 },
  "risk":     { "score": 82, "level": "critical", "drivers": [ ... ] },
  "changes":  [ { "path": "...", "status": "modified", "risk": "breaking", "reason": "..." } ],
  "coverage": {
    "gaps":    [ { "path": "...", "reason": "...", "suggested_test": "..." } ],
    "covered": [ { "path": "...", "tests": ["..."] } ],
    "stubs":   [ { "path": "...", "content": "# Auto-generated stub ..." } ]
  },
  "sentinel": {
    "findings": [ { "kind": "migration_no_code", "severity": "high", "location": "...", "detail": "...", "evidence": "..." } ]
  },
  "drafts": {
    "release_notes_md": "## v1.1.0\n...",
    "changelog_md":     "### Changed\n...",
    "pre_release_fixes": [ "..." ],
    "rollback_steps":   [ { "step": 1, "action": "...", "reason": "..." } ]
  }
}
```

Full schema is defined in [`app/models.py`](app/models.py).

---

## Running the Tests

```bash
python -m pytest tests/ -v
```

121 tests across 5 test modules. No external services required.

---

## How IBM Bob Was Used

This project was built entirely in IBM Bob 2.0, a local AI engineering assistant.

### Planning (Plan mode)

Bob was used in Plan mode to design the full system before writing any code. It
produced `docs/PLAN.md` covering the module layout, data flow, report JSON
schema, parallel subagent delegation table, and a task list. This planning phase
prevented several integration issues later by making inter-module contracts
explicit up front.

### Building (Agent mode)

All code was written in Agent mode. The main agent wrote foundation files
(`app/models.py`, `app/gitutil.py`, `tests/fixtures/report.json`) first, then
delegated to parallel subagents.

### Parallel Subagents (Phase 3a and Phase 3b)

- **Phase 3a** — Three subagents ran in parallel: DIFF ENGINE wrote
  `app/diff_engine.py` + `tests/test_diff_engine.py`; COVERAGE MAPPER wrote
  `app/coverage.py` + `tests/test_coverage.py`; SENTINEL wrote `app/sentinel.py`
  + `tests/test_sentinel.py`. All 51 initial tests passed.
- **Phase 3b** — Two subagents ran in parallel: DRAFTER wrote `app/drafter.py`;
  DASHBOARD wrote `app/static/index.html`. The main agent then wrote the
  orchestrator (`app/report.py`) and `app/main.py`.

### Quality-Fix Tasks

After each phase Bob identified gaps itself — missing edge cases, wrong heuristic
direction, hardcoded caps — and fixed them in targeted follow-up tasks without
being told to. For example:
- It replaced the hard risk-score cap with a diminishing-returns formula
  autonomously after noticing scores were uncalibrated.
- It detected that the test-existence check was comparing against CWD instead
  of the analyzed repo path, and fixed it.
- It noticed the dropdown auto-adjust was moving tags in the wrong direction
  (newest-first list semantics), and corrected it.

### Facts from BOB_USAGE.md

All facts above are sourced from [`BOB_USAGE.md`](BOB_USAGE.md), which was
updated after every task.
