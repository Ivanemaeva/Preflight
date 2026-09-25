#!/usr/bin/env bash
# assisted-by: IBM Bob 2.0 Phase 3b — run script
# Usage: ./run.sh [repo_path]
# repo_path defaults to ./sample-repo

set -euo pipefail

REPO_PATH="${1:-./sample-repo}"
export PREFLIGHT_REPO="$REPO_PATH"

echo "Installing dependencies..."
pip install -r requirements.txt -q

echo "Starting PreFlight on http://localhost:8000 (repo: $REPO_PATH)"
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
