# Dashboard Agent (port 9008)

Provides item-level dashboard insights for search queries:

- current stock vs min/max thresholds
- last 7 sales records (units + revenue)
- last 7 demand predictions
- recommendation action + priority

## Run

```bash
cd Agents/dashboard-agent
pip install -r requirements.txt
python agent.py
```

## Endpoints

- `GET /health`
- `POST /item-insights` with `{ "query": "milk" }`
