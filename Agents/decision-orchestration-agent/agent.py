"""Decision Orchestrator Agent – Coordinates sub-agents for prescriptive inventory interventions.

Uses LangChain/LangGraph for multi-agent reasoning and retrieval workflows.
Integrates Mistral LLM for contextual reasoning and prescriptive recommendations.
Implements RAG with PostgreSQL for evidence-based decisions and explanations.
"""
import os
import logging
from typing import TypedDict, List, Dict, Optional, Literal
from datetime import datetime, date
from pathlib import Path

from common.expiry import days_until_expiry

import requests
import psycopg2
from psycopg2.extras import RealDictCursor
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
AGENT_SHARED_TOKEN = os.getenv("AGENT_SHARED_TOKEN", "")

# Subagent URLs (feasibility + cost merged into single agent at 9002)
SUBAGENT_URLS = {
    "risk": os.getenv("RISK_AGENT_URL", "http://localhost:9004/risk"),
    "feasibility_and_cost": os.getenv(
        "FEASIBILITY_AND_COST_AGENT_URL", "http://localhost:9002/feasibility-and-cost"
    ),
    "cost_impact": os.getenv("COST_IMPACT_AGENT_URL", "http://localhost:9002/cost-impact"),
    "explanation": os.getenv("EXPLANATION_AGENT_URL", "http://localhost:9003/explain"),
    "food_bank": os.getenv("FOOD_BANK_AGENT_URL", "http://localhost:9007/nearest"),
}


def _agent_headers() -> Dict[str, str]:
    headers = {}
    if AGENT_SHARED_TOKEN:
        headers["X-Agent-Token"] = AGENT_SHARED_TOKEN
    return headers

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
    context: dict  # may contain "intent": "waste" | "pricing" | "reorder" | "general", "user_asked_about_waste"
    
    # Subagent Results
    risk_assessment: dict
    feasibility_check: dict
    cost_impact: dict
    nearest_food_banks: List[dict]  # when discard/donate: for donation suggestion
    explanation: dict
    
    # Decision Engine output (sets recommended_action before optional food bank call)
    recommended_action: str  # donate | discount | bundle | reorder | hold | price_increase | ...
    _decision_overrides: dict  # optional overrides from decision engine for synthesize
    _historical_context: dict
    _bundle_candidates: List[dict]
    _similar_items: List[dict]
    _demand_signal: str
    
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


def _latest_unit_cost_from_sales(sales: List[dict]) -> Optional[float]:
    """Get unit_cost from the most recent sale (sales assumed ordered by purchase_date DESC)."""
    if not sales:
        return None
    try:
        uc = sales[0].get("unit_cost")
        if uc is not None:
            return float(uc)
    except (TypeError, ValueError):
        pass
    return None


def get_latest_unit_cost_from_sales(inventory_id: str) -> Optional[float]:
    """Get the most recent unit_cost from sales for this item (for suggesting selling_price when missing)."""
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


def _suggested_selling_price_from_cost(unit_cost: float, margin_percent: Optional[float] = None) -> float:
    """Suggest a selling price from unit_cost with margin. Used when inventory.selling_price is not set."""
    margin = margin_percent if margin_percent is not None else DEFAULT_MARGIN_PERCENT
    return round(unit_cost * (1 + margin / 100.0), 2)


def _reorder_price_increase_suggestion(
    item_data: dict,
    historical_context: Optional[Dict] = None,
    remaining_stock: Optional[int] = None,
    days_until_expiry: Optional[int] = None,
) -> tuple:
    """Return (suggested_price_increase_percent, suggested_selling_price) for reorder.

    Guardrails:
    - no price increase when stock is zero/out-of-stock
    - no price increase for near-expiry items
    """
    try:
        rs = int(remaining_stock) if remaining_stock is not None else 0
    except (TypeError, ValueError):
        rs = 0
    if rs <= 0:
        return (None, None)
    if days_until_expiry is not None and days_until_expiry <= NEAR_EXPIRY_DAYS:
        return (None, None)

    selling_price = (item_data or {}).get("selling_price") or (
        ((historical_context or {}).get("inventory") or {}).get("selling_price")
    )
    if selling_price is None and historical_context:
        unit_cost = _latest_unit_cost_from_sales(historical_context.get("sales") or [])
        if unit_cost is not None:
            try:
                selling_price = _suggested_selling_price_from_cost(unit_cost)
            except (TypeError, ValueError):
                pass
    try:
        sp = float(selling_price) if selling_price is not None else None
    except (TypeError, ValueError):
        sp = None
    if sp is None or sp <= 0:
        return (None, None)
    pct = REORDER_PRICE_INCREASE_PERCENT
    increased = round(sp * (1 + pct / 100.0), 2)
    return (pct, increased)


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
MAX_DISCOUNT_LIMIT = 50
BASE_DISCOUNT = 10
# When selling_price is missing, suggest from previous unit_cost (sales) + margin
DEFAULT_MARGIN_PERCENT = float(os.getenv("DEFAULT_MARGIN_PERCENT", "20.0"))
# Along with reorder: suggest a small price increase (1-2%) to capture margin
REORDER_PRICE_INCREASE_PERCENT = float(os.getenv("REORDER_PRICE_INCREASE_PERCENT", "2.0"))
# Waste rules (exact business policy)
DONATE_URGENT_DAYS = 3
DISCOUNT_WINDOW_LOW = 4
DISCOUNT_WINDOW_HIGH = 7
BUNDLE_WINDOW_LOW = 7
BUNDLE_WINDOW_HIGH = 10
NEAR_EXPIRY_DAYS = 14


