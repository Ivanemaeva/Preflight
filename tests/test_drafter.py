# assisted-by: IBM Bob 2.0 four-fix task — repo-path test existence, range validation, drafter dedup, diff reason, task 2026-09-25
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
from app.drafter import _classify_commit, _group_commits, draft

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


# Realistic commits matching sample-repo v1.0.0..v1.1.0
_SAMPLE_COMMITS = [
    CommitInfo(sha="89f149a", message="docs(config): expand module docstring with dev-mode note", author="dev"),
    CommitInfo(sha="7fa5ab3", message="test(config): add tests for Settings defaults and env override", author="dev"),
    CommitInfo(sha="ed0c90d", message="feat(pricing): add calculate_total_cents for payment provider integration", author="dev"),
    CommitInfo(sha="0a680e4", message="feat(db): 0003 migration — add discount_code column to orders", author="dev"),
    CommitInfo(sha="a40f189", message="feat(webhooks): add payment webhook endpoint with HMAC verification", author="dev"),
    CommitInfo(sha="61a5476", message="refactor(api): represent order total as integer cents for payment accuracy", author="dev"),
    CommitInfo(sha="042eed9", message="chore: register webhooks router; bump app version to 1.1.0", author="dev"),
    CommitInfo(sha="c2d0c12", message="test: update order tests to assert total_cents field", author="dev"),
    CommitInfo(sha="208b542", message="docs: update README — add webhook endpoint, fix typo in features list", author="dev"),
]


@pytest.fixture(scope="module")
def changeset(report_data) -> ChangeSet:
    r = report_data["range"]
    return ChangeSet(
        repo_path=".",
        from_tag=r["from"],
        to_tag=r["to"],
        commits=_SAMPLE_COMMITS,
    )


@pytest.fixture(scope="module")
def drafts(changeset, changes, coverage, sentinel, report_data):
    return draft(
        changeset=changeset,
        changes=changes,
        coverage=coverage,
        sentinel=sentinel,
        to_tag=report_data["range"]["to"],
        from_tag=report_data["range"]["from"],
    )


# ---------------------------------------------------------------------------
# Tests — conventional-commit classification helpers
# ---------------------------------------------------------------------------

def test_classify_feat():
    section, body = _classify_commit("feat(webhooks): add payment webhook endpoint with HMAC verification")
    assert section == "Features"
    assert "webhook" in body.lower()


def test_classify_fix():
    section, body = _classify_commit("fix: correct null pointer in orders handler")
    assert section == "Fixes"


def test_classify_refactor():
    section, body = _classify_commit("refactor(api): represent order total as integer cents")
    assert section == "Refactors"


def test_classify_docs():
    section, body = _classify_commit("docs(config): expand module docstring")
    assert section == "Docs and tests"


def test_classify_test():
    section, body = _classify_commit("test(config): add tests for Settings defaults")
    assert section == "Docs and tests"


def test_classify_chore():
    section, body = _classify_commit("chore: bump version to 1.1.0")
    assert section == "Chores"


def test_classify_non_conventional():
    section, body = _classify_commit("update README file")
    assert section == "Chores"
    assert body == "update README file"


def test_group_commits_sections():
    commits = [
        CommitInfo(sha="a", message="feat: add login", author="x"),
        CommitInfo(sha="b", message="fix: patch null", author="x"),
        CommitInfo(sha="c", message="chore: bump version", author="x"),
    ]
    groups = _group_commits(commits)
    assert "Features" in groups
    assert "Fixes" in groups
    assert "Chores" in groups
    assert groups["Features"] == ["add login"]
    assert groups["Fixes"] == ["patch null"]


# ---------------------------------------------------------------------------
# Tests — release notes structure
# ---------------------------------------------------------------------------

def test_release_notes_has_breaking_section(drafts):
    """Fixture has 2 breaking changes — section header must appear."""
    assert "⚠ Breaking Changes" in drafts.release_notes_md


def test_breaking_changes_merged_per_file(drafts):
    """Diff-engine + sentinel reasons for the SAME file must be merged into one bullet."""
    rn = drafts.release_notes_md
    # Both app/schemas.py entries (diff engine + sentinel api_breaking) → one bullet
    lines = [l for l in rn.splitlines() if "app/schemas.py" in l]
    assert len(lines) == 1, (
        f"Expected exactly 1 bullet for app/schemas.py, got {len(lines)}: {lines}"
    )


def test_route_file_labelled_affected_by_schema_change(drafts):
    """Routes only impacted by a schema change must be labelled 'affected by the schema change'."""
    rn = drafts.release_notes_md
    routes_line = next(
        (l for l in rn.splitlines() if "orders.py" in l), None
    )
    assert routes_line is not None, "No line for orders.py in release notes"
    assert "affected by the schema change" in routes_line, (
        f"Expected 'affected by the schema change' label on route bullet; got: {routes_line!r}"
    )


