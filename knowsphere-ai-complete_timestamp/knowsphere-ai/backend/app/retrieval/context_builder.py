"""
Context Builder.

Takes the retriever's ranked chunks and turns them into a token-budgeted,
deduplicated, numbered set of context blocks ready for the prompt builder.
Numbering here ([1], [2], ...) is the same numbering the LLM is instructed
to cite with, and what citation_engine.py maps back to source metadata —
this module is the single source of truth for that numbering.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.documents.chunking import count_tokens
from app.retrieval.vector_store import RetrievedChunk

DEFAULT_MAX_CONTEXT_TOKENS = 3000


@dataclass
class ContextBlock:
    index: int  # 1-based — matches the [n] citation marker used in the prompt
    chunk: RetrievedChunk
    token_count: int

    def label(self) -> str:
        section = self.chunk.chunk_metadata.get("section")
        base = f"{self.chunk.document_title}"
        return f"{base} — {section}" if section else base


@dataclass
class ContextBundle:
    blocks: list[ContextBlock]
    total_tokens: int
    truncated: bool  # True if one or more retrieved chunks were dropped for budget

    @property
    def is_empty(self) -> bool:
        return len(self.blocks) == 0

    def render(self) -> str:
        """Render as the numbered context text the prompt builder embeds."""
        parts = []
        for block in self.blocks:
            parts.append(f"[{block.index}] Source: {block.label()}\n{block.chunk.content}")
        return "\n\n".join(parts)


def build_context(
    chunks: list[RetrievedChunk], max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS
) -> ContextBundle:
    # Dedupe by chunk_id — defensive; a single retrieval call won't produce
    # duplicates today, but this keeps the builder safe if a future
    # multi-query retrieval path (e.g. hybrid search) feeds it overlapping results.
    seen_ids: set[int] = set()
    deduped: list[RetrievedChunk] = []
    for c in chunks:
        if c.chunk_id in seen_ids:
            continue
        seen_ids.add(c.chunk_id)
        deduped.append(c)

    blocks: list[ContextBlock] = []
    total_tokens = 0
    truncated = False

    for i, chunk in enumerate(deduped, start=1):
        token_count = count_tokens(chunk.content)
        if total_tokens + token_count > max_context_tokens and blocks:
            truncated = True
            break
        blocks.append(ContextBlock(index=i, chunk=chunk, token_count=token_count))
        total_tokens += token_count

    return ContextBundle(blocks=blocks, total_tokens=total_tokens, truncated=truncated)
