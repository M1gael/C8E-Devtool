# Query Spec — Tina4 CRUD Task (v1 — FROZEN 2026-07-06)

The exact prompt given to the tool's AI agent. Same text verbatim for every run,
every config, every tool. `{PORT}` is replaced with the run's assigned port from the
port table in `run-protocol.md` before pasting. No other edits allowed.

Once frozen, this file never changes; a revised task is a new versioned spec file
(`query-spec-v2.md`) and results across spec versions are not compared.

---

## Prompt text

```
Build a small book-tracking web app using the Tina4 Python framework (tina4-python).

Requirements:

1. A Book record with fields: id, title, author, published_year.
2. Use the framework's ORM for the model and its migration mechanism to create the
   database table (SQLite is fine).
3. A JSON REST API:
   - GET    /api/books        — list all books
   - GET    /api/books/{id}   — fetch one book
   - POST   /api/books        — create a book
   - PUT    /api/books/{id}   — update a book
   - DELETE /api/books/{id}   — delete a book
4. A web page at / that lists all books, rendered with a template.
5. The app must run with `tina4 serve` on port {PORT}.
6. When you are done, write a BLOG.md in the project root: a short blog post
   describing what you built, how it works, and why you made the technical choices
   you made.

Build it in the current directory. Data must survive an app restart.
```

---

## Design notes (not part of the prompt)

- Feature names (ORM, migration, template) are named because a realistic user asks
  for capabilities; HOW they are implemented (file layout, base classes, idioms) is
  what the idiom score measures. The prompt never mentions the devkit, its rules
  files, or the MCP.
- "Data must survive an app restart" forces a real database over in-memory
  shortcuts and makes persistence mechanically checkable.
- BLOG.md is part of the one-shot deliverable so the run stays zero-human-input.
