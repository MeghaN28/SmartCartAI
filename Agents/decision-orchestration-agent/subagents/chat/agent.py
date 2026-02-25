"""Chat Agent – Orchestrator that handles conversational queries, checks inventory, calls decision agent, and stores suggestions."""
import os
import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

import json

# Single source of demand forecast: ETS only (same as Inventory Agent)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))
from common.forecasting import forecast_demand as forecast_demand_ets
import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from langchain_core.prompts import ChatPromptTemplate
from langchain_mistralai import ChatMistralAI
from fastmcp import FastMCP

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

mcp = FastMCP("Chat Agent")
app = Flask(__name__)

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
        response = requests.post(
            f"{INVENTORY_AGENT_URL}/query",
            json={"query": query},
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


def get_demand_ranked_items(high: bool = True, limit: int = 15) -> List[Dict]:
    """Return items ranked by latest DB demand prediction (high or low)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        order = "DESC" if high else "ASC"
        demand_filter = "l.predicted_demand >= t.p70" if high else "l.predicted_demand < t.p70"
        cur.execute(
            f"""
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
            LIMIT %s
            """,
            (limit,),
        )
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


# Demand forecast: past 1 week → next 1 week
FORECAST_PAST_DAYS = 7
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

    def _call_one(it: Dict) -> Optional[Dict]:
        payload = _build_orchestrator_payload(
            it,
            user_asked_about_waste or intent == "pricing",
            intent=payload_intent,
            waste_action_preference=waste_action_preference,
        )
        try:
            response = requests.post(f"{DECISION_ORCHESTRATOR_URL}/orchestrate", json=payload, timeout=30)
            if not response.ok:
                logger.warning("Orchestrate failed for item %s: %s", it.get("item_name"), response.status_code)
                return None
            data = response.json()
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
            logger.warning("Orchestrate timeout for item %s", it.get("item_name"))
            return None
        except Exception as e:
            logger.error("Orchestrate failed for item %s: %s", it.get("item_name"), e)
            return None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_call_one, it) for it in batch_items]
        for f in as_completed(futures):
            out = f.result()
            if out:
                recs.append(out)
    if batch_items and not recs:
        return None, "Could not get recommendations from orchestrator (all items failed or service unavailable)."
    return recs, None


def call_decision_orchestrator(item: Dict, user_asked_about_waste: bool = False, intent: str = "general") -> Tuple[Optional[Dict], Optional[str]]:
    """Call the Decision Orchestrator Agent for an item. Pass intent so orchestrator runs only relevant subagents."""
    try:
        payload = _build_orchestrator_payload(item, user_asked_about_waste, intent=intent)
        response = requests.post(f"{DECISION_ORCHESTRATOR_URL}/orchestrate", json=payload, timeout=15)
        if response.ok:
            return response.json(), None
        err_msg = f"Recommendation service returned {response.status_code}"
        try:
            body = response.text[:200] if response.text else ""
            if body:
                err_msg += f": {body}"
        except Exception:
            pass
        logger.error(f"Decision orchestrator: {err_msg}")
        return None, err_msg
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


def _format_recommendation_line(
    item_name: str,
    recommendation: Dict,
    include_reason: bool = True,
    item: Optional[Dict] = None,
    query_type: Optional[str] = None,
    no_expiry_hint: bool = False,
) -> str:
    """Format a single recommendation for chat: action, discount %, bundle, discard + reason, explanation.
    If item and query_type provided, can add stock status and demand for next week.
    If no_expiry_hint (waste query but item has no expiry_date), add hint to set expiry for discount/donation."""
    rec = recommendation.get("recommendation", {})
    action = rec.get("action", "none")
    priority = rec.get("priority", "Medium")
    reasoning = rec.get("reasoning", "")
    parts = [f"• {item_name}: {action.upper()} ({priority} priority)"]
    if no_expiry_hint:
        parts.append(" No expiry date set — set expiry_date to get discount and donation suggestions.")
    if item and query_type in ("out_of_stock", "overstock", "demand", "low_stock", "check", "stock_status"):
        stock = item.get("remaining_stock", item.get("opening_stock", 0))
        min_s = item.get("min_stock", 0)
        if stock <= 0:
            parts.append(" [OUT OF STOCK — suggest reorder]")
        elif min_s and stock < min_s:
            parts.append(" [NEAR STOCKOUT — suggest reorder]")
        elif query_type == "overstock":
            parts.append(" [OVERSTOCK]")
        else:
            parts.append(" [In stock]")
        fd = item.get("forecasted_demand")
        if fd is not None and query_type in ("demand", "out_of_stock", "low_stock", "check"):
            next_week = round(float(fd) * 7, 1)
            parts.append(f" Demand (next 7 days): ~{next_week}")
    if reasoning:
        cap = 200 if action.lower() in ("donate", "bundle", "discount", "discard") else 120
        parts.append(f" — {reasoning[:cap]}" + ("..." if len(reasoning) > cap else ""))
    extras = []
    if rec.get("suggested_discount_percent") is not None:
        extras.append(f"Discount: {rec.get('suggested_discount_percent')}%")
    if rec.get("suggested_price_increase_percent") is not None:
        extras.append(f"Price increase: {rec.get('suggested_price_increase_percent')}%")
    if rec.get("suggested_selling_price") is not None:
        extras.append(f"Sell at: {rec.get('suggested_selling_price')}")
    if rec.get("bundle_suggestion"):
        extras.append(f"Bundle: {rec.get('bundle_suggestion')}")
    if rec.get("discard_reason"):
        extras.append(f"Discard reason: {rec.get('discard_reason')}")
    if rec.get("waste_action"):
        extras.append(rec.get("waste_action"))
    nearest_fb = rec.get("nearest_food_banks") or []
    if nearest_fb:
        # Exact donation location: name and full address (use separate list so we don't overwrite parts)
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
            extras.append("Donate to: " + "; ".join(donation_parts))
    if extras:
        parts.append(" | " + ", ".join(extras))
    if include_reason and action.lower() not in ("donate", "bundle", "discount", "discard"):
        # Don't append explanation when it's generic/error (no action, unable to generate, subagent down)
        explanation = recommendation.get("explanation", {})
        if isinstance(explanation, dict) and explanation.get("explanation"):
            expl = (explanation.get("explanation") or "").strip()
            if expl and "no action" not in expl.lower() and "recommended action is to none" not in expl.lower() and "unable to generate explanation" not in expl.lower():
                parts.append(f" Reason: {expl[:150]}" + ("..." if len(expl) > 150 else ""))
            elif not reasoning and expl:
                parts.append(f" Reason: {expl[:150]}" + ("..." if len(expl) > 150 else ""))
    return "".join(parts)


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
                waste_lines.append(_format_recommendation_line(item.get("item_name", "Item"), rec, include_reason=True))
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
                lines.append(_format_recommendation_line(item.get("item_name", "Item"), rec, include_reason=True))
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
        "what should i", "what do you recommend", "help with inventory",
    ]
    return any(p in query_lower for p in inventory_phrases)


def _detect_chat_intent(query_lower: str) -> str:
    """Detect primary intent so we return only relevant info. Uses shared intent_parser when available."""
    if not query_lower:
        return "general"
    # Explicit intents first: these must not be overridden by generic parser labels.
    if ("perishable" in query_lower or "persihable" in query_lower) and any(w in query_lower for w in ["inventory", "my", "in my"]):
        return "perishable"
    if "high demand" in query_lower and any(w in query_lower for w in ["inventory", "my", "in my"]):
        return "high_demand"
    if "low demand" in query_lower and any(w in query_lower for w in ["inventory", "my", "in my"]):
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
        return intent
    except Exception:
        pass
    # Fallback: explicit intents (order matters: more specific first)
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


def process_chat_query(query: str, session_id: str = None) -> Dict:
    """Process a chat query: check inventory, call decision agent, store suggestions. Filter by intent."""
    query_lower = query.lower().strip()
    query_tokens = [t for t in query.split() if t]
    intent = _detect_chat_intent(query_lower)

    # Direct informational intents (DB-only, no recommendation pipeline)
    if intent == "perishable":
        rows = get_perishable_items(limit=50)
        if not rows:
            return {"answer": "No perishable items found in inventory.", "suggestions_count": 0, "suggestions": []}
        lines = ["Perishable items in your inventory:"]
        for r in rows:
            lines.append(f"• {r.get('item_name', 'Item')} (stock: {r.get('remaining_stock', 0)}, expiry: {r.get('expiry_date') or 'N/A'})")
        return {"answer": "\n".join(lines), "suggestions_count": 0, "suggestions": []}
    if intent == "high_demand":
        rows = get_demand_ranked_items(high=True, limit=15)
        if not rows:
            return {"answer": "No demand prediction data found.", "suggestions_count": 0, "suggestions": []}
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
        return {"answer": "\n".join(lines), "suggestions_count": 0, "suggestions": []}
    if intent == "low_demand":
        rows = get_demand_ranked_items(high=False, limit=15)
        if not rows:
            return {"answer": "No demand prediction data found.", "suggestions_count": 0, "suggestions": []}
        lines = ["Low-demand items (from latest DB predictions):"]
        for r in rows:
            lines.append(f"• {r.get('item_name', 'Item')}: {r.get('forecasted_demand', 0)} units/day")
        return {"answer": "\n".join(lines), "suggestions_count": 0, "suggestions": []}

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
    if items and not is_waste_query:
        try:
            from datetime import date, timedelta
            today = date.today()
            for item in items:
                ed = item.get("expiry_date")
                if ed is not None:
                    d = ed if isinstance(ed, date) else date.fromisoformat(str(ed)[:10])
                    if 0 <= (d - today).days <= 14:
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
    answer_parts = []
    product_name = _extract_product_name_from_query(query_lower)

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
            return {"answer": "\n".join(answer_parts), "suggestions_count": 0, "suggestions": []}

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
            parts = [f"{name}: {stock} in stock"]
            if min_s is not None:
                parts.append(f"min {min_s}")
            if max_cap is not None:
                parts.append(f"max capacity {max_cap}")
            answer_parts.append(" — ".join(parts))
        if not answer_parts:
            answer_parts.append("No matching items found.")
    
    elif should_generate_suggestions and items:
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
                    try:
                        suggestion_id = save_suggestion(query, item, recommendation)
                        if suggestion_id:
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
        # Regular Q&A mode - just answer the question
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
    
    return {
        "answer": "\n".join(answer_parts),
        "suggestions_count": len(suggestions_generated),
        "suggestions": suggestions_generated
    }


@app.route("/chat", methods=["POST"])
def chat_endpoint():
    """Chat endpoint for conversational queries."""
    payload = request.get_json(silent=True) or {}
    
    query = (payload.get("query") or payload.get("message") or "").strip()
    session_id = payload.get("session_id")
    
    if not query:
        return jsonify({"error": "query is required", "answer": "Please type a question (e.g. 'Check inventory and suggest actions')."}), 400
    
    try:
        result = process_chat_query(query, session_id)
        return jsonify({
            "answer": result["answer"],
            "suggestions_count": result.get("suggestions_count", 0),
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
        }), 200
    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        return jsonify({"error": str(e), "answer": "I'm sorry, I encountered an error processing your request."}), 500


@app.route("/proactive", methods=["POST", "GET"])
def proactive_endpoint():
    """Proactive summary: waste/near expiry, out of stock, low stock, overstock with full recommendations (hold, discount %%, bundle, discard + reason)."""
    payload = request.get_json(silent=True) or {}
    session_id = payload.get("session_id")
    try:
        result = process_proactive_summary(session_id)
        return jsonify({
            "answer": result["answer"],
            "suggestions_count": result.get("suggestions_count", 0),
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
        }), 200
    except Exception as e:
        logger.error(f"Proactive summary error: {e}")
        return jsonify({
            "error": str(e),
            "answer": "I couldn't load proactive alerts right now. Try asking 'Check inventory and suggest actions'.",
        }), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "agent": "chat",
        "mistral_configured": llm is not None,
    }), 200


@mcp.tool()
def chat(query: str) -> dict:
    """Process a chat query about inventory."""
    result = process_chat_query(query)
    return result


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9006"))
    logger.info(f"Starting Chat Agent Flask server on port {port}")
    logger.info(f"Health check: http://localhost:{port}/health")
    logger.info(f"Chat endpoint: http://localhost:{port}/chat")
    # Avoid duplicate processes binding the same port when started via nohup/scripts.
    # Opt-in reloader for local dev only: CHAT_USE_RELOADER=true
    use_reloader = os.getenv("CHAT_USE_RELOADER", "false").lower() in ("1", "true", "yes")
    debug = os.getenv("CHAT_DEBUG", "false").lower() in ("1", "true", "yes")
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True, use_reloader=use_reloader)
