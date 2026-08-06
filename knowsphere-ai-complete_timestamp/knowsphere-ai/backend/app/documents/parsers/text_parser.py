import re

from app.documents.parsers.base import BaseParser, ParsedDocument, ParsedSection, ParserError

_ENCODINGS_TO_TRY = ("utf-8", "utf-8-sig", "latin-1")


def _read_text_file(file_path: str) -> str:
    last_exc = None
    for enc in _ENCODINGS_TO_TRY:
        try:
            with open(file_path, "r", encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, OSError) as exc:
            last_exc = exc
    raise ParserError(f"Could not read '{file_path}' as text with any known encoding: {last_exc}")


class TxtParser(BaseParser):
    supported_extensions = ("txt",)

    def parse(self, file_path: str) -> ParsedDocument:
        text = _read_text_file(file_path)
        # Reuse the "§section" convention already established in the prototype —
        # if present, split on it so chunk metadata can carry a section label.
        matches = list(re.finditer(r"§\s*([\w.]+)\s*[:\-–]?\s*", text))
        sections = []
        if matches:
            for i, m in enumerate(matches):
                start = m.end()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                sections.append(ParsedSection(label=f"§{m.group(1)}", content=text[start:end].strip()))
        else:
            sections = [ParsedSection(label=None, content=text.strip())]

        doc = ParsedDocument(sections=sections)
        self.validate_not_empty(doc, file_path)
        return doc


class MarkdownParser(BaseParser):
    supported_extensions = ("md", "markdown")

    def parse(self, file_path: str) -> ParsedDocument:
        text = _read_text_file(file_path)
        lines = text.splitlines()

        sections: list[ParsedSection] = []
        current_label = None
        current_lines: list[str] = []

        def flush():
            if current_lines:
                content = "\n".join(current_lines).strip()
                if content:
                    sections.append(ParsedSection(label=current_label, content=content))

        heading_re = re.compile(r"^(#{1,6})\s+(.*)")
        for line in lines:
            m = heading_re.match(line)
            if m:
                flush()
                current_label = m.group(2).strip()
                current_lines = []
            else:
                current_lines.append(line)
        flush()

        if not sections:
            sections = [ParsedSection(label=None, content=text.strip())]

        doc = ParsedDocument(sections=sections)
        self.validate_not_empty(doc, file_path)
        return doc
