#!/usr/bin/env python3
"""Run the real Decision Orchestrator pipeline across all near-expiry Perishable
items and persist results via the Chat Agent's own save_suggestion(), producing a
fresh, honest suggestions dataset for scripts/waste_graphs.py to summarize.

This imports Agents/decision-orchestration-agent/subagents/chat/agent.py as a module
(guarded by `if __name__ == "__main__"` there, so importing it does not start its MCP
server) and calls its existing call_decision_orchestrator_batch()/save_suggestion()
functions -- the same code path a live chat query like "What's going to waste?" uses --
rather than re-implementing orchestration logic here.

Requires the Flask subagents (risk/cost/explanation/food-bank) and the Decision
Orchestrator to already be running (e.g. via ./start_agents_mcp.sh).

Run: python3 database/scripts/run_full_waste_evaluation.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "Agents"))
sys.path.insert(0, str(ROOT / "Agents" / "decision-orchestration-agent" / "subagents" / "chat"))

import agent as chat_agent  # noqa: E402

BATCH_SIZE = 8  # matches call_decision_orchestrator_batch's internal cap


def main():
    items = chat_agent.get_near_expiry_items(within_days=14)
    items = [it for it in items if it.get("item_type") == "Perishable"]

    if not items:
        print("No near-expiry Perishable items found; nothing to evaluate.")
        return

    print(f"Evaluating {len(items)} near-expiry Perishable item(s):")
    for it in items:
        print(f"  - {it['item_name']} (expiry {it.get('expiry_date')}, stock {it.get('remaining_stock')})")

    saved = 0
    failed = []
    for i in range(0, len(items), BATCH_SIZE):
        chunk = items[i:i + BATCH_SIZE]
        recs, err = chat_agent.call_decision_orchestrator_batch(
            chunk, user_asked_about_waste=True, intent="waste"
        )
        if err:
            print(f"Batch error: {err}")
        if not recs:
            failed.extend(it["item_name"] for it in chunk)
            continue

        rec_by_id = {r["inventory_id"]: r for r in recs}
        for it in chunk:
            rec = rec_by_id.get(it["inventory_id"])
            if not rec:
                failed.append(it["item_name"])
                continue
            suggestion_id = chat_agent.save_suggestion(
                "[evaluation] What's going to waste?", it, rec
            )
            action = (rec.get("recommendation") or {}).get("action", "none")
            if suggestion_id:
                saved += 1
                print(f"  Saved suggestion {suggestion_id}: {it['item_name']} -> {action}")
            else:
                failed.append(it["item_name"])

    print(f"\nDone. Saved {saved}/{len(items)} suggestions.")
    if failed:
        print(f"Failed/no recommendation for: {failed}")


if __name__ == "__main__":
    main()
