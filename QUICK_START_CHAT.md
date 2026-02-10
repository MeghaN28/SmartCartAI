# Quick Start - Chat Agent

The Chat Agent needs to be running as a Flask service for the chatbot to work.

## Option 1: Start All Agents (Recommended)

```bash
cd /Users/meghanarendrasimha/Documents/SmartCartAI
./start_agents.sh
```

This starts all agents including the Chat Agent on port 9006.

## Option 2: Start Chat Agent Only

If you only need the chat agent:

```bash
cd /Users/meghanarendrasimha/Documents/SmartCartAI
./start_chat_agent.sh
```

Or manually:

```bash
cd /Users/meghanarendrasimha/Documents/SmartCartAI/Agents/decision-orchestration-agent/subagents/chat

# Set environment variables
export MISTRAL_API_KEY=SWqT1KZpsaFqYIcd6AqFlvQrjK8xFWeC
export MISTRAL_MODEL=mistral-medium
export DB_HOST=localhost
export DB_PORT=5432
export DB_NAME=smartcart_ai
export DB_USER=meghanarendrasimha
export DB_PASSWORD=Welcome@123
export DECISION_ORCHESTRATOR_URL=http://localhost:9000
export PORT=9006

# Start Flask app (use python3 on macOS)
python3 agent.py
```

## Verify Chat Agent is Running

```bash
# Check if port 9006 is listening
curl http://localhost:9006/health

# Should return:
# {"status":"ok","agent":"chat","mistral_configured":true}
```

## Troubleshooting

### Connection Refused Error

If you get "Connection refused" error:

1. **Check if Chat Agent is running:**
   ```bash
   lsof -i :9006
   # or
   curl http://localhost:9006/health
   ```

2. **If not running, start it:**
   ```bash
   ./start_chat_agent.sh
   ```

3. **Check logs:**
   ```bash
   tail -f logs/chat-agent.log
   ```

### Port Already in Use

If port 9006 is already in use:

```bash
# Find and kill the process
lsof -ti :9006 | xargs kill -9

# Or change the port
export PORT=9007
python3 agent.py
```

Then update the backend config:
```java
CHAT_AGENT_URL=http://localhost:9007
```

### Dependencies Missing

Install dependencies:

```bash
cd Agents/decision-orchestration-agent/subagents/chat
pip3 install -r requirements.txt
```

## Required Services

For the chatbot to work fully, you need:

1. ✅ **Chat Agent** (port 9006) - Flask service
2. ✅ **Decision Orchestrator Agent** (port 9000) - Flask service  
3. ✅ **Subagents** (ports 9001-9004) - Flask services
4. ✅ **Java Backend** (port 8080) - Spring Boot
5. ✅ **PostgreSQL Database** - Running with `smartcart_ai` database

## Testing the Chat Agent

Once running, test it:

```bash
curl -X POST http://localhost:9006/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Check inventory and suggest actions", "session_id": "test123"}'
```

Or test via backend:

```bash
curl -X POST http://localhost:8080/api/agents/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Check inventory and suggest actions", "session_id": "test123"}'
```
