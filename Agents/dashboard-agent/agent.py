"""Dashboard Agent: item-level dashboard insights for sales, demand, and stock charts."""
import os
import logging
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request
from fastmcp import FastMCP

try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("dashboard-agent")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "smartcart_ai")
DB_USER = os.getenv("DB_USER", "meghanarendrasimha")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Welcome@123")
PORT = int(os.getenv("PORT", "9008"))

app = Flask(__name__)
mcp = FastMCP("Dashboard Agent")


def _to_float(value: Any) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def get_db_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor,
    )


def _find_item(cur, query: str) -> Optional[Dict[str, Any]]:
    like = f"%{query.strip()}%"
    cur.execute(
        """
        SELECT inventory_id, item_name, category, item_type, vendor_id,
               COALESCE(opening_stock, 0) AS opening_stock,
               COALESCE(min_stock, 0) AS min_stock,
               COALESCE(max_capacity, 0) AS max_capacity,
               selling_price
        FROM inventory
        WHERE item_name ILIKE %s OR category ILIKE %s
        ORDER BY CASE WHEN item_name ILIKE %s THEN 0 ELSE 1 END, item_name ASC
        LIMIT 1
        """,
        (like, like, like),
    )
    row = cur.fetchone()
    return dict(row) if row else None


def _sales_series(cur, inventory_id: str) -> Dict[str, List[Any]]:
    cur.execute(
        """
        WITH recent AS (
            SELECT purchase_date::date AS sale_date,
                   COALESCE(SUM(quantity), 0) AS quantity,
                   COALESCE(SUM(total_cost), 0) AS revenue
            FROM sales
            WHERE inventory_id = %s
            GROUP BY purchase_date::date
            ORDER BY sale_date DESC
            LIMIT 7
        )
        SELECT sale_date, quantity, revenue
        FROM recent
        ORDER BY sale_date ASC
        """,
        (inventory_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        labels = [(date.today() - timedelta(days=offset)).strftime("%m/%d") for offset in range(6, -1, -1)]
        return {"labels": labels, "quantity": [0] * 7, "revenue": [0] * 7}

    labels = [r["sale_date"].strftime("%m/%d") for r in rows]
    quantity = [_to_int(r.get("quantity")) for r in rows]
    revenue = [round(_to_float(r.get("revenue")), 2) for r in rows]
    return {"labels": labels, "quantity": quantity, "revenue": revenue}


def _demand_series(cur, inventory_id: str) -> Dict[str, List[Any]]:
    cur.execute(
        """
        SELECT prediction_date::date AS prediction_date,
               COALESCE(predicted_demand, 0) AS predicted_demand
        FROM demand
        WHERE inventory_id = %s
        ORDER BY prediction_date DESC
        LIMIT 7
        """,
        (inventory_id,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    if not rows:
        labels = [(date.today() - timedelta(days=offset)).strftime("%m/%d") for offset in range(6, -1, -1)]
        return {"labels": labels, "predicted": [0] * 7}

    rows.reverse()
    labels = [r["prediction_date"].strftime("%m/%d") for r in rows]
    predicted = [_to_int(r.get("predicted_demand")) for r in rows]
    return {"labels": labels, "predicted": predicted}


def _build_recommendation(metrics: Dict[str, Any]) -> Dict[str, Any]:
    current_stock = _to_int(metrics.get("current_stock"))
    min_stock = _to_int(metrics.get("min_stock"))
    max_capacity = _to_int(metrics.get("max_capacity"))
    avg_daily_demand = _to_float(metrics.get("avg_daily_demand"))
    coverage_days = metrics.get("stock_coverage_days")

    if current_stock <= min_stock:
        action = "reorder"
        priority = "High"
        reasoning = "Current stock is at or below minimum stock level and may cause stockout risk."
    elif coverage_days is not None and coverage_days < 5:
        action = "reorder"
        priority = "Medium"
        reasoning = "Projected stock coverage is under 5 days based on recent demand and needs replenishment soon."
    elif max_capacity > 0 and current_stock >= int(max_capacity * 0.9) and avg_daily_demand <= 2:
        action = "reduce-purchase"
        priority = "Medium"
        reasoning = "Stock is close to max capacity while demand is low, so reduce future purchase volume."
    else:
        action = "monitor"
        priority = "Low"
        reasoning = "Stock and demand are balanced. Continue monitoring and reorder only when threshold is reached."

    return {
        "action": action,
        "priority": priority,
        "reasoning": reasoning,
        "queries": [
            "Show sales trend for the last 7 records",
            "Show predicted demand for the item",
            "Compare current stock with minimum stock and expected demand",
        ],
    }


@app.get("/health")
def health():
    return jsonify({"status": "healthy", "service": "dashboard-agent", "port": PORT})


def _build_item_insights(query: str) -> Dict[str, Any]:
    query = str(query or "").strip()
    if not query:
        raise ValueError("query is required")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        item = _find_item(cur, query)
        if not item:
            cur.close()
            conn.close()
            raise LookupError(f"No inventory item found for '{query}'")

        sales = _sales_series(cur, item["inventory_id"])
        demand = _demand_series(cur, item["inventory_id"])

        current_stock = _to_int(item.get("opening_stock"))
        min_stock = _to_int(item.get("min_stock"))
        max_capacity = _to_int(item.get("max_capacity"))
        total_sales_units = sum(sales["quantity"])
        total_sales_revenue = round(sum(sales["revenue"]), 2)
        latest_predicted_demand = demand["predicted"][-1] if demand["predicted"] else 0
        avg_daily_demand = (sum(demand["predicted"]) / len(demand["predicted"])) if demand["predicted"] else 0.0
        stock_coverage_days = round(current_stock / avg_daily_demand, 1) if avg_daily_demand > 0 else None

        metrics = {
            "current_stock": current_stock,
            "min_stock": min_stock,
            "max_capacity": max_capacity,
            "stock_gap": current_stock - min_stock,
            "last_7_sales_units": total_sales_units,
            "last_7_sales_revenue": total_sales_revenue,
            "latest_predicted_demand": latest_predicted_demand,
            "avg_daily_demand": round(avg_daily_demand, 2),
            "stock_coverage_days": stock_coverage_days,
        }

        recommendation = _build_recommendation(metrics)
        expected_7_day_demand = int(round(avg_daily_demand * 7))

        response = {
            "query": query,
            "item": {
                "inventory_id": item.get("inventory_id"),
                "item_name": item.get("item_name"),
                "category": item.get("category"),
                "item_type": item.get("item_type"),
                "vendor_id": item.get("vendor_id"),
            },
            "metrics": metrics,
            "recommendation": recommendation,
            "charts": {
                "sales": sales,
                "demand": demand,
                "stock": {
                    "labels": ["Current", "Min", "Max", "Expected 7D Demand"],
                    "values": [current_stock, min_stock, max_capacity, expected_7_day_demand],
                },
            },
        }

        cur.close()
        conn.close()
        return response
    except (ValueError, LookupError):
        raise
    except Exception as e:
        logger.exception("Failed to build item insights")
        raise RuntimeError(str(e)) from e


@app.post("/item-insights")
def item_insights():
    body = request.get_json(silent=True) or {}
    query = str(body.get("query") or body.get("item_name") or "").strip()
    try:
        return jsonify(_build_item_insights(query))
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except LookupError as e:
        return jsonify({"error": str(e), "query": query}), 404
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


@mcp.tool()
def get_item_insights(query: str) -> Dict[str, Any]:
    """Return dashboard item insights including stock/sales/demand metrics and chart-ready series."""
    return _build_item_insights(query)


@mcp.tool()
def get_dashboard_health() -> Dict[str, Any]:
    """Return dashboard agent health details."""
    return {"status": "healthy", "service": "dashboard-agent", "port": PORT}


if __name__ == "__main__":
    logger.info("Starting Dashboard Agent on port %s", PORT)
    app.run(host="0.0.0.0", port=PORT, debug=True)
