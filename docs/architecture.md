# Architecture Overview 📋

This document maps the repository structure to the architecture diagram (see `Dataset/SmartCartAI_UseCases.drawio`) and describes the **user-facing flow**.

## User-facing flow (Chat → Inventory → Decision → Explanation → User)

1. **Chat Agent** (open endpoint) — The user interacts here. Backend exposes `POST /api/agents/chat` and proxies to the Chat Agent (port 9006).

2. **Chat Agent calls Inventory Agent** — For each user query, the Chat Agent calls the Inventory Agent with the query. The Inventory Agent is the single place that interprets the user’s intent and **sees the database** (low stock, expired, near expiring, items going to waste, reorder, suggest, etc.).

3. **Inventory Agent** — Queries the DB based on the user query and returns **signals** (items that need attention). It can also send events to the Decision Agent (e.g. when running continuous monitoring or when processing a single event via `POST /inventory`).

4. **Decision Orchestration Agent** — Receives signals (per item) and **orchestrates sub-agents** in sequence: Risk Assessment → Feasibility → Cost Impact → **Food Bank** (when discard/donate) → **Explanation Agent** → synthesizes the final recommendation.

5. **Explanation Agent** — Produces the human-readable explanation and recommendation. That output is included in the Decision Orchestrator’s response.

6. **Back to Chat Agent** — The Chat Agent receives the recommendation (including explanation) for each item, returns the answer to the **user** and persists entries in the **Suggestion** tab (suggestions table).

```
User → Chat Agent → Inventory Agent (DB: low stock / expired / waste / …)
                          ↓
                     signals (items)
                          ↓
              Decision Orchestrator → Risk → Feasibility → Cost Impact → Food Bank* → Explanation
                          ↓
              Chat Agent ← recommendation + explanation
                          ↓
              User (reply) + Suggestion tab (saved)
```
*Food Bank runs when action is discard/donate or user asked about waste; returns nearest food banks for donation_info.

## Mappings 🔧

