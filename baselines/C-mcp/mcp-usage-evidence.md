# Config C — MCP usage ground truth (2026-07-09)

Source: Antigravity session transcripts at
`~/.gemini/antigravity/brain/<session-id>/.system_generated/logs/transcript_full.jsonl`.
Sessions identified by content, not mtime (run markers: port, "lending-library",
v2.2-C "Framework knowledge" block). In-repo artifacts are silent either way —
neither BLOG mentions MCP, both plan/ dirs empty — so transcripts are the only
measurement surface. No tokens appear below (tool-call args only).

## run-1 — session 5cdeb13b-2a0f-4695-a703-95265e8e2bc4 (bare v2.1 prompt)

**`call_mcp_tool` count: 0.** Server connected, 7 tools listed to the agent,
zero discovery, zero calls. The 29/30 build is pure prior model knowledge.

## run-2 — session a91ed73a-ba1a-4021-9c25-87c2e38cb962 (directed v2.2-C prompt)

**`call_mcp_tool` count: 14 — all `tina4_context`, zero codegen tools
(tina4_code / tina4_review / tina4_chat never invoked).** Directive complied
with in full. Call instructions, in order:

1. Basic project, routes, database configuration, ORM, templates (overview)
2. Routing detail: path/query params, request/response, cookies, headers, bodies
3. Authentication + sessions: login, JWT issuance, current-user identification
4. JWT auth + middleware detail: Bearer validation, secret config, sessions+API split
5. SQLite config, migrations, ORM models/relationships, query builder
6. Migration structure: file format, naming, run command
7. i18n setup: file locations, marking text, language selection
8. Queues: background workers, producers/consumers, code examples
9. Queue implementation: exact file content / class signatures
10. Queue import paths + signatures (third queue query)
11. Email: imports, SMTP env config, examples
12. Template rendering: `render` import + signature
13. Template rendering — "again"
14. Template rendering — "third attempt"

### Retrieval-quality signal

Two topics needed repeated queries: **queues ×3** (8–10) and **template
rendering ×3** (12–14, the agent's own toolAction labels say "again" / "third
attempt"). After the third template miss the run hand-rolled its own `render()`
helper (`src/app/template.py`) instead of using a framework call. One mid-run
oddity: the agent at one point addressed the operator — "Please trigger the
`tina4_context` tool if you have specific snippets or architectural
recommendations" — before resuming self-serve calls.

### Second source: the agent's own narration (user-provided, 2026-07-09 late)

The run-2 step narration from the Antigravity UI adds ground truth the
transcript grep could not show:

- **Calls 12–14 (template rendering) FAILED** — "the connection to the
  `tina4-coder` MCP server is closed or not responding". So the tally is
  **11 answered + 3 failed**; the server never came back during the run
  (→ MCP-02 in findings-log).
- **The queue context that WAS answered taught a nonexistent API** —
  `from tina4_python.queue import Queue, Producer, Consumer` and
  `Consumer(Queue(topic=...)).poll()`. Verified against an installed
  tina4-python 3.13.58: `tina4_python.queue` exports only Job, Queue, and
  backend classes; the real interface is `queue.pop()`. The run's email
  worker + tests were first written on the MCP-served shape, its own pytest
  run failed on the import, and one `tina4 serve` boot crashed on the
  leftover import before the agent fixed both by `dir()` introspection
  (→ MCP-01 in findings-log). All calls passed `language: "python"`.
- **Local source introspection was a co-equal knowledge channel** — dozens of
  `.venv\Scripts\python -c "... dir()/inspect.signature(...)"` probes on
  Response, redirect, TestClient, i18n, Frond filters/globals, plus a source
  search for "translate". The correct queue and render facts came from these,
  not from MCP. The directed sub-mode is therefore MCP-first, not MCP-only.
- **Why repo plan/ is empty:** implementation_plan.md, task.md,
  walkthrough.md, a verify_pages.py script, and a browser-test video all went
  to the session brain dir (Antigravity's sanctioned artifact location), not
  the working dir. Product files stayed inside the working dir.

## Non-eval session (excluded)

Session 3ab5424f-...: 11 `call_mcp_tool` calls, no Lend markers — this is the
user's separate other-AI-accident session (the retracted AG-C1-01 `example/`
scaffold). Not eval data; listed only so the count isn't misattributed later.
