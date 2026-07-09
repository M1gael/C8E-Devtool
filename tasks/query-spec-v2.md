# Task Spec v2 — "use Tina4 to build it" (no framework leads)

> **v2.1 (2026-07-08):** prompt now pins the LANGUAGE ("Tina4 Python framework") — v2.0
> left it open and run-3 built PHP (finding AG-A2-03). Runs 1–2 ran on v2.0 wording and
> organically chose Python; run-3 rerun + configs B/C use v2.1. Naming a language is a
> platform constraint like the port, not a framework lead.

> **v2.2-C (2026-07-09, config-C runs 2–3 only, user decision):** adds one "Framework
> knowledge" block (below, marked) directing the agent to source framework knowledge
> ONLY via the MCP `tina4_context` retrieval tool and to write all application code
> itself (no tina4_code/tina4_review/tina4_chat codegen). Comparability: C run-1 ran
> BARE v2.1 (measures undirected MCP discovery); C runs 2–3 measure directed
> retrieval-grounded building. Deliberate intra-C split — label the two sub-modes in
> all comparisons. Configs A/B unaffected.

Supersedes `query-spec.md` (v1) for the redo. v1 saturated: a plain single-entity
CRUD app let a capable model score 9/9·6/6 in every run, and most of the output was
`tina4 init` scaffold — so the task barely tested the tool. v2 is a richer, coherent
product whose plain-English requirements *force* many more Tina4 features, without
ever naming one. Feature coverage is grounded in `book-1-python` (pulled via
`tina4 books`).

Rules for the brief: describe **product outcomes only**. Never name a framework
mechanism (ORM, migration, route, decorator, session, queue, mailer, localisation,
OpenAPI, validation, status code, etc.). Tone: "use Tina4 to build X." Nothing about
docs — if a tool fetches the book/docs itself, that is part of what that config *is*
and gets logged; we neither invite nor forbid it.

---

## Grading map — NOT given to the agent (our reference)

Each requirement and the Tina4 capability it silently forces + book chapter:

| Requirement (product wording) | Forces (unspoken) | Book ch |
|---|---|---|
| Books, members, loans; each book's current status + full loan history | data model + **relationships** + migrations | 05, 06 |
| All data survives restarts | real persistence, not in-memory | 05 |
| Browse/search by title/author/year; page smoothly through tens of thousands | query building, **pagination**, indexing | 07 |
| Staff sign in before managing anything | **authentication + login + sessions** | 08, 09 |
| Anyone not signed in is **refused by the API**, not just hidden in the UI | write-auth actually enforced; correct public/protected split; **works with debug off** | 08, 34 |
| Every change attributed to a staff member, recorded for audit | logging / audit trail | 15 |
| Borrow → member emailed a receipt; recording the loan returns immediately | **background queue + email + events** | 12, 16, 13 |
| A book already out cannot be borrowed again; API rejects clearly | domain validation + **correct error responses** | 03 |
| Bad/incomplete input rejected with clear, correct errors | input validation, proper status codes | 03 |
| Each book has a cover image users can upload | **file upload** handling | 03 |
| Clean, usable web interface | templates / frontend | 04, 17 |
| Available in English and one other language | **localisation** | 14 |
| Ships an automated test suite proving the behaviour | **testing** | 18 |
| Interactive documentation for the API | OpenAPI / Swagger | 20 |
| Runs under `tina4 serve` AND in production config (debug off, real secret) | deployment posture, secret hygiene | 33, 34 |

That is ~12 feature areas vs v1's ~4. The auth-in-production axis — the exact thing
v1 couldn't measure — is now a core requirement, phrased purely as behaviour.

This is a demanding task by design; expect longer runs and higher token cost per run.
That cost delta between configs A/B/C is itself a signal worth recording.

---

## PROMPT — paste everything below this line to the agent

Use the Tina4 Python framework to build **Lend** — a community lending-library
application.

The public can browse and search the catalogue. Library staff sign in to manage it.
Lend must work both as a website and as a JSON API, and it must be production-ready.

**Catalogue & data**
- Track books (title, author, published year, ISBN, and a cover image), members
  (name, email, join date), and loans (which member has which book, the borrow and
  due dates, and whether it has been returned).
- A book can be borrowed by different members over time. Lend must always know a
  book's current availability and its full borrowing history.
- All data must persist and survive an application restart.

**For the public (not signed in)**
- Browse and search the catalogue by title, author, or year, and page through it
  smoothly even when it holds tens of thousands of titles.
- Open any book to see its details, including whether it is currently available.

**For staff (signed in)**
- Staff must sign in before they can add, edit, or remove books or members, or record
  loans and returns.
- Anyone who is not signed in must be refused from those actions — not merely hidden
  in the interface, but actually refused by the API.
- Every change is attributed to the staff member who made it and recorded so it can
  be reviewed later.

**Borrowing**
- When a member borrows a book, they are emailed a receipt showing the due date.
  Recording the loan must return immediately — nobody should wait for the email.
- A book that is already out on loan cannot be borrowed again until it is returned;
  the API must reject that attempt clearly.

**Quality bar**
- Incomplete or invalid input is rejected with clear, correct error responses.
- The web interface should be clean and easy to use, and available in English and one
  other language.
- Include an automated test suite that proves the behaviour described above.
- Provide interactive documentation for the API.

**Framework knowledge** *(v2.2-C block — include ONLY for config-C runs 2–3; omit everywhere else)*
- When you need Tina4 framework knowledge, obtain it only through the connected
  Tina4 MCP server's context tool (`tina4_context`). Do not use that server's
  code-generation, review, or chat tools to produce the application — write all
  the application code yourself.

**Running it**
- It must run under `tina4 serve` on port {PORT}.
- It must also run correctly in production configuration — with debugging turned off,
  a real secret configured, and all data intact.
- Work entirely within the current working directory — build everything here, and do
  not create or modify anything outside it.

When you are finished, write a `BLOG.md` describing what you built and the key
decisions you made.
