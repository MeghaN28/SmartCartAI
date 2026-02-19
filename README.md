# SmartCartAI

SmartCartAI is an intelligent inventory management system designed to optimize retail operations through AI-powered decision-making. The system integrates a React Native mobile app frontend, a Java backend for data processing, and Python-based data generation tools to simulate and manage inventory, sales, and consumption data.

## Features

- **AI-Powered Inventory Management**: Automated decision-making for stock levels, expiry tracking, and waste reduction
- **Real-time Dashboard**: Monitor inventory status, at-risk items, and agent actions
- **Mobile App Interface**: Cross-platform React Native app for easy access
- **Data Simulation**: Generate realistic inventory, sales, and consumption datasets
- **Modular Architecture**: Separate frontend, backend, and data components for scalability

## Project Structure

```
SmartCartAI/
├── README.md
├── Agents/                    # AI agents for decision-making
├── Dataset/                   # Data generation and CSV files
│   ├── createdataset.py       # Python script to generate sample data
│   ├── inventory_master_50_unique.csv
│   ├── sales_50.csv
│   └── consumption_50.csv
├── SmartCartAIBackend/        # Java backend application + services
│   ├── README.md
│   ├── services/              # Inventory, Sales, Demand services
│   │   ├── inventory-service/
│   │   ├── sales-service/
│   │   └── demand-service/
│   ├── lib/
│   └── src/
│       └── App.java
├── SmartCartAIFrontEnd/       # React Native/Expo frontend
│   ├── app.json
│   ├── package.json
│   └── app/
│       ├── _layout.tsx
│       ├── (tabs)/
│       │   ├── _layout.tsx
│       │   ├── index.tsx      # Dashboard
│       │   └── explore.tsx
│       ├── inventory.tsx      # Inventory overview
│       ├── decisions.tsx
│       └── impact.tsx

```

## Architecture layers

This project is organized in clearly separated layers that map to the architecture diagram (`Dataset/SmartCartAI_UseCases.drawio`). Below is a short description of each layer and its responsibilities.

- **User Interface (UI) — `SmartCartAIFrontEnd/`** 🔧
  - Cross-platform React Native (Expo) mobile app that displays the dashboard, inventory list, decision recommendations, and impact analysis.
  - Communicates with the backend services and agents through REST APIs.
  - Responsibilities: visualization, user actions, showing explanations and agent recommendations.

- **Agents — `Agents/`** 🤖
  - Contains AI agents and helper scripts. The main **Decision-Orchestration Agent** coordinates subagents (Feasibility, CostImpact, Explanation, RiskAssessment).
  - Responsibilities: orchestrate decision-making, aggregate signals, request subagent analyses, and return structured recommendations and explanations for the UI.

- **Backend Services — `SmartCartAIBackend/services/`** 🛠️
  - Microservices that provide REST APIs for core domain data:
    - Inventory Service — inventory CRUD, flagging, recommendations endpoint
    - Sales Service — sales data access and ingestion
    - Demand Service — demand predictions and related endpoints
  - Each service owns its API contract and reads/writes to the shared database.

- **Database — `database/`** 🗄️
  - SQL schema and migration artifacts live here (`database/schema.sql`).
  - Stores inventory, sales, and demand data used by services and agents.

- **Dataset & Data Generation — `Dataset/`** 🧾
  - Scripts and CSV sample data for testing and prototyping (e.g., `createdataset.py`, `sales_50.csv`, `inventory_master_50_unique.csv`).
  - Used to train models or run experiments in the Agents layer.


- **Docs & CI — `docs/`, `.github/workflows/`** 📚
  - Architecture documentation and CI placeholders. Keep these up to date as services and tests are added.


## Installation

### Prerequisites

- Node.js (for frontend)
- Java JDK (for backend)
- Python 3 (for data generation)
- Expo CLI (for React Native development)

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd SmartCartAIFrontEnd
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npx expo start
   ```

### Backend Setup

1. Navigate to the backend directory:
   ```bash
   cd SmartCartAIBackend
   ```

2. Compile and run the Java application:
   ```bash
   javac -d bin src/App.java
   java -cp bin App
   ```

3. Service placeholders for Inventory, Sales and Demand live under `SmartCartAIBackend/services/`. Once implemented, you can build the service images and run the local stack using `infra/docker-compose.yml` (see `infra/` for a placeholder `docker-compose.yml`).

How to run placeholders locally:

- Build and run the placeholder stack:
  ```bash
  docker-compose -f infra/docker-compose.yml up --build -d
  ```

- Verify services (example):
  - Inventory: http://localhost:8081/inventory
  ```bash
  curl http://localhost:8081/inventory || echo "inventory service not responding"
  ```

- Stop the stack:
  ```bash
  docker-compose -f infra/docker-compose.yml down
  ```

Notes:
- Update `infra/docker-compose.yml` to point to local `build:` contexts or pushed image names once you implement the services. 🔧
- Add CI steps to build and publish images to a registry when services are production-ready. 🚀

### Data Generation

1. Navigate to the dataset directory:
   ```bash
   cd Dataset
   ```

2. Run the Python script to generate sample data:
   ```bash
   python createdataset.py
   ```

## Usage

### Mobile App

- **Dashboard**: View key metrics including total inventory items, at-risk items, agent actions, and waste reduction estimates
- **Inventory**: Browse inventory items with stock levels, expiry information, and risk assessments
- **Decisions**: Review AI-generated recommendations for inventory management
- **Impact**: Analyze the impact of AI decisions on operations

### Data Analysis

The dataset includes:
- `inventory_master_50_unique.csv`: Product catalog with categories, stock levels, and vendor information
- `sales_50.csv`: Daily sales data for 50 products
- `consumption_50.csv`: Consumption tracking including routine use, spoilage, and samples

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request


## Technologies Used

- **Frontend**: React Native, Expo, TypeScript
- **Backend**: Java
- **Data Processing**: Python, Pandas, NumPy
- **AI/ML**: (To be implemented in Agents folder)
# Subagents (from Agents/decision-orchestration-agent)
cd Agents/decision-orchestration-agent/subagents/risk-assessment && PORT=9004 python3 agent.py
cd Agents/decision-orchestration-agent/subagents/feasibility && PORT=9001 python3 agent.py
cd Agents/decision-orchestration-agent/subagents/cost-impact && PORT=9002 python3 agent.py
cd Agents/decision-orchestration-agent/subagents/explanation && PORT=9003 python3 agent.py
cd Agents/decision-orchestration-agent/subagents/food-bank && PORT=9007 python3 agent.py

# Inventory
cd Agents/inventory-agent && PORT=9005 python3 agent.py

# Orchestrator & Chat
cd Agents/decision-orchestration-agent && PORT=9000 python3 agent.py
cd Agents/decision-orchestration-agent/subagents/chat && PORT=9006 python3 agent.py