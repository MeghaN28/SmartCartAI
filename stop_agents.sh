#!/bin/bash

# SmartCartAI Agents Stop Script

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Stopping SmartCartAI Agents...${NC}"

# Stop agents by PID files if they exist
if [ -d "logs" ]; then
    for pidfile in logs/*.pid; do
        if [ -f "$pidfile" ]; then
            PID=$(cat "$pidfile")
            if ps -p $PID > /dev/null 2>&1; then
                kill $PID
                echo -e "${GREEN}Stopped process $PID${NC}"
            fi
            rm "$pidfile"
        fi
    done
fi

# Also kill any remaining agent processes
pkill -f "python3 agent.py" 2>/dev/null
pkill -f "python agent.py" 2>/dev/null
pkill -f "Python agent.py" 2>/dev/null
pkill -f "decision-orchestration-agent/.*/agent.py" 2>/dev/null
pkill -f "inventory-agent/agent.py" 2>/dev/null

# Force free known agent ports in case stale processes remain
for port in 9000 9002 9003 9004 9005 9006 9007; do
    PIDS=$(lsof -t -iTCP:$port -sTCP:LISTEN 2>/dev/null)
    if [ -n "$PIDS" ]; then
        kill $PIDS 2>/dev/null
    fi
done

echo -e "${GREEN}All agents stopped.${NC}"
