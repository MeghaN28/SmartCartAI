#!/bin/bash

# Check which agents are running

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Checking SmartCartAI Agents Status...${NC}"
echo ""

agents=(
    "9004:Risk Assessment"
    "9001:Feasibility"
    "9002:Cost Impact"
    "9003:Explanation"
    "9006:Chat Agent"
    "9000:Decision Orchestrator"
    "9005:Inventory Monitoring"
)

all_running=true

for agent_info in "${agents[@]}"; do
    port="${agent_info%%:*}"
    name="${agent_info##*:}"
    
    if curl -s http://localhost:$port/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} $name (port $port) - ${GREEN}RUNNING${NC}"
    else
        echo -e "${RED}✗${NC} $name (port $port) - ${RED}NOT RUNNING${NC}"
        all_running=false
    fi
done

echo ""
if [ "$all_running" = true ]; then
    echo -e "${GREEN}All agents are running!${NC}"
else
    echo -e "${YELLOW}Some agents are not running. Start them with: ./start_agents.sh${NC}"
fi

echo ""
echo "Backend Status:"
if curl -s http://localhost:8080/api/inventory > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Java Backend (port 8080) - RUNNING${NC}"
else
    echo -e "${RED}✗ Java Backend (port 8080) - NOT RUNNING${NC}"
fi
