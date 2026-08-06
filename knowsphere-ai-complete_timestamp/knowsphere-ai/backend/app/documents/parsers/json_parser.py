import json

from app.documents.parsers.base import BaseParser, ParsedDocument, ParsedSection, ParserError


def _flatten(obj, prefix: str = "") -> list[tuple[str, str]]:
    """Flatten arbitrary JSON into (path, value) pairs, e.g. ("user.name", "Alice")."""
    pairs = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            path = f"{prefix}.{k}" if prefix else str(k)
            pairs.extend(_flatten(v, path))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            pairs.extend(_flatten(item, f"{prefix}[{i}]"))
    else:
        pairs.append((prefix, str(obj)))
    return pairs


class JsonParser(BaseParser):
    supported_extensions = ("json",)

    #: top-level array entries are grouped into sections of this size, so a
    #: 10,000-record export doesn't become a single unchunkable section.
    entries_per_section = 25

    def parse(self, file_path: str) -> ParsedDocument:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ParserError(f"'{file_path}' is not valid JSON: {exc}") from exc
        except OSError as exc:
            raise ParserError(f"Could not read '{file_path}': {exc}") from exc

        sections: list[ParsedSection] = []

        if isinstance(data, list):
            for start in range(0, len(data), self.entries_per_section):
                batch = data[start:start + self.entries_per_section]
                lines = []
                for i, item in enumerate(batch, start=start):
                    pairs = _flatten(item, f"[{i}]")
                    lines.append("\n".join(f"{p}: {v}" for p, v in pairs))
                label = f"records {start + 1}-{min(start + self.entries_per_section, len(data))}"
                sections.append(ParsedSection(label=label, content="\n\n".join(lines)))
        else:
            pairs = _flatten(data)
            content = "\n".join(f"{p}: {v}" for p, v in pairs)
            sections.append(ParsedSection(label=None, content=content))

        doc = ParsedDocument(sections=sections)
        self.validate_not_empty(doc, file_path)
        return doc
