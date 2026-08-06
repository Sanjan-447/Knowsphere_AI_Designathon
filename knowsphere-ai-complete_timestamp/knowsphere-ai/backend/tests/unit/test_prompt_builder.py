"""Unit tests for chat/prompt_builder.py — no DB, no network, pure function tests."""
from app.chat.prompt_builder import build_prompt, INSUFFICIENT_CONTEXT_RESPONSE
from app.retrieval.context_builder import ContextBundle, ContextBlock
from app.retrieval.vector_store import RetrievedChunk


def _make_chunk(chunk_id=1, content="Employees accrue 21 PTO days per year."):
    return RetrievedChunk(
        chunk_id=chunk_id, document_id=1, chunk_index=0, content=content,
        chunk_metadata={"section": "§1"}, similarity_score=0.8,
        document_title="PTO Policy", document_file_type="txt",
        document_source_type="upload", document_department="HR",
    )


def test_build_prompt_includes_system_and_user_messages():
    context = ContextBundle(blocks=[ContextBlock(index=1, chunk=_make_chunk(), token_count=10)], total_tokens=10, truncated=False)
    messages = build_prompt(question="How many PTO days?", context=context, conversation_history=[], role_name="employee")

    assert messages[0].role == "system"
    assert messages[-1].role == "user"
    assert messages[-1].content == "How many PTO days?"


def test_build_prompt_system_message_grounds_in_context_only():
    context = ContextBundle(blocks=[ContextBlock(index=1, chunk=_make_chunk(), token_count=10)], total_tokens=10, truncated=False)
    messages = build_prompt(question="q", context=context, conversation_history=[], role_name="admin")
    system = messages[0].content

    assert "ONLY" in system
    assert "[1]" in system  # the citation format instruction references bracket numbers
    assert INSUFFICIENT_CONTEXT_RESPONSE in system


def test_build_prompt_empty_context_says_no_documents_found():
    context = ContextBundle(blocks=[], total_tokens=0, truncated=False)
    messages = build_prompt(question="q", context=context, conversation_history=[], role_name="employee")
    assert "No relevant enterprise documents" in messages[0].content


def test_build_prompt_includes_role_name():
    context = ContextBundle(blocks=[], total_tokens=0, truncated=False)
    messages = build_prompt(question="q", context=context, conversation_history=[], role_name="manager")
    assert "manager" in messages[0].content


def test_build_prompt_windows_long_history():
    """MAX_HISTORY_MESSAGES caps how much prior conversation gets included —
    verify it actually truncates rather than including everything."""
    from app.chat.prompt_builder import MAX_HISTORY_MESSAGES

    class FakeMsg:
        def __init__(self, i):
            self.role = "user" if i % 2 == 0 else "assistant"
            self.content = f"message {i}"

    history = [FakeMsg(i) for i in range(MAX_HISTORY_MESSAGES + 10)]
    context = ContextBundle(blocks=[], total_tokens=0, truncated=False)
    messages = build_prompt(question="latest question", context=context, conversation_history=history, role_name="employee")

    # system + windowed history + the new question
    assert len(messages) == 1 + MAX_HISTORY_MESSAGES + 1
