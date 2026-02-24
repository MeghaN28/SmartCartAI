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
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-small-latest")

# Optional LLM for query intent (understand any phrasing; fallback to keyword logic if unavailable)
_llm = None
if MISTRAL_API_KEY:
    try:
        from langchain_mistralai import ChatMistralAI
        from langchain_core.output_parsers import JsonOutputParser
        _llm = ChatMistralAI(model=MISTRAL_MODEL, mistral_api_key=MISTRAL_API_KEY)
        logger.info("Inventory agent: Mistral LLM loaded for query understanding")
    except Exception as e:
        logger.warning("Inventory agent: Mistral not available for query understanding: %s", e)

# Single source of demand forecast: ETS only (shared with Chat agent)
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common.forecasting import forecast_demand as forecast_demand_ets, FORECAST_PAST_DAYS

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


# -----------------------------------------------------------------------------
# Query-based item lookup (for Chat Agent: low stock, expired, near expiring, waste, etc.)
# -----------------------------------------------------------------------------


def get_near_expiry_items(within_days: int = 14) -> List[dict]:
    """Get expired or near-expiry items (expiry in past or within within_days). Expired first, then soonest to expire (same as home page / chatbot)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT inventory_id, item_name, category, form, usage,
                       opening_stock AS remaining_stock, min_stock, max_capacity,
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
                SELECT inventory_id, item_name, category, opening_stock AS remaining_stock,
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


def get_items_by_name(search: str) -> List[dict]:
    """Get inventory items whose name contains the search term."""
    if not search or not search.strip():
        return []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        pattern = f"%{search.strip()}%"
        try:
            cur.execute("""
                SELECT inventory_id, item_name, category, form, usage,
                       opening_stock AS remaining_stock, min_stock, max_capacity,
                       vendor_id, expiry_date, selling_price
                FROM inventory
                WHERE item_name ILIKE %s
                ORDER BY opening_stock ASC
                LIMIT 20
            """, (pattern,))
        except Exception:
            conn.rollback()
            cur.execute("""
                SELECT inventory_id, item_name, category, opening_stock AS remaining_stock,
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


def get_out_of_stock_items(limit: int = 20) -> List[dict]:
    """Get items with zero or negative stock (out of stock / stock out)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT inventory_id, item_name, category, form, usage,
                       opening_stock AS remaining_stock, min_stock, max_capacity,
                       vendor_id, expiry_date, selling_price
                FROM inventory
                WHERE opening_stock <= 0
                ORDER BY opening_stock ASC
                LIMIT %s
            """, (limit,))
        except Exception:
            conn.rollback()
            cur.execute("""
                SELECT inventory_id, item_name, category, opening_stock AS remaining_stock,
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


def get_overstock_items(limit: int = 20) -> List[dict]:
    """Get items with stock at or above 90%% of max_capacity (overstock)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                SELECT inventory_id, item_name, category, form, usage,
                       opening_stock AS remaining_stock, min_stock, max_capacity,
                       vendor_id, expiry_date, selling_price
                FROM inventory
                WHERE max_capacity IS NOT NULL AND max_capacity > 0
                  AND opening_stock >= max_capacity * 0.9
                ORDER BY opening_stock DESC
                LIMIT %s
            """, (limit,))
        except Exception:
            conn.rollback()
            cur.execute("""
                SELECT inventory_id, item_name, category, opening_stock AS remaining_stock,
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


def get_items_needing_attention(query: str) -> List[dict]:
    """Get inventory items that need attention based on the user query (low stock, check all, etc.)."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query_lower = query.lower()
        sel_ext = (
            "SELECT inventory_id, item_name, category, form, usage, opening_stock AS remaining_stock, "
            "min_stock, max_capacity, vendor_id, expiry_date, selling_price FROM inventory"
        )
        sel_base = (
            "SELECT inventory_id, item_name, category, opening_stock AS remaining_stock, "
            "min_stock, max_capacity, vendor_id FROM inventory"
        )
        if any(w in query_lower for w in ["low stock", "low in stock", "reorder", "suggest", "recommend", "near stockout", "near to stockout", "stockout"]):
            q = " WHERE opening_stock <= min_stock ORDER BY opening_stock ASC LIMIT 20"
        elif any(w in query_lower for w in ["all", "everything", "check"]):
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
        logger.error(f"Error getting items needing attention: {e}")
        return []


def _enrich_items_with_forecast(items: List[dict]) -> None:
    """Add ETS forecasted_demand to each item; floor with demand.predicted_demand from DB so demand can be boosted."""
    for item in items:
        inv_id = item.get("inventory_id")
        if not inv_id:
            continue
        history = fetch_consumption_history(inv_id)
        ets = forecast_demand_ets(history)
        floor = fetch_demand_floor(inv_id)
        item["forecasted_demand"] = max(ets, floor)


def _classify_query_intent_with_llm(query: str) -> Optional[Dict]:
    """
    Use LLM to classify user intent so any natural phrasing is understood (no keyword lists).
    Returns {"intent": "near_expiry"|"low_stock"|"out_of_stock"|"overstock"|"demand"|"stock_status"|"by_name", "product_names": [...] or null}
    or None if LLM unavailable/fails.
    """
    if not _llm:
        return None
    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_core.output_parsers import JsonOutputParser
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an inventory query classifier. Classify the user's intent into exactly one of:
- near_expiry: items going to waste, expiring soon, near expiry, donate, sell soon, going bad, about to expire
- low_stock: need reorder, low stock, running low, suggest reorder
- out_of_stock: out of stock, stockout, zero stock
- overstock: overstock, excess stock, too much stock
- demand: demand forecast, next week demand, predict demand
- stock_status: in stock, current stock, stock level, what do we have
- by_name: asking about specific product(s) by name (e.g. apple, milk, banana)

If the user mentions specific product names (e.g. "apple and banana", "milk"), set intent to by_name and list them in product_names as a JSON array of strings. Otherwise product_names is null.

Reply with only valid JSON, no markdown: {"intent": "<one of the above>", "product_names": ["name1", "name2"] or null}"""),
            ("user", "{query}"),
        ])
        chain = prompt | _llm | JsonOutputParser()
        out = chain.invoke({"query": query.strip()})
        if isinstance(out, dict) and out.get("intent") in (
            "near_expiry", "low_stock", "out_of_stock", "overstock", "demand", "stock_status", "by_name"
        ):
            return out
    except Exception as e:
        logger.debug("LLM intent classification failed: %s", e)
    return None


