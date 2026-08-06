"""
LangGraph orchestration module (Phase 4).

Contains NO business logic — every node in nodes/ is a thin wrapper
calling a function or method that already existed before Phase 4
(app.security.prompt_injection_guard, app.retrieval.*, app.chat.*,
app.providers.llm.*). graph.py wires those nodes into a compiled
StateGraph; state.py defines the TypedDict that flows between them.

See app/chat/rag_service.py's module docstring for how this graph is used
by the non-streaming path, and why the streaming path calls the same node
functions directly instead of invoking the compiled graph.
"""
