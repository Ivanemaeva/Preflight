# assisted-by: IBM Bob 2.0 quality-fix — docstring-safe + test-file-safe rules
"""Diff analysis engine for PreFlight.

Public API
----------
analyse(changeset: ChangeSet) -> list[FileChange]
    Classify every changed file as 'breaking', 'risky', or 'safe'.
"""

from __future__ import annotations

import ast
import re
from typing import Optional

from app.models import ChangeSet, ChangedFile, FileChange


# ---------------------------------------------------------------------------
# Helpers — AST-based symbol extraction
# ---------------------------------------------------------------------------

def _public_symbols(source: str) -> set[str]:
    """Return set of public module-level function/class names in *source*.

    A name is public when it does NOT start with '_'.
    Returns empty set on parse failure.
    """
    if not source.strip():
        return set()
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    names: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                names.add(node.name)
    return names


def _public_function_signatures(source: str) -> dict[str, list[str]]:
    """Return {func_name: [param_names…]} for all public module-level functions.

    Includes type annotation strings so that annotation-only changes are
    detected.  Returns empty dict on parse failure.
    """
    if not source.strip():
        return {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    sigs: dict[str, list[str]] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                params: list[str] = []
                for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                    ann = ""
                    if arg.annotation:
                        ann = ast.unparse(arg.annotation)
                    params.append(f"{arg.arg}:{ann}")
                if node.args.vararg:
                    params.append(f"*{node.args.vararg.arg}")
                if node.args.kwarg:
                    params.append(f"**{node.args.kwarg.arg}")
                sigs[node.name] = params
    return sigs


# ---------------------------------------------------------------------------
# Helpers — Pydantic Response schema field extraction
# ---------------------------------------------------------------------------

_RESPONSE_CLASS_RE = re.compile(r"class\s+\w*Response\s*\(.*?BaseModel.*?\)", re.MULTILINE)


def _has_response_model(source: str) -> bool:
    """Return True if *source* contains a class ...Response(BaseModel) definition."""
    return bool(_RESPONSE_CLASS_RE.search(source))


def _response_fields(source: str) -> dict[str, set[str]]:
    """Return {ClassName: {field_names…}} for all *Response(BaseModel) classes.

    Field names are the names of class-level annotated assignments
    (including simple `name: type` declarations).
    """
    if not source.strip():
        return {}
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}
    result: dict[str, set[str]] = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            if not node.name.endswith("Response"):
                continue
            # check it inherits from BaseModel (best-effort name check)
            bases = [ast.unparse(b) for b in node.bases]
            if not any("BaseModel" in b for b in bases):
                continue
            fields: set[str] = set()
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                    if not item.target.id.startswith("_"):
                        fields.add(item.target.id)
            result[node.name] = fields
    return result


# ---------------------------------------------------------------------------
# Per-file classification
# ---------------------------------------------------------------------------

def _is_python(path: str) -> bool:
    return path.endswith(".py")


def _is_migration(path: str) -> bool:
    return "migrations/" in path or "migrations\\" in path


def _is_test_file(path: str) -> bool:
    """Return True for files under a tests/ directory."""
    return path.startswith("tests/") or "/tests/" in path


def _strip_docstrings(source: str) -> ast.Module | None:
    """Parse *source* and return an AST with all docstring nodes removed.

    Returns None on parse failure.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    class _DocstringStripper(ast.NodeTransformer):
        def _strip(self, node: ast.AST) -> ast.AST:
            if (
                isinstance(node.body[0], ast.Expr)  # type: ignore[attr-defined]
                and isinstance(node.body[0].value, ast.Constant)  # type: ignore[attr-defined]
                and isinstance(node.body[0].value.value, str)
            ):
                node.body = node.body[1:]  # type: ignore[attr-defined]
            return node

        def visit_Module(self, node: ast.Module) -> ast.AST:
            self.generic_visit(node)
            return self._strip(node) if node.body else node

        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
            self.generic_visit(node)
            return self._strip(node) if node.body else node

        visit_AsyncFunctionDef = visit_FunctionDef  # type: ignore[assignment]

        def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
            self.generic_visit(node)
            return self._strip(node) if node.body else node

    return _DocstringStripper().visit(tree)


def _only_docstring_or_comment_change(old: str, new: str) -> bool:
    """Return True when old and new differ only in docstrings or comment lines.

    Strategy:
    1. Strip comments from both texts.
    2. Parse both stripped texts and remove docstring nodes via AST.
    3. Compare ast.dump() of the two resulting trees.
    """
    if not old.strip() or not new.strip():
        return False

    def _strip_comments(src: str) -> str:
        """Remove # comment lines (keep non-comment lines, preserving structure)."""
        lines = []
        for line in src.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("#"):
                lines.append("")
            else:
                lines.append(line)
        return "\n".join(lines)

    old_nc = _strip_comments(old)
    new_nc = _strip_comments(new)

    old_tree = _strip_docstrings(old_nc)
    new_tree = _strip_docstrings(new_nc)

    if old_tree is None or new_tree is None:
        return False

    return ast.dump(old_tree) == ast.dump(new_tree)


