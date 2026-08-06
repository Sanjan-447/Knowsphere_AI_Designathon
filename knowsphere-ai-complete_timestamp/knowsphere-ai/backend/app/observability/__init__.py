"""
Observability module (Phase 5): LangSmith configuration and tracing.

Implements: ObservabilityConfig (the singleton settings row — this is
where a LangSmith API key is stored, encrypted, admin-managed via
/api/v1/observability/langsmith), and traced_invoke() (wraps the RAG
graph's non-streaming invocation in LangSmith tracing when configured).

Honest limitation: this sandbox cannot reach smith.langchain.com, so while
this is written against LangSmith's real SDK, live trace visibility has
not been verified from this environment — that's on the operator once a
real key is configured. See service.py's docstring for the full explanation.

The streaming chat path is NOT traced through LangSmith — it never calls
the compiled graph's .invoke() at all (see chat/rag_service.py's Phase 4
docstring on why streaming bypasses the graph object), so there's no
single Runnable invocation for tracing_context() to wrap. Traced graph
execution currently covers non-streaming chat only.
"""
