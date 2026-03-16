"""Chat Agent – Orchestrator that handles conversational queries, checks inventory, calls decision agent, and stores suggestions."""
import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import date, datetime
from urllib.parse import quote_plus

import json

# Single source of demand forecast: ETS only (same as Inventory Agent)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from common.forecasting import forecast_demand as forecast_demand_ets
from common.expiry import days_until_expiry as days_until_expiry_fn
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from langchain_core.prompts import ChatPromptTemplate
from langchain_mistralai import ChatMistralAI
from fastmcp import FastMCP
import asyncio
import threading
from fastmcp import Client as McpClient

# Load environment variables from .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chat-agent")

# Configuration
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-medium")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "smartcart_ai")
DB_USER = os.getenv("DB_USER", "meghanarendrasimha")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Welcome@123")
DECISION_ORCHESTRATOR_URL = os.getenv("DECISION_ORCHESTRATOR_URL", "http://localhost:9000")
INVENTORY_AGENT_URL = os.getenv("INVENTORY_AGENT_URL", "http://localhost:9005")
FOOD_BANK_AGENT_URL = os.getenv("FOOD_BANK_AGENT_URL", "http://localhost:9007")
CHAT_HUMANIZE = os.getenv("CHAT_HUMANIZE", "false").strip().lower() in ("1", "true", "yes", "y", "on")
AGENT_SHARED_TOKEN = os.getenv("AGENT_SHARED_TOKEN", "")

mcp = FastMCP("Chat Agent")

# Initialize Mistral LLM
llm = None
if MISTRAL_API_KEY:
    try:
        llm = ChatMistralAI(model=MISTRAL_MODEL, mistral_api_key=MISTRAL_API_KEY)
        logger.info("Mistral LLM initialized for chat")
    except Exception as e:
        logger.warning(f"Failed to initialize Mistral LLM: {e}. Chat will have limited functionality.")


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


def get_near_expiry_items(within_days: int = 14) -> List[Dict]:
    """Get expired or near-expiry items (expiry_date in the past or within within_days). Top priority: expired first, then soonest to expire."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            # Include expired (expiry_date < today) and near-expiry (up to within_days ahead); order so expired first, then soonest
            cur.execute("""
                SELECT inventory_id, item_name, category, form, usage, item_type,
                       opening_stock as remaining_stock, min_stock, max_capacity,
                       vendor_id, expiry_date, selling_price
                FROM inventory
                WHERE expiry_date IS NOT NULL
                  AND expiry_date <= CURRENT_DATE + INTERVAL '1 day' * %s
                ORDER BY expiry_date ASC
                LIMIT 50
            """, (within_days,))
        except Exception:
            conn.rollback()
            cur.execute("""
                SELECT inventory_id, item_name, category, opening_stock as remaining_stock,
                       min_stock, max_capacity, vendor_id
                FROM inventory
                LIMIT 0
            """)
        items = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return items
    except Exception as e:
        logger.error(f"Error getting near-expiry items: {e}")
        return []


def get_items_by_name(search: str) -> List[Dict]:
    """Get inventory items whose name contains the search term (e.g. 'apple')."""
    if not search or not search.strip():
        return []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        pattern = f"%{search.strip()}%"
        try:
            cur.execute("""
                SELECT inventory_id, item_name, category, form, usage, item_type,
                       opening_stock as remaining_stock, min_stock, max_capacity,
                       vendor_id, expiry_date, selling_price
                FROM inventory
                WHERE item_name ILIKE %s
                ORDER BY opening_stock ASC
                LIMIT 20
            """, (pattern,))
        except Exception:
            conn.rollback()
            cur.execute("""
                SELECT inventory_id, item_name, category, opening_stock as remaining_stock,
                       min_stock, max_capacity, vendor_id
                FROM inventory
                WHERE item_name ILIKE %s
                ORDER BY opening_stock ASC
                LIMIT 20
            """, (pattern,))
        items = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return items
    except Exception as e:
        logger.error(f"Error getting items by name: {e}")
        return []


def call_inventory_agent_query(query: str) -> Tuple[List[Dict], Optional[str], Optional[str]]:
    """
    Call the Inventory Agent with the user query. Inventory Agent sees the DB
    (low stock, expired, near expiring, waste, etc.) and returns matching items.
    Returns (items_list, error_message, query_type). On success error_message is None.
    query_type is e.g. "near_expiry", "low_stock", "check" so Chat can show the right empty message.
    """
    try:
        headers = {"X-Agent-Token": AGENT_SHARED_TOKEN} if AGENT_SHARED_TOKEN else None
        response = requests.post(
            f"{INVENTORY_AGENT_URL}/query",
            json={"query": query},
            headers=headers,
            timeout=10,
        )
        if not response.ok:
            return [], f"Inventory agent returned {response.status_code}", None
        data = response.json()
        items = data.get("items") or []
        query_type = data.get("query_type") or None
        return items, None, query_type
    except requests.exceptions.ConnectionError:
        return [], "Inventory agent not reachable (is it running on port 9005?)", None
    except requests.exceptions.Timeout:
        return [], "Inventory agent timed out", None
    except Exception as e:
        return [], str(e)[:120], None


def get_out_of_stock_items(limit: int = 10) -> List[Dict]:
    """Get items with zero or negative stock (out of stock)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT inventory_id, item_name, category, item_type, opening_stock as remaining_stock,
                       min_stock, max_capacity, vendor_id, expiry_date, selling_price
                FROM inventory
                WHERE opening_stock <= 0
                ORDER BY opening_stock ASC
                LIMIT %s
            """, (limit,))
        except Exception:
            conn.rollback()
            cur.execute("""
                SELECT inventory_id, item_name, category, opening_stock as remaining_stock,
                       min_stock, max_capacity, vendor_id
                FROM inventory
                WHERE opening_stock <= 0
                ORDER BY opening_stock ASC
                LIMIT %s
            """, (limit,))
        items = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return items
    except Exception as e:
        logger.error(f"Error getting out-of-stock items: {e}")
        return []


def get_overstock_items(limit: int = 10) -> List[Dict]:
    """Get items with stock at or above 90%% of max_capacity (overstock)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT inventory_id, item_name, category, item_type, opening_stock as remaining_stock,
                       min_stock, max_capacity, vendor_id, expiry_date, selling_price
                FROM inventory
                WHERE max_capacity IS NOT NULL AND max_capacity > 0
                  AND opening_stock >= max_capacity * 0.9
                ORDER BY opening_stock DESC
                LIMIT %s
            """, (limit,))
        except Exception:
            conn.rollback()
            cur.execute("""
                SELECT inventory_id, item_name, category, opening_stock as remaining_stock,
                       min_stock, max_capacity, vendor_id
                FROM inventory
                WHERE max_capacity IS NOT NULL AND max_capacity > 0
                  AND opening_stock >= max_capacity * 0.9
                ORDER BY opening_stock DESC
                LIMIT %s
            """, (limit,))
        items = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return items
    except Exception as e:
        logger.error(f"Error getting overstock items: {e}")
        return []


def get_perishable_items(limit: int = 30) -> List[Dict]:
    """Return perishable items from inventory (DB-authoritative, with robust classification)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT inventory_id, item_name, category, form, usage, item_type,
                   opening_stock as remaining_stock, min_stock, max_capacity,
                   vendor_id, expiry_date, selling_price
            FROM inventory
            ORDER BY item_name ASC
            LIMIT %s
            """,
            (max(limit * 3, 60),),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        out = []
        for r in rows:
            combined = " ".join([
                str(r.get("item_type") or ""),
                str(r.get("category") or ""),
                str(r.get("usage") or ""),
            ]).strip().lower()
            if not combined:
                continue
            if any(tok in combined for tok in ("non-perishable", "non perishable", "nonperishable")):
                continue
            if "perishable" in combined:
                out.append(r)
        return out[:limit]
    except Exception as e:
        logger.error(f"Error getting perishable items: {e}")
        return []


def get_non_perishable_items(limit: int = 30) -> List[Dict]:
    """Return non-perishable items from inventory (DB-authoritative)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT inventory_id, item_name, category, form, usage, item_type,
                   opening_stock as remaining_stock, min_stock, max_capacity,
                   vendor_id, expiry_date, selling_price
            FROM inventory
            ORDER BY item_name ASC
            LIMIT %s
            """,
            (max(limit * 3, 60),),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        out = []
        for r in rows:
            combined = " ".join([
                str(r.get("item_type") or ""),
                str(r.get("category") or ""),
                str(r.get("usage") or ""),
            ]).strip().lower()
            if not combined:
                continue
            if any(tok in combined for tok in ("non-perishable", "non perishable", "nonperishable")):
                out.append(r)
                continue
            # Defensive: if explicitly tagged perishable, do not classify as non-perishable.
            if "perishable" in combined:
                continue
        return out[:limit]
    except Exception as e:
        logger.error(f"Error getting non-perishable items: {e}")
        return []


def get_sales_last_week(item_name: str, limit: int = 20) -> List[Dict]:
    """Return last-7-days sales rows and aggregates for inventory items matching name.
    "Last week" is computed from latest available sales date in DB, not wall-clock date.
    """
    if not item_name or not item_name.strip():
        return []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            WITH matched_items AS (
              SELECT i.inventory_id, i.item_name
              FROM inventory i
              WHERE i.item_name ILIKE %s
            ),
            latest_per_item AS (
              SELECT s.inventory_id, MAX(s.purchase_date)::date AS max_purchase_date
              FROM sales s
              JOIN matched_items m ON m.inventory_id = s.inventory_id
              GROUP BY s.inventory_id
            )
            SELECT
              m.inventory_id,
              m.item_name,
              COUNT(s.invoice_id) AS sales_rows,
              COALESCE(SUM(s.quantity), 0) AS total_quantity,
              COALESCE(AVG(s.unit_cost), 0) AS avg_unit_cost,
              COALESCE(SUM(s.total_cost), 0) AS total_cost
            FROM matched_items m
            LEFT JOIN latest_per_item lp
              ON lp.inventory_id = m.inventory_id
            LEFT JOIN sales s
              ON s.inventory_id = m.inventory_id
             AND lp.max_purchase_date IS NOT NULL
             AND s.purchase_date >= lp.max_purchase_date - INTERVAL '6 day'
             AND s.purchase_date <= lp.max_purchase_date
            GROUP BY m.inventory_id, m.item_name
            ORDER BY total_quantity DESC, m.item_name ASC
            LIMIT %s
            """,
            (f"%{item_name.strip()}%", limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Error getting sales data for '{item_name}': {e}")
        return []


def get_demand_ranked_items(high: bool = True, limit: Optional[int] = None) -> List[Dict]:
    """Return items ranked by latest DB demand prediction (high or low)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        order = "DESC" if high else "ASC"
        demand_filter = "l.predicted_demand >= t.p70" if high else "l.predicted_demand < t.p70"
        query = f"""
            WITH latest AS (
              SELECT DISTINCT ON (d.inventory_id) d.inventory_id, d.predicted_demand
              FROM demand d
              WHERE d.predicted_demand IS NOT NULL
              ORDER BY d.inventory_id, d.prediction_date DESC, d.demand_id DESC
            ),
            thr AS (
              SELECT percentile_cont(0.70) WITHIN GROUP (ORDER BY predicted_demand) AS p70
              FROM latest
            )
            SELECT i.inventory_id, i.item_name, i.item_type, i.expiry_date, i.opening_stock as remaining_stock,
                   i.min_stock, i.selling_price, l.predicted_demand as forecasted_demand
            FROM latest l
            JOIN inventory i ON i.inventory_id = l.inventory_id
            CROSS JOIN thr t
            WHERE t.p70 IS NOT NULL AND {demand_filter}
            ORDER BY l.predicted_demand {order}, i.item_name ASC
            """
        params: Tuple = ()
        if limit is not None and int(limit) > 0:
            query += "\nLIMIT %s"
            params = (int(limit),)
        cur.execute(query, params)
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Error getting demand-ranked items: {e}")
        return []


def get_price_increase_candidates(limit: int = 30) -> List[Dict]:
    """Candidates for price increase: high demand and not near expiry."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            WITH latest AS (
              SELECT DISTINCT ON (d.inventory_id) d.inventory_id, d.predicted_demand
              FROM demand d
              WHERE d.predicted_demand IS NOT NULL
              ORDER BY d.inventory_id, d.prediction_date DESC, d.demand_id DESC
            ),
            thr AS (
              SELECT percentile_cont(0.70) WITHIN GROUP (ORDER BY predicted_demand) AS p70
              FROM latest
            )
            SELECT i.inventory_id, i.item_name, i.category, i.form, i.usage, i.item_type,
                   i.opening_stock as remaining_stock, i.min_stock, i.max_capacity,
                   i.vendor_id, i.expiry_date, i.selling_price, l.predicted_demand as forecasted_demand
            FROM inventory i
            JOIN latest l ON l.inventory_id = i.inventory_id
            CROSS JOIN thr t
            WHERE t.p70 IS NOT NULL
              AND l.predicted_demand >= t.p70
              AND (i.expiry_date IS NULL OR i.expiry_date > CURRENT_DATE + INTERVAL '14 day')
              AND COALESCE(i.opening_stock, 0) > COALESCE(i.min_stock, 0)
            ORDER BY l.predicted_demand DESC, i.item_name ASC
            LIMIT %s
            """,
            (limit,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"Error getting price increase candidates: {e}")
        return []


def get_items_needing_attention(query: str) -> List[Dict]:
    """Get inventory items that need attention based on the query."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        query_lower = query.lower()
        
        # Determine what items to check based on query
        sel_ext = "SELECT inventory_id, item_name, category, form, \"use\", opening_stock as remaining_stock, min_stock, max_capacity, vendor_id, expiry_date, selling_price FROM inventory"
        sel_base = "SELECT inventory_id, item_name, category, opening_stock as remaining_stock, min_stock, max_capacity, vendor_id FROM inventory"
        if any(word in query_lower for word in ["low stock", "low in stock", "reorder", "suggest", "recommend"]):
            q = " WHERE opening_stock <= min_stock ORDER BY opening_stock ASC LIMIT 20"
        elif any(word in query_lower for word in ["all", "everything", "check"]):
            q = " ORDER BY opening_stock ASC LIMIT 20"
        else:
            q = " WHERE opening_stock <= min_stock ORDER BY opening_stock ASC LIMIT 10"
        try:
            cur.execute(sel_ext + q)
        except Exception:
            conn.rollback()
            cur.execute(sel_base + q)
        items = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return items
    except Exception as e:
        logger.error(f"Error getting items: {e}")
        return []


