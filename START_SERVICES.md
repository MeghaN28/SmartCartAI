# SmartCartAI - Service Startup Guide

This guide shows how to start all three components of SmartCartAI in separate terminals.

## Prerequisites

1. **Database**: Ensure PostgreSQL is running and `smartcart_ai` database exists
2. **Dependencies**: 
   - Python 3.8+ with all agent dependencies installed
   - Java 17+ and Maven
   - Node.js and npm

## Starting Services

Open **3 separate terminal windows** and run the following commands:

### Terminal 1: Python Agents

```bash
cd /Users/meghanarendrasimha/Documents/SmartCartAI
./start_agents.sh
```

This will start:
- Risk Assessment Agent (port 9004)
- Feasibility Agent (port 9001)
- Cost Impact Agent (port 9002)
- Explanation Agent (port 9003)
- Chat Agent (port 9006)
- Decision Orchestrator Agent (port 9000)
- Inventory Monitoring Agent (port 9005)

**Expected output:**
```
Starting SmartCartAI Agents...
Starting Subagents...
Risk Assessment Agent started (PID: ...)
Feasibility Agent started (PID: ...)
Cost Impact Agent started (PID: ...)
Explanation Agent started (PID: ...)
Chat Agent started (PID: ...)
Starting Orchestrator Agent...
Decision Orchestrator Agent started (PID: ...)
Starting Inventory Monitoring Agent...
Inventory Monitoring Agent started (PID: ...)
All agents started successfully!
```

### Terminal 2: Java Backend

```bash
cd /Users/meghanarendrasimha/Documents/SmartCartAI/SmartCartAIBackend
./mvnw spring-boot:run
```

**Expected output:**
```
  .   ____          _            __ _ _
 /\\ / ___'_ __ _ _(_)_ __  __ _ \ \ \ \
( ( )\___ | '_ | '_| | '_ \/ _` | \ \ \ \
 \\/  ___)| |_)| | | | | || (_| |  ) ) ) )
  '  |____| .__|_| |_|_| |_\__, | / / / /
 =========|_|==============|___/=/_/_/_/
 :: Spring Boot ::                (v3.2.0)

Started SmartCartAIApplication in X.XXX seconds
```

The backend will be available at: `http://localhost:8080`

### Terminal 3: Frontend (React Native)

```bash
cd /Users/meghanarendrasimha/Documents/SmartCartAI/SmartCartAIFrontEnd/mobile
npm start
```

**Expected output:**
```
› Metro waiting on exp://192.168.x.x:8081
› Scan the QR code above with Expo Go (Android) or the Camera app (iOS)

› Press a │ open Android
› Press i │ open iOS simulator
› Press w │ open web

› Press r │ reload app
› Press m │ toggle menu
› Press ? │ show all commands
```

## Verify Services Are Running

### Check Python Agents:
```bash
curl http://localhost:9005/health  # Inventory Agent
curl http://localhost:9000/health  # Decision Orchestrator
curl http://localhost:9004/health  # Risk Assessment
curl http://localhost:9001/health  # Feasibility
curl http://localhost:9002/health  # Cost Impact
curl http://localhost:9003/health  # Explanation
curl http://localhost:9006/health  # Chat Agent
```

### Check Java Backend:
```bash
curl http://localhost:8080/api/inventory
# Or open in browser: http://localhost:8080/swagger-ui.html
```

### Check Frontend:
- The Expo dev server should show a QR code
- Open Expo Go app on your phone and scan the QR code
- Or press `i` for iOS simulator or `a` for Android emulator

## Alternative: Start All in Background

If you prefer to start everything in the background:

```bash
cd /Users/meghanarendrasimha/Documents/SmartCartAI
./start_all.sh --background
```

To stop all services:
```bash
./stop_all.sh
```

## Troubleshooting

### Python Agents Not Starting
- Check database connection: `psql -h localhost -U meghanarendrasimha -d smartcart_ai`
- Verify `.env` files exist in agent directories
- Check if ports are already in use: `lsof -i :9000`

### Java Backend Not Starting
- Verify Java 17+ is installed: `java -version`
- Check database connection in `application.properties`
- Ensure port 8080 is not in use: `lsof -i :8080`

### Frontend Not Starting
- Install dependencies: `npm install`
- Check Node.js version: `node --version` (should be 14+)
- Clear cache: `npm start -- --reset-cache`

## Service URLs

- **Java Backend API**: http://localhost:8080
- **Swagger UI**: http://localhost:8080/swagger-ui.html
- **Inventory Agent**: http://localhost:9005
- **Decision Orchestrator**: http://localhost:9000
- **Chat Agent**: http://localhost:9006
- **Frontend (Expo)**: http://localhost:8081 (Metro bundler)

## Stopping Services

### Manual Stop:
- **Terminal 1**: Press `Ctrl+C` to stop Python agents
- **Terminal 2**: Press `Ctrl+C` to stop Java backend
- **Terminal 3**: Press `Ctrl+C` to stop frontend

### Using Scripts:
```bash
./stop_all.sh  # Stops all services
./stop_agents.sh  # Stops only Python agents
```
