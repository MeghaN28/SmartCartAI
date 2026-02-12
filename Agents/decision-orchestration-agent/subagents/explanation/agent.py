"""Explanation Generation Subagent – Produces human-readable justifications using Mistral LLM."""
import os
import logging
from typing import Dict
from pathlib import Path

from flask import Flask, request, jsonify
from langchain_core.prompts import ChatPromptTemplate
from langchain_mistralai import ChatMistralAI
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
logger = logging.getLogger("explanation")


def strip_markdown(text: str) -> str:
    """Remove markdown so explanation is plain text in chat and suggestion tab."""
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

# Configuration
MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY", "")
MISTRAL_MODEL = os.getenv("MISTRAL_MODEL", "mistral-medium")

mcp = FastMCP("Explanation Subagent")
app = Flask(__name__)

# Initialize Mistral LLM
llm = None
if MISTRAL_API_KEY:
    try:
        llm = ChatMistralAI(model=MISTRAL_MODEL, mistral_api_key=MISTRAL_API_KEY)
        logger.info("Mistral LLM initialized for explanation generation")
    except Exception as e:
        logger.warning(f"Failed to initialize Mistral LLM: {e}. Will use template-based explanations.")


def generate_explanation(inventory_id: str, suggested_action: str, risk_assessment: Dict,
                        feasibility_check: Dict, cost_impact: Dict, item_data: Dict,
                        forecasted_demand: float, context: Dict) -> Dict:
    """Generate human-readable explanation for the recommendation."""
    
    item_name = item_data.get("item_name", "Unknown Item")
    risk_level = risk_assessment.get("risk_level", "unknown")
    risk_factors = risk_assessment.get("risk_factors", [])
    is_feasible = feasibility_check.get("is_feasible", True)
    constraints = feasibility_check.get("constraints", [])
    estimated_cost = cost_impact.get("estimated_cost", 0)
    within_budget = cost_impact.get("within_budget", True)
    
    # Prepare context for explanation
    context_text = f"""
Item: {item_name} (ID: {inventory_id})
Recommended Action: {suggested_action}
Forecasted Demand: {forecasted_demand:.2f} units/day

Risk Assessment:
- Risk Level: {risk_level}
- Risk Factors: {len(risk_factors)} identified
{chr(10).join(f"  • {rf.get('description', '')}" for rf in risk_factors[:3])}

Feasibility:
- Feasible: {is_feasible}
- Constraints: {len(constraints)} identified
{chr(10).join(f"  • {c.get('description', '')}" for c in constraints[:3])}

Cost Impact:
- Estimated Cost: ${estimated_cost:.2f}
- Within Budget: {within_budget}
"""
    
    if llm:
        try:
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an inventory management expert explaining recommendations to managers.
Provide a clear, concise, and actionable explanation that covers:
1. Why this action is recommended
2. What risks are being addressed
3. What the expected outcome is
4. Any important considerations or constraints

Write in a professional but accessible tone. Keep it under 200 words.
IMPORTANT: Output plain text only. Do not use markdown: no asterisks for bold, no hashtags for headers, no bullet markdown. The text will be shown in the chat and in the suggestion tab as-is."""),
                ("user", "Generate an explanation for this recommendation:\n\n{context}"),
            ])
            
            chain = prompt | llm
            response = chain.invoke({"context": context_text})
            explanation_text = response.content if hasattr(response, 'content') else str(response)
            explanation_text = strip_markdown(explanation_text)
            
            return {
                "explanation": explanation_text,
                "llm_generated": True,
                "timestamp": __import__("datetime").datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"LLM explanation generation failed: {e}")
            # Fall through to template-based
    
    # Template-based explanation (fallback)
    explanation_parts = []
    
    explanation_parts.append(f"Based on the analysis of {item_name}, the recommended action is to {suggested_action}.")
    
    if risk_level in ["critical", "high"]:
        explanation_parts.append(f"This addresses a {risk_level} risk level with {len(risk_factors)} identified risk factors.")
        if risk_factors:
            top_risk = risk_factors[0].get("description", "")
            explanation_parts.append(f"Primary concern: {top_risk}")
    
    if not is_feasible:
        explanation_parts.append("Note: This action has feasibility constraints that need to be addressed.")
        if constraints:
            explanation_parts.append(f"Key constraint: {constraints[0].get('description', '')}")
    
    if estimated_cost > 0:
        explanation_parts.append(f"The estimated cost is ${estimated_cost:.2f}, which is {'within' if within_budget else 'exceeding'} budget limits.")
    
    if forecasted_demand > 0:
        explanation_parts.append(f"Based on consumption patterns, forecasted demand is {forecasted_demand:.2f} units per day.")
    
    explanation_parts.append(f"Taking this action will help maintain optimal inventory levels and prevent stockouts.")
    
    return {
        "explanation": strip_markdown(" ".join(explanation_parts)),
        "llm_generated": False,
        "timestamp": __import__("datetime").datetime.now().isoformat(),
    }


@app.route("/explain", methods=["POST"])
def explain_endpoint():
    """Explanation generation endpoint."""
    payload = request.get_json(silent=True) or {}
    
    inventory_id = payload.get("inventory_id", "")
    suggested_action = payload.get("suggested_action", "none")
    risk_assessment = payload.get("risk_assessment", {})
    feasibility_check = payload.get("feasibility_check", {})
    cost_impact = payload.get("cost_impact", {})
    item_data = payload.get("item_data", {})
    forecasted_demand = payload.get("forecasted_demand", 0.0)
    context = payload.get("context", {})
    
    if not inventory_id:
        return jsonify({"error": "inventory_id required"}), 400
    
    result = generate_explanation(
        inventory_id, suggested_action, risk_assessment,
        feasibility_check, cost_impact, item_data,
        forecasted_demand, context
    )
    return jsonify(result), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({
        "status": "ok",
        "agent": "explanation",
        "mistral_configured": llm is not None,
    }), 200


@mcp.tool()
def explain_recommendation(inventory_id: str, action: str) -> dict:
    """Generate explanation for a recommendation."""
    return generate_explanation(
        inventory_id, action, {}, {}, {}, {}, 0.0, {}
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", "9003"))
    app.run(host="0.0.0.0", port=port, debug=True)