def _extract_item_name_for_stock_or_demand(query: str) -> Optional[str]:
    """Extract product name from 'stock for X', 'tock for X' (typo), 'demand for X', 'forecast demand for X'."""
    q = query.strip().rstrip("?.!,")
    if not q:
        return None
    q_lower = q.lower()
    for prefix in ("stock for ", "tock for ", "demand for ", "forecast demand for "):
        if prefix in q_lower:
            name = q_lower.split(prefix, 1)[-1].strip()
            name = name.split()[0] if name else None  # single product name
            return name if (name and len(name) < 50) else None
    return None


def _extract_item_name_from_waste_query(query: str) -> Optional[str]:
    """Extract a likely item name from a waste-related query, e.g. 'is milk 1l going on waste' -> 'milk 1l'."""
    waste_stopwords = {
        "is", "going", "to", "waste", "on", "whats", "what", "the", "any", "anything",
        "sell", "donate", "soon", "expir", "expiry", "expiring", "for", "me", "my",
    }
    tokens = [t for t in query.split() if t]
    # Take longest contiguous run of non-stopwords (likely the product name)
    best = []
    current = []
    for t in tokens:
        if t.lower() in waste_stopwords:
            if len(current) > len(best):
                best = current
            current = []
        else:
            current.append(t)
    if len(current) > len(best):
        best = current
    return " ".join(best).strip() or None


