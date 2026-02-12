#!/bin/bash

# Start Chat Agent standalone
# This script starts just the Chat Agent Flask service

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Starting Chat Agent...${NC}"

# Load .env from project root or decision-orchestration-agent (API key stays out of repo)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
for envfile in "$SCRIPT_DIR/.env" "$SCRIPT_DIR/Agents/decision-orchestration-agent/.env"; do
  if [ -f "$envfile" ]; then set -a; source "$envfile"; set +a; break; fi
done
export MISTRAL_MODEL="${MISTRAL_MODEL:-mistral-medium}"
export DB_HOST="${DB_HOST:-localhost}"
export DB_PORT=5432
export DB_NAME=smartcart_ai
export DB_USER=meghanarendrasimha
export DB_PASSWORD=Welcome@123
export DECISION_ORCHESTRATOR_URL=http://localhost:9000
export PORT=9006

# Navigate to chat agent directory
cd "$(dirname "$0")/Agents/decision-orchestration-agent/subagents/chat"

# Check if dependencies are installed
if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Installing dependencies...${NC}"
    if command -v pip3 &> /dev/null; then
        pip3 install -r requirements.txt
    elif command -v pip &> /dev/null; then
        pip install -r requirements.txt
    else
        echo -e "${RED}Error: pip not found. Please install pip${NC}"
        exit 1
    fi
fi

# Start the Flask app
echo -e "${GREEN}Starting Chat Agent on port 9006...${NC}"
echo -e "${GREEN}Chat Agent will be available at: http://localhost:9006${NC}"
echo -e "${YELLOW}Press Ctrl+C to stop${NC}"
echo ""

# Try python3 first, fallback to python
if command -v python3 &> /dev/null; then
    python3 agent.py
elif command -v python &> /dev/null; then
    python agent.py
else
    echo -e "${RED}Error: Python not found. Please install Python 3.8+${NC}"
    exit 1
fi
