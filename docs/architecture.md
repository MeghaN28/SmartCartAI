# Architecture Overview 📋

This document maps the repository structure to the architecture diagram (see `Dataset/SmartCartAI_UseCases.drawio`).

## Mappings 🔧
- `SmartCartAIBackend/services/` — Java REST APIs (Inventory, Sales, Demand) that read/write to `database/` tables.
- `Agents/` — Agent code:
  - `decision-orchestration-agent/` — Orchestrates decisions by calling subagents (feasibility, cost-impact, explanation, risk-assessment).
  - `inventory-agent/` — Monitors inventory, reports events to the Decision Orchestration Agent, and receives directives (reorder/hold/transfer). Integrates with `SmartCartAIBackend/services/inventory-service`.
- `database/` — SQL schema and DB helpers.
- `docs/` — Architecture docs and diagrams.

## Next steps ✅
1. Implement service backends (Spring Boot / Node / Go) and open ports.
2. Add tests, CI pipeline, and container builds.

Diagram source: `Dataset/SmartCartAI_UseCases.drawio` (original architecture diagram).