"""Decision Orchestrator Agent – Coordinates sub-agents for prescriptive inventory interventions.

Uses LangChain/LangGraph for multi-agent reasoning and retrieval workflows.
Integrates Mistral LLM for contextual reasoning and prescriptive recommendations.
Implements RAG with PostgreSQL for evidence-based decisions and explanations.
"""
import os
import logging
from typing import TypedDict, List, Dict, Optional, Literal
from datetime import datetime
from pathlib import Path

import requests
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify
from langchain_core.prompts import ChatPromptTemplate
from langchain_mistralai import ChatMistralAI
from langchain_core.output_parsers import JsonOutputParser
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
logger = logging.getLogger("decision-orchestrator")

# Configuration
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-medium")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "smartcart_ai")
DB_USER = os.getenv("DB_USER", "meghanarendrasimha")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Welcome@123")

# Subagent URLs
SUBAGENT_URLS = {
    "risk": os.getenv("RISK_AGENT_URL", "http://localhost:9004/risk"),
    "feasibility": os.getenv("FEASIBILITY_AGENT_URL", "http://localhost:9001/feasibility"),
    "cost_impact": os.getenv("COST_IMPACT_AGENT_URL", "http://localhost:9002/cost-impact"),
    "explanation": os.getenv("EXPLANATION_AGENT_URL", "http://localhost:9003/explain"),
    "food_bank": os.getenv("FOOD_BANK_AGENT_URL", "http://localhost:9007/nearest"),
}

# MCP Server
mcp = FastMCP("Decision Orchestrator Agent")

# Initialize Mistral LLM
llm = None
if MISTRAL_API_KEY:
    try:
        llm = ChatMistralAI(model=MISTRAL_MODEL, mistral_api_key=MISTRAL_API_KEY)
        logger.info("Mistral LLM initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize Mistral LLM: {e}. Some features may be limited.")


# -----------------------------------------------------------------------------
# State Schema
# -----------------------------------------------------------------------------


class DecisionOrchestratorState(TypedDict, total=False):
    """State passed through the decision orchestration graph."""
    
    # Input
    inventory_id: str
    event_type: str
    remaining_stock: int
    suggested_action: str
    stock_signal: str
    consumption_signal: str
    forecasted_demand: Optional[float]
    item_data: dict
    consumption_history: List[dict]
    context: dict
    
    # Subagent Results
    risk_assessment: dict
    feasibility_check: dict
    cost_impact: dict
    nearest_food_banks: List[dict]  # when discard/donate: for donation suggestion
    explanation: dict
    
    # Final Output
    recommendation: dict
    error: str


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def strip_markdown(text: str) -> str:
    """Remove markdown formatting so output is plain text (no **, #, etc.) for chat and suggestion tab."""
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


# -----------------------------------------------------------------------------
# Database Utilities for RAG
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


def _ensure_embedding_floats(emb) -> List[float]:
    """Convert embedding from DB (list, array, or JSON string) to list of floats. Avoids 'can't multiply sequence by non-int of type str'."""
    if emb is None:
        return []
    if isinstance(emb, str):
        try:
            import json
            emb = json.loads(emb)
        except Exception:
            return []
    if not hasattr(emb, "__iter__") or isinstance(emb, str):
        return []
    out = []
    for x in emb:
        try:
            out.append(float(x))
        except (TypeError, ValueError):
            pass
    return out