# Demand forecast window (default 7; can be overridden via env and shared common.forecasting)
try:
    from common.forecasting import FORECAST_PAST_DAYS as _FORECAST_PAST_DAYS
except Exception:
    _FORECAST_PAST_DAYS = 7
FORECAST_PAST_DAYS = int(os.getenv("FORECAST_PAST_DAYS", str(_FORECAST_PAST_DAYS)))
FORECAST_NEXT_WEEK_DAYS = 7


def _serialize_date(val):
    """Return ISO date string or None for payloads."""
    if val is None:
        return None
    if hasattr(val, "isoformat"):
        return val.isoformat()
    return str(val)[:10]


def strip_markdown(text: str) -> str:
    """Remove markdown so chat and suggestion tab show plain text."""
    if not text or not isinstance(text, str):
        return text
    import re
    s = text
    s = re.sub(r'\*\*([^*]+)\*\*', r'\1', s)
    s = re.sub(r'\*([^*]+)\*', r'\1', s)
    s = re.sub(r'^#+\s*', '', s, flags=re.MULTILINE)
    s = re.sub(r'__([^_]+)__', r'\1', s)
    s = re.sub(r'_([^_]+)_', r'\1', s)
    return s.strip()


def get_consumption_history(inventory_id: str, last_n_days: int = FORECAST_PAST_DAYS) -> List[Dict]:
    """Get consumption history for an item (default: past 1 week for demand forecast).
    Tries schema column 'date' first (schema.sql), then 'transaction_date' for compatibility."""
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT date, quantity_consumed, remaining_stock, department, consumption_reason
                FROM consumption
                WHERE inventory_id = %s AND date >= CURRENT_DATE - INTERVAL '1 day' * %s
                ORDER BY date DESC
            """, (inventory_id, last_n_days))
        except Exception:
            conn.rollback()  # required after failed query so next execute doesn't get "transaction is aborted"
            cur.execute("""
                SELECT transaction_date as date, quantity_consumed, remaining_stock, department, consumption_reason
                FROM consumption
                WHERE inventory_id = %s AND transaction_date >= CURRENT_DATE - INTERVAL '1 day' * %s
                ORDER BY transaction_date DESC
            """, (inventory_id, last_n_days))
        history = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return history
    except Exception as e:
        logger.error(f"Error getting consumption history: {e}")
        try:
            if conn is not None:
                conn.rollback()
        except Exception:
            pass
        return []


def get_demand_floor(inventory_id: str) -> float:
    """Return daily demand floor from demand table so DB can boost forecasted demand."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT predicted_demand FROM demand
            WHERE inventory_id = %s
            ORDER BY prediction_date DESC NULLS LAST
            LIMIT 1
        """, (inventory_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row.get("predicted_demand") is not None:
            return float(row["predicted_demand"])
    except Exception as e:
        logger.debug(f"Demand floor not available for {inventory_id}: {e}")
    return 0.0


def calculate_forecasted_demand(consumption_history: List[Dict]) -> float:
    """Forecast demand using ETS (Holt-Winters) only – same as Inventory Agent and common.forecasting."""
    return forecast_demand_ets(consumption_history)


def _extract_product_name_from_query(query_lower: str) -> Optional[str]:
    """Extract product name for stock/demand lookup: 'stock for honey' -> 'honey', 'tock for Apple' (typo) -> 'apple'."""
    if not query_lower or len(query_lower) > 200:
        return None
    name_part = None
    if "stock for " in query_lower:
        name_part = query_lower.split("stock for ", 1)[-1].strip()
    elif "tock for " in query_lower:  # typo: "tock" -> "stock"
        name_part = query_lower.split("tock for ", 1)[-1].strip()
    elif "forecast demand for " in query_lower:
        name_part = query_lower.split("forecast demand for ", 1)[-1].strip()
    elif "demand for " in query_lower:
        name_part = query_lower.split("demand for ", 1)[-1].strip()
    elif "sales for " in query_lower:
        name_part = query_lower.split("sales for ", 1)[-1].strip()
    elif "last week sales for " in query_lower:
        name_part = query_lower.split("last week sales for ", 1)[-1].strip()
    elif query_lower.strip().startswith("for "):
        name_part = query_lower.replace("for ", "", 1).strip()
    if name_part:
        name_part = name_part.rstrip("?.!,")
        # Single-word "for X" -> keep one word; "stock for X" / "demand for X" -> keep full phrase for filtering
        if query_lower.strip().startswith("for ") and " " in name_part:
            name_part = name_part.split()[0]
    return name_part if (name_part and len(name_part) < 50) else None


def _build_orchestrator_payload(item: Dict, user_asked_about_waste: bool, intent: str = "general", waste_action_preference: Optional[str] = None) -> Dict:
    """Build a single item payload for /orchestrate. Pass intent so orchestrator calls only relevant subagents and returns one recommended_action per item."""
    consumption_history = get_consumption_history(item['inventory_id'])
    if item.get('forecasted_demand') is not None:
        forecasted_demand = float(item['forecasted_demand'])
    else:
        forecasted_demand = calculate_forecasted_demand(consumption_history)
    demand_floor = get_demand_floor(item['inventory_id'])
    if demand_floor > 0:
        forecasted_demand = max(forecasted_demand, demand_floor)
    if forecasted_demand <= 0:
        forecasted_demand = None
    remaining_stock = item.get('remaining_stock', 0)
    min_stock = item.get('min_stock')
    if remaining_stock <= 0:
        stock_signal = "critical"
    elif min_stock is not None and remaining_stock < min_stock:
        stock_signal = "low"
    else:
        stock_signal = "normal"
    # Pricing intent uses waste path (donation + feasibility) for discount/price_increase %; need user_asked_about_waste so synthesize runs rule engine
    if user_asked_about_waste or intent == "pricing":
        context = {"user_asked_about_waste": True, "intent": intent if intent == "pricing" else "waste", "fast_mode": True}
        if waste_action_preference:
            context["waste_action_preference"] = waste_action_preference
        event_type, suggested_action = "near_expiry", "none"
    else:
        event_type = "low_stock" if stock_signal != "normal" else "monitoring"
        suggested_action = "reorder" if stock_signal != "normal" else "none"
        context = {"intent": intent}
    return {
        "inventory_id": item['inventory_id'],
        "event_type": event_type,
        "remaining_stock": remaining_stock,
        "suggested_action": suggested_action,
        "stock_signal": stock_signal,
        "consumption_signal": "normal",
        "forecasted_demand": forecasted_demand,
        "item_data": {
            "item_name": item.get('item_name'),
            "category": item.get('category'),
            "form": item.get('form'),
            "use": item.get('usage'),
            "usage": item.get('usage'),
            "item_type": item.get('item_type'),
            "min_stock": min_stock,
            "max_capacity": item.get('max_capacity', 1000),
            "vendor_id": item.get('vendor_id'),
            "expiry_date": _serialize_date(item.get('expiry_date') or item.get('expiryDate')),
            "selling_price": float(item.get('selling_price')) if item.get('selling_price') is not None else None,
        },
        "consumption_history": consumption_history[:10],
        "context": context,
    }


def call_decision_orchestrator_batch(items: List[Dict], user_asked_about_waste: bool, intent: str = "general", waste_action_preference: Optional[str] = None) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """Call /orchestrate once per item; collect responses. All orchestration uses single-item endpoint only. Filter by recommended_action in caller."""
    if not items:
        return [], None
    # Same limit as before: process up to 8 items per "batch" (now N sequential /orchestrate calls)
    batch_items = items[:8]
    payload_intent = intent if intent == "pricing" else ("waste" if user_asked_about_waste else intent)
    recs = []
    workers = min(
        len(batch_items),
        max(1, int(os.getenv("CHAT_ORCHESTRATOR_BATCH_WORKERS", "4"))),
    )

    last_error: List[str] = []  # thread-safe: append only

    def _call_one(it: Dict) -> Optional[Dict]:
        payload = _build_orchestrator_payload(
            it,
            user_asked_about_waste or intent == "pricing",
            intent=payload_intent,
            waste_action_preference=waste_action_preference,
        )
        try:
            data = _call_orchestrator_mcp(payload)
            rec = data.get("recommendation", {})
            item_name = (payload.get("item_data") or {}).get("item_name", "Item")
            logger.info("Orchestrate item=%s recommended_action=%s", item_name, rec.get("action", ""))
            return {
                "inventory_id": payload.get("inventory_id", ""),
                "item_name": item_name,
                "recommendation": rec,
                "risk_assessment": data.get("risk_assessment", {}),
                "feasibility_check": data.get("feasibility_check", {}),
                "cost_impact": data.get("cost_impact", {}),
                "explanation": data.get("explanation", {}),
            }
        except requests.exceptions.Timeout:
            msg = "Orchestrator timed out."
            logger.warning("Orchestrate timeout for item %s", it.get("item_name"))
            last_error.append(msg)
            return None
        except requests.exceptions.ConnectionError as e:
            msg = "Orchestrator not reachable (is it running on port 9000 or 9100?)."
            logger.error("Orchestrate connection failed for item %s: %s", it.get("item_name"), e)
            last_error.append(msg)
            return None
        except Exception as e:
            err_str = str(e).strip()[:200]
            logger.error("Orchestrate failed for item %s: %s", it.get("item_name"), e)
            # Surface Mistral / auth / API errors to the user
            if "401" in err_str or "unauthorized" in err_str.lower() or "api_key" in err_str.lower() or "mistral" in err_str.lower():
                last_error.append("Mistral API key invalid or missing. Set MISTRAL_API_KEY in the Decision Orchestrator .env (Agents/decision-orchestration-agent/.env).")
            elif "500" in err_str or "error" in err_str.lower():
                last_error.append(err_str or "Orchestrator or subagent error (check Mistral API key and that subagents are running).")
            else:
                last_error.append(err_str or "Orchestrator failed.")
            return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_call_one, it) for it in batch_items]
        for f in as_completed(futures):
            out = f.result()
            if out:
                recs.append(out)
    if batch_items and not recs:
        detail = last_error[-1] if last_error else "all items failed or service unavailable"
        base = "Could not get recommendations from orchestrator (" + detail + ")."
        if "mistral" not in detail.lower() and "api_key" not in detail.lower() and "not reachable" not in detail.lower():
            base += " Check MISTRAL_API_KEY in Agents/decision-orchestration-agent/.env and that the Decision Orchestrator (and subagents) are running."
        return None, base
    return recs, None


def call_decision_orchestrator(item: Dict, user_asked_about_waste: bool = False, intent: str = "general") -> Tuple[Optional[Dict], Optional[str]]:
    """Call the Decision Orchestrator Agent for an item. Pass intent so orchestrator runs only relevant subagents."""
    try:
        payload = _build_orchestrator_payload(item, user_asked_about_waste, intent=intent)
        return _call_orchestrator_mcp(payload), None
    except requests.exceptions.ConnectionError as e:
        err_msg = "Recommendation service is not reachable. Is the Decision Orchestrator running?"
        logger.error(f"Decision orchestrator connection failed: {e}")
        return None, err_msg
    except requests.exceptions.Timeout as e:
        err_msg = "Recommendation service timed out."
        logger.error(f"Decision orchestrator timeout: {e}")
        return None, err_msg
    except Exception as e:
        err_msg = str(e)[:150]
        logger.error(f"Error calling decision orchestrator: {e}")
        return None, err_msg


def _orchestrator_mcp_url() -> str:
    # Default orchestrator MCP endpoint (MCP-only orchestrator)
    return os.getenv("DECISION_ORCHESTRATOR_MCP_URL", "http://localhost:9100/mcp")


def _run_coro_sync(coro):
    """Run an async coroutine from sync code, even if we're already in an event loop.

    FastMCP tool handlers may execute inside an active asyncio event loop. In that case,
    asyncio.run() would raise: 'asyncio.run() cannot be called from a running event loop'.
    We avoid that by running the coroutine in a dedicated thread with its own event loop.
    """
    try:
        asyncio.get_running_loop()
        in_loop = True
    except RuntimeError:
        in_loop = False

    if not in_loop:
        return asyncio.run(coro)

    result = {"value": None, "error": None}

    def _worker():
        try:
            result["value"] = asyncio.run(coro)
        except Exception as e:
            result["error"] = e

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    t.join()
    if result["error"] is not None:
        raise result["error"]
    return result["value"]


def _call_orchestrator_http(payload: Dict) -> Dict:
    """Fallback: POST to Decision Orchestrator HTTP /orchestrate (e.g. port 9000)."""
    base = (DECISION_ORCHESTRATOR_URL or "").strip().rstrip("/")
    if not base or not base.startswith("http"):
        raise ValueError("DECISION_ORCHESTRATOR_URL not set or invalid")
    url = base + "/orchestrate"
    timeout = int(os.getenv("CHAT_ORCHESTRATOR_HTTP_TIMEOUT", "90"))
    r = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=timeout)
    if not r.ok:
        try:
            body = r.json()
            err = body.get("error", r.text[:300])
        except Exception:
            err = r.text[:300] if r.text else "HTTP %s" % r.status_code
        raise RuntimeError(err)
    data = r.json()
    # Normalize to same shape as MCP (backend may return { recommendation, ... } directly)
    if "recommendation" in data:
        return data
    return {"recommendation": data.get("recommendation", {}), "risk_assessment": data.get("risk_assessment", {}), "feasibility_check": data.get("feasibility_check", {}), "cost_impact": data.get("cost_impact", {}), "explanation": data.get("explanation", {})}


def _call_orchestrator_mcp(payload: Dict) -> Dict:
    """Call orchestrator via MCP (default 9100); on failure try HTTP /orchestrate (e.g. 9000)."""
    url = _orchestrator_mcp_url()

    async def _call():
        async with McpClient(url) as c:
            result = await c.call_tool("orchestrate", {"payload": payload})
            return result.data

    try:
        return _run_coro_sync(_call())
    except Exception as e:
        logger.warning("Orchestrator MCP failed (%s), trying HTTP fallback to %s", e, DECISION_ORCHESTRATOR_URL)
        try:
            return _call_orchestrator_http(payload)
        except Exception as http_err:
            logger.error("Orchestrator HTTP fallback failed: %s", http_err)
            raise


def save_suggestion(user_query: str, item: Dict, recommendation: Dict) -> Optional[int]:
    """Save a suggestion to the database."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        rec = recommendation.get('recommendation', {})
        risk = recommendation.get('risk_assessment', {})
        feasibility = recommendation.get('feasibility_check', {})
        cost = recommendation.get('cost_impact', {})
        explanation = recommendation.get('explanation', {})
        
        donation_info_val = None
        if rec.get('nearest_food_banks'):
            donation_info_val = json.dumps(rec.get('nearest_food_banks'))
        cur.execute("""
            INSERT INTO suggestions (
                inventory_id, item_name, user_query, action, priority, reasoning,
                expected_outcome, risk_level, risk_score, is_feasible,
                estimated_cost, within_budget, explanation, current_stock,
                min_stock, forecasted_demand, status, donation_info, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            RETURNING suggestion_id
        """, (
            item['inventory_id'],
            item.get('item_name'),
            user_query,
            rec.get('action', 'none'),
            rec.get('priority', 'Medium'),
            rec.get('reasoning', ''),
            rec.get('expected_outcome', ''),
            risk.get('risk_level', 'unknown'),
            risk.get('risk_score', 0),
            feasibility.get('is_feasible', True),
            cost.get('estimated_cost', 0),
            cost.get('within_budget', True),
            explanation.get('explanation', '') if isinstance(explanation, dict) else str(explanation),
            item.get('remaining_stock', 0),
            item.get('min_stock', 0),
            recommendation.get('forecasted_demand', 0.0),
            'pending',
            donation_info_val
        ))
        
        suggestion_id = cur.fetchone()['suggestion_id']
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Saved suggestion {suggestion_id} for item {item['inventory_id']}")
        return suggestion_id
    except Exception as e:
        logger.error(f"Error saving suggestion: {e}")
        return None


