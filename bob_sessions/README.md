<!-- assisted-by: IBM Bob 2.0 final-polish (first draft); revised by the developer -->
# bob_sessions — IBM Bob task session summaries

Screenshots of the IBM Bob task session consumption summaries (task, context length, task id,
workspace and Bobcoins) for the PreFlight build. Task numbers follow the order in which the tasks
were run. The full task log is in [`../BOB_USAGE.md`](../BOB_USAGE.md).

| File | Task shown |
|------|-----------|
| `ivane_task02_planning_summary.png` | **Planning (Plan mode).** Bob produced `docs/PLAN.md`: module layout, data flow, report schema, subagent delegation and task list. |
| `ivane_task03_sample_repo_and_parallel_build_summary.png` | **Sample repository and Phase 3a.** Bob built `sample-repo/` (21 commits, two tags, four planted issues), then ran three parallel subagents (diff engine, coverage mapper, sentinel). 51 tests passed. |
| `ivane_task03_todo_list_13of13.png` | **Same task, to-do list.** All 13 steps completed. |
| `ivane_task04_quality_fixes_summary.png` | **First fix round.** Function-level coverage gaps, docstring-safe diff rules. 63 tests passed. |
| `ivane_task05_drafter_dashboard_summary.png` | **Phase 3b.** Two parallel subagents (drafter, dashboard), then the orchestrator, API and run scripts. 80 tests passed. |
| `ivane_task06_quality_fixes_2_summary.png` | **Second fix round.** Tag defaults, diminishing-returns risk score, commit-based release notes, rollback plan split, stub handling, Windows run script. 105 tests passed. |
| `ivane_task07_final_fixes_summary.png` | **Third fix round.** Repo-path test lookup, range validation (HTTP 400), merged breaking-change notes, specific diff reasons. 117 tests passed. |
| `ivane_task07_final_fixes_todo.png` | **Same task, to-do list.** All 11 steps completed. |
| `ivane_task08_polish_summary.png` | **Final polish.** Stub import fix, dropdown direction fix, `.gitignore`, `sample-repo.bundle`, MIT license, README, demo script and submission statements. 121 tests passed. |
