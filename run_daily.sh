#!/usr/bin/env bash
# Wrapper for cron/launchd - activates the venv, runs the report, logs output.
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p logs
source venv/bin/activate
python generate_report.py >> "logs/run-$(date +%F).log" 2>&1
