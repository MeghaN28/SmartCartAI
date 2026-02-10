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
            SELECT date, quantity_consumed, remaining_stock, department, consumption_reason
            FROM consumption
            WHERE inventory_id = %s
            ORDER BY date DESC
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
    """Synthesize final recommendation using LLM and RAG context."""
    # Retrieve historical context for RAG
    historical_context = retrieve_historical_context(state.get("inventory_id", ""))
    
    # Prepare context for LLM
    context_text = f"""
Inventory Item: {state.get('item_data', {}).get('item_name', 'Unknown')}
Current Stock: {state.get('remaining_stock', 0)}
Min Stock: {state.get('item_data', {}).get('min_stock', 0)}
Forecasted Demand: {state.get('forecasted_demand', 0)}
Stock Signal: {state.get('stock_signal', 'unknown')}
Consumption Signal: {state.get('consumption_signal', 'unknown')}

Risk Assessment: {state.get('risk_assessment', {})}
Feasibility: {state.get('feasibility_check', {})}
Cost Impact: {state.get('cost_impact', {})}

Historical Consumption (last 5): {historical_context['consumption'][:5]}
Recent Sales (last 3): {historical_context['sales'][:3]}
"""
    
    if llm:
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert inventory management advisor. Based on the provided context,
analyze the situation and provide a prescriptive recommendation. Consider:
1. Risk factors and their severity
2. Operational feasibility
3. Cost implications
4. Historical patterns

Provide a structured recommendation with:
- action: The recommended action (reorder, hold, transfer, none)
- priority: High, Medium, or Low
- reasoning: Brief explanation
- expected_outcome: What will happen if this action is taken
"""),
                ("user", "Context:\n{context}\n\nProvide a prescriptive recommendation."),
            ])
            
            chain = prompt | llm | JsonOutputParser()
            llm_result = chain.invoke({"context": context_text})
            
            recommendation = {
                "action": llm_result.get("action", state.get("suggested_action", "none")),
                "priority": llm_result.get("priority", "Medium"),
                "reasoning": llm_result.get("reasoning", ""),
                "expected_outcome": llm_result.get("expected_outcome", ""),
                "llm_enhanced": True,
            }
        except Exception as e:
            logger.error(f"LLM synthesis failed: {e}")
            recommendation = {
                "action": state.get("suggested_action", "none"),
                "priority": "Medium",
                "reasoning": "Based on rule-based analysis",
                "expected_outcome": "Stock levels will be maintained",
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
        
        recommendation = {
            "action": state.get("suggested_action", "none"),
            "priority": priority,
            "reasoning": f"Risk: {risk_level}, Feasible: {is_feasible}, Budget: {within_budget}",
            "expected_outcome": "Stock levels will be optimized",
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
    logger.info("Received orchestration request: %s", payload.get("inventory_id"))
    
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
