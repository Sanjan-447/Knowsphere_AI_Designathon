# Administrator Guide

## User Management

**Settings → User Management** (admin only).

- **Create a user**: click "Add user," set their role (Admin/Manager/
  Employee). There's no self-service signup by design — provisioning is
  an admin action.
- **Change a role**: use the role dropdown next to any user in the table.
  Takes effect immediately on their next request.
- **Disable a user**: "Disable" button — their existing sessions keep
  working until they expire or you also reset their sessions (below);
  they simply can't log in again.
- **Force a logout everywhere**: "Reset sessions" — revokes every active
  refresh token for that user immediately. Use this after a role change
  you want to take effect right away, or if you suspect a compromised
  account.

## Provider Configuration

**Settings → Provider settings** (admin only).

Each provider needs: a type (OpenAI/Anthropic/Gemini/Groq/OpenRouter/
NVIDIA NIM/Ollama/OpenAI-compatible), an API key (unless self-hosted
Ollama), and a **capability** — `llm`, `embedding`, or `both`.

**Important**: only OpenAI, Gemini, and OpenAI-compatible endpoints can do
embeddings in this system. Groq, OpenRouter, Anthropic, NVIDIA NIM, and
Ollama are chat-only — the system enforces this and will reject trying to
set `embedding`/`both` capability on those types.

**Practical recommendation**: if you're running on free-tier keys, Groq
or OpenRouter work well for chat generation, but you'll need a *separate*
provider (Gemini's free tier, or a self-hosted Ollama embedding model) for
embeddings — see the README's provider configuration section for the full
breakdown of what's free where.

Click **"Set default"** on a provider to make it the org-wide default —
this takes effect on the very next chat message, no restart needed.

## Document Upload & Management

**Documents** page (Admin/Manager).

- Drag-and-drop or click to browse. Supports PDF, DOCX, TXT, Markdown,
  CSV, XLSX, JSON, EML. Chat exports (Slack/Teams/WhatsApp) and share-link
  URLs use their own dedicated upload paths — see the Documents page's
  distinct upload options.
- Watch the status badge progress: `uploaded → parsing → chunking →
  embedding → indexing → ready` (or `failed`, with a reason). Uploads are
  processed asynchronously by a Celery worker — if a document sits at
  `uploaded` forever, the worker probably isn't running.
- Set document visibility via role-access controls at upload or edit time
  — a document with no roles assigned is visible to everyone; assigning
  specific roles restricts it (this is how confidential documents, like
  compensation data, stay invisible to unauthorized roles even in the
  chat assistant's answers).
- **Reprocess** re-runs the full pipeline without a new file upload —
  useful after fixing an embedding provider issue.

## Dashboard Usage

- **Enterprise Dashboard** (home page): org-wide KPIs — users, documents,
  queries, response times, cache hit rate, token/cost totals.
- **Analytics**: usage trends over time, most-asked topics (keyword
  frequency, not semantic clustering), frequently-cited documents,
  department usage, feedback effectiveness. Filterable by date/department/
  provider.
- **Knowledge Intelligence**: gap analysis — unanswered questions, missing
  knowledge areas, low-confidence responses, documents never retrieved,
  stale documents, duplicate detection (expected to show empty — duplicates
  are prevented at upload time).
- **System Monitoring**: live (not simulated) health of Postgres, pgvector,
  Redis, Celery workers, disk, CPU/memory.
- **Provider Monitoring**: per-provider success rate, response time, token
  usage, estimated cost, last-used timestamp.
- **Retrieval Dashboard / Inspector**: click "Open full inspector" on any
  recent query to see the exact retrieved chunks, similarity scores, the
  full rendered context, and — admin-only — the raw prompt sent to the LLM.
- **Audit Log**: every login, upload, delete, provider change, role
  change, and chat query, searchable and exportable. Immutable — no
  edit/delete endpoint exists for this data.
- **Notifications**: failed uploads/embeddings/retrievals, provider
  failures, system errors. "Scan for expired documents" is a manual
  trigger, not an automatic background job (no scheduler is configured).

## Reports

Every analytics view and the audit log has **Export CSV/Excel/PDF**
buttons. Reports available: Overview, Usage, Feedback, Knowledge Gaps,
Audit Log.

## LangSmith Observability

**Settings → LangSmith observability** (admin only). Paste your API key,
set a project name, toggle tracing on, then click **"Test connection"**
to verify it actually works before relying on it — this makes a real API
call to LangSmith, not a simulated check.

**Coverage note**: non-streaming chat gets full per-node tracing;
streaming chat gets one summary trace per request, not a node-by-node
breakdown — a deliberate trade-off explained in the README's Phase 5
LangSmith section.