def query_inventory_for_user(query: str) -> Dict:
    """
    Interpret user query and return matching items from the database.
    Uses LLM to understand any natural phrasing (e.g. "near expiry items", "what's going on waste");
    falls back to keyword logic if LLM unavailable.
    Each item includes forecasted_demand (ETS). Returns {"items": [...], "query_type": "..."}.
    """
    query_lower = query.lower().strip()
    query_tokens = [t for t in query.split() if t]

    # "stock for Apple" / "tock for Apple" (typo) / "demand for X" – always look up by name first (reliable, no LLM)
    stock_or_demand_name = _extract_item_name_for_stock_or_demand(query)
    if stock_or_demand_name:
        items = get_items_by_name(stock_or_demand_name)
        if items is not None:
            _enrich_items_with_forecast(items)
            query_type = "demand" if ("demand" in query_lower or "forecast" in query_lower) else "by_name"
            return {"items": items, "query_type": query_type}

    # LLM-based intent: understand any user phrasing without keyword lists
    llm_result = _classify_query_intent_with_llm(query)
    if llm_result:
        intent = llm_result.get("intent")
        product_names = llm_result.get("product_names")
        if intent == "near_expiry":
            items = get_near_expiry_items(within_days=14)
            if not items and product_names:
                seen = set()
                merged = []
                for name in product_names[:10]:
                    for it in get_items_by_name(name) or []:
                        if it.get("inventory_id") not in seen:
                            seen.add(it.get("inventory_id"))
                            merged.append(it)
                items = merged
            _enrich_items_with_forecast(items)
            return {"items": items, "query_type": "near_expiry"}
        if intent == "out_of_stock":
            items = get_out_of_stock_items(limit=20)
            _enrich_items_with_forecast(items)
            return {"items": items, "query_type": "out_of_stock"}
        if intent == "overstock":
            items = get_overstock_items(limit=20)
            _enrich_items_with_forecast(items)
            return {"items": items, "query_type": "overstock"}
        if intent == "demand":
            items = get_items_needing_attention(query)
            if not items:
                try:
                    conn = get_db_connection()
                    cur = conn.cursor()
                    try:
                        cur.execute("""SELECT inventory_id, item_name, category, form, usage,
                            opening_stock AS remaining_stock, min_stock, max_capacity, vendor_id, expiry_date, selling_price
                            FROM inventory ORDER BY opening_stock ASC LIMIT 30""", ())
                    except Exception:
                        conn.rollback()
                        cur.execute("""SELECT inventory_id, item_name, category, opening_stock AS remaining_stock,
                            min_stock, max_capacity, vendor_id FROM inventory ORDER BY opening_stock ASC LIMIT 30""", ())
                    items = [dict(row) for row in cur.fetchall()]
                    cur.close()
                    conn.close()
                except Exception:
                    items = []
            _enrich_items_with_forecast(items)
            return {"items": items, "query_type": "demand"}
        if intent == "stock_status":
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("""SELECT inventory_id, item_name, category, form, usage,
                        opening_stock AS remaining_stock, min_stock, max_capacity, vendor_id, expiry_date, selling_price
                        FROM inventory WHERE opening_stock > 0 ORDER BY opening_stock ASC LIMIT 30""", ())
                except Exception:
                    conn.rollback()
                    cur.execute("""SELECT inventory_id, item_name, category, opening_stock AS remaining_stock,
                        min_stock, max_capacity, vendor_id FROM inventory WHERE opening_stock > 0 ORDER BY opening_stock ASC LIMIT 30""", ())
                items = [dict(row) for row in cur.fetchall()]
                cur.close()
                conn.close()
            except Exception:
                items = []
            _enrich_items_with_forecast(items)
            return {"items": items, "query_type": "stock_status"}
        if intent == "by_name" and product_names:
            seen = set()
            merged = []
            for name in product_names[:10]:
                for it in get_items_by_name(name) or []:
                    if it.get("inventory_id") not in seen:
                        seen.add(it.get("inventory_id"))
                        merged.append(it)
            if merged:
                _enrich_items_with_forecast(merged)
                return {"items": merged, "query_type": "by_name"}
        if intent == "low_stock":
            items = get_items_needing_attention(query)
            _enrich_items_with_forecast(items)
            return {"items": items, "query_type": "low_stock"}

    # Fallback: keyword-based logic when LLM unavailable or intent not fully resolved
    # Out of stock / stock out
    if any(w in query_lower for w in ["out of stock", "stock out", "stockout", "out-of-stock", "zero stock"]):
        items = get_out_of_stock_items(limit=20)
        _enrich_items_with_forecast(items)
        return {"items": items, "query_type": "out_of_stock"}

    # Overstock
    if any(w in query_lower for w in ["overstock", "over stock", "excess stock", "too much stock"]):
        items = get_overstock_items(limit=20)
        _enrich_items_with_forecast(items)
        return {"items": items, "query_type": "overstock"}

    # Stock status / in stock / current stock
    if any(w in query_lower for w in ["in stock", "stock level", "current stock", "stock status", "how much stock"]):
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            try:
                cur.execute("""
                    SELECT inventory_id, item_name, category, form, usage,
                           opening_stock AS remaining_stock, min_stock, max_capacity,
                           vendor_id, expiry_date, selling_price
                    FROM inventory
                    WHERE opening_stock > 0
                    ORDER BY opening_stock ASC
                    LIMIT 30
                """, ())
            except Exception:
                conn.rollback()
                cur.execute("""
                    SELECT inventory_id, item_name, category, opening_stock AS remaining_stock,
                           min_stock, max_capacity, vendor_id
                    FROM inventory
                    WHERE opening_stock > 0
                    ORDER BY opening_stock ASC
                    LIMIT 30
                """, ())
            items = [dict(row) for row in cur.fetchall()]
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Error getting in-stock items: {e}")
            items = []
        _enrich_items_with_forecast(items)
        return {"items": items, "query_type": "stock_status"}

    # Demand for next week / demand forecast
    if any(w in query_lower for w in ["demand", "demand for next week", "forecast", "next week demand"]):
        items = get_items_needing_attention(query)
        if not items:
            # Return top items by consumption or all with limit
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                try:
                    cur.execute("""
                        SELECT inventory_id, item_name, category, form, usage,
                               opening_stock AS remaining_stock, min_stock, max_capacity,
                               vendor_id, expiry_date, selling_price
                        FROM inventory ORDER BY opening_stock ASC LIMIT 30
                    """, ())
                except Exception:
                    conn.rollback()
                    cur.execute("""
                        SELECT inventory_id, item_name, category, opening_stock AS remaining_stock,
                               min_stock, max_capacity, vendor_id FROM inventory ORDER BY opening_stock ASC LIMIT 30
                    """, ())
                items = [dict(row) for row in cur.fetchall()]
                cur.close()
                conn.close()
            except Exception as e:
                logger.error(f"Error getting items for demand query: {e}")
                items = []
        _enrich_items_with_forecast(items)
        return {"items": items, "query_type": "demand"}

    # Waste / expiry / donate / sell-soon
    waste_trigger = any(w in query_lower for w in [
        "waste", "donate", "sell soon", "expir", "expiry", "going to waste",
        "sell or donate", "anything to sell", "anything to donate", "whats going to waste"
    ])
    if waste_trigger:
        near_expiry = get_near_expiry_items(within_days=14)
        # If user asked about a specific item (e.g. "is milk 1l going on waste"), find by name even if no expiry
        if not near_expiry:
            item_name = _extract_item_name_from_waste_query(query)
            if item_name:
                by_name = get_items_by_name(item_name)
                if by_name:
                    _enrich_items_with_forecast(by_name)
                    return {"items": by_name, "query_type": "near_expiry"}
            # Try tokens as item name: longest first so "milk" is tried before "can" (avoids matching "Soda Can")
            stopwords = {"is", "going", "to", "waste", "on", "whats", "what", "the", "any", "sell", "donate", "soon"}
            skip_generic = {"can", "we", "it", "or", "be", "do", "go"}  # often match wrong products (e.g. "can" -> Soda Can)
            candidates = [t for t in query_tokens if len(t) > 1 and t.lower() not in stopwords and t.lower() not in skip_generic]
            candidates.sort(key=lambda t: -len(t))  # longest first
            for token in candidates:
                by_name = get_items_by_name(token)
                if by_name:
                    _enrich_items_with_forecast(by_name)
                    return {"items": by_name, "query_type": "near_expiry"}
            # Fallback: if no expiry dates are set on ANY items, return items with low stock or items that could waste soon
            # This ensures users get actionable suggestions even when expiry dates are not populated
            try:
                conn = get_db_connection()
                cur = conn.cursor()
                try:
                    # Get items with low stock (at risk of waste if unsold) or items with expiry date not yet set (could set and track)
                    cur.execute("""
                        SELECT inventory_id, item_name, category, form, usage,
                               opening_stock AS remaining_stock, min_stock, max_capacity,
                               vendor_id, expiry_date, selling_price
                        FROM inventory
                        WHERE opening_stock > 0
                        ORDER BY opening_stock ASC, max_capacity DESC
                        LIMIT 15
                    """, ())
                except Exception:
                    conn.rollback()
                    cur.execute("""
                        SELECT inventory_id, item_name, category, opening_stock AS remaining_stock,
                               min_stock, max_capacity, vendor_id
                        FROM inventory
                        WHERE opening_stock > 0
                        ORDER BY opening_stock ASC
                        LIMIT 15
                    """, ())
                near_expiry = [dict(row) for row in cur.fetchall()]
                cur.close()
                conn.close()
            except Exception as e:
                logger.warning(f"Fallback waste query returned no items: {e}")
                near_expiry = []
        _enrich_items_with_forecast(near_expiry)
        return {"items": near_expiry, "query_type": "near_expiry"}

    # Multi-item: "apple and banana" or "apple, banana" or "suggest for apple and banana" – get items for each name and merge
    if " and " in query_lower or ", " in query_lower:
        from re import split as re_split
        parts = re_split(r"\s+and\s+|\s*,\s*", query_lower)
        parts = [p.strip() for p in parts if len(p.strip()) > 0]
        stopwords = {"suggest", "recommend", "for", "what", "do", "the", "me", "give", "check", "analyze", "you"}
        part_names = []
        for p in parts:
            tokens = [t for t in p.split() if t and t not in stopwords]
            if tokens:
                part_names.append(tokens[-1])  # take last token of segment (e.g. "apple" from "what do you suggest for apple")
        if part_names:
            seen_ids = set()
            merged = []
            for name in part_names:
                by_name = get_items_by_name(name)
                for it in by_name or []:
                    if it.get("inventory_id") not in seen_ids:
                        seen_ids.add(it.get("inventory_id"))
                        merged.append(it)
            if merged:
                _enrich_items_with_forecast(merged)
                return {"items": merged, "query_type": "by_name"}

    # Default: items needing attention (low stock, suggest, recommend, check)
    items = get_items_needing_attention(query)

    # If query looks like an item name and we got nothing, look up by name
    if not items and len(query_tokens) <= 3 and query_tokens:
        items_by_name = get_items_by_name(query.strip())
        if items_by_name:
            _enrich_items_with_forecast(items_by_name)
            return {"items": items_by_name, "query_type": "by_name"}

    # "Check X and suggest" – try to find item by name from tokens
    if not items and len(query_tokens) >= 2:
        stopwords = {
            "check", "inventory", "and", "suggest", "actions", "what", "items", "need",
            "reorder", "for", "my", "the", "me", "please", "analyze", "give", "recommendations",
            "going", "waste", "sell", "donate", "soon", "anything", "should", "to",
        }
        for token in query_tokens:
            if len(token) > 2 and token.lower() not in stopwords:
                items_by_name = get_items_by_name(token)
                if items_by_name:
                    _enrich_items_with_forecast(items_by_name)
                    return {"items": items_by_name, "query_type": "by_name"}

    query_type = "check" if any(w in query_lower for w in ["all", "everything", "check"]) else "low_stock"
    _enrich_items_with_forecast(items)
    return {"items": items, "query_type": query_type}


