"""Inventory Monitoring Agent – Enhanced with PostgreSQL monitoring, forecasting, and MCP support.

Continuously monitors inventory data (stocks, consumption, thresholds, item properties) from PostgreSQL.
Signals inventory items based on real-time stock signals and consumption signals.
Uses statistical forecasting (exponential smoothing/moving averages) for demand prediction.
Sends flagged items to Decision Orchestrator Agent for prescriptive processing.
"""
import os
import logging
import threading
import time
from typing import Literal, TypedDict, List, Dict, Optional
from datetime import datetime, timedelta
from collections import deque
from pathlib import Path

import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from langgraph.graph import StateGraph, START, END
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
logger = logging.getLogger("inventory-agent")

# Configuration
DECISION_AGENT_URL = os.getenv("DECISION_AGENT_URL", "http://localhost:9000/orchestrate")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "smartcart_ai")
DB_USER = os.getenv("DB_USER", "meghanarendrasimha")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Welcome@123")
MONITORING_INTERVAL = int(os.getenv("MONITORING_INTERVAL", "30"))  # seconds

# MCP Server
mcp = FastMCP("Inventory Monitoring Agent")


# -----------------------------------------------------------------------------
# State schema (used by all nodes)
# -----------------------------------------------------------------------------


class InventoryAgentState(TypedDict, total=False):
    """State passed between graph nodes."""

    # Input
    inventory_id: str
    event_type: str  # e.g. "low_stock", "consumption", "expiry", "hold"
    quantity: int
    remaining_stock: int
    context: dict
    item_data: dict  # Full item data from DB
    consumption_history: List[dict]  # Historical consumption data
    forecasted_demand: Optional[float]  # Forecasted demand

    # Intermediate
    is_valid: bool
    suggested_action: str  # e.g. "reorder", "hold", "transfer", "none"
    stock_signal: str  # "low", "critical", "normal", "high"
    consumption_signal: str  # "high", "normal", "low"

    # Output
    decision_agent_response: dict
    error: str


# -----------------------------------------------------------------------------
# Database Connection & Utilities
# -----------------------------------------------------------------------------


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


def fetch_inventory_item(inventory_id: str) -> Optional[dict]:
    """Fetch inventory item details from PostgreSQL."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM inventory WHERE inventory_id = %s",
            (inventory_id,)
        )
        result = cur.fetchone()
        cur.close()
        conn.close()
        return dict(result) if result else None
    except Exception as e:
        logger.error(f"Error fetching inventory item {inventory_id}: {e}")
        return None


def fetch_consumption_history(inventory_id: str, days: int = 30) -> List[dict]:
    """Fetch consumption history for an item."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cutoff_date = datetime.now() - timedelta(days=days)
        cur.execute(
            """
            SELECT transaction_date as date, quantity_consumed, remaining_stock, department, consumption_reason
            FROM consumption
            WHERE inventory_id = %s AND transaction_date >= %s
            ORDER BY transaction_date DESC
            """,
            (inventory_id, cutoff_date)
        )
        results = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return results
    except Exception as e:
        logger.error(f"Error fetching consumption history for {inventory_id}: {e}")
        return []


