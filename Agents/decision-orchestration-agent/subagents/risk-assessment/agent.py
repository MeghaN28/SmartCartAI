"""Risk Assessment Subagent – Analyzes risk status of flagged inventory items."""
import os
import logging
from typing import Dict, List
from datetime import datetime, timedelta
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
logger = logging.getLogger("risk-assessment")

# Configuration
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "smartcart_ai")
DB_USER = os.getenv("DB_USER", "meghanarendrasimha")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Welcome@123")

mcp = FastMCP("Risk Assessment Subagent")
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


def assess_risk(inventory_id: str, item_data: Dict, remaining_stock: int, 
                consumption_history: List[Dict], forecasted_demand: float) -> Dict:
    """Assess risk factors for an inventory item."""
    risk_factors = []
    risk_score = 0
    
    # Risk 1: Stock level below minimum
    min_stock = item_data.get("min_stock", 10)
    if remaining_stock < min_stock:
        risk_factors.append({
            "factor": "low_stock",
            "severity": "high" if remaining_stock == 0 else "medium",
            "description": f"Stock ({remaining_stock}) below minimum threshold ({min_stock})",
        })
        risk_score += 30 if remaining_stock == 0 else 20
    
    # Risk 2: High consumption rate vs forecast
    if consumption_history and forecasted_demand > 0:
        recent_consumption = sum(float(h.get("quantity_consumed", 0)) for h in consumption_history[:7])
        avg_daily = recent_consumption / min(7, len(consumption_history))
        if avg_daily > forecasted_demand * 1.5:
            risk_factors.append({
                "factor": "high_consumption_rate",
                "severity": "high",
                "description": f"Consumption rate ({avg_daily:.2f}/day) exceeds forecast ({forecasted_demand:.2f}/day)",
            })
            risk_score += 25
    
    # Risk 3: Stockout risk (days until stockout)
    if consumption_history and remaining_stock > 0:
        recent_consumption = sum(float(h.get("quantity_consumed", 0)) for h in consumption_history[:7])
        avg_daily = recent_consumption / min(7, len(consumption_history)) if consumption_history else 0
        if avg_daily > 0:
            days_until_stockout = remaining_stock / avg_daily
            if days_until_stockout < 3:
                risk_factors.append({
                    "factor": "imminent_stockout",
                    "severity": "critical",
                    "description": f"Estimated {days_until_stockout:.1f} days until stockout",
                })
                risk_score += 40
            elif days_until_stockout < 7:
                risk_factors.append({
                    "factor": "potential_stockout",
                    "severity": "high",
                    "description": f"Estimated {days_until_stockout:.1f} days until stockout",
                })
                risk_score += 20
    
    # Risk 4: Category-based risk (critical items)
    category = item_data.get("category", "").lower()
    item_type = item_data.get("item_type", "").lower()
    if any(keyword in category or keyword in item_type for keyword in ["emergency", "critical", "life-saving"]):
        risk_factors.append({
            "factor": "critical_category",
            "severity": "high",
            "description": "Item is in a critical category",
        })
        risk_score += 15
    
    # Determine overall risk level
    if risk_score >= 60:
        risk_level = "critical"
    elif risk_score >= 40:
        risk_level = "high"
    elif risk_score >= 20:
        risk_level = "medium"
    else:
        risk_level = "low"
    
    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_factors": risk_factors,
        "timestamp": datetime.now().isoformat(),
    }


@app.route("/risk", methods=["POST"])
def risk_endpoint():
    """Risk assessment endpoint."""
    payload = request.get_json(silent=True) or {}
    
    inventory_id = payload.get("inventory_id", "")
    item_data = payload.get("item_data", {})
    remaining_stock = payload.get("remaining_stock", 0)
    consumption_history = payload.get("consumption_history", [])
    forecasted_demand = payload.get("forecasted_demand", 0.0)
    
    if not inventory_id:
        return jsonify({"error": "inventory_id required"}), 400
    
    result = assess_risk(inventory_id, item_data, remaining_stock, consumption_history, forecasted_demand)
    return jsonify(result), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "agent": "risk-assessment"}), 200


@mcp.tool()
def assess_item_risk(inventory_id: str) -> dict:
    """Assess risk for an inventory item."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM inventory WHERE inventory_id = %s", (inventory_id,))
        item = cur.fetchone()
        cur.close()
        conn.close()
        
        if not item:
            return {"error": f"Inventory item {inventory_id} not found"}
        
        item_data = dict(item)
        remaining_stock = item_data.get("opening_stock", 0)
        
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM consumption WHERE inventory_id = %s ORDER BY transaction_date DESC LIMIT 30",
            (inventory_id,)
        )
        consumption_history = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        
        return assess_risk(inventory_id, item_data, remaining_stock, consumption_history, 0.0)
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9004"))
    app.run(host="0.0.0.0", port=port, debug=True)
