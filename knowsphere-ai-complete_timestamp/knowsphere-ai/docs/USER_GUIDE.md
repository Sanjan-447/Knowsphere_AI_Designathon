# User Guide

For everyday employees using KnowSphere AI — not administrators. See the
[Administrator Guide](./ADMIN_GUIDE.md) for provider setup, user
management, and dashboards.

## Logging In

Go to the app's login page and sign in with the email and password your
administrator gave you. There's no self-service sign-up — accounts are
created by an admin.

## Asking Questions (Ask Knowsphere)

Click **Ask Knowsphere** in the sidebar. Type a question about company
policies, benefits, onboarding, or anything else covered in the
organization's uploaded documents, and press Enter or click **Ask**.

- Answers stream in live, word by word.
- If the assistant genuinely doesn't have information to answer your
  question, it will tell you plainly rather than guess — you'll see:
  *"The requested information is not available in the enterprise
  knowledge base."*
- You can ask follow-up questions in the same conversation — the
  assistant remembers what you've already discussed in that chat.
- Use **+ New chat** to start a fresh conversation, and rename or delete
  past conversations from the sidebar.

## Citations

Every factual answer includes numbered citation cards below it — click
one to open a panel showing exactly which document, section, email, or
chat message the answer came from, plus a short excerpt so you can verify
it yourself rather than just trusting the assistant.

## Giving Feedback

Every assistant response has 👍 / 👎 buttons underneath it. Use them
honestly — this data genuinely gets reviewed by administrators to find
gaps in the knowledge base and improve retrieval quality over time. If
you have more to say, admins can also see comments if the interface you're
using supports adding one.

## Uploading Documents

If your role allows document management (Admin or Manager), you'll see a
**Documents** page with a drag-and-drop upload area. If you're an
Employee, you can still browse and search the document library — you just
can't add, delete, or reprocess documents. This isn't a bug; it's
intentional access control.

## Searching Documents

On the **Documents** page, use the search box to filter by title, or the
file-type/source-type dropdowns to narrow the list. Click any document to
see its metadata and a content preview.

## What You Won't See (and Why)

- Documents your role isn't permitted to see simply don't show up — not
  greyed out, not "access denied," just absent. If HR-only compensation
  data exists, an Employee-role account won't even know it exists,
  because the assistant is never given that content to draw from in the
  first place.
- The exact prompt sent to the AI model and detailed retrieval debugging
  are admin-only (the "Retrieval Inspector") — not something a regular
  user's chat interface exposes.

## Getting Help

If something looks wrong (a document you expect isn't findable, an
answer seems incorrect, the app is behaving unexpectedly), talk to your
administrator — they have dashboards showing exactly what the assistant
retrieved and why for any given question.
