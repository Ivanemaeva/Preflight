# assisted-by: IBM Bob 2.0 Phase 3b — risk score tests
"""Tests for app/report.py — compute_risk_score and build_report orchestration.

Covers:
- high/critical score with the four planted issues
- low score with only safe changes
- no double-counting when diff engine + sentinel flag same file
"""

from __future__ import annotations

import os
from typing import List

import pytest

from app.models import (
    Coverage,
    CoverageGap,
    FileChange,
    Sentinel,
    SentinelFinding,
)
from app.report import build_report, compute_risk_score


# ---------------------------------------------------------------------------
# Helpers — build minimal model objects
# ---------------------------------------------------------------------------

def _fc(path: str, risk: str, status: str = "modified") -> FileChange:
    return FileChange(path=path, status=status, risk=risk, reason="test")  # type: ignore[arg-type]


def _gap(path: str) -> CoverageGap:
    return CoverageGap(path=path, reason="no test", suggested_test=f"tests/test_{path}.py")


def _sentinel(kind: str, severity: str, location: str) -> SentinelFinding:
    return SentinelFinding(kind=kind, severity=severity, location=location, detail="d", evidence="e")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test 1 — sample release (v1.0.0..v1.1.0) scores high or critical but < 100
# ---------------------------------------------------------------------------

class TestSampleReleaseScore:
    """The planted issues must push the score to high or critical (>= 50)."""

    def test_sample_release_scores_high_or_critical(self) -> None:
        """build_report against sample-repo v1.0.0..v1.1.0 must score >= 50.
        The four planted issues (2 breaking changes, migration_no_code, env_undocumented,
        2 coverage gaps) produce enough raw points that the capped score is critical.
        """
        repo = os.getenv("PREFLIGHT_REPO", "./sample-repo")
        report = build_report("v1.0.0", "v1.1.0", repo)
        assert report.risk.score >= 50, (
            f"Expected high/critical (>=50), got {report.risk.score} ({report.risk.level})"
        )
        assert report.risk.level in ("high", "critical"), (
            f"Expected high or critical, got {report.risk.level}"
        )

    def test_sample_release_four_planted_issues(self) -> None:
        """All four planted issues must appear somewhere in the report."""
        repo = os.getenv("PREFLIGHT_REPO", "./sample-repo")
        report = build_report("v1.0.0", "v1.1.0", repo)

        # 1. migration_no_code
        kinds = {f.kind for f in report.sentinel.findings}
        assert "migration_no_code" in kinds, "migration_no_code finding missing"

        # 2. api_breaking or breaking diff
        has_breaking_diff = any(c.risk == "breaking" for c in report.changes)
        has_api_breaking_sentinel = "api_breaking" in kinds
        assert has_breaking_diff or has_api_breaking_sentinel, (
            "No breaking change detected (neither diff engine nor sentinel)"
        )

        # 3. env_undocumented
        assert "env_undocumented" in kinds, "env_undocumented finding missing"

        # 4. coverage gap for pricing or webhooks
        gap_paths = {g.path for g in report.coverage.gaps}
        assert any("pricing" in p or "webhook" in p for p in gap_paths), (
            f"Expected pricing/webhooks coverage gap, got: {gap_paths}"
        )


# ---------------------------------------------------------------------------
# Test 2 — safe release scores low
# ---------------------------------------------------------------------------

class TestSafeReleaseScore:
    """A release with only safe changes and no sentinel findings scores low."""

    def test_only_safe_changes_scores_low(self) -> None:
        changes: List[FileChange] = [
            _fc("README.md", "safe"),
            _fc("app/config.py", "safe"),
        ]
        cov = Coverage()
        sent = Sentinel()
        score, level, drivers = compute_risk_score(changes, sent, cov)
        assert score == 0, f"Expected 0, got {score}"
        assert level == "low"
        assert drivers == []


# ---------------------------------------------------------------------------
# Test 3 — no double-counting
# ---------------------------------------------------------------------------

class TestNoDoubleCount:
    """If diff engine AND sentinel both flag the same file for the same issue,
    we must NOT count the sentinel points on top of the diff engine points."""

    def test_breaking_plus_api_breaking_sentinel_not_doubled(self) -> None:
        """diff engine says app/schemas.py is 'breaking' (+25 pts).
        sentinel says api_breaking on the same file.
        The sentinel api_breaking for that file must NOT add another +20 pts.
        """
        changes: List[FileChange] = [
            _fc("app/schemas.py", "breaking"),
        ]
        sent = Sentinel(findings=[
            _sentinel("api_breaking", "high", "app/schemas.py"),
        ])
        cov = Coverage()
        score, level, drivers = compute_risk_score(changes, sent, cov)

        # Only the diff-engine breaking +25 should count; sentinel skipped.
        assert score == 25, (
            f"Expected 25 (no double-count), got {score}. "
            f"Drivers: {[(d.label, d.points) for d in drivers]}"
        )
        # Only one driver (the diff engine one)
        assert len(drivers) == 1

    def test_separate_sentinel_kind_still_counted(self) -> None:
        """migration_no_code sentinel on a file is NOT the same as 'breaking' diff,
        so it must still be counted even if that file is also 'breaking'."""
        changes: List[FileChange] = [
            _fc("migrations/0003.sql", "risky", "added"),
        ]
        sent = Sentinel(findings=[
            _sentinel("migration_no_code", "high", "migrations/0003.sql"),
        ])
        cov = Coverage()
        score, level, drivers = compute_risk_score(changes, sent, cov)

        # risky +10 + migration_no_code high +20 = 30
        assert score == 30, f"Expected 30, got {score}"
        assert len(drivers) == 2


# ---------------------------------------------------------------------------
# Test 4 — level band boundaries
# ---------------------------------------------------------------------------

class TestLevelBands:
    """Check the four level bands."""

    def _score(self, pts: int) -> tuple[int, str]:
        # Build exactly pts worth of risky changes
        n = pts // 10
        changes = [_fc(f"f{i}.py", "risky") for i in range(n)]
        score, level, _ = compute_risk_score(changes, Sentinel(), Coverage())
        return score, level

    def test_low_band(self) -> None:
        score, level = self._score(0)
        assert level == "low"

    def test_medium_band(self) -> None:
        score, level = self._score(30)
        assert level == "medium"

    def test_high_band(self) -> None:
        score, level = self._score(60)
        assert level == "high"

    def test_critical_band(self) -> None:
        score, level = self._score(80)
        assert level == "critical"

    def test_cap_at_100(self) -> None:
        # 20 breaking changes = 500 raw points; must cap at 100
        changes = [_fc(f"f{i}.py", "breaking") for i in range(20)]
        score, level, _ = compute_risk_score(changes, Sentinel(), Coverage())
        assert score == 100
        assert level == "critical"
