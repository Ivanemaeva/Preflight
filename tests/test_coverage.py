# assisted-by: IBM Bob 2.0 quality-fix — function-level gap detection
"""Tests for app.coverage.analyse.

Integration tests run against sample-repo v1.0.0..v1.1.0.
Unit tests use synthetic ChangeSet / ChangedFile objects.
"""

from __future__ import annotations

import pytest

from app.gitutil import build_changeset
from app.coverage import analyse
from app.models import ChangeSet, ChangedFile, CoverageGap, CoveredFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _paths(items) -> list[str]:
    return [item.path for item in items]


def _make_cs(*files: ChangedFile) -> ChangeSet:
    """Build a minimal synthetic ChangeSet."""
    return ChangeSet(
        repo_path="./sample-repo",
        from_tag="v1.0.0",
        to_tag="v1.1.0",
        files=list(files),
    )


def _cf(
    path: str,
    status: str = "modified",
    new_content: str = "",
) -> ChangedFile:
    return ChangedFile(path=path, status=status, new_content=new_content)


# ---------------------------------------------------------------------------
# Integration tests — real sample-repo v1.0.0..v1.1.0
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def coverage():
    """Build coverage once for all integration assertions."""
    cs = build_changeset("v1.0.0", "v1.1.0", repo_path="./sample-repo")
    return analyse(cs, repo_path="./sample-repo")


def test_pricing_in_gaps(coverage):
    """app/pricing.py must appear in gaps (calculate_total_cents has no test)."""
    assert "app/pricing.py" in _paths(coverage.gaps), (
        f"Expected app/pricing.py in gaps; got gaps={_paths(coverage.gaps)}"
    )


def test_pricing_gap_function_level_reason(coverage):
    """pricing.py gap reason must name calculate_total_cents() specifically."""
    pricing_gap = next(
        (g for g in coverage.gaps if g.path == "app/pricing.py"), None
    )
    assert pricing_gap is not None, "app/pricing.py not found in gaps"
    assert "calculate_total_cents()" in pricing_gap.reason, (
        f"Expected function name in reason; got: {pricing_gap.reason!r}"
    )
    assert "tests/test_pricing.py" in pricing_gap.reason, (
        f"Expected test file name in reason; got: {pricing_gap.reason!r}"
    )


def test_pricing_stub_has_function_test(coverage):
    """Stub for pricing.py must have a test_calculate_total_cents skeleton."""
    pricing_stub = next(
        (s for s in coverage.stubs if "pricing" in s.path), None
    )
    assert pricing_stub is not None, "No stub found for pricing"
    assert "calculate_total_cents" in pricing_stub.content, (
        f"Expected calculate_total_cents in stub; got:\n{pricing_stub.content}"
    )


def test_webhooks_in_gaps(coverage):
    """app/webhooks.py must appear in gaps (new module, no test file)."""
    assert "app/webhooks.py" in _paths(coverage.gaps), (
        f"Expected app/webhooks.py in gaps; got gaps={_paths(coverage.gaps)}"
    )


def test_orders_in_covered(coverage):
    """app/routes/orders.py must appear in covered (tests/test_orders.py exists)."""
    assert "app/routes/orders.py" in _paths(coverage.covered), (
        f"Expected app/routes/orders.py in covered; got covered={_paths(coverage.covered)}"
    )


def test_stubs_have_content(coverage):
    """coverage.stubs must have at least one entry with non-empty content."""
    assert len(coverage.stubs) >= 1, "Expected at least one stub"
    non_empty = [s for s in coverage.stubs if s.content.strip()]
    assert non_empty, "Expected at least one stub with non-empty content"


def test_webhooks_gap_reason_new_module(coverage):
    """New module added with no test → reason must mention 'New module added'."""
    webhooks_gap = next(
        (g for g in coverage.gaps if g.path == "app/webhooks.py"), None
    )
    assert webhooks_gap is not None
    assert "New module" in webhooks_gap.reason
    # Ensure pricing.py does NOT use the wrong "New module" or "No test file
    # imports or references" message — it has a test file, just missing the fn
    pricing_gap = next(
        (g for g in coverage.gaps if g.path == "app/pricing.py"), None
    )
    assert pricing_gap is not None
    assert "No test file imports or references" not in pricing_gap.reason, (
        f"pricing.py has a test file; wrong reason: {pricing_gap.reason!r}"
    )


