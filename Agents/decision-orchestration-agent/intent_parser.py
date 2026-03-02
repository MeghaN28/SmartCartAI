"""Intent detection for inventory chatbot. Classifies user questions into action categories.

Used by the orchestrator and chatbot to route queries and select the correct pipeline.
Intent categories: waste, expiry, reorder, discount, bundle, donate, discard, stock_status, forecast, recommendation.
"""
import re
from typing import Dict, Optional

# Intent constants for consistent routing
INTENT_WASTE = "waste"
INTENT_EXPIRY = "expiry"
INTENT_REORDER = "reorder"
INTENT_DISCOUNT = "discount"
INTENT_BUNDLE = "bundle"
INTENT_DONATE = "donate"
INTENT_DISCARD = "discard"
INTENT_STOCK_STATUS = "stock_status"
INTENT_FORECAST = "forecast"
INTENT_RECOMMENDATION = "recommendation"
INTENT_PRICING = "pricing"
INTENT_GENERAL = "general"

# Keywords per intent (order matters: more specific first)
INTENT_KEYWORDS = [
    (INTENT_STOCK_STATUS, [
        "stock for", "stock of", "tell me stock", "what is the stock", "how much", "how many",
        "current stock", "stock level", "inventory level", "how much stock", "stock status",
    ]),
    (INTENT_FORECAST, [
        "forecast demand", "demand for", "demand forecast", "predict demand", "demand prediction",
    ]),
    (INTENT_DONATE, [
        "which items to donate", "which items can be donated", "items to donate",
        "donate", "donation", "donate to", "food bank", "give away", "can be donated",
        "what can be donated", "where to donate",
    ]),
    (INTENT_DISCOUNT, [
        "discount", "discount %", "discount percent", "mark down", "reduce price",
        "which items should be discounted", "what should we discount",
    ]),
    (INTENT_BUNDLE, [
        "bundle", "bundled", "bundling", "which items should be bundled", "can be bundled",
    ]),
    (INTENT_DISCARD, [
        "discard", "dispose", "throw away", "throwout", "throw out", "dump",
        "expired", "past expiry", "past expiration", "unsafe to sell",
        "which items to discard", "what items to discard", "items to discard",
    ]),
    (INTENT_WASTE, [
        "waste", "going to waste", "sell soon", "expir", "expiry", "sell or donate",
        "anything to sell", "anything to donate", "whats going to waste", "reduce waste",
    ]),
    (INTENT_EXPIRY, [
        "going to expire", "expiring soon", "expire", "near expiry", "expiry date",
        "what is going to expire", "what will expire",
    ]),
    (INTENT_PRICING, [
        "pricing", "price", "increase price", "markup", "price increase",
    ]),
    (INTENT_REORDER, [
        "low stock", "reorder", "re order", "re-order",
        "check inventory", "out of stock", "need to order",
        "what to reorder", "should i reorder", "reorder milk", "running low",
    ]),
    (INTENT_RECOMMENDATION, [
        "suggest", "recommend", "what should", "what do", "check", "analyze",
        "what actions", "actions should i take", "recommendations", "what can i do",
    ]),
]


def parse_intent(query: str) -> Dict[str, str]:
    """Detect primary intent from user message. Rule-based; one intent per query.

    Returns:
        {"intent": "<waste|expiry|reorder|discount|bundle|donate|stock_status|forecast|recommendation|pricing|general>",
         "waste_related": True/False}
    """
    if not query or not isinstance(query, str):
        return {"intent": INTENT_GENERAL, "waste_related": False}

    q = query.lower().strip()
    # Normalize common spacing/hyphen variants so keyword matching is robust.
    q = re.sub(r"\bre\s*[-\s]+\s*order\b", "reorder", q)

    for intent, keywords in INTENT_KEYWORDS:
        if any(kw in q for kw in keywords):
            waste_related = intent in (
                INTENT_WASTE, INTENT_EXPIRY, INTENT_DONATE, INTENT_DISCOUNT, INTENT_BUNDLE, INTENT_DISCARD
            )
            return {"intent": intent, "waste_related": waste_related}

    return {"intent": INTENT_GENERAL, "waste_related": False}


def get_waste_action_preference(query: str) -> Optional[str]:
    """If the user asks specifically for one waste action, return it: 'discount' | 'donate' | 'bundle' | 'discard'."""
    if not query:
        return None
    q = query.lower()
    if any(w in q for w in ["donate", "donation", "food bank"]):
        return "donate"
    if any(w in q for w in ["discount", "discount %", "mark down", "reduce price"]):
        return "discount"
    if any(w in q for w in ["bundle", "bundled", "bundling"]):
        return "bundle"
    if any(w in q for w in ["discard", "dispose", "throw away", "expired"]):
        return "discard"
    return None
