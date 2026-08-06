"""
Chat export parser.

Unlike the other parsers, this one isn't routed purely by file extension —
it's invoked explicitly via the "upload chat export" endpoint (see
documents/routes.py), since a .json or .txt file could just as easily be a
generic document. Within that, it sniffs the actual shape of the content to
support Slack-style and Microsoft Teams-style JSON exports, plus WhatsApp's
plain-text export format.
"""
import json
import re

from app.documents.parsers.base import BaseParser, ParsedDocument, ParsedSection, ParserError

_MESSAGES_PER_SECTION = 40

# WhatsApp export line format: "MM/DD/YY, HH:MM - Sender Name: message text"
_WHATSAPP_LINE_RE = re.compile(
    r"^(\d{1,2}/\d{1,2}/\d{2,4}),\s(\d{1,2}:\d{2}(?:\s?[APap][Mm])?)\s-\s([^:]+):\s(.*)$"
)


def _format_messages(messages: list[dict], text_key: str, user_key: str, ts_key: str) -> list[ParsedSection]:
    sections = []
    for start in range(0, len(messages), _MESSAGES_PER_SECTION):
        batch = messages[start:start + _MESSAGES_PER_SECTION]
        lines = []
        for m in batch:
            user = m.get(user_key, "unknown")
            text = m.get(text_key, "")
            ts = m.get(ts_key, "")
            if text:
                lines.append(f"[{ts}] {user}: {text}")
        if lines:
            label = f"messages {start + 1}-{min(start + _MESSAGES_PER_SECTION, len(messages))}"
            sections.append(ParsedSection(label=label, content="\n".join(lines)))
    return sections


class ChatExportParser(BaseParser):
    supported_extensions = ("json", "txt")

    def parse(self, file_path: str) -> ParsedDocument:
        if file_path.lower().endswith(".json"):
            return self._parse_json(file_path)
        return self._parse_whatsapp_txt(file_path)

    def _parse_json(self, file_path: str) -> ParsedDocument:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ParserError(f"'{file_path}' is not valid JSON: {exc}") from exc

        if isinstance(data, dict) and "messages" in data:
            data = data["messages"]
        if not isinstance(data, list):
            raise ParserError(f"Chat export '{file_path}' is not a list of messages.")

        metadata = {}
        sections: list[ParsedSection] = []

        if data and "text" in data[0] and "user" in data[0]:
            # Slack-style export
            sections = _format_messages(data, text_key="text", user_key="user", ts_key="ts")
            metadata["chat_platform"] = "slack"
        elif data and "body" in data[0]:
            # Microsoft Teams / Graph API-style export
            normalized = []
            for m in data:
                body = m.get("body", {})
                content = body.get("content") if isinstance(body, dict) else str(body)
                normalized.append({
                    "text": content,
                    "user": (m.get("from") or {}).get("user", {}).get("displayName", "unknown")
                    if isinstance(m.get("from"), dict) else str(m.get("from", "unknown")),
                    "ts": m.get("createdDateTime", ""),
                })
            sections = _format_messages(normalized, text_key="text", user_key="user", ts_key="ts")
            metadata["chat_platform"] = "teams"
        else:
            raise ParserError(
                f"Chat export '{file_path}' doesn't match a recognized Slack or Teams message schema."
            )

        doc = ParsedDocument(sections=sections, metadata=metadata)
        self.validate_not_empty(doc, file_path)
        return doc

    def _parse_whatsapp_txt(self, file_path: str) -> ParsedDocument:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="latin-1") as f:
                lines = f.readlines()

        messages = []
        current = None
        for line in lines:
            m = _WHATSAPP_LINE_RE.match(line.strip())
            if m:
                if current:
                    messages.append(current)
                date, time, sender, text = m.groups()
                current = {"ts": f"{date} {time}", "user": sender.strip(), "text": text}
            elif current:
                # continuation of a multi-line message
                current["text"] += "\n" + line.strip()
        if current:
            messages.append(current)

        if not messages:
            raise ParserError(
                f"'{file_path}' doesn't match the expected WhatsApp export format "
                "('MM/DD/YY, HH:MM - Sender: message')."
            )

        sections = _format_messages(messages, text_key="text", user_key="user", ts_key="ts")
        doc = ParsedDocument(sections=sections, metadata={"chat_platform": "whatsapp"})
        self.validate_not_empty(doc, file_path)
        return doc