def _get_inventory_summary() -> Dict:
    """Get inventory summary (total items, total stock, low stock count)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT 
                COUNT(*) as total_items,
                COALESCE(SUM(opening_stock), 0) as total_stock,
                COUNT(CASE WHEN opening_stock <= min_stock THEN 1 END) as low_stock_count
            FROM inventory
        """)
        summary = dict(cur.fetchone())
        cur.close()
        conn.close()
        return summary
    except Exception as e:
        logger.error(f"Error getting inventory summary: {e}")
        return {"total_items": 0, "total_stock": 0, "low_stock_count": 0}


def _humanize_recommendation_answer(query: str, intent: str, answer_text: str) -> str:
    """Use LLM to polish recommendation responses for readability without changing decisions."""
    if not llm or not answer_text:
        return answer_text
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You rewrite inventory recommendation output for store managers.
Goals:
1) Keep all original recommendation facts intact (item names, action, percentages, prices, donation names, bundle pairings).
2) Improve readability and tone: plain, human, practical.
3) Use short sections in plain text only: Summary, Recommended actions, Why this matters.
4) Keep concise (max ~220 words).
5) No markdown symbols (**, #, tables). Plain text only."""),
            ("user", "User query: {query}\nIntent: {intent}\nRaw recommendation output:\n{answer_text}\n\nRewrite now."),
        ])
        chain = prompt | llm
        resp = chain.invoke({"query": query, "intent": intent, "answer_text": answer_text})
        rewritten = resp.content if hasattr(resp, "content") else str(resp)
        cleaned = strip_markdown(rewritten).strip()
        return cleaned or answer_text
    except Exception as e:
        logger.debug(f"Recommendation humanization skipped: {e}")
        return answer_text


