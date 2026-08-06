"""
Chat module (Phase 3).

Implements: ChatSession/ChatMessage/Citation models, the Prompt Builder,
Citation Engine, and RagService (the top-level Enterprise RAG orchestrator
tying retrieval -> context -> prompt -> LLM -> citations together), plus
the chat API routes (session CRUD, send message, SSE streaming).

Reserved for Phase 4: LangGraph multi-agent orchestration, agent routing,
agent memory. RagService's linear pipeline is deliberately NOT a LangGraph
graph yet — Phase 4 replaces its internals with a graph without changing
the routes that call it.
"""
