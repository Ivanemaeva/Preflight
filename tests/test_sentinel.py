# assisted-by: IBM Bob 2.0 Phase 3a — SENTINEL
"""Tests for app.sentinel.

Integration tests run against sample-repo v1.0.0..v1.1.0.
Unit tests use synthetic ChangedFile / ChangeSet objects.
"""

from __future__ import annotations

import pytest

from app.gitutil import build_changeset
from app.models import ChangeSet, ChangedFile, SentinelFinding
from app.sentinel import analyse


# ---------------------------------------------------------------------------
# Integration tests — sample-repo v1.0.0..v1.1.0
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sample_findings() -> list[SentinelFinding]:
    cs = build_changeset("v1.0.0", "v1.1.0", repo_path="./sample-repo")
    sentinel = analyse(cs, repo_path="./sample-repo")
    return sentinel.findings


def test_migration_no_code_discount_code(sample_findings):
    """Migration 0003_add_discount_code.sql should fire migration_no_code."""
    matches = [
        f for f in sample_findings
        if f.kind == "migration_no_code"
        and "0003_add_discount_code" in f.location
    ]
    assert matches, (
        f"Expected a migration_no_code finding at 0003_add_discount_code; "
        f"got findings: {[(f.kind, f.location) for f in sample_findings]}"
    )


def test_api_breaking_schemas(sample_findings):
    """Removal of 'total' field from OrderResponse should fire api_breaking."""
    matches = [
        f for f in sample_findings
        if f.kind == "api_breaking"
        and "schemas.py" in f.location
    ]
    assert matches, (
        f"Expected an api_breaking finding at schemas.py; "
        f"got findings: {[(f.kind, f.location) for f in sample_findings]}"
    )


def test_env_undocumented_payment_webhook_secret(sample_findings):
    """PAYMENT_WEBHOOK_SECRET usage in webhooks.py should fire env_undocumented."""
    matches = [
        f for f in sample_findings
        if f.kind == "env_undocumented"
        and "PAYMENT_WEBHOOK_SECRET" in f.evidence
    ]
    assert matches, (
        f"Expected an env_undocumented finding whose evidence contains "
        f"PAYMENT_WEBHOOK_SECRET; "
        f"got findings: {[(f.kind, f.evidence) for f in sample_findings]}"
    )


def test_total_findings_count(sample_findings):
    """At least 3 total findings must be detected in the sample-repo diff."""
    assert len(sample_findings) >= 3, (
        f"Expected >= 3 findings, got {len(sample_findings)}: "
        f"{[(f.kind, f.location) for f in sample_findings]}"
    )


# ---------------------------------------------------------------------------
# Unit test helpers
# ---------------------------------------------------------------------------

def _make_cs(*files: ChangedFile) -> ChangeSet:
    return ChangeSet(
        repo_path=".",
        from_tag="v1.0.0",
        to_tag="v1.1.0",
        files=list(files),
    )


# ---------------------------------------------------------------------------
# Unit tests — migration_no_code detector
# ---------------------------------------------------------------------------

def test_unit_migration_no_code_fires():
    """SQL ADD COLUMN with no Python reference should fire migration_no_code."""
    sql_file = ChangedFile(
        path="migrations/0010_add_coupon.sql",
        status="added",
        new_content="ALTER TABLE orders ADD COLUMN coupon_code TEXT;",
    )
    py_file = ChangedFile(
        path="app/unrelated.py",
        status="modified",
        new_content="# nothing here\n",
    )
    cs = _make_cs(sql_file, py_file)
    result = analyse(cs)
    kinds = [f.kind for f in result.findings]
    assert "migration_no_code" in kinds


def test_unit_migration_no_code_silent_when_referenced():
    """If the column name appears in a .py file, no finding should be raised."""
    sql_file = ChangedFile(
        path="migrations/0011_add_promo.sql",
        status="added",
        new_content="ALTER TABLE orders ADD COLUMN promo_code TEXT;",
    )
    py_file = ChangedFile(
        path="app/models.py",
        status="modified",
        new_content="promo_code = Column(String)\n",
    )
    cs = _make_cs(sql_file, py_file)
    result = analyse(cs)
    migration_findings = [f for f in result.findings if f.kind == "migration_no_code"]
    assert migration_findings == [], (
        f"Expected no migration_no_code finding but got: {migration_findings}"
    )