def _days_until_expiry_from_item(item_data: dict, historical_inventory: Optional[dict] = None) -> Optional[int]:
    """Get days until expiry from item_data (or historical_inventory). Supports expiry_date and expiryDate keys."""
    expiry_value = None
    if item_data:
        expiry_value = item_data.get("expiry_date") or item_data.get("expiryDate")
    if not expiry_value and historical_inventory:
        expiry_value = historical_inventory.get("expiry_date") or historical_inventory.get("expiryDate")
    if not expiry_value:
        return None
    return days_until_expiry(expiry_value)


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
    """Surplus factor based on excess stock over expected demand before expiry.

    Uses a smooth scale (instead of hard buckets) so discount % varies per item.
    """
    surplus = remaining_stock - forecasted_demand_before_expiry
    if surplus <= 0:
        return 0.0
    # Normalize by expected demand before expiry. Keep a floor so low-demand items
    # don't explode to max discount from small absolute surplus values.
    scale = max(15.0, forecasted_demand_before_expiry * 0.75)
    score = (surplus / scale) * 2.5
    return min(14.0, max(0.0, round(score, 1)))


def compute_discount_from_expiry(
    days_until_expiry: Optional[int],
    selling_price: Optional[float],
    remaining_stock: int = 0,
    forecasted_demand: Optional[float] = None,
) -> tuple:
    """
    Compute discount % and suggested price using dynamic formula:
    discount_percent = min(max_discount_limit, base_discount + urgency_factor + surplus_factor).
    Surplus factor is smooth to avoid repeated identical percentages.
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


def get_latest_predicted_demand(inventory_id: str) -> Optional[float]:
    """Return latest predicted_demand for one item from demand table."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT predicted_demand
            FROM demand
            WHERE inventory_id = %s AND predicted_demand IS NOT NULL
            ORDER BY prediction_date DESC, demand_id DESC
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
        logger.debug("Could not read latest predicted_demand for %s: %s", inventory_id, e)
    return None


def get_demand_signal(forecasted_demand: Optional[float]) -> str:
    """
    Classify demand as high/low from DB distribution only (latest prediction per item).
    Returns: high | low | unknown.
    """
    if forecasted_demand is None:
        return "unknown"
    try:
        fd = float(forecasted_demand)
    except (TypeError, ValueError):
        return "unknown"
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            """
            WITH latest AS (
              SELECT DISTINCT ON (inventory_id) inventory_id, predicted_demand
              FROM demand
              WHERE predicted_demand IS NOT NULL
              ORDER BY inventory_id, prediction_date DESC, demand_id DESC
            )
            SELECT percentile_cont(0.70) WITHIN GROUP (ORDER BY predicted_demand) AS p70
            FROM latest
            """
        )
        row = cur.fetchone() or {}
        cur.close()
        conn.close()
        p70 = row.get("p70")
        if p70 is None:
            return "unknown"
        return "high" if fd >= float(p70) else "low"
    except Exception as e:
        logger.debug("Could not compute demand signal: %s", e)
        return "unknown"


