# Repository Folder Structure (maps to architecture diagram)

- /SmartCartAIBackend/services/
  - inventory-service/  (Inventory API placeholder)
  - sales-service/      (Sales API placeholder)
  - demand-service/     (Demand API placeholder)

- /agents/
  - decision-orchestration-agent/
    - agent.py
    - subagents/
      - feasibility/
      - cost-impact/
      - explanation/
      - risk-assessment/
  - inventory-agent/
    - agent.py
    - README.md
    - tests/

- /database/
  - schema.sql

- /infra/
  - docker-compose.yml

- /docs/
  - architecture.md

- /Dataset/
  - SmartCartAI_UseCases.drawio  (architecture diagram source)

This tree is intentionally minimal to make the architecture clear on GitHub. Fill in implementation files and tests per service/sub-agent when ready.