def calculate_current_stock(inventory_id: str) -> Optional[int]:
    """Calculate current stock from opening stock and consumption."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get opening stock
        cur.execute("SELECT opening_stock FROM inventory WHERE inventory_id = %s", (inventory_id,))
        inv_row = cur.fetchone()
        if not inv_row:
            cur.close()
            conn.close()
            return None
        
        opening_stock = inv_row['opening_stock'] or 0
        
        # Get total consumption
        cur.execute(
            "SELECT COALESCE(SUM(quantity_consumed), 0) as total FROM consumption WHERE inventory_id = %s",
            (inventory_id,)
        )
        consumption_row = cur.fetchone()
        total_consumed = consumption_row['total'] if consumption_row else 0
        
        # Get latest remaining stock from consumption table if available
        cur.execute(
            "SELECT remaining_stock FROM consumption WHERE inventory_id = %s ORDER BY transaction_date DESC LIMIT 1",
            (inventory_id,)
        )
        latest_row = cur.fetchone()
        if latest_row and latest_row['remaining_stock'] is not None:
            current_stock = latest_row['remaining_stock']
        else:
            current_stock = opening_stock - total_consumed
        
        cur.close()
        conn.close()
        return max(0, current_stock)
    except Exception as e:
        logger.error(f"Error calculating current stock for {inventory_id}: {e}")
        return None


# -----------------------------------------------------------------------------
# Forecasting Functions (next 1 week forecast from past 1 week historical data)
# -----------------------------------------------------------------------------

# Demand forecast: use past 7 days of consumption to forecast for the next 7 days
FORECAST_PAST_DAYS = 7
FORECAST_NEXT_WEEK_DAYS = 7


def exponential_smoothing(history: List[float], alpha: float = 0.3) -> float:
    """Exponential smoothing forecast (daily rate)."""
    if not history:
        return 0.0
    if len(history) == 1:
        return history[0]
    
    forecast = history[0]
    for value in history[1:]:
        forecast = alpha * value + (1 - alpha) * forecast
    return forecast


def moving_average(history: List[float], window: int = 7) -> float:
    """Moving average forecast (daily rate); window = past days (e.g. 7 for past week)."""
    if not history:
        return 0.0
    window = min(window, len(history))
    if window <= 0:
        return 0.0
    return sum(history[-window:]) / window


def forecast_demand(consumption_history: List[dict], method: str = "exponential_smoothing") -> float:
    """Forecast demand for the next 1 week: expected daily demand rate based on past 1 week of consumption.
    consumption_history should be the last 7 days. Return value = daily rate; next-week total = rate * 7."""
    if not consumption_history:
        return 0.0
    
    # Use only the most recent FORECAST_PAST_DAYS days
    recent = consumption_history[:FORECAST_PAST_DAYS]
    consumptions = [float(row.get('quantity_consumed', 0)) for row in recent if row.get('quantity_consumed') is not None]
    
    if not consumptions:
        return 0.0
    
    # Reverse to chronological order (oldest first) for exponential smoothing
    consumptions.reverse()
    
    if method == "exponential_smoothing":
        return exponential_smoothing(consumptions)
    elif method == "moving_average":
        return moving_average(consumptions, window=FORECAST_PAST_DAYS)
    else:
        return moving_average(consumptions, window=FORECAST_PAST_DAYS)


# -----------------------------------------------------------------------------
# Graph nodes (each returns a partial state update)
# -----------------------------------------------------------------------------


def receive_event(state: InventoryAgentState) -> dict:
    """Normalize and validate incoming event; fetch item data from DB."""
    inventory_id = state.get("inventory_id") or ""
    event_type = state.get("event_type") or "unknown"
    remaining = state.get("remaining_stock")
    
    # Fetch item data from PostgreSQL
    item_data = fetch_inventory_item(inventory_id) if inventory_id else None
    
    # If remaining_stock not provided, calculate it
    if remaining is None and inventory_id:
        remaining = calculate_current_stock(inventory_id)
    
    # Fetch consumption history: past 1 week for demand forecast (next 1 week)
    consumption_history = fetch_consumption_history(inventory_id, days=FORECAST_PAST_DAYS) if inventory_id else []
    
    is_valid = bool(inventory_id and event_type and remaining is not None and item_data)
    
    return {
        "inventory_id": inventory_id,
        "event_type": event_type,
        "remaining_stock": remaining,
        "item_data": item_data or {},
        "consumption_history": consumption_history,
        "is_valid": is_valid,
    }


def check_stock(state: InventoryAgentState) -> dict:
    """Check stock levels against thresholds and generate stock signals."""
    remaining = state.get("remaining_stock") or 0
    item_data = state.get("item_data", {})
    min_stock = item_data.get("min_stock") or state.get("context", {}).get("min_stock", 10)
    max_capacity = item_data.get("max_capacity") or state.get("context", {}).get("max_capacity", 1000)
    
    # Determine stock signal
    if remaining <= 0:
        stock_signal = "critical"
        suggested_action = "reorder"
    elif remaining < min_stock:
        stock_signal = "low"
        suggested_action = "reorder"
    elif remaining >= max_capacity * 0.9:
        stock_signal = "high"
        suggested_action = "hold"
    else:
        stock_signal = "normal"
        suggested_action = "none"
    
    return {
        "stock_signal": stock_signal,
        "suggested_action": suggested_action,
    }


def suggest_action(state: InventoryAgentState) -> dict:
    """Analyze consumption patterns and forecast demand to refine action suggestion."""
    consumption_history = state.get("consumption_history", [])
    remaining_stock = state.get("remaining_stock", 0)
    item_data = state.get("item_data", {})
    min_stock = item_data.get("min_stock", 10)
    
    # Forecast demand
    forecasted_demand = forecast_demand(consumption_history, method="exponential_smoothing")
    
    # Analyze consumption signal
    if consumption_history:
        recent_consumptions = [float(h.get('quantity_consumed', 0)) for h in consumption_history[:7]]
        avg_recent = sum(recent_consumptions) / len(recent_consumptions) if recent_consumptions else 0
        if avg_recent > forecasted_demand * 1.5:
            consumption_signal = "high"
        elif avg_recent < forecasted_demand * 0.5:
            consumption_signal = "low"
        else:
            consumption_signal = "normal"
    else:
        consumption_signal = "normal"
    
    # Refine action based on forecast and consumption
    current_action = state.get("suggested_action", "none")
    stock_signal = state.get("stock_signal", "normal")
    
    # If consumption is high and stock is low, prioritize reorder
    if consumption_signal == "high" and stock_signal in ["low", "critical"]:
        suggested_action = "reorder"
    # If forecasted demand exceeds current stock, suggest reorder
    elif forecasted_demand > remaining_stock and remaining_stock < min_stock * 1.5:
        suggested_action = "reorder"
    else:
        suggested_action = current_action
    
    return {
        "forecasted_demand": forecasted_demand,
        "consumption_signal": consumption_signal,
        "suggested_action": suggested_action,
    }


def notify_decision_agent(state: InventoryAgentState) -> dict:
    """Send event and suggestion to Decision Orchestration Agent with full context."""
    if not state.get("is_valid"):
        return {"decision_agent_response": {"skipped": True, "reason": "invalid_event"}}

    payload = {
        "inventory_id": state.get("inventory_id"),
        "event_type": state.get("event_type"),
        "remaining_stock": state.get("remaining_stock"),
        "suggested_action": state.get("suggested_action"),
        "stock_signal": state.get("stock_signal"),
        "consumption_signal": state.get("consumption_signal"),
        "forecasted_demand": state.get("forecasted_demand"),
        "item_data": state.get("item_data", {}),
        "consumption_history": state.get("consumption_history", [])[:10],  # Last 10 records
        "context": state.get("context") or {},
        "timestamp": datetime.now().isoformat(),
    }
    try:
        r = requests.post(DECISION_AGENT_URL, json=payload, timeout=10)
        decision_agent_response = r.json() if r.ok else {"status_code": r.status_code, "text": r.text}
    except Exception as e:
        logger.exception("Failed to notify decision agent")
        decision_agent_response = {"error": str(e)}

    return {"decision_agent_response": decision_agent_response}


def route_after_receive(state: InventoryAgentState) -> Literal["check_stock", "notify_decision_agent"]:
    """Route: if valid, go to check_stock; else skip to notify (which will skip the call)."""
    return "check_stock" if state.get("is_valid") else "notify_decision_agent"


# -----------------------------------------------------------------------------
# Build and compile the graph
# -----------------------------------------------------------------------------


def build_inventory_graph() -> StateGraph:
    """Build the inventory agent StateGraph and return the compiled graph."""
    builder = StateGraph(InventoryAgentState)

    builder.add_node("receive_event", receive_event)
    builder.add_node("check_stock", check_stock)
    builder.add_node("suggest_action", suggest_action)
    builder.add_node("notify_decision_agent", notify_decision_agent)

    builder.add_edge(START, "receive_event")
    builder.add_conditional_edges("receive_event", route_after_receive)
    builder.add_edge("check_stock", "suggest_action")
    builder.add_edge("suggest_action", "notify_decision_agent")
    builder.add_edge("notify_decision_agent", END)

    return builder.compile()


# Compiled graph (singleton)
_inventory_graph = None


def get_inventory_graph():
    """Return the compiled LangGraph inventory graph."""
    global _inventory_graph
    if _inventory_graph is None:
        _inventory_graph = build_inventory_graph()
    return _inventory_graph


# -----------------------------------------------------------------------------
# Continuous Monitoring Thread
# -----------------------------------------------------------------------------


def monitor_inventory_continuously():
    """Continuously monitor inventory and signal flagged items."""
    logger.info("Starting continuous inventory monitoring...")
    
    while True:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Fetch all inventory items
            cur.execute("SELECT inventory_id FROM inventory")
            inventory_ids = [row['inventory_id'] for row in cur.fetchall()]
            cur.close()
            conn.close()
            
            flagged_items = []
            
            for inventory_id in inventory_ids:
                try:
                    # Calculate current stock
                    current_stock = calculate_current_stock(inventory_id)
                    if current_stock is None:
                        continue
                    
                    # Fetch item data
                    item_data = fetch_inventory_item(inventory_id)
                    if not item_data:
                        continue
                    
                    min_stock = item_data.get("min_stock", 10)
                    
                    # Check if item needs attention
                    if current_stock < min_stock:
                        # Fetch consumption history
                        consumption_history = fetch_consumption_history(inventory_id, days=FORECAST_PAST_DAYS)
                        
                        # Create event state
                        initial_state: InventoryAgentState = {
                            "inventory_id": inventory_id,
                            "event_type": "low_stock",
                            "remaining_stock": current_stock,
                            "item_data": item_data,
                            "consumption_history": consumption_history,
                            "context": {},
                        }
                        
                        # Run through graph
                        graph = get_inventory_graph()
                        final_state = graph.invoke(initial_state)
                        
                        if final_state.get("is_valid") and final_state.get("suggested_action") != "none":
                            flagged_items.append({
                                "inventory_id": inventory_id,
                                "item_name": item_data.get("item_name"),
                                "current_stock": current_stock,
                                "min_stock": min_stock,
                                "suggested_action": final_state.get("suggested_action"),
                                "stock_signal": final_state.get("stock_signal"),
                                "forecasted_demand": final_state.get("forecasted_demand"),
                            })
                            logger.info(f"Flagged item: {inventory_id} ({item_data.get('item_name')}) - {final_state.get('suggested_action')}")
                
                except Exception as e:
                    logger.error(f"Error processing inventory item {inventory_id}: {e}")
                    continue
            
            if flagged_items:
                logger.info(f"Found {len(flagged_items)} flagged items")
            
            # Sleep before next monitoring cycle
            time.sleep(MONITORING_INTERVAL)
        
        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
            time.sleep(MONITORING_INTERVAL)


# -----------------------------------------------------------------------------
# MCP Tools
# -----------------------------------------------------------------------------


@mcp.tool()
def check_inventory_status(inventory_id: str) -> dict:
    """Check the current status of an inventory item."""
    item_data = fetch_inventory_item(inventory_id)
    if not item_data:
        return {"error": f"Inventory item {inventory_id} not found"}
    
    current_stock = calculate_current_stock(inventory_id)
    consumption_history = fetch_consumption_history(inventory_id, days=FORECAST_PAST_DAYS)
    forecasted_demand = forecast_demand(consumption_history)
    forecast_next_week_total = round(forecasted_demand * FORECAST_NEXT_WEEK_DAYS, 2)
    
    return {
        "inventory_id": inventory_id,
        "item_name": item_data.get("item_name"),
        "current_stock": current_stock,
        "min_stock": item_data.get("min_stock"),
        "max_capacity": item_data.get("max_capacity"),
        "forecasted_demand": forecasted_demand,
        "forecast_next_week_total": forecast_next_week_total,
        "forecast_based_on_past_days": FORECAST_PAST_DAYS,
        "consumption_history_count": len(consumption_history),
    }


@mcp.tool()
def signal_inventory_item(inventory_id: str, event_type: str = "low_stock") -> dict:
    """Manually signal an inventory item for processing."""
    initial_state: InventoryAgentState = {
        "inventory_id": inventory_id,
        "event_type": event_type,
        "remaining_stock": None,  # Will be calculated
        "context": {},
    }
    
    graph = get_inventory_graph()
    final_state = graph.invoke(initial_state)
    
    return {
        "inventory_id": inventory_id,
        "is_valid": final_state.get("is_valid"),
        "suggested_action": final_state.get("suggested_action"),
        "stock_signal": final_state.get("stock_signal"),
        "forecasted_demand": final_state.get("forecasted_demand"),
        "decision_agent_response": final_state.get("decision_agent_response"),
    }


# -----------------------------------------------------------------------------
# HTTP API (Flask)
# -----------------------------------------------------------------------------

app = Flask(__name__)


@app.route("/inventory", methods=["POST"])
def inventory_event():
    """Accept an inventory event, run the LangGraph pipeline, return final state."""
    payload = request.get_json(silent=True) or {}
    logger.info("Received inventory event: %s", payload)

    initial_state: InventoryAgentState = {
        "inventory_id": payload.get("inventory_id", ""),
        "event_type": payload.get("event_type", ""),
        "quantity": payload.get("quantity", 0),
        "remaining_stock": payload.get("remaining_stock"),
        "context": payload.get("context", {}),
    }

    graph = get_inventory_graph()
    final_state = graph.invoke(initial_state)

    return jsonify({
        "result": {
            "decision_agent_response": final_state.get("decision_agent_response"),
            "suggested_action": final_state.get("suggested_action"),
            "stock_signal": final_state.get("stock_signal"),
            "consumption_signal": final_state.get("consumption_signal"),
            "forecasted_demand": final_state.get("forecasted_demand"),
            "is_valid": final_state.get("is_valid"),
        },
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "agent": "inventory"}), 200


@app.route("/monitor/start", methods=["POST"])
def start_monitoring():
    """Start continuous monitoring (if not already running)."""
    # Check if monitoring thread is already running
    for thread in threading.enumerate():
        if thread.name == "inventory_monitor":
            return jsonify({"status": "already_running"}), 200
    
    monitor_thread = threading.Thread(target=monitor_inventory_continuously, name="inventory_monitor", daemon=True)
    monitor_thread.start()
    return jsonify({"status": "started"}), 200


@app.route("/monitor/status", methods=["GET"])
def monitor_status():
    """Check if monitoring is running."""
    is_running = any(t.name == "inventory_monitor" and t.is_alive() for t in threading.enumerate())
    return jsonify({"monitoring": is_running}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9005"))
    
    # Start monitoring thread
    monitor_thread = threading.Thread(target=monitor_inventory_continuously, name="inventory_monitor", daemon=True)
    monitor_thread.start()
    
    # Run Flask app
    app.run(host="0.0.0.0", port=port, debug=True)
