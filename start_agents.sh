#!/bin/bash

# SmartCartAI Agents Startup Script
# This script starts all agents with proper environment variables

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Starting SmartCartAI Agents (MCP-first)...${NC}"

# Chat + Orchestrator are MCP-only now. Use the MCP-first startup script.
exec "$(cd "$(dirname "$0")" && pwd)/start_agents_mcp.sh"

# Load env from project root or decision-orchestration-agent (API key stays out of repo)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
for envfile in "$SCRIPT_DIR/.env" "$SCRIPT_DIR/Agents/decision-orchestration-agent/.env"; do
  if [ -f "$envfile" ]; then set -a; source "$envfile"; set +a; break; fi
done
export MISTRAL_MODEL="${MISTRAL_MODEL:-mistral-medium}"

# Database configuration
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=smartcart_ai
export DB_USER=meghanarendrasimha
export DB_PASSWORD=Welcome@123

# Agent URLs
export DECISION_AGENT_URL=http://localhost:9000/orchestrate
export MONITORING_INTERVAL=30

# Create log directory
mkdir -p logs

echo -e "${YELLOW}Starting Subagents...${NC}"

# Start Risk Assessment Agent (port 9004) - nohup keeps it running after terminal closes
cd Agents/decision-orchestration-agent/subagents/risk-assessment
export PORT=9004
nohup python3 agent.py >> ../../../../logs/risk-assessment.log 2>&1 &
RISK_PID=$!
echo -e "${GREEN}Risk Assessment Agent started (PID: $RISK_PID)${NC}"
cd ../../../../

# Start Feasibility & Cost Impact Agent (port 9002, merged)
cd Agents/decision-orchestration-agent/subagents/cost-impact
export PORT=9002
nohup python3 agent.py >> ../../../../logs/cost-impact.log 2>&1 &
COST_PID=$!
echo -e "${GREEN}Feasibility & Cost Impact Agent started (PID: $COST_PID)${NC}"
cd ../../../../

# Start Explanation Agent (port 9003)
cd Agents/decision-orchestration-agent/subagents/explanation
export PORT=9003
nohup python3 agent.py >> ../../../../logs/explanation.log 2>&1 &
EXPLANATION_PID=$!
echo -e "${GREEN}Explanation Agent started (PID: $EXPLANATION_PID)${NC}"
cd ../../../../

# Start Food Bank Agent (port 9007) – nearest food banks for donate/discard suggestions
cd Agents/decision-orchestration-agent/subagents/food-bank
export PORT=9007
nohup python3 agent.py >> ../../../../logs/food-bank.log 2>&1 &
FOODBANK_PID=$!
echo -e "${GREEN}Food Bank Agent started (PID: $FOODBANK_PID)${NC}"
cd ../../../../

# Start Chat Agent (port 9006)
cd Agents/decision-orchestration-agent/subagents/chat
export PORT=9006
export DECISION_ORCHESTRATOR_URL=http://localhost:9000
nohup python3 agent.py >> ../../../../logs/chat-agent.log 2>&1 &
CHAT_PID=$!
echo -e "${GREEN}Chat Agent started (PID: $CHAT_PID) on port 9006${NC}"
echo -e "${YELLOW}  Chat Agent URL: http://localhost:9006/chat${NC}"
cd ../../../../

# Start Dashboard Agent (port 9008)
cd Agents/dashboard-agent
export PORT=9008
nohup python3 agent.py >> ../../logs/dashboard-agent.log 2>&1 &
DASHBOARD_PID=$!
echo -e "${GREEN}Dashboard Agent started (PID: $DASHBOARD_PID) on port 9008${NC}"
echo -e "${YELLOW}  Dashboard Agent URL: http://localhost:9008/item-insights${NC}"
cd ../../

# Wait a moment for subagents to start
sleep 2

echo -e "${YELLOW}Starting Orchestrator Agent...${NC}"
# Start Decision Orchestrator Agent (port 9000)
cd Agents/decision-orchestration-agent
export PORT=9000
nohup python3 agent.py >> ../../logs/orchestrator.log 2>&1 &
ORCHESTRATOR_PID=$!
echo -e "${GREEN}Decision Orchestrator Agent started (PID: $ORCHESTRATOR_PID)${NC}"
cd ../../

# Wait a moment for orchestrator to start
sleep 2

echo -e "${YELLOW}Starting Inventory Monitoring Agent...${NC}"
# Start Inventory Monitoring Agent (port 9005)
cd Agents/inventory-agent
export PORT=9005
nohup python3 agent.py >> ../../logs/inventory-agent.log 2>&1 &
INVENTORY_PID=$!
echo -e "${GREEN}Inventory Monitoring Agent started (PID: $INVENTORY_PID)${NC}"
cd ../../

# Save PIDs to file for easy stopping
echo "$RISK_PID" > logs/risk-assessment.pid
echo "$COST_PID" > logs/cost-impact.pid
echo "$EXPLANATION_PID" > logs/explanation.pid
echo "$FOODBANK_PID" > logs/food-bank.pid
echo "$CHAT_PID" > logs/chat-agent.pid
echo "$DASHBOARD_PID" > logs/dashboard-agent.pid
echo "$ORCHESTRATOR_PID" > logs/orchestrator.pid
echo "$INVENTORY_PID" > logs/inventory-agent.pid

echo ""
echo -e "${GREEN}All agents started successfully!${NC}"
echo ""
echo "Agent Status:"
echo "  - Risk Assessment:        http://localhost:9004/health"
echo "  - Feasibility & Cost:      http://localhost:9002/health"
echo "  - Explanation:            http://localhost:9003/health"
echo "  - Food Bank:               http://localhost:9007/health"
echo "  - Chat Agent:              http://localhost:9006/health"
echo "  - Dashboard Agent:         http://localhost:9008/health"
echo "  - Decision Orchestrator:   http://localhost:9000/health"
echo "  - Inventory Monitoring:    http://localhost:9005/health"
echo ""
echo "Logs are in the 'logs/' directory"
echo ""
echo "Agents will keep running even if you close this terminal (started with nohup)."
echo "To stop all agents, run: ./stop_agents.sh"
echo "Or manually kill processes: pkill -f 'python agent.py'"
