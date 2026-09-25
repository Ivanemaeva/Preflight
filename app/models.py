# assisted-by: IBM Bob 2.0 Phase 3a — foundation
"""Pydantic models — single source of truth for the PreFlight report JSON.

Schema matches docs/PLAN.md §3 exactly.
"""

from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Sub-models: range
# ---------------------------------------------------------------------------

class RangeInfo(BaseModel):
    """The tag range that was analysed."""
    from_tag: str = Field(..., alias="from")
    to_tag: str = Field(..., alias="to")
    commits: int
    files_changed: int

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Sub-models: risk
# ---------------------------------------------------------------------------

class RiskDriver(BaseModel):
    """A single contribution to the overall risk score."""
    label: str
    points: int


class Risk(BaseModel):
    """Aggregate risk score and band."""
    score: int = Field(..., ge=0, le=100)
    level: Literal["low", "medium", "high", "critical"]
    drivers: List[RiskDriver] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Sub-models: changes[]
# ---------------------------------------------------------------------------

FileStatus = Literal["added", "modified", "deleted", "renamed"]
RiskLevel = Literal["breaking", "risky", "safe"]


class FileChange(BaseModel):
    """Risk classification for a single changed file."""
    path: str
    status: FileStatus
    risk: RiskLevel
    reason: str
    lines_added: int = 0
    lines_removed: int = 0


# ---------------------------------------------------------------------------
# Sub-models: coverage{}
# ---------------------------------------------------------------------------

class CoverageGap(BaseModel):
    """A changed source file with no corresponding test."""
    path: str
    reason: str
    suggested_test: str


class CoveredFile(BaseModel):
    """A changed source file that has at least one test."""
    path: str
    tests: List[str]


class CoverageStub(BaseModel):
    """A generated stub test file for a gap."""
    path: str
    content: str


class Coverage(BaseModel):
    gaps: List[CoverageGap] = Field(default_factory=list)
    covered: List[CoveredFile] = Field(default_factory=list)
    stubs: List[CoverageStub] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Sub-models: sentinel{}
# ---------------------------------------------------------------------------

SentinelKind = Literal[
    "migration_no_code",
    "api_breaking",
    "env_undocumented",
    "config_key_added",
]
Severity = Literal["high", "medium", "low"]


class SentinelFinding(BaseModel):
    """A single sentinel finding."""
    kind: SentinelKind
    severity: Severity
    location: str
    detail: str
    evidence: str = ""


class Sentinel(BaseModel):
    findings: List[SentinelFinding] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Sub-models: drafts{}
# ---------------------------------------------------------------------------

class RollbackStep(BaseModel):
    step: int
    action: str
    reason: str


class Drafts(BaseModel):
    release_notes_md: str = ""
    changelog_md: str = ""
    rollback_steps: List[RollbackStep] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top-level Report
# ---------------------------------------------------------------------------

class Report(BaseModel):
    """The full PreFlight Release Readiness Report."""
    range: RangeInfo
    risk: Risk
    changes: List[FileChange] = Field(default_factory=list)
    coverage: Coverage = Field(default_factory=Coverage)
    sentinel: Sentinel = Field(default_factory=Sentinel)
    drafts: Drafts = Field(default_factory=Drafts)


# ---------------------------------------------------------------------------
# ChangeSet — internal data structure passed between analysers
# ---------------------------------------------------------------------------

class ChangedFile(BaseModel):
    """Per-file data from the git diff."""
    path: str
    old_path: Optional[str] = None          # set on renames
    status: FileStatus
    patch: str = ""                          # unified diff text
    old_content: str = ""                    # content at from_tag  (may be empty for added files)
    new_content: str = ""                    # content at to_tag    (may be empty for deleted files)
    lines_added: int = 0
    lines_removed: int = 0


class CommitInfo(BaseModel):
    sha: str
    message: str
    author: str


class ChangeSet(BaseModel):
    """Everything gitutil extracts for a tag range."""
    repo_path: str
    from_tag: str
    to_tag: str
    commits: List[CommitInfo] = Field(default_factory=list)
    files: List[ChangedFile] = Field(default_factory=list)