def filter_high_demand_candidates(candidates: List[Dict]) -> List[Dict]:
    """Keep only bundle candidates that are high demand based on demand table latest predictions."""
    if not candidates:
        return []
    ids = [c.get("inventory_id") for c in candidates if c.get("inventory_id")]
    if not ids:
        return []
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        placeholders = ",".join(["%s"] * len(ids))
        cur.execute(
            f"""
            WITH latest AS (
              SELECT DISTINCT ON (inventory_id) inventory_id, predicted_demand
              FROM demand
              WHERE inventory_id IN ({placeholders}) AND predicted_demand IS NOT NULL
              ORDER BY inventory_id, prediction_date DESC, demand_id DESC
            ),
            threshold AS (
              SELECT percentile_cont(0.70) WITHIN GROUP (ORDER BY predicted_demand) AS p70
              FROM (
                SELECT DISTINCT ON (inventory_id) inventory_id, predicted_demand
                FROM demand
                WHERE predicted_demand IS NOT NULL
                ORDER BY inventory_id, prediction_date DESC, demand_id DESC
              ) x
            )
            SELECT l.inventory_id
            FROM latest l CROSS JOIN threshold t
            WHERE t.p70 IS NOT NULL AND l.predicted_demand >= t.p70
            """,
            tuple(ids),
        )
        high_ids = {r["inventory_id"] for r in cur.fetchall()}
        cur.close()
        conn.close()
        return [c for c in candidates if c.get("inventory_id") in high_ids]
    except Exception as e:
        logger.debug("Could not filter high-demand bundle candidates: %s", e)
        return []


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
    preferred_waste_action: Optional[str] = None,
    allow_donate_without_banks: bool = False,
    is_perishable: Optional[bool] = None,
    demand_signal: Optional[str] = None,
    high_demand_bundle_candidates: Optional[List[dict]] = None,
) -> tuple:
    """
    Select exactly ONE intervention per item (mutually exclusive, hierarchical).
    Returns (action, reasoning, expected_outcome, overrides).
    Policy:
    - donate: perishable + 0–3 days + low demand
    - discount: 4–7 days + high demand
    - bundle: 7–10 days + low demand + similar high-demand item available
    - price_increase: high demand items (when not in near-expiry window)
    - reorder: handled before this function
    """
    if is_perishable is None:
        is_perishable = True  # default so existing callers unchanged
    fc = feasibility_check or {}
    ci = cost_impact or {}
    if fc.get("error"):
        is_feasible = True
    else:
        is_feasible = fc.get("is_feasible", True)
    if ci.get("error"):
        within_budget = True
    else:
        within_budget = ci.get("within_budget", True)

    if demand_signal not in ("high", "low"):
        demand_signal = "unknown"
    demand_high = demand_signal == "high"
    demand_low = demand_signal == "low"

    try:
        daily_demand = float(forecasted_demand) if forecasted_demand is not None else None
    except (TypeError, ValueError):
        daily_demand = None

    # Expiry tiers
    expired = days_until_expiry is not None and days_until_expiry < 0
    expires_today = days_until_expiry == 0
    urgent_donate_days = days_until_expiry is not None and 1 <= days_until_expiry <= DONATE_URGENT_DAYS
    discount_window = (
        days_until_expiry is not None
        and DISCOUNT_WINDOW_LOW <= days_until_expiry <= DISCOUNT_WINDOW_HIGH
    )
    bundle_window = (
        days_until_expiry is not None
        and BUNDLE_WINDOW_LOW <= days_until_expiry <= BUNDLE_WINDOW_HIGH
    )
    near_expiry = days_until_expiry is not None and 1 <= days_until_expiry <= 10
    expiry_not_near = days_until_expiry is None or days_until_expiry > NEAR_EXPIRY_DAYS

    compatible_items = high_demand_bundle_candidates or []
    if not compatible_items:
        compatible_items = filter_high_demand_candidates(similar_items if similar_items else bundle_candidates)
    compatible_items = [c for c in compatible_items if c.get("item_name")]
    has_high_demand_similar = len(compatible_items) > 0

    discount_pct, computed_suggested_price = compute_discount_from_expiry(
        days_until_expiry, selling_price, remaining_stock, forecasted_demand
    )
    try:
        sp = float(selling_price) if selling_price is not None else None
    except (TypeError, ValueError):
        sp = None

    def _overrides(discount_pct=None, price=None, bundle=None, food_banks=None, price_increase_pct=None, increased_price=None):
        o = {
            "suggested_discount_percent": discount_pct,
            "suggested_selling_price": price,
            "bundle_suggestion": bundle,
            "nearest_food_banks": food_banks or [],
        }
        if price_increase_pct is not None:
            o["suggested_price_increase_percent"] = price_increase_pct
        if increased_price is not None:
            o["suggested_selling_price"] = increased_price
        return o

    def _discount_return(pct_val, price_val, reason_suffix):
        pct = pct_val if pct_val and pct_val > 0 else 15
        price = price_val or (round(sp * (1 - pct / 100.0), 2) if sp and pct > 0 else None)
        reasoning = f"{reason_suffix} A {pct}% discount for {item_name} can help clear stock."
        if price is not None:
            reasoning += f" Suggested price: ${price}."
        return ("discount", reasoning, "Clear stock before expiry.", _overrides(discount_pct=pct, price=price))

    def _bundle_return(reason_suffix: str):
        if has_high_demand_similar:
            first = compatible_items[0]
            bundle_name = (first.get("item_name") or "similar item").strip()
            reasoning = f"{reason_suffix} Bundle {item_name} with {bundle_name} to increase sell-through."
            return (
                "bundle",
                reasoning,
                "Better sell-through via bundled offer.",
                _overrides(bundle=f"Bundle with: {bundle_name}"),
            )
        reasoning = f"{reason_suffix} No high-demand similar items available for a bundle."
        return ("hold", reasoning, "Monitor and re-evaluate after demand refresh.", _overrides(bundle=None))

    # --- 1. Expired → Discard (do not donate non-perishables or expired bulk like Sugar/Flour to food bank) ---
    if expired:
        reasoning = (
            f"{item_name} is past expiry ({days_until_expiry} days). Discard to avoid health risk; do not sell or donate."
        )
        return ("discard", reasoning, "Remove expired stock safely.", _overrides())

    if expires_today:
        reasoning = (
            f"{item_name} expires today. Discard immediately to avoid spoilage risk."
        )
        return ("discard", reasoning, "Remove same-day expiring stock safely.", _overrides())

    # --- 2. Price increase: high demand + not near expiry ---
    if demand_high and expiry_not_near and within_budget and is_feasible:
        if sp and sp > 0:
            price_increase_pct = 10
            increased_price = round(sp * (1 + price_increase_pct / 100.0), 2)
            demand_txt = f"{daily_demand:.1f}/day" if daily_demand is not None else "high"
            reasoning = (
                f"Demand is high ({demand_txt}) and expiry is not near. "
                f"Increase price by {price_increase_pct}% for {item_name}. Suggested: ${increased_price}."
            )
            return ("price_increase", reasoning, "Capture value with a modest price increase.",
                    _overrides(price_increase_pct=price_increase_pct, increased_price=increased_price))

    # --- 3. Donate: perishable + 0–3 days + low demand ---
    if urgent_donate_days and demand_low and within_budget and (nearest_food_banks or allow_donate_without_banks):
        if is_perishable:
            if nearest_food_banks:
                fb = nearest_food_banks[0]
                name = (fb.get("name") or "nearest food bank").strip()
                addr = (fb.get("address") or "").strip()
                reasoning = f"Urgent expiry ({days_until_expiry} days). Donating {item_name} to {name} minimizes waste."
                if addr:
                    reasoning += f" Donate to: {name}, {addr}."
                return ("donate", reasoning, "Zero waste and social value.", _overrides(food_banks=[fb]))
            return (
                "donate",
                f"Urgent expiry ({days_until_expiry} days). Donating {item_name} to a nearby food bank minimizes waste.",
                "Zero waste and social value.",
                _overrides(food_banks=[]),
            )
        return ("hold", f"{item_name} is non-perishable; donation is not selected for this window.", "Monitor item and apply pricing policy if needed.", _overrides())

    # --- 4. Discount: 4–7 days + high demand ---
    if discount_window and demand_high and within_budget and is_feasible:
        return _discount_return(
            discount_pct,
            computed_suggested_price,
            f"Expiry window {days_until_expiry} days with high demand. ",
        )

    # --- 5. Bundle: 7–10 days + low demand + similar high-demand pair ---
    if bundle_window and demand_low and within_budget and is_feasible:
        return _bundle_return(f"Expiry window {days_until_expiry} days with low demand.")

    # --- 6. Near-expiry but policy conditions not met ---
    if near_expiry:
        return (
            "hold",
            f"{item_name} is near expiry but policy conditions were not met (demand signal: {demand_signal}).",
            "Wait for updated demand or act manually.",
            _overrides(),
        )

    # --- 7. Missing/unknown demand: avoid assumptions ---
    if demand_signal == "unknown":
        return (
            "hold",
            f"Demand data is unavailable for {item_name}; no pricing/donation action selected.",
            "Run demand prediction and retry.",
            _overrides(),
        )

    # Final fallback
    return ("hold", f"No intervention rule matched for {item_name}.", "Monitor item.", _overrides())


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
        r = requests.post(SUBAGENT_URLS["risk"], json=payload, headers=_agent_headers(), timeout=5)
        risk_assessment = r.json() if r.ok else {"error": f"HTTP {r.status_code}"}
        status = "ok" if not risk_assessment.get("error") else "error"
        logger.info("[Subagent] Risk Assessment completed | item=%s | status=%s", item_name, status)
    except Exception as e:
        logger.error(f"Risk assessment failed: {e}")
        risk_assessment = {"error": str(e), "risk_level": "unknown", "risk_factors": []}
        logger.info("[Subagent] Risk Assessment completed | item=%s | status=error", item_name)
    
    return {"risk_assessment": risk_assessment}


