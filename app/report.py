# assisted-by: IBM Bob 2.0 four-fix task — repo-path test existence, range validation, drafter dedup, diff reason, task 2026-09-25
"""Orchestrator — merges analyser outputs, computes risk score, returns Report.

Public API
----------
build_report(from_tag, to_tag, repo_path=None) -> Report
compute_risk_score(changes, sentinel, coverage) -> tuple[int, str, list[RiskDriver]]

Score design
------------
Raw points per signal:
  each 'breaking' change               → +25
  each 'risky' change                  → +10
  sentinel high / medium / low         → +20 / +10 / +4
  coverage gap                         → +8

Root-cause dedup:
  • sentinel api_breaking for a file already flagged breaking by the diff engine → skipped
  • a route/view file flagged breaking ONLY because it uses a schema that was itself
    flagged breaking by the diff engine gets +10 ("impacted by breaking schema change")
    instead of +25

Diminishing returns (replaces the hard cap):
  score = round(100 * (1 − exp(−raw / 80)))

Level bands (unchanged from PLAN.md):
  0–24 low · 25–49 medium · 50–74 high · 75+ critical
"""

from __future__ import annotations

import math
import os
from typing import List

import git

from app import coverage as coverage_mod
from app import diff_engine, sentinel as sentinel_mod
from app.drafter import draft
from app.gitutil import build_changeset
from app.models import (
    Coverage,
    FileChange,
    RangeInfo,
    Report,
    Risk,
    RiskDriver,
    Sentinel,
)


# ---------------------------------------------------------------------------
# Score weights
# ---------------------------------------------------------------------------

_BREAKING_PTS = 25
_BREAKING_IMPACTED_PTS = 10   # route affected by a breaking schema, not a root cause
_RISKY_PTS = 10
_SENTINEL_HIGH = 20
_SENTINEL_MEDIUM = 10
_SENTINEL_LOW = 4
_GAP_PTS = 8
_DIMINISHING_SCALE = 80       # controls knee of the curve


# ---------------------------------------------------------------------------
# Route/schema heuristic
# ---------------------------------------------------------------------------

_SCHEMA_PATTERNS = ("schemas.py", "schema.py", "models.py", "serializers.py")
_ROUTE_PATTERNS = ("routes/", "views/", "endpoints/", "handlers/")


def _looks_like_schema(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    return any(p.endswith(s) for s in _SCHEMA_PATTERNS)


def _looks_like_route(path: str) -> bool:
    p = path.replace("\\", "/").lower()
    return any(pat in p for pat in _ROUTE_PATTERNS)


def _level(score: int) -> str:
    if score < 25:
        return "low"
    if score < 50:
        return "medium"
    if score < 75:
        return "high"
    return "critical"


def compute_risk_score(
    changes: List[FileChange],
    sentinel: Sentinel,
    coverage: Coverage,
) -> tuple[int, str, List[RiskDriver]]:
    """Compute risk score from analyser outputs.

    De-duplication rules:
    1. sentinel api_breaking for a file already classified 'breaking' by the
       diff engine → skipped (same root cause already counted).
    2. A route file classified 'breaking' where a schema file in the same
       changeset is *also* breaking → the route gets only +10 pts
       ("impacted by breaking schema change") instead of +25.
    """
    drivers: List[RiskDriver] = []

    # Track files already scored via diff-engine to avoid double-counting.
    breaking_paths = {c.path for c in changes if c.risk == "breaking"}

    # Is there at least one breaking schema file?
    has_breaking_schema = any(_looks_like_schema(p) for p in breaking_paths)

    # --- diff engine contributions ---
    for c in changes:
        if c.risk == "breaking":
            if has_breaking_schema and _looks_like_route(c.path) and not _looks_like_schema(c.path):
                # This route is breaking because a schema it uses changed;
                # it's an impacted file, not the root cause.
                drivers.append(RiskDriver(
                    label=f"impacted by breaking schema change — {c.path}: {c.reason}",
                    points=_BREAKING_IMPACTED_PTS,
                ))
            else:
                drivers.append(RiskDriver(
                    label=f"breaking change in {c.path}: {c.reason}",
                    points=_BREAKING_PTS,
                ))
        elif c.risk == "risky":
            drivers.append(RiskDriver(
                label=f"risky change in {c.path}: {c.reason}",
                points=_RISKY_PTS,
            ))

    # --- sentinel contributions (skip api_breaking for files already counted) ---
    _severity_pts = {"high": _SENTINEL_HIGH, "medium": _SENTINEL_MEDIUM, "low": _SENTINEL_LOW}
    for f in sentinel.findings:
        # Avoid double-counting: if sentinel raises api_breaking for a path
        # that the diff engine already classified as breaking, skip it.
        if f.kind == "api_breaking" and f.location in breaking_paths:
            continue
        pts = _severity_pts.get(f.severity, _SENTINEL_LOW)
        drivers.append(RiskDriver(
            label=f"sentinel: {f.kind} — {f.location}",
            points=pts,
        ))

    # --- coverage gap contributions ---
    for gap in coverage.gaps:
        drivers.append(RiskDriver(
            label=f"coverage gap — {gap.path}: {gap.reason}",
            points=_GAP_PTS,
        ))

    raw = sum(d.points for d in drivers)
    # Diminishing returns: score = round(100 * (1 - exp(-raw / 80)))
    score = round(100 * (1 - math.exp(-raw / _DIMINISHING_SCALE)))
    level = _level(score)
    return score, level, drivers


def build_report(
    from_tag: str,
    to_tag: str,
    repo_path: str | None = None,
) -> Report:
    """Run all analysers against the tag range and return the full Report."""
    effective_repo = repo_path or os.getenv("PREFLIGHT_REPO", "./sample-repo")

    # Validate range: from must be a strict ancestor of to
    if from_tag == to_tag:
        raise ValueError("'from' must be an older tag than 'to'")
    try:
        repo = git.Repo(effective_repo)
        from_commit = repo.commit(from_tag)
        to_commit = repo.commit(to_tag)
        if not repo.is_ancestor(from_commit, to_commit):
            raise ValueError("'from' must be an older tag than 'to'")
    except git.GitCommandError as exc:
        raise ValueError(f"Invalid tag: {exc}") from exc

    changeset = build_changeset(from_tag, to_tag, effective_repo)

    changes: List[FileChange] = diff_engine.analyse(changeset)
    cov: Coverage = coverage_mod.analyse(changeset, effective_repo)
    sent: Sentinel = sentinel_mod.analyse(changeset, effective_repo)

    score, level, drivers = compute_risk_score(changes, sent, cov)

    drafts = draft(
        changeset=changeset,
        changes=changes,
        coverage=cov,
        sentinel=sent,
        to_tag=to_tag,
        from_tag=from_tag,
    )

    return Report(
        range=RangeInfo(
            **{"from": from_tag, "to": to_tag},
            commits=len(changeset.commits),
            files_changed=len(changeset.files),
        ),
        risk=Risk(score=score, level=level, drivers=drivers),
        changes=changes,
        coverage=cov,
        sentinel=sent,
        drafts=drafts,
    )
