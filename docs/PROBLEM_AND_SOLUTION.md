<!-- assisted-by: IBM Bob 2.0 final-polish (first draft); revised by the developer -->
# PreFlight — Problem and Solution

## The problem

Before a team ships a new version, someone has to review the release by hand. They compare the diff
and ask the same questions every time. Does each database migration have matching application
code? Is every new environment variable documented? Does every new function have a test? Did a
public API change break the clients that use it?

This review is slow, repetitive and easy to get wrong under time pressure, and the cost of a miss is
high. A migration with no code behind it, an undocumented environment variable that makes a new
deployment fail at runtime, a renamed API field that breaks every client with no version bump, or an
untested pricing function are all visible in the diff before the release ships. They still reach
production because nobody has time to check them systematically.

## The solution

PreFlight is a local release risk auditor. The user picks two git tags in a small web dashboard, and
PreFlight analyses everything that changed between them and produces a Release Readiness Report:

- **A risk score from 0 to 100** with a level (low, medium, high, critical) and the list of drivers behind the number.
- **Every changed file classified** as breaking, risky or safe, with a specific reason. Docstring-only and test-only changes are recognised as safe, so the report is not noisy.
- **Test coverage gaps at function level**, for example "calculate_total_cents() was added but no test calls it", with a generated stub test.
- **Migration, config and environment mismatches** from the Sentinel: a migration with no matching code, an environment variable missing from `.env.example`, and breaking API response changes.
- **Drafted release notes and changelog**, built from the commit messages, plus a "fix before release" list and an ordered rollback plan.

The analysis is deterministic (git, Python AST and regular expressions). It uses no cloud services, no
external APIs and no language model at runtime, so it runs offline in under a second: about 0.05 s
for the sample release, measured on the API.

## Demonstration

The included sample repository is a small orders API with two tagged releases. Between v1.0.0 and
v1.1.0 four realistic problems were planted: a migration with no matching code, a backward-incompatible
API field rename, an undocumented environment variable, and a new function with no test. PreFlight finds
all four and rates the release 82 out of 100, critical. Its 121 automated tests cover the analysis logic.

## Scope and limits

PreFlight targets Python / FastAPI-style projects with SQL migrations, and it was tested on the
included sample repository. It highlights risks for a human reviewer and does not replace the review.
