# PreFlight — Release Risk Auditor: Build Plan
<!-- assisted-by: IBM Bob 2.0 Phase 1 Planning -->

## Overview

PreFlight accepts two git tags (`from`, `to`), analyses everything that changed
between them, and returns a single JSON **Release Readiness Report** served by a
FastAPI backend and rendered in a zero-build HTML dashboard.

The workspace currently contains only `AGENTS.md`. All files are net-new.

---

## 1. File / Module Layout

```
preflight/
├── app/
│   ├── models.py          # Pydantic schemas — single source of truth for the report JSON
│   ├── gitutil.py         # Tag enumeration + ChangeSet builder (files, status, patches, content)
│   ├── diff_engine.py     # Risk-classifies each changed file → changes[]
│   ├── coverage.py        # Identifies test-coverage gaps → coverage{}
│   ├── sentinel.py        # Detects migrations, breaking API, env/config changes → sentinel{}
│   ├── drafter.py         # Produces release notes, changelog, rollback steps → drafts{}
│   ├── report.py          # Orchestrator: merges findings, computes risk score, returns Report
│   └── main.py            # FastAPI app: GET /api/tags, GET /api/report?from=&to=
├── app/static/
│   └── index.html         # Single-file dashboard — fetches /api/report, renders all sections
├── tests/
│   ├── fixtures/
│   │   └── report.json    # Canonical fixture matching the full schema (used by DRAFTER + DASHBOARD)
│   ├── test_diff_engine.py
│   ├── test_coverage.py
│   ├── test_sentinel.py
│   └── test_report.py
├── sample-repo/           # Tiny git repo with tagged commits used for end-to-end smoke tests
├── run.sh                 # pip install -r requirements.txt && uvicorn app.main:app --port 8000
├── requirements.txt
├── README.md
├── BOB_USAGE.md
└── docs/
    ├── PLAN.md            # ← this file
    └── DEMO_SCRIPT.md
```

---

## 2. Data Flow

```
GET /api/report?from=v1.0.0&to=v1.1.0
        │
        ▼
  gitutil.build_changeset(from, to)
        │  returns ChangeSet
        │  (commits, per-file: path, status, patch, old_content, new_content)
        │
   ┌────┴─────────────────────────────────┐
   │             (independent)            │
   ▼                ▼                     ▼
diff_engine     coverage.py          sentinel.py
  .analyse()     .analyse()            .analyse()
   │                │                     │
   └────────┬────────────────────────────┘
            ▼
        report.py
         • merges changes[], coverage{}, sentinel{}
         • calls drafter.draft(changeset, changes, sentinel)
         • computes risk score
         • returns Report (validated by Pydantic)
            │
            ▼
     JSON response → index.html dashboard
```

---

## 3. Report JSON Schema

```jsonc
{
  "range": {
    "from": "v1.0.0",
    "to":   "v1.1.0",
    "commits": 12,
    "files_changed": 7
  },
  "risk": {
    "score": 42,                       // 0-100, capped
    "level": "medium",                 // low|medium|high|critical
    "drivers": [
      { "label": "breaking change in api.py", "points": 25 }
    ]
  },
  "changes": [
    {
      "path": "app/api.py",
      "status": "modified",            // added|modified|deleted|renamed
      "risk": "breaking",              // breaking|risky|safe
      "reason": "Public function signature changed",
      "lines_added": 10,
      "lines_removed": 3
    }
  ],
  "coverage": {
    "gaps": [
      { "path": "app/api.py", "reason": "No test imports this module", "suggested_test": "tests/test_api.py" }
    ],
    "covered": [
      { "path": "app/util.py", "tests": ["tests/test_util.py"] }
    ],
    "stubs": [
      { "path": "tests/test_api.py", "content": "# TODO: test api.py\n" }
    ]
  },
  "sentinel": {
    "findings": [
      {
        "kind": "migration_no_code",   // migration_no_code|api_breaking|env_undocumented|config_key_added
        "severity": "high",            // high|medium|low
        "location": "db/migrations/0002.sql",
        "detail": "Migration file added but no corresponding model change detected",
        "evidence": "CREATE TABLE ..."
      }
    ]
  },
  "drafts": {
    "release_notes_md": "## v1.1.0\n...",
    "changelog_md": "### Changed\n...",
    "rollback_steps": [
      { "step": 1, "action": "Revert tag to v1.0.0", "reason": "Breaking API change present" }
    ]
  }
}
```

