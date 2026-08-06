"""
Parser registry — the single place that maps a file type to its parser.
Adding a new format later means writing one BaseParser subclass and adding
one line here.
"""
from app.documents.parsers.base import BaseParser, ParserError  # noqa: F401 (re-exported for convenience)
from app.documents.parsers.pdf_parser import PdfParser
from app.documents.parsers.docx_parser import DocxParser
from app.documents.parsers.text_parser import TxtParser, MarkdownParser
from app.documents.parsers.spreadsheet_parser import CsvParser, XlsxParser
from app.documents.parsers.json_parser import JsonParser
from app.documents.parsers.email_parser import EmailParser, MsgParser

# Ordinary document upload — routed purely by file extension.
_PARSERS_BY_EXTENSION: dict[str, BaseParser] = {}


def _register(parser: BaseParser):
    for ext in parser.supported_extensions:
        _PARSERS_BY_EXTENSION[ext] = parser


_register(PdfParser())
_register(DocxParser())
_register(TxtParser())
_register(MarkdownParser())
_register(CsvParser())
_register(XlsxParser())
_register(JsonParser())
_register(EmailParser())
_register(MsgParser())

SUPPORTED_EXTENSIONS = tuple(sorted(_PARSERS_BY_EXTENSION.keys()))


def get_parser_for_extension(extension: str) -> BaseParser | None:
    return _PARSERS_BY_EXTENSION.get(extension.lower().lstrip("."))


def is_supported_extension(extension: str) -> bool:
    return extension.lower().lstrip(".") in _PARSERS_BY_EXTENSION


def get_chat_export_parser() -> BaseParser:
    # Imported lazily to avoid circularity concerns if this module ever grows.
    from app.documents.parsers.chat_export_parser import ChatExportParser
    return ChatExportParser()
