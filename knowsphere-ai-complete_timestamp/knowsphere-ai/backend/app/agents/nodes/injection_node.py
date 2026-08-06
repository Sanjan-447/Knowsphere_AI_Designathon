"""
Prompt injection check — the graph's first node.

Wraps app.security.prompt_injection_guard.check_for_injection() exactly as
Phase 3 called it. No logic here; this is purely the adapter between "a
function that takes a string" and "a graph node that reads/writes state."
"""
from app.agents.state import GraphState
from app.security.prompt_injection_guard import check_for_injection


def injection_check_node(state: GraphState) -> dict:
    result = check_for_injection(state["question"])
    return {"injection_flagged": result.flagged}
