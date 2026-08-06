"""
Parser interface.

Every format-specific parser implements BaseParser.parse(file_path) and
returns a ParsedDocument — a normalized shape the rest of the pipeline
(cleaning, chunking, metadata extraction) works with regardless of source
format. This is the "reusable parser interface" / "extensible parser
framework" the spec asks for: adding a new format later means writing one
class and registering it in registry.py, nothing else changes.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ParsedSection:
    """One logical unit of a document — a heading + its text, if the format
    has structure (headings, sheet names, email fields); label is None for
    formats with no natural structure (plain TXT), and the whole document
    becomes a single unlabeled section."""

    label: str | None
    content: str


@dataclass
class ParsedDocument:
    """Normalized output of any parser."""

    sections: list[ParsedSection]
    metadata: dict = field(default_factory=dict)  # author, subject, from, channel, source_url, etc.

    @property
    def full_text(self) -> str:
        return "\n\n".join(s.content for s in self.sections if s.content.strip())


class ParserError(Exception):
    """Raised for corrupted, empty, or otherwise unparseable files."""


class BaseParser(ABC):
    #: file extensions this parser handles, without the dot, lowercase
    supported_extensions: tuple[str, ...] = ()

    @abstractmethod
    def parse(self, file_path: str) -> ParsedDocument:
        ...

    def validate_not_empty(self, doc: ParsedDocument, file_path: str) -> None:
        if not doc.full_text.strip():
            raise ParserError(f"'{file_path}' parsed successfully but contains no extractable text.")
