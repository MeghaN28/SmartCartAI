# SmartCartAI

SmartCartAI is an intelligent inventory management system that optimizes retail operations through AI-powered decision-making. It combines a **React Native (Expo)** mobile app, a **Spring Boot** Java backend, **Python AI agents** (LangChain/LangGraph, Mistral), and **PostgreSQL** for inventory, sales, consumption, and demand data.

## Features

- **AI-Powered Inventory Management**: Multi-agent system for stock levels, expiry tracking, waste reduction, and prescriptive recommendations (discount, bundle, donate, reorder)
- **Conversational Chat**: Natural-language queries and AI suggestions via a dedicated Chat Agent (waste rules, stock lookups, recommendations)
- **Real-time Dashboard**: Monitor inventory status, at-risk items, agent actions, and impact metrics
- **Mobile App**: Cross-platform React Native (Expo) app with dashboard, chatbot, inventory views, suggestion log, and upload/forecast screens
- **Decision Orchestration**: Risk assessment, feasibility, cost-impact, explanation, and food-bank subagents coordinated by a central orchestrator with RAG over PostgreSQL
- **Dashboard Agent Insights**: Item-level popup recommendations from dashboard search with stock/sales/demand chart data
- **Data & Scripts**: Sample CSV datasets, Python data generation (`Dataset/`), and SQL scripts for demand/pricing tuning (`database/scripts/`)

## Screenshots

<details>
<summary>Mobile app UI (tap to expand)</summary>

<table>
  <tr>
    <td><img src="Screenshot%202026-02-24%20at%2010.10.49%E2%80%AFPM.png" alt="Screenshot 1" width="260" /></td>
    <td><img src="Screenshot%202026-02-24%20at%2010.11.00%E2%80%AFPM.png" alt="Screenshot 2" width="260" /></td>
  </tr>
  <tr>
    <td><img src="Screenshot%202026-02-24%20at%2010.11.11%E2%80%AFPM.png" alt="Screenshot 3" width="260" /></td>
    <td><img src="Screenshot%202026-02-24%20at%2010.11.19%E2%80%AFPM.png" alt="Screenshot 4" width="260" /></td>
  </tr>
  <tr>
    <td><img src="Screenshot%202026-02-24%20at%2010.11.26%E2%80%AFPM.png" alt="Screenshot 5" width="260" /></td>
    <td><img src="Screenshot%202026-02-24%20at%2010.11.33%E2%80%AFPM.png" alt="Screenshot 6" width="260" /></td>
  </tr>
  <tr>
    <td><img src="Screenshot%202026-02-24%20at%2010.11.40%E2%80%AFPM.png" alt="Screenshot 7" width="260" /></td>
    <td><img src="Screenshot%202026-02-24%20at%2010.11.58%E2%80%AFPM.png" alt="Screenshot 8" width="260" /></td>
  </tr>
  <tr>
    <td><img src="Screenshot%202026-02-24%20at%2010.12.05%E2%80%AFPM.png" alt="Screenshot 9" width="260" /></td>
    <td><img src="Screenshot%202026-02-24%20at%2010.12.15%E2%80%AFPM.png" alt="Screenshot 10" width="260" /></td>
  </tr>
  <tr>
    <td><img src="Screenshot%202026-02-24%20at%2010.12.34%E2%80%AFPM.png" alt="Screenshot 11" width="260" /></td>
    <td><img src="Screenshot%202026-02-24%20at%2010.12.42%E2%80%AFPM.png" alt="Screenshot 12" width="260" /></td>
  </tr>
  <tr>
    <td><img src="Screenshot%202026-02-24%20at%2010.12.51%E2%80%AFPM.png" alt="Screenshot 13" width="260" /></td>
    <td><img src="Screenshot%202026-02-24%20at%2010.13.00%E2%80%AFPM.png" alt="Screenshot 14" width="260" /></td>
  </tr>
  <tr>
    <td><img src="Screenshot%202026-02-24%20at%2010.43.24%E2%80%AFPM.png" alt="Screenshot 15" width="260" /></td>
    <td><img src="Screenshot%202026-02-24%20at%2010.43.32%E2%80%AFPM.png" alt="Screenshot 16" width="260" /></td>
  </tr>
  <tr>
    <td><img src="Screenshot%202026-02-24%20at%2010.43.38%E2%80%AFPM.png" alt="Screenshot 17" width="260" /></td>
    <td></td>
  </tr>
