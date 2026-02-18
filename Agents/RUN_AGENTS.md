# How to Run the Agents (Flask)

All agents **already run on Flask**. Restart them after code changes so the app uses the latest logic.

## 1. Decision Orchestrator (port 9000)

Required for chat suggestions (waste rules, discount/bundle/donate).

```bash
cd Agents/decision-orchestration-agent
python agent.py
```

You should see the server start on port 9000. Leave this terminal open.

## 2. Chat Agent (port 9006)

This is what the mobile app and backend call for "chat". With `debug=True` and `use_reloader=True`, **edits to the Chat Agent code will reload automatically** (no need to restart unless you change the Decision Orchestrator).

```bash
cd Agents/decision-orchestration-agent/subagents/chat
python agent.py
```

You should see:
- `Starting Chat Agent Flask server on port 9006`
- `Health check: http://localhost:9006/health`
- `Chat endpoint: http://localhost:9006/chat`

Leave this terminal open.

## 3. Optional: Inventory Agent (port 9005)

Needed if you want the Chat Agent to resolve queries via the Inventory Agent (e.g. "stock for apple" when the inventory service is up).

```bash
cd Agents/inventory-agent
python agent.py
```

## 4. Optional: Subagents (for full recommendation pipeline)

For full risk/feasibility/cost/explanation, run these in separate terminals from `Agents/decision-orchestration-agent`:

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

If the app still shows old behavior, ensure:

1. You restarted the **Chat Agent** and **Decision Orchestrator** after pulling code changes.
2. No other process is using ports 9000 or 9006.
3. The backend (Spring Boot) is pointing at `localhost:9006` for chat.
