"""Central orchestrator: connects intent, inventory, and subagents in strict pipeline order.

Execution order (mandatory):
  1. Intent detection (caller or parse_intent)
  2. Fetch relevant inventory (caller or orchestrator)
  3. For each item: Risk Agent -> Feasibility Agent -> Cost Agent -> Decision Engine
     -> Food Bank Agent (only when action == donate or expiry risk high)
     -> Synthesize recommendation -> Explanation Agent
  4. Return final explainable response

This module is the single entry point for the full pipeline. The Flask app in agent.py
invokes run_pipeline() for /orchestrate and /orchestrate_batch.
"""
from typing import Dict, Any, List, Optional

# Lazy import to avoid circular dependency (agent.py imports this for run_pipeline)
_orchestration_graph = None


def get_graph():
    """Return the compiled orchestration graph (Risk -> Feasibility -> Cost -> Decision -> [Food bank] -> Synthesize -> Explanation)."""
    global _orchestration_graph
    if _orchestration_graph is None:
        from agent import get_orchestration_graph
        _orchestration_graph = get_orchestration_graph()
    return _orchestration_graph


def run_pipeline(initial_state: Dict[str, Any]) -> Dict[str, Any]:
    """Run the full pipeline for one item in strict order. Returns final state with recommendation and explanation.

    initial_state must include: inventory_id, event_type, remaining_stock, suggested_action, stock_signal,
    consumption_signal, item_data, consumption_history, context (with optional intent, user_asked_about_waste).
    """
    graph = get_graph()
    return graph.invoke(initial_state)


def run_pipeline_batch(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Run the full pipeline for each item; returns list of results (one per item)."""
    results = []
    for it in items:
        initial_state = {
            "inventory_id": it.get("inventory_id", ""),
            "event_type": it.get("event_type", "low_stock"),
            "remaining_stock": it.get("remaining_stock"),
            "suggested_action": it.get("suggested_action", "reorder"),
            "stock_signal": it.get("stock_signal", "low"),
            "consumption_signal": it.get("consumption_signal", "normal"),
            "forecasted_demand": it.get("forecasted_demand"),
            "item_data": it.get("item_data", {}),
            "consumption_history": it.get("consumption_history", []),
            "context": it.get("context", {}),
        }
        try:
            final_state = run_pipeline(initial_state)
            rec = final_state.get("recommendation", {})
            results.append({
                "inventory_id": initial_state["inventory_id"],
                "item_name": (initial_state.get("item_data") or {}).get("item_name", "Item"),
                "recommendation": rec,
                "risk_assessment": final_state.get("risk_assessment", {}),
                "feasibility_check": final_state.get("feasibility_check", {}),
                "cost_impact": final_state.get("cost_impact", {}),
                "explanation": final_state.get("explanation", {}),
            })
        except Exception as e:
            import logging
            logging.getLogger("orchestrator").error("Pipeline item %s failed: %s", initial_state.get("inventory_id"), e)
            results.append({
                "inventory_id": initial_state["inventory_id"],
                "item_name": (initial_state.get("item_data") or {}).get("item_name", "Item"),
                "recommendation": {
                    "action": "hold",
                    "priority": "Low",
                    "reasoning": "Pipeline error; monitor stock.",
                    "expected_outcome": "Review manually.",
                },
                "risk_assessment": {},
                "feasibility_check": {},
                "cost_impact": {},
                "explanation": {},
            })
    return results
