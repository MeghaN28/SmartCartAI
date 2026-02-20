# SmartCartAI

SmartCartAI is an intelligent inventory management system that optimizes retail operations through AI-powered decision-making. It combines a **React Native (Expo)** mobile app, a **Spring Boot** Java backend, **Python AI agents** (LangChain/LangGraph, Mistral), and **PostgreSQL** for inventory, sales, consumption, and demand data.

## Features

- **AI-Powered Inventory Management**: Multi-agent system for stock levels, expiry tracking, waste reduction, and prescriptive recommendations (discount, bundle, donate, reorder)
- **Conversational Chat**: Natural-language queries and AI suggestions via a dedicated Chat Agent (waste rules, stock lookups, recommendations)
- **Real-time Dashboard**: Monitor inventory status, at-risk items, agent actions, and impact metrics
- **Mobile App**: Cross-platform React Native (Expo) app with dashboard, chatbot, inventory views, suggestion log, and upload/forecast screens
- **Decision Orchestration**: Risk assessment, feasibility, cost-impact, explanation, and food-bank subagents coordinated by a central orchestrator with RAG over PostgreSQL
- **Data & Scripts**: Sample CSV datasets, Python data generation (`Dataset/`), and SQL scripts for demand/pricing tuning (`database/scripts/`)

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
│   │   │   ├── feasibility/      # 9001
│   │   │   ├── cost-impact/      # 9002
│   │   │   ├── explanation/      # 9003
│   │   │   └── food-bank/        # 9007
│   │   └── README.md
│   ├── inventory-agent/      # Inventory monitoring & forecasting (port 9005)
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
  React Native (Expo) app: dashboard, inventory, chatbot, suggestion log, upload/forecast. Talks to the Java backend and Chat Agent for recommendations and explanations.

- **Agents — `Agents/`**  
  - **Decision Orchestration Agent** (9000): Coordinates subagents, uses LangGraph and Mistral for prescriptive interventions and RAG over PostgreSQL.  
  - **Chat Agent** (9006): Handles natural-language chat and waste/discount/bundle/donate suggestions; used by the mobile app and backend.  
  - **Inventory Agent** (9005): Monitors inventory, forecasting (e.g. ETS), flags items, and can call the orchestrator.  
  - **Subagents**: Risk (9004), Feasibility (9001), Cost Impact (9002), Explanation (9003), Food Bank (9007). Run separately for full pipeline; orchestrator has fallbacks if they are not running.

- **Backend — `SmartCartAIBackend/`**  
  Single Spring Boot application. REST APIs for inventory, sales, consumption, demand; proxies chat to the Chat Agent. Swagger UI at `http://localhost:8080/swagger-ui.html`.

- **Database — `database/`**  
  PostgreSQL schema and migration/scripts. Tables: inventory, sales, consumption, demand (and related). Scripts in `database/scripts/` for demand and pricing (see `database/scripts/README.md`).

- **Dataset — `Dataset/`**  
  Python script and CSV sample data for prototyping and loading into the DB.

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

### 2. Frontend

```bash
cd SmartCartAIFrontEnd/mobile
npm install
npm start
```

Use Expo Go to open the app (scan QR or press `i`/`a` for simulator).

### 3. Backend (Spring Boot)

```bash
cd SmartCartAIBackend
./mvnw spring-boot:run
```

API: `http://localhost:8080`. Configure DB (and optional agent URLs) in `src/main/resources/application.properties`.

### 4. Python Agents

**Quick start (all agents):**

```bash
./start_agents.sh
```

**Or run manually** (see `Agents/RUN_AGENTS.md` for details):

- **Required for chat/suggestions:** Decision Orchestrator (9000), Chat Agent (9006)
- **Optional:** Inventory Agent (9005); subagents Risk (9004), Feasibility (9001), Cost Impact (9002), Explanation (9003), Food Bank (9007)

Example (orchestrator + chat only):

```bash
cd Agents/decision-orchestration-agent && PORT=9000 python3 agent.py
cd Agents/decision-orchestration-agent/subagents/chat && PORT=9006 python3 agent.py
```

Set `MISTRAL_API_KEY` (and optionally DB credentials) via `.env` in `Agents/decision-orchestration-agent/` or the project root.

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
