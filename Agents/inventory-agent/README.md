# Inventory Monitoring Agent

Continuously monitors inventory data (stocks, consumption, thresholds, item properties) from PostgreSQL. Signals inventory items based on real-time stock signals and consumption signals. Uses statistical forecasting (exponential smoothing/moving averages) for demand prediction. Sends flagged items to Decision Orchestrator Agent for prescriptive processing.

## Features

- **Continuous PostgreSQL Monitoring**: Automatically monitors inventory levels and consumption patterns
- **Real-time Stock Signals**: Detects low stock, critical stock, and normal stock conditions
- **Consumption Signal Analysis**: Analyzes consumption patterns to identify anomalies
- **Statistical Forecasting**: Uses exponential smoothing and moving averages for demand prediction
- **MCP Compliance**: Exposes tools via Model Context Protocol (fastMCP)
- **LangGraph Integration**: Uses LangGraph for state-based workflow orchestration

## Graph Overview

- **State**: `InventoryAgentState` (TypedDict) holds inventory data, consumption history, forecasts, signals, and recommendations
- **Nodes**:
  - `receive_event` – Fetch and validate inventory data from PostgreSQL
  - `check_stock` – Compare stock levels against thresholds and generate stock signals
  - `suggest_action` – Analyze consumption patterns and forecast demand to suggest actions
  - `notify_decision_agent` – Send flagged items to Decision Orchestrator Agent
- **Edges**: Sequential flow through validation → stock check → action suggestion → decision agent notification

## Setup

```bash
cd Agents/inventory-agent
pip install -r requirements.txt
```

## Configuration

Set environment variables:

**Option 1: Use .env file (Recommended)**
A `.env` file has been created in `Agents/inventory-agent/` with the database credentials configured.

**Option 2: Set environment variables manually**
```bash
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=smartcart_ai
DB_USER=meghanarendrasimha
DB_PASSWORD=Welcome@123

# Decision Orchestrator
DECISION_AGENT_URL=http://localhost:9000/orchestrate

# Monitoring
MONITORING_INTERVAL=30  # seconds between monitoring cycles
PORT=9005
```

## Usage

Start the agent:

```bash
python agent.py
```

The agent will:
1. Start continuous monitoring in a background thread
2. Expose HTTP API on port 9005 (default)
3. Expose MCP tools for model integration

## Endpoints

- `POST /inventory` – Process an inventory event (JSON). Runs the LangGraph pipeline and returns results.
- `GET /health` – Health check
- `POST /monitor/start` – Start continuous monitoring (if not already running)
- `GET /monitor/status` – Check if monitoring is active

## Example Payload

```json
{
  "inventory_id": "INV-001",
  "event_type": "low_stock",
  "remaining_stock": 5,
  "quantity": 2,
  "context": { "min_stock": 10 }
}
```

## MCP Tools

- `check_inventory_status(inventory_id)` – Check current status of an inventory item
- `signal_inventory_item(inventory_id, event_type)` – Manually signal an item for processing

## Continuous Monitoring

The agent runs a background thread that:
1. Fetches all inventory items from PostgreSQL
2. Calculates current stock levels
3. Compares against thresholds
4. Flags items requiring attention
5. Sends flagged items to Decision Orchestrator Agent

Monitoring runs every 30 seconds by default (configurable via `MONITORING_INTERVAL`).

## Forecasting Methods

- **Exponential Smoothing**: Uses alpha parameter (default 0.3) for weighted averaging
- **Moving Average**: Uses configurable window (default 7 days)

Forecasts are used to:
- Predict future demand
- Identify consumption anomalies
- Refine reorder recommendations