# ---------------------------------------------------------------------------
# Unit tests — synthetic ChangeSet objects (no git needed)
# ---------------------------------------------------------------------------

class TestNamingConvention:
    """naming-convention detection: tests/test_<stem>.py."""

    def test_no_test_file_goes_to_gaps(self, tmp_path):
        """A source file with no matching test file should appear in gaps."""
        cs = _make_cs(_cf("app/calculator.py", status="added", new_content="def add(a, b): return a+b\n"))
        cov = analyse(cs, repo_path=str(tmp_path))
        assert "app/calculator.py" in _paths(cov.gaps)
        assert "app/calculator.py" not in _paths(cov.covered)

    def test_matching_test_file_by_name_covers_all_symbols(self, tmp_path):
        """When tests/test_foo.py exists and covers all symbols, file is covered."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        # test file references 'my_func'
        (tests_dir / "test_foo.py").write_text("def test_my_func():\n    assert my_func() == 1\n")
        cs = _make_cs(_cf("app/foo.py", new_content="def my_func():\n    return 1\n"))
        cov = analyse(cs, repo_path=str(tmp_path))
        assert "app/foo.py" in _paths(cov.covered)
        assert "app/foo.py" not in _paths(cov.gaps)

    def test_test_file_missing_new_symbol_causes_gap(self, tmp_path):
        """When tests/test_foo.py exists but misses a new function, file is a gap."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        # test file only tests old_func, not new_func
        (tests_dir / "test_foo.py").write_text("def test_old_func():\n    assert old_func() == 0\n")
        old_content = "def old_func():\n    return 0\n"
        new_content = "def old_func():\n    return 0\n\ndef new_func():\n    return 99\n"
        cs = _make_cs(ChangedFile(
            path="app/foo.py",
            status="modified",
            old_content=old_content,
            new_content=new_content,
        ))
        cov = analyse(cs, repo_path=str(tmp_path))
        assert "app/foo.py" in _paths(cov.gaps)
        gap = next(g for g in cov.gaps if g.path == "app/foo.py")
        # Reason must mention the specific function, not a generic module message
        assert "new_func()" in gap.reason

    def test_gap_reason_mentions_test_file(self, tmp_path):
        """Gap reason must name the existing test file when one exists."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        # test file does not call or reference new_fn anywhere (no word match)
        (tests_dir / "test_foo.py").write_text("def test_existing():\n    existing()\n")
        old_content = "def existing(): pass\n"
        new_content = "def existing(): pass\ndef new_fn(): pass\n"
        cs = _make_cs(ChangedFile(
            path="app/foo.py",
            status="modified",
            old_content=old_content,
            new_content=new_content,
        ))
        cov = analyse(cs, repo_path=str(tmp_path))
        gap = next((g for g in cov.gaps if g.path == "app/foo.py"), None)
        assert gap is not None
        assert "tests/test_foo.py" in gap.reason


class TestImportScan:
    """import-scan detection: scanning tests/ for import statements."""

    def test_import_scan_finds_module(self, tmp_path):
        """A test file that does `import app.bar` should mark app/bar.py covered."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        # Naming convention file does NOT exist (no test_bar.py)
        # but test_integration.py imports the module
        (tests_dir / "test_integration.py").write_text(
            "import app.bar\n\ndef test_something():\n    assert app.bar.do_thing() == 1\n"
        )
        cs = _make_cs(
            _cf("app/bar.py", new_content="def do_thing():\n    return 1\n")
        )
        cov = analyse(cs, repo_path=str(tmp_path))
        assert "app/bar.py" in _paths(cov.covered)

    def test_from_import_scan_finds_module(self, tmp_path):
        """A test file that does `from app.baz import fn` should mark app/baz.py covered."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_baz.py").write_text(
            "from app.baz import fn\n\ndef test_fn():\n    assert fn() == 42\n"
        )
        cs = _make_cs(
            _cf("app/baz.py", new_content="def fn():\n    return 42\n")
        )
        cov = analyse(cs, repo_path=str(tmp_path))
        assert "app/baz.py" in _paths(cov.covered)

    def test_no_import_goes_to_gaps(self, tmp_path):
        """If no test file imports the module, file goes to gaps."""
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "test_other.py").write_text("import app.other\n")
        cs = _make_cs(_cf("app/unrelated.py", status="added", new_content="def foo(): pass\n"))
        cov = analyse(cs, repo_path=str(tmp_path))
        assert "app/unrelated.py" in _paths(cov.gaps)


class TestStubs:
    """Stub generation."""

    def test_stub_content_is_non_empty(self, tmp_path):
        """A gap should produce a stub with non-empty content."""
        cs = _make_cs(_cf("app/missing.py", status="added", new_content="def go(): pass\n"))
        cov = analyse(cs, repo_path=str(tmp_path))
        assert len(cov.stubs) >= 1
        assert cov.stubs[0].content.strip() != ""

    def test_stub_path_follows_convention(self, tmp_path):
        """Stub path should be tests/test_<stem>.py."""
        cs = _make_cs(_cf("app/mymod.py", status="added", new_content="def go(): pass\n"))
        cov = analyse(cs, repo_path=str(tmp_path))
        stub_paths = [s.path for s in cov.stubs]
        assert "tests/test_mymod.py" in stub_paths

    def test_stub_reason_added(self, tmp_path):
        """Added file with no tests should have 'New module added' reason."""
        cs = _make_cs(_cf("app/brand_new.py", status="added", new_content="def run(): pass\n"))
        cov = analyse(cs, repo_path=str(tmp_path))
        gap = next((g for g in cov.gaps if g.path == "app/brand_new.py"), None)
        assert gap is not None
        assert "New module added" in gap.reason

    def test_stub_reason_modified(self, tmp_path):
        """Modified file with no tests and a new function → gap mentions function name."""
        cs = _make_cs(ChangedFile(
            path="app/existing.py",
            status="modified",
            old_content="def run(): pass\n",
            new_content="def run(): pass\ndef extra(): pass\n",
        ))
        cov = analyse(cs, repo_path=str(tmp_path))
        gap = next((g for g in cov.gaps if g.path == "app/existing.py"), None)
        assert gap is not None
        # No test file at all → the "No test file" generic reason applies
        assert "No test file" in gap.reason

    def test_stub_has_per_function_skeleton(self, tmp_path):
        """Stub for a file with uncovered functions should have per-function tests."""
        cs = _make_cs(ChangedFile(
            path="app/alpha.py",
            status="added",
            old_content="",
            new_content="def alpha_one(): pass\ndef alpha_two(): pass\n",
        ))
        cov = analyse(cs, repo_path=str(tmp_path))
        stub = next((s for s in cov.stubs if "alpha" in s.path), None)
        assert stub is not None
        assert "alpha_one" in stub.content
        assert "alpha_two" in stub.content


class TestEdgeCases:
    """Edge-case filtering."""

    def test_test_files_ignored(self, tmp_path):
        """Files under tests/ should not be analysed."""
        cs = _make_cs(_cf("tests/test_something.py", new_content="def test_x(): pass\n"))
        cov = analyse(cs, repo_path=str(tmp_path))
        assert len(cov.gaps) == 0
        assert len(cov.covered) == 0

    def test_non_python_files_ignored(self, tmp_path):
        """Non-.py files should not be analysed."""
        cs = _make_cs(_cf("migrations/0001_init.sql", new_content="CREATE TABLE foo;"))
        cov = analyse(cs, repo_path=str(tmp_path))
        assert len(cov.gaps) == 0
        assert len(cov.covered) == 0
