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
        current_embedding = list(row["embedding"]) if row["embedding"] else []

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
            emb = r.get("embedding")
            if emb is None:
                continue
            emb_list = list(emb) if hasattr(emb, "__iter__") and not isinstance(emb, str) else emb
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
    payload = {
        "inventory_id": state.get("inventory_id"),
        "suggested_action": state.get("suggested_action"),
        "item_data": state.get("item_data", {}),
        "forecasted_demand": state.get("forecasted_demand"),
        "context": state.get("context", {}),
    }
    
    try:
        r = requests.post(SUBAGENT_URLS["cost_impact"], json=payload, timeout=5)
        cost_impact = r.json() if r.ok else {"error": f"HTTP {r.status_code}"}
    except Exception as e:
        logger.error(f"Cost impact assessment failed: {e}")
        cost_impact = {"error": str(e), "estimated_cost": 0, "within_budget": True}
    
    return {"cost_impact": cost_impact}


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

    item_data = state.get("item_data", {})
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

    # Signal to LLM when user asked about waste/expiry so it suggests discount or sell/donate
    user_asked_about_waste = (
        state.get("event_type") == "near_expiry"
        or state.get("context", {}).get("user_asked_about_waste")
    )
    waste_hint = "\nUser asked about waste/expiry (e.g. 'What's going to waste?'): Yes. Prefer suggesting discount or 'sell or donate soon' to reduce waste." if user_asked_about_waste else ""

    # Prepare context for LLM (include expiry and price for waste/price optimization)
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
Event type: {state.get('event_type', 'unknown')}
{waste_hint}

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

Use: risk, feasibility, cost, historical consumption and sales, and similar-item evidence. If expiry date is near (e.g. within 7-14 days), consider suggesting discount or "sell or donate soon" to reduce waste. If selling price is available and stock is high, you may suggest a small discount to move inventory.

When suggesting discounts or waste reduction, also provide: (1) what percentage discount to give (0-50), (2) what price to sell at if you have current selling price, (3) whether to bundle with other items and with what (e.g. "Bundle with yogurt and granola").

IMPORTANT: Output plain text only in reasoning and expected_outcome. Do not use markdown: no asterisks, no hashtags, no bold/italic. Write in clear sentences so the text can be shown in chat and in the suggestion tab as-is.

Provide a structured recommendation as JSON with:
- action: Exactly one of: reorder, hold, transfer, discard, none
- priority: High, Medium, or Low
- reasoning: 1-2 plain-text sentences (no markdown)
- expected_outcome: One plain-text sentence (no markdown)
- suggested_discount_percent: Optional number 0-50 if a discount is recommended (e.g. near expiry or overstock), else null
- suggested_selling_price: Optional number or string for recommended selling price (e.g. 2.99 or "Sell at $2.99"), else null
- bundle_suggestion: Optional string suggesting what to bundle with (e.g. "Bundle with yogurt and cereal"), else null
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
            discard_reason = llm_result.get("discard_reason")
            if isinstance(discard_reason, str):
                discard_reason = strip_markdown(discard_reason).strip() or None
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
                "action": llm_result.get("action", state.get("suggested_action", "none")),
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
            if user_asked_about_waste:
                recommendation = {
                    "action": "none",
                    "priority": "Medium",
                    "reasoning": "Item is near expiry. Consider a 10-20% discount or sell/donate soon. Bundle with complementary items if possible.",
                    "expected_outcome": "Reduced waste and better use of soon-to-expire inventory.",
                    "suggested_discount_percent": 15,
                    "suggested_selling_price": None,
                    "bundle_suggestion": "Bundle with complementary items to move stock.",
                    "discard_reason": None,
                    "llm_enhanced": False,
                }
            else:
                recommendation = {
                    "action": state.get("suggested_action", "none"),
                    "priority": "Medium",
                    "reasoning": "Based on rule-based analysis",
                    "expected_outcome": "Stock levels will be maintained",
                    "discard_reason": None,
                    "llm_enhanced": False,
                }
    else:
        # Fallback to rule-based recommendation
        risk_level = state.get("risk_assessment", {}).get("risk_level", "medium")
        is_feasible = state.get("feasibility_check", {}).get("is_feasible", True)
        within_budget = state.get("cost_impact", {}).get("within_budget", True)
        
        if risk_level == "high" and is_feasible and within_budget:
            priority = "High"
        elif risk_level == "medium":
            priority = "Medium"
        else:
            priority = "Low"
        
        if user_asked_about_waste:
            recommendation = {
                "action": "none",
                "priority": priority,
                "reasoning": "Item is near expiry. Consider a 10-20% discount or sell/donate soon. Bundle with complementary items if possible.",
                "expected_outcome": "Reduced waste and better use of soon-to-expire inventory.",
                "suggested_discount_percent": 15,
                "suggested_selling_price": None,
                "bundle_suggestion": "Bundle with complementary items to move stock.",
                "discard_reason": None,
                "llm_enhanced": False,
            }
        else:
            recommendation = {
                "action": state.get("suggested_action", "none"),
                "priority": priority,
                "reasoning": f"Risk: {risk_level}, Feasible: {is_feasible}, Budget: {within_budget}",
                "expected_outcome": "Stock levels will be optimized",
                "discard_reason": None,
                "llm_enhanced": False,
            }
    
    return {
        "recommendation": {
            **recommendation,
            "timestamp": datetime.now().isoformat(),
            "inventory_id": state.get("inventory_id"),
            "risk_assessment": state.get("risk_assessment", {}),
            "feasibility_check": state.get("feasibility_check", {}),
            "cost_impact": state.get("cost_impact", {}),
            "explanation": state.get("explanation", {}),
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
    builder.add_node("generate_explanation", generate_explanation)
    builder.add_node("synthesize_recommendation", synthesize_recommendation)
    
    # Define flow: Sequential execution through subagents, then explanation and synthesis
    builder.add_edge(START, "assess_risk")
    builder.add_edge("assess_risk", "check_feasibility")
    builder.add_edge("check_feasibility", "assess_cost_impact")
    builder.add_edge("assess_cost_impact", "generate_explanation")
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
    app.run(host="0.0.0.0", port=port, debug=True)
