#!/usr/bin/env bash
# assisted-by: IBM Bob 2.0 final-polish — bundle clone on first run, task 2026-09-25
# Usage: ./run.sh [repo_path]
# repo_path defaults to ./sample-repo

set -euo pipefail

REPO_PATH="${1:-./sample-repo}"
export PREFLIGHT_REPO="$REPO_PATH"

if [ ! -d "$REPO_PATH" ]; then
  if [ -f "sample-repo.bundle" ]; then
    echo "sample-repo not found — cloning from sample-repo.bundle..."
    git clone sample-repo.bundle "$REPO_PATH"
  else
    echo "ERROR: $REPO_PATH does not exist and sample-repo.bundle was not found." >&2
    exit 1
  fi
fi

echo "Installing dependencies..."
pip3 install -r requirements.txt -q

echo "Starting PreFlight on http://127.0.0.1:8000 (repo: $REPO_PATH)"
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
