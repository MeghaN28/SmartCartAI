"""Feasibility Subagent – Checks operational limits and category-based regulations."""
import os
import logging
from typing import Dict

from flask import Flask, request, jsonify
from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("feasibility")

mcp = FastMCP("Feasibility Subagent")
app = Flask(__name__)

# Category-based regulations (can be loaded from DB or config)
CATEGORY_REGULATIONS = {
    "controlled_substance": {
        "requires_approval": True,
        "max_order_quantity": 100,
        "requires_documentation": True,
    },
    "prescription": {
        "requires_approval": True,
        "max_order_quantity": 500,
        "requires_documentation": True,
    },
    "over_the_counter": {
        "requires_approval": False,
        "max_order_quantity": 1000,
        "requires_documentation": False,
    },
}


def check_feasibility(inventory_id: str, suggested_action: str, item_data: Dict, 
                      remaining_stock: int, context: Dict) -> Dict:
    """Check if the suggested action is operationally feasible."""
    constraints = []
    is_feasible = True
    
    # Check 1: Action validity
    valid_actions = ["reorder", "hold", "transfer", "discard", "none"]
    if suggested_action not in valid_actions:
        constraints.append({
            "constraint": "invalid_action",
            "description": f"Action '{suggested_action}' is not valid",
        })
        is_feasible = False
        return {"is_feasible": False, "constraints": constraints}
    
    if suggested_action == "none":
        return {"is_feasible": True, "constraints": [], "message": "No action required"}
    
    # Check 2: Category-based regulations
    category = item_data.get("category", "").lower()
    item_type = item_data.get("item_type", "").lower()
    
    # Determine regulation category
    regulation_category = None
    if any(keyword in category or keyword in item_type for keyword in ["controlled", "narcotic"]):
        regulation_category = "controlled_substance"
    elif any(keyword in category or keyword in item_type for keyword in ["prescription", "rx"]):
        regulation_category = "prescription"
    else:
        regulation_category = "over_the_counter"
    
    regulations = CATEGORY_REGULATIONS.get(regulation_category, {})
    
    if suggested_action == "reorder":
        # Check if reorder requires approval
        if regulations.get("requires_approval", False):
            constraints.append({
                "constraint": "approval_required",
                "description": f"Category '{regulation_category}' requires approval for reorder",
                "severity": "warning",
            })
        
        # Check max order quantity
        max_order = regulations.get("max_order_quantity", 1000)
        min_stock = item_data.get("min_stock", 10)
        suggested_quantity = max(min_stock * 2, min_stock - remaining_stock)
        
        if suggested_quantity > max_order:
            constraints.append({
                "constraint": "max_order_exceeded",
                "description": f"Suggested quantity ({suggested_quantity}) exceeds max ({max_order})",
                "severity": "error",
            })
            is_feasible = False
        
        # Check if documentation required
        if regulations.get("requires_documentation", False):
            constraints.append({
                "constraint": "documentation_required",
                "description": "Documentation required for this category",
                "severity": "info",
            })
    
    # Check 3: Storage capacity
    max_capacity = item_data.get("max_capacity")
    if max_capacity and suggested_action == "reorder":
        min_stock = item_data.get("min_stock", 10)
        suggested_quantity = max(min_stock * 2, min_stock - remaining_stock)
        if remaining_stock + suggested_quantity > max_capacity:
            constraints.append({
                "constraint": "storage_capacity",
                "description": f"Reorder would exceed storage capacity ({max_capacity})",
                "severity": "error",
            })
            is_feasible = False
    
    # Check 4: Vendor availability (from context)
    vendor_id = item_data.get("vendor_id")
    if not vendor_id and suggested_action == "reorder":
        constraints.append({
            "constraint": "no_vendor",
            "description": "No vendor assigned for this item",
            "severity": "warning",
        })
    
    return {
        "is_feasible": is_feasible,
        "constraints": constraints,
        "regulation_category": regulation_category,
        "suggested_action": suggested_action,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    }


@app.route("/feasibility", methods=["POST"])
def feasibility_endpoint():
    """Feasibility check endpoint."""
    payload = request.get_json(silent=True) or {}
    
    inventory_id = payload.get("inventory_id", "")
    suggested_action = payload.get("suggested_action", "none")
    item_data = payload.get("item_data", {})
    remaining_stock = payload.get("remaining_stock", 0)
    context = payload.get("context", {})
    
    if not inventory_id:
        return jsonify({"error": "inventory_id required"}), 400
    
    result = check_feasibility(inventory_id, suggested_action, item_data, remaining_stock, context)
    return jsonify(result), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "agent": "feasibility"}), 200


@mcp.tool()
def check_item_feasibility(inventory_id: str, action: str) -> dict:
    """Check feasibility of an action for an inventory item."""
    # This would need to fetch item data from DB
    return check_feasibility(inventory_id, action, {}, 0, {})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9001"))
    app.run(host="0.0.0.0", port=port, debug=True)
