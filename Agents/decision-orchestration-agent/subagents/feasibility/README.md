# Feasibility Subagent (deprecated – merged)

**This subagent has been merged into the Cost Impact agent.**

- **Use instead:** Feasibility and cost impact are now handled by the **Feasibility & Cost Impact** agent (same process as Cost Impact) on **port 9002**.
- **Combined endpoint:** `POST http://localhost:9002/feasibility-and-cost`
- **Payload:** Same as before (`inventory_id`, `suggested_action`, `item_data`, `remaining_stock`, `context`; optionally `forecasted_demand`).
- **Response:** `{ "feasibility_check": { ... }, "cost_impact": { ... } }`

The orchestrator calls this single endpoint; you do not need to start a separate Feasibility agent on port 9001.

See: `subagents/cost-impact/` for the merged implementation.
