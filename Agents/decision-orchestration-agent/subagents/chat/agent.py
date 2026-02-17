"""Chat Agent – Orchestrator that handles conversational queries, checks inventory, calls decision agent, and stores suggestions."""
import os
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime

import json
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
    """Get items with expiry_date within the next within_days (for waste/donate/sell-soon flows)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT inventory_id, item_name, category, form, "use",
                       opening_stock as remaining_stock, min_stock, max_capacity,
                       vendor_id, expiry_date, selling_price
                FROM inventory
                WHERE expiry_date IS NOT NULL
                  AND expiry_date >= CURRENT_DATE
                  AND expiry_date <= CURRENT_DATE + INTERVAL '1 day' * %s
                ORDER BY expiry_date ASC
                LIMIT 20
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
                SELECT inventory_id, item_name, category, form, "use",
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


def call_inventory_agent_query(query: str) -> Tuple[List[Dict], Optional[str]]:
    """
    Call the Inventory Agent with the user query. Inventory Agent sees the DB
    (low stock, expired, near expiring, waste, etc.) and returns matching items.
    Returns (items_list, error_message). On success error_message is None.
    """
    try:
        response = requests.post(
            f"{INVENTORY_AGENT_URL}/query",
            json={"query": query},
            timeout=10,
        )
        if not response.ok:
            return [], f"Inventory agent returned {response.status_code}"
        data = response.json()
        items = data.get("items") or []
        return items, None
    except requests.exceptions.ConnectionError:
        return [], "Inventory agent not reachable (is it running on port 9005?)"
    except requests.exceptions.Timeout:
        return [], "Inventory agent timed out"
    except Exception as e:
        return [], str(e)[:120]


def get_out_of_stock_items(limit: int = 10) -> List[Dict]:
    """Get items with zero or negative stock (out of stock)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT inventory_id, item_name, category, opening_stock as remaining_stock,
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
                SELECT inventory_id, item_name, category, opening_stock as remaining_stock,
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
    """Get consumption history for an item (default: past 1 week for demand forecast)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
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
        return []


def calculate_forecasted_demand(consumption_history: List[Dict]) -> float:
    """Forecast demand for the next 1 week: daily rate from past 1 week of consumption (total / 7 days)."""
    if not consumption_history:
        return 0.0
    total_consumed = sum(float(h.get('quantity_consumed', 0) or 0) for h in consumption_history)
    if total_consumed <= 0:
        return 0.0
    # Past N days → daily rate = total / N (forecast for next week uses this daily rate)
    n_days = min(len(consumption_history), FORECAST_PAST_DAYS)
    if n_days == 0:
        return 0.0
    return total_consumed / FORECAST_PAST_DAYS


def call_decision_orchestrator(item: Dict, user_asked_about_waste: bool = False) -> Tuple[Optional[Dict], Optional[str]]:
    """Call the Decision Orchestrator Agent for an item. Returns (response_json, error_message).
    When user_asked_about_waste is True (e.g. 'What's going to waste?'), passes near_expiry intent
    so the orchestrator can suggest discount / sell or donate soon."""
    try:
        consumption_history = get_consumption_history(item['inventory_id'])
        forecasted_demand = calculate_forecasted_demand(consumption_history)
        
        # Determine stock signal
        remaining_stock = item.get('remaining_stock', 0)
        min_stock = item.get('min_stock', 10)
        
        if remaining_stock == 0:
            stock_signal = "critical"
        elif remaining_stock < min_stock:
            stock_signal = "low"
        else:
            stock_signal = "normal"
        
        # For waste/expiry queries, tell the orchestrator so it can suggest discount or sell/donate
        if user_asked_about_waste:
            event_type = "near_expiry"
            suggested_action = "none"
            context = {"user_asked_about_waste": True}
        else:
            event_type = "low_stock" if stock_signal != "normal" else "monitoring"
            suggested_action = "reorder" if stock_signal != "normal" else "none"
            context = {}
        
        payload = {
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
                "use": item.get('use'),
                "min_stock": min_stock,
                "max_capacity": item.get('max_capacity', 1000),
                "vendor_id": item.get('vendor_id'),
                "expiry_date": _serialize_date(item.get('expiry_date')),
                "selling_price": float(item.get('selling_price')) if item.get('selling_price') is not None else None,
            },
            "consumption_history": consumption_history[:10],
            "context": context,
        }
        
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
                min_stock, forecasted_demand, status, donation_info
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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


def _format_recommendation_line(item_name: str, recommendation: Dict, include_reason: bool = True) -> str:
    """Format a single recommendation for chat: action, discount %, bundle, discard + reason, explanation."""
    rec = recommendation.get("recommendation", {})
    action = rec.get("action", "none")
    priority = rec.get("priority", "Medium")
    reasoning = rec.get("reasoning", "")
    parts = [f"• {item_name}: {action.upper()} ({priority} priority)"]
    if reasoning:
        parts.append(f" — {reasoning[:120]}" + ("..." if len(reasoning) > 120 else ""))
    extras = []
    if rec.get("suggested_discount_percent") is not None:
        extras.append(f"Discount: {rec.get('suggested_discount_percent')}%")
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
        names = [str(fb.get("name", "")).strip() for fb in nearest_fb[:3] if fb.get("name")]
        if names:
            extras.append("Donate to: " + ", ".join(names))
    if extras:
        parts.append(" | " + ", ".join(extras))
    if include_reason:
        explanation = recommendation.get("explanation", {})
        if isinstance(explanation, dict) and explanation.get("explanation"):
            parts.append(f" Reason: {(explanation.get('explanation') or '')[:150]}" + ("..." if len(explanation.get("explanation", "")) > 150 else ""))
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
    (waste/near expiry, out of stock, low stock, overstock) with full recommendations:
    hold, discount %, bundle, discard + reason, using the full decision pipeline.
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

    # Process up to 2 items per category through the full decision pipeline (subagents: risk, feasibility, cost, explanation)
    categories = [
        ("Waste / Near expiry", near_expiry[:2], True),   # user_asked_about_waste=True
        ("Out of stock", out_of_stock[:2], False),
        ("Low stock", low_stock[:2], False),
        ("Overstock", overstock[:2], False),
    ]
    suggestions_saved = 0
    for label, items, waste_intent in categories:
        if not items:
            continue
        lines.append(f"**{label}**")
        for item in items:
            rec, err = call_decision_orchestrator(item, user_asked_about_waste=waste_intent)
            if err:
                lines.append(f"• {item.get('item_name', 'Item')}: Could not get recommendation — {err}")
                continue
            if rec:
                sid = save_suggestion("Proactive alert", item, rec)
                if sid:
                    suggestions_saved += 1
                lines.append(_format_recommendation_line(item.get("item_name", "Item"), rec, include_reason=True))
        lines.append("")

    if suggestions_saved > 0:
        lines.append(f"✅ {suggestions_saved} suggestion(s) saved. Check the Suggestions tab for details.")

    return {
        "answer": "\n".join(lines).replace("**", "").strip(),  # plain text for chat
        "suggestions_count": suggestions_saved,
    }


def process_chat_query(query: str, session_id: str = None) -> Dict:
    """Process a chat query: check inventory, call decision agent, store suggestions."""
    query_lower = query.lower().strip()
    query_tokens = [t for t in query.split() if t]
    
    # Check if this is a question that should trigger suggestions
    should_generate_suggestions = any(word in query_lower for word in [
        "suggest", "recommend", "what should", "what do", "check", "analyze",
        "low stock", "reorder", "need", "help"
    ])
    # Waste / expiry / donate / sell-soon triggers
    waste_trigger = any(word in query_lower for word in [
        "waste", "donate", "sell soon", "expir", "expiry", "going to waste",
        "sell or donate", "anything to sell", "anything to donate"
    ])
    if waste_trigger:
        should_generate_suggestions = True

    # Get items from Inventory Agent (single place that sees DB for user query).
    # Fall back to local DB if Inventory Agent is unavailable.
    items, inv_err = call_inventory_agent_query(query)
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
                items = []
        if not items and len(query_tokens) <= 3 and query_tokens:
            items_by_name = get_items_by_name(query.strip())
            if items_by_name:
                items = items_by_name
                should_generate_suggestions = True
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

    # When user asked about waste/expiry and we still have no items, try local near-expiry (e.g. agent returned [])
    if not items and waste_trigger:
        items = get_near_expiry_items(within_days=14)
    
    suggestions_generated = []
    answer_parts = []
    
    if should_generate_suggestions and items:
        answer_parts.append(f"I've analyzed your inventory and found {len(items)} item(s) that need attention.")
        answer_parts.append("Here are my recommendations:\n")
        errors = []

        # Process each item through decision orchestrator (pass waste intent for waste/expiry queries)
        for item in items[:10]:  # Limit to 10 items
            try:
                recommendation, err = call_decision_orchestrator(item, user_asked_about_waste=waste_trigger)
                if err:
                    errors.append(f"{item.get('item_name', item.get('inventory_id', '?'))}: {err}")
                    answer_parts.append(f"• {item.get('item_name', 'Item')}: Could not get recommendation — {err}")
                    continue
                if recommendation:
                    # Save suggestion to database
                    suggestion_id = save_suggestion(query, item, recommendation)
                    if suggestion_id:
                        suggestions_generated.append({
                            "item": item['item_name'],
                            "action": recommendation.get('recommendation', {}).get('action', 'none'),
                            "priority": recommendation.get('recommendation', {}).get('priority', 'Medium'),
                            "suggestion_id": suggestion_id
                        })
                        answer_parts.append(_format_recommendation_line(item['item_name'], recommendation, include_reason=True))
                    else:
                        errors.append(f"{item.get('item_name')}: Failed to save suggestion to database.")
                else:
                    errors.append(f"{item.get('item_name')}: No recommendation returned.")
            except Exception as e:
                logger.error(f"Error processing item {item.get('inventory_id')}: {e}")
                errors.append(f"{item.get('item_name', 'Item')}: {str(e)[:80]}")
                answer_parts.append(f"• {item.get('item_name', 'Item')}: Error — {str(e)[:80]}")

        if suggestions_generated:
            answer_parts.append(f"\n✅ Generated {len(suggestions_generated)} suggestion(s). Check the Suggestion Log to see all details.")
        elif errors:
            answer_parts.append("\n⚠️ No suggestions could be saved. Common causes: Decision Orchestrator not running (start it on port 9000), or subagents (risk, feasibility, cost, explanation) not running. Check server logs for details.")
        else:
            answer_parts.append("\nNo suggestions were generated for these items.")
    
    elif should_generate_suggestions and not items:
        # User asked to check/suggest but no items found (e.g. no low stock, empty DB, or item name not found)
        logger.info("Check/suggest requested but no items returned (empty list or DB issue). Showing inventory summary.")
        summary = _get_inventory_summary()
        total = summary.get("total_items", 0)
        low = summary.get("low_stock_count", 0)
        answer_parts.append("I've checked your inventory.")
        if total == 0:
            answer_parts.append("There are no items in your inventory yet.")
        elif waste_trigger:
            answer_parts.append("No items are near expiry in the next 14 days. To get discount, bundle, and donation suggestions, set expiry_date on items in your inventory.")
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
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
