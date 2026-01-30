# Inventory Agent

Monitors inventory-related events (levels, holds, expiries) and notifies the
Decision Orchestration Agent to request a decision (reorder, hold, transfer).

Usage
-----
- Start the agent: `python agent.py` (defaults to port `9005`).
- Configure decision agent URL with `DECISION_AGENT_URL` env var (default: `http://localhost:9000/orchestrate`).

Behavior
--------
- POST JSON to `/inventory` to simulate an inventory event. The agent forwards
  the event to the configured Decision Orchestration Agent and returns its
  response as JSON.
