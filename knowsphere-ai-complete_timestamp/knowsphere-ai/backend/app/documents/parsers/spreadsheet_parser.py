import pandas as pd

from app.documents.parsers.base import BaseParser, ParsedDocument, ParsedSection, ParserError

_MAX_ROWS_PER_SECTION = 200  # keep sections at a manageable chunking size for large sheets


def _df_to_sections(df: pd.DataFrame, sheet_label: str | None) -> list[ParsedSection]:
    if df.empty:
        return []
    columns = [str(c) for c in df.columns]
    sections = []
    for start in range(0, len(df), _MAX_ROWS_PER_SECTION):
        chunk_df = df.iloc[start:start + _MAX_ROWS_PER_SECTION]
        lines = [" | ".join(columns)]
        for _, row in chunk_df.iterrows():
            lines.append(" | ".join(str(v) for v in row.tolist()))
        label = sheet_label
        if len(df) > _MAX_ROWS_PER_SECTION:
            label = f"{sheet_label or 'rows'} {start + 1}-{min(start + _MAX_ROWS_PER_SECTION, len(df))}"
        sections.append(ParsedSection(label=label, content="\n".join(lines)))
    return sections


class CsvParser(BaseParser):
    supported_extensions = ("csv",)

    def parse(self, file_path: str) -> ParsedDocument:
        try:
            df = pd.read_csv(file_path)
        except pd.errors.EmptyDataError:
            raise ParserError(f"CSV '{file_path}' is empty.")
        except Exception as exc:
            raise ParserError(f"Could not parse CSV '{file_path}': {exc}") from exc

        sections = _df_to_sections(df, None)
        doc = ParsedDocument(sections=sections, metadata={"row_count": len(df), "columns": list(df.columns.astype(str))})
        self.validate_not_empty(doc, file_path)
        return doc


class XlsxParser(BaseParser):
    supported_extensions = ("xlsx", "xls")

    def parse(self, file_path: str) -> ParsedDocument:
        try:
            sheets = pd.read_excel(file_path, sheet_name=None)
        except Exception as exc:
            raise ParserError(f"Could not parse Excel file '{file_path}': {exc}") from exc

        sections: list[ParsedSection] = []
        for sheet_name, df in sheets.items():
            sections.extend(_df_to_sections(df, sheet_label=f"sheet: {sheet_name}"))

        doc = ParsedDocument(sections=sections, metadata={"sheet_names": list(sheets.keys())})
        self.validate_not_empty(doc, file_path)
        return doc
