"""Feasibility & Cost Impact Subagent (merged) – Operational feasibility (action, capacity, vendor) and cost/margin limits. No regulations/approval."""
import os
import logging
from typing import Dict, Optional
from pathlib import Path
from datetime import datetime

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

mcp = FastMCP("Feasibility & Cost Impact Subagent")
app = Flask(__name__)

VALID_ACTIONS = ["reorder", "hold", "transfer", "discard", "none", "discount", "bundle", "donate", "price_increase"]


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


def get_latest_unit_cost(inventory_id: str) -> Optional[float]:
    """Get the most recent unit_cost from sales (previous purchase) for this item. Used to suggest selling_price when missing."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT unit_cost FROM sales
            WHERE inventory_id = %s AND unit_cost IS NOT NULL AND unit_cost > 0
            ORDER BY purchase_date DESC NULLS LAST
            LIMIT 1
            """,
            (inventory_id,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        return float(row["unit_cost"]) if row and row.get("unit_cost") is not None else None
    except Exception as e:
        logger.debug(f"Could not get latest unit_cost for {inventory_id}: {e}")
        return None


def get_average_unit_cost(inventory_id: str) -> Optional[float]:
    """Get average unit cost from the last 10 sales (by purchase_date)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT AVG(unit_cost) AS avg_cost
            FROM (
                SELECT unit_cost FROM sales
                WHERE inventory_id = %s AND unit_cost > 0
                ORDER BY purchase_date DESC NULLS LAST
                LIMIT 10
            ) t
            """,
            (inventory_id,),
        )
        result = cur.fetchone()
        cur.close()
        conn.close()
        return float(result["avg_cost"]) if result and result.get("avg_cost") is not None else None
    except Exception as e:
        logger.error(f"Error fetching average cost: {e}")
        return None


def check_feasibility_simple(
    inventory_id: str,
    suggested_action: str,
    item_data: Dict,
    remaining_stock: int,
    context: Dict,
) -> Dict:
    """Check if the suggested action is operationally feasible (no regulations/approval)."""
    constraints = []
    is_feasible = True

    if suggested_action not in VALID_ACTIONS:
        constraints.append({
            "constraint": "invalid_action",
            "description": f"Action '{suggested_action}' is not valid",
        })
        is_feasible = False
        return {
            "is_feasible": False,
            "constraints": constraints,
            "suggested_action": suggested_action,
            "timestamp": datetime.now().isoformat(),
        }

    if suggested_action == "none":
        return {
            "is_feasible": True,
            "constraints": [],
            "message": "No action required",
            "suggested_action": suggested_action,
            "timestamp": datetime.now().isoformat(),
        }

    if suggested_action == "reorder":
        min_stock = item_data.get("min_stock", 10)
        max_capacity = item_data.get("max_capacity")
        suggested_quantity = max(min_stock * 2, min_stock - remaining_stock)
        if remaining_stock < 0:
            suggested_quantity = max(suggested_quantity, min_stock)

        if max_capacity is not None and remaining_stock + suggested_quantity > max_capacity:
            constraints.append({
                "constraint": "storage_capacity",
                "description": f"Reorder would exceed storage capacity ({max_capacity})",
                "severity": "error",
            })
            is_feasible = False

        vendor_id = item_data.get("vendor_id")
        if not vendor_id:
            constraints.append({
                "constraint": "no_vendor",
                "description": "No vendor assigned for this item",
                "severity": "warning",
            })

    return {
        "is_feasible": is_feasible,
        "constraints": constraints,
        "suggested_action": suggested_action,
        "timestamp": datetime.now().isoformat(),
    }


