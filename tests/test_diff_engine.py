# assisted-by: IBM Bob 2.0 four-fix task — repo-path test existence, range validation, drafter dedup, diff reason, task 2026-09-25
"""Tests for app.diff_engine.analyse().

Covers:
  1. Integration tests against sample-repo v1.0.0..v1.1.0
  2. Synthetic unit tests for individual classification rules
"""

from __future__ import annotations

import pytest

from app.gitutil import build_changeset
from app.diff_engine import analyse
from app.models import ChangedFile, ChangeSet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_changeset(*files: ChangedFile) -> ChangeSet:
    """Build a minimal synthetic ChangeSet from the given ChangedFile objects."""
    return ChangeSet(
        repo_path=".",
        from_tag="v0",
        to_tag="v1",
        commits=[],
        files=list(files),
    )


def _make_file(**kwargs) -> ChangedFile:
    """Create a ChangedFile with sensible defaults, overridable via kwargs."""
    defaults = dict(
        path="app/example.py",
        status="modified",
        patch="",
        old_content="",
        new_content="",
        lines_added=0,
        lines_removed=0,
    )
    defaults.update(kwargs)
    return ChangedFile(**defaults)


# ---------------------------------------------------------------------------
# Integration tests — sample-repo v1.0.0..v1.1.0
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sample_changes():
    """Build changeset and run analysis once for all integration tests."""
    cs = build_changeset("v1.0.0", "v1.1.0", repo_path="./sample-repo")
    return {fc.path: fc for fc in analyse(cs)}


def test_schemas_breaking(sample_changes):
    """app/schemas.py — OrderResponse.total renamed to total_cents → breaking."""
    fc = sample_changes.get("app/schemas.py")
    assert fc is not None, "app/schemas.py not found in changeset"
    assert fc.risk == "breaking", (
        f"Expected 'breaking' for app/schemas.py, got '{fc.risk}'. Reason: {fc.reason}"
    )


def test_orders_route_breaking(sample_changes):
    """app/routes/orders.py — uses OrderResponse whose schema changed → breaking."""
    fc = sample_changes.get("app/routes/orders.py")
    assert fc is not None, "app/routes/orders.py not found in changeset"
    assert fc.risk == "breaking", (
        f"Expected 'breaking' for app/routes/orders.py, got '{fc.risk}'. Reason: {fc.reason}"
    )


def test_pricing_risky(sample_changes):
    """app/pricing.py — new public function added (calculate_total_cents) → risky."""
    fc = sample_changes.get("app/pricing.py")
    assert fc is not None, "app/pricing.py not found in changeset"
    assert fc.risk == "risky", (
        f"Expected 'risky' for app/pricing.py, got '{fc.risk}'. Reason: {fc.reason}"
    )


def test_pricing_reason_names_new_function(sample_changes):
    """app/pricing.py reason must mention 'New public function(s) added' with the function name."""
    fc = sample_changes.get("app/pricing.py")
    assert fc is not None, "app/pricing.py not found in changeset"
    assert "New public function(s) added" in fc.reason, (
        f"Expected 'New public function(s) added' in reason; got: {fc.reason!r}"
    )
    assert "calculate_total_cents" in fc.reason, (
        f"Expected function name in reason; got: {fc.reason!r}"
    )


def test_webhooks_risky(sample_changes):
    """app/webhooks.py — new Python file → risky."""
    fc = sample_changes.get("app/webhooks.py")
    assert fc is not None, "app/webhooks.py not found in changeset"
    assert fc.risk == "risky", (
        f"Expected 'risky' for app/webhooks.py, got '{fc.risk}'. Reason: {fc.reason}"
    )


def test_migration_risky(sample_changes):
    """migrations/0003_add_discount_code.sql — migration added → risky."""
    fc = sample_changes.get("migrations/0003_add_discount_code.sql")
    assert fc is not None, "migrations/0003_add_discount_code.sql not found in changeset"
    assert fc.risk == "risky", (
        f"Expected 'risky' for migration, got '{fc.risk}'. Reason: {fc.reason}"
    )


