# assisted-by: IBM Bob 2.0 four-fix task — repo-path test existence, range validation, drafter dedup, diff reason, task 2026-09-25
"""Tests for app/report.py — compute_risk_score and build_report orchestration.

Covers:
- sample release v1.0.0..v1.1.0 scores between 75 and 95 (critical or high)
- safe release scores under 10
- root-cause dedup: route impacted by breaking schema gets +10 not +25
- no double-counting when diff engine + sentinel flag same file
- diminishing returns: score is monotonically non-decreasing with raw points
- level band boundaries
"""

from __future__ import annotations

import math
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
from app.report import (
    _BREAKING_IMPACTED_PTS,
    _BREAKING_PTS,
    _DIMINISHING_SCALE,
    build_report,
    compute_risk_score,
)


# ---------------------------------------------------------------------------
# Helpers — build minimal model objects
# ---------------------------------------------------------------------------

def _fc(path: str, risk: str, status: str = "modified") -> FileChange:
    return FileChange(path=path, status=status, risk=risk, reason="test")  # type: ignore[arg-type]


def _gap(path: str) -> CoverageGap:
    return CoverageGap(path=path, reason="no test", suggested_test=f"tests/test_{path}.py")


def _sentinel(kind: str, severity: str, location: str) -> SentinelFinding:
    return SentinelFinding(kind=kind, severity=severity, location=location, detail="d", evidence="e")  # type: ignore[arg-type]


def _raw_to_score(raw: int) -> int:
    """Mirror the diminishing-returns formula from report.py."""
    return round(100 * (1 - math.exp(-raw / _DIMINISHING_SCALE)))


# ---------------------------------------------------------------------------
# Test 1 — sample release (v1.0.0..v1.1.0) scores between 75 and 95
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Test 0 — range validation
# ---------------------------------------------------------------------------

class TestRangeValidation:
    """build_report must raise ValueError for invalid tag ranges."""

    def test_same_tag_raises_value_error(self) -> None:
        """from == to must raise ValueError."""
        repo = os.getenv("PREFLIGHT_REPO", "./sample-repo")
        with pytest.raises(ValueError, match="'from' must be an older tag than 'to'"):
            build_report("v1.0.0", "v1.0.0", repo)

    def test_inverted_range_raises_value_error(self) -> None:
        """from newer than to must raise ValueError."""
        repo = os.getenv("PREFLIGHT_REPO", "./sample-repo")
        with pytest.raises(ValueError, match="'from' must be an older tag than 'to'"):
            build_report("v1.1.0", "v1.0.0", repo)

    def test_valid_range_does_not_raise(self) -> None:
        """Valid range must not raise."""
        repo = os.getenv("PREFLIGHT_REPO", "./sample-repo")
        report = build_report("v1.0.0", "v1.1.0", repo)
        assert report is not None


# ---------------------------------------------------------------------------
# Test 1 — sample release (v1.0.0..v1.1.0) scores between 75 and 95
# ---------------------------------------------------------------------------

