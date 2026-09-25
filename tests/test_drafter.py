# assisted-by: IBM Bob 2.0 Phase 3b — DRAFTER
"""Tests for app/drafter.py — all inputs built from tests/fixtures/report.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models import (
    ChangeSet,
    CommitInfo,
    Coverage,
    CoverageGap,
    FileChange,
    Sentinel,
    SentinelFinding,
)
from app.drafter import draft

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "report.json"


@pytest.fixture(scope="module")
def report_data() -> dict:
    return json.loads(FIXTURE_PATH.read_text())


@pytest.fixture(scope="module")
def changes(report_data) -> list[FileChange]:
    return [FileChange(**c) for c in report_data["changes"]]


@pytest.fixture(scope="module")
def coverage(report_data) -> Coverage:
    return Coverage(
        gaps=[CoverageGap(**g) for g in report_data["coverage"]["gaps"]],
    )


@pytest.fixture(scope="module")
def sentinel(report_data) -> Sentinel:
    return Sentinel(
        findings=[SentinelFinding(**f) for f in report_data["sentinel"]["findings"]],
    )


@pytest.fixture(scope="module")
def changeset(report_data) -> ChangeSet:
    r = report_data["range"]
    return ChangeSet(
        repo_path=".",
        from_tag=r["from"],
        to_tag=r["to"],
    )


@pytest.fixture(scope="module")
def drafts(changeset, changes, coverage, sentinel, report_data):
    return draft(
        changeset=changeset,
        changes=changes,
        coverage=coverage,
        sentinel=sentinel,
        to_tag=report_data["range"]["to"],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_release_notes_has_breaking_section(drafts):
    """Fixture has 2 breaking changes — section header must appear."""
    assert "⚠ Breaking Changes" in drafts.release_notes_md


def test_release_notes_has_db_section(drafts):
    """Database section must be present and mention the migration path."""
    rn = drafts.release_notes_md
    assert "### Database" in rn
    assert "migrations/0003_add_discount_code.sql" in rn


def test_changelog_has_added_section(drafts):
    """At least one 'added' file with non-breaking risk should produce ### Added."""
    assert "### Added" in drafts.changelog_md


def test_rollback_steps_ordered(drafts):
    """Step 1 action must reference a migration rollback; last step is verification."""
    steps = drafts.rollback_steps
    assert len(steps) >= 2

    first_action = steps[0].action.lower()
    assert "migration" in first_action or "roll back" in first_action

    last_action = steps[-1].action.lower()
    assert "redeploy" in last_action or "verify" in last_action


def test_rollback_steps_numbered_sequentially(drafts):
    """Steps must be numbered 1, 2, 3, … N with no gaps."""
    numbers = [s.step for s in drafts.rollback_steps]
    assert numbers == list(range(1, len(numbers) + 1))


def test_no_llm_calls():
    """drafter.py must not import openai, anthropic, or requests at module level."""
    import app.drafter as drafter_module

    globals_set = set(vars(drafter_module).keys())
    forbidden = {"openai", "anthropic", "requests"}
    assert globals_set.isdisjoint(forbidden), (
        f"Forbidden LLM imports found: {globals_set & forbidden}"
    )


def test_empty_changeset(report_data):
    """Empty inputs → no breaking section; rollback ends with verification."""
    empty_changeset = ChangeSet(
        repo_path=".",
        from_tag=report_data["range"]["from"],
        to_tag=report_data["range"]["to"],
    )
    result = draft(
        changeset=empty_changeset,
        changes=[],
        coverage=Coverage(),
        sentinel=Sentinel(),
        to_tag=report_data["range"]["to"],
    )

    assert "⚠ Breaking Changes" not in result.release_notes_md

    assert len(result.rollback_steps) >= 1
    last = result.rollback_steps[-1]
    assert "redeploy" in last.action.lower() or "verify" in last.action.lower()
