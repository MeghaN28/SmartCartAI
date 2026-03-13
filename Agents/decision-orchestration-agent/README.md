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

5. **Food Bank** (Port 9007)
   - Returns nearest food banks for donation suggestions
   - Used when recommending DONATE

### Why are subagents "down" or connection refused?

Subagents are **separate processes**. They do not start with the Decision Orchestrator. If you only run `python agent.py` in the orchestrator folder, the orchestrator runs on port 9000 but **no subagent is running** on 9001, 9002, 9003, 9004, or 9007, so you get "Connection refused" for those ports.

- **To have full behavior** (risk, feasibility, cost, explanation, food bank): start each subagent in its own terminal (see **Usage** below).
- **If you don't start them**: the orchestrator still completes and uses fallbacks (e.g. rule-based DONATE/BUNDLE/DISCOUNT). You may see "Feasibility check failed", "Explanation generation failed", etc., but recommendations are still produced.

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
MISTRAL_API_KEY=<your-mistral-api-key>
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
FOOD_BANK_AGENT_URL=http://localhost:9007/nearest

PORT=9000
```

## Usage

Start the orchestrator:

```bash
python agent.py
```

Start subagents (each in its own terminal; from `Agents/decision-orchestration-agent`):

```bash
# Terminal 2 – Risk Assessment (9004)
cd subagents/risk-assessment && python agent.py

# Terminal 3 – Feasibility (9001)
cd subagents/feasibility && python agent.py

# Terminal 4 – Cost Impact (9002)
cd subagents/cost-impact && python agent.py

# Terminal 5 – Explanation (9003)
cd subagents/explanation && python agent.py

# Terminal 6 – Food Bank (9007)
cd subagents/food-bank && python agent.py
```

If you don't start these, the orchestrator still runs and returns recommendations using rule-based logic and fallbacks; you'll see "Connection refused" or "failed" in logs for the subagents that aren't running.

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