def check_feasibility_and_cost(state: DecisionOrchestratorState) -> dict:
    """Call merged Feasibility & Cost Impact subagent (single HTTP call)."""
    inv_id = state.get("inventory_id", "?")
    item_name = (state.get("item_data") or {}).get("item_name", "?")
    logger.info(
        "[Subagent] Calling Feasibility & Cost Impact | item=%s | inventory_id=%s",
        item_name,
        inv_id,
    )
    item_data = state.get("item_data", {})
    context = dict(state.get("context", {}))
    context.setdefault("selling_price", item_data.get("selling_price"))
    context.setdefault("remaining_stock", state.get("remaining_stock"))
    payload = {
        "inventory_id": state.get("inventory_id"),
        "suggested_action": state.get("suggested_action"),
        "item_data": item_data,
        "remaining_stock": state.get("remaining_stock"),
        "forecasted_demand": state.get("forecasted_demand"),
        "context": context,
    }
    try:
        r = requests.post(SUBAGENT_URLS["feasibility_and_cost"], json=payload, headers=_agent_headers(), timeout=8)
        if not r.ok:
            feasibility_check = {"error": f"HTTP {r.status_code}", "is_feasible": False, "constraints": []}
            cost_impact = {"error": f"HTTP {r.status_code}", "estimated_cost": 0, "within_budget": True}
            logger.info("[Subagent] Feasibility & Cost completed | item=%s | status=error", item_name)
        else:
            data = r.json()
            feasibility_check = data.get("feasibility_check", {})
            cost_impact = data.get("cost_impact", {})
            fc_ok = not feasibility_check.get("error")
            ci_ok = not cost_impact.get("error")
            status = "ok" if (fc_ok and ci_ok) else "error"
            logger.info(
                "[Subagent] Feasibility & Cost completed | item=%s | status=%s",
                item_name,
                status,
            )
    except Exception as e:
        logger.error(f"Feasibility & Cost Impact call failed: {e}")
        feasibility_check = {"error": str(e), "is_feasible": False, "constraints": []}
        cost_impact = {"error": str(e), "estimated_cost": 0, "within_budget": True}
        logger.info("[Subagent] Feasibility & Cost completed | item=%s | status=error", item_name)
    return {
        "feasibility_check": feasibility_check,
        "cost_impact": cost_impact,
    }


def run_decision_engine(state: DecisionOrchestratorState) -> dict:
    """Run deterministic decision rules; set recommended_action and _decision_overrides. Food bank is called only when recommended_action == donate (or high expiry risk)."""
    inventory_id = state.get("inventory_id", "")
    item_data = state.get("item_data", {})
    remaining = state.get("remaining_stock", 0)
    forecasted = state.get("forecasted_demand")
    suggested_action = state.get("suggested_action", "none")
    user_asked_about_waste = (state.get("context") or {}).get("user_asked_about_waste", False)
    preferred_waste_action = (state.get("context") or {}).get("waste_action_preference")

    # Reorder path: no waste decision needed
    if suggested_action == "reorder":
        return {"recommended_action": "reorder", "_decision_overrides": None}

    # Low stock: reorder only — never donate, discount, or bundle (do not include in donation suggestions)
    min_stock = item_data.get("min_stock", 10)
    is_low_stock = (
        state.get("stock_signal") in ("low", "critical")
        or (remaining is not None and min_stock is not None and remaining <= min_stock)
    )
    if is_low_stock:
        return {"recommended_action": "reorder", "_decision_overrides": None}

    # Non-waste path: hold or reorder
    if not user_asked_about_waste and state.get("event_type") != "near_expiry":
        return {"recommended_action": suggested_action or "hold", "_decision_overrides": None}

    # Waste/expiry path: run rule matrix with empty food banks (we fetch food banks only if decision is donate)
    historical_context = state.get("_historical_context") or retrieve_historical_context(inventory_id)
    db_inventory = (historical_context or {}).get("inventory") or {}
    merged_item_data = dict(item_data or {})
    for k in ("item_name", "category", "form", "usage", "use", "item_type", "expiry_date", "selling_price", "min_stock", "max_capacity", "vendor_id"):
        if db_inventory.get(k) is not None:
            merged_item_data[k] = db_inventory.get(k)
    days_until_expiry = _days_until_expiry_from_item(merged_item_data, db_inventory)
    selling_price = merged_item_data.get("selling_price") or db_inventory.get("selling_price")
    # When selling_price is missing, suggest from previous unit_cost (sales) + margin for discount suggestions
    if selling_price is None:
        unit_cost = _latest_unit_cost_from_sales(historical_context.get("sales") or [])
        if unit_cost is not None:
            try:
                selling_price = _suggested_selling_price_from_cost(unit_cost)
            except (TypeError, ValueError):
                pass
    if selling_price is not None:
        try:
            selling_price = float(selling_price)
        except (TypeError, ValueError):
            selling_price = None
    bundle_candidates = state.get("_bundle_candidates") or retrieve_bundle_candidates(inventory_id, merged_item_data, limit=10)
    similar_items = state.get("_similar_items") or retrieve_similar_items_by_embedding(inventory_id, limit=5)
    is_perishable = _is_item_perishable(merged_item_data)
    forecasted = forecasted if forecasted is not None else get_latest_predicted_demand(inventory_id)
    demand_signal = get_demand_signal(forecasted)
    high_demand_bundle_candidates = filter_high_demand_candidates(similar_items if similar_items else bundle_candidates)

    action_key, reasoning, expected_outcome, overrides = pick_one_waste_suggestion(
        state.get("risk_assessment", {}),
        state.get("feasibility_check", {}),
        state.get("cost_impact", {}),
        [],  # no food banks yet; fetch only when action == donate
        bundle_candidates,
        similar_items,
        remaining,
        days_until_expiry,
        merged_item_data.get("item_name", "Item"),
        forecasted,
        selling_price,
        preferred_waste_action=preferred_waste_action,
        allow_donate_without_banks=True,
        is_perishable=is_perishable,
        demand_signal=demand_signal,
        high_demand_bundle_candidates=high_demand_bundle_candidates,
    )
    return {
        "recommended_action": action_key,
        "_decision_overrides": {"reasoning": reasoning, "expected_outcome": expected_outcome, **overrides},
        "_historical_context": historical_context,
        "_bundle_candidates": bundle_candidates,
        "_similar_items": similar_items,
        "_demand_signal": demand_signal,
    }


