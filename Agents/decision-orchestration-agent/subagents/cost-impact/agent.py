"""Cost & Operational Impact Subagent – Ensures interventions stay within cost/margin limits."""
import os
import logging
from typing import Dict, Optional
from pathlib import Path

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from fastmcp import FastMCP

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass  # python-dotenv not installed, use system env vars

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cost-impact")

# Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "smartcart_ai")
DB_USER = os.getenv("DB_USER", "meghanarendrasimha")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Welcome@123")

# Cost limits (can be loaded from config or DB)
MAX_ORDER_COST = float(os.getenv("MAX_ORDER_COST", "10000.0"))
MIN_MARGIN_PERCENT = float(os.getenv("MIN_MARGIN_PERCENT", "20.0"))

mcp = FastMCP("Cost Impact Subagent")
app = Flask(__name__)


def get_db_connection():
    """Create a PostgreSQL connection."""
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor
    )


def get_average_unit_cost(inventory_id: str) -> Optional[float]:
    """Get average unit cost from recent sales."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT AVG(unit_cost) as avg_cost
            FROM sales
            WHERE inventory_id = %s AND unit_cost > 0
            ORDER BY purchase_date DESC
            LIMIT 10
            """,
            (inventory_id,)
        )
        result = cur.fetchone()
        cur.close()
        conn.close()
        return float(result['avg_cost']) if result and result['avg_cost'] else None
    except Exception as e:
        logger.error(f"Error fetching average cost: {e}")
        return None


def assess_cost_impact(inventory_id: str, suggested_action: str, item_data: Dict,
                      forecasted_demand: Optional[float], context: Dict) -> Dict:
    """Assess cost and operational impact of the suggested action."""
    estimated_cost = 0.0
    within_budget = True
    cost_breakdown = {}
    warnings = []
    
    if suggested_action == "reorder":
        # Calculate suggested reorder quantity
        min_stock = item_data.get("min_stock", 10)
        max_capacity = item_data.get("max_capacity", 1000)
        remaining_stock = context.get("remaining_stock", 0)
        
        # Suggested quantity: enough to reach 2x min_stock or fill to reasonable level
        target_stock = max(min_stock * 2, min_stock * 1.5)
        suggested_quantity = max(target_stock - remaining_stock, min_stock)
        
        # Cap at max capacity
        if max_capacity:
            suggested_quantity = min(suggested_quantity, max_capacity - remaining_stock)
        
        # Get unit cost
        unit_cost = get_average_unit_cost(inventory_id)
        if not unit_cost:
            # Fallback: use context or default
            unit_cost = context.get("unit_cost", 10.0)
            warnings.append("Using estimated unit cost")
        
        estimated_cost = suggested_quantity * unit_cost
        cost_breakdown = {
            "suggested_quantity": suggested_quantity,
            "unit_cost": unit_cost,
            "total_cost": estimated_cost,
        }
        
        # Check against budget limits
        if estimated_cost > MAX_ORDER_COST:
            within_budget = False
            warnings.append(f"Order cost (${estimated_cost:.2f}) exceeds max order limit (${MAX_ORDER_COST:.2f})")
        
        # Check margin (if selling price available)
        selling_price = context.get("selling_price")
        if selling_price and unit_cost:
            margin_percent = ((selling_price - unit_cost) / selling_price) * 100
            if margin_percent < MIN_MARGIN_PERCENT:
                warnings.append(f"Margin ({margin_percent:.1f}%) below minimum ({MIN_MARGIN_PERCENT}%)")
    
    elif suggested_action == "transfer":
        # Transfer costs are typically lower (shipping/handling)
        estimated_cost = 50.0  # Placeholder
        cost_breakdown = {
            "transfer_cost": estimated_cost,
        }
    
    elif suggested_action in ["hold", "none"]:
        # No additional cost
        estimated_cost = 0.0
        cost_breakdown = {"action": "no_cost"}
    
    # Calculate operational impact
    operational_impact = "low"
    if estimated_cost > MAX_ORDER_COST * 0.8:
        operational_impact = "high"
    elif estimated_cost > MAX_ORDER_COST * 0.5:
        operational_impact = "medium"
    
    return {
        "estimated_cost": estimated_cost,
        "within_budget": within_budget,
        "cost_breakdown": cost_breakdown,
        "operational_impact": operational_impact,
        "warnings": warnings,
        "suggested_action": suggested_action,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    }


@app.route("/cost-impact", methods=["POST"])
def cost_impact_endpoint():
    """Cost impact assessment endpoint."""
    payload = request.get_json(silent=True) or {}
    
    inventory_id = payload.get("inventory_id", "")
    suggested_action = payload.get("suggested_action", "none")
    item_data = payload.get("item_data", {})
    forecasted_demand = payload.get("forecasted_demand")
    context = payload.get("context", {})
    
    if not inventory_id:
        return jsonify({"error": "inventory_id required"}), 400
    
    result = assess_cost_impact(inventory_id, suggested_action, item_data, forecasted_demand, context)
    return jsonify(result), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "agent": "cost-impact"}), 200


@mcp.tool()
def assess_item_cost_impact(inventory_id: str, action: str) -> dict:
    """Assess cost impact of an action for an inventory item."""
    return assess_cost_impact(inventory_id, action, {}, None, {})


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9002"))
    app.run(host="0.0.0.0", port=port, debug=True)
