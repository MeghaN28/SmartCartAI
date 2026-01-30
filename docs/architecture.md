# Architecture Overview 📋

This document maps the repository structure to the architecture diagram (see `Dataset/SmartCartAI_UseCases.drawio`).

## Mappings 🔧
- `SmartCartAIBackend/services/` — Java REST APIs (Inventory, Sales, Demand) that read/write to `database/` tables.
- `agents/` — Agent code (Decision-Orchestration Agent + Sub-Agents: Feasibility, CostImpact, Explanation, RiskAssessment).
- `database/` — SQL schema and DB helpers.
- `docs/` — Architecture docs and diagrams.

## Next steps ✅
1. Implement service backends (Spring Boot / Node / Go) and open ports.
2. Add tests, CI pipeline, and container builds.

Diagram source: `Dataset/SmartCartAI_UseCases.drawio` (original architecture diagram).