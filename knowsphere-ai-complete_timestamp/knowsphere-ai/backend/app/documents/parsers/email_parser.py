import email
import email.policy
from email.utils import parsedate_to_datetime

from app.documents.parsers.base import BaseParser, ParsedDocument, ParsedSection, ParserError


def _extract_eml_body(msg) -> str:
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                try:
                    parts.append(part.get_content())
                except Exception:
                    pass
        if parts:
            return "\n\n".join(parts)
        # Fall back to HTML part if no plain-text part exists (still usable text, just unstripped)
        for part in msg.walk():
            if part.get_content_type() == "text/html" and not part.get_filename():
                try:
                    return part.get_content()
                except Exception:
                    pass
        return ""
    try:
        return msg.get_content()
    except Exception:
        return ""


class EmailParser(BaseParser):
    """Handles .eml (standard MIME) directly. .msg (Outlook binary format)
    is handled by MsgParser below, since it needs a different library."""

    supported_extensions = ("eml",)

    def parse(self, file_path: str) -> ParsedDocument:
        try:
            with open(file_path, "rb") as f:
                msg = email.message_from_binary_file(f, policy=email.policy.default)
        except Exception as exc:
            raise ParserError(f"Could not parse EML file '{file_path}': {exc}") from exc

        body = _extract_eml_body(msg)
        header_lines = [
            f"From: {msg.get('From', '')}",
            f"To: {msg.get('To', '')}",
            f"Subject: {msg.get('Subject', '')}",
            f"Date: {msg.get('Date', '')}",
        ]
        sections = [
            ParsedSection(label="headers", content="\n".join(header_lines)),
            ParsedSection(label="body", content=body.strip()),
        ]

        metadata = {
            "email_from": msg.get("From", ""),
            "email_to": msg.get("To", ""),
            "email_subject": msg.get("Subject", ""),
        }
        date_header = msg.get("Date")
        if date_header:
            try:
                metadata["source_last_modified"] = parsedate_to_datetime(date_header).isoformat()
            except Exception:
                pass

        doc = ParsedDocument(sections=sections, metadata=metadata)
        self.validate_not_empty(doc, file_path)
        return doc


class MsgParser(BaseParser):
    """Outlook's binary .msg format, via the extract-msg library."""

    supported_extensions = ("msg",)

    def parse(self, file_path: str) -> ParsedDocument:
        try:
            import extract_msg
        except ImportError as exc:
            raise ParserError("The 'extract-msg' package is required to parse .msg files.") from exc

        try:
            msg = extract_msg.Message(file_path)
        except Exception as exc:
            raise ParserError(f"Could not parse MSG file '{file_path}': {exc}") from exc

        header_lines = [
            f"From: {msg.sender or ''}",
            f"To: {msg.to or ''}",
            f"Subject: {msg.subject or ''}",
            f"Date: {msg.date or ''}",
        ]
        body = (msg.body or "").strip()

        sections = [
            ParsedSection(label="headers", content="\n".join(header_lines)),
            ParsedSection(label="body", content=body),
        ]

        metadata = {
            "email_from": msg.sender or "",
            "email_to": msg.to or "",
            "email_subject": msg.subject or "",
        }
        if msg.date:
            metadata["source_last_modified"] = str(msg.date)

        try:
            msg.close()
        except Exception:
            pass

        doc = ParsedDocument(sections=sections, metadata=metadata)
        self.validate_not_empty(doc, file_path)
        return doc
