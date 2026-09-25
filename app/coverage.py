# assisted-by: IBM Bob 2.0 final-polish — fix stub import for modules with no public functions, task 2026-09-25
"""Coverage analyser for PreFlight.

Public API
----------
analyse(changeset, repo_path) -> Coverage
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path
from typing import List

from app.models import ChangeSet, Coverage, CoveredFile, CoverageGap, CoverageStub


_IMPORT_RE = re.compile(
    r"(?:^|\s)(?:import|from)\s+([\w\.]+)"
)


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


def _public_functions_in_source(source: str) -> List[str]:
    """Return names of public module-level functions in *source* (via AST).

    A function is public when its name does not start with '_'.
    Returns [] on empty source or parse failure.
    """
    if not source.strip():
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    names: List[str] = []
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                names.append(node.name)
    return names


def _added_or_changed_public_functions(
    old_content: str, new_content: str
) -> List[str]:
    """Return public function names that were added or were already present in new_content.

    For a newly added file (old_content is empty) every public function is
    considered "added".  For a modified file only functions whose name is new
    relative to old_content are returned (i.e. genuine additions).
    """
    new_fns = _public_functions_in_source(new_content)
    if not old_content.strip():
        # Brand-new file — all functions are new
        return new_fns
    old_fns = set(_public_functions_in_source(old_content))
    return [fn for fn in new_fns if fn not in old_fns]


def _uncovered_added_functions(
    old_content: str,
    new_content: str,
    test_texts: List[str],
) -> List[str]:
    """Return added/new public function names that are not referenced in any test text.

    A function name is considered referenced when it appears as a whole word
    (i.e. surrounded by word boundaries) in at least one test file.
    """
    candidates = _added_or_changed_public_functions(old_content, new_content)
    if not candidates:
        return []
    combined_tests = "\n".join(test_texts)
    uncovered: List[str] = []
    for fn in candidates:
        pattern = re.compile(r"\b" + re.escape(fn) + r"\b")
        if not pattern.search(combined_tests):
            uncovered.append(fn)
    return uncovered


def _make_stub_content(
    source_path: str,
    uncovered_fns: List[str] | None = None,
    add_to_existing: bool = False,
) -> str:
    """Generate stub content for source_path.

    If *add_to_existing* is True the stub begins with a header comment
    telling the developer to ADD the snippet to the existing file rather than
    creating a new one.

    If *uncovered_fns* is supplied, emit one skeleton test per function.
    """
    module = _module_dotpath(source_path)
    stem = _stem(source_path)
    lines: List[str] = []
    if uncovered_fns:
        import_line = f"from {module} import {', '.join(uncovered_fns)}"
    else:
        import_line = f"import {module}"

    if add_to_existing:
        lines += [
            "# ADD the following tests to the existing file",
            f"# Source module: {module}",
            "",
            import_line,
            "",
        ]
    else:
        lines += [
            "# Auto-generated stub — replace with real tests",
            f"# Source module: {module}",
            "",
            "import pytest",
            import_line,
            "",
        ]
    if uncovered_fns:
        for fn in uncovered_fns:
            lines += [
                "",
                f"def test_{fn}():",
                f'    """TODO: test {module}.{fn}"""',
                '    raise NotImplementedError("Stub — not yet implemented")',
            ]
    else:
        lines += [
            "",
            f"def test_{stem}_placeholder():",
            f'    """TODO: write tests for {module}"""',
            '    raise NotImplementedError("Stub — not yet implemented")',
        ]
    return "\n".join(lines) + "\n"


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

        # 3. Gather text of each discovered test file
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

        # 4. Determine which added/changed public functions are untested
        uncovered = _uncovered_added_functions(
            cf.old_content, cf.new_content, test_texts
        )

        # Does the suggested test file already exist on disk (in the ANALYZED repo)?
        preflight_test_exists = (Path(resolved) / convention_path).exists()

        if test_files:
            if uncovered:
                # Test file(s) exist but don't reference some new functions
                fn_list = ", ".join(f"{fn}()" for fn in uncovered)
                test_file_str = ", ".join(test_files)
                reason = (
                    f"{fn_list} {'was' if len(uncovered) == 1 else 'were'} added "
                    f"but no test calls {'it' if len(uncovered) == 1 else 'them'} "
                    f"({test_file_str} exists but never references "
                    f"{'it' if len(uncovered) == 1 else 'them'})"
                )
                gaps.append(
                    CoverageGap(
                        path=path,
                        reason=reason,
                        suggested_test=convention_path,
                    )
                )
                stubs.append(
                    CoverageStub(
                        path=convention_path,
                        content=_make_stub_content(path, uncovered, add_to_existing=preflight_test_exists),
                    )
                )
            else:
                covered.append(CoveredFile(path=path, tests=test_files))
        else:
            # No test file found at all
            if is_new:
                reason = "New module added with no corresponding test file"
            else:
                reason = "No test file imports or references this module"
            gaps.append(
                CoverageGap(
                    path=path,
                    reason=reason,
                    suggested_test=convention_path,
                )
            )
            stubs.append(
                CoverageStub(
                    path=convention_path,
                    content=_make_stub_content(path, uncovered or None, add_to_existing=preflight_test_exists),
                )
            )

    return Coverage(gaps=gaps, covered=covered, stubs=stubs)