- **SmartCartAIBackend** — Java REST APIs (Inventory, Sales, Demand, Suggestion, Agents proxy). Reads/writes `database/` tables.
- **Agents/**
  - **decision-orchestration-agent/subagents/chat/** — **Chat Agent**: user-facing; calls Inventory Agent for query-based item lookup, then Decision Orchestrator per item; saves suggestions and returns answer.
  - **inventory-agent/** — Queries DB for user intent (low stock, expired, near expiring, waste, etc.); exposes `POST /query` for Chat and `POST /inventory` for events; can send signals to Decision Orchestrator.
  - **decision-orchestration-agent/agent.py** — **Decision Orchestrator**: runs subagents (risk-assessment, feasibility, cost-impact, food-bank, explanation) and returns recommendation + explanation.
  - **decision-orchestration-agent/subagents/** — risk-assessment, feasibility, cost-impact, food-bank (nearest food banks for donate/discard), explanation (explanation produces the final text for the user and suggestion tab).
- **database/** — SQL schema, suggestions table, migrations.
- **docs/** — Architecture docs and diagrams.

Diagram source: `Dataset/SmartCartAI_UseCases.drawio` (original architecture diagram).

---

## Mermaid diagrams

### High-level system (components)

```mermaid
flowchart TB
  subgraph GCP["GCP Cloud"]
    subgraph Agents["Agentic orchestration (LangGraph)"]
      Inv["Inventory Agent\n(Python/LangChain)"]
      Orch["Decision Orchestrator\n(Decision Agent)"]
      Risk["Risk Assessment\nSub-Agent"]
      Feas["Feasibility\nSub-Agent"]
      Cost["Cost/Impact\nSub-Agent"]
      FoodBank["Food Bank\nSub-Agent"]
      Expl["Explanation Gen\nSub-Agent"]
      Orch --> Risk --> Feas --> Cost --> FoodBank --> Expl
      Inv --> Orch
    end
    DB[("PostgreSQL\n(Inventory, Sales,\nDemand, Suggestions)")]
    API["Spring Boot\nJava APIs"]
    Mistral["Mistral LLM\n(Bedrock/Vertex)"]
    Orch -.-> Mistral
  end
  App["React Native App"]
  API <--> DB
  API --> Inv
  API <--> App
```

### User-facing flow (Chat → Orchestrator → Subagents)

```mermaid
flowchart LR
  User((User)) --> Chat[Chat Agent]
  Chat --> Inv[Inventory Agent]
  Inv --> DB[(PostgreSQL)]
  Inv --> |signals| Orch[Decision Orchestrator]
  Orch --> Risk[Risk Assessment]
  Risk --> Feas[Feasibility]
  Feas --> Cost[Cost Impact]
  Cost --> FB[Food Bank*]
  FB --> Expl[Explanation]
  Expl --> Chat
  Chat --> User
  Chat --> |save| Suggestions[(suggestions)]
```

*Food Bank runs when action is discard/donate or user asked about waste.*

### Decision pipeline (subagents only)

```mermaid
flowchart LR
  A[Risk Assessment] --> B[Feasibility]
  B --> C[Cost Impact]
  C --> D[Food Bank*]
  D --> E[Explanation]
```

### Full system (theme + layers, including Food Bank)

```mermaid
---
config:
  theme: base
  layout: dagre
  themeVariables:
    fontSize: 36px
    fontFamily: Inter, Segoe UI, Arial
    primaryColor: '#ffffff'
    primaryTextColor: '#0f172a'
    primaryBorderColor: '#4f46e5'
    lineColor: '#64748b'
    secondaryColor: '#eef2ff'
    tertiaryColor: '#f8fafc'
    clusterBkg: '#f8fafc'
    clusterBorder: '#6366f1'
---
flowchart LR

%% ========== 1. USER (leftmost) ==========
subgraph User["👤 User Layer"]
    U(("User"))
end

%% ========== 2. FRONTEND ==========
subgraph Frontend["🖥️ Frontend Layer"]
    ChatUI["Chat Interface"]
    SuggestionTab["Suggestion Log"]
    Dashboard["Dashboard"]
    App["SmartCartAI App"]
end

%% ========== 3. BACKEND ==========
subgraph Backend["⚙️ Backend Layer"]
    REST["REST API"]
    AgentCtrl["Agent Controller"]
    SuggestionCtrl["Suggestion API"]
    InventoryCtrl["Inventory API"]
end

%% ========== 4. AI AGENTS (core pipeline) ==========
subgraph Agents["🤖 AI Agent Layer"]
    Chat["Chat Agent\n(Entry Point)"]
    Inventory["Inventory Agent"]
    Orch["Decision Orchestrator"]
    subgraph SubAgents["Sub-Agents"]
        Risk["Risk Assessment"]
        Feas["Feasibility"]
        Cost["Cost Impact"]
        FoodBank["Food Bank\n(nearest for donate)"]
        Expl["Explanation"]
    end
end

%% ========== 5. CAPABILITIES ==========
subgraph Capabilities["🔧 AI Capabilities"]
    MCP["MCP\n(FastMCP)"]
    RAG["RAG\n(Retrieval)"]
    Forecast["Demand\nForecasting"]
end

%% ========== 6. LLM ==========
subgraph LLM["🧠 LLM Layer"]
    Mistral["Mistral LLM"]
end

%% ========== 7. DATA (rightmost) ==========
subgraph Data["🗄️ Data Layer"]
    DB[(PostgreSQL\nsmartcart_ai)]
end

%% ========== FLOW: User -> Frontend -> Backend -> Agents -> Capabilities/LLM/Data ==========

U --> ChatUI
U --> SuggestionTab
U --> Dashboard
ChatUI --> App
SuggestionTab --> App
Dashboard --> App
App --> REST
REST --> AgentCtrl
REST --> SuggestionCtrl
REST --> InventoryCtrl

AgentCtrl --> Chat
Chat --> Inventory
Chat --> Orch
Chat --> MCP
Chat --> DB
Chat --> Mistral

Inventory --> DB
Inventory --> Forecast
Inventory --> MCP
Inventory -.->|signal| Orch

Orch --> Risk
Orch --> Feas
Orch --> Cost
Orch --> FoodBank
Orch --> Expl
Orch --> RAG
Orch --> MCP
Orch --> DB
Orch --> Mistral

Risk --> MCP
Risk --> DB
Feas --> MCP
Cost --> MCP
Cost --> DB
FoodBank --> MCP
FoodBank --> DB
Expl --> MCP
Expl --> Mistral

SuggestionCtrl --> DB
InventoryCtrl --> DB
```