def test_at_least_one_safe(sample_changes):
    """At least one file in the changeset should be classified as 'safe'."""
    safe_files = [fc for fc in sample_changes.values() if fc.risk == "safe"]
    assert safe_files, (
        "Expected at least one 'safe' file in sample-repo v1.0.0..v1.1.0 changeset. "
        f"All risks: {[(p, fc.risk) for p, fc in sample_changes.items()]}"
    )


def test_config_py_is_safe(sample_changes):
    """app/config.py only changed its module docstring — must be safe."""
    fc = sample_changes.get("app/config.py")
    assert fc is not None, "app/config.py not found in changeset"
    assert fc.risk == "safe", (
        f"Expected 'safe' for app/config.py (docstring-only change), "
        f"got '{fc.risk}'. Reason: {fc.reason}"
    )


# ---------------------------------------------------------------------------
# Unit tests — synthetic ChangedFile objects (no git repo required)
# ---------------------------------------------------------------------------

class TestBreakingPublicSymbolRemoved:
    """Rule 1: removing a module-level public function/class → breaking."""

    def test_removed_function(self):
        old = "def foo():\n    pass\n\ndef bar():\n    pass\n"
        new = "def foo():\n    pass\n"
        cf = _make_file(
            path="app/utils.py",
            status="modified",
            old_content=old,
            new_content=new,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "breaking"
        assert "bar" in result[0].reason

    def test_removed_class(self):
        old = "class Foo:\n    pass\n\nclass Bar:\n    pass\n"
        new = "class Foo:\n    pass\n"
        cf = _make_file(
            path="app/views.py",
            status="modified",
            old_content=old,
            new_content=new,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "breaking"

    def test_private_removal_is_not_breaking(self):
        """Removing a private symbol (_foo) must NOT be breaking."""
        old = "def _foo():\n    pass\n\ndef bar():\n    pass\n"
        new = "def bar():\n    pass\n"
        cf = _make_file(
            path="app/utils.py",
            status="modified",
            old_content=old,
            new_content=new,
        )
        result = analyse(_make_changeset(cf))
        # bar is still present; _foo is private — should be risky or safe, not breaking
        assert result[0].risk != "breaking"


class TestBreakingSignatureChange:
    """Rule 2: changing parameter names/count/annotations of a public function → breaking."""

    def test_param_removed(self):
        old = "def process(item, flag=False):\n    pass\n"
        new = "def process(item):\n    pass\n"
        cf = _make_file(
            path="app/processor.py",
            status="modified",
            old_content=old,
            new_content=new,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "breaking"
        assert "process" in result[0].reason

    def test_param_added(self):
        old = "def send(payload):\n    pass\n"
        new = "def send(payload, retry: int = 0):\n    pass\n"
        cf = _make_file(
            path="app/sender.py",
            status="modified",
            old_content=old,
            new_content=new,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "breaking"

    def test_annotation_change(self):
        old = "def compute(x: int) -> int:\n    return x\n"
        new = "def compute(x: str) -> str:\n    return x\n"
        cf = _make_file(
            path="app/compute.py",
            status="modified",
            old_content=old,
            new_content=new,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "breaking"

    def test_unchanged_signature_not_breaking(self):
        src = "def greet(name: str) -> str:\n    return f'Hello {name}'\n"
        cf = _make_file(
            path="app/greet.py",
            status="modified",
            old_content=src,
            new_content=src + "\n# comment\n",
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk != "breaking"


class TestBreakingResponseSchema:
    """Rule 3: Pydantic Response schema field removed/renamed → breaking."""

    def test_field_removed(self):
        old = (
            "from pydantic import BaseModel\n"
            "class OrderResponse(BaseModel):\n"
            "    id: int\n"
            "    total: float\n"
        )
        new = (
            "from pydantic import BaseModel\n"
            "class OrderResponse(BaseModel):\n"
            "    id: int\n"
        )
        cf = _make_file(
            path="app/schemas.py",
            status="modified",
            old_content=old,
            new_content=new,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "breaking"
        assert "total" in result[0].reason

    def test_field_renamed(self):
        old = (
            "from pydantic import BaseModel\n"
            "class ItemResponse(BaseModel):\n"
            "    price: float\n"
        )
        new = (
            "from pydantic import BaseModel\n"
            "class ItemResponse(BaseModel):\n"
            "    price_cents: int\n"
        )
        cf = _make_file(
            path="app/item_schemas.py",
            status="modified",
            old_content=old,
            new_content=new,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "breaking"

    def test_field_added_is_not_breaking(self):
        """Adding a new field to a Response model is not breaking."""
        old = (
            "from pydantic import BaseModel\n"
            "class UserResponse(BaseModel):\n"
            "    id: int\n"
        )
        new = (
            "from pydantic import BaseModel\n"
            "class UserResponse(BaseModel):\n"
            "    id: int\n"
            "    email: str\n"
        )
        cf = _make_file(
            path="app/user_schemas.py",
            status="modified",
            old_content=old,
            new_content=new,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk != "breaking"


class TestRiskyRules:
    """Rules 4–7: various risky classifications."""

    def test_new_python_file_is_risky(self):
        """Rule 4: newly added Python file → risky."""
        cf = _make_file(
            path="app/newmodule.py",
            status="added",
            new_content="def hello():\n    pass\n",
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "risky"

    def test_modified_python_adds_new_public_function_reason(self):
        """Rule 4b: modified Python adding a new public function → specific reason."""
        cf = _make_file(
            path="app/pricing.py",
            status="modified",
            old_content="def existing(): pass\n",
            new_content="def existing(): pass\ndef brand_new(): pass\n",
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "risky"
        assert "New public function(s) added" in result[0].reason
        assert "brand_new" in result[0].reason

    def test_modified_python_adds_new_class_reason(self):
        """Rule 4b: modified Python adding a new public class → specific reason."""
        cf = _make_file(
            path="app/models.py",
            status="modified",
            old_content="class Existing: pass\n",
            new_content="class Existing: pass\nclass NewModel: pass\n",
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "risky"
        assert "New public function(s) added" in result[0].reason
        assert "NewModel" in result[0].reason

    def test_modified_python_no_new_public_symbols_uses_generic_reason(self):
        """If a modified file does not add new public symbols, use the generic reason."""
        cf = _make_file(
            path="app/utils.py",
            status="modified",
            old_content="def foo(): return 1\n",
            new_content="def foo(): return 2\n",
            lines_added=1,
            lines_removed=1,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "risky"
        # Should NOT use the new-function reason
        assert "New public function(s) added" not in result[0].reason

    def test_modified_python_large_diff_is_risky(self):
        """Rule 5: modified Python with > 20 lines changed → risky."""
        old_lines = "\n".join(f"x{i} = {i}" for i in range(15))
        new_lines = "\n".join(f"x{i} = {i * 2}" for i in range(15))  # logic changed
        cf = _make_file(
            path="app/big_change.py",
            status="modified",
            old_content=old_lines,
            new_content=new_lines,
            lines_added=15,
            lines_removed=10,  # total = 25 > 20
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "risky"

    def test_migration_file_is_risky(self):
        """Rule 6: SQL migration file → risky."""
        cf = _make_file(
            path="migrations/0004_add_column.sql",
            status="added",
            new_content="ALTER TABLE foo ADD COLUMN bar TEXT;",
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "risky"

    def test_modified_python_small_diff_is_risky(self):
        """Rule 7: modified Python (small change, no breaking criteria) → risky."""
        src = "def foo():\n    pass\n"
        cf = _make_file(
            path="app/small.py",
            status="modified",
            old_content=src,
            new_content=src + "x = 1\n",  # real logic change, not a comment
            lines_added=1,
            lines_removed=0,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "risky"


class TestSafeRule:
    """Rule 8: non-Python, non-migration files → safe."""

    def test_readme_is_safe(self):
        cf = _make_file(
            path="README.md",
            status="modified",
            old_content="# Old\n",
            new_content="# New\n",
            lines_added=1,
            lines_removed=1,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "safe"

    def test_config_toml_is_safe(self):
        cf = _make_file(
            path="pyproject.toml",
            status="modified",
            old_content='version = "1.0.0"\n',
            new_content='version = "1.1.0"\n',
            lines_added=1,
            lines_removed=1,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "safe"

    def test_sql_file_not_in_migrations_is_safe(self):
        """An SQL file outside the migrations/ directory should be safe."""
        cf = _make_file(
            path="scripts/seed_data.sql",
            status="modified",
            old_content="INSERT INTO foo VALUES (1);\n",
            new_content="INSERT INTO foo VALUES (2);\n",
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "safe"


class TestDocstringOnlySafe:
    """Rule 0b: Python files where only docstrings/comments changed → safe."""

    def test_module_docstring_change_is_safe(self):
        """Adding/changing module-level docstring only → safe."""
        old = 'def foo():\n    pass\n'
        new = '"""New module docstring."""\ndef foo():\n    pass\n'
        cf = _make_file(
            path="app/mymod.py",
            status="modified",
            old_content=old,
            new_content=new,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "safe", (
            f"Expected safe for docstring-only change; got {result[0].risk}: {result[0].reason}"
        )

    def test_function_docstring_change_is_safe(self):
        """Changing a function docstring only → safe."""
        old = 'def bar():\n    """Old doc."""\n    return 1\n'
        new = 'def bar():\n    """New, improved doc."""\n    return 1\n'
        cf = _make_file(
            path="app/utils.py",
            status="modified",
            old_content=old,
            new_content=new,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "safe"

    def test_comment_only_change_is_safe(self):
        """Changing only # comment lines → safe."""
        old = "# old comment\ndef baz():\n    return 42\n"
        new = "# new comment, updated\ndef baz():\n    return 42\n"
        cf = _make_file(
            path="app/baz.py",
            status="modified",
            old_content=old,
            new_content=new,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "safe"

    def test_logic_change_is_not_safe(self):
        """Changing actual logic is not classified as safe."""
        old = 'def calc():\n    return 1\n'
        new = 'def calc():\n    return 2\n'
        cf = _make_file(
            path="app/calc.py",
            status="modified",
            old_content=old,
            new_content=new,
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk != "safe"


class TestTestFileSafe:
    """Rule 0a: files under tests/ are safe unless deleted."""

    def test_modified_test_file_is_safe(self):
        """Modifying a test file → safe."""
        cf = _make_file(
            path="tests/test_foo.py",
            status="modified",
            old_content="def test_x(): pass\n",
            new_content="def test_x(): pass\ndef test_y(): pass\n",
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "safe"

    def test_added_test_file_is_safe(self):
        """Adding a new test file → safe."""
        cf = _make_file(
            path="tests/test_new.py",
            status="added",
            new_content="def test_new(): pass\n",
        )
        result = analyse(_make_changeset(cf))
        assert result[0].risk == "safe"

    def test_deleted_test_file_is_not_safe(self):
        """Deleting a test file should NOT be safe (the breaking/risky rules decide)."""
        cf = _make_file(
            path="tests/test_gone.py",
            status="deleted",
            old_content="def test_x(): pass\n",
            new_content="",
        )
        result = analyse(_make_changeset(cf))
        # Should not be safe — a deleted test file is a risk signal
        assert result[0].risk != "safe"
