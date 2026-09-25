# assisted-by: IBM Bob 2.0 Phase 3b — DRAFTER
"""Deterministic draft generator — no LLM calls.

Produces release notes, a changelog, and ordered rollback steps
from the structured outputs of the three analysers.
"""

from __future__ import annotations

from app.models import (
    ChangeSet,
    Coverage,
    Drafts,
    FileChange,
    RollbackStep,
    Sentinel,
)


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
    # Categorise changes
    # ------------------------------------------------------------------
    breaking = [c for c in changes if c.risk == "breaking"]
    new_features = [c for c in changes if c.status == "added" and c.risk != "breaking"]
    migrations = [c for c in changes if "migrations/" in c.path]
    # "Other": safe-or-risky modified (not breaking, not added, not a migration)
    other = [
        c for c in changes
        if c.risk != "breaking"
        and c.status != "added"
        and "migrations/" not in c.path
    ]
    # safe modified only (for changelog Fixed/Docs section)
    safe_modified = [c for c in changes if c.risk == "safe" and c.status != "added"]

    # ------------------------------------------------------------------
    # release_notes_md
    # ------------------------------------------------------------------
    rn_parts: list[str] = [f"## {to_tag}\n"]

    if breaking:
        rn_parts.append("### ⚠ Breaking Changes")
        for c in breaking:
            rn_parts.append(f"- `{c.path}` — {c.reason}")
        rn_parts.append("")

    if new_features:
        rn_parts.append("### New Features")
        for c in new_features:
            rn_parts.append(f"- `{c.path}` — {c.reason}")
        rn_parts.append("")

    if migrations:
        rn_parts.append("### Database")
        for c in migrations:
            rn_parts.append(f"- `{c.path}` — {c.reason}")
        rn_parts.append("")

    if other:
        rn_parts.append("### Other")
        for c in other:
            rn_parts.append(f"- `{c.path}` — {c.reason}")
        rn_parts.append("")

    release_notes_md = "\n".join(rn_parts)

    # ------------------------------------------------------------------
    # changelog_md
    # ------------------------------------------------------------------
    cl_parts: list[str] = []

    if breaking:
        cl_parts.append("### Changed")
        for c in breaking:
            cl_parts.append(f"- `{c.path}`: {c.reason} (breaking)")
        cl_parts.append("")

    if new_features:
        cl_parts.append("### Added")
        for c in new_features:
            cl_parts.append(f"- `{c.path}`")
        cl_parts.append("")

    if safe_modified:
        cl_parts.append("### Fixed / Docs")
        for c in safe_modified:
            cl_parts.append(f"- `{c.path}`: {c.reason}")
        cl_parts.append("")

    changelog_md = "\n".join(cl_parts)

    # ------------------------------------------------------------------
    # rollback_steps
    # ------------------------------------------------------------------
    steps: list[tuple[str, str]] = []  # (action, reason)

    # 1. migrations first
    for f in sentinel.findings:
        if f.kind == "migration_no_code":
            steps.append((
                f"Roll back migration at {f.location}: reverse the SQL change",
                f.detail,
            ))

    # 2. breaking changes (config/code)
    _from = from_tag or (changeset.from_tag if changeset else "") or "v1.0.0"
    for c in breaking:
        steps.append((
            f"Revert breaking change in {c.path}: git checkout {_from} -- {c.path}",
            c.reason,
        ))

    # 3. env undocumented
    env_findings = [f for f in sentinel.findings if f.kind == "env_undocumented"]
    if env_findings:
        vars_list = ", ".join(f.location for f in env_findings)
        # use the first finding's detail for the reason
        steps.append((
            f"Remove or document undocumented env var(s): {vars_list}",
            env_findings[0].detail,
        ))

    # 4. final verification step (always present)
    steps.append((
        "Redeploy previous tag and verify all endpoints return expected responses",
        "Confirm rollback succeeded",
    ))

    rollback_steps = [
        RollbackStep(step=i + 1, action=action, reason=reason)
        for i, (action, reason) in enumerate(steps)
    ]

    return Drafts(
        release_notes_md=release_notes_md,
        changelog_md=changelog_md,
        rollback_steps=rollback_steps,
    )