</table>

</details>

## Project Structure

```
SmartCartAI/
├── README.md
├── start_all.sh              # Start all services (optional background mode)
├── start_agents.sh           # Start all Python agents
├── stop_all.sh               # Stop all services
├── START_SERVICES.md         # Step-by-step service startup guide
│
├── Agents/                   # Python AI agents (Flask)
│   ├── RUN_AGENTS.md         # How to run each agent
│   ├── decision-orchestration-agent/   # Orchestrator (port 9000)
│   │   ├── agent.py
│   │   ├── subagents/
│   │   │   ├── chat/         # Chat Agent (port 9006)
│   │   │   ├── risk-assessment/   # 9004
│   │   │   ├── cost-impact/      # 9002 (Feasibility + Cost Impact, merged)
│   │   │   ├── feasibility/      # 9001 (legacy/optional)
│   │   │   ├── explanation/      # 9003
│   │   │   └── food-bank/        # 9007
│   │   └── README.md
│   ├── inventory-agent/      # Inventory monitoring & forecasting (port 9005)
│   ├── dashboard-agent/      # Dashboard item insights (port 9008)
│   └── common/               # Shared utilities (e.g. forecasting)
│
├── SmartCartAIBackend/       # Spring Boot REST API (port 8080)
│   ├── pom.xml
│   ├── mvnw
│   └── src/main/java/        # Controllers, DTOs, services
│
├── SmartCartAIFrontEnd/
│   └── mobile/               # React Native (Expo) app
│       ├── package.json
│       ├── App.js
│       └── src/
│           ├── screens/      # Dashboard, Chatbot, Home, SuggestionLog, etc.
│           ├── components/
│           ├── navigation/
│           └── config.js      # API base URL
│
├── database/
│   ├── schema.sql            # PostgreSQL schema (inventory, sales, consumption, demand)
│   └── scripts/              # Demand and pricing SQL scripts (README inside)
│
├── Dataset/                  # Data generation and sample CSVs
│   ├── createdataset.py
│   ├── inventory_master_50_unique.csv
│   ├── sales_50.csv
│   └── consumption_50.csv
│
└── docs/                     # Architecture and design docs
```

## Architecture

- **UI — `SmartCartAIFrontEnd/mobile/`**  
  React Native (Expo) app: dashboard, inventory, chatbot, suggestion log, upload/forecast.

- **Agents — `Agents/`**  
  - **Chat Agent** (9006): User-facing entry point for natural-language chat. For DB-backed questions, it calls the Inventory Agent, then calls the Decision Orchestrator per flagged item and returns the final response (and can persist suggestions).  
  - **Inventory Agent** (9005): Interprets user intent and queries PostgreSQL (low stock, expired, near-expiring, waste, reorder, etc.). Returns “signals” (items needing attention) and can trigger orchestration.  
  - **Dashboard Agent** (9008): Provides item-level insights for the dashboard search popup (stock/sales/demand charts + recommendations).  
  - **Decision Orchestration Agent** (9000): Runs the decision pipeline per item and synthesizes the final recommendation (RAG over PostgreSQL + optional LLM).  
  - **Subagents (optional, full pipeline)**: Risk (9004) → Feasibility + Cost Impact (9002, merged) → Food Bank (9007, donate/discard) → Explanation (9003).

- **Backend — `SmartCartAIBackend/`**  
  Single Spring Boot application. REST APIs for inventory/sales/consumption/demand/suggestions and an agent proxy endpoint that forwards chat to the Chat Agent. Swagger UI at `http://localhost:8080/swagger-ui.html`.

