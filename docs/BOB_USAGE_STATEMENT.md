<!-- assisted-by: IBM Bob 2.0 final-polish (first draft); revised by the developer -->
# PreFlight — How IBM Bob Was Used

All application code in PreFlight was written by IBM Bob 2.0 in the Bob IDE. I directed each phase,
ran and reviewed the results, and decided what needed fixing. The task log is `BOB_USAGE.md` and the
session summary screenshots are in `bob_sessions/`.

## Plan mode

Bob first saved the project rules (stack, non-goals, conventions) in `AGENTS.md`. Then, in Plan mode
with the create-plan skill, it produced `docs/PLAN.md`: module layout, data flow, the report JSON
schema, score weights, a subagent delegation table with file ownership, and a task list sized to
the Bobcoin budget. It used an explore subagent to inspect the workspace before planning.

## Agent mode

- **Sample repository:** Bob built a realistic orders API in its own git repository, with 21 commits,
  two tags and four planted issues, and printed a table mapping each issue to its file and commit.
- **Phase 3a, parallel subagents:** Bob wrote the shared models and git utilities, then ran three subagents
  at once with separate file ownership: diff engine, coverage mapper and sentinel. It noticed a problem
  with one subagent's test fixture and fixed it, and finished with 51 passing tests and all four planted
  issues detected.
- **Phase 3b, parallel subagents:** two subagents built the drafter and the dashboard at the same time. Bob
  then wrote the orchestrator, the FastAPI API and the run scripts. 80 tests passed.

## Review and fix rounds

After each phase I ran PreFlight and reviewed the output. This found real problems, for example:

- a false coverage reason (a test file was said not to reference a module that it imports);
- harmless docstring and test changes flagged as risky;
- a risk score that always hit 100;
- stub tests that would overwrite existing test files;
- reversed tag ranges accepted by the API;
- a dashboard dropdown that adjusted in the wrong direction.

I gave Bob the list of problems. Bob implemented the fixes and their tests, and in the process caught and
corrected two failing tests of its own. The suite grew from 80 to 121 tests, and the sample release now
scores 82 (critical) instead of a saturated 100.

## Bob features used

Plan mode, Agent mode, parallel subagents with approval of each spawn, skills, the task to-do list,
project rules in `AGENTS.md`, per-task git commits and the task session summaries.

## My own changes

I unpinned the library versions in `requirements.txt` so the project installs on Python 3.13 on Windows,
and I captured the screenshots. About 27 of the 40 Bobcoins were used.
