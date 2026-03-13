# SmartCartAI Agents Setup Guide

This guide explains how to set up and run the Inventory Monitoring Agent and Decision Orchestrator Agent system.

## Overview

The system consists of:
1. **Chat Agent** (user-facing) – Open endpoint where the user interacts. Calls the Inventory Agent with the user query, then the Decision Orchestrator per item; returns the answer to the user and saves suggestions to the Suggestion tab.
2. **Inventory Monitoring Agent** – Sees the database for the user query (low stock, expired, near expiring, waste, etc.). Exposes `POST /query` for the Chat Agent and `POST /inventory` for events; can send signals to the Decision Orchestrator.
3. **Decision Orchestrator Agent** – Receives signals (per item) and coordinates subagents to produce prescriptive recommendations.
4. **Subagents**:
   - Risk Assessment Agent
   - Feasibility Agent
   - Cost & Operational Impact Agent
   - **Food Bank Agent** (finds nearest food banks for donate/discard suggestions; optional)
   - Explanation Generation Agent (produces the final explanation shown to the user and stored in the Suggestion tab)

**Request flow:** User → Chat Agent → Inventory Agent (DB query) → items back to Chat → for each item: Decision Orchestrator → Risk → Feasibility → Cost Impact → (Food Bank when discard/donate) → Explanation → recommendation + explanation back to Chat → user reply + Suggestion tab.

## Prerequisites

- Python 3.8+
- PostgreSQL database with SmartCartAI schema
- Mistral API key (optional, for LLM features)
- Java 17+ and Maven (for backend)

## Database Setup

Ensure PostgreSQL is running and the SmartCartAI schema is created:

```bash
# Create database (if not exists)
createdb -U meghanarendrasimha smartcart_ai

# Run schema
psql -U meghanarendrasimha -d smartcart_ai < database/schema.sql

# Run migrations (facility, food_banks, suggestions.donation_info)
psql -U meghanarendrasimha -d smartcart_ai -f database/migrations/add_facility_food_banks_donation.sql
# Optional: add_expiry_and_price.sql, add_suggestion_discount_waste.sql if not already applied

# Import sample data (optional)
psql -U meghanarendrasimha -d smartcart_ai -c "\copy inventory FROM 'Dataset/inventory_master_50_unique.csv' CSV HEADER"
psql -U meghanarendrasimha -d smartcart_ai -c "\copy sales FROM 'Dataset/sales_50.csv' CSV HEADER"
psql -U meghanarendrasimha -d smartcart_ai -c "\copy consumption FROM 'Dataset/consumption_50.csv' CSV HEADER"
```

## Environment Variables

Create `.env` files or set environment variables:

### Inventory Monitoring Agent

**Option 1: Use .env file (Recommended)**
A `.env` file has been created in `Agents/inventory-agent/` with the database credentials configured.

**Option 2: Set environment variables manually**
```bash
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=smartcart_ai
export DB_USER=meghanarendrasimha
export DB_PASSWORD=Welcome@123
export DECISION_AGENT_URL=http://localhost:9000/orchestrate
export MONITORING_INTERVAL=30
export PORT=9005
```

### Decision Orchestrator Agent

**Option 1: Use .env file (Recommended)**
A `.env` file has been created in `Agents/decision-orchestration-agent/` with the Mistral API key configured.

**Option 2: Set environment variables manually**
```bash
export MISTRAL_API_KEY=<your-mistral-api-key>
export MISTRAL_MODEL=mistral-medium
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=smartcart_ai
export DB_USER=meghanarendrasimha
export DB_PASSWORD=Welcome@123
export PORT=9000
```

### Subagents

**Option 1: Use .env files (Recommended)**
`.env` files have been created for each subagent with the database credentials configured.

**Option 2: Set environment variables manually**
```bash
# Database (for all subagents)
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=smartcart_ai
export DB_USER=meghanarendrasimha
export DB_PASSWORD=Welcome@123

# Risk Assessment
export PORT=9004

# Feasibility
export PORT=9001

# Cost Impact
export PORT=9002

# Explanation
export PORT=9003
export MISTRAL_API_KEY=<your-mistral-api-key>
```

**Note:** `.env` files have been created for all subagents with the database credentials and Mistral API key configured.

## Installation

### 1. Install Inventory Monitoring Agent

```bash
cd Agents/inventory-agent
pip install -r requirements.txt
```

### 2. Install Decision Orchestrator Agent

```bash
cd Agents/decision-orchestration-agent
pip install -r requirements.txt
```

### 3. Install Subagents

