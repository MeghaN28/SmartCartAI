"""Chat Agent – Orchestrator that handles conversational queries, checks inventory, calls decision agent, and stores suggestions."""
import os
import logging
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime

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


def get_items_needing_attention(query: str) -> List[Dict]:
    """Get inventory items that need attention based on the query."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        query_lower = query.lower()
        
        # Determine what items to check based on query
        if any(word in query_lower for word in ["low stock", "low in stock", "reorder", "suggest", "recommend"]):
            # Get all low stock items
            cur.execute("""
                SELECT inventory_id, item_name, category, opening_stock as remaining_stock, 
                       min_stock, max_capacity, vendor_id
                FROM inventory
                WHERE opening_stock <= min_stock
                ORDER BY opening_stock ASC
                LIMIT 20
            """)
        elif any(word in query_lower for word in ["all", "everything", "check"]):
            # Get all items
            cur.execute("""
                SELECT inventory_id, item_name, category, opening_stock as remaining_stock,
                       min_stock, max_capacity, vendor_id
                FROM inventory
                ORDER BY opening_stock ASC
                LIMIT 20
            """)
        else:
            # Get low stock items by default
            cur.execute("""
                SELECT inventory_id, item_name, category, opening_stock as remaining_stock,
                       min_stock, max_capacity, vendor_id
                FROM inventory
                WHERE opening_stock <= min_stock
                ORDER BY opening_stock ASC
                LIMIT 10
            """)
        
        items = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return items
    except Exception as e:
        logger.error(f"Error getting items: {e}")
        return []


def get_consumption_history(inventory_id: str) -> List[Dict]:
    """Get consumption history for an item."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT date, quantity_consumed, remaining_stock, department, consumption_reason
            FROM consumption
            WHERE inventory_id = %s
            ORDER BY date DESC
            LIMIT 30
        """, (inventory_id,))
        history = [dict(row) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return history
    except Exception as e:
        logger.error(f"Error getting consumption history: {e}")
        return []


def calculate_forecasted_demand(consumption_history: List[Dict]) -> float:
    """Calculate forecasted demand using simple moving average."""
    if not consumption_history:
        return 0.0
    consumptions = [float(h.get('quantity_consumed', 0)) for h in consumption_history[:7] if h.get('quantity_consumed')]
    if not consumptions:
        return 0.0
    return sum(consumptions) / len(consumptions)


def call_decision_orchestrator(item: Dict) -> Optional[Dict]:
    """Call the Decision Orchestrator Agent for an item."""
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
        
        payload = {
            "inventory_id": item['inventory_id'],
            "event_type": "low_stock" if stock_signal != "normal" else "monitoring",
            "remaining_stock": remaining_stock,
            "suggested_action": "reorder" if stock_signal != "normal" else "none",
            "stock_signal": stock_signal,
            "consumption_signal": "normal",
            "forecasted_demand": forecasted_demand,
            "item_data": {
                "item_name": item.get('item_name'),
                "category": item.get('category'),
                "min_stock": min_stock,
                "max_capacity": item.get('max_capacity', 1000),
                "vendor_id": item.get('vendor_id'),
            },
            "consumption_history": consumption_history[:10],
            "context": {},
        }
        
        response = requests.post(f"{DECISION_ORCHESTRATOR_URL}/orchestrate", json=payload, timeout=10)
        if response.ok:
            return response.json()
        else:
            logger.error(f"Decision orchestrator returned {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error calling decision orchestrator: {e}")
        return None


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
        
        cur.execute("""
            INSERT INTO suggestions (
                inventory_id, item_name, user_query, action, priority, reasoning,
                expected_outcome, risk_level, risk_score, is_feasible,
                estimated_cost, within_budget, explanation, current_stock,
                min_stock, forecasted_demand, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
            'pending'
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


def process_chat_query(query: str, session_id: str = None) -> Dict:
    """Process a chat query: check inventory, call decision agent, store suggestions."""
    query_lower = query.lower()
    
    # Check if this is a question that should trigger suggestions
    should_generate_suggestions = any(word in query_lower for word in [
        "suggest", "recommend", "what should", "what do", "check", "analyze",
        "low stock", "reorder", "need", "help"
    ])
    
    # Get items that need attention
    items = get_items_needing_attention(query)
    
    suggestions_generated = []
    answer_parts = []
    
    if should_generate_suggestions and items:
        answer_parts.append(f"I've analyzed your inventory and found {len(items)} item(s) that need attention.")
        answer_parts.append("Here are my recommendations:\n")
        
        # Process each item through decision orchestrator
        for item in items[:10]:  # Limit to 10 items
            try:
                recommendation = call_decision_orchestrator(item)
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
                        
                        rec = recommendation.get('recommendation', {})
                        answer_parts.append(
                            f"• {item['item_name']}: {rec.get('action', 'none').upper()} "
                            f"({rec.get('priority', 'Medium')} priority) - {rec.get('reasoning', '')[:100]}"
                        )
            except Exception as e:
                logger.error(f"Error processing item {item.get('inventory_id')}: {e}")
        
        if suggestions_generated:
            answer_parts.append(f"\n✅ Generated {len(suggestions_generated)} suggestion(s). Check the Suggestion Log to see all details.")
        else:
            answer_parts.append("\nNo suggestions were generated. All items appear to be in good standing.")
    
    else:
        # Regular Q&A mode - just answer the question
        if llm:
            try:
                # Get summary context
                conn = get_db_connection()
                cur = conn.cursor()
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_items,
                        SUM(opening_stock) as total_stock,
                        COUNT(CASE WHEN opening_stock <= min_stock THEN 1 END) as low_stock_count
                    FROM inventory
                """)
                summary = dict(cur.fetchone())
                cur.close()
                conn.close()
                
                context_text = f"""
Inventory Summary:
- Total Items: {summary.get('total_items', 0)}
- Total Stock: {summary.get('total_stock', 0)}
- Low Stock Items: {summary.get('low_stock_count', 0)}
"""
                
                prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are a helpful inventory management assistant for SmartCartAI.
Answer questions about inventory, stock levels, and provide general information.
Be concise and helpful."""),
                    ("user", "Question: {query}\n\nContext:\n{context}\n\nAnswer:"),
                ])
                
                chain = prompt | llm
                response = chain.invoke({"query": query, "context": context_text})
                answer = response.content if hasattr(response, 'content') else str(response)
                answer_parts.append(answer)
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
    
    query = payload.get("query", "").strip()
    session_id = payload.get("session_id")
    
    if not query:
        return jsonify({"error": "query is required"}), 400
    
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
