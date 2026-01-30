"""Inventory Agent (stub)

Exposes a small HTTP endpoint that receives inventory events and forwards them to
the Decision Orchestration Agent for evaluation. Designed as a minimal example
for local development and testing.
"""
import os
import logging
import requests
from flask import Flask, request, jsonify

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("inventory-agent")

DECISION_AGENT_URL = os.getenv("DECISION_AGENT_URL", "http://localhost:9000/orchestrate")

app = Flask(__name__)


def notify_decision(payload):
    """Send an inventory event to the Decision Orchestration Agent.

    Returns the parsed JSON response, or a dict with `error` on failure.
    """
    try:
        logger.info("Notifying decision agent at %s", DECISION_AGENT_URL)
        r = requests.post(DECISION_AGENT_URL, json=payload, timeout=5)
        try:
            return r.json()
        except Exception:
            return {"status_code": r.status_code, "text": r.text}
    except Exception as e:
        logger.exception("Failed to notify decision agent")
        return {"error": str(e)}


@app.route("/inventory", methods=["POST"])
def inventory_event():
    payload = request.get_json(silent=True) or {}
    logger.info("Received inventory event: %s", payload)
    result = notify_decision(payload)
    return jsonify({"result": result}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9005"))
    app.run(host="0.0.0.0", port=port, debug=True)