def _classify_file(
    cf: ChangedFile,
    breaking_response_classes: set[str],
) -> FileChange:
    """Classify a single ChangedFile.  Returns a FileChange.

    breaking_response_classes — set of Response class names that were already
    determined to be breaking (used in the second-pass router check).
    """
    path = cf.path
    status = cf.status
    lines_total = cf.lines_added + cf.lines_removed

    # ------------------------------------------------------------------
    # Rule 0a — test files are safe unless deleted
    # ------------------------------------------------------------------
    if _is_test_file(path) and status != "deleted":
        return FileChange(
            path=path,
            status=status,
            risk="safe",
            reason="Test file modified (not deleted)",
            lines_added=cf.lines_added,
            lines_removed=cf.lines_removed,
        )

    # ------------------------------------------------------------------
    # Rule 0b — docstring / comment-only Python change is safe
    # ------------------------------------------------------------------
    if _is_python(path) and status == "modified":
        if _only_docstring_or_comment_change(cf.old_content, cf.new_content):
            return FileChange(
                path=path,
                status=status,
                risk="safe",
                reason="Only docstrings or comments changed — no logic modified",
                lines_added=cf.lines_added,
                lines_removed=cf.lines_removed,
            )

    # ------------------------------------------------------------------
    # Rule 1 & 2 — Python AST checks (breaking)
    # ------------------------------------------------------------------
    if _is_python(path) and status != "added":
        old_symbols = _public_symbols(cf.old_content)
        new_symbols = _public_symbols(cf.new_content)

        removed = old_symbols - new_symbols
        if removed:
            return FileChange(
                path=path,
                status=status,
                risk="breaking",
                reason=f"Public symbol(s) removed: {', '.join(sorted(removed))}",
                lines_added=cf.lines_added,
                lines_removed=cf.lines_removed,
            )

        # Rename detection: net-zero change in count but different names
        added_names = new_symbols - old_symbols
        if added_names and len(old_symbols) == len(new_symbols):
            # Some old names are gone and the same count of new names appeared
            old_gone = old_symbols - new_symbols
            if old_gone:
                return FileChange(
                    path=path,
                    status=status,
                    risk="breaking",
                    reason=f"Public symbol(s) renamed: {', '.join(sorted(old_gone))} → {', '.join(sorted(added_names))}",
                    lines_added=cf.lines_added,
                    lines_removed=cf.lines_removed,
                )

        # Rule 2 — signature change
        old_sigs = _public_function_signatures(cf.old_content)
        new_sigs = _public_function_signatures(cf.new_content)
        for fname, old_params in old_sigs.items():
            if fname in new_sigs and new_sigs[fname] != old_params:
                return FileChange(
                    path=path,
                    status=status,
                    risk="breaking",
                    reason=f"Signature of public function '{fname}' changed",
                    lines_added=cf.lines_added,
                    lines_removed=cf.lines_removed,
                )

    # ------------------------------------------------------------------
    # Rule 3 — Pydantic Response schema field removed / renamed
    # ------------------------------------------------------------------
    if _is_python(path) and status != "added":
        if _has_response_model(cf.old_content) or _has_response_model(cf.new_content):
            old_fields_map = _response_fields(cf.old_content)
            new_fields_map = _response_fields(cf.new_content)
            all_classes = set(old_fields_map) | set(new_fields_map)
            for cls in all_classes:
                old_f = old_fields_map.get(cls, set())
                new_f = new_fields_map.get(cls, set())
                dropped = old_f - new_f
                if dropped:
                    return FileChange(
                        path=path,
                        status=status,
                        risk="breaking",
                        reason=f"{cls}: field(s) removed or renamed: {', '.join(sorted(dropped))}",
                        lines_added=cf.lines_added,
                        lines_removed=cf.lines_removed,
                    )

    # ------------------------------------------------------------------
    # Rule 3b — Python router/view file that uses a breaking Response model
    # ------------------------------------------------------------------
    if _is_python(path) and status == "modified" and breaking_response_classes:
        content = cf.new_content or cf.old_content
        for cls_name in breaking_response_classes:
            if cls_name in content:
                return FileChange(
                    path=path,
                    status=status,
                    risk="breaking",
                    reason=f"Uses {cls_name} whose response schema had a breaking field change",
                    lines_added=cf.lines_added,
                    lines_removed=cf.lines_removed,
                )

    # ------------------------------------------------------------------
    # Rule 4 — new Python file
    # ------------------------------------------------------------------
    if _is_python(path) and status == "added":
        return FileChange(
            path=path,
            status=status,
            risk="risky",
            reason="New Python source file — no test coverage established",
            lines_added=cf.lines_added,
            lines_removed=cf.lines_removed,
        )

    # ------------------------------------------------------------------
    # Rule 5 — modified Python, > 20 lines changed
    # ------------------------------------------------------------------
    if _is_python(path) and status == "modified" and lines_total > 20:
        return FileChange(
            path=path,
            status=status,
            risk="risky",
            reason=f"Modified Python source with {lines_total} lines changed (> 20)",
            lines_added=cf.lines_added,
            lines_removed=cf.lines_removed,
        )

    # ------------------------------------------------------------------
    # Rule 6 — migration file added or modified
    # ------------------------------------------------------------------
    if _is_migration(path) and status in ("added", "modified"):
        return FileChange(
            path=path,
            status=status,
            risk="risky",
            reason="Migration file added or modified — requires DBA review",
            lines_added=cf.lines_added,
            lines_removed=cf.lines_removed,
        )

    # ------------------------------------------------------------------
    # Rule 7 — any other modified Python source
    # ------------------------------------------------------------------
    if _is_python(path) and status == "modified":
        return FileChange(
            path=path,
            status=status,
            risk="risky",
            reason="Modified Python source",
            lines_added=cf.lines_added,
            lines_removed=cf.lines_removed,
        )

    # ------------------------------------------------------------------
    # Rule 8 — everything else is safe
    # ------------------------------------------------------------------
    return FileChange(
        path=path,
        status=status,
        risk="safe",
        reason="Non-breaking change (docs, config, or no-logic modification)",
        lines_added=cf.lines_added,
        lines_removed=cf.lines_removed,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyse(changeset: ChangeSet) -> list[FileChange]:
    """Classify every file in *changeset* as 'breaking', 'risky', or 'safe'.

    Returns a list of FileChange objects in the same order as
    changeset.files.
    """
    # First pass: identify breaking Response classes so that router files
    # referencing them can be escalated to breaking in the second pass.
    breaking_response_classes: set[str] = set()
    for cf in changeset.files:
        if not _is_python(cf.path) or cf.status == "added":
            continue
        if _has_response_model(cf.old_content) or _has_response_model(cf.new_content):
            old_fields_map = _response_fields(cf.old_content)
            new_fields_map = _response_fields(cf.new_content)
            all_classes = set(old_fields_map) | set(new_fields_map)
            for cls in all_classes:
                old_f = old_fields_map.get(cls, set())
                new_f = new_fields_map.get(cls, set())
                if old_f - new_f:
                    breaking_response_classes.add(cls)

    # Second pass: classify every file
    results: list[FileChange] = []
    for cf in changeset.files:
        fc = _classify_file(cf, breaking_response_classes)
        results.append(fc)

    return results
