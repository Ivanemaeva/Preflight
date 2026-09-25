# assisted-by: IBM Bob 2.0 Phase 3a — COVERAGE MAPPER
"""Coverage analyser for PreFlight.

Public API
----------
analyse(changeset, repo_path) -> Coverage
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List

from app.models import ChangeSet, Coverage, CoveredFile, CoverageGap, CoverageStub


_IMPORT_RE = re.compile(
    r"(?:^|\s)(?:import|from)\s+([\w\.]+)"
)

_DEF_RE = re.compile(r"^(?:def|class)\s+(\w+)", re.MULTILINE)


def _module_dotpath(source_path: str) -> str:
    """Convert a file path like app/foo/bar.py to its dotted module name app.foo.bar."""
    return source_path.replace("\\", "/").removesuffix(".py").replace("/", ".")


def _stem(source_path: str) -> str:
    """Return the bare filename stem, e.g. 'bar' from 'app/foo/bar.py'."""
    return Path(source_path).stem


def _convention_test_path(source_path: str) -> str:
    """Return the naming-convention test path, e.g. 'tests/test_bar.py'."""
    return f"tests/test_{_stem(source_path)}.py"


def _find_test_files_by_convention(
    convention_path: str, tests_dir: Path
) -> List[str]:
    """Return [convention_path] if the file actually exists on disk, else []."""
    candidate = tests_dir / Path(convention_path).name
    if candidate.exists():
        return [convention_path]
    return []


def _find_test_files_by_import(
    module_dotpath: str, tests_dir: Path
) -> List[str]:
    """Scan every .py file in tests_dir for imports of module_dotpath."""
    found: List[str] = []
    if not tests_dir.exists():
        return found
    for test_file in tests_dir.rglob("*.py"):
        try:
            text = test_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Match: `import app.foo.bar` or `from app.foo.bar import`
        pattern = re.compile(
            rf"(?:^|\s)(?:import\s+{re.escape(module_dotpath)}"
            rf"|from\s+{re.escape(module_dotpath)}\s+import)",
            re.MULTILINE,
        )
        if pattern.search(text):
            rel = test_file.relative_to(tests_dir.parent).as_posix()
            found.append(rel)
    return found


def _uncovered_functions(new_content: str, test_texts: List[str]) -> List[str]:
    """Return function/class names defined in new_content that appear in none of test_texts."""
    defined = _DEF_RE.findall(new_content)
    if not defined:
        return []
    combined_tests = "\n".join(test_texts)
    missing = [name for name in defined if name not in combined_tests]
    return missing


def _make_stub_content(source_path: str) -> str:
    """Generate a placeholder test file for source_path."""
    module = _module_dotpath(source_path)
    stem = _stem(source_path)
    return (
        f"# Auto-generated stub — replace with real tests\n"
        f"# Source module: {module}\n"
        f"\n"
        f"import pytest\n"
        f"\n"
        f"\n"
        f"def test_{stem}_placeholder():\n"
        f"    \"\"\"TODO: write tests for {module}\"\"\"\n"
        f"    raise NotImplementedError(\"Stub — not yet implemented\")\n"
    )


def analyse(changeset: ChangeSet, repo_path: str | None = None) -> Coverage:
    """Analyse coverage for all Python source files in *changeset*.

    Parameters
    ----------
    changeset:  the ChangeSet built by gitutil.build_changeset
    repo_path:  path to the repository root; defaults to ./sample-repo
    """
    resolved = repo_path or os.getenv("PREFLIGHT_REPO", "./sample-repo")
    tests_dir = Path(resolved) / "tests"

    gaps: List[CoverageGap] = []
    covered: List[CoveredFile] = []
    stubs: List[CoverageStub] = []

    for cf in changeset.files:
        path = cf.path.replace("\\", "/")

        # Only Python source files outside tests/
        if not path.endswith(".py"):
            continue
        if path.startswith("tests/") or "/tests/" in path:
            continue

        # Treat as "added" when status is added OR old_content is empty
        # (gitpython sometimes returns change_type=None for new files)
        is_new = cf.status == "added" or cf.old_content == ""

        module_dotpath = _module_dotpath(path)
        convention_path = _convention_test_path(path)

        # 1. Find by naming convention
        test_files = _find_test_files_by_convention(convention_path, tests_dir)

        # 2. Find by import scan (add any not already found)
        import_hits = _find_test_files_by_import(module_dotpath, tests_dir)
        for hit in import_hits:
            if hit not in test_files:
                test_files.append(hit)

        # 3. If test files found, check whether all defined symbols are covered
        if test_files:
            # Gather text of each test file for symbol checking
            test_texts: List[str] = []
            for tf_rel in test_files:
                tf_abs = Path(resolved) / tf_rel
                if tf_abs.exists():
                    try:
                        test_texts.append(
                            tf_abs.read_text(encoding="utf-8", errors="replace")
                        )
                    except OSError:
                        pass

            missing_fns = _uncovered_functions(cf.new_content, test_texts)
            if missing_fns:
                # Test file exists but doesn't cover new symbols → gap
                reason = (
                    "New module added with no corresponding test file"
                    if is_new
                    else "No test file imports or references this module"
                )
                gaps.append(
                    CoverageGap(
                        path=path,
                        reason=reason,
                        suggested_test=convention_path,
                    )
                )
                stubs.append(
                    CoverageStub(path=convention_path, content=_make_stub_content(path))
                )
            else:
                covered.append(CoveredFile(path=path, tests=test_files))
        else:
            # No test file found at all
            reason = (
                "New module added with no corresponding test file"
                if is_new
                else "No test file imports or references this module"
            )
            gaps.append(
                CoverageGap(
                    path=path,
                    reason=reason,
                    suggested_test=convention_path,
                )
            )
            stubs.append(
                CoverageStub(path=convention_path, content=_make_stub_content(path))
            )

    return Coverage(gaps=gaps, covered=covered, stubs=stubs)