def feasibility_and_cost_impact(
    inventory_id: str,
    suggested_action: str,
    item_data: Dict,
    remaining_stock: int,
    forecasted_demand: Optional[float],
    context: Dict,
) -> Dict:
    """Run feasibility (simple) and cost impact; return both for orchestrator."""
    ctx = dict(context)
    ctx.setdefault("remaining_stock", remaining_stock)
    feasibility_check = check_feasibility_simple(
        inventory_id, suggested_action, item_data, remaining_stock, context
    )
    cost_impact = assess_cost_impact(
        inventory_id, suggested_action, item_data, forecasted_demand, ctx
    )
    return {
        "feasibility_check": feasibility_check,
        "cost_impact": cost_impact,
    }


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
        
        # Get unit cost (average of last 10 sales, or latest single sale, or context/default)
        unit_cost = get_average_unit_cost(inventory_id) or get_latest_unit_cost(inventory_id)
        if not unit_cost:
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
        
        # Check margin (if selling price available from context or item_data)
        selling_price = context.get("selling_price") or item_data.get("selling_price")
        try:
            if selling_price is not None:
                selling_price = float(selling_price)
        except (TypeError, ValueError):
            selling_price = None
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

    elif suggested_action == "price_increase":
        # Pricing intent: validate margin stays acceptable after increase (no extra cost; revenue impact only)
        selling_price = context.get("selling_price") or item_data.get("selling_price")
        unit_cost = get_average_unit_cost(inventory_id) or get_latest_unit_cost(inventory_id) or context.get("unit_cost")
        estimated_cost = 0.0
        cost_breakdown = {"action": "price_increase", "revenue_impact": "positive"}
        if selling_price is not None and unit_cost is not None:
            try:
                sp, uc = float(selling_price), float(unit_cost)
                margin_percent = ((sp - uc) / sp) * 100 if sp else 0
                if margin_percent < MIN_MARGIN_PERCENT:
                    warnings.append(f"Current margin ({margin_percent:.1f}%) below minimum ({MIN_MARGIN_PERCENT}%); price increase still improves margin.")
            except (TypeError, ValueError):
                pass

    elif suggested_action == "discount":
        # Waste/pricing: ensure discounted price does not go below cost (cost = previous unit_cost from sales)
        selling_price = context.get("selling_price") or item_data.get("selling_price")
        unit_cost = get_average_unit_cost(inventory_id) or get_latest_unit_cost(inventory_id) or context.get("unit_cost")
        discount_pct = context.get("suggested_discount_percent") or 0
        estimated_cost = 0.0
        cost_breakdown = {"action": "discount", "discount_pct": discount_pct}
        if selling_price is not None and unit_cost is not None and discount_pct:
            try:
                sp, uc = float(selling_price), float(unit_cost)
                discounted_price = sp * (1 - discount_pct / 100.0)
                if discounted_price < uc:
                    within_budget = False
                    warnings.append(f"Discounted price (${discounted_price:.2f}) below cost (${uc:.2f}); consider lower discount or donate.")
            except (TypeError, ValueError):
                pass

    elif suggested_action in ["hold", "none", "discard", "donate", "bundle"]:
        # No additional cost (donate/bundle are clearance; treat as zero cost here)
        estimated_cost = 0.0
        cost_breakdown = {"action": "no_cost" if suggested_action in ["hold", "none"] else suggested_action}
    
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
        "timestamp": datetime.now().isoformat(),
    }


@app.route("/feasibility-and-cost", methods=["POST"])
def feasibility_and_cost_endpoint():
    """Combined feasibility + cost impact (one call for orchestrator)."""
    payload = request.get_json(silent=True) or {}
    inventory_id = payload.get("inventory_id", "")
    suggested_action = payload.get("suggested_action", "none")
    item_data = payload.get("item_data", {})
    forecasted_demand = payload.get("forecasted_demand")
    context = payload.get("context", {})
    remaining_stock = payload.get("remaining_stock")
    if remaining_stock is None:
        remaining_stock = context.get("remaining_stock", 0)
    if not inventory_id:
        return jsonify({"error": "inventory_id required"}), 400
    context.setdefault("selling_price", item_data.get("selling_price"))
    context.setdefault("remaining_stock", remaining_stock)
    result = feasibility_and_cost_impact(
        inventory_id, suggested_action, item_data, remaining_stock, forecasted_demand, context
    )
    return jsonify(result), 200


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
    return jsonify({"status": "ok", "agent": "feasibility-cost-impact"}), 200


@mcp.tool()
def assess_feasibility_and_cost(
    inventory_id: str,
    action: str,
    item_data: Optional[dict] = None,
    remaining_stock: int = 0,
    context: Optional[dict] = None,
) -> dict:
    """Check feasibility and cost impact for an action (merged)."""
    item_data = item_data or {}
    context = context or {}
    result = feasibility_and_cost_impact(
        inventory_id, action, item_data, remaining_stock, None, context
    )
    return result


@mcp.tool()
def assess_item_cost_impact(inventory_id: str, action: str) -> dict:
    """Assess cost impact of an action for an inventory item (cost only)."""
    return assess_cost_impact(inventory_id, action, {}, None, {})


if __name__ == "__main__":
    # Mode switch:
    # - Default: Flask REST server (existing app integrations)
    # - MCP HTTP: expose MCP tools at http://host:port/mcp (for MCP-first usage)
    mode = os.getenv("SMARTCART_AGENT_MODE", "flask").strip().lower()
    if mode in ("mcp", "mcp_http", "mcp-http", "http_mcp"):
        mcp_port = int(os.getenv("MCP_PORT", "9102"))
        host = os.getenv("MCP_HOST", "0.0.0.0")
        logger.info("Starting Feasibility & Cost Impact MCP server on %s:%s", host, mcp_port)
        mcp.run(transport="http", host=host, port=mcp_port)
    else:
        port = int(os.getenv("PORT", "9002"))
        app.run(host="0.0.0.0", port=port, debug=True)
