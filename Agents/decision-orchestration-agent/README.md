# Decision Orchestrator Agent

Coordinates multiple sub-agents to produce prescriptive inventory interventions. Uses LangChain/LangGraph for multi-agent reasoning and retrieval workflows. Integrates Mistral LLM for contextual reasoning and prescriptive recommendations. Implements RAG (Retrieval-Augmented Generation) with PostgreSQL for evidence-based decisions and explanations.

## Features

- **Multi-Agent Coordination**: Orchestrates Risk Assessment, Feasibility, Cost Impact, and Explanation subagents
- **LangGraph Integration**: Uses LangGraph for parallel subagent execution and sequential synthesis
- **Mistral LLM Integration**: Leverages Mistral for contextual reasoning and recommendation synthesis
- **RAG with PostgreSQL**: Retrieves historical inventory, consumption, and sales data for evidence-based decisions
- **MCP Compliance**: Exposes tools via Model Context Protocol (fastMCP)

## Architecture

### Subagents

1. **Risk Assessment** (Port 9004)
   - Analyzes risk status of flagged items
   - Identifies risk factors (low stock, high consumption, critical categories)
   - Calculates risk scores and levels

2. **Feasibility** (Port 9001)
   - Checks operational limits
   - Validates category-based regulations
   - Ensures actions comply with constraints

3. **Cost & Operational Impact** (Port 9002)
   - Estimates cost of interventions
   - Checks against budget limits
   - Evaluates margin requirements

4. **Explanation Generation** (Port 9003)
   - Produces human-readable justifications
   - Uses Mistral LLM for natural language explanations
   - Falls back to template-based explanations if LLM unavailable

### Graph Flow

1. **Parallel Execution**: Risk Assessment, Feasibility, and Cost Impact run in parallel
2. **Explanation Generation**: Uses results from all subagents to generate explanation
3. **Synthesis**: LLM synthesizes final recommendation with RAG context

## Setup

```bash
cd Agents/decision-orchestration-agent
pip install -r requirements.txt
```

## Configuration

Set environment variables:

**Option 1: Use .env file (Recommended)**
A `.env` file has been created in `Agents/decision-orchestration-agent/` with the Mistral API key and database credentials configured.

**Option 2: Set environment variables manually**
```bash
# Mistral LLM
MISTRAL_API_KEY=SWqT1KZpsaFqYIcd6AqFlvQrjK8xFWeC
MISTRAL_MODEL=mistral-medium

# Database (for RAG)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=smartcart_ai
DB_USER=meghanarendrasimha
DB_PASSWORD=Welcome@123

# Subagent URLs (optional, defaults shown)
RISK_AGENT_URL=http://localhost:9004/risk
FEASIBILITY_AGENT_URL=http://localhost:9001/feasibility
COST_IMPACT_AGENT_URL=http://localhost:9002/cost-impact
EXPLANATION_AGENT_URL=http://localhost:9003/explain

PORT=9000
```

## Usage

Start the orchestrator:

```bash
python agent.py
```

Start subagents (in separate terminals):

```bash
# Risk Assessment
cd subagents/risk-assessment
python agent.py

# Feasibility
cd subagents/feasibility
python agent.py

# Cost Impact
cd subagents/cost-impact
python agent.py

# Explanation
cd subagents/explanation
python agent.py
```

## Endpoints

- `POST /orchestrate` – Main orchestration endpoint. Accepts inventory event and returns prescriptive recommendation.
- `GET /health` – Health check (includes Mistral configuration status)

## Example Request

```json
{
  "inventory_id": "INV-001",
  "event_type": "low_stock",
  "remaining_stock": 5,
  "suggested_action": "reorder",
  "stock_signal": "low",
  "consumption_signal": "normal",
  "forecasted_demand": 2.5,
  "item_data": {
    "item_name": "Item Name",
    "category": "Category",
    "min_stock": 10,
    "max_capacity": 1000
  },
  "consumption_history": [...],
  "context": {}
}
```

## Example Response

```json
{
  "recommendation": {
    "action": "reorder",
    "priority": "High",
    "reasoning": "Stock levels are critically low...",
    "expected_outcome": "Stock levels will be restored...",
    "timestamp": "2026-02-09T12:00:00",
    "llm_enhanced": true
  },
  "risk_assessment": {
    "risk_level": "high",
    "risk_score": 45,
    "risk_factors": [...]
  },
  "feasibility_check": {
    "is_feasible": true,
    "constraints": []
  },
  "cost_impact": {
    "estimated_cost": 500.00,
    "within_budget": true
  },
  "explanation": {
    "explanation": "Based on the analysis...",
    "llm_generated": true
  }
}
```

## MCP Tools

- `orchestrate_intervention(inventory_id, event_type)` – Orchestrate a prescriptive intervention for an inventory item

## RAG Implementation

The orchestrator retrieves:
- **Inventory Details**: Item properties, thresholds, capacity
- **Consumption History**: Last 20 consumption records
- **Sales History**: Last 10 sales transactions

This context is used to:
- Ground LLM recommendations in operational evidence
- Provide historical context for risk assessment
- Calculate accurate cost estimates

## LLM Fallback

If Mistral LLM is not configured or unavailable:
- Subagents continue to function with rule-based logic
- Explanation generation uses template-based explanations
- Recommendations are synthesized using rule-based priority logic
