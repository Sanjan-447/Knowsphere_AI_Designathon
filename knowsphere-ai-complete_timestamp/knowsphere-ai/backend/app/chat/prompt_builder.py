"""
Prompt Builder.

Constructs the actual message list sent to the LLM: a system prompt that
strictly grounds the model in retrieved context (including the exact
fallback phrase the spec requires when context is insufficient), plus
windowed conversation history, plus the new question.
"""
from __future__ import annotations

from app.providers.llm.base import ChatMessage
from app.retrieval.context_builder import ContextBundle
from app.chat.models import ChatMessage as ChatMessageModel

INSUFFICIENT_CONTEXT_RESPONSE = "The requested information is not available in the enterprise knowledge base."

#: how many prior turns (user+assistant pairs, so this is messages, not
#: pairs) to include verbatim — simple windowing per the spec's
#: "Context Window Management" ask. A future phase can replace this with
#: rolling summarization (see the original architecture blueprint's
#: "Conversation memory" section) without changing this function's signature.
MAX_HISTORY_MESSAGES = 12


def _build_system_prompt(context: ContextBundle, role_name: str) -> str:
    if context.is_empty:
        context_section = "(No relevant enterprise documents were found for this question.)"
    else:
        context_section = context.render()

    return f"""You are Knowsphere AI, an internal enterprise knowledge assistant. \
You are speaking with a user whose role is: {role_name}.

Answer ONLY using the numbered context sources below — these are the only documents this user is \
permitted to access for this query. Do not use outside knowledge, and do not guess.

Rules:
- Every factual claim must be followed by a citation marker in the exact format [n], matching the \
source number it came from, e.g. "Employees accrue 21 PTO days per year [1]."
- If the sources below do not contain enough information to answer the question, respond with \
EXACTLY this sentence and nothing else: "{INSUFFICIENT_CONTEXT_RESPONSE}"
- Never fabricate a citation number that isn't listed below.
- Keep answers concise and clear — a few sentences unless the question genuinely requires more detail.

CONTEXT SOURCES:

{context_section}"""


def build_prompt(
    *,
    question: str,
    context: ContextBundle,
    conversation_history: list[ChatMessageModel],
    role_name: str,
) -> list[ChatMessage]:
    messages: list[ChatMessage] = [ChatMessage(role="system", content=_build_system_prompt(context, role_name))]

    windowed_history = conversation_history[-MAX_HISTORY_MESSAGES:]
    for msg in windowed_history:
        llm_role = "assistant" if msg.role == "assistant" else "user"
        messages.append(ChatMessage(role=llm_role, content=msg.content))

    messages.append(ChatMessage(role="user", content=question))
    return messages
