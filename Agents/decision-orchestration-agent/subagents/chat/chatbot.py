"""Chatbot entry point: receives user message, calls orchestrator, returns response.

This module is the single entry point for the chat flow. It MUST NOT call subagents directly.
Flow: User Question -> Chatbot -> Orchestrator -> Agents -> Explanation -> Chatbot -> User.
"""
from typing import Dict, Optional
import sys
from pathlib import Path

# Ensure parent (decision-orchestration-agent) is on path for intent_parser
_here = Path(__file__).resolve().parent
_parent = _here.parent.parent
if str(_parent) not in sys.path:
    sys.path.insert(0, str(_parent))


def handle_message(query: str, session_id: Optional[str] = None) -> Dict:
    """Receive a user message, call the orchestrator (via chat agent), return the response.

    The chat agent fetches relevant inventory and then calls the Decision Orchestrator
    (/orchestrate or /orchestrate_batch). It does NOT call risk, feasibility, cost, food bank,
    or explanation subagents directly.
    """
    from agent import process_chat_query
    return process_chat_query(query, session_id=session_id)


# When run as script, start the Flask app (chat agent server)
if __name__ == "__main__":
    from agent import app
    port = int(__import__("os").getenv("PORT", "9006"))
    app.run(host="0.0.0.0", port=port, debug=False)
