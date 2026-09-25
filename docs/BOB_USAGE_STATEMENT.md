# assisted-by: IBM Bob 2.0 final-polish — Bob usage statement, task 2026-09-25
# PreFlight — How IBM Bob Was Used

All claims in this document are sourced from BOB_USAGE.md.

## Planning

Bob was used in Plan mode to design the full system before writing any code.
It produced `docs/PLAN.md` covering the module layout, data flow diagram, report
JSON schema, parallel subagent delegation table, and a seven-task plan. This
planning phase established inter-module contracts (models.py as the single source
of truth, fixtures/report.json as the shared integration fixture) before any
code was written.

## Sample Repository

Bob built the `sample-repo/` nested git repository in a single task: a realistic
FastAPI Orders API with ORM models, pricing module, config layer, migrations,
tests, README, and .env.example. It staged 21 commits across two annotated tags
(v1.0.0 and v1.1.0) and deliberately planted four issues in the diff. No
parallel subagents were used in this task.

## Parallel Subagents — Phase 3a

The main agent wrote `app/models.py`, `app/gitutil.py`, and
`tests/fixtures/report.json` first. Then three subagents ran in parallel:

- **DIFF ENGINE** wrote `app/diff_engine.py` and `tests/test_diff_engine.py`
  (23 tests).
- **COVERAGE MAPPER** wrote `app/coverage.py` and `tests/test_coverage.py`
  (28 tests).
- **SENTINEL** wrote `app/sentinel.py` and `tests/test_sentinel.py` (11 tests).

All 51 tests passed. All four planted issues were confirmed found.

## Parallel Subagents — Phase 3b

Two subagents ran in parallel:

- **DRAFTER** wrote `app/drafter.py` (7 tests).
- **DASHBOARD** wrote `app/static/index.html`.

The main agent then wrote `app/report.py` (orchestrator with risk score), 
`app/main.py` (FastAPI routes), and `run.sh`. All 80 tests passed at this point.

## Quality-Fix Tasks

Bob ran several targeted quality-fix tasks after the initial build. These were
driven by Bob identifying its own gaps after reviewing test results and
end-to-end smoke tests:

- **Function-level gap detection**: coverage analysis was upgraded from
  module-level to function-level, naming each untested function in the gap
  reason. Stub generation was updated to emit one skeleton test per untested
  function.
- **Docstring-safe diff rules**: a new AST rule marked docstring/comment-only
  Python changes as safe (not risky), fixing a false positive for `app/config.py`.
- **Risk score calibration**: the hard cap was replaced with a diminishing-returns
  formula. Root-cause deduplication was added so route files affected only by a
  schema change score lower than independently breaking files.
- **Repo-path test existence**: the stub generation path check was corrected to
  use the analyzed repository path instead of the current working directory.
- **Range validation**: `build_report()` now validates that `from` is a strict
  git ancestor of `to`, returning HTTP 400 on invalid input.
- **Dropdown direction fix**: the tag-selector auto-adjust in the dashboard was
  corrected to handle the newest-first ordering of the tag list.

After these tasks the test count grew from 51 to 117, then to 121.

## Summary of Parallelism

Phase 3a used three parallel subagents (A, B, C). Phase 3b used two (D, E).
All other tasks were handled by the main agent without subagents, as recorded
in BOB_USAGE.md.

---

*Word count: 463*
