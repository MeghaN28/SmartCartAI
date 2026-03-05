#!/bin/bash

# SmartCartAI - Start All Services
# This script provides instructions and can start services in background

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}SmartCartAI - Service Startup Guide${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}To start all services, open 3 terminals and run:${NC}"
echo ""
echo -e "${GREEN}TERMINAL 1 - Python Agents:${NC}"
echo "  cd $(pwd)"
echo "  ./start_agents.sh"
echo ""
echo -e "${GREEN}TERMINAL 2 - Java Backend:${NC}"
echo "  cd $(pwd)/SmartCartAIBackend"
echo "  ./mvnw spring-boot:run"
echo ""
echo -e "${GREEN}TERMINAL 3 - Frontend (React Native):${NC}"
echo "  cd $(pwd)/SmartCartAIFrontEnd/mobile"
echo "  npm start"
echo ""
echo -e "${YELLOW}Or use this script to start all in background:${NC}"
echo "  ./start_all.sh --background"
echo ""

if [ "$1" == "--background" ]; then
    echo -e "${GREEN}Starting all services in background...${NC}"
    # Load optional root env for security/runtime config
    if [ -f ".env" ]; then
        set -a
        source ".env"
        set +a
    fi
    export JWT_ENFORCE="${JWT_ENFORCE:-true}"
    export JWT_SECRET="${JWT_SECRET:-smartcart-local-jwt-secret-change-me-32chars}"
    export APP_AUTH_USERNAME="${APP_AUTH_USERNAME:-admin}"
    export APP_AUTH_PASSWORD="${APP_AUTH_PASSWORD:-change-me}"
    export AGENT_SHARED_TOKEN="${AGENT_SHARED_TOKEN:-smartcart-local-agent-token}"
    
    # Start Python agents
    echo -e "${YELLOW}Starting Python agents...${NC}"
    bash ./start_agents.sh
    
    # Wait a bit for agents to start
    sleep 3
    
    # Start Java backend
    echo -e "${YELLOW}Starting Java backend...${NC}"
    cd SmartCartAIBackend
    ./mvnw spring-boot:run > ../logs/backend.log 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > ../logs/backend.pid
    echo -e "${GREEN}Java backend started (PID: $BACKEND_PID)${NC}"
    cd ..
    
    # Wait a bit for backend to start
    sleep 5
    
    # Start frontend
    echo -e "${YELLOW}Starting React Native frontend...${NC}"
    cd SmartCartAIFrontEnd/mobile
    npm start > ../../logs/frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > ../../logs/frontend.pid
    echo -e "${GREEN}Frontend started (PID: $FRONTEND_PID)${NC}"
    cd ../..
    
    echo ""
    echo -e "${GREEN}All services started in background!${NC}"
    echo ""
    echo "Service Status:"
    echo "  - Python Agents:     Check logs/inventory-agent.log, logs/orchestrator.log, etc."
    echo "  - Java Backend:      http://localhost:8080"
    echo "  - Frontend:          Expo dev server (check terminal or logs/frontend.log)"
    echo ""
    echo "To stop all services: ./stop_all.sh"
else
    echo -e "${YELLOW}Run with --background flag to start all services automatically.${NC}"
fi