def _is_item_perishable(item_data: Optional[dict]) -> bool:
    """
    Determine whether an item is perishable.

    Primary source: `item_type` from DB (expected values like "Perishable" / "Non-Perishable").
    Fallback: keyword match over item_type + category + usage for backwards compatibility.
    """
    if not isinstance(item_data, dict):
        return False
    item_type = str(item_data.get("item_type") or "").strip().lower()
    if item_type:
        non_tokens = ("non-perishable", "non perishable", "nonperishable")
        if any(t in item_type for t in non_tokens):
            return False
        if "perishable" in item_type:
            return True
    combined = " ".join([
        item_type,
        str(item_data.get("category") or "").strip().lower(),
        str(item_data.get("usage") or item_data.get("use") or "").strip().lower(),
    ]).strip()
    if not combined:
        return False
    non_tokens = ("non-perishable", "non perishable", "nonperishable")
    if any(t in combined for t in non_tokens):
        return False
    return "perishable" in combined


def get_donation_options(state: DecisionOrchestratorState) -> dict:
    """Call Food Bank subagent ONLY when recommended_action == donate OR (expiry risk high and near expiry)."""
    recommended_action = state.get("recommended_action", "")
    risk_level = (state.get("risk_assessment") or {}).get("risk_level", "")
    event_type = state.get("event_type", "")
    should_fetch = (
        recommended_action == "donate"
        or (risk_level in ("critical", "high") and event_type == "near_expiry")
    )
    if not should_fetch:
        logger.info("[Subagent] Food Bank skipped | reason=not donate (action=%s)", recommended_action)
        return {"nearest_food_banks": state.get("nearest_food_banks", [])}
    inv_id = state.get("inventory_id", "?")
    item_name = (state.get("item_data") or {}).get("item_name", "?")
    logger.info("[Subagent] Calling Food Bank | item=%s | inventory_id=%s", item_name, inv_id)
    try:
        r = requests.post(SUBAGENT_URLS["food_bank"], json={"limit": 5}, headers=_agent_headers(), timeout=5)
        if r.ok:
            data = r.json()
            banks = data.get("nearest_food_banks", [])
            logger.info("[Subagent] Food Bank completed | item=%s | status=ok | banks=%s", item_name, len(banks))
            return {"nearest_food_banks": banks}
        logger.info("[Subagent] Food Bank completed | item=%s | status=error | http=%s", item_name, r.status_code)
    except Exception as e:
        logger.warning(f"Food bank lookup failed: {e}")
        logger.info("[Subagent] Food Bank completed | item=%s | status=error", item_name)
    return {"nearest_food_banks": state.get("nearest_food_banks", [])}


def generate_explanation(state: DecisionOrchestratorState) -> dict:
    """Call Explanation Generation subagent with the actual recommended action and full state."""
    if (state.get("context") or {}).get("fast_mode"):
        return {"explanation": {"explanation": "", "llm_enhanced": False}}
    inv_id = state.get("inventory_id", "?")
    item_name = (state.get("item_data") or {}).get("item_name", "?")
    logger.info("[Subagent] Calling Explanation | item=%s | inventory_id=%s", item_name, inv_id)
    # Use the final recommended action (from recommendation or decision engine), not initial suggested_action
    rec = state.get("recommendation") or {}
    recommended_action = rec.get("action") or state.get("recommended_action") or state.get("suggested_action") or "none"
    try:
        fd = state.get("forecasted_demand")
        forecasted_demand = float(fd) if fd is not None else 0.0
    except (TypeError, ValueError):
        forecasted_demand = 0.0
    payload = {
        "inventory_id": state.get("inventory_id"),
        "suggested_action": recommended_action,
        "risk_assessment": state.get("risk_assessment", {}),
        "feasibility_check": state.get("feasibility_check", {}),
        "cost_impact": state.get("cost_impact", {}),
        "item_data": state.get("item_data", {}),
        "forecasted_demand": forecasted_demand,
        "context": state.get("context", {}),
        "nearest_food_banks": state.get("nearest_food_banks", []),
    }
    
    try:
        r = requests.post(SUBAGENT_URLS["explanation"], json=payload, headers=_agent_headers(), timeout=10)
        explanation = r.json() if r.ok else {"error": f"HTTP {r.status_code}"}
        status = "ok" if not explanation.get("error") else "error"
        logger.info("[Subagent] Explanation completed | item=%s | status=%s", item_name, status)
    except Exception as e:
        logger.error(f"Explanation generation failed: {e}")
        explanation = {"error": str(e), "explanation": "Unable to generate explanation."}
        logger.info("[Subagent] Explanation completed | item=%s | status=error", item_name)
    
    return {"explanation": explanation}


