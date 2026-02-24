"""Feasibility Subagent – DEPRECATED. Merged into Cost Impact agent (port 9002).

Use POST http://localhost:9002/feasibility-and-cost instead.
This stub returns 410 Gone so callers know to use the merged endpoint.
"""
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

MERGED_URL = os.getenv("FEASIBILITY_AND_COST_AGENT_URL", "http://localhost:9002/feasibility-and-cost")


@app.route("/feasibility", methods=["POST"])
def feasibility_endpoint():
    return jsonify({
        "error": "Feasibility agent deprecated; merged into Cost Impact.",
        "use_instead": MERGED_URL,
        "message": "POST to the URL above with the same payload (inventory_id, suggested_action, item_data, remaining_stock, context). Response includes feasibility_check and cost_impact.",
    }), 410


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "deprecated",
        "agent": "feasibility",
        "use_instead": "Feasibility & Cost Impact at port 9002",
        "url": MERGED_URL,
    }), 410


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9001"))
    app.run(host="0.0.0.0", port=port, debug=True)
