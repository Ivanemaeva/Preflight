# assisted-by: IBM Bob 2.0 four-fix task — repo-path test existence, range validation, drafter dedup, diff reason, task 2026-09-25
"""FastAPI application — serves the dashboard and the API.

Routes
------
GET /                  → index.html  (dashboard)
GET /api/tags          → list of tag strings
GET /api/report        → full Report JSON  (?from=v1.0.0&to=v1.1.0)
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import gitutil
from app.models import Report
from app.report import build_report

app = FastAPI(title="PreFlight", version="1.0.0")

_STATIC_DIR = Path(__file__).parent / "static"

# Serve static files (CSS, JS, etc.) if the directory has more than just index.html
if _STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    """Serve the dashboard."""
    index = _STATIC_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return FileResponse(str(index))


@app.get("/api/tags")
def api_tags() -> list[str]:
    """Return all tags in the configured repository, newest-first."""
    repo_path = os.getenv("PREFLIGHT_REPO", "./sample-repo")
    try:
        return gitutil.list_tags(repo_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/report", response_model=Report)
def api_report(
    from_tag: str = Query(..., alias="from"),
    to_tag: str = Query(..., alias="to"),
) -> JSONResponse:
    """Run the full PreFlight analysis and return the Report as JSON."""
    repo_path = os.getenv("PREFLIGHT_REPO", "./sample-repo")
    try:
        report = build_report(from_tag, to_tag, repo_path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # Use model_dump with by_alias=True so "from"/"to" keys round-trip correctly.
    return JSONResponse(content=report.model_dump(by_alias=True))
