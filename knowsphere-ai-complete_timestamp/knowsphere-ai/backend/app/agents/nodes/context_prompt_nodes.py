"""
Context Builder and Prompt Builder nodes — thin wrappers around Phase 3's
build_context() and build_prompt(), completely unchanged.
"""
from app.agents.state import GraphState
from app.retrieval.context_builder import build_context
from app.chat.prompt_builder import build_prompt


def context_builder_node(state: GraphState) -> dict:
    context = build_context(state.get("reranked_chunks", []))
    return {"context": context}


def prompt_builder_node(state: GraphState) -> dict:
    prompt_messages = build_prompt(
        question=state["question"],
        context=state["context"],
        conversation_history=list(state["session"].messages),
        role_name=state["current_role"],
    )
    return {"prompt_messages": prompt_messages}
