# AGENTS.md — PreFlight Project Rules

## Project

**PreFlight** is a Release Risk Auditor. It takes two git tags of a project
(e.g. `v1.0.0..v1.1.0`), analyzes everything that changed, and produces a
**Release Readiness Report** in a local web dashboard:

- Risk-classified changes
- Test coverage gaps
- Migration / config / env mismatches
- Auto-drafted release notes
- Rollback plan

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3 + FastAPI |
| Frontend | Single-file HTML/JS dashboard (no build tooling, no npm) |
| Git access | gitpython |
| Analysis | Deterministic — git, regex, Python `ast`. No LLM calls at runtime. |
| Services | Zero external services |

> If a part of the stack fights you for more than 15 minutes, simplify it.

---

## Non-Goals

- No auth, accounts, or database servers
- No cloud services or CI/CD integrations
- Do not refactor or improve code outside the scope of the current task
- PreFlight must **never** import or depend on `/sample-repo`; the repo path is
  a runtime parameter (`PREFLIGHT_REPO` env var, default `./sample-repo`)

---

## Conventions

1. **Header comment** — Add `# assisted-by: IBM Bob 2.0 <task>` to every file
   you create or materially change.
2. **Usage log** — Append every task to `BOB_USAGE.md`:
   date · task · what it did · files touched · whether parallel subagents were
   used.
3. **Git discipline** — One commit per logical step with a clear message.
4. **Task wrap-up** — Every task ends with: what was done, files touched, what
   remains.
5. **Fail-fast** — If a step still fails after two fix attempts, stop and
   report your best diagnosis instead of looping.
6. **Security** — Never write credentials or API keys into any file.
7. **Budget** — Bobcoin budget is small; keep tasks focused and flag when a
   task is expensive.

---

## Cut Order (if behind schedule)

Cut in this order; the first three are optional, the last three are not:

| Priority | Section | Cuttable? |
|---|---|---|
| Cut first | Rollback plan section | ✂ yes |
| Cut second | Coverage stubs | ✂ yes |
| Cut third | Dashboard polish | ✂ yes |
| **Non-negotiable** | Diff engine | ✗ no |
| **Non-negotiable** | Sentinel | ✗ no |
| **Non-negotiable** | Dashboard with real data | ✗ no |
