# assisted-by: IBM Bob 2.0 Phase 3a — foundation
"""Git utilities for PreFlight.

Public API
----------
list_tags(repo_path)            → list[str]   — annotated + lightweight tags, sorted
build_changeset(repo_path, from_tag, to_tag) → ChangeSet
"""

from __future__ import annotations

import os
from typing import List

import git  # gitpython

from app.models import ChangedFile, ChangeSet, CommitInfo, FileStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_repo_path(repo_path: str | None) -> str:
    """Return repo_path, falling back to PREFLIGHT_REPO env var then ./sample-repo."""
    if repo_path:
        return repo_path
    return os.getenv("PREFLIGHT_REPO", "./sample-repo")


def _status_char_to_literal(char: str) -> FileStatus:
    mapping = {
        "A": "added",
        "M": "modified",
        "D": "deleted",
        "R": "renamed",
    }
    return mapping.get(char.upper()[0], "modified")  # type: ignore[return-value]


def _count_lines(patch: str) -> tuple[int, int]:
    """Return (lines_added, lines_removed) from a unified diff string."""
    added = sum(1 for line in patch.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in patch.splitlines() if line.startswith("-") and not line.startswith("---"))
    return added, removed


def _blob_content(blob) -> str:
    """Safely decode a git blob to a string; return '' on binary/missing."""
    if blob is None:
        return ""
    try:
        return blob.data_stream.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_tags(repo_path: str | None = None) -> List[str]:
    """Return all tag names in the repository, sorted by creation date descending."""
    path = _resolve_repo_path(repo_path)
    repo = git.Repo(path)
    tags = sorted(
        repo.tags,
        key=lambda t: (
            t.tag.tagged_date if hasattr(t, "tag") and t.tag else t.commit.committed_date
        ),
        reverse=True,
    )
    return [t.name for t in tags]


def build_changeset(
    from_tag: str,
    to_tag: str,
    repo_path: str | None = None,
) -> ChangeSet:
    """Build a ChangeSet containing every file and commit between two tags.

    Parameters
    ----------
    from_tag:  the earlier tag (e.g. "v1.0.0")
    to_tag:    the later tag   (e.g. "v1.1.0")
    repo_path: path to the git repository; falls back to PREFLIGHT_REPO env var
    """
    path = _resolve_repo_path(repo_path)
    repo = git.Repo(path)

    from_commit = repo.commit(from_tag)
    to_commit = repo.commit(to_tag)

    # --- commits in range (from_tag excluded, to_tag included) ---------------
    commit_objects = list(repo.iter_commits(f"{from_tag}..{to_tag}"))
    commits: List[CommitInfo] = [
        CommitInfo(
            sha=c.hexsha[:8],
            message=c.message.strip().splitlines()[0],
            author=str(c.author),
        )
        for c in reversed(commit_objects)
    ]

    # --- file diffs -----------------------------------------------------------
    diffs = from_commit.diff(to_commit, create_patch=True)
    files: List[ChangedFile] = []

    for diff_item in diffs:
        status_char = diff_item.change_type or "M"
        status = _status_char_to_literal(status_char)

        # path: prefer new path; for deletes use old path
        path_str: str = diff_item.b_path or diff_item.a_path or ""
        old_path: str | None = diff_item.a_path if status == "renamed" else None

        try:
            patch = diff_item.diff.decode("utf-8", errors="replace") if diff_item.diff else ""
        except Exception:
            patch = ""

        lines_added, lines_removed = _count_lines(patch)

        old_content = _blob_content(diff_item.a_blob)
        new_content = _blob_content(diff_item.b_blob)

        files.append(
            ChangedFile(
                path=path_str,
                old_path=old_path,
                status=status,
                patch=patch,
                old_content=old_content,
                new_content=new_content,
                lines_added=lines_added,
                lines_removed=lines_removed,
            )
        )

    return ChangeSet(
        repo_path=path,
        from_tag=from_tag,
        to_tag=to_tag,
        commits=commits,
        files=files,
    )
