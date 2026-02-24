# Feasibility & Cost Impact Subagent (merged)

This agent handles both **operational feasibility** and **cost/margin impact** in one service.

- **Feasibility (no regulations):** Valid action, storage capacity (reorder vs `max_capacity`), vendor presence.
- **Cost impact:** Estimated cost, within_budget vs `MAX_ORDER_COST`, margin %, discount vs cost checks.

## Endpoints

- `POST /feasibility-and-cost` – **Combined** (used by the orchestrator). Payload: `inventory_id`, `suggested_action`, `item_data`, `remaining_stock`, `context`, optional `forecasted_demand`. Response: `{ "feasibility_check": {...}, "cost_impact": {...} }`.
- `POST /cost-impact` – Cost only (backward compatible).
- `GET /health`

## Config

`DB_*`, `MAX_ORDER_COST`, `MIN_MARGIN_PERCENT`. Port: **9002** (default).