def fetch_demand_floor(inventory_id: str) -> float:
    """Return daily demand floor from demand table (predicted_demand). Used as min forecast so DB can boost demand."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT predicted_demand FROM demand
            WHERE inventory_id = %s
            ORDER BY prediction_date DESC NULLS LAST
            LIMIT 1
            """,
            (inventory_id,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row.get("predicted_demand") is not None:
            return float(row["predicted_demand"])
    except Exception as e:
        logger.debug(f"Demand floor not available for {inventory_id}: {e}")
    return 0.0


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
    
    # Forecast demand (ETS only – same as common.forecasting)
    forecasted_demand = forecast_demand_ets(consumption_history)
    
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
    forecasted_demand = forecast_demand_ets(consumption_history)
    forecast_next_week_total = round(forecasted_demand * FORECAST_PAST_DAYS, 2)
    
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


@app.route("/query", methods=["POST"])
def query():
    """
    Accept a user query and return items from the database that match the intent.
    Used by the Chat Agent: inventory-agent is the single place that sees the DB
    for user queries (low stock, expired, near expiring, waste, etc.).
    """
    payload = request.get_json(silent=True) or {}
    user_query = (payload.get("query") or payload.get("message") or "").strip()
    if not user_query:
        return jsonify({"items": [], "query_type": "none", "error": "query is required"}), 400
    result = query_inventory_for_user(user_query)
    return jsonify(result), 200


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