```bash
# Risk Assessment
cd Agents/decision-orchestration-agent/subagents/risk-assessment
pip install -r requirements.txt

# Feasibility
cd Agents/decision-orchestration-agent/subagents/feasibility
pip install -r requirements.txt

# Cost Impact
cd Agents/decision-orchestration-agent/subagents/cost-impact
pip install -r requirements.txt

# Explanation
cd Agents/decision-orchestration-agent/subagents/explanation
pip install -r requirements.txt
```

## Running the System

### Option 1: Run All Services Manually

Open separate terminals:

**Terminal 1 - Risk Assessment Agent:**
```bash
cd Agents/decision-orchestration-agent/subagents/risk-assessment
python agent.py
```

**Terminal 2 - Feasibility Agent:**
```bash
cd Agents/decision-orchestration-agent/subagents/feasibility
python agent.py
```

**Terminal 3 - Cost Impact Agent:**
```bash
cd Agents/decision-orchestration-agent/subagents/cost-impact
python agent.py
```

**Terminal 4 - Explanation Agent:**
```bash
cd Agents/decision-orchestration-agent/subagents/explanation
python agent.py
```

**Terminal 5 - Decision Orchestrator Agent:**
```bash
cd Agents/decision-orchestration-agent
python agent.py
```

**Terminal 6 - Inventory Monitoring Agent:**
```bash
cd Agents/inventory-agent
python agent.py
```

**Terminal 7 - Java Backend:**
```bash
cd SmartCartAIBackend
./mvnw spring-boot:run
```

### Option 2: Use a Process Manager

Create a `start_all.sh` script:

```bash
#!/bin/bash

# Start subagents in background
cd Agents/decision-orchestration-agent/subagents/risk-assessment && python agent.py &
cd Agents/decision-orchestration-agent/subagents/feasibility && python agent.py &
cd Agents/decision-orchestration-agent/subagents/cost-impact && python agent.py &
cd Agents/decision-orchestration-agent/subagents/explanation && python agent.py &

# Start orchestrator
cd Agents/decision-orchestration-agent && python agent.py &

# Start inventory monitoring
cd Agents/inventory-agent && python agent.py &

# Start backend
cd SmartCartAIBackend && ./mvnw spring-boot:run &

echo "All services started. Use 'pkill -f agent.py' to stop."
```

## Verification

### Check Agent Health

```bash
# Inventory Monitoring Agent
curl http://localhost:9005/health

# Decision Orchestrator Agent
curl http://localhost:9000/health

# Subagents
curl http://localhost:9004/health  # Risk Assessment
curl http://localhost:9001/health  # Feasibility
curl http://localhost:9002/health  # Cost Impact
curl http://localhost:9003/health  # Explanation
```

### Test Orchestration

```bash
curl -X POST http://localhost:8080/api/agents/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "inventory_id": "INV-001",
    "event_type": "low_stock",
    "remaining_stock": 5,
    "suggested_action": "reorder",
    "stock_signal": "low",
    "item_data": {
      "item_name": "Test Item",
      "min_stock": 10,
      "max_capacity": 1000
    }
  }'
```

### Check Monitoring Status

```bash
curl http://localhost:8080/api/agents/inventory/monitor/status
```

## Frontend Integration

The frontend is already configured to use the agent endpoints via the Java backend. The React Native app will:

1. Display inventory items from the backend
2. Allow users to trigger recommendations via the Dashboard
3. Show detailed recommendations including risk assessment, feasibility, cost impact, and explanations

## Troubleshooting

### Agents Not Starting

- Check PostgreSQL is running: `pg_isready`
- Verify database credentials in environment variables
- Check ports are not already in use: `lsof -i :9000`

### Mistral LLM Not Working

- Verify `MISTRAL_API_KEY` is set correctly
- Check API key is valid and has credits
- System will fall back to rule-based logic if LLM unavailable

### Subagents Not Responding

- Ensure all subagents are running before starting orchestrator
- Check subagent URLs match in orchestrator configuration
- Review subagent logs for errors

### Database Connection Issues

- Verify PostgreSQL is accessible: `psql -h localhost -U meghanarendrasimha -d smartcart_ai`
- Check firewall settings
- Ensure database schema is created
- Verify database name is `smartcart_ai` (with underscore, not hyphen)

## Architecture Notes

- **MCP Layer**: All agents expose tools via Model Context Protocol (fastMCP) for standardized communication
- **RAG**: Decision Orchestrator uses PostgreSQL for retrieval-augmented generation
- **Forecasting**: Inventory Monitoring Agent uses exponential smoothing and moving averages
- **Continuous Monitoring**: Runs in background thread, checking inventory every 30 seconds (configurable)

## Next Steps

- Configure Mistral API key for LLM features
- Adjust monitoring interval based on your needs
- Customize category regulations in Feasibility agent
- Set cost limits in Cost Impact agent
- Add more sophisticated forecasting models if needed
