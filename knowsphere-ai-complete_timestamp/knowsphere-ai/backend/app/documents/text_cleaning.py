"""
Text cleaning — runs on every ParsedSection's content after parsing and
before chunking. Strips the kind of repeated boilerplate and noise that, if
left in, pollutes embeddings with irrelevant repeated text (the same
reasoning as the "Clean" stage in the architecture blueprint's RAG workflow).
"""
import re

_MULTI_BLANK_LINES = re.compile(r"\n{3,}")
_MULTI_SPACES = re.compile(r"[ \t]{2,}")
_PAGE_NUMBER_LINE = re.compile(r"^\s*(page\s+)?\d{1,4}\s*(of\s*\d{1,4})?\s*$", re.IGNORECASE)
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def clean_text(text: str) -> str:
    if not text:
        return ""

    text = _CONTROL_CHARS.sub("", text)

    lines = text.splitlines()
    cleaned_lines = [line for line in lines if not _PAGE_NUMBER_LINE.match(line)]
    text = "\n".join(cleaned_lines)

    text = _MULTI_SPACES.sub(" ", text)
    text = _MULTI_BLANK_LINES.sub("\n\n", text)

    return text.strip()