def _humanize_chat_answer(query: str, intent: str, answer_text: str) -> str:
    """Make any chat answer more readable while preserving factual content."""
    if not llm or not answer_text:
        return answer_text
    try:
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Rewrite the assistant answer for a store manager so it is easy to read.
Rules:
1) Keep all facts exactly the same (item names, actions, quantities, percentages, prices, dates, food-bank names).
2) Do not invent or remove facts.
3) Use plain text only (no markdown symbols, no tables).
4) Keep concise and practical.
5) If there are multiple items, keep one item per line using a simple bullet like "- ".
6) If the answer is already clear, return it with only light cleanup."""),
            ("user", "User query: {query}\nIntent: {intent}\nAnswer:\n{answer_text}\n\nRewrite now."),
        ])
        chain = prompt | llm
        resp = chain.invoke({"query": query, "intent": intent, "answer_text": answer_text})
        rewritten = resp.content if hasattr(resp, "content") else str(resp)
        cleaned = strip_markdown(rewritten).strip()
        return cleaned or answer_text
    except Exception as e:
        logger.debug(f"General answer humanization skipped: {e}")
        return answer_text


def _format_recommendation_line(
    item_name: str,
    recommendation: Dict,
    include_reason: bool = True,
    item: Optional[Dict] = None,
    query_type: Optional[str] = None,
    no_expiry_hint: bool = False,
) -> str:
    """Format a single recommendation for chat: action plus full sentence reasoning."""
    rec = recommendation.get("recommendation", {})
    action = (rec.get("action") or "none").lower()
    priority = rec.get("priority", "Medium")
    reasoning = rec.get("reasoning", "") or ""
    reasoning_clean = " ".join(str(reasoning).split())

    def _with_period(text: str) -> str:
        text = (text or "").strip()
        if not text:
            return ""
        return text if text.endswith(".") else text + "."

    def _describe_action() -> str:
        if action == "discard":
            return f"Discard {item_name} immediately to eliminate the spoilage or health risk"
        if action == "donate":
            return f"Donate {item_name} while it is still usable"
        if action == "discount":
            pct = rec.get("suggested_discount_percent")
            if pct is not None:
                return f"Discount {item_name} by {pct}% to accelerate sell-through before expiry"
            return f"Discount {item_name} now to increase sales velocity"
        if action == "bundle":
            bundle = rec.get("bundle_suggestion")
            if bundle:
                return f"Bundle {item_name} with {bundle}"
            return f"Bundle {item_name} with a complementary item to boost demand"
        if action == "reorder":
            return f"Reorder {item_name} because current levels cannot sustain demand"
        if action == "price_increase":
            pct = rec.get("suggested_price_increase_percent")
            if pct is not None:
                return f"Increase {item_name}'s price by {pct}% given strong demand"
            return f"Raise {item_name}'s price to match demand"
        if action == "hold":
            return f"Hold {item_name} and monitor sales before making changes"
        if action == "none":
            return f"Review {item_name} manually as no automatic action was selected"
        return f"Recommend {action} for {item_name}"

    signal_bits: List[str] = []
    if item:
        expiry_raw = item.get("expiry_date")
        if expiry_raw:
            try:
                days = days_until_expiry_fn(expiry_raw)
                if days is not None:
                    if days < 0:
                        signal_bits.append(f"expired {abs(days)} day(s) ago")
                    elif days == 0:
                        signal_bits.append("expires today")
                    else:
                        signal_bits.append(f"expires in {days} day(s)")
            except Exception:
                pass
        stock = item.get("remaining_stock")
        if stock is None:
            stock = item.get("opening_stock")
        min_s = item.get("min_stock")
        try:
            stock_val = int(stock) if stock is not None else None
        except Exception:
            stock_val = None
        try:
            min_val = int(min_s) if min_s is not None else None
        except Exception:
            min_val = None
        if stock_val is not None:
            if min_val is not None:
                signal_bits.append(f"stock {stock_val} (minimum {min_val})")
            else:
                signal_bits.append(f"stock {stock_val}")
        fd = item.get("forecasted_demand")
        if fd is not None and query_type in ("demand", "out_of_stock", "low_stock", "check", "stock_status"):
            try:
                next_week = round(float(fd) * 7, 1)
                signal_bits.append(f"forecast ~{next_week} units over 7 days")
            except Exception:
                pass

    signal_sentence = ""
    if signal_bits:
        signal_sentence = f"Current signals: {signal_bits[0].capitalize()}"
        if len(signal_bits) > 1:
            signal_sentence += ", " + ", ".join(signal_bits[1:])
        signal_sentence = _with_period(signal_sentence)

    reason_sentence = ""
    if include_reason and reasoning_clean:
        cap = 220 if action in ("donate", "bundle", "discount", "discard") else 160
        snippet = reasoning_clean[:cap]
        reason_sentence = _with_period(snippet[: cap]) if snippet else ""
    elif not reasoning_clean and signal_sentence:
        reason_sentence = ""  # rely on signal sentence for explanation

    extras_sentences: List[str] = []
    discount_pct = rec.get("suggested_discount_percent")
    if discount_pct is not None:
        extras_sentences.append(_with_period(f"Suggested discount: {discount_pct}%"))
    price_increase_pct = rec.get("suggested_price_increase_percent")
    if price_increase_pct is not None:
        extras_sentences.append(_with_period(f"Suggested price increase: {price_increase_pct}%"))
    suggested_price = rec.get("suggested_selling_price")
    if suggested_price is not None:
        extras_sentences.append(_with_period(f"Suggested selling price: {suggested_price}"))
    bundle_suggestion = rec.get("bundle_suggestion")
    if bundle_suggestion:
        extras_sentences.append(_with_period(f"Bundle suggestion: {bundle_suggestion}"))
    discard_reason = rec.get("discard_reason")
    if discard_reason:
        extras_sentences.append(_with_period(f"Discard reason: {discard_reason}"))

    nearest_fb = rec.get("nearest_food_banks") or []
    if nearest_fb and action == "donate":
        donation_parts = []
        for fb in nearest_fb[:3]:
            name = str(fb.get("name", "")).strip()
            addr = str(fb.get("address", "")).strip()
            city = str(fb.get("city", "")).strip()
            state = str(fb.get("state", "")).strip()
            zip_ = str(fb.get("zip", "")).strip()
            loc = ", ".join(x for x in [addr, city, state, zip_] if x)
            if name and loc:
                donation_parts.append(f"{name} at {loc}")
            elif name:
                donation_parts.append(name)
        if donation_parts:
            extras_sentences.append(_with_period(f"Recommended donation locations: {'; '.join(donation_parts)}"))

    if no_expiry_hint:
        extras_sentences.append(_with_period("No expiry date set; add expiry_date so we can suggest discount or donation actions"))

    priority_sentence = _with_period(f"Priority: {priority}")

    result_sentences: List[str] = []
    action_sentence = _with_period(_describe_action())
    if action_sentence:
        result_sentences.append(f"{item_name}: {action_sentence}")
    if reason_sentence:
        result_sentences.append(reason_sentence)
    if signal_sentence and not reason_sentence:
        result_sentences.append(signal_sentence)
    elif signal_sentence and reason_sentence:
        result_sentences.append(signal_sentence)
    if extras_sentences:
        result_sentences.extend([s for s in extras_sentences if s])
    if priority_sentence:
        result_sentences.append(priority_sentence)

    explanation = recommendation.get("explanation", {})
    if include_reason and isinstance(explanation, dict):
        expl_text = " ".join(str(explanation.get("explanation") or "").split()).strip()
        expl_l = expl_text.lower()
        if expl_text and "no action" not in expl_l and "recommended action is to none" not in expl_l and "unable to generate explanation" not in expl_l:
            if not reasoning_clean or (expl_text[:60].lower() not in reasoning_clean.lower()):
                result_sentences.append(_with_period(f"Explanation: {expl_text[:160]}"))

    return " ".join(s for s in result_sentences if s)


def _build_food_bank_map_url(food_banks: List[Dict]) -> Optional[str]:
    """Build a Google Maps search URL for nearest food banks."""
    if not food_banks:
        return None
    first = food_banks[0] or {}
    lat = first.get("lat")
    lon = first.get("lon")
    if lat is not None and lon is not None:
        return f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
    city = str(first.get("city", "")).strip()
    state = str(first.get("state", "")).strip()
    area = ", ".join(x for x in [city, state] if x).strip()
    query = "food banks"
    if area:
        query = f"{query} near {area}"
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


def get_nearest_food_banks_direct(limit: int = 5) -> List[Dict]:
    """Fetch nearest food banks directly from Food Bank subagent."""
    try:
        headers = {"X-Agent-Token": AGENT_SHARED_TOKEN} if AGENT_SHARED_TOKEN else None
        r = requests.get(
            f"{FOOD_BANK_AGENT_URL}/nearest",
            params={"limit": max(1, min(limit, 20))},
            headers=headers,
            timeout=8,
        )
        if not r.ok:
            return []
        data = r.json() or {}
        banks = data.get("nearest_food_banks") or []
        return banks if isinstance(banks, list) else []
    except Exception:
        return []


def get_proactive_alert_items() -> Dict[str, List[Dict]]:
    """Get all items that need proactive attention: waste/near expiry, out of stock, low stock, overstock."""
    near_expiry = get_near_expiry_items(within_days=14)
    out_of_stock = get_out_of_stock_items(limit=10)
    low_stock = get_items_needing_attention("low stock")  # opening_stock <= min_stock
    overstock = get_overstock_items(limit=10)
    # Deduplicate: if an item is in out_of_stock, don't also list in low_stock
    low_stock_ids = {i["inventory_id"] for i in low_stock}
    out_ids = {i["inventory_id"] for i in out_of_stock}
    low_stock = [i for i in low_stock if i["inventory_id"] not in out_ids]
    return {
        "near_expiry": near_expiry,
        "out_of_stock": out_of_stock,
        "low_stock": low_stock[:10],
        "overstock": overstock,
    }


def process_proactive_summary(session_id: str = None) -> Dict:
    """
    Proactively analyze inventory and return a summary of what needs attention
    (waste/near expiry: donate/discount/bundle combined, out of stock, low stock, overstock).
    Does NOT store proactive recommendations in suggestions — display only.
    """
    alerts = get_proactive_alert_items()
    near_expiry = alerts["near_expiry"]
    out_of_stock = alerts["out_of_stock"]
    low_stock = alerts["low_stock"]
    overstock = alerts["overstock"]

    total_issues = len(near_expiry) + len(out_of_stock) + len(low_stock) + len(overstock)
    if total_issues == 0:
        summary = _get_inventory_summary()
        return {
            "answer": "Everything looks good right now. No items are near expiry, out of stock, low stock, or overstock. "
            + f"You have {summary.get('total_items', 0)} item(s) in inventory. Ask me to check inventory or suggest actions anytime.",
            "suggestions_count": 0,
        }

    lines = ["Here's what needs your attention right now:\n"]
    waste_actions = ("donate", "discount", "bundle", "discard")

    # Waste / Near expiry (expired + near-expiry, same as home page): top priority; show all in chatbot suggestions
    if near_expiry:
        waste_items = near_expiry[:24]
        recs, batch_err = call_decision_orchestrator_batch(
            waste_items, user_asked_about_waste=True, intent="waste", waste_action_preference=None
        )
        if batch_err and not recs:
            lines.append("**Waste / Near expiry**")
            lines.append(f"• Could not get recommendations — {batch_err}")
        elif recs:
            items_by_id = {it["inventory_id"]: it for it in waste_items}
            waste_lines = []
            for rec in recs:
                rec_action = (rec.get("recommendation") or {}).get("action", "")
                if rec_action not in waste_actions:
                    continue
                item = items_by_id.get(rec.get("inventory_id"))
                if not item:
                    continue
                waste_lines.append(_format_recommendation_line(
                    item.get("item_name", "Item"),
                    rec,
                    include_reason=True,
                    item=item,
                    query_type="near_expiry",
                ))
            if waste_lines:
                lines.append("**Waste / Near expiry (donate / discount / bundle)**")
                lines.extend(waste_lines)
            lines.append("")

    # Out of stock, low stock, overstock: show recommendations but do not save to suggestions
    categories = [
        ("Out of stock", out_of_stock[:3], False, "reorder"),
        ("Low stock", low_stock[:3], False, "reorder"),
        ("Overstock", overstock[:2], False, "general"),
    ]
    for label, items, waste_intent, category_intent in categories:
        if not items:
            continue
        lines.append(f"**{label}**")
        for item in items:
            rec, err = call_decision_orchestrator(item, user_asked_about_waste=waste_intent, intent=category_intent)
            if err:
                lines.append(f"• {item.get('item_name', 'Item')}: Could not get recommendation — {err}")
                continue
            if rec:
                # Pass item + query_type so each line is self-explaining (signals: stock/min/forecast/expiry).
                lines.append(_format_recommendation_line(
                    item.get("item_name", "Item"),
                    rec,
                    include_reason=True,
                    item=item,
                    query_type=("out_of_stock" if label == "Out of stock" else ("low_stock" if label == "Low stock" else ("overstock" if label == "Overstock" else None))),
                ))
        lines.append("")

    return {
        "answer": "\n".join(lines).replace("**", "").strip(),  # plain text for chat
        "suggestions_count": 0,  # proactive is display-only; no storage in suggestions
    }


def _query_looks_like_inventory(query_lower: str) -> bool:
    """True if the query clearly asks about inventory, stock, reorder, waste, suggestions, etc. Used to skip inventory path for general questions."""
    inventory_phrases = [
        "stock", "reorder", "inventory", "waste", "donate", "donation", "discount", "bundle",
        "suggest", "recommend", "check", "analyze", "low stock", "out of stock", "need to order",
        "what to reorder", "expir", "expiry", "going to waste", "items need", "items to",
        "stock level", "stock for", "demand for", "forecast", "pricing", "price increase",
        "what should i", "what do you recommend", "help with inventory", "sales", "last week",
    ]
    return any(p in query_lower for p in inventory_phrases)


def _detect_chat_intent(query_lower: str) -> str:
    """Detect primary intent so we return only relevant info. Uses shared intent_parser when available."""
    if not query_lower:
        return "general"
    high_demand_phrases = ("high demand", "high-demand", "high on demand", "in high demand")
    low_demand_phrases = ("low demand", "low-demand", "low on demand", "in low demand")
    if any(w in query_lower for w in ["food bank", "foodbank", "nearest food bank", "nearest food banks"]):
        return "food_bank"
    if any(w in query_lower for w in ["sales last week", "last week sales", "sales for", "sales related"]):
        return "sales"
    if any(w in query_lower for w in ["food bank", "foodbank", "nearest food bank", "nearest food banks"]):
        return "food_bank"
    # Explicit intents first: these must not be overridden by generic parser labels.
    if any(w in query_lower for w in ["non-perishable", "non perishable", "nonperishable", "non-perisbale", "non perisbale"]):
        return "non_perishable"
    if ("perishable" in query_lower or "persihable" in query_lower) and any(w in query_lower for w in ["inventory", "my", "in my"]):
        return "perishable"
    if any(p in query_lower for p in high_demand_phrases) and any(w in query_lower for w in ["inventory", "my", "in my"]):
        return "high_demand"
    if any(p in query_lower for p in low_demand_phrases) and any(w in query_lower for w in ["inventory", "my", "in my"]):
        return "low_demand"
    if any(w in query_lower for w in ["items need price increase", "what items need price increase", "which items need price increase"]):
        return "price_increase"
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
        from intent_parser import parse_intent
        parsed = parse_intent(query_lower)
        intent = parsed.get("intent", "general")
        # Map intent_parser names to chat's existing names where different
        if intent == "stock_status":
            return "stock"
        if intent == "forecast":
            return "demand"
        if intent == "recommendation":
            return "general"  # chat treats as general + should_generate_suggestions
        if intent == "stock_status" and any(w in query_lower for w in ["sales", "last week"]):
            return "sales"
        return intent
    except Exception:
        pass
    # Fallback: explicit intents (order matters: more specific first)
    if any(w in query_lower for w in ["sales last week", "last week sales", "sales for", "sales related"]):
        return "sales"
    if any(w in query_lower for w in ["non-perishable", "non perishable", "nonperishable", "non-perisbale", "non perisbale"]):
        return "non_perishable"
    if any(p in query_lower for p in high_demand_phrases):
        return "high_demand"
    if any(p in query_lower for p in low_demand_phrases):
        return "low_demand"
    if any(w in query_lower for w in ["price increase", "increase price", "items need price increase"]):
        return "price_increase"
    if any(w in query_lower for w in ["stock for", "stock of", "tell me stock", "what is the stock", "how much", "how many", "current stock", "stock level"]):
        return "stock"
    if any(w in query_lower for w in ["forecast demand", "demand for", "demand forecast", "demand forecast for"]):
        return "demand"
    if any(w in query_lower for w in ["discard", "dispose", "expired", "throw away", "which items to discard"]):
        return "discard"
    if any(w in query_lower for w in ["waste", "donate", "donation", "discount", "bundle", "bundled", "sell soon", "expir", "expiry", "going to waste", "sell or donate", "anything to sell", "anything to donate"]):
        return "waste"
    if any(w in query_lower for w in ["pricing", "price", "discount %", "discount percent", "increase price", "markup"]):
        return "pricing"
    if any(w in query_lower for w in ["low stock", "reorder", "check inventory", "out of stock", "need to order", "what to reorder"]):
        return "reorder"
    return "general"


def _answer_with_llm_only(query: str) -> Dict:
    """Answer general (non-inventory) questions directly from the LLM. No inventory lookup or recommendations."""
    if llm:
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are a helpful assistant. Answer the user's question concisely and clearly.
IMPORTANT: Output plain text only. Do not use markdown: no asterisks for bold, no hashtags for headers. The answer will be shown in chat as-is."""),
                ("user", "{query}"),
            ])
            chain = prompt | llm
            response = chain.invoke({"query": query})
            answer = response.content if hasattr(response, "content") else str(response)
            return {
                "answer": strip_markdown(answer),
                "suggestions_count": 0,
                "suggestions": [],
            }
        except Exception as e:
            logger.error(f"LLM-only answer failed: {e}")
    return {
        "answer": "I can help with general questions when the language model is configured. For inventory, ask about stock, reorder, or suggestions.",
        "suggestions_count": 0,
        "suggestions": [],
    }