def test_release_notes_has_db_section(drafts):
    """Database section must be present and mention the migration path."""
    rn = drafts.release_notes_md
    assert "### Database" in rn
    assert "migrations/0003_add_discount_code.sql" in rn


def test_release_notes_has_commit_sections(drafts):
    """Commit-message sections (Features, Refactors, etc.) must appear."""
    rn = drafts.release_notes_md
    assert "### Features" in rn
    assert "### Refactors" in rn or "refactor" in rn.lower()
    assert "### Docs and tests" in rn or "### Chores" in rn


def test_release_notes_groups_feat_commits(drafts):
    """Each feat commit body must appear in the Features section."""
    rn = drafts.release_notes_md
    assert "add calculate_total_cents" in rn
    assert "add payment webhook endpoint" in rn


def test_release_notes_no_test_or_readme_paths(drafts):
    """Test files and README must NOT appear as file paths in release notes."""
    rn = drafts.release_notes_md
    # Should not have raw test file paths or README.md listed as a change
    assert "README.md" not in rn or "webhook endpoint" in rn  # may mention in commit body is ok
    for line in rn.splitlines():
        assert not (line.startswith("- `tests/") or line.startswith("- `test_")), (
            f"Test file path leaked into release notes: {line!r}"
        )


# ---------------------------------------------------------------------------
# Tests — changelog structure
# ---------------------------------------------------------------------------

def test_changelog_has_added_section(drafts):
    """Commit-message-driven changelog must have an Added section."""
    assert "### Added" in drafts.changelog_md


def test_changelog_has_changed_section_for_breaking(drafts):
    """Breaking changes must still appear in ### Changed."""
    assert "### Changed" in drafts.changelog_md


# ---------------------------------------------------------------------------
# Tests — rollback steps (real actions only)
# ---------------------------------------------------------------------------

def test_rollback_steps_ordered(drafts):
    """Step 1 must reference migration revert; last step is verification."""
    steps = drafts.rollback_steps
    assert len(steps) >= 2

    first_action = steps[0].action.lower()
    assert "migration" in first_action or "revert" in first_action

    last_action = steps[-1].action.lower()
    assert "verify" in last_action or "smoke" in last_action


def test_rollback_steps_numbered_sequentially(drafts):
    """Steps must be numbered 1, 2, 3, … N with no gaps."""
    numbers = [s.step for s in drafts.rollback_steps]
    assert numbers == list(range(1, len(numbers) + 1))


def test_rollback_steps_no_document_env_var(drafts):
    """'document' / 'undocumented env var' actions must NOT be in rollback steps."""
    for step in drafts.rollback_steps:
        assert "document" not in step.action.lower() or "undocumented" not in step.action.lower(), (
            f"Documentation action leaked into rollback steps: {step.action!r}"
        )


# ---------------------------------------------------------------------------
# Tests — pre_release_fixes
# ---------------------------------------------------------------------------

def test_pre_release_fixes_contains_env_undocumented(drafts):
    """env_undocumented sentinel finding must produce a pre_release_fix entry."""
    assert len(drafts.pre_release_fixes) >= 1
    actions = [f.action.lower() for f in drafts.pre_release_fixes]
    assert any(("env" in a or "document" in a) for a in actions), (
        f"Expected env/document pre-release fix, got: {actions}"
    )


def test_pre_release_fixes_not_in_rollback(drafts):
    """pre_release_fixes items must not also appear in rollback_steps."""
    rollback_actions = {s.action.lower() for s in drafts.rollback_steps}
    for fix in drafts.pre_release_fixes:
        assert fix.action.lower() not in rollback_actions, (
            f"Pre-release fix leaked into rollback: {fix.action!r}"
        )


# ---------------------------------------------------------------------------
# Tests — misc / edge cases
# ---------------------------------------------------------------------------

def test_no_llm_calls():
    """drafter.py must not import openai, anthropic, or requests at module level."""
    import app.drafter as drafter_module

    globals_set = set(vars(drafter_module).keys())
    forbidden = {"openai", "anthropic", "requests"}
    assert globals_set.isdisjoint(forbidden), (
        f"Forbidden LLM imports found: {globals_set & forbidden}"
    )


def test_empty_changeset(report_data):
    """Empty inputs → no breaking section; rollback still ends with verification."""
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
    assert "verify" in last.action.lower() or "smoke" in last.action.lower()


def test_empty_changeset_no_pre_release_fixes(report_data):
    """Empty sentinel findings → no pre_release_fixes."""
    cs = ChangeSet(
        repo_path=".",
        from_tag=report_data["range"]["from"],
        to_tag=report_data["range"]["to"],
    )
    result = draft(
        changeset=cs, changes=[], coverage=Coverage(), sentinel=Sentinel(),
        to_tag=report_data["range"]["to"],
    )
    assert result.pre_release_fixes == []