# ---------------------------------------------------------------------------
# Unit tests — api_breaking detector
# ---------------------------------------------------------------------------

def test_unit_api_breaking_fires():
    """Removing a field from a Response BaseModel should fire api_breaking."""
    old_content = (
        "from pydantic import BaseModel\n\n"
        "class FooResponse(BaseModel):\n"
        "    id: int\n"
        "    name: str\n"
        "    score: float\n"
    )
    new_content = (
        "from pydantic import BaseModel\n\n"
        "class FooResponse(BaseModel):\n"
        "    id: int\n"
        "    name: str\n"
        # score removed
    )
    patch = (
        " class FooResponse(BaseModel):\n"
        "     id: int\n"
        "     name: str\n"
        "-    score: float\n"
    )
    f = ChangedFile(
        path="app/schemas.py",
        status="modified",
        old_content=old_content,
        new_content=new_content,
        patch=patch,
    )
    result = analyse(_make_cs(f))
    assert any(
        fi.kind == "api_breaking" and "schemas.py" in fi.location
        for fi in result.findings
    )


def test_unit_api_breaking_silent_when_no_response_model():
    """A plain model (not *Response) should not trigger api_breaking."""
    old_content = (
        "from pydantic import BaseModel\n\n"
        "class Order(BaseModel):\n"
        "    id: int\n"
        "    name: str\n"
    )
    new_content = (
        "from pydantic import BaseModel\n\n"
        "class Order(BaseModel):\n"
        "    id: int\n"
        # name removed, but not a Response class
    )
    f = ChangedFile(
        path="app/models.py",
        status="modified",
        old_content=old_content,
        new_content=new_content,
        patch="-    name: str\n",
    )
    result = analyse(_make_cs(f))
    breaking = [fi for fi in result.findings if fi.kind == "api_breaking"]
    assert breaking == []


# ---------------------------------------------------------------------------
# Unit tests — env_undocumented detector
# ---------------------------------------------------------------------------

def test_unit_env_undocumented_fires(tmp_path):
    """An os.getenv call for an undocumented var should fire env_undocumented."""
    env_example = tmp_path / ".env.example"
    env_example.write_text("DATABASE_URL=sqlite:///./orders.db\n", encoding="utf-8")

    f = ChangedFile(
        path="app/webhooks.py",
        status="added",
        new_content='SECRET = os.getenv("MY_SECRET_KEY")\n',
    )
    cs = ChangeSet(
        repo_path=str(tmp_path),
        from_tag="v1.0.0",
        to_tag="v1.1.0",
        files=[f],
    )
    result = analyse(cs, repo_path=str(tmp_path))
    assert any(
        fi.kind == "env_undocumented" and "MY_SECRET_KEY" in fi.evidence
        for fi in result.findings
    )


def test_unit_env_undocumented_silent_when_documented(tmp_path):
    """A documented env var should NOT fire env_undocumented."""
    env_example = tmp_path / ".env.example"
    env_example.write_text("DATABASE_URL=sqlite:///./orders.db\n", encoding="utf-8")

    f = ChangedFile(
        path="app/config.py",
        status="modified",
        new_content='URL = os.getenv("DATABASE_URL", "sqlite:///./orders.db")\n',
    )
    cs = ChangeSet(
        repo_path=str(tmp_path),
        from_tag="v1.0.0",
        to_tag="v1.1.0",
        files=[f],
    )
    result = analyse(cs, repo_path=str(tmp_path))
    env_findings = [fi for fi in result.findings if fi.kind == "env_undocumented"]
    assert env_findings == []


# ---------------------------------------------------------------------------
# Unit tests — config_key_added detector
# ---------------------------------------------------------------------------

def test_unit_config_key_added_fires():
    """A new os.getenv assignment added to config.py should fire config_key_added."""
    patch = (
        " class Settings:\n"
        "+    NEW_KEY: str = os.getenv(\"NEW_KEY\", \"default\")\n"
    )
    f = ChangedFile(
        path="app/config.py",
        status="modified",
        patch=patch,
        old_content="class Settings:\n    pass\n",
        new_content='class Settings:\n    NEW_KEY: str = os.getenv("NEW_KEY", "default")\n',
    )
    result = analyse(_make_cs(f))
    assert any(fi.kind == "config_key_added" for fi in result.findings)