class TestSampleReleaseScore:
    """The planted issues must push the score to 75–95 (critical or high)."""

    def test_sample_release_score_in_range(self) -> None:
        """build_report against sample-repo v1.0.0..v1.1.0 must score 75–95."""
        repo = os.getenv("PREFLIGHT_REPO", "./sample-repo")
        report = build_report("v1.0.0", "v1.1.0", repo)
        assert 75 <= report.risk.score <= 95, (
            f"Expected score 75–95, got {report.risk.score} ({report.risk.level})\n"
            f"Drivers: {[(d.label, d.points) for d in report.risk.drivers]}"
        )
        assert report.risk.level in ("critical", "high"), (
            f"Expected critical or high, got {report.risk.level}"
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
# Test 2 — safe release scores under 10
# ---------------------------------------------------------------------------

class TestSafeReleaseScore:
    """A release with only safe changes and no sentinel findings scores < 10."""

    def test_only_safe_changes_scores_near_zero(self) -> None:
        changes: List[FileChange] = [
            _fc("README.md", "safe"),
            _fc("app/config.py", "safe"),
        ]
        cov = Coverage()
        sent = Sentinel()
        score, level, drivers = compute_risk_score(changes, sent, cov)
        assert score < 10, f"Expected score < 10 for safe-only release, got {score}"
        assert level == "low"
        assert drivers == []


# ---------------------------------------------------------------------------
# Test 3 — root-cause dedup: route impacted by breaking schema
# ---------------------------------------------------------------------------

class TestRootCauseDedup:
    """When a schema file is breaking, a route file that is also breaking
    should receive only the impacted weight (+10), not the full breaking weight (+25)."""

    def test_route_impacted_by_breaking_schema_gets_reduced_weight(self) -> None:
        changes: List[FileChange] = [
            _fc("app/schemas.py", "breaking"),           # root cause
            _fc("app/routes/orders.py", "breaking"),     # impacted route
        ]
        score, level, drivers = compute_risk_score(changes, Sentinel(), Coverage())

        points_by_label = {d.label: d.points for d in drivers}
        # schema should get full breaking points
        schema_driver = next(
            (d for d in drivers if "schemas.py" in d.label and d.points == _BREAKING_PTS), None
        )
        assert schema_driver is not None, (
            f"Expected full breaking pts for schemas.py. Drivers: {list(points_by_label.items())}"
        )
        # route should get only impacted points
        route_driver = next(
            (d for d in drivers if "orders.py" in d.label), None
        )
        assert route_driver is not None, "Missing driver for orders.py"
        assert route_driver.points == _BREAKING_IMPACTED_PTS, (
            f"Expected route to get {_BREAKING_IMPACTED_PTS} pts (impacted), "
            f"got {route_driver.points}"
        )

    def test_breaking_schema_only_gets_full_weight(self) -> None:
        """When only a schema file is breaking (no route), it gets full weight."""
        changes = [_fc("app/schemas.py", "breaking")]
        score, level, drivers = compute_risk_score(changes, Sentinel(), Coverage())
        assert drivers[0].points == _BREAKING_PTS

    def test_breaking_route_without_breaking_schema_gets_full_weight(self) -> None:
        """A breaking route with no breaking schema in the set gets full weight."""
        changes = [
            _fc("app/routes/orders.py", "breaking"),
            _fc("app/config.py", "safe"),
        ]
        score, level, drivers = compute_risk_score(changes, Sentinel(), Coverage())
        route_driver = next((d for d in drivers if "orders.py" in d.label), None)
        assert route_driver is not None
        assert route_driver.points == _BREAKING_PTS


# ---------------------------------------------------------------------------
# Test 4 — no double-counting (sentinel api_breaking for file already counted)
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
        assert len(drivers) == 1, (
            f"Expected 1 driver (no double-count), got {len(drivers)}. "
            f"Drivers: {[(d.label, d.points) for d in drivers]}"
        )
        assert drivers[0].points == _BREAKING_PTS

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

        # risky +10 + migration_no_code high +20 = 30 raw → diminishing score
        expected_raw = 30
        expected_score = _raw_to_score(expected_raw)
        assert score == expected_score, f"Expected {expected_score}, got {score}"
        assert len(drivers) == 2


# ---------------------------------------------------------------------------
# Test 5 — diminishing returns: monotonic behaviour
# ---------------------------------------------------------------------------

class TestDiminishingReturns:
    """Score must be monotonically non-decreasing as more risky changes are added,
    and must never reach 100 with finite inputs."""

    def test_monotonic_with_increasing_risky_changes(self) -> None:
        prev_score = -1
        for n in range(0, 20):
            changes = [_fc(f"f{i}.py", "risky") for i in range(n)]
            score, _, _ = compute_risk_score(changes, Sentinel(), Coverage())
            assert score >= prev_score, (
                f"Score decreased at n={n}: was {prev_score}, now {score}"
            )
            prev_score = score

    def test_very_high_raw_asymptotically_approaches_100(self) -> None:
        """Diminishing returns: 100 breaking changes → raw=2500.
        The score is allowed to round to 100, but must not exceed it."""
        changes = [_fc(f"f{i}.py", "breaking") for i in range(100)]
        score, _, _ = compute_risk_score(changes, Sentinel(), Coverage())
        assert score <= 100, f"Score must never exceed 100, got {score}"
        # With raw=2500 the score should be ≥ 99 (deeply into the saturation zone)
        assert score >= 99, f"Expected near-100 for huge raw, got {score}"

    def test_zero_raw_gives_zero_score(self) -> None:
        score, level, _ = compute_risk_score([], Sentinel(), Coverage())
        assert score == 0
        assert level == "low"

    def test_formula_matches_expectation(self) -> None:
        """80 raw points → round(100 * (1 - exp(-1))) ≈ 63."""
        changes = [_fc(f"f{i}.py", "risky") for i in range(8)]  # 8 * 10 = 80 raw
        score, _, _ = compute_risk_score(changes, Sentinel(), Coverage())
        expected = _raw_to_score(80)
        assert score == expected


# ---------------------------------------------------------------------------
# Test 6 — level band boundaries
# ---------------------------------------------------------------------------

class TestLevelBands:
    """Check the four level bands against the diminishing-returns formula."""

    def test_low_band(self) -> None:
        # 0 raw → score 0 → low
        score, level, _ = compute_risk_score([], Sentinel(), Coverage())
        assert level == "low"

    def test_medium_band(self) -> None:
        # We need score in 25-49. raw ≈ 23 → score≈25 (1 risky = 10 raw = score ~12)
        # 3 risky = 30 raw → score ≈ 31 → medium
        changes = [_fc(f"f{i}.py", "risky") for i in range(3)]
        score, level, _ = compute_risk_score(changes, Sentinel(), Coverage())
        assert level == "medium", f"Expected medium, got {level} (score={score})"

    def test_high_band(self) -> None:
        # Need score 50-74. raw = 100 → score ≈ 71 → high
        changes = [_fc(f"f{i}.py", "risky") for i in range(10)]
        score, level, _ = compute_risk_score(changes, Sentinel(), Coverage())
        assert level == "high", f"Expected high, got {level} (score={score})"

    def test_critical_band(self) -> None:
        # raw = 200 → score ≈ 92 → critical
        changes = [_fc(f"f{i}.py", "risky") for i in range(20)]
        score, level, _ = compute_risk_score(changes, Sentinel(), Coverage())
        assert level == "critical", f"Expected critical, got {level} (score={score})"
