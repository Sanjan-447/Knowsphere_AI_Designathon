# Sample documents for testing the ingestion pipeline

These are small, safe, synthetic files for exercising every parser in the pipeline.
**All of these have actually been uploaded through the real API and verified end-to-end**
(not just unit-tested) — see the note at the bottom on what that caught.

| File | Tests |
|---|---|
| `pto-policy.txt` | TXT parser, §-section splitting |
| `onboarding.md` | Markdown parser, heading-based sectioning |
| `team_roster.csv` | CSV parser, tabular row formatting |
| `benefits.json` | JSON parser, record flattening |
| `remote-work-policy.pdf` | PDF parser, page-level sectioning, PDF metadata extraction |
| `benefits-guide.docx` | DOCX parser, Word heading styles, tables, author metadata |
| `expense-deadline.eml` | Email parser, header/body sectioning, subject/sender/date extraction |
| `hr-data.xlsx` | XLSX parser, multi-sheet handling, sheet names in metadata |
| `slack-export-sample.json` | Chat export parser (upload via `/documents/chat-export`, not the general upload endpoint) |

Upload the first eight via the Document library page or `POST /api/v1/documents` (field name `files`).
Upload `slack-export-sample.json` via `POST /api/v1/documents/chat-export` (field name `file`) so it's
parsed as a chat export rather than a generic JSON document.

Share-link ingestion (`POST /api/v1/documents/share-link`) doesn't have a sample file here since it
takes a URL, not an upload — it's been verified against both a real bearer-token-protected local
server and a real public internet URL (a GitHub raw file); see the main README's verification notes.

To test .msg (Outlook binary format) parsing, use a real .msg file from your own machine — none is
included here since there's no straightforward way to generate one synthetically.

## What real-file testing caught that synthetic/unit testing didn't

`benefits-guide.docx` and `expense-deadline.eml` weren't just used to prove the parsers run — they
found a real bug: email citations were showing `"date": null` even though the email clearly had a
`Date:` header. The cause: `source_last_modified` is deliberately stored on `Document`'s fixed column
(not the flexible `document_metadata` table), but the citation engine was looking it up in the wrong
table. Fixed in `chat/citation_engine.py`. This is exactly the kind of bug that a parser unit test with
hand-built fixtures wouldn't catch, since the fixture would only exist in whichever table the test
author remembered to populate — a real uploaded file exercises the actual ingestion → citation path
end to end.

