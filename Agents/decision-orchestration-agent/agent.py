"""Decision-Orchestration Agent (stub)

Simple Python stub showing how orchestration may call sub-agents.
"""
import requests

SUBAGENTS = {
    "feasibility": "http://localhost:9001/feasibility",
    "cost_impact": "http://localhost:9002/cost-impact",
    "explanation": "http://localhost:9003/explain",
    "risk": "http://localhost:9004/risk"
}


def orchestrate(payload):
    results = {}
    for name, url in SUBAGENTS.items():
        try:
            r = requests.post(url, json=payload, timeout=5)
            results[name] = r.json()
        except Exception as e:
            results[name] = {"error": str(e)}
    # Combine results (placeholder)
    return {"combined": results}


if __name__ == "__main__":
    sample = {"inventory_id": "123", "context": {}}
    print(orchestrate(sample))
