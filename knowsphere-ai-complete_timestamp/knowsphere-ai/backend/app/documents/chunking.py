"""
Semantic chunking.

Chunks by paragraph within each parsed section, rather than a naive
fixed-character sliding window over the raw text — this is what "preserve
semantic boundaries" means in practice: a chunk boundary falls between
paragraphs (or sentences, for one oversized paragraph), never mid-sentence,
and never crosses a section boundary (a PDF page, a DOCX heading, an email
header vs. body) uninvited. Overlap is carried forward as whole trailing
paragraphs/sentences, not an arbitrary token slice, so a chunk always reads
as coherent text on its own.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.documents.parsers.base import ParsedDocument
from app.documents.text_cleaning import clean_text

DEFAULT_MAX_TOKENS = 700     # within the spec's 500-800 token range
DEFAULT_OVERLAP_TOKENS = 100

logger = logging.getLogger("knowsphere.chunking")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_encoding = None
_tiktoken_unavailable = False


def _get_encoding():
    """Lazily load tiktoken's BPE table on first use, not at import time —
    it fetches a file from a Microsoft-hosted blob on first use in a fresh
    environment, which some firewalled/offline networks can't reach. If
    that happens, we fall back to a whitespace-based token estimate rather
    than fail the whole pipeline over a token-counting nicety."""
    global _encoding, _tiktoken_unavailable
    if _encoding is not None or _tiktoken_unavailable:
        return _encoding
    try:
        import tiktoken
        _encoding = tiktoken.get_encoding("cl100k_base")
    except Exception as exc:
        logger.warning(
            "tiktoken's BPE table could not be loaded (%s) — falling back to an "
            "approximate word-based token estimate. Chunk sizes will be "
            "approximately, not exactly, on-target.", exc,
        )
        _tiktoken_unavailable = True
    return _encoding


def count_tokens(text: str) -> int:
    if not text:
        return 0
    encoding = _get_encoding()
    if encoding is not None:
        return len(encoding.encode(text))
    # Fallback estimate: ~4 characters per token is a widely-used approximation
    # for English text with cl100k-style tokenizers.
    return max(1, len(text) // 4)


@dataclass
class ChunkDraft:
    content: str
    token_count: int
    section_label: str | None


def _split_oversized_paragraph(paragraph: str, max_tokens: int) -> list[str]:
    """A single paragraph longer than max_tokens gets split on sentence
    boundaries instead of being force-truncated or crossing as one giant chunk."""
    sentences = _SENTENCE_SPLIT_RE.split(paragraph)
    pieces, current, current_tokens = [], [], 0
    for sentence in sentences:
        s_tokens = count_tokens(sentence)
        if current and current_tokens + s_tokens > max_tokens:
            pieces.append(" ".join(current))
            current, current_tokens = [], 0
        current.append(sentence)
        current_tokens += s_tokens
    if current:
        pieces.append(" ".join(current))
    return pieces


def _take_overlap_paragraphs(paragraphs: list[str], overlap_tokens: int) -> list[str]:
    """Return the trailing paragraphs (in order) whose combined token count
    is closest to (without exceeding) overlap_tokens, to seed the next chunk."""
    if overlap_tokens <= 0:
        return []
    taken, total = [], 0
    for para in reversed(paragraphs):
        t = count_tokens(para)
        if total + t > overlap_tokens and taken:
            break
        taken.insert(0, para)
        total += t
    return taken


def _chunk_section_text(
    text: str, max_tokens: int, overlap_tokens: int
) -> list[str]:
    raw_paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    # Break any single oversized paragraph into sentence-level pieces first.
    paragraphs: list[str] = []
    for p in raw_paragraphs:
        if count_tokens(p) > max_tokens:
            paragraphs.extend(_split_oversized_paragraph(p, max_tokens))
        else:
            paragraphs.append(p)

    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para_tokens = count_tokens(para)
        if current and current_tokens + para_tokens > max_tokens:
            chunks.append("\n\n".join(current))
            overlap = _take_overlap_paragraphs(current, overlap_tokens)
            current = list(overlap)
            current_tokens = sum(count_tokens(p) for p in current)
        current.append(para)
        current_tokens += para_tokens

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def chunk_document(
    doc: ParsedDocument,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[ChunkDraft]:
    """Chunk every section of a parsed document, never merging content across
    section boundaries — each resulting chunk carries its source section's
    label as metadata (page number, heading, sheet name, etc.)."""
    drafts: list[ChunkDraft] = []

    for section in doc.sections:
        cleaned = clean_text(section.content)
        if not cleaned:
            continue
        for chunk_text in _chunk_section_text(cleaned, max_tokens, overlap_tokens):
            if not chunk_text.strip():
                continue
            drafts.append(
                ChunkDraft(
                    content=chunk_text,
                    token_count=count_tokens(chunk_text),
                    section_label=section.label,
                )
            )

    return drafts
