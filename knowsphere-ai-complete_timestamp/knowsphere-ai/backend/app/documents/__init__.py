"""
Document Intelligence & Knowledge Ingestion module (Phase 2).

Implements: multi-format upload, parsing (PDF/DOCX/TXT/CSV/XLSX/JSON/MD/
EML/MSG), a generic share-link downloader connector, text cleaning,
semantic chunking, embedding generation, and pgvector storage — the full
ingestion pipeline up to and including "ready to be retrieved."

Deliberately NOT implemented here (reserved for Phase 3): semantic
retrieval/query-time search, the LangGraph agent workflow, and response
generation. This module produces embedded, stored chunks; it does not yet
answer questions with them.
"""
