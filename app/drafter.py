# assisted-by: IBM Bob 2.0 four-fix task — repo-path test existence, range validation, drafter dedup, diff reason, task 2026-09-25
"""Deterministic draft generator — no LLM calls.

Produces release notes, a changelog, and ordered rollback steps
from the structured outputs of the three analysers.

Release notes are built from commit messages grouped by conventional-commit
type.  Rollback steps contain only real rollback actions; items like
"document the undocumented env var" go into pre_release_fixes instead.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

from app.models import (
    ChangeSet,
    CommitInfo,
    Coverage,
    Drafts,
    FileChange,
    PreReleaseFix,
    RollbackStep,
    Sentinel,
)

# Regex that matches conventional-commit prefixes like "feat(scope): msg"
_CC_RE = re.compile(r"^(\w+)(?:\([^)]*\))?!?:\s*(.*)", re.IGNORECASE)

# Mapping of conventional-commit type → section label
_CC_SECTION: Dict[str, str] = {
    "feat":     "Features",
    "fix":      "Fixes",
    "refactor": "Refactors",
    "perf":     "Refactors",
    "docs":     "Docs and tests",
    "test":     "Docs and tests",
    "chore":    "Chores",
    "build":    "Chores",
    "ci":       "Chores",
    "style":    "Chores",
    "revert":   "Chores",
}

# Paths that should never appear in release notes
_IGNORE_PATHS = re.compile(r"(tests?/|test_|README|\.md$)", re.IGNORECASE)


def _classify_commit(msg: str) -> Tuple[str, str]:
    """Return (section_key, cleaned_message) for a commit message.

    section_key is one of the values in _CC_SECTION, or 'Chores' as fallback.
    """
    m = _CC_RE.match(msg)
    if m:
        cc_type = m.group(1).lower()
        body = m.group(2).strip()
        section = _CC_SECTION.get(cc_type, "Chores")
        return section, body
    return "Chores", msg.strip()


def _group_commits(commits: List[CommitInfo]) -> Dict[str, List[str]]:
    """Group commit messages by section label, preserving insertion order.

    Returns a dict like {"Features": ["msg1", ...], "Fixes": [...], ...}
    Only non-empty sections are included.
    """
    # Ordered sections so the output is deterministic
    order = ["Features", "Fixes", "Refactors", "Docs and tests", "Chores"]
    groups: Dict[str, List[str]] = {s: [] for s in order}
    for commit in commits:
        section, body = _classify_commit(commit.message)
        groups[section].append(body)
    return {s: groups[s] for s in order if groups[s]}


def draft(
    changeset: ChangeSet,
    changes: list[FileChange],
    coverage: Coverage,
    sentinel: Sentinel,
    to_tag: str,
    from_tag: str = "",
) -> Drafts:
    """Build Drafts deterministically from analyser outputs."""

    # ------------------------------------------------------------------
    # Categorise changes — skip test files and README for notes
    # ------------------------------------------------------------------
    breaking = [c for c in changes if c.risk == "breaking"]
    migrations = [c for c in changes if "migrations/" in c.path]

    # ------------------------------------------------------------------
    # release_notes_md
    # ------------------------------------------------------------------
    rn_parts: list[str] = [f"## {to_tag}\n"]

    # Breaking Changes: merge diff-engine + sentinel api_breaking entries per file.
    # Files that are only flagged via a schema-change impact are labelled accordingly.
    breaking_schema_paths: set[str] = set()
    breaking_route_paths: set[str] = set()
    for c in breaking:
        if any(c.path.endswith(s) for s in ("schemas.py", "schema.py", "models.py", "serializers.py")):
            breaking_schema_paths.add(c.path)
        elif any(pat in c.path.replace("\\", "/").lower() for pat in ("routes/", "views/", "endpoints/", "handlers/")):
            breaking_route_paths.add(c.path)

    # Build per-file reason map: path → list of reason strings
    file_reasons: dict[str, list[str]] = {}
    for c in breaking:
        file_reasons.setdefault(c.path, []).append(c.reason)
    for f in sentinel.findings:
        if f.kind == "api_breaking":
            file_reasons.setdefault(f.location, []).append(f.detail)

    breaking_items: list[str] = []
    for path, reasons in file_reasons.items():
        combined = "; ".join(dict.fromkeys(reasons))  # dedup while preserving order
        is_schema_impacted_only = (
            path in breaking_route_paths
            and breaking_schema_paths
            and path not in breaking_schema_paths
        )
        if is_schema_impacted_only:
            breaking_items.append(f"- `{path}` — affected by the schema change: {combined}")
        else:
            breaking_items.append(f"- `{path}` — {combined}")

    if breaking_items:
        rn_parts.append("### ⚠ Breaking Changes")
        rn_parts.extend(breaking_items)
        rn_parts.append("")

    # Database: migration files found by the diff engine
    if migrations:
        rn_parts.append("### Database")
        for c in migrations:
            rn_parts.append(f"- `{c.path}` — {c.reason}")
        rn_parts.append("")

    # Commit-message sections
    if changeset.commits:
        groups = _group_commits(changeset.commits)
        for section, messages in groups.items():
            rn_parts.append(f"### {section}")
            for msg in messages:
                rn_parts.append(f"- {msg}")
            rn_parts.append("")

    release_notes_md = "\n".join(rn_parts)

    # ------------------------------------------------------------------
    # changelog_md — same structure, commit-message driven
    # ------------------------------------------------------------------
    cl_parts: list[str] = []

    if breaking:
        cl_parts.append("### Changed")
        for c in breaking:
            if not _IGNORE_PATHS.search(c.path):
                cl_parts.append(f"- `{c.path}`: {c.reason} (breaking)")
        cl_parts.append("")

    if changeset.commits:
        groups = _group_commits(changeset.commits)
        section_to_keep_change = {"Features": "Added", "Fixes": "Fixed", "Refactors": "Refactored"}
        for section, messages in groups.items():
            header = section_to_keep_change.get(section, section)
            cl_parts.append(f"### {header}")
            for msg in messages:
                cl_parts.append(f"- {msg}")
            cl_parts.append("")

    changelog_md = "\n".join(cl_parts)

    # ------------------------------------------------------------------
    # rollback_steps — real rollback actions only
    # ------------------------------------------------------------------
    steps: list[tuple[str, str]] = []  # (action, reason)

    _from = from_tag or (changeset.from_tag if changeset else "") or "previous"

    # 1. Revert migration(s) first
    for f in sentinel.findings:
        if f.kind == "migration_no_code":
            steps.append((
                f"Revert migration {f.location}: reverse the SQL change",
                f.detail,
            ))

    # 2. Revert code to the previous tag
    if breaking:
        steps.append((
            f"Revert code to the previous tag: git checkout {_from}",
            f"{len(breaking)} breaking change(s) must be rolled back",
        ))

    # 3. Redeploy the previous tag
    steps.append((
        f"Redeploy the previous tag ({_from}) to all environments",
        "Restore the known-good release",
    ))

    # 4. Verify
    steps.append((
        "Verify: run smoke tests and confirm all endpoints return expected responses",
        "Confirm rollback succeeded",
    ))

    rollback_steps = [
        RollbackStep(step=i + 1, action=action, reason=reason)
        for i, (action, reason) in enumerate(steps)
    ]

    # ------------------------------------------------------------------
    # pre_release_fixes — items to address BEFORE releasing (not rollback)
    # ------------------------------------------------------------------
    pre_fixes: list[PreReleaseFix] = []

    for f in sentinel.findings:
        if f.kind == "env_undocumented":
            pre_fixes.append(PreReleaseFix(
                action=f"Document undocumented env var in {f.location} in .env.example and README",
                reason=f.detail,
            ))
        elif f.kind == "config_key_added":
            pre_fixes.append(PreReleaseFix(
                action=f"Document new config key at {f.location} before releasing",
                reason=f.detail,
            ))

    return Drafts(
        release_notes_md=release_notes_md,
        changelog_md=changelog_md,
        rollback_steps=rollback_steps,
        pre_release_fixes=pre_fixes,
    )
