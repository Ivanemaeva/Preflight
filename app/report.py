# assisted-by: IBM Bob 2.0 Phase 3b — orchestrator
"""Orchestrator — merges analyser outputs, computes risk score, returns Report.

Public API
----------
build_report(from_tag, to_tag, repo_path=None) -> Report
compute_risk_score(changes, sentinel, coverage) -> tuple[int, str, list[RiskDriver]]
"""

from __future__ import annotations

import os
from typing import List

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
# Score weights — per docs/PLAN.md §3
# ---------------------------------------------------------------------------

_BREAKING_PTS = 25
_RISKY_PTS = 10
_SENTINEL_HIGH = 20
_SENTINEL_MEDIUM = 10
_SENTINEL_LOW = 4
_GAP_PTS = 8
_SCORE_CAP = 100


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

    De-duplicates: if a file is flagged as 'breaking' by the diff engine AND
    by sentinel (api_breaking), the sentinel points for that same file are
    skipped — we count the max contribution once.
    """
    drivers: List[RiskDriver] = []

    # Track files already scored via diff-engine to avoid double-counting.
    breaking_paths = {c.path for c in changes if c.risk == "breaking"}

    # --- diff engine contributions ---
    for c in changes:
        if c.risk == "breaking":
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
    score = min(raw, _SCORE_CAP)
    level = _level(score)
    return score, level, drivers


def build_report(
    from_tag: str,
    to_tag: str,
    repo_path: str | None = None,
) -> Report:
    """Run all analysers against the tag range and return the full Report."""
    effective_repo = repo_path or os.getenv("PREFLIGHT_REPO", "./sample-repo")

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
