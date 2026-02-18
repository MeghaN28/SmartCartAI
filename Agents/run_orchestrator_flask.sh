#!/bin/bash
# Run Decision Orchestrator on Flask (port 9000). Execute from project root: ./Agents/run_orchestrator_flask.sh
set -e
cd "$(dirname "$0")/decision-orchestration-agent"
echo "Starting Decision Orchestrator (Flask) on port 9000..."
echo "Stop with Ctrl+C. Restart this after changing orchestrator code."
exec python agent.py
