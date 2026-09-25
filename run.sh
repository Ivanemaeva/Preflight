#!/usr/bin/env bash
# assisted-by: IBM Bob 2.0 quality-fix — host 127.0.0.1, python3 -m uvicorn, task 2026-09-25
# Usage: ./run.sh [repo_path]
# repo_path defaults to ./sample-repo

set -euo pipefail

REPO_PATH="${1:-./sample-repo}"
export PREFLIGHT_REPO="$REPO_PATH"

echo "Installing dependencies..."
pip3 install -r requirements.txt -q

echo "Starting PreFlight on http://127.0.0.1:8000 (repo: $REPO_PATH)"
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
