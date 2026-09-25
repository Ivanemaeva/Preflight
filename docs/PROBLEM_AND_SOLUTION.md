# assisted-by: IBM Bob 2.0 final-polish — problem and solution statement, task 2026-09-25
# PreFlight — Problem and Solution

## The Problem

Every software team that ships versioned releases faces the same friction point:
the release review. Before tagging a new version and deploying to production,
someone must manually inspect every changed file, check that schema migrations
have corresponding model code, confirm that new environment variables are listed
in documentation, and verify that every new function is tested.

For a medium-sized release this takes 20 to 40 minutes of careful, focused work.
For a large release it can take hours. The process is tedious, cognitively
expensive, and failure-prone. Engineers doing it under time pressure miss things.

The consequences of missed issues are severe. A migration file without matching
application code silently corrupts data on deploy. An undocumented environment
variable causes a new deployment to fail at runtime — often in a way that looks
unrelated to the release. A breaking API rename breaks every client that has not
been updated, with no warning and no version bump to signal the change. An
untested pricing function lets billing bugs reach production.

These are not hypothetical scenarios. They are the kinds of issues that create
post-mortem incident cards. And they are entirely predictable — they show up in
the diff before the release ships.

## The Solution

PreFlight is a local release risk tool that automates the tedious parts of
release review. It takes two git tags as input and runs five deterministic
analysis steps in under a second: a diff engine that classifies every changed
file as breaking, risky, or safe using Python AST comparison; a coverage mapper
that checks whether every new public function is referenced by a test file; a
sentinel that detects migration/code mismatches, undocumented environment
variables, and breaking API signature changes; a drafter that produces
ready-to-paste release notes and an ordered rollback plan; and an orchestrator
that merges all findings into a single risk score on a 0 to 100 scale.

The results are presented in a zero-install web dashboard. A reviewer opens a
browser, selects two tags, clicks Run Analysis, and within seconds has a
prioritised list of everything that needs attention before the release ships —
with specific file names, function names, and actionable fix suggestions.

PreFlight uses no cloud services, no external APIs, and no language model at
runtime. All analysis is deterministic: git, Python AST, and regular expressions.
It runs entirely on the developer's machine and works against any git repository.

The four issues planted in the included sample repository — a migration without
code, a breaking API rename, an undocumented env var, and an untested pricing
change — are all caught and displayed correctly in the dashboard.

---

*Word count: 393*