- **Database — `database/`**  
  PostgreSQL schema and migration/scripts. Tables: inventory, sales, consumption, demand (and related). Scripts in `database/scripts/` for demand and pricing (see `database/scripts/README.md`).

- **Dataset — `Dataset/`**  
  Python script and CSV sample data for prototyping and loading into the DB.

## Documentation

- `START_SERVICES.md`: step-by-step startup order (agents → backend → frontend)
- `docs/architecture.md`: end-to-end flow (Chat → Inventory → Decision Orchestrator → subagents)
- `AGENTS_SETUP.md`: agent environment variables and setup notes
- `Agents/RUN_AGENTS.md`: run each agent/subagent manually

## Prerequisites

- **Node.js** (for frontend)
- **Java 17+** and Maven (backend uses `./mvnw`)
- **Python 3.8+** (for agents and data generation)
- **PostgreSQL** (database `smartcart_ai`; apply `database/schema.sql`)
- **Expo CLI** / Expo Go (for React Native development)
- **Mistral API key** (for LLM features; optional for some fallbacks)

## Installation & Running

### 1. Database

Create the database and apply the schema:

```bash
createdb smartcart_ai
psql -h localhost -U <user> -d smartcart_ai -f database/schema.sql
```

Optionally load sample data from `Dataset/` (see `Dataset/Copydata.txt` or use `createdataset.py` and your import process).

### 2. Python Agents (recommended first)

**Quick start (all agents):**

```bash
./start_agents.sh
```

**Minimum for chat/suggestions:** Decision Orchestrator (9000) + Chat Agent (9006).  
**Optional:** Inventory Agent (9005), Dashboard Agent (9008), and the subagents (Risk/Feasibility+Cost/Explanation/Food Bank).

Health checks:

```bash
curl http://localhost:9006/health
curl http://localhost:9000/health
curl http://localhost:9008/health
```

See `AGENTS_SETUP.md` and `Agents/RUN_AGENTS.md` for environment variables (use `.env` files; don’t commit real API keys/passwords).

### 3. Backend (Spring Boot)

```bash
cd SmartCartAIBackend
./mvnw spring-boot:run
```

API: `http://localhost:8080`. Configure DB (and agent URLs like `CHAT_AGENT_URL`) in `src/main/resources/application.properties`.

### 4. Frontend (React Native)

```bash
cd SmartCartAIFrontEnd/mobile
npm install
npm start
```

Use Expo Go to open the app (scan QR or press `i`/`a` for simulator).

### Full stack (three terminals)

See **START_SERVICES.md** for the recommended order: (1) Python agents via `./start_agents.sh`, (2) Java backend via `./mvnw spring-boot:run`, (3) Frontend via `cd SmartCartAIFrontEnd/mobile && npm start`. Use `./start_all.sh --background` to start all in background; `./stop_all.sh` to stop.

## Usage

- **Mobile**: Dashboard metrics, inventory list, AI chatbot, suggestion log, item forecast, upload purchase.
- **Backend**: REST APIs for inventory/sales/consumption/demand; chat endpoint forwards to Chat Agent.
- **Agents**: Orchestrator `/orchestrate` for prescriptive recommendations; Chat Agent `/chat` for natural-language queries and suggestions.

## Data & Scripts

- **Dataset**: `inventory_master_50_unique.csv`, `sales_50.csv`, `consumption_50.csv`; generate with `python createdataset.py` in `Dataset/`.
- **Demand/pricing**: Use scripts in `database/scripts/` (e.g. `set_high_demand.sql`, `set_all_high_demand.sql`) to tune demand used by agents; see `database/scripts/README.md`.

## Technologies

- **Frontend**: React Native, Expo, JavaScript
- **Backend**: Java 17, Spring Boot, Swagger
- **Agents**: Python 3, Flask, LangChain, LangGraph, Mistral AI, FastMCP, PostgreSQL (RAG)
- **Data**: Python, Pandas/NumPy (dataset generation); PostgreSQL

## Contributing

1. Fork the repository  
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)  
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)  
4. Push to the branch (`git push origin feature/AmazingFeature`)  
5. Open a Pull Request  
