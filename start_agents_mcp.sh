#!/bin/bash

# SmartCartAI Startup Script (MCP-first)
# Chat + Orchestrator run as MCP HTTP servers (9100+).
# Subagents (risk/cost/explanation/food-bank) remain Flask REST services (9000+) because the orchestrator
# still calls them via HTTP POST.
#
# Usage:
#   ./start_agents_mcp.sh
#
# MCP endpoints will be available at:
#   - Chat Agent:            http://localhost:9106/mcp
#   - Decision Orchestrator: http://localhost:9100/mcp
# Flask REST endpoints will be available at:
#   - Risk Assessment:        http://localhost:9004/risk
#   - Feasibility & Cost:     http://localhost:9002/feasibility-and-cost
#   - Explanation:            http://localhost:9003/explain
#   - Food Bank:              http://localhost:9007/nearest
#   - Inventory Agent:        http://localhost:9005/query
#   - Dashboard Agent:        http://localhost:9008/item-insights

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}Starting SmartCartAI (MCP-first)...${NC}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Load env from project root or decision-orchestration-agent (keep secrets out of repo)
for envfile in "$SCRIPT_DIR/.env" "$SCRIPT_DIR/Agents/decision-orchestration-agent/.env"; do
  if [ -f "$envfile" ]; then set -a; source "$envfile"; set +a; break; fi
done

mkdir -p logs

export MCP_HOST="${MCP_HOST:-0.0.0.0}"

echo -e "${YELLOW}Starting Flask subagents (required by orchestrator)...${NC}"

unset SMARTCART_AGENT_MODE || true

cd "$SCRIPT_DIR/Agents/decision-orchestration-agent/subagents/risk-assessment"
PORT=9004 nohup python3 agent.py >> "$SCRIPT_DIR/logs/risk-assessment.log" 2>&1 &
echo -e "${GREEN}Risk (Flask) started on 9004${NC}"

cd "$SCRIPT_DIR/Agents/decision-orchestration-agent/subagents/cost-impact"
PORT=9002 nohup python3 agent.py >> "$SCRIPT_DIR/logs/cost-impact.log" 2>&1 &
echo -e "${GREEN}Feasibility+Cost (Flask) started on 9002${NC}"

cd "$SCRIPT_DIR/Agents/decision-orchestration-agent/subagents/explanation"
PORT=9003 nohup python3 agent.py >> "$SCRIPT_DIR/logs/explanation.log" 2>&1 &
echo -e "${GREEN}Explanation (Flask) started on 9003${NC}"

cd "$SCRIPT_DIR/Agents/decision-orchestration-agent/subagents/food-bank"
PORT=9007 nohup python3 agent.py >> "$SCRIPT_DIR/logs/food-bank.log" 2>&1 &
echo -e "${GREEN}Food Bank (Flask) started on 9007${NC}"

cd "$SCRIPT_DIR/Agents/inventory-agent"
PORT=9005 nohup python3 agent.py >> "$SCRIPT_DIR/logs/inventory-agent.log" 2>&1 &
echo -e "${GREEN}Inventory Agent (Flask) started on 9005${NC}"

cd "$SCRIPT_DIR/Agents/dashboard-agent"
PORT=9008 nohup python3 agent.py >> "$SCRIPT_DIR/logs/dashboard-agent.log" 2>&1 &
echo -e "${GREEN}Dashboard Agent (Flask) started on 9008${NC}"

echo -e "${YELLOW}Starting MCP servers (Chat + Orchestrator)...${NC}"

export SMARTCART_AGENT_MODE=mcp

cd "$SCRIPT_DIR/Agents/decision-orchestration-agent/subagents/chat"
MCP_PORT=9106 nohup python3 agent.py >> "$SCRIPT_DIR/logs/mcp-chat.log" 2>&1 &
echo -e "${GREEN}Chat MCP started on 9106${NC}"

cd "$SCRIPT_DIR/Agents/decision-orchestration-agent"
MCP_PORT=9100 nohup python3 agent.py >> "$SCRIPT_DIR/logs/mcp-orchestrator.log" 2>&1 &
echo -e "${GREEN}Orchestrator MCP started on 9100${NC}"

echo ""
echo -e "${GREEN}Services started.${NC}"
echo ""
echo "MCP endpoints:"
echo "  - Orchestrator:  http://localhost:9100/mcp"
echo "  - Chat:          http://localhost:9106/mcp"
echo ""
echo "Flask endpoints (internal subagents + DB helpers):"
echo "  - Risk:          http://localhost:9004/risk"
echo "  - Feas+Cost:     http://localhost:9002/feasibility-and-cost"
echo "  - Explanation:   http://localhost:9003/explain"
echo "  - Food bank:     http://localhost:9007/nearest"
echo "  - Inventory:     http://localhost:9005/query"
echo "  - Dashboard:     http://localhost:9008/item-insights"
echo ""
echo "Logs: logs/*.log"