def _cosine_sim(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two embedding vectors (pure Python, no numpy)."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def retrieve_similar_items_by_embedding(inventory_id: str, limit: int = 5) -> List[Dict]:
    """Retrieve inventory items most similar by embedding; include past suggestions for evidence."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT embedding FROM inventory WHERE inventory_id = %s AND embedding IS NOT NULL",
            (inventory_id,),
        )
        row = cur.fetchone()
        if not row or not row.get("embedding"):
            cur.close()
            conn.close()
            return []
        current_embedding = _ensure_embedding_floats(row.get("embedding"))
        if not current_embedding:
            cur.close()
            conn.close()
            return []

        cur.execute(
            """
            SELECT inventory_id, item_name, embedding, min_stock, opening_stock, category
            FROM inventory
            WHERE embedding IS NOT NULL AND inventory_id != %s
            """,
            (inventory_id,),
        )
        others = [dict(r) for r in cur.fetchall()]
        cur.close()
        conn.close()

        scored = []
        for r in others:
            emb_list = _ensure_embedding_floats(r.get("embedding"))
            if not emb_list or len(emb_list) != len(current_embedding):
                continue
            sim = _cosine_sim(current_embedding, emb_list)
            scored.append(({**r, "similarity": round(sim, 4)}, sim))
        scored.sort(key=lambda x: -x[1])
        top = [x[0] for x in scored[:limit]]

        if not top:
            return []

        # Fetch past suggestions for similar items (evidence for recommendation)
        conn = get_db_connection()
        cur = conn.cursor()
        ids = [t["inventory_id"] for t in top]
        placeholders = ",".join(["%s"] * len(ids))
        cur.execute(
            f"""
            SELECT inventory_id, action, priority, reasoning, expected_outcome, created_at
            FROM suggestions
            WHERE inventory_id IN ({placeholders})
            ORDER BY created_at DESC
            """,
            tuple(ids),
        )
        suggestions_by_id = {}
        for r in cur.fetchall():
            d = dict(r)
            inv_id = d.pop("inventory_id")
            if inv_id not in suggestions_by_id:
                suggestions_by_id[inv_id] = []
            suggestions_by_id[inv_id].append(d)
        cur.close()
        conn.close()

        for t in top:
            t["past_suggestions"] = suggestions_by_id.get(t["inventory_id"], [])[:3]
        return top
    except Exception as e:
        logger.error(f"Error retrieving similar items by embedding: {e}")
        return []


def retrieve_historical_context(inventory_id: str) -> Dict:
    """Retrieve historical inventory and consumption data for RAG."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get inventory details
        cur.execute("SELECT * FROM inventory WHERE inventory_id = %s", (inventory_id,))
        inventory = cur.fetchone()
        
        # Get recent consumption
        cur.execute(
            """
            SELECT transaction_date as date, quantity_consumed, remaining_stock, department, consumption_reason
            FROM consumption
            WHERE inventory_id = %s
            ORDER BY transaction_date DESC
            LIMIT 20
            """,
            (inventory_id,)
        )
        consumption = [dict(row) for row in cur.fetchall()]
        
        # Get recent sales
        cur.execute(
            """
            SELECT purchase_date, quantity, unit_cost, total_cost
            FROM sales
            WHERE inventory_id = %s
            ORDER BY purchase_date DESC
            LIMIT 10
            """,
            (inventory_id,)
        )
        sales = [dict(row) for row in cur.fetchall()]
        
        cur.close()
        conn.close()
        
        return {
            "inventory": dict(inventory) if inventory else {},
            "consumption": consumption,
            "sales": sales,
        }
    except Exception as e:
        logger.error(f"Error retrieving historical context: {e}")
        return {"inventory": {}, "consumption": [], "sales": []}


def retrieve_bundle_candidates(inventory_id: str, item_data: Dict, limit: int = 10) -> List[Dict]:
    """Retrieve other inventory items that can be bundled with this item (same category, form, or use)."""
    try:
        category = (item_data.get("category") or "").strip()
        form = (item_data.get("form") or "").strip()
        use = (item_data.get("usage") or item_data.get("use") or "").strip()
        conn = get_db_connection()
        cur = conn.cursor()
        # Get other items: same category, or same form, or same use; has stock; exclude self
        conditions = ["inventory_id != %s", "COALESCE(opening_stock, 0) > 0"]
        args = [inventory_id]
        if category or form or use:
            parts = []
            if category:
                parts.append("(category IS NOT NULL AND TRIM(category) = %s)")
                args.append(category)
            if form:
                parts.append("(form IS NOT NULL AND TRIM(form) = %s)")
                args.append(form)
            if use:
                parts.append("(usage IS NOT NULL AND TRIM(usage) = %s)")
                args.append(use)
            if parts:
                conditions.append("(" + " OR ".join(parts) + ")")
        cur.execute(
            """
            SELECT inventory_id, item_name, category, form, usage, opening_stock
            FROM inventory
            WHERE """ + " AND ".join(conditions) + """
            ORDER BY
                CASE WHEN category IS NOT NULL AND TRIM(category) = %s THEN 0 ELSE 1 END,
                CASE WHEN form IS NOT NULL AND TRIM(form) = %s THEN 0 ELSE 1 END,
                COALESCE(opening_stock, 0) DESC
            LIMIT %s
            """,
            args + [category, form, limit],
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error retrieving bundle candidates: {e}")
        return []


# Intervention priority thresholds (waste / near-expiry)
DISCOUNT_EXPIRY_THRESHOLD = 14
BUNDLE_EXPIRY_THRESHOLD = 14
DONATION_THRESHOLD = 7
MAX_DISCOUNT_LIMIT = 50
BASE_DISCOUNT = 10
# Donation rules
SURPLUS_FOR_DONATION = 20  # units
LOW_DEMAND_THRESHOLD = 1.0  # units/day

# Explicit waste rules (priority order: DONATE only when surplus very high, else BUNDLE when low+similar, else DISCOUNT when demand good)
# DONATE only when we clearly can't sell in time (very high surplus). Otherwise DISCOUNT when demand is good.
LOT_VERY_HIGH_SURPLUS_ONLY = 80   # surplus >= this → DONATE (can't sell in time)
LOT_VERY_HIGH_STOCK_AND_SURPLUS = (150, 30)  # (stock >= 150 and surplus >= 30) → DONATE
LOT_LOW_MAX_STOCK = 22   # stock <= this with similar items → BUNDLE (low stock)
LOT_BUNDLE_STOCK_MIN, LOT_BUNDLE_STOCK_MAX = 20, 320   # stock in this range + similar items → BUNDLE
LOT_MEDIUM_MIN_STOCK = 5
MEDIUM_DEMAND_THRESHOLD = 2.0  # forecasted_demand >= this → "demand is more", use DISCOUNT (no stock ceiling so high stock + demand still gets DISCOUNT)
# HOLD: when demand will clear stock (surplus strongly negative) → no urgent action, monitor
SURPLUS_COMFORTABLE = -80   # surplus <= this (demand > stock) → HOLD
# When forecast is missing/zero, assume this daily demand so surplus is not entire stock (avoids everything → DONATE)
DEFAULT_DAILY_DEMAND_WHEN_MISSING = 25.0
# When expiry not set, use this many days for demand_before_expiry so surplus is meaningful
DEFAULT_EXPIRY_DAYS_WHEN_MISSING = 14
# Very high stock (absolute) → DONATE to get variety (not everything DISCOUNT)
LOT_VERY_HIGH_ABSOLUTE_STOCK = 380  # stock >= this → DONATE even if demand is good (clear space / social impact)


def _urgency_factor(expiry_days_remaining: Optional[int]) -> float:
    """Urgency increases as days until expiry decrease."""
    if expiry_days_remaining is None or expiry_days_remaining > DISCOUNT_EXPIRY_THRESHOLD:
        return 0.0
    if expiry_days_remaining > 7:
        return 2.0
    if expiry_days_remaining > 4:
        return 5.0
    if expiry_days_remaining > 1:
        return 10.0
    if expiry_days_remaining > 0:
        return 15.0
    return 18.0  # expired or today


def _surplus_factor(remaining_stock: int, forecasted_demand_before_expiry: float) -> float:
    """Surplus factor based on excess stock over expected demand before expiry."""
    surplus = remaining_stock - forecasted_demand_before_expiry
    if surplus <= 0:
        return 0.0
    if surplus <= 20:
        return 2.0
    if surplus <= 50:
        return 5.0
    if surplus <= 100:
        return 8.0
    return 12.0


def compute_discount_from_expiry(
    days_until_expiry: Optional[int],
    selling_price: Optional[float],
    remaining_stock: int = 0,
    forecasted_demand: Optional[float] = None,
) -> tuple:
    """
    Compute discount % and suggested price using dynamic formula:
    discount_percent = min(max_discount_limit, base_discount + urgency_factor + surplus_factor).
    Returns (discount_percent, suggested_price).
    """
    try:
        sp = float(selling_price) if selling_price is not None else None
    except (TypeError, ValueError):
        sp = None
    if days_until_expiry is None or days_until_expiry > DISCOUNT_EXPIRY_THRESHOLD:
        return 0, (sp if sp is not None else None)
    daily_demand = float(forecasted_demand) if forecasted_demand is not None else 0.0
    demand_before_expiry = daily_demand * max(0, min(days_until_expiry, DISCOUNT_EXPIRY_THRESHOLD))
    urgency = _urgency_factor(days_until_expiry)
    surplus = _surplus_factor(remaining_stock, demand_before_expiry)
    raw_pct = BASE_DISCOUNT + urgency + surplus
    pct = int(round(min(MAX_DISCOUNT_LIMIT, max(0, raw_pct))))
    suggested = round(sp * (1 - pct / 100.0), 2) if sp is not None and sp > 0 else None
    return pct, suggested


def pick_one_waste_suggestion(
    risk_assessment: dict,
    feasibility_check: dict,
    cost_impact: dict,
    nearest_food_banks: List[dict],
    bundle_candidates: List[dict],
    similar_items: List[dict],
    remaining_stock: int,
    days_until_expiry: Optional[int],
    item_name: str,
    forecasted_demand: Optional[float],
    selling_price: Optional[float],
) -> tuple:
    """
    Select EXACTLY ONE intervention using explicit rules (priority order):
    1. Lot very high → DONATE (excess stock cannot be sold in time)
    2. Lot a little less + similar items in lot → BUNDLE (low/moderate stock, bundle with similar)
    3. Lot medium + demand is more → DISCOUNT (good demand, discount to clear)
    Returns (action_key, reasoning, expected_outcome, rec_overrides).
    """
    is_feasible = (feasibility_check or {}).get("is_feasible", True)
    within_budget = (cost_impact or {}).get("within_budget", True)
    item_sellable = is_feasible

    # Use default demand when missing so surplus isn't entire stock (avoids everything → DONATE)
    daily_demand = float(forecasted_demand) if forecasted_demand is not None and forecasted_demand > 0 else DEFAULT_DAILY_DEMAND_WHEN_MISSING
    days_for_demand = (days_until_expiry if days_until_expiry is not None else DEFAULT_EXPIRY_DAYS_WHEN_MISSING)
    demand_before_expiry = daily_demand * max(0, min(days_for_demand, DISCOUNT_EXPIRY_THRESHOLD))
    has_expiry_urgency = days_until_expiry is not None and days_until_expiry <= DISCOUNT_EXPIRY_THRESHOLD
    has_high_stock = remaining_stock > 0
    surplus_qty = remaining_stock - demand_before_expiry

    # Classify lot level: DONATE only when surplus is very high (can't sell in time)
    stock_ge, surplus_ge = LOT_VERY_HIGH_STOCK_AND_SURPLUS
    lot_very_high = (
        surplus_qty >= LOT_VERY_HIGH_SURPLUS_ONLY
        or (remaining_stock >= stock_ge and surplus_qty >= surplus_ge)
    )
    lot_low_or_less = remaining_stock <= LOT_LOW_MAX_STOCK
    lot_bundle_range = LOT_BUNDLE_STOCK_MIN <= remaining_stock <= LOT_BUNDLE_STOCK_MAX  # moderate stock + similar → BUNDLE
    lot_medium = remaining_stock >= LOT_MEDIUM_MIN_STOCK  # no upper cap so "medium + demand" includes high stock with good demand
    demand_is_more = daily_demand >= MEDIUM_DEMAND_THRESHOLD
    surplus_comfortable = surplus_qty <= SURPLUS_COMFORTABLE  # demand will clear stock → HOLD

    compatible_items = similar_items if similar_items else bundle_candidates
    compatible_items = [c for c in (compatible_items or []) if c.get("item_name")]
    has_similar_in_lot = len(compatible_items) > 0

    discount_pct, computed_suggested_price = compute_discount_from_expiry(
        days_until_expiry, selling_price, remaining_stock, forecasted_demand
    )
    if computed_suggested_price is None and selling_price is not None and selling_price > 0 and discount_pct > 0:
        try:
            computed_suggested_price = round(float(selling_price) * (1 - discount_pct / 100.0), 2)
        except (TypeError, ValueError):
            computed_suggested_price = None

    # --- Rule 1a: Very high surplus → DONATE (can't sell in time) ---
    if lot_very_high and within_budget and (nearest_food_banks or []):
        fb = nearest_food_banks[0]
        name = (fb.get("name") or "nearest food bank").strip()
        addr = (fb.get("address") or "").strip()
        reasoning = (
            f"Lot is very high (stock {remaining_stock}, surplus over demand {max(0, int(surplus_qty))}). "
            f"Donating {item_name} to {name} minimizes waste and provides social value."
        )
        if addr:
            reasoning += f" Donate to: {name}, {addr}."
        expected_outcome = "Zero waste and social value through donation."
        return (
            "donate",
            reasoning,
            expected_outcome,
            {
                "suggested_discount_percent": None,
                "suggested_selling_price": None,
                "bundle_suggestion": None,
                "nearest_food_banks": [fb],
            },
        )

    # --- Rule 1b: Very high stock (absolute) → DONATE for variety (e.g. 400+ units; donate to clear space) ---
    if remaining_stock >= LOT_VERY_HIGH_ABSOLUTE_STOCK and within_budget and (nearest_food_banks or []):
        fb = nearest_food_banks[0]
        name = (fb.get("name") or "nearest food bank").strip()
        addr = (fb.get("address") or "").strip()
        reasoning = (
            f"Stock is very high ({remaining_stock} units). Donating part of {item_name} to {name} frees space and reduces waste risk while supporting the community."
        )
        if addr:
            reasoning += f" Donate to: {name}, {addr}."
        expected_outcome = "Zero waste and social value through donation; inventory space freed."
        return (
            "donate",
            reasoning,
            expected_outcome,
            {
                "suggested_discount_percent": None,
                "suggested_selling_price": None,
                "bundle_suggestion": None,
                "nearest_food_banks": [fb],
            },
        )

    # --- Rule 2: Moderate stock + similar items in lot → BUNDLE ---
    if lot_bundle_range and has_similar_in_lot and item_sellable and within_budget:
        first = compatible_items[0]
        bundle_item_name = (first.get("item_name") or "complementary item").strip()
        similarity = first.get("similarity")
        compat_reason = f"similarity {similarity:.2f}" if similarity is not None else "complementary category or usage"
        reasoning = (
            f"Stock is in a good range for bundling ({remaining_stock} units) and similar items are available. "
            f"{item_name} pairs well with {bundle_item_name} ({compat_reason}). "
            f"Bundle with {bundle_item_name} to increase sell-through and reduce waste."
        )
        expected_outcome = "Better sell-through and reduced waste via bundled offer."
        return (
            "bundle",
            reasoning,
            expected_outcome,
            {
                "suggested_discount_percent": None,
                "suggested_selling_price": None,
                "bundle_suggestion": f"Bundle with: {bundle_item_name}",
                "nearest_food_banks": [],
            },
        )

    # --- Rule 2b: Demand will clear stock (surplus comfortable) → HOLD ---
    if surplus_comfortable and demand_is_more and remaining_stock >= LOT_MEDIUM_MIN_STOCK:
        reasoning = (
            f"Demand is healthy ({daily_demand:.1f} units/day) and will clear current stock ({remaining_stock}) in the period. "
            f"No urgent action for {item_name}; monitor and reorder as needed."
        )
        expected_outcome = "Stock will clear with current demand; monitor levels."
        return (
            "hold",
            reasoning,
            expected_outcome,
            {
                "suggested_discount_percent": None,
                "suggested_selling_price": None,
                "bundle_suggestion": None,
                "nearest_food_banks": [],
            },
        )

    # --- Rule 3: Demand is more (and some stock) → DISCOUNT (vary % by stock so not identical for every item) ---
    if lot_medium and demand_is_more and item_sellable and within_budget:
        # Vary discount by stock: base 10%, +2% per 50 units over 150, cap 25% (so recommendations differ)
        if discount_pct and discount_pct > 0:
            pct = discount_pct
        else:
            base, cap = 10, 25
            extra = min(cap - base, max(0, (remaining_stock - 150) // 50) * 2)
            pct = base + extra
        price = computed_suggested_price
        if price is None and selling_price is not None and pct > 0:
            try:
                price = round(float(selling_price) * (1 - pct / 100.0), 2)
            except (TypeError, ValueError):
                pass
        if has_expiry_urgency:
            reasoning = (
                f"Demand is healthy ({daily_demand:.1f} units/day), stock {remaining_stock}. "
                f"{item_name} has {days_until_expiry} day(s) before expiry. A {pct}% discount clears stock and reduces waste."
            )
        else:
            reasoning = (
                f"Demand is healthy ({daily_demand:.1f} units/day), stock {remaining_stock}. "
                f"A {pct}% discount for {item_name} clears stock and recovers revenue."
            )
        if price is not None:
            reasoning += f" Suggested price: ${price}."
        expected_outcome = "Reduce waste and recover revenue through increased sell-through."
        return (
            "discount",
            reasoning,
            expected_outcome,
            {
                "suggested_discount_percent": pct,
                "suggested_selling_price": price,
                "bundle_suggestion": None,
                "nearest_food_banks": [],
            },
        )

    # --- Fallback: expiry soon + discount possible ---
    if has_expiry_urgency and has_high_stock and item_sellable and within_budget:
        pct = max(discount_pct or 0, 5)
        reasoning = (
            f"{item_name} has {days_until_expiry} day(s) before expiry. A {pct}% discount is recommended to improve sell-through and reduce waste."
        )
        expected_outcome = "Reduce waste through price adjustment."
        return (
            "discount",
            reasoning,
            expected_outcome,
            {
                "suggested_discount_percent": pct,
                "suggested_selling_price": computed_suggested_price,
                "bundle_suggestion": None,
                "nearest_food_banks": [],
            },
        )

    # --- Fallback: expiry + food bank → donate ---
    if has_expiry_urgency and (nearest_food_banks or []) and within_budget:
        fb = nearest_food_banks[0]
        name = (fb.get("name") or "nearest food bank").strip()
        reasoning = f"Donating {item_name} to {name} minimizes waste and provides social value."
        expected_outcome = "Zero waste and social value through donation."
        return (
            "donate",
            reasoning,
            expected_outcome,
            {
                "suggested_discount_percent": None,
                "suggested_selling_price": None,
                "bundle_suggestion": None,
                "nearest_food_banks": [fb],
            },
        )

    # --- Fallback: surplus or risk + food bank → donate ---
    risk_level = (risk_assessment or {}).get("risk_level")
    has_surplus = surplus_qty > 0
    risk_flag = risk_level in ("high", "medium")
    if (nearest_food_banks or []) and within_budget and (has_surplus or risk_flag):
        fb = nearest_food_banks[0]
        name = (fb.get("name") or "nearest food bank").strip()
        reasoning = f"Donating {item_name} to {name} minimizes waste and provides social value."
        expected_outcome = "Zero waste and social value through donation."
        return (
            "donate",
            reasoning,
            expected_outcome,
            {
                "suggested_discount_percent": None,
                "suggested_selling_price": None,
                "bundle_suggestion": None,
                "nearest_food_banks": [fb],
            },
        )

    reasoning = "Monitor stock levels closely for waste risk. Consider setting expiry dates to enable discount/donation suggestions."
    expected_outcome = "Stock levels will be monitored."
    return (
        "hold",
        reasoning,
        expected_outcome,
        {
            "suggested_discount_percent": None,
            "suggested_selling_price": None,
            "bundle_suggestion": None,
            "nearest_food_banks": [],
        },
    )


# Rule order: DONATE (lot very high) → BUNDLE (lot low + similar items) → DISCOUNT (lot medium + demand more) → fallbacks


# -----------------------------------------------------------------------------
# Graph Nodes
# -----------------------------------------------------------------------------


def assess_risk(state: DecisionOrchestratorState) -> dict:
    """Call Risk Assessment subagent."""
    inv_id = state.get("inventory_id", "?")
    item_name = (state.get("item_data") or {}).get("item_name", "?")
    logger.info("[Subagent] Calling Risk Assessment | item=%s | inventory_id=%s", item_name, inv_id)
    payload = {
        "inventory_id": state.get("inventory_id"),
        "item_data": state.get("item_data", {}),
        "remaining_stock": state.get("remaining_stock"),
        "consumption_history": state.get("consumption_history", []),
        "forecasted_demand": state.get("forecasted_demand"),
    }
    
    try:
        r = requests.post(SUBAGENT_URLS["risk"], json=payload, timeout=5)
        risk_assessment = r.json() if r.ok else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        logger.error(f"Risk assessment failed: {e}")
        risk_assessment = {"error": str(e), "risk_level": "unknown", "risk_factors": []}
    
    return {"risk_assessment": risk_assessment}


def check_feasibility(state: DecisionOrchestratorState) -> dict:
    """Call Feasibility subagent."""
    inv_id = state.get("inventory_id", "?")
    item_name = (state.get("item_data") or {}).get("item_name", "?")
    logger.info("[Subagent] Calling Feasibility | item=%s | inventory_id=%s", item_name, inv_id)
    payload = {
        "inventory_id": state.get("inventory_id"),
        "suggested_action": state.get("suggested_action"),
        "item_data": state.get("item_data", {}),
        "remaining_stock": state.get("remaining_stock"),
        "context": state.get("context", {}),
    }
    
    try:
        r = requests.post(SUBAGENT_URLS["feasibility"], json=payload, timeout=5)
        feasibility_check = r.json() if r.ok else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        logger.error(f"Feasibility check failed: {e}")
        feasibility_check = {"error": str(e), "is_feasible": False, "constraints": []}
    
    return {"feasibility_check": feasibility_check}


def assess_cost_impact(state: DecisionOrchestratorState) -> dict:
    """Call Cost & Operational Impact subagent."""
    inv_id = state.get("inventory_id", "?")
    item_name = (state.get("item_data") or {}).get("item_name", "?")
    logger.info("[Subagent] Calling Cost Impact | item=%s | inventory_id=%s", item_name, inv_id)
    item_data = state.get("item_data", {})
    context = dict(state.get("context", {}))
    context.setdefault("selling_price", item_data.get("selling_price"))
    context.setdefault("remaining_stock", state.get("remaining_stock"))
    payload = {
        "inventory_id": state.get("inventory_id"),
        "suggested_action": state.get("suggested_action"),
        "item_data": item_data,
        "forecasted_demand": state.get("forecasted_demand"),
        "context": context,
    }
    
    try:
        r = requests.post(SUBAGENT_URLS["cost_impact"], json=payload, timeout=5)
        cost_impact = r.json() if r.ok else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        logger.error(f"Cost impact assessment failed: {e}")
        cost_impact = {"error": str(e), "estimated_cost": 0, "within_budget": True}
    
    return {"cost_impact": cost_impact}


def get_donation_options(state: DecisionOrchestratorState) -> dict:
    """Call Food Bank subagent when action is discard or user asked about waste/donate."""
    suggested_action = state.get("suggested_action", "")
    event_type = state.get("event_type", "")
    user_asked_about_waste = (state.get("context") or {}).get("user_asked_about_waste", False)
    should_fetch = (
        suggested_action == "discard"
        or event_type == "near_expiry"
        or user_asked_about_waste
    )
    if not should_fetch:
        return {"nearest_food_banks": []}
    try:
        r = requests.post(SUBAGENT_URLS["food_bank"], json={"limit": 5}, timeout=5)
        if r.ok:
            data = r.json()
            return {"nearest_food_banks": data.get("nearest_food_banks", [])}
    except Exception as e:
        logger.warning(f"Food bank lookup failed: {e}")
    return {"nearest_food_banks": []}


def generate_explanation(state: DecisionOrchestratorState) -> dict:
    """Call Explanation Generation subagent."""
    inv_id = state.get("inventory_id", "?")
    item_name = (state.get("item_data") or {}).get("item_name", "?")
    logger.info("[Subagent] Calling Explanation | item=%s | inventory_id=%s", item_name, inv_id)
    payload = {
        "inventory_id": state.get("inventory_id"),
        "suggested_action": state.get("suggested_action"),
        "risk_assessment": state.get("risk_assessment", {}),
        "feasibility_check": state.get("feasibility_check", {}),
        "cost_impact": state.get("cost_impact", {}),
        "item_data": state.get("item_data", {}),
        "forecasted_demand": state.get("forecasted_demand"),
        "context": state.get("context", {}),
        "nearest_food_banks": state.get("nearest_food_banks", []),
    }
    
    try:
        r = requests.post(SUBAGENT_URLS["explanation"], json=payload, timeout=10)
        explanation = r.json() if r.ok else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        logger.error(f"Explanation generation failed: {e}")
        explanation = {"error": str(e), "explanation": "Unable to generate explanation."}
    
    return {"explanation": explanation}


def synthesize_recommendation(state: DecisionOrchestratorState) -> dict:
    """Synthesize final recommendation using LLM, RAG context, and embedding-based similar items."""
    inventory_id = state.get("inventory_id", "")
    historical_context = retrieve_historical_context(inventory_id)
    similar_items = retrieve_similar_items_by_embedding(inventory_id, limit=5)
    item_data = state.get("item_data", {})

    # Bundle candidates: other items from inventory (same category/form/use) for exact bundle suggestion
    bundle_candidates = retrieve_bundle_candidates(inventory_id, item_data, limit=10)
    bundle_candidates_text = "None available."
    if bundle_candidates:
        lines = [f"  - {c.get('item_name', '?')} (category: {c.get('category') or 'N/A'}, form: {c.get('form') or 'N/A'}, usage: {c.get('usage') or c.get('use') or 'N/A'}, stock: {c.get('opening_stock', 0)})" for c in bundle_candidates]
        bundle_candidates_text = "\n".join(lines)

    # Format similar-items evidence (embedding-based)
    similar_text = "None available."
    if similar_items:
        lines = []
        for s in similar_items:
            name = s.get("item_name", "?")
            sim = s.get("similarity", 0)
            stock = s.get("opening_stock")
            min_s = s.get("min_stock")
            past = s.get("past_suggestions", [])
            past_str = "; ".join(
                f"{p.get('action', '')}({p.get('priority', '')}): {(p.get('reasoning') or '')[:60]}..."
                for p in past[:2]
            ) if past else "no past suggestions"
            lines.append(f"  - {name} (similarity {sim}, stock {stock}/min {min_s}): {past_str}")
        similar_text = "\n".join(lines) if lines else "None available."

    expiry_date = item_data.get("expiry_date") or (historical_context.get("inventory") or {}).get("expiry_date")
    selling_price = item_data.get("selling_price") or (historical_context.get("inventory") or {}).get("selling_price")
    days_until_expiry = None
    if expiry_date:
        try:
            from datetime import date
            e = expiry_date if isinstance(expiry_date, date) else date.fromisoformat(str(expiry_date)[:10])
            days_until_expiry = (e - date.today()).days
        except Exception:
            days_until_expiry = None

    # Dynamic discount (urgency + surplus) for context; intervention selection uses pick_one_waste_suggestion
    remaining = state.get("remaining_stock", 0)
    forecasted = state.get("forecasted_demand")
    discount_pct, computed_suggested_price = compute_discount_from_expiry(
        days_until_expiry, selling_price, remaining, forecasted
    )
    discount_hint = f"Calculated discount from expiry and surplus: {discount_pct}%. Suggested selling price: ${computed_suggested_price}" if computed_suggested_price is not None else f"Calculated discount: {discount_pct}%."

    # Signal to LLM when user asked about waste/expiry so it suggests discount or sell/donate
    user_asked_about_waste = (
        state.get("event_type") == "near_expiry"
        or state.get("context", {}).get("user_asked_about_waste")
    )
    waste_hint = "\nUser asked about waste/expiry (e.g. 'What's going to waste?'): Yes. Prefer suggesting discount or 'sell or donate soon' to reduce waste." if user_asked_about_waste else ""

    # Prepare context for LLM (include expiry, price, bundle candidates, calculated discount)
    context_text = f"""
Inventory Item: {item_data.get('item_name', 'Unknown')}
Current Stock: {state.get('remaining_stock', 0)}
Min Stock: {item_data.get('min_stock', 0)}
Forecasted Demand: {state.get('forecasted_demand', 0)}
Stock Signal: {state.get('stock_signal', 'unknown')}
Consumption Signal: {state.get('consumption_signal', 'unknown')}
Expiry Date: {expiry_date or 'Not set'}
Days until expiry: {days_until_expiry if days_until_expiry is not None else 'N/A'}
Selling Price: {selling_price if selling_price is not None else 'Not set'}
{discount_hint}
Event type: {state.get('event_type', 'unknown')}
{waste_hint}

Bundle candidates (from inventory – same or complementary category/form/use; use ONLY these item names in bundle_suggestion):
{bundle_candidates_text}

Risk Assessment: {state.get('risk_assessment', {})}
Feasibility: {state.get('feasibility_check', {})}
Cost Impact: {state.get('cost_impact', {})}

Historical Consumption (last 5): {historical_context['consumption'][:5]}
Recent Sales (last 3): {historical_context['sales'][:3]}

Similar items (embedding-based) and their past recommendations (use as evidence):
{similar_text}
"""
    
    if llm:
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert inventory management advisor. Give a strong, prescriptive recommendation that is evidence-based and actionable.

Use: risk, feasibility, cost, historical consumption and sales, and similar-item evidence. If expiry date is near (e.g. within 7-14 days), consider suggesting discount or "sell or donate soon" to reduce waste.

DISCOUNT AND BUNDLE (when not using intervention selector): Use the "Calculated discount" value from context for suggested_discount_percent (0-50). Use "Suggested selling price" when provided. bundle_suggestion: use ONLY item names from "Bundle candidates" list; format as "Bundle with: ItemA" using exact names from that list.

IMPORTANT: Output plain text only in reasoning and expected_outcome. Do not use markdown: no asterisks, no hashtags, no bold/italic. Write in clear sentences so the text can be shown in chat and in the suggestion tab as-is.

Provide a structured recommendation as JSON with:
- action: Exactly one of: reorder, hold, transfer, discard, none
- priority: High, Medium, or Low
- reasoning: 1-2 plain-text sentences (no markdown)
- expected_outcome: One plain-text sentence (no markdown)
- suggested_discount_percent: Number 0-50 from calculated discount in context, else null
- suggested_selling_price: Number from context (e.g. 2.99) when provided, else null
- bundle_suggestion: "Bundle with: Name1, Name2" using ONLY names from Bundle candidates list, else null
- waste_action: Optional string if relevant, e.g. "Sell or donate soon" when expiry is near, else null
- discard_reason: Required when action is discard: one plain-text sentence explaining why to discard (e.g. expired, damaged, unsaleable), else null
"""),
                ("user", "Context:\n{context}\n\nProvide a single, strong prescriptive recommendation as JSON."),
            ])
            
            chain = prompt | llm | JsonOutputParser()
            llm_result = chain.invoke({"context": context_text})
            
            reasoning = llm_result.get("reasoning", "")
            expected_outcome = llm_result.get("expected_outcome", "")
            suggested_discount = llm_result.get("suggested_discount_percent")
            suggested_price = llm_result.get("suggested_selling_price")
            bundle_suggestion = llm_result.get("bundle_suggestion")
            if isinstance(bundle_suggestion, str):
                bundle_suggestion = strip_markdown(bundle_suggestion).strip() or None
            # When waste/expiry: use rule-based exact values if LLM omitted them
            if user_asked_about_waste:
                if suggested_discount is None:
                    suggested_discount = discount_pct
                if suggested_price is None:
                    suggested_price = computed_suggested_price
                if not bundle_suggestion and bundle_candidates:
                    names = [c.get("item_name", "").strip() for c in bundle_candidates[:3] if c.get("item_name")]
                    if names:
                        bundle_suggestion = "Bundle with: " + ", ".join(names)
            discard_reason = llm_result.get("discard_reason")
            if isinstance(discard_reason, str):
                discard_reason = strip_markdown(discard_reason).strip() or None
            action = llm_result.get("action", state.get("suggested_action", "none"))
            suggested_action = state.get("suggested_action", "none")
            # Reorder (low stock): one clear suggestion — reorder by expiry date (use state so proactive low-stock gets this)
            if suggested_action == "reorder" or action == "reorder":
                expiry_str = f" by {expiry_date}" if expiry_date else ""
                reasoning = f"Reorder{expiry_str} to maintain stock; prioritize by expiry date."
                expected_outcome = "Stock levels will be maintained and waste minimized."
                recommendation = {
                    "action": "reorder",
                    "priority": llm_result.get("priority", "Medium"),
                    "reasoning": reasoning,
                    "expected_outcome": strip_markdown(expected_outcome),
                    "suggested_discount_percent": None,
                    "suggested_selling_price": None,
                    "bundle_suggestion": None,
                    "waste_action": None,
                    "discard_reason": None,
                    "llm_enhanced": True,
                }
            elif user_asked_about_waste:
                # Exactly ONE intervention: DISCOUNT -> BUNDLE -> DONATION (priority order)
                _pk, reasoning_one, expected_one, overrides = pick_one_waste_suggestion(
                    state.get("risk_assessment", {}),
                    state.get("feasibility_check", {}),
                    state.get("cost_impact", {}),
                    state.get("nearest_food_banks", []),
                    bundle_candidates,
                    similar_items,
                    state.get("remaining_stock", 0),
                    days_until_expiry,
                    item_data.get("item_name", "Item"),
                    state.get("forecasted_demand"),
                    selling_price,
                )
                recommendation = {
                    "action": _pk,
                    "priority": llm_result.get("priority", "Medium"),
                    "reasoning": reasoning_one,
                    "expected_outcome": expected_one,
                    "suggested_discount_percent": overrides.get("suggested_discount_percent"),
                    "suggested_selling_price": overrides.get("suggested_selling_price"),
                    "bundle_suggestion": overrides.get("bundle_suggestion"),
                    "waste_action": strip_markdown(llm_result.get("waste_action") or "") or None,
                    "discard_reason": discard_reason,
                    "llm_enhanced": True,
                }
                # Apply donation override: store only the chosen food bank(s) for UI
                if "nearest_food_banks" in overrides:
                    recommendation["_nearest_food_banks_override"] = overrides["nearest_food_banks"]
            else:
                extra_parts = []
                if suggested_discount is not None:
                    extra_parts.append(f"Suggested discount: {suggested_discount}%.")
                if suggested_price is not None:
                    extra_parts.append(f"Suggested selling price: {suggested_price}.")
                if bundle_suggestion:
                    extra_parts.append(f"Bundle suggestion: {bundle_suggestion}.")
                if discard_reason:
                    extra_parts.append(f"Discard reason: {discard_reason}.")
                if extra_parts:
                    reasoning = (strip_markdown(reasoning) + " " + " ".join(extra_parts)).strip()
                recommendation = {
                    "action": action,
                    "priority": llm_result.get("priority", "Medium"),
                    "reasoning": reasoning,
                    "expected_outcome": strip_markdown(expected_outcome),
                    "suggested_discount_percent": suggested_discount,
                    "suggested_selling_price": suggested_price if suggested_price is not None else None,
                    "bundle_suggestion": bundle_suggestion,
                    "waste_action": strip_markdown(llm_result.get("waste_action") or "") or None,
                    "discard_reason": discard_reason,
                    "llm_enhanced": True,
                }
        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            suggested_action = state.get("suggested_action", "none")
            if suggested_action == "reorder":
                expiry_str = f" by {expiry_date}" if expiry_date else ""
                recommendation = {
                    "action": "reorder",
                    "priority": "Medium",
                    "reasoning": f"Reorder{expiry_str} to maintain stock; prioritize by expiry date.",
                    "expected_outcome": "Stock levels will be maintained and waste minimized.",
                    "suggested_discount_percent": None,
                    "suggested_selling_price": None,
                    "bundle_suggestion": None,
                    "discard_reason": None,
                    "llm_enhanced": False,
                }
            elif user_asked_about_waste:
                _pk, reasoning_one, expected_one, overrides = pick_one_waste_suggestion(
                    state.get("risk_assessment", {}),
                    state.get("feasibility_check", {}),
                    state.get("cost_impact", {}),
                    state.get("nearest_food_banks", []),
                    bundle_candidates,
                    similar_items,
                    state.get("remaining_stock", 0),
                    days_until_expiry,
                    item_data.get("item_name", "Item"),
                    state.get("forecasted_demand"),
                    selling_price,
                )
                recommendation = {
                    "action": _pk,
                    "priority": "Medium",
                    "reasoning": reasoning_one,
                    "expected_outcome": expected_one,
                    "suggested_discount_percent": overrides.get("suggested_discount_percent"),
                    "suggested_selling_price": overrides.get("suggested_selling_price"),
                    "bundle_suggestion": overrides.get("bundle_suggestion"),
                    "discard_reason": None,
                    "llm_enhanced": False,
                }
                if "nearest_food_banks" in overrides:
                    recommendation["_nearest_food_banks_override"] = overrides["nearest_food_banks"]
            else:
                recommendation = {
                    "action": suggested_action,
                    "priority": "Medium",
                    "reasoning": "Risk and feasibility indicate monitoring; no waste intervention required.",
                    "expected_outcome": "Stock levels will be maintained",
                    "discard_reason": None,
                    "llm_enhanced": False,
                }
    else:
        # Fallback to rule-based recommendation (no LLM)
        risk_level = state.get("risk_assessment", {}).get("risk_level", "medium")
        is_feasible = state.get("feasibility_check", {}).get("is_feasible", True)
        within_budget = state.get("cost_impact", {}).get("within_budget", True)
        suggested_action = state.get("suggested_action", "none")

        if risk_level == "high" and is_feasible and within_budget:
            priority = "High"
        elif risk_level == "medium":
            priority = "Medium"
        else:
            priority = "Low"

        if suggested_action == "reorder":
            expiry_str = f" by {expiry_date}" if expiry_date else ""
            recommendation = {
                "action": "reorder",
                "priority": priority,
                "reasoning": f"Reorder{expiry_str} to maintain stock; prioritize by expiry date.",
                "expected_outcome": "Stock levels will be maintained and waste minimized.",
                "suggested_discount_percent": None,
                "suggested_selling_price": None,
                "bundle_suggestion": None,
                "discard_reason": None,
                "llm_enhanced": False,
            }
        elif user_asked_about_waste:
            _pk, reasoning_one, expected_one, overrides = pick_one_waste_suggestion(
                state.get("risk_assessment", {}),
                state.get("feasibility_check", {}),
                state.get("cost_impact", {}),
                state.get("nearest_food_banks", []),
                bundle_candidates,
                similar_items,
                state.get("remaining_stock", 0),
                days_until_expiry,
                item_data.get("item_name", "Item"),
                state.get("forecasted_demand"),
                selling_price,
            )
            recommendation = {
                "action": _pk,
                "priority": priority,
                "reasoning": reasoning_one,
                "expected_outcome": expected_one,
                "suggested_discount_percent": overrides.get("suggested_discount_percent"),
                "suggested_selling_price": overrides.get("suggested_selling_price"),
                "bundle_suggestion": overrides.get("bundle_suggestion"),
                "discard_reason": None,
                "llm_enhanced": False,
            }
            if "nearest_food_banks" in overrides:
                recommendation["_nearest_food_banks_override"] = overrides["nearest_food_banks"]
        else:
            recommendation = {
                "action": suggested_action,
                "priority": priority,
                "reasoning": f"Risk: {risk_level}, Feasible: {is_feasible}, Budget: {within_budget}",
                "expected_outcome": "Stock levels will be optimized",
                "suggested_discount_percent": None,
                "suggested_selling_price": None,
                "bundle_suggestion": None,
                "discard_reason": None,
                "llm_enhanced": False,
            }

    # Build final recommendation: use override for nearest_food_banks when we picked "donate" only
    nearest_fb = recommendation.pop("_nearest_food_banks_override", None)
    if nearest_fb is None:
        nearest_fb = state.get("nearest_food_banks", [])
    return {
        "recommendation": {
            **recommendation,
            "timestamp": datetime.now().isoformat(),
            "inventory_id": state.get("inventory_id"),
            "risk_assessment": state.get("risk_assessment", {}),
            "feasibility_check": state.get("feasibility_check", {}),
            "cost_impact": state.get("cost_impact", {}),
            "explanation": state.get("explanation", {}),
            "nearest_food_banks": nearest_fb,
        }
    }


# -----------------------------------------------------------------------------
# Build Graph
# -----------------------------------------------------------------------------


def build_orchestration_graph() -> StateGraph:
    """Build the decision orchestration StateGraph."""
    builder = StateGraph(DecisionOrchestratorState)
    
    # Add nodes
    builder.add_node("assess_risk", assess_risk)
    builder.add_node("check_feasibility", check_feasibility)
    builder.add_node("assess_cost_impact", assess_cost_impact)
    builder.add_node("get_donation_options", get_donation_options)
    builder.add_node("generate_explanation", generate_explanation)
    builder.add_node("synthesize_recommendation", synthesize_recommendation)
    
    # Define flow: cost impact -> optional food bank lookup (discard/donate) -> explanation -> synthesis
    builder.add_edge(START, "assess_risk")
    builder.add_edge("assess_risk", "check_feasibility")
    builder.add_edge("check_feasibility", "assess_cost_impact")
    builder.add_edge("assess_cost_impact", "get_donation_options")
    builder.add_edge("get_donation_options", "generate_explanation")
    builder.add_edge("generate_explanation", "synthesize_recommendation")
    builder.add_edge("synthesize_recommendation", END)
    
    return builder.compile()


# Compiled graph (singleton)
_orchestration_graph = None


def get_orchestration_graph():
    """Return the compiled LangGraph orchestration graph."""
    global _orchestration_graph
    if _orchestration_graph is None:
        _orchestration_graph = build_orchestration_graph()
    return _orchestration_graph


# -----------------------------------------------------------------------------
# MCP Tools
# -----------------------------------------------------------------------------


@mcp.tool()
def orchestrate_intervention(inventory_id: str, event_type: str = "low_stock") -> dict:
    """Orchestrate a prescriptive intervention for an inventory item."""
    # Fetch item data
    historical_context = retrieve_historical_context(inventory_id)
    item_data = historical_context.get("inventory", {})
    
    if not item_data:
        return {"error": f"Inventory item {inventory_id} not found"}
    
    initial_state: DecisionOrchestratorState = {
        "inventory_id": inventory_id,
        "event_type": event_type,
        "remaining_stock": None,  # Will be calculated
        "suggested_action": "reorder",
        "stock_signal": "low",
        "consumption_signal": "normal",
        "item_data": item_data,
        "consumption_history": historical_context.get("consumption", []),
        "context": {},
    }
    
    graph = get_orchestration_graph()
    final_state = graph.invoke(initial_state)
    
    return final_state.get("recommendation", {})


# -----------------------------------------------------------------------------
# HTTP API (Flask)
# -----------------------------------------------------------------------------

app = Flask(__name__)


@app.route("/orchestrate", methods=["POST"])
def orchestrate():
    """Main orchestration endpoint."""
    payload = request.get_json(silent=True) or {}
    inv_id = payload.get("inventory_id", "?")
    item_name = (payload.get("item_data") or {}).get("item_name", "?")
    logger.info("[Orchestrator] Received request | item=%s | inventory_id=%s | event_type=%s", item_name, inv_id, payload.get("event_type", ""))
    
    initial_state: DecisionOrchestratorState = {
        "inventory_id": payload.get("inventory_id", ""),
        "event_type": payload.get("event_type", "low_stock"),
        "remaining_stock": payload.get("remaining_stock"),
        "suggested_action": payload.get("suggested_action", "reorder"),
        "stock_signal": payload.get("stock_signal", "low"),
        "consumption_signal": payload.get("consumption_signal", "normal"),
        "forecasted_demand": payload.get("forecasted_demand"),
        "item_data": payload.get("item_data", {}),
        "consumption_history": payload.get("consumption_history", []),
        "context": payload.get("context", {}),
    }
    
    graph = get_orchestration_graph()
    final_state = graph.invoke(initial_state)
    
    rec = final_state.get("recommendation", {})
    logger.info("[Orchestrator] Pipeline complete | item=%s | inventory_id=%s | action=%s", item_name, inv_id, rec.get("action", "?"))
    
    return jsonify({
        "recommendation": final_state.get("recommendation", {}),
        "risk_assessment": final_state.get("risk_assessment", {}),
        "feasibility_check": final_state.get("feasibility_check", {}),
        "cost_impact": final_state.get("cost_impact", {}),
        "explanation": final_state.get("explanation", {}),
    }), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "agent": "decision-orchestrator",
        "mistral_configured": llm is not None,
    }), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9000"))
    # Run without Flask debug/reloader in production/testing here to avoid
    # multiple processes that can interfere with local TCP binding and tests.
    app.run(host="0.0.0.0", port=port, debug=False)
