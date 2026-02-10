#!/bin/bash

# SmartCartAI - Stop All Services

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}Stopping all SmartCartAI services...${NC}"

# Stop Python agents
if [ -f "stop_agents.sh" ]; then
    ./stop_agents.sh
fi

# Stop Java backend
if [ -d "logs" ] && [ -f "logs/backend.pid" ]; then
    BACKEND_PID=$(cat logs/backend.pid)
    if ps -p $BACKEND_PID > /dev/null 2>&1; then
        kill $BACKEND_PID
        echo -e "${GREEN}Stopped Java backend (PID: $BACKEND_PID)${NC}"
    fi
    rm logs/backend.pid
fi

# Stop frontend
if [ -d "logs" ] && [ -f "logs/frontend.pid" ]; then
    FRONTEND_PID=$(cat logs/frontend.pid)
    if ps -p $FRONTEND_PID > /dev/null 2>&1; then
        kill $FRONTEND_PID
        echo -e "${GREEN}Stopped frontend (PID: $FRONTEND_PID)${NC}"
    fi
    rm logs/frontend.pid
fi

# Kill any remaining processes
pkill -f "spring-boot:run" 2>/dev/null
pkill -f "expo start" 2>/dev/null
pkill -f "npm start" 2>/dev/null

echo -e "${GREEN}All services stopped.${NC}"
