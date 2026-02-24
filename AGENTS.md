# SmartCartAI Agents — Do's and Don'ts

Guidelines for working with the Python AI agents (Decision Orchestrator, Chat, Inventory, and subagents).

---

## Do's

### Running & startup
- **Do** start the Decision Orchestrator (port 9000) and Chat Agent (port 9006) for chat and suggestions to work.
- **Do** run subagents (risk, feasibility-and-cost, explanation, food-bank) if you want the full recommendation pipeline; the orchestrator can fall back if they are down.
- **Do** use `./start_agents.sh` or follow `Agents/RUN_AGENTS.md` for the correct startup order.
- **Do** restart agents after code changes so the app uses the latest logic (Chat Agent can auto-reload when `use_reloader=True`).
- **Do** check health before testing: `curl http://localhost:9006/health` and `curl http://localhost:9000/health`.

### Configuration & environment
- **Do** set `MISTRAL_API_KEY` (e.g. in `.env` under `Agents/decision-orchestration-agent/` or project root) for LLM features.
- **Do** keep DB credentials in `.env` per agent (or subagent) and avoid committing real passwords; use `.env.example` for templates.
- **Do** ensure the backend points to the right agent URLs: `CHAT_AGENT_URL`, `DECISION_ORCHESTRATOR_URL`, `INVENTORY_AGENT_URL` (defaults: 9006, 9000, 9005).

### Architecture & flow
- **Do** treat the Chat Agent as the user-facing entry point; it calls Inventory Agent for DB-backed queries, then the Decision Orchestrator per item.
- **Do** let the Inventory Agent be the single place that interprets user intent and queries the database (low stock, expired, waste, reorder, etc.).
- **Do** keep the pipeline order: Risk Assessment → Feasibility & Cost (merged) → Food Bank (when discard/donate) → Explanation.

### Development & code
- **Do** install dependencies per agent: `pip install -r requirements.txt` in each agent/subagent directory.
- **Do** use the shared `Agents/common/` utilities (e.g. forecasting) where applicable.
- **Do** log errors and timeouts so you can debug orchestrator ↔ subagent communication.

### Database & data
- **Do** apply `database/schema.sql` and any migrations before running agents.
- **Do** use the database name `smartcart_ai` (underscore, not hyphen).

---

## Don'ts

### Running & ports
- **Don't** run multiple instances of the same agent on the same port (e.g. two Chat Agents on 9006).
- **Don't** assume the full pipeline works if only the orchestrator and chat are running; subagents are optional but needed for full risk/feasibility/cost/explanation.
- **Don't** start the backend (Spring Boot) before agents if the app depends on chat/orchestrate; start agents first, then backend, then frontend (see `START_SERVICES.md`).

### Configuration & secrets
- **Don't** commit `.env` files with real API keys or database passwords to the repo.
- **Don't** hardcode `MISTRAL_API_KEY` or DB credentials in source code.
- **Don't** change subagent ports without updating the orchestrator’s configuration (URLs for risk, feasibility-and-cost, explanation, food-bank).

### Architecture & flow
- **Don't** bypass the Chat Agent for user-facing chat; the backend proxies to the Chat Agent for a reason.
- **Don't** put direct DB query logic for “user intent” in the orchestrator; that belongs in the Inventory Agent.
- **Don't** reorder the subagent pipeline (Risk → Feasibility & Cost → Food Bank → Explanation) without updating the orchestrator and docs.

### Development & code
- **Don't** skip installing dependencies in a subagent directory when adding or changing that subagent.
- **Don't** remove or change the `/health` endpoints; the backend and scripts may rely on them.
- **Don't** block the Flask app with long synchronous calls; use timeouts and fallbacks when calling subagents or external APIs.

### Database & data
- **Don't** use a database name with a hyphen (e.g. `smartcart-ai`); use `smartcart_ai`.
- **Don't** assume schema is up to date; run migrations (e.g. `add_facility_food_banks_donation.sql`) when required by agents.

---

## Quick reference

| Agent                    | Port | Required for chat/suggestions |
|--------------------------|------|------------------------------|
| Decision Orchestrator    | 9000 | Yes                          |
| Chat Agent               | 9006 | Yes                          |
| Inventory Agent          | 9005 | Optional (needed for DB-backed chat) |
| Risk Assessment          | 9004 | Optional (full pipeline)     |
| Feasibility & Cost Impact| 9002 | Optional (full pipeline)     |
| Explanation              | 9003 | Optional (full pipeline)     |
| Food Bank                | 9007 | Optional (donate/discard)     |

For setup details, see `AGENTS_SETUP.md` and `Agents/RUN_AGENTS.md`.
