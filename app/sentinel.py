# assisted-by: IBM Bob 2.0 Phase 3a — SENTINEL
"""Sentinel analyser — detects four categories of risky changes.

Public API
----------
analyse(changeset, repo_path=None) -> Sentinel
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path

from app.models import ChangeSet, Sentinel, SentinelFinding


# ---------------------------------------------------------------------------
# Detector 1 — migration_no_code
# ---------------------------------------------------------------------------

def _detect_migration_no_code(changeset: ChangeSet) -> list[SentinelFinding]:
    findings: list[SentinelFinding] = []

    sql_files = [
        f for f in changeset.files
        if fnmatch.fnmatch(f.path, "migrations/*.sql")
        and f.status in ("added", "modified")
    ]
    if not sql_files:
        return findings

    # Collect new_content of every .py file in the changeset for reference lookup
    py_contents: list[str] = [
        f.new_content
        for f in changeset.files
        if f.path.endswith(".py")
    ]

    for sql_file in sql_files:
        content = sql_file.new_content or sql_file.patch

        # Extract column / table names mentioned in ADD COLUMN or CREATE TABLE
        names: list[tuple[str, str]] = []  # (regex_label, name)
        for line in content.splitlines():
            m = re.search(r"ADD COLUMN\s+(\w+)", line, re.IGNORECASE)
            if m:
                names.append((line.strip(), m.group(1)))
            m = re.search(r"CREATE TABLE\s+(\w+)", line, re.IGNORECASE)
            if m:
                names.append((line.strip(), m.group(1)))

        for evidence_line, name in names:
            # Check whether any Python file's new_content mentions this name
            mentioned = any(name in py_src for py_src in py_contents)
            if not mentioned:
                findings.append(
                    SentinelFinding(
                        kind="migration_no_code",
                        severity="high",
                        location=sql_file.path,
                        detail=(
                            f"SQL migration adds '{name}' but no Python file references it."
                        ),
                        evidence=evidence_line,
                    )
                )
    return findings


# ---------------------------------------------------------------------------
# Detector 2 — api_breaking
# ---------------------------------------------------------------------------

_RESPONSE_CLASS_RE = re.compile(r"class\s+\w+Response\s*\(BaseModel\)")
_FIELD_RE = re.compile(r"^\s{4}(\w+)\s*:", re.MULTILINE)


def _public_fields(content: str) -> set[str]:
    """Return the set of public field names from all Response classes in content."""
    return set(_FIELD_RE.findall(content))


def _detect_api_breaking(changeset: ChangeSet) -> list[SentinelFinding]:
    findings: list[SentinelFinding] = []

    for f in changeset.files:
        if not f.path.endswith(".py"):
            continue
        if not _RESPONSE_CLASS_RE.search(f.old_content):
            continue

        old_fields = _public_fields(f.old_content)
        new_fields = _public_fields(f.new_content)
        removed = old_fields - new_fields
        if not removed:
            continue

        # Build evidence from the patch
        patch_lines = [
            line for line in f.patch.splitlines()
            if (line.startswith("+") or line.startswith("-"))
            and not line.startswith("+++")
            and not line.startswith("---")
        ]
        evidence = "\n".join(patch_lines[:6])

        for field in sorted(removed):
            findings.append(
                SentinelFinding(
                    kind="api_breaking",
                    severity="high",
                    location=f.path,
                    detail=(
                        f"Response model field '{field}' was removed — "
                        "existing API clients will break."
                    ),
                    evidence=evidence,
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Detector 3 — env_undocumented
# ---------------------------------------------------------------------------

_GETENV_RE = re.compile(
    r'os\.getenv\(\s*["\'](\w+)["\']'
    r'|os\.environ\[\s*["\'](\w+)["\']\s*\]'
    r'|os\.environ\.get\(\s*["\'](\w+)["\']',
)


def _detect_env_undocumented(
    changeset: ChangeSet, repo_path: str | None
) -> list[SentinelFinding]:
    findings: list[SentinelFinding] = []

    env_example_content = ""
    if repo_path:
        env_example_path = Path(repo_path) / ".env.example"
        if env_example_path.exists():
            env_example_content = env_example_path.read_text(encoding="utf-8")

    for f in changeset.files:
        if not f.path.endswith(".py"):
            continue
        source = f.new_content
        for line in source.splitlines():
            for m in _GETENV_RE.finditer(line):
                varname = m.group(1) or m.group(2) or m.group(3)
                if varname and varname not in env_example_content:
                    findings.append(
                        SentinelFinding(
                            kind="env_undocumented",
                            severity="high",
                            location=f.path,
                            detail=(
                                f"Environment variable '{varname}' is used but absent "
                                "from .env.example."
                            ),
                            evidence=line.strip(),
                        )
                    )
    return findings


# ---------------------------------------------------------------------------
# Detector 4 — config_key_added
# ---------------------------------------------------------------------------

_CONFIG_ASSIGN_RE = re.compile(
    r"^\+\s+\w+\s*(?::\s*\w+)?\s*=\s*os\.getenv", re.MULTILINE
)


def _detect_config_key_added(changeset: ChangeSet) -> list[SentinelFinding]:
    findings: list[SentinelFinding] = []

    for f in changeset.files:
        if not f.path.endswith(".py"):
            continue
        basename = Path(f.path).name
        if not (
            fnmatch.fnmatch(basename, "*config*.py")
            or fnmatch.fnmatch(basename, "*settings*.py")
        ):
            continue

        for m in _CONFIG_ASSIGN_RE.finditer(f.patch):
            added_line = m.group(0).lstrip("+").strip()
            findings.append(
                SentinelFinding(
                    kind="config_key_added",
                    severity="medium",
                    location=f.path,
                    detail=(
                        "New config key reads from env without documentation: "
                        f"{added_line}"
                    ),
                    evidence=added_line,
                )
            )
    return findings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyse(changeset: ChangeSet, repo_path: str | None = None) -> Sentinel:
    """Run all four sentinel detectors against *changeset* and return findings."""
    effective_repo = repo_path or changeset.repo_path or None
    findings: list[SentinelFinding] = []
    findings.extend(_detect_migration_no_code(changeset))
    findings.extend(_detect_api_breaking(changeset))
    findings.extend(_detect_env_undocumented(changeset, effective_repo))
    findings.extend(_detect_config_key_added(changeset))
    return Sentinel(findings=findings)
