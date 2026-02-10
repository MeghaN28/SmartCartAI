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

echo -e "${GREEN}All agents stopped.${NC}"