### Score Weights

| Signal | Points |
|---|---|
| Each `breaking` change | +25 |
| Each `risky` change | +10 |
| Sentinel finding — `high` | +20 |
| Sentinel finding — `medium` | +10 |
| Sentinel finding — `low` | +4 |
| Each coverage gap | +8 |
| **Cap** | 100 |

**Level bands:** 0-24 → low · 25-49 → medium · 50-74 → high · 75+ → critical

---

## 4. Parallel Subagent Delegation

The **main agent** writes `app/models.py` and `app/gitutil.py` first because
every subagent depends on them. The fixture `tests/fixtures/report.json` is also
written by the main agent so DRAFTER and DASHBOARD can build independently.

| Subagent | Files owned | Depends on |
|---|---|---|
| **DIFF ENGINE** | `app/diff_engine.py`, `tests/test_diff_engine.py` | models.py, gitutil.py |
| **COVERAGE MAPPER** | `app/coverage.py`, `tests/test_coverage.py` | models.py, gitutil.py |
| **SENTINEL** | `app/sentinel.py`, `tests/test_sentinel.py` | models.py, gitutil.py |
| **DRAFTER** | `app/drafter.py`, `app/report.py`, `tests/test_report.py` | models.py, fixture report.json |
| **DASHBOARD** | `app/static/index.html`, `docs/DEMO_SCRIPT.md` | fixture report.json |

After all subagents complete, the main agent writes `app/main.py`, `run.sh`,
`requirements.txt`, `README.md`, and wires everything together.

---

## 5. Task List (Bobcoin-aware — one context window each)

- [x] **T1 — Foundation** (main agent): Create `app/models.py` (all Pydantic models matching section 3), `app/gitutil.py` (git tag list + ChangeSet builder via gitpython), `tests/fixtures/report.json` (canonical fixture), `requirements.txt`, `sample-repo/` scaffold with two tagged commits. Status: `done`

- [x] **T2 — Diff Engine** (subagent DIFF ENGINE): Implement `app/diff_engine.py` — parse patches from ChangeSet, classify each file as breaking / risky / safe using AST diffing and heuristics (public API changes, deletions, signature changes). Write `tests/test_diff_engine.py`. Status: `done`

- [x] **T3 — Coverage Mapper** (subagent COVERAGE MAPPER): Implement `app/coverage.py` — walk changed files, map to test files by naming convention and import scanning, identify gaps, generate stub content. Write `tests/test_coverage.py`. Status: `done`

- [x] **T4 — Sentinel** (subagent SENTINEL): Implement `app/sentinel.py` — detect migration files without model changes, env vars not in `.env.example`, new config keys, removed public symbols. Write `tests/test_sentinel.py`. Status: `done`

- [x] **T5 — Drafter + Orchestrator** (subagent DRAFTER): Implement `app/drafter.py` (template-based release notes, changelog, rollback steps) and `app/report.py` (merge all analyzer outputs, score computation, return Report). Write `tests/test_report.py` using the fixture. Status: `done`

- [x] **T6 — Dashboard** (subagent DASHBOARD): Implement `app/static/index.html` — single-file, no build tools, renders all report sections from `/api/report` JSON. Write `docs/DEMO_SCRIPT.md`. Status: `done`

- [x] **T7 — Wiring + Smoke Test** (main agent): Implement `app/main.py` (FastAPI routes), `run.sh`, `README.md`, `BOB_USAGE.md` entry. Run full smoke test against `sample-repo/`. Fix any integration issues. Status: `done`

---

## Open Questions / Decisions Already Made

- **No LLM at runtime** — all analysis is deterministic (git, regex, Python AST).
- **No database** — report is computed on-demand per request.
- **sample-repo/** is never imported by the app; it is a runtime parameter only.
- DRAFTER and DASHBOARD build against the fixture until real analyzers land (T2–T4).
- Tests use pytest; no coverage tool required beyond the app's own coverage logic.