def _needs_minimum_explanation(query_lower: str) -> bool:
    """True if the user is asking what the inventory 'minimum' refers to."""
    normalized = query_lower.replace("-", " ").replace("_", " ")
    minimum_terms = (
        "minimum",
        "min stock",
        "min stock level",
        "min level",
        "min_stock",
        "minlevel",
        "safety stock",
        "target stock",
    )
    question_terms = (
        "what",
        "mean",
        "meaning",
        "explain",
        "explanation",
        "definition",
        "describe",
        "why",
        "how",
        "tell me",
        "what is",
        "what does",
    )
    has_min = any(term in normalized for term in minimum_terms)
    has_question = any(term in normalized for term in question_terms)
    return has_min and has_question


def process_chat_query(query: str, session_id: str = None, include_eval_context: bool = False) -> Dict:
    """Process a chat query: check inventory, call decision agent, store suggestions. Filter by intent."""
    query_lower = query.lower().strip()
    # Normalize common typos/spaces so we stay on DB-backed intent paths.
    query_lower = query_lower.replace("re order", "reorder").replace("re-order", "reorder")
    query_lower = query_lower.replace("non perisbale", "non perishable").replace("non-perisbale", "non-perishable")
    query_tokens = [t for t in query.split() if t]
    intent = _detect_chat_intent(query_lower)
    is_food_bank_query = any(k in query_lower for k in ["food bank", "foodbank", "nearest food", "donation center"])

    def _build_response(
        answer: str,
        suggestions_count: int = 0,
        suggestions: Optional[List[Dict]] = None,
        nearest_food_banks: Optional[List[Dict]] = None,
        map_search_url: Optional[str] = None,
        retrieved_contexts: Optional[List[str]] = None,
    ) -> Dict:
        cleaned = strip_markdown(answer or "").strip()
        humanized = _humanize_chat_answer(query, intent, cleaned)
        return {
            "answer": humanized,
            "suggestions_count": suggestions_count,
            "suggestions": suggestions or [],
            "nearest_food_banks": nearest_food_banks or [],
            "map_search_url": map_search_url,
            "retrieved_contexts": retrieved_contexts or [],
        }

    if _needs_minimum_explanation(query_lower):
        explanation = (
            "The \"minimum\" number shown in SmartCartAI is the `min_stock` field stored on each inventory row (see `inventory.min_stock`). "
            "It represents your safety-stock target—the quantity you aim to keep so normal demand can be met without running out. "
            "When current stock reaches or drops below that minimum the risk-assessment agent flags it as low/out-of-stock, so the system can suggest reordering or waste actions. "
            "When an item is expired but still above the minimum, the alert simply reports how much stock you still hold versus that target; the discard/donate call is driven by expiry and buffer rather than the minimum value itself."
        )
        return _build_response(explanation)

    # Direct nearest-food-bank lookup when user asks specifically about food banks.
    if is_food_bank_query and intent not in ("waste", "donate", "discount", "bundle", "discard", "reorder", "pricing", "price_increase"):
        banks = get_nearest_food_banks_direct(limit=5)
        if not banks:
            return _build_response("I couldn't find nearby food banks right now. Please ensure the food-bank agent is running on port 9007.")
        lines = ["Nearest food banks:"]
        for fb in banks[:5]:
            name = str(fb.get("name", "")).strip() or "Food bank"
            addr = str(fb.get("address", "")).strip()
            city = str(fb.get("city", "")).strip()
            state = str(fb.get("state", "")).strip()
            zip_code = str(fb.get("zip", "")).strip()
            dist = fb.get("distance_mi")
            loc = ", ".join(x for x in [addr, city, state, zip_code] if x)
            suffix = f" ({dist} mi)" if dist is not None else ""
            lines.append(f"• {name}: {loc}{suffix}")
        return _build_response(
            "\n".join(lines),
            nearest_food_banks=banks[:5],
            map_search_url=_build_food_bank_map_url(banks),
        )

    # Direct informational intents (DB-only, no recommendation pipeline)
    if intent == "sales":
        item_name = _extract_product_name_from_query(query_lower) or ""
        if not item_name:
            # fallback from "sales last week for X"
            if " for " in query_lower:
                item_name = query_lower.split(" for ", 1)[-1].strip("?.!, ")
        rows = get_sales_last_week(item_name, limit=20) if item_name else []
        if not rows:
            return _build_response("No sales records found in table sales for the last 7 days for the requested item.")
        lines = [f"Sales last 7 days for '{item_name}' (from sales table):"]
        for r in rows:
            lines.append(
                f"• {r.get('item_name', 'Item')}: qty {int(r.get('total_quantity') or 0)}, "
                f"rows {int(r.get('sales_rows') or 0)}, "
                f"avg unit_cost {float(r.get('avg_unit_cost') or 0):.2f}, "
                f"total_cost {float(r.get('total_cost') or 0):.2f}"
            )
        return _build_response("\n".join(lines))

    if intent == "perishable":
        rows = get_perishable_items(limit=50)
        if not rows:
            return _build_response("No perishable items found in inventory.")
        lines = ["Perishable items in your inventory:"]
        for r in rows:
            lines.append(f"• {r.get('item_name', 'Item')} (stock: {r.get('remaining_stock', 0)}, expiry: {r.get('expiry_date') or 'N/A'})")
        return _build_response("\n".join(lines))
    if intent == "non_perishable":
        rows = get_non_perishable_items(limit=50)
        if not rows:
            return _build_response("No non-perishable items found in inventory.")
        lines = ["Non-perishable items in your inventory:"]
        for r in rows:
            lines.append(f"• {r.get('item_name', 'Item')} (stock: {r.get('remaining_stock', 0)}, expiry: {r.get('expiry_date') or 'N/A'})")
        return _build_response("\n".join(lines))
    if intent == "high_demand":
        rows = get_demand_ranked_items(high=True)
        if not rows:
            return _build_response("No demand prediction data found.")
        lines = ["High-demand items (from latest DB predictions):"]
        action_lines = []
        info_lines = []
        for r in rows:
            name = r.get("item_name", "Item")
            demand = r.get("forecasted_demand", 0)
            stock = r.get("remaining_stock")
            min_s = r.get("min_stock")
            try:
                stock_v = int(stock) if stock is not None else None
            except Exception:
                stock_v = None
            try:
                min_v = int(min_s) if min_s is not None else None
            except Exception:
                min_v = None

            is_low = (
                stock_v is not None
                and (stock_v <= 0 or (min_v is not None and stock_v <= min_v))
            )
            if is_low:
                rec, err = call_decision_orchestrator(r, user_asked_about_waste=False, intent="reorder")
                if rec and not err:
                    action_lines.append(
                        _format_recommendation_line(
                            name,
                            rec,
                            include_reason=False,
                            item=r,
                            query_type="low_stock",
                        )
                    )
                else:
                    info_lines.append(
                        f"• {name}: {demand} units/day, stock {stock_v if stock_v is not None else '?'}, min {min_v if min_v is not None else '?'}"
                    )
            else:
                info_lines.append(
                    f"• {name}: {demand} units/day, stock {stock_v if stock_v is not None else '?'}"
                )
        if action_lines:
            lines.append("Action needed (high demand + low/out stock):")
            lines.extend(action_lines)
            lines.append("")
        if info_lines:
            lines.append("Other high-demand items:")
            lines.extend(info_lines)
        return _build_response("\n".join(lines))
    if intent == "low_demand":
        rows = get_demand_ranked_items(high=False)
        if not rows:
            return _build_response("No demand prediction data found.")
        lines = ["Low-demand items (from latest DB predictions):"]
        for r in rows:
            lines.append(f"• {r.get('item_name', 'Item')}: {r.get('forecasted_demand', 0)} units/day")
        return _build_response("\n".join(lines))

    def _is_low_or_out_stock(it: Dict) -> bool:
        """Low/out-of-stock items should only appear in reorder suggestions."""
        stock = it.get("remaining_stock")
        if stock is None:
            stock = it.get("opening_stock")
        try:
            stock_val = int(stock) if stock is not None else None
        except Exception:
            stock_val = None
        if stock_val is None:
            return False
        if stock_val <= 0:
            return True
        min_s = it.get("min_stock")
        try:
            min_val = int(min_s) if min_s is not None else None
        except Exception:
            min_val = None
        return (min_val is not None) and (stock_val <= min_val)

    def _days_until_expiry(it: Dict) -> Optional[int]:
        """Return days until expiry for an item, if available."""
        expiry_raw = it.get("expiry_date") or it.get("expiryDate")
        if not expiry_raw:
            return None
        return days_until_expiry_fn(expiry_raw)

    def _bundle_near_miss_reason(item: Dict, rec_action: str, rec_reasoning: str) -> str:
        """Explain why an item missed the bundle rule."""
        days = _days_until_expiry(item)
        if days is None:
            return "missing expiry_date, so bundle window cannot be evaluated"
        if days < 0:
            return f"expired ({abs(days)} day(s) ago); discard path takes priority"
        if 0 <= days <= 3:
            return f"urgent expiry in {days} day(s); donate/clearance path takes priority"
        if 4 <= days <= 6:
            return f"in {days}-day discount window, not the 7–10 day bundle window"
        if days > 10:
            return f"expires in {days} day(s), outside the 7–10 day bundle window"
        if rec_action == "price_increase":
            return "high demand item; price increase is prioritized over bundling"
        if rec_action == "hold" and "No high-demand similar items available for a bundle" in rec_reasoning:
            return "no similar high-demand pairing item found"
        if rec_action == "hold" and "demand signal" in rec_reasoning.lower():
            return "demand signal did not meet bundle rule (needs low demand)"
        if rec_action and rec_action != "bundle":
            return f"policy selected {rec_action.upper()} instead"
        return "bundle conditions were not fully met"

    def _get_bundle_near_miss_lines(recs: List[Dict], items_by_id: Dict, limit: int = 6) -> List[str]:
        """Build near-miss lines for bundle intent when no strict bundle matches are found."""
        with_expiry = []
        for rec in recs:
            inv_id = rec.get("inventory_id")
            item = items_by_id.get(inv_id)
            if not item or _is_low_or_out_stock(item):
                continue
            recommendation = rec.get("recommendation") or {}
            rec_action = (recommendation.get("action") or "").strip().lower()
            if rec_action == "bundle":
                continue
            name = item.get("item_name", "Item")
            days = _days_until_expiry(item)
            if days is None:
                # For bundle near-miss, only show items with a valid expiry timeline.
                continue
            reason = _bundle_near_miss_reason(item, rec_action, recommendation.get("reasoning", ""))
            entry = (name, reason, days)
            with_expiry.append(entry)

        # Prioritize items that are closest to bundle window (7–10 days), then soonest expiry.
        def _sort_key(entry: Tuple[str, str, Optional[int]]) -> Tuple[int, int]:
            _, _, days = entry
            if days is None:
                return (3, 9999)
            if 7 <= days <= 10:
                return (0, days)
            if days > 10:
                return (1, days - 10)
            # days < 7
            return (2, 7 - days)

        with_expiry.sort(key=_sort_key)
        selected = with_expiry[:limit]
        lines = [f"• {name}: {reason}" for name, reason, _ in selected]
        return lines

    # General questions with no inventory keywords → answer directly from LLM (no inventory analysis or recommendations)
    if intent == "general" and not _query_looks_like_inventory(query_lower):
        return _answer_with_llm_only(query)

    # Check if this is a question that should trigger suggestions
    should_generate_suggestions = any(word in query_lower for word in [
        "suggest", "recommend", "what should", "what do", "check", "analyze",
        "low stock", "reorder", "need", "help"
    ])
    # Waste / expiry / donate / discount / bundle triggers (Chat-side)
    waste_trigger = any(word in query_lower for word in [
        "waste", "donate", "donation", "discount", "bundle", "bundled", "discard", "dispose", "sell soon", "expir", "expiry", "going to waste",
        "sell or donate", "anything to sell", "anything to donate", "whats going to waste"
    ])
    if waste_trigger:
        should_generate_suggestions = True
    if intent == "reorder":
        should_generate_suggestions = True
    if intent == "pricing":
        should_generate_suggestions = True
    if intent == "price_increase":
        should_generate_suggestions = True

    # Normalize typos so Inventory Agent returns the right item (e.g. "tock for Apple" -> "stock for apple")
    normalized_query = query_lower.replace("tock for ", "stock for ") if "tock for " in query_lower else query
    # Get items from Inventory Agent (single place that sees DB for user query).
    items, inv_err, inventory_query_type = call_inventory_agent_query(normalized_query)
    # Force item set by intent so we only return relevant data (use subagents/DB, not everything)
    if intent == "reorder":
        alerts = get_proactive_alert_items()
        out_of_stock = alerts.get("out_of_stock", [])
        low_stock = alerts.get("low_stock", [])
        out_ids = {i["inventory_id"] for i in out_of_stock}
        items = list(out_of_stock) + [i for i in low_stock if i["inventory_id"] not in out_ids]
        inventory_query_type = "low_stock" if items else "out_of_stock"
    elif intent == "waste" or intent in ("donate", "discount", "bundle", "discard"):
        # "Which items to donate/discount/bundle/discard" → same item set as waste (near-expiry)
        items = get_near_expiry_items(within_days=14)
        if not items and inv_err:
            items = get_items_needing_attention(query)
        inventory_query_type = "near_expiry"
    elif intent == "pricing":
        pricing_items = get_near_expiry_items(within_days=14)
        items = pricing_items if pricing_items else items
        inventory_query_type = "near_expiry"
    elif intent == "price_increase":
        items = get_price_increase_candidates(limit=30)
        inventory_query_type = "demand"
    # Only auto-enable recommendations for intents that imply "give me actions"; never for pure stock or demand lookups
    if intent in ("reorder", "waste", "donate", "discount", "bundle", "discard", "pricing", "price_increase") and items and inventory_query_type in ("near_expiry", "low_stock", "out_of_stock", "overstock", "demand"):
        should_generate_suggestions = True
    # Use Inventory Agent's interpretation: if it said "near_expiry", treat as waste; donate/discount/bundle are waste sub-intents
    is_waste_query = (intent in ("waste", "donate", "discount", "bundle", "discard")) or waste_trigger or (inventory_query_type == "near_expiry")
    # If we have items and any has expiry within 14 days, run waste intervention (discount/bundle/donate)
    # Important: never auto-flip a REORDER request into waste mode, even if some low/out-of-stock items also have near expiry.
    # Otherwise we filter out low/out-of-stock items and return empty recommendations for reorder queries.
    if items and not is_waste_query and intent != "reorder":
        try:
            for item in items:
                ed = item.get("expiry_date") or item.get("expiryDate")
                days = days_until_expiry_fn(ed)
                if days is not None and 0 <= days <= 14:
                    is_waste_query = True
                    break
        except Exception:
            pass
    if inv_err and (should_generate_suggestions or waste_trigger):
        logger.warning(f"Inventory agent unavailable ({inv_err}), using local DB fallback")

    if not items and inv_err:
        # Fallback: Chat Agent queries DB locally (same logic as Inventory Agent)
        items = get_items_needing_attention(query)
        if waste_trigger:
            near_expiry = get_near_expiry_items(within_days=14)
            if near_expiry:
                items = near_expiry
            else:
                # Try by-name for waste: longest token first so "milk" is tried before "can"
                waste_stopwords = {"is", "going", "to", "waste", "on", "whats", "what", "the", "any", "sell", "donate", "soon"}
                skip_generic = {"can", "we", "it", "or", "be", "do", "go"}
                candidates = [t for t in query_tokens if len(t) > 1 and t.lower() not in waste_stopwords and t.lower() not in skip_generic]
                candidates.sort(key=lambda t: -len(t))
                for token in candidates:
                    items_by_name = get_items_by_name(token)
                    if items_by_name:
                        items = items_by_name
                        break
                if not items and len(query_tokens) >= 2:
                    name_part = " ".join(t for t in query_tokens if t.lower() not in waste_stopwords)
                    if name_part:
                        items = get_items_by_name(name_part)
            if not items:
                items = []
        if not items and len(query_tokens) <= 3 and query_tokens:
            items_by_name = get_items_by_name(query.strip())
            if items_by_name:
                items = items_by_name
                should_generate_suggestions = True
        if should_generate_suggestions and not items and (" and " in query_lower or ", " in query_lower):
            import re as _re
            segs = _re.split(r"\s+and\s+|\s*,\s*", query_lower)
            stopwords = {"suggest", "recommend", "for", "what", "do", "the", "me", "give", "check", "you"}
            seen = set()
            merged = []
            for seg in segs:
                toks = [t for t in seg.split() if t and t not in stopwords]
                if toks:
                    name = toks[-1]
                    items_by_name = get_items_by_name(name)
                    for it in items_by_name or []:
                        if it.get("inventory_id") not in seen:
                            seen.add(it.get("inventory_id"))
                            merged.append(it)
            if merged:
                items = merged
        if should_generate_suggestions and not items and len(query_tokens) >= 2:
            stopwords = {
                "check", "inventory", "and", "suggest", "actions", "what", "items", "need",
                "reorder", "for", "my", "the", "me", "please", "analyze", "give", "recommendations",
                "going", "waste", "sell", "donate", "soon", "anything", "should", "to",
            }
            for token in query_tokens:
                if len(token) > 2 and token.lower() not in stopwords:
                    items_by_name = get_items_by_name(token)
                    if items_by_name:
                        items = items_by_name
                        break

    # If query looks like a stock question but we have no items yet, try to resolve by name (e.g. "stock for apple" -> get_items_by_name("apple"))
    if not items and any(phrase in query_lower for phrase in ["stock for", "stock of", "tell me stock", "tell me the stock", "what is the stock"]):
        if "stock for " in query_lower:
            name_part = query_lower.split("stock for ", 1)[-1].strip()
            if name_part and len(name_part) < 50:
                items = get_items_by_name(name_part)
        if not items and query_tokens:
            stopwords = {"stock", "for", "of", "the", "me", "tell", "what", "is", "level", "current"}
            for token in reversed(query_tokens):
                if len(token) > 1 and token.lower() not in stopwords:
                    items = get_items_by_name(token)
                    if items:
                        break

    # "forecast demand for X" / "demand for X" -> resolve items by name so we return demand for that item only
    query_looks_like_demand_for_item = ("forecast demand for" in query_lower) or ("demand for" in query_lower) or ("demand forecast for" in query_lower)
    if query_looks_like_demand_for_item:
        name_part = None
        if "forecast demand for " in query_lower:
            name_part = query_lower.split("forecast demand for ", 1)[-1].strip()
        elif "demand forecast for " in query_lower:
            name_part = query_lower.split("demand forecast for ", 1)[-1].strip()
        elif "demand for " in query_lower:
            name_part = query_lower.split("demand for ", 1)[-1].strip()
        if name_part and len(name_part) < 50:
            name_part = name_part.rstrip("?.!,")
            demand_items = get_items_by_name(name_part)
            if demand_items:
                items = demand_items

    # "for X" (e.g. "for honey", "what about for honey") -> try to resolve as single-item stock/demand
    if not items and " for " in query_lower and len(query_tokens) <= 5:
        if query_lower.strip().startswith("for "):
            name_part = query_lower.replace("for ", "", 1).strip().rstrip("?.!,")
            if name_part and len(name_part) < 40:
                items = get_items_by_name(name_part)
        else:
            idx = query_lower.find(" for ")
            if idx != -1:
                name_part = query_lower[idx + 5:].strip().rstrip("?.!,").split()[0] if query_lower[idx + 5:] else None
                if name_part and len(name_part) < 40:
                    items = get_items_by_name(name_part)

    # When user asked about waste/expiry (or Inventory said near_expiry) and we still have no items, try local near-expiry then by-name
    if not items and is_waste_query:
        items = get_near_expiry_items(within_days=14)
        if not items and query_tokens:
            waste_stopwords = {"is", "going", "to", "waste", "on", "whats", "what", "the", "any", "sell", "donate", "soon"}
            skip_generic = {"can", "we", "it", "or", "be", "do", "go"}
            candidates = [t for t in query_tokens if len(t) > 1 and t.lower() not in waste_stopwords and t.lower() not in skip_generic]
            candidates.sort(key=lambda t: -len(t))
            for token in candidates:
                items_by_name = get_items_by_name(token)
                if items_by_name:
                    items = items_by_name
                    break
            if not items:
                name_part = " ".join(t for t in query_tokens if t.lower() not in waste_stopwords)
                if name_part:
                    items = get_items_by_name(name_part)
    
    suggestions_generated = []
    used_recommendation_pipeline = False
    nearest_food_banks_for_ui: List[Dict] = []
    nearest_food_bank_keys = set()
    eval_contexts: List[str] = []
    eval_context_keys = set()
    answer_parts = []
    product_name = _extract_product_name_from_query(query_lower)

    def _push_eval_context(text: str):
        if not include_eval_context:
            return
        cleaned = " ".join(str(text or "").split()).strip()
        if not cleaned:
            return
        key = cleaned.lower()
        if key in eval_context_keys:
            return
        eval_context_keys.add(key)
        eval_contexts.append(cleaned)

    def _collect_eval_context_from_recommendation(item: Dict, rec_payload: Optional[Dict]):
        if not include_eval_context or not rec_payload:
            return
        rec_obj = rec_payload.get("recommendation") or {}
        risk = rec_payload.get("risk_assessment") or {}
        feasibility = rec_payload.get("feasibility_check") or {}
        cost = rec_payload.get("cost_impact") or {}
        explanation = rec_payload.get("explanation") or {}

        item_name = str(item.get("item_name", "Item")).strip() or "Item"
        item_category = str(item.get("category", "")).strip()
        expiry_date = item.get("expiry_date")
        base_line = f"Item: {item_name}"
        if item_category:
            base_line += f" (category: {item_category})"
        if expiry_date:
            base_line += f", expiry: {expiry_date}"
        _push_eval_context(base_line)

        action = str(rec_obj.get("action", "")).strip()
        reasoning = str(rec_obj.get("reasoning", "")).strip()
        expected_outcome = str(rec_obj.get("expected_outcome", "")).strip()
        if action:
            line = f"Recommended action: {action}"
            if reasoning:
                line += f". Reason: {reasoning}"
            if expected_outcome:
                line += f". Outcome: {expected_outcome}"
            _push_eval_context(line)

        discount_pct = rec_obj.get("suggested_discount_percent")
        suggested_price = rec_obj.get("suggested_price")
        if discount_pct is not None or suggested_price is not None:
            price_line = "Pricing:"
            if discount_pct is not None:
                price_line += f" discount {discount_pct}%"
            if suggested_price is not None:
                price_line += f", suggested price {suggested_price}"
            _push_eval_context(price_line)

        if isinstance(explanation, dict):
            explanation_text = str(explanation.get("explanation", "")).strip()
            if explanation_text:
                _push_eval_context(f"Explanation: {explanation_text}")

        risk_level = str(risk.get("risk_level", "")).strip()
        risk_score = risk.get("risk_score")
        if risk_level or risk_score is not None:
            _push_eval_context(f"Risk: level={risk_level or 'unknown'}, score={risk_score}")

        is_feasible = feasibility.get("is_feasible")
        if is_feasible is not None:
            _push_eval_context(f"Feasibility: is_feasible={is_feasible}")

        estimated_cost = cost.get("estimated_cost")
        within_budget = cost.get("within_budget")
        if estimated_cost is not None or within_budget is not None:
            _push_eval_context(f"Cost impact: estimated_cost={estimated_cost}, within_budget={within_budget}")

        nearest_food_banks = rec_obj.get("nearest_food_banks") or []
        for fb in nearest_food_banks[:3]:
            name = str(fb.get("name", "")).strip()
            address = str(fb.get("address", "")).strip()
            city = str(fb.get("city", "")).strip()
            state = str(fb.get("state", "")).strip()
            parts = [p for p in [name, address, city, state] if p]
            if parts:
                _push_eval_context("Nearest food bank: " + ", ".join(parts))

    def _collect_nearest_food_banks(rec_payload: Optional[Dict]):
        """Collect unique nearest-food-bank rows from recommendation payloads for UI map rendering."""
        if not rec_payload:
            return
        rec_obj = rec_payload.get("recommendation") or {}
        action = str(rec_obj.get("action", "")).strip().lower()
        # Show map cards only when the recommendation is to donate.
        if action != "donate":
            return
        candidates = rec_obj.get("nearest_food_banks") or []
        for fb in candidates:
            name = str(fb.get("name", "")).strip()
            addr = str(fb.get("address", "")).strip()
            city = str(fb.get("city", "")).strip()
            state = str(fb.get("state", "")).strip()
            zip_code = str(fb.get("zip", "")).strip()
            lat = fb.get("lat")
            lon = fb.get("lon")
            key = (name.lower(), addr.lower(), city.lower(), state.lower(), zip_code, str(lat), str(lon))
            if key in nearest_food_bank_keys:
                continue
            nearest_food_bank_keys.add(key)
            nearest_food_banks_for_ui.append({
                "name": name,
                "address": addr,
                "city": city,
                "state": state,
                "zip": zip_code,
                "lat": lat,
                "lon": lon,
                "phone": str(fb.get("phone", "")).strip(),
                "url": str(fb.get("url", "")).strip(),
                "distance_mi": fb.get("distance_mi"),
            })

    # "forecast demand for X" / "demand for X" -> return forecast for that item only (no recommendations)
    if query_looks_like_demand_for_item and items:
        for item in items[:10]:
            name = item.get("item_name", "Item")
            consumption_history = get_consumption_history(item.get("inventory_id"))
            forecasted_demand = calculate_forecasted_demand(consumption_history)
            demand_floor = get_demand_floor(item.get("inventory_id", ""))
            if demand_floor > 0:
                forecasted_demand = max(forecasted_demand, demand_floor)
            if forecasted_demand <= 0:
                answer_parts.append(f"{name}: demand data unavailable")
                continue
            answer_parts.append(f"{name}: forecasted demand {forecasted_demand:.1f} units/day (next 7 days)")
        if answer_parts:
            return _build_response("\n".join(answer_parts))

    # Simple stock lookup: "stock for apple", "tell me the stock for apple" — return stock info only, no recommendations
    query_looks_like_stock_question = any(phrase in query_lower for phrase in [
        "stock for", "stock of", "tell me stock", "tell me the stock", "what is the stock",
        "how much", "how many", "current stock", "stock level", "level for", "stock for"
    ])
    stock_lookup_only = (
        items
        and (
            (inventory_query_type in ("stock_status", "by_name") and not should_generate_suggestions)
            or query_looks_like_stock_question
        )
    )
    if stock_lookup_only:
        # When query names a product (e.g. "stock for honey"), show only that product's stock
        display_items = items
        if product_name:
            filtered = [i for i in items if product_name.lower() in (i.get("item_name") or "").lower()]
            if filtered:
                display_items = filtered
        for item in display_items[:10]:
            name = item.get("item_name", "Item")
            stock = item.get("remaining_stock")
            if stock is None:
                stock = item.get("opening_stock")
            if stock is None:
                stock = "?"
            min_s = item.get("min_stock")
            max_cap = item.get("max_capacity")
            status = "🟢 STABLE"
            try:
                stock_i = int(stock) if stock is not None and stock != "?" else None
            except Exception:
                stock_i = None
            try:
                min_i = int(min_s) if min_s is not None else None
            except Exception:
                min_i = None
            if isinstance(stock_i, int) and stock_i <= 0:
                status = "🔴 OUT OF STOCK"
            elif isinstance(stock_i, int) and isinstance(min_i, int) and min_i > 0 and stock_i <= min_i:
                status = "🟠 LOW STOCK"
            parts = [f"{name} | Stock: {stock} | Status: {status}"]
            if min_s is not None:
                parts.append(f"min {min_s}")
            if max_cap is not None:
                parts.append(f"max capacity {max_cap}")
            answer_parts.append(" — ".join(parts))
        if not answer_parts:
            answer_parts.append("No matching items found.")
    
    elif should_generate_suggestions and items:
        used_recommendation_pipeline = True
        # Stock/demand summary for out_of_stock, overstock, demand, stock_status query types
        if inventory_query_type == "out_of_stock":
            answer_parts.append(f"I found {len(items)} item(s) out of stock. Consider reordering to avoid lost sales.")
        elif inventory_query_type == "overstock":
            answer_parts.append(f"I found {len(items)} item(s) overstock (at or above 90%% of max capacity).")
        elif inventory_query_type == "demand":
            answer_parts.append("Here is demand forecast for the next 7 days based on recent consumption:\n")
        elif inventory_query_type == "stock_status":
            answer_parts.append(f"Current stock: {len(items)} item(s) in stock.\n")
        elif is_waste_query:
            # Don't say "20 items" when we only analyze 8 and show fewer; avoid confusion
            if intent == "donate":
                answer_parts.append("I've checked items that may be suitable for donation.")
            elif intent == "discount":
                answer_parts.append("I've checked items that may be suitable for discounting.")
            elif intent == "bundle":
                answer_parts.append("I've checked items that may be suitable for bundling.")
            elif intent == "discard":
                answer_parts.append("I've checked items that should be discarded (expired).")
            else:
                answer_parts.append("I've checked items that may be going to waste.")
        else:
            answer_parts.append(f"I've analyzed your inventory and found {len(items)} item(s) that need attention.")
        answer_parts.append("Here are my recommendations:\n")
        errors = []

        # Waste/expiry: one batch request. Sort by expiry (soonest first) so DISCOUNT candidates (near-term expiry) get into the batch.
        if (is_waste_query or intent == "price_increase") and items:
            from datetime import date as _date
            # Low/out-of-stock should only show under reorder, never donate/discount/bundle/discard.
            items = [it for it in items if not _is_low_or_out_stock(it)]
            def _expiry_sort_key(it):
                ed = it.get("expiry_date")
                if ed is None:
                    return (_date.max,)
                try:
                    d = ed if isinstance(ed, _date) else _date.fromisoformat(str(ed)[:10])
                    return (d,)
                except Exception:
                    return (_date.max,)
            waste_items_sorted = sorted(items, key=_expiry_sort_key)
            batch_size = 8   # keep under batch timeout (orchestrator runs pipeline per item; 8 items ~within 120s)
            # Do not pass waste_action_preference: orchestrator computes one canonical action per item (hierarchy).
            # We filter by that stored action below when user asks "what to discount/donate/bundle" to avoid duplicates.
            waste_action_preference = None
            # Process all near-expiry items in batches of 8 (up to 4 batches = 32 items) so "28 items expiring" gets all checked
            recs = []
            batch_err = None
            max_batches = 4
            for start in range(0, min(len(waste_items_sorted), max_batches * batch_size), batch_size):
                chunk = waste_items_sorted[start : start + batch_size]
                if not chunk:
                    break
                batch_intent = "pricing" if intent in ("pricing", "price_increase") else "waste"
                chunk_recs, chunk_err = call_decision_orchestrator_batch(chunk, user_asked_about_waste=True, intent=batch_intent, waste_action_preference=waste_action_preference)
                if chunk_err:
                    batch_err = chunk_err
                    if not recs:
                        break
                    break
                recs.extend(chunk_recs or [])
            if batch_err and not recs:
                errors.append(batch_err)
                answer_parts.append(f"• Could not get recommendations — {batch_err}")
            elif recs:
                items_by_id = {it["inventory_id"]: it for it in items}
                waste_actions = ("donate", "discount", "bundle", "discard")
                # Filter by stored action: each item has exactly one action from the hierarchy; show only items matching the user's question.
                waste_action_filter = None
                if intent == "waste" or intent in ("donate", "discount", "bundle", "discard"):
                    if intent == "donate":
                        waste_action_filter = "donate"
                    elif intent == "discount":
                        waste_action_filter = "discount"
                    elif intent == "bundle":
                        waste_action_filter = "bundle"
                    elif intent == "discard":
                        waste_action_filter = "discard"
                    elif "pricing" in query_lower and "discount" in query_lower:
                        waste_action_filter = None
                    elif "discard" in query_lower or "dispose" in query_lower:
                        waste_action_filter = "discard"
                    elif "discount" in query_lower:
                        waste_action_filter = "discount"
                    elif "donation" in query_lower or "donate" in query_lower or "donated" in query_lower:
                        waste_action_filter = "donate"
                    elif "bundle" in query_lower or "bundled" in query_lower:
                        waste_action_filter = "bundle"
                waste_shown = 0  # count how many we show so we can fall back if filter yields zero
                for rec in recs:
                    inv_id = rec.get("inventory_id")
                    item = items_by_id.get(inv_id)
                    if not item:
                        continue
                    rec_action = (rec.get("recommendation") or {}).get("action", "")
                    # Low/out-of-stock items are reorder only: never show under donate/discount/bundle/discard/waste lists
                    if _is_low_or_out_stock(item):
                        continue
                    # Intent filter: waste query -> only show donate, discount, bundle (not hold or price_increase)
                    if intent == "waste" and rec_action not in waste_actions:
                        continue
                    # Sub-intent: show only the waste action the user asked for (discount / donate / bundle)
                    if waste_action_filter and rec_action != waste_action_filter:
                        continue
                    # Intent filter: pricing -> only show lines with a pricing %
                    if intent in ("pricing", "price_increase"):
                        r = rec.get("recommendation") or {}
                        if r.get("suggested_discount_percent") is None and r.get("suggested_price_increase_percent") is None:
                            continue
                    if intent == "price_increase" and rec_action != "price_increase":
                        continue
                    recommendation = rec  # full response shape: has "recommendation" key
                    _collect_eval_context_from_recommendation(item, recommendation)
                    try:
                        suggestion_id = save_suggestion(query, item, recommendation)
                        if suggestion_id:
                            _collect_nearest_food_banks(recommendation)
                            suggestions_generated.append({
                                "item": item["item_name"],
                                "action": recommendation.get("recommendation", {}).get("action", "none"),
                                "priority": recommendation.get("recommendation", {}).get("priority", "Medium"),
                                "suggestion_id": suggestion_id,
                            })
                            no_expiry = not item.get("expiry_date")
                            answer_parts.append(_format_recommendation_line(
                                item["item_name"], recommendation, include_reason=True,
                                item=item, query_type=inventory_query_type,
                                no_expiry_hint=no_expiry,
                            ))
                            waste_shown += 1
                        else:
                            errors.append(f"{item.get('item_name')}: Failed to save suggestion.")
                    except Exception as e:
                        logger.error(f"Error processing batch item {inv_id}: {e}")
                        errors.append(f"{item.get('item_name', 'Item')}: {str(e)[:80]}")
                # Replace generic "Here are my recommendations" with action-specific intro when user asked for one action
                if waste_action_filter or intent in ("pricing", "price_increase"):
                    try:
                        idx = next(i for i, p in enumerate(answer_parts) if p == "Here are my recommendations:\n")
                        action_intro = (
                            {"discount": "These can be discounted:\n", "donate": "These can be donated:\n", "bundle": "These can be bundled:\n", "discard": "These should be discarded:\n"}.get(waste_action_filter or "")
                            or ("Price increase suggestions:\n" if intent == "price_increase" else ("Pricing suggestions:\n" if intent == "pricing" else None))
                        )
                        if action_intro:
                            answer_parts[idx] = action_intro
                    except StopIteration:
                        pass
                # When user asked for one action and none matched, say so and explain why
                if waste_action_filter and waste_shown == 0:
                    filter_label = {"discount": "discount", "donate": "donation", "bundle": "bundling", "discard": "discard"}.get(waste_action_filter, waste_action_filter)
                    answer_parts.append(f"No items are currently recommended for {filter_label}.")
                    if waste_action_filter == "bundle":
                        near_miss_lines = _get_bundle_near_miss_lines(recs, items_by_id, limit=6)
                        if near_miss_lines:
                            answer_parts.append("Near-miss bundle candidates:")
                            answer_parts.extend(near_miss_lines)
                    if waste_action_filter == "donate":
                        answer_parts.append("Donation is recommended only for PERISHABLE items expiring in 0–3 days (urgent). If nothing is that close to expiry, you may see discounts/bundles instead.")
                    elif waste_action_filter == "discount":
                        answer_parts.append("Discount is recommended for PERISHABLE and NON-PERISHABLE items expiring in 4–7 days when demand is high.")
                    elif waste_action_filter == "bundle":
                        answer_parts.append("Bundling is recommended for PERISHABLE and NON-PERISHABLE items expiring in 7–10 days when demand is low, paired with similar high-demand items.")
                    elif waste_action_filter == "discard":
                        answer_parts.append("Discard is recommended only for EXPIRED items (past expiry). If none are expired, you may see donate/discount/bundle instead.")
                    else:
                        answer_parts.append("Ask \"What's going to waste?\" to see all suggested actions (donate/discount/bundle/discard).")
                if intent == "price_increase" and waste_shown == 0:
                    answer_parts.append("No items are currently recommended for price increase.")
                # Do not save or mention items with no matching action (donate/discount/bundle) when user asked for one
            else:
                answer_parts.append("• No recommendations returned from batch.")
        else:
            # Non-waste: reorder path (uses orchestrator with user_asked_about_waste=False -> reorder suggestions)
            for item in items[:8]:
                try:
                    recommendation, err = call_decision_orchestrator(item, user_asked_about_waste=False, intent=intent)
                    if err:
                        errors.append(f"{item.get('item_name', item.get('inventory_id', '?'))}: {err}")
                        answer_parts.append(f"• {item.get('item_name', 'Item')}: Could not get recommendation — {err}")
                        continue
                    if recommendation:
                        _collect_eval_context_from_recommendation(item, recommendation)
                        _collect_nearest_food_banks(recommendation)
                        rec_action = (recommendation.get("recommendation") or {}).get("action", "")
                        # Intent reorder: only show reorder actions (no waste suggestions)
                        if intent == "reorder" and rec_action != "reorder":
                            continue
                        suggestion_id = save_suggestion(query, item, recommendation)
                        if suggestion_id:
                            suggestions_generated.append({
                                "item": item["item_name"],
                                "action": rec_action,
                                "priority": recommendation.get("recommendation", {}).get("priority", "Medium"),
                                "suggestion_id": suggestion_id,
                            })
                            answer_parts.append(_format_recommendation_line(
                                item["item_name"], recommendation, include_reason=True,
                                item=item, query_type=inventory_query_type,
                                no_expiry_hint=False,
                            ))
                        else:
                            errors.append(f"{item.get('item_name')}: Failed to save suggestion to database.")
                    else:
                        errors.append(f"{item.get('item_name')}: No recommendation returned.")
                except Exception as e:
                    logger.error(f"Error processing item {item.get('inventory_id')}: {e}")
                    errors.append(f"{item.get('item_name', 'Item')}: {str(e)[:80]}")
                    answer_parts.append(f"• {item.get('item_name', 'Item')}: Error — {str(e)[:80]}")

        # No footer lines — response is just the intro and recommendation lines
    
    elif should_generate_suggestions and not items:
        # User asked to check/suggest but no items found (e.g. no low stock, empty DB, or item name not found)
        logger.info("Check/suggest requested but no items returned (empty list or DB issue). Showing inventory summary.")
        summary = _get_inventory_summary()
        total = summary.get("total_items", 0)
        low = summary.get("low_stock_count", 0)
        answer_parts.append("I've checked your inventory.")
        if total == 0:
            answer_parts.append("There are no items in your inventory yet.")
        elif is_waste_query:
            answer_parts.append("No items are currently at expiry risk (within 14 days).")
            answer_parts.append("To get actionable suggestions for waste reduction, you can:")
            answer_parts.append("1. Set expiry_date on items in your inventory - this helps identify items approaching expiry so we can suggest discounts, bundling, or donation")
            answer_parts.append("2. Ask about specific items by name (e.g. 'What about milk?')")
            answer_parts.append("3. Ask about low stock items that may need reordering to prevent waste")
            answer_parts.append("Your inventory currently has " + str(total) + " item(s) with " + str(low) + " items at low stock levels.")
        else:
            answer_parts.append(f"You have {total} item(s) in inventory. No items currently need attention (low stock count: {low}).")
        answer_parts.append("Try asking about a specific item by name (e.g. \"apple\") or \"What items need reordering?\" when you have low stock.")
    
    else:
        # Regular Q&A mode. Avoid LLM hallucinations for inventory-like queries.
        if _query_looks_like_inventory(query_lower):
            answer_parts.append("I couldn't find matching DB records for that inventory query. Please try with an exact item name from your inventory.")
            return _build_response("\n".join(answer_parts))
        # Non-inventory general Q&A
        if llm:
            try:
                summary = _get_inventory_summary()
                context_text = f"""
Inventory Summary:
- Total Items: {summary.get('total_items', 0)}
- Total Stock: {summary.get('total_stock', 0)}
- Low Stock Items: {summary.get('low_stock_count', 0)}
"""
                
                prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are a helpful inventory management assistant for SmartCartAI.
