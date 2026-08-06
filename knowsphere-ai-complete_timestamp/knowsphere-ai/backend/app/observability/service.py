"""
Observability service.

Two things live here:
1. get_active_config() / test_connection() — plain config access and a
   real (if network-permitting) connectivity check against LangSmith's API.
2. traced_invoke() — wraps a LangGraph invocation in LangSmith's
   tracing_context() when configured and enabled, or calls it directly
   (a true no-op, not a stub) when not. This is the one integration point
   RagService.answer() calls through; nothing about the graph itself
   changes whether tracing is on or off.

Honest limitation, stated once here rather than scattered as inline
comments: this sandbox's network egress allowlist does not include
smith.langchain.com or api.smith.langchain.com, so while this integration
is written against LangSmith's real, documented SDK (tracing_context(),
Client(), has_project()), it has not been verified to actually produce
visible traces in a live LangSmith project from this environment. That
verification happens on your end once a real API key is configured.
"""
from __future__ import annotations

import logging

from app.observability.models import ObservabilityConfig

logger = logging.getLogger("knowsphere.observability")


def get_active_config() -> ObservabilityConfig | None:
    """Returns the singleton config row if one exists and tracing is
    enabled with a key present; otherwise None, meaning "tracing is off."""
    config = ObservabilityConfig.query.first()
    if config and config.tracing_enabled and config.encrypted_api_key:
        return config
    return None


def get_or_create_config() -> ObservabilityConfig:
    config = ObservabilityConfig.query.first()
    if not config:
        from app.extensions import db
        config = ObservabilityConfig(project_name="knowsphere-ai", tracing_enabled=False)
        db.session.add(config)
        db.session.commit()
    return config


def test_connection(config: ObservabilityConfig) -> tuple[bool, str]:
    """A real (not simulated) connectivity check: asks LangSmith whether
    the configured project exists, using the configured key. Returns
    (passed, message)."""
    api_key = config.get_api_key()
    if not api_key:
        return False, "No API key configured."

    try:
        from langsmith import Client
        client = Client(api_key=api_key, api_url=config.endpoint or None)
        exists = client.has_project(config.project_name)
        if exists:
            return True, f"Connected — project '{config.project_name}' found."
        return True, f"Connected, but project '{config.project_name}' doesn't exist yet — it will be created on first trace."
    except Exception as exc:  # noqa: BLE001 — this call can fail for many reasons (bad key, network, wrong URL); surface all of them the same way
        return False, f"Connection failed: {exc}"


def traced_invoke(graph, initial_state: dict) -> dict:
    """Runs a compiled LangGraph graph's .invoke(), wrapped in LangSmith
    tracing when configured+enabled, otherwise a direct passthrough call.
    LangGraph's nodes are internally wrapped as LangChain Runnables, so
    they pick up the active tracing context automatically — no per-node
    instrumentation needed here, which is the whole reason
    langsmith.run_helpers.tracing_context() was chosen over manually
    wrapping each node function.

    Important control-flow note: graph.invoke() is called exactly once, no
    matter what. Setting up the tracing context is wrapped in its own
    try/except (a bad key or unreachable network legitimately shouldn't
    block a chat request) — but invoke() itself is called outside that
    except, so if it raises for a real, unrelated reason, that exception
    propagates normally instead of triggering a second, duplicate
    invocation. An earlier version of this function had invoke() inside
    the same try block as tracing setup, which would have silently run
    the whole graph twice — including its DB writes — on any invoke()
    failure. Caught before it shipped, not after."""
    config = get_active_config()
    if config is None:
        return graph.invoke(initial_state)

    tracing_ctx = None
    try:
        from langsmith import Client
        from langsmith.run_helpers import tracing_context

        client = Client(api_key=config.get_api_key(), api_url=config.endpoint or None)
        tracing_ctx = tracing_context(enabled=True, client=client, project_name=config.project_name)
        tracing_ctx.__enter__()
    except Exception as exc:  # noqa: BLE001 — tracing setup must never block a chat request
        logger.warning("LangSmith tracing setup failed for this request, continuing untraced: %s", exc)
        tracing_ctx = None

    try:
        return graph.invoke(initial_state)
    finally:
        if tracing_ctx is not None:
            try:
                tracing_ctx.__exit__(None, None, None)
            except Exception:  # noqa: BLE001 — tearing down tracing must never mask the real result/exception above
                logger.warning("LangSmith tracing context teardown failed (trace may be incomplete)")


class StreamTraceHandle:
    """Coarser tracing for the streaming chat path — a single parent span
    covering the whole request, rather than the non-streaming path's
    automatic per-node child spans.

    Why streaming can't reuse traced_invoke() as-is: tracing_context()'s
    automatic instrumentation only fires for LangChain Runnables (which is
    what graph.invoke() calls under the hood). The streaming path never
    calls graph.invoke() at all — per Phase 4's design, it calls the same
    node *functions* directly as plain Python calls (see
    chat/rag_service.py's module docstring) so it can yield tokens
    incrementally. A plain function call isn't a Runnable, so there's
    nothing for tracing_context() to automatically wrap.

    Rather than leave streaming completely untraced, or take on the
    larger, riskier change of decorating every shared node function with
    @traceable (which would add LangSmith-specific code into modules that
    are otherwise fully tracing-agnostic — retrieval, prompt building,
    citation extraction — coupling them to an observability concern they
    shouldn't need to know about), this creates ONE manual LangSmith run
    wrapping the entire streaming request as a single span. You get a
    trace with the question, the full response, retrieval stats, and
    total latency — not the node-by-node breakdown the non-streaming path
    gets. That asymmetry is a real, stated limitation, not a hidden one.

    Field name note: RunTree's actual schema (verified against the
    installed langsmith version, not assumed) uses `session_name` for what
    the LangSmith UI calls a "project", and `ls_client` for the client
    instance — `project_name`/`client` are NOT valid fields on this class,
    despite being the argument names on tracing_context() and Client().
    Different classes in the same SDK using different names for the same
    concept is exactly the kind of thing worth checking against the
    installed version rather than assuming from convention.
    """

    def __init__(self, question: str):
        self.config = get_active_config()
        self.run_tree = None
        self.question = question

    def __enter__(self):
        if self.config is None:
            return self
        try:
            from langsmith.run_trees import RunTree
            self.run_tree = RunTree(
                name="chat_stream_request", run_type="chain",
                session_name=self.config.project_name,
                ls_client=self._client(),
                inputs={"question": self.question},
            )
            self.run_tree.post()
        except Exception as exc:  # noqa: BLE001
            logger.warning("LangSmith streaming trace setup failed, continuing untraced: %s", exc)
            self.run_tree = None
        return self

    def _client(self):
        from langsmith import Client
        return Client(api_key=self.config.get_api_key(), api_url=self.config.endpoint or None)

    def record(self, *, outputs: dict, error: str | None = None):
        if self.run_tree is None:
            return
        try:
            self.run_tree.end(outputs=outputs, error=error)
            self.run_tree.patch()
        except Exception:  # noqa: BLE001 — never let trace submission break the actual response
            logger.warning("LangSmith streaming trace submission failed (trace may be missing)")

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False  # never suppress real exceptions from the caller's block
