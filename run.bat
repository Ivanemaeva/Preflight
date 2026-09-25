@echo off
REM assisted-by: IBM Bob 2.0 quality-fix — Windows run script, task 2026-09-25
REM Usage: run.bat [repo_path]
REM repo_path defaults to .\sample-repo

SET REPO_PATH=%1
IF "%REPO_PATH%"=="" SET REPO_PATH=.\sample-repo
SET PREFLIGHT_REPO=%REPO_PATH%

echo Installing dependencies...
pip install -r requirements.txt -q

echo Starting PreFlight on http://127.0.0.1:8000 (repo: %REPO_PATH%)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
