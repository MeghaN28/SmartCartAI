# How to Run the Agents (MCP-first)

Chat Agent and Decision Orchestrator run as **MCP HTTP servers**. Subagents (risk / feasibility+cost / explanation / food bank) remain **Flask REST services** because the orchestrator still calls them via HTTP POST.

Start services (MCP + required Flask subagents):

```bash
./start_agents.sh
```

MCP endpoints are available at:
- Orchestrator: `http://localhost:9100/mcp`
- Chat: `http://localhost:9106/mcp`

Flask subagent endpoints (called by orchestrator) are available at:
- Risk: `http://localhost:9004/risk`
- Feasibility+Cost: `http://localhost:9002/feasibility-and-cost`
- Explanation: `http://localhost:9003/explain`
- Food bank: `http://localhost:9007/nearest`

Example MCP client call:

```bash
python3 evaluation/mcp_demo.py
```

## Manual run (optional)

If you want to run services individually:

```bash
cd Agents/decision-orchestration-agent
MCP_PORT=9100 python agent.py
```

```bash
cd Agents/decision-orchestration-agent/subagents/chat
MCP_PORT=9106 python agent.py
```

## Optional: Inventory Agent (port 9005)

Needed if you want the Chat Agent to resolve queries via the Inventory Agent (e.g. "stock for apple" when the inventory service is up).

```bash
cd Agents/inventory-agent
python agent.py
```

## Dashboard Agent (port 9008)

Needed for dashboard search popup insights (sales/demand/stock charts and recommendation).

```bash
cd Agents/dashboard-agent
python agent.py
```

## Subagents (required for full recommendation pipeline)

Run these in separate terminals from `Agents/decision-orchestration-agent`:

```bash
cd Agents/decision-orchestration-agent/subagents/risk-assessment && python agent.py
cd Agents/decision-orchestration-agent/subagents/feasibility && python agent.py
cd Agents/decision-orchestration-agent/subagents/cost-impact && python agent.py
cd Agents/decision-orchestration-agent/subagents/explanation && python agent.py
cd Agents/decision-orchestration-agent/subagents/food-bank && python agent.py
```

## Quick test

1. Start **Decision Orchestrator** (terminal 1).
2. Start **Chat Agent** (terminal 2).
3. Test health:
   - `curl http://localhost:9006/health`
   - `curl http://localhost:9000/health`
4. Test chat (or use your app):
   - `curl -X POST http://localhost:9006/chat -H "Content-Type: application/json" -d '{"query":"stock for apple"}'`

## Backend configuration

The Java backend expects:

- `CHAT_AGENT_URL=http://localhost:9006` (default)
- `DECISION_ORCHESTRATOR_URL=http://localhost:9000` (default)
- `INVENTORY_AGENT_URL=http://localhost:9005` (default)
- `DASHBOARD_AGENT_URL=http://localhost:9008` (default)

If the app still shows old behavior, ensure:

1. You restarted the **Chat Agent** and **Decision Orchestrator** after pulling code changes.
2. No other process is using ports 9000 or 9006.
3. The backend (Spring Boot) is pointing at `localhost:9006` for chat.
