from pypdf import PdfReader
from pypdf.errors import PdfReadError

from app.documents.parsers.base import BaseParser, ParsedDocument, ParsedSection, ParserError


class PdfParser(BaseParser):
    supported_extensions = ("pdf",)

    def parse(self, file_path: str) -> ParsedDocument:
        try:
            reader = PdfReader(file_path)
        except (PdfReadError, FileNotFoundError, OSError) as exc:
            raise ParserError(f"Could not open PDF '{file_path}': {exc}") from exc

        if reader.is_encrypted:
            try:
                reader.decrypt("")  # try an empty password before giving up
            except Exception as exc:
                raise ParserError(f"PDF '{file_path}' is password-protected and could not be opened.") from exc

        sections: list[ParsedSection] = []
        for page_num, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            sections.append(ParsedSection(label=f"page {page_num}", content=text))

        metadata = {}
        info = reader.metadata
        if info:
            if info.author:
                metadata["author"] = info.author
            if info.title:
                metadata["pdf_title"] = info.title
            if info.creation_date:
                metadata["created_at_source"] = str(info.creation_date)

        doc = ParsedDocument(sections=sections, metadata=metadata)
        self.validate_not_empty(doc, file_path)
        return doc