def synthesize_recommendation(state: DecisionOrchestratorState) -> dict:
    """Synthesize final recommendation using LLM, RAG context, and embedding-based similar items."""
    inventory_id = state.get("inventory_id", "")
    historical_context = state.get("_historical_context") or retrieve_historical_context(inventory_id)
    similar_items = state.get("_similar_items") or retrieve_similar_items_by_embedding(inventory_id, limit=5)
    item_data = state.get("item_data", {})
    db_inventory = (historical_context or {}).get("inventory") or {}
    merged_item_data = dict(item_data or {})
    for k in ("item_name", "category", "form", "usage", "use", "item_type", "expiry_date", "selling_price", "min_stock", "max_capacity", "vendor_id"):
        if db_inventory.get(k) is not None:
            merged_item_data[k] = db_inventory.get(k)

    # Bundle candidates: other items from inventory (same category/form/use) for exact bundle suggestion
    bundle_candidates = state.get("_bundle_candidates") or retrieve_bundle_candidates(inventory_id, merged_item_data, limit=10)
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

    days_until_expiry = _days_until_expiry_from_item(merged_item_data, db_inventory)
    expiry_date = merged_item_data.get("expiry_date") or merged_item_data.get("expiryDate") or db_inventory.get("expiry_date") or db_inventory.get("expiryDate")
    selling_price = merged_item_data.get("selling_price") or db_inventory.get("selling_price")
    # When selling_price is missing, suggest from previous unit_cost (sales) + margin
    if selling_price is None:
        unit_cost = _latest_unit_cost_from_sales(historical_context.get("sales") or [])
        if unit_cost is not None:
            try:
                selling_price = _suggested_selling_price_from_cost(unit_cost)
            except (TypeError, ValueError):
                pass
    if selling_price is not None:
        try:
            selling_price = float(selling_price)
        except (TypeError, ValueError):
            selling_price = None

    # Dynamic discount (urgency + surplus) for context; intervention selection uses pick_one_waste_suggestion
    remaining = state.get("remaining_stock", 0)
    forecasted = state.get("forecasted_demand")
    if forecasted is None:
        forecasted = get_latest_predicted_demand(inventory_id)
    demand_signal = state.get("_demand_signal") or get_demand_signal(forecasted)
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
Min Stock: {merged_item_data.get('min_stock', 0)}
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
    
    use_llm = bool(llm) and not bool((state.get("context") or {}).get("fast_mode"))
    if use_llm:
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
            # Reorder (low stock): one clear suggestion — reorder by expiry date; suggest 1-2% price increase
            if suggested_action == "reorder" or action == "reorder":
                expiry_str = f" by {expiry_date}" if expiry_date else ""
                reasoning = f"Reorder{expiry_str} to maintain stock; prioritize by expiry date."
                price_inc_pct, increased_price = _reorder_price_increase_suggestion(
                    merged_item_data,
                    historical_context,
                    remaining_stock=state.get("remaining_stock"),
                    days_until_expiry=days_until_expiry,
                )
                if price_inc_pct is not None:
                    reasoning += f" Consider a {price_inc_pct:.0f}% price increase to capture margin while restocking."
                expected_outcome = "Stock levels will be maintained and waste minimized."
                recommendation = {
                    "action": "reorder",
                    "priority": llm_result.get("priority", "Medium"),
                    "reasoning": reasoning,
                    "expected_outcome": strip_markdown(expected_outcome),
                    "suggested_discount_percent": None,
                    "suggested_selling_price": increased_price,
                    "bundle_suggestion": None,
                    "waste_action": None,
                    "discard_reason": None,
                    "llm_enhanced": True,
                }
                if price_inc_pct is not None:
                    recommendation["suggested_price_increase_percent"] = price_inc_pct
            elif user_asked_about_waste:
                # Use decision engine result when already computed (pipeline ran decision_engine first)
                overrides = state.get("_decision_overrides") or {}
                rec_action = state.get("recommended_action")
                unit_cost = _latest_unit_cost_from_sales(historical_context.get("sales") or [])
                def _cap_price_above_cost(price_val):
                    if price_val is None or unit_cost is None:
                        return price_val
                    try:
                        p, uc = float(price_val), float(unit_cost)
                        return max(p, uc) if p < uc else p
                    except (TypeError, ValueError):
                        return price_val
                if rec_action and overrides:
                    suggested_price_val = overrides.get("suggested_selling_price")
                    suggested_price_val = _cap_price_above_cost(suggested_price_val)
                    recommendation = {
                        "action": rec_action,
                        "priority": llm_result.get("priority", "Medium"),
                        "reasoning": overrides.get("reasoning", ""),
                        "expected_outcome": overrides.get("expected_outcome", ""),
                        "suggested_discount_percent": overrides.get("suggested_discount_percent"),
                        "suggested_selling_price": suggested_price_val,
                        "bundle_suggestion": overrides.get("bundle_suggestion"),
                        "waste_action": strip_markdown(llm_result.get("waste_action") or "") or None,
                        "discard_reason": discard_reason,
                        "llm_enhanced": True,
                    }
                    # Use state's nearest_food_banks (filled when recommended_action was donate)
                    if rec_action == "donate" and state.get("nearest_food_banks"):
                        recommendation["_nearest_food_banks_override"] = state["nearest_food_banks"]
                else:
                    preferred = (state.get("context") or {}).get("waste_action_preference")
                    _is_perishable = _is_item_perishable(merged_item_data)
                    _hd_candidates = filter_high_demand_candidates(similar_items if similar_items else bundle_candidates)
                    _pk, reasoning_one, expected_one, overrides = pick_one_waste_suggestion(
                        state.get("risk_assessment", {}),
                        state.get("feasibility_check", {}),
                        state.get("cost_impact", {}),
                        state.get("nearest_food_banks", []),
                        bundle_candidates,
                        similar_items,
                        state.get("remaining_stock", 0),
                        days_until_expiry,
                        merged_item_data.get("item_name", "Item"),
                        state.get("forecasted_demand"),
                        selling_price,
                        preferred_waste_action=preferred,
                        is_perishable=_is_perishable,
                        demand_signal=demand_signal,
                        high_demand_bundle_candidates=_hd_candidates,
                    )
                    suggested_price_val = _cap_price_above_cost(overrides.get("suggested_selling_price"))
                    recommendation = {
                        "action": _pk,
                        "priority": llm_result.get("priority", "Medium"),
                        "reasoning": reasoning_one,
                        "expected_outcome": expected_one,
                        "suggested_discount_percent": overrides.get("suggested_discount_percent"),
                        "suggested_selling_price": suggested_price_val,
                        "bundle_suggestion": overrides.get("bundle_suggestion"),
                        "waste_action": strip_markdown(llm_result.get("waste_action") or "") or None,
                        "discard_reason": discard_reason,
                        "llm_enhanced": True,
                    }
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
                reasoning = f"Reorder{expiry_str} to maintain stock; prioritize by expiry date."
                price_inc_pct, increased_price = _reorder_price_increase_suggestion(
                    merged_item_data,
                    None,
                    remaining_stock=state.get("remaining_stock"),
                    days_until_expiry=days_until_expiry,
                )
                if price_inc_pct is not None:
                    reasoning += f" Consider a {price_inc_pct:.0f}% price increase to capture margin while restocking."
                recommendation = {
                    "action": "reorder",
                    "priority": "Medium",
                    "reasoning": reasoning,
                    "expected_outcome": "Stock levels will be maintained and waste minimized.",
                    "suggested_discount_percent": None,
                    "suggested_selling_price": increased_price,
                    "bundle_suggestion": None,
                    "discard_reason": None,
                    "llm_enhanced": False,
                }
                if price_inc_pct is not None:
                    recommendation["suggested_price_increase_percent"] = price_inc_pct
            elif user_asked_about_waste:
                overrides = state.get("_decision_overrides") or {}
                rec_action = state.get("recommended_action")
                if rec_action and overrides:
                    recommendation = {
                        "action": rec_action,
                        "priority": "Medium",
                        "reasoning": overrides.get("reasoning", ""),
                        "expected_outcome": overrides.get("expected_outcome", ""),
                        "suggested_discount_percent": overrides.get("suggested_discount_percent"),
                        "suggested_selling_price": overrides.get("suggested_selling_price"),
                        "bundle_suggestion": overrides.get("bundle_suggestion"),
                        "discard_reason": None,
                        "llm_enhanced": False,
                    }
                    if rec_action == "donate" and state.get("nearest_food_banks"):
                        recommendation["_nearest_food_banks_override"] = state["nearest_food_banks"]
                else:
                    preferred = (state.get("context") or {}).get("waste_action_preference")
                    _is_perishable = _is_item_perishable(merged_item_data)
                    _hd_candidates = filter_high_demand_candidates(similar_items if similar_items else bundle_candidates)
                    _pk, reasoning_one, expected_one, overrides = pick_one_waste_suggestion(
                        state.get("risk_assessment", {}),
                        state.get("feasibility_check", {}),
                        state.get("cost_impact", {}),
                        state.get("nearest_food_banks", []),
                        bundle_candidates,
                        similar_items,
                        state.get("remaining_stock", 0),
                        days_until_expiry,
                        merged_item_data.get("item_name", "Item"),
                        state.get("forecasted_demand"),
                        selling_price,
                        preferred_waste_action=preferred,
                        is_perishable=_is_perishable,
                        demand_signal=demand_signal,
                        high_demand_bundle_candidates=_hd_candidates,
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
            reasoning = f"Reorder{expiry_str} to maintain stock; prioritize by expiry date."
            price_inc_pct, increased_price = _reorder_price_increase_suggestion(
                state.get("item_data", {}),
                None,
                remaining_stock=state.get("remaining_stock"),
                days_until_expiry=days_until_expiry,
            )
            if price_inc_pct is not None:
                reasoning += f" Consider a {price_inc_pct:.0f}% price increase to capture margin while restocking."
            recommendation = {
                "action": "reorder",
                "priority": priority,
                "reasoning": reasoning,
                "expected_outcome": "Stock levels will be maintained and waste minimized.",
                "suggested_discount_percent": None,
                "suggested_selling_price": increased_price,
                "bundle_suggestion": None,
                "discard_reason": None,
                "llm_enhanced": False,
            }
            if price_inc_pct is not None:
                recommendation["suggested_price_increase_percent"] = price_inc_pct
        elif user_asked_about_waste:
            overrides = state.get("_decision_overrides") or {}
            rec_action = state.get("recommended_action")
            if rec_action and overrides:
                recommendation = {
                    "action": rec_action,
                    "priority": priority,
                    "reasoning": overrides.get("reasoning", ""),
                    "expected_outcome": overrides.get("expected_outcome", ""),
                    "suggested_discount_percent": overrides.get("suggested_discount_percent"),
                    "suggested_selling_price": overrides.get("suggested_selling_price"),
                    "bundle_suggestion": overrides.get("bundle_suggestion"),
                    "discard_reason": None,
                    "llm_enhanced": False,
                }
                if rec_action == "donate" and state.get("nearest_food_banks"):
                    recommendation["_nearest_food_banks_override"] = state["nearest_food_banks"]
            else:
                preferred = (state.get("context") or {}).get("waste_action_preference")
                _is_perishable = _is_item_perishable(merged_item_data)
                _hd_candidates = filter_high_demand_candidates(similar_items if similar_items else bundle_candidates)
                _pk, reasoning_one, expected_one, overrides = pick_one_waste_suggestion(
                    state.get("risk_assessment", {}),
                    state.get("feasibility_check", {}),
                    state.get("cost_impact", {}),
                    state.get("nearest_food_banks", []),
                    bundle_candidates,
                    similar_items,
                    state.get("remaining_stock", 0),
                    days_until_expiry,
                    merged_item_data.get("item_name", "Item"),
                    state.get("forecasted_demand"),
                    selling_price,
                    preferred_waste_action=preferred,
                    is_perishable=_is_perishable,
                    demand_signal=demand_signal,
                    high_demand_bundle_candidates=_hd_candidates,
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

    # Priority override (risk management): Perishable/urgent items should surface as High priority.
    try:
        _is_perishable = _is_item_perishable(merged_item_data)
    except Exception:
        _is_perishable = False
    _action = (recommendation or {}).get("action", "") or ""
    if _action in ("discard", "reorder"):
        recommendation["priority"] = "High"
    elif days_until_expiry is not None and 0 <= days_until_expiry <= DONATE_URGENT_DAYS:
        recommendation["priority"] = "High"
    elif _is_perishable and _action in ("donate", "discount", "bundle"):
        recommendation["priority"] = "High"
    elif _action in ("donate", "discount", "bundle"):
        recommendation["priority"] = "Medium"
    elif _action:
        recommendation["priority"] = "Low"

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
# Build Graph (intent-based: call only relevant subagents)
# -----------------------------------------------------------------------------


def _should_call_food_bank(state: DecisionOrchestratorState) -> str:
    """Only call food bank when recommended_action == donate or high expiry risk."""
    recommended_action = state.get("recommended_action", "")
    risk_level = (state.get("risk_assessment") or {}).get("risk_level", "")
    event_type = state.get("event_type", "")
    if recommended_action == "donate" or (risk_level in ("critical", "high") and event_type == "near_expiry"):
        return "get_donation_options"
    return "synthesize_recommendation"


def _subagents_called_from_state(final_state: dict) -> dict:
    """Build a summary of which subagents were called and their status (for verification in logs + response)."""
    risk = final_state.get("risk_assessment") or {}
    feasibility = final_state.get("feasibility_check") or {}
    cost = final_state.get("cost_impact") or {}
    explanation = final_state.get("explanation") or {}
    rec = final_state.get("recommendation") or {}
    recommended_action = rec.get("action") or final_state.get("recommended_action") or ""
    nearest_food_banks = final_state.get("nearest_food_banks") or []

    return {
        "risk": "error" if risk.get("error") else "ok",
        "feasibility": "error" if feasibility.get("error") else "ok",
        "cost_impact": "error" if cost.get("error") else "ok",
        "food_bank": "skipped" if recommended_action != "donate" else ("ok" if nearest_food_banks else "ok"),
        "explanation": "error" if explanation.get("error") else "ok",
    }


def build_orchestration_graph() -> StateGraph:
    """Build the decision orchestration StateGraph. STRICT order: Risk -> Feasibility & Cost (merged) -> Decision -> (Food bank if donate) -> Synthesize -> Explanation."""
    builder = StateGraph(DecisionOrchestratorState)

    builder.add_node("assess_risk", assess_risk)
    builder.add_node("check_feasibility_and_cost", check_feasibility_and_cost)
    builder.add_node("run_decision_engine", run_decision_engine)
    builder.add_node("get_donation_options", get_donation_options)
    builder.add_node("synthesize_recommendation", synthesize_recommendation)
    builder.add_node("generate_explanation", generate_explanation)

    builder.add_edge(START, "assess_risk")
    builder.add_edge("assess_risk", "check_feasibility_and_cost")
    builder.add_edge("check_feasibility_and_cost", "run_decision_engine")
    builder.add_conditional_edges(
        "run_decision_engine",
        _should_call_food_bank,
        {
            "get_donation_options": "get_donation_options",
            "synthesize_recommendation": "synthesize_recommendation",
        },
    )
    builder.add_edge("get_donation_options", "synthesize_recommendation")
    builder.add_edge("synthesize_recommendation", "generate_explanation")
    builder.add_edge("generate_explanation", END)

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


@mcp.tool()
def orchestrate(payload: dict) -> dict:
    """
    MCP version of POST /orchestrate.
    Accepts the same JSON payload shape as the REST endpoint and returns the same response fields.
    """
    payload = payload or {}
    _item = payload.get("item_data") or {}
    _fd = (
        payload.get("forecasted_demand")
        or payload.get("predicted_demand")
        or _item.get("forecasted_demand")
        or _item.get("predicted_demand")
    )
    initial_state: DecisionOrchestratorState = {
        "inventory_id": payload.get("inventory_id", ""),
        "event_type": payload.get("event_type", "low_stock"),
        "remaining_stock": payload.get("remaining_stock"),
        "suggested_action": payload.get("suggested_action", "reorder"),
        "stock_signal": payload.get("stock_signal", "low"),
        "consumption_signal": payload.get("consumption_signal", "normal"),
        "forecasted_demand": _fd,
        "item_data": payload.get("item_data", {}),
        "consumption_history": payload.get("consumption_history", []),
        "context": payload.get("context", {}),
    }
    graph = get_orchestration_graph()
    final_state = graph.invoke(initial_state)
    subagents_called = _subagents_called_from_state(final_state)
    return {
        "recommendation": final_state.get("recommendation", {}),
        "risk_assessment": final_state.get("risk_assessment", {}),
        "feasibility_check": final_state.get("feasibility_check", {}),
        "cost_impact": final_state.get("cost_impact", {}),
        "explanation": final_state.get("explanation", {}),
        "subagents_called": subagents_called,
    }


if __name__ == "__main__":
    # MCP-only: expose tools at http://host:port/mcp
    mcp_port = int(os.getenv("MCP_PORT", "9100"))
    host = os.getenv("MCP_HOST", "0.0.0.0")
    logger.info("Starting Decision Orchestrator MCP server on %s:%s", host, mcp_port)
    mcp.run(transport="http", host=host, port=mcp_port)