Answer questions about inventory, stock levels, and provide general information.
Be concise and helpful.
IMPORTANT: Output plain text only. Do not use markdown: no asterisks for bold, no hashtags for headers. The answer will be shown in the chat as-is."""),
                    ("user", "Question: {query}\n\nContext:\n{context}\n\nAnswer:"),
                ])
                
                chain = prompt | llm
                response = chain.invoke({"query": query, "context": context_text})
                answer = response.content if hasattr(response, 'content') else str(response)
                answer_parts.append(strip_markdown(answer))
            except Exception as e:
                logger.error(f"LLM processing failed: {e}")
                answer_parts.append("I can help you with inventory questions. Try asking about low stock items, categories, or request suggestions.")
        else:
            answer_parts.append("I can help you with inventory management. Ask me to check inventory or generate suggestions for items that need attention.")
    
    final_answer = _humanize_chat_answer(query, intent, "\n".join(answer_parts))

    map_search_url = _build_food_bank_map_url(nearest_food_banks_for_ui)
    return _build_response(
        final_answer,
        suggestions_count=len(suggestions_generated),
        suggestions=suggestions_generated,
        nearest_food_banks=nearest_food_banks_for_ui[:5],
        map_search_url=map_search_url,
        retrieved_contexts=eval_contexts if include_eval_context else [],
    )


@mcp.tool()
def chat(query: str, session_id: str = None, include_eval_context: bool = False) -> dict:
    """Process a chat query about inventory."""
    return process_chat_query(query, session_id, include_eval_context=include_eval_context)


@mcp.tool()
def proactive(session_id: str = None) -> dict:
    """Return proactive summary (same as /proactive) for MCP clients."""
    return process_proactive_summary(session_id)


if __name__ == "__main__":
    # MCP-only: expose tools at http://host:port/mcp
    mcp_port = int(os.getenv("MCP_PORT", "9106"))
    host = os.getenv("MCP_HOST", "0.0.0.0")
    logger.info("Starting Chat Agent MCP server on %s:%s", host, mcp_port)
    mcp.run(transport="http", host=host, port=mcp_port)
