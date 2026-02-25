#!/bin/bash
# Run Chat Agent on Flask (port 9006). Execute from project root: ./Agents/run_chat_flask.sh
set -e
cd "$(dirname "$0")/decision-orchestration-agent/subagents/chat"
echo "Starting Chat Agent (Flask) on port 9006..."
echo "Stop with Ctrl+C. Code changes will auto-reload."
PYTHON_BIN="${PYTHON_BIN:-python3}"
if command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi
exec "$PYTHON_BIN" agent.py
