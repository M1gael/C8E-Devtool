# Findings Log

Living log for all findings across tools and configs. Log-only policy: findings are
recorded here with version stamps and reproduction steps; nothing is fixed from here.

Finding ID format: `<TOOL>-<CONFIG>-<n>` — e.g. `AG-A-01` (Antigravity, vanilla, first
finding). Harness/assist-layer findings (devkit installer, MCP service) use
`DK-<n>` / `MCP-<n>`. Framework defects encountered while building the harness use
`FW-<n>` (they affect what agents under test will produce).

## Evaluation Progress

| Tool | Config | Run 1 | Run 2 | Run 3 | Ledger |
|------|--------|-------|-------|-------|--------|
| Antigravity v1.107.0 | A — vanilla | ▶ | ▶ | ▶ | (pending) |
| Antigravity v1.107.0 | B — +devkit | — | — | — | (pending) |
| Antigravity v1.107.0 | C — +MCP | — | — | — | (pending) |

Statuses: — not started · ▶ in progress · ✓ graded · ⛔ blocked

## Harness status

- 2026-07-06 — Grader calibrated: reference app (graders/reference-app/, built from
  docs on tina4-python 3.13.52) scores **9/9 functional, 6/6 idiom**. One grader bug
  found+fixed during calibration (F9 DDL scan walked into `.venv/`).
- 2026-07-06 — Baseline A-vanilla captured (baselines/A-vanilla/): 7 extensions
  (versioned), no settings.json (OOB defaults), no AGENTS.md, eval ports 7000–7040
  free, devkit content pinned by SHA256. MCP: `~/.gemini/config/mcp_config.json`
  exists but is **empty (0 bytes)** — no servers configured; this is the file
  config C will populate with the Tina4 MCP.
- 2026-07-06 — Hub built (hub/, tina4 app on :7000) and verified end-to-end:
  discovers all 9 runs, reflects a live app's running state + click-through links,
  flips back on teardown. Warm page load ~300 ms.

## Open loops / next actions

- **Phase A in flight (2026-07-07).** All three A-vanilla runs executed on the Pro
  account (Flash 3.5 / Turbo / medium). **All three declared done (2026-07-07);
  outputs frozen + committed (isolation .git removed).** **Grading deferred to a
  single clean pass**: agent-spawned `tina4 serve` instances are IDE-managed, unkillable
  from the shell (Access denied), so 7011/12/13 only free when their IDE windows are
  closed. A stale server tests instead of a clean boot → invalid grade. See Run notes
  below. Grade command per run:
  `python graders/grade_run.py --run-dir <dir> --port <7011|7012|7013> --serve-cmd "uv run tina4 serve --no-browser"`.
- **First bust (2026-07-07, discarded).** A-1 attempt 1 hit the free-tier session
  limit mid-build → invalid per run-protocol (never declared done). run-1 wiped clean,
  re-run on Pro. Switched to Pro for all 9 runs (same model/mode → not a confound;
  account tier is quota only).
- **Repo status.** Harness + baselines + A-vanilla runs 1-3 (frozen, ungraded)
  committed to `main` as M1gael and pushed to origin. Not yet committed: per-run
  grading results (`results.json`/`run.json`) — land in the clean grading pass.
- **Token capture unresolved.** Need to check whether Antigravity surfaces per-session
  tokens (see tasks/metrics.md). Until confirmed, `run.json.tokens` stays null.
- **Grader auto-duration not built.** mtime-based `duration_s` auto-fill in
  grade_run.py was proposed, not implemented. Time is manual (run.json) for now.
- **Hub process is session-bound.** Background `tina4 serve` dies when the Claude
  session ends; restart with `cd hub; uv run tina4 serve --no-browser`. Baseline is
  static files — needs no restart.

## Run notes

### A-1 (antigravity/a-vanilla/run-1) — DONE, grade pending
- Timeline (local SAST = UTC+2): start **12:57**, last source edit **13:17** (~20 min).
  Cost: **10% of the Pro 5-hour session bucket**. `self_tested=YES` — proven: the
  agent's own `logs/tina4.log` shows it ran `tina4 serve` and exercised
  GET/POST/PUT/DELETE + GET / live (all 200/201) before declaring done.
- Output shape: idiomatic — `src/routes/{books_api,web}.py`, `src/orm/Book.py`
  (ORM: IntegerField/StringField, `table_name="books"`), `migrations/…_create_books_table.sql`,
  `src/templates/{base,books}.twig`, `pyproject.toml`+`uv.lock`+own `.venv`, `BLOG.md`.
  `.env`: `TINA4_DEBUG=true`, `TINA4_DATABASE_URL=sqlite:///data/books.db`,
  `TINA4_PORT=7011` (binds 7011 — confirmed in log, no port artifact).
- **Preliminary finding AG-A-01 (to verify at EOD):** all three write routes register
  as **`auth=required`** (per boot log) despite the agent stacking `@noauth()` above
  `@post/@put/@delete` in books_api.py. Writes only succeeded in self-test because
  `TINA4_DEBUG=true` bypasses auth. With `DEBUG=false` (production) POST/PUT/DELETE
  would 401 → latent production-auth failure. Suspected cause (unconfirmed): decorator
  order — `@post` registers the route before `@noauth()` runs — and/or `@noauth` import
  path `tina4_python.core.router`. Grader will show F3/F6/F7 empirically (expected to
  pass under shipped debug=true .env). Confirm whether it's agent error vs framework
  behavior before assigning origin.
- Grading blocker at time of writing: agent's `tina4 serve` still LISTENING on 7011
  (PID 30576, child of Antigravity PID 33052); `taskkill` → Access denied. Needs the
  run-1 IDE window closed to free the port for a clean-boot grade. Note: tina4 also
  opens a secondary "test port" 8011 (stable, no hot-reload) alongside 7011.

### A-2 (run-2) & A-3 (run-3) — DONE, grade pending
- Both produced idiomatic output: `src/routes/`, `src/orm/Book.py`, `migrations/`,
  `src/templates/{base,books}.twig`, `pyproject.toml`+`uv.lock`, `BLOG.md`. Both `.env`
  ship `TINA4_DEBUG=true` + correct port (7012 / 7013). No inline secrets (sweep clean;
  `TINA4_SECRET` isolated in gitignored `.env.local`).
- Structural variance to weigh at grading: run-1 & run-2 split routes into
  `books_api.py` + `web.py`; **run-3 uses a single `src/routes/books.py`**. run-1 &
  run-3 wrote their own `.gitignore` (excluding `.env`); **run-2 wrote none**.
- **run-3 left a `temp_init/` scratch scaffold** (full duplicate tina4 skeleton) in the
  run root — agent cruft, committed as frozen evidence. Candidate cleanliness finding
  **AG-A-03** (verify at grading).
- run-2 & run-3 contain a gitignored `.tina4/` dir (tina4's built-in multi-agent config:
  coder/debug/planner/supervisor/vision + `chat/thoughts.json`) — framework runtime
  state, **not committed**; noted for interest (run-1 has none). run-1 & run-2 share an
  identical migration timestamp (`…110004`); run-3 differs (`…132000`).
- Detailed self-test + auth-registration findings deferred to the clean-boot grading
  pass (reads each run's `logs/tina4.log` like A-1).

## Findings

FW-01 — Shipped CLAUDE.md documents `select().to_array()` but `select()` returns a plain list
- Found: 2026-07-06, tina4-python 3.13.52 (pip), while building the grader reference app.
- Issue: the package's bundled CLAUDE.md shows `Product().select(limit=100).to_array()`
  ("Common Patterns → REST API with ORM"), but `ORM.select()` returns `list[Self]`
  (orm/model.py `def select(...) -> list[Self]`), so the documented pattern raises
  `AttributeError: 'list' object has no attribute 'to_array'`.
- Relevance: coding agents read the shipped CLAUDE.md and will reproduce the crash
  verbatim. Reproduced live: reference app first draft failed exactly this way on GET /.
- Status: OPEN. Probe: reference-app calibration covers the corrected pattern.

FW-02 — Package `__version__` string lags the released version
- Found: 2026-07-06, tina4-python 3.13.52 (pip).
- Issue: `tina4_python/__init__.py` has `__version__ = "3.13.51"` while pip reports
  3.13.52; the debug error overlay also displays "Tina4 v3.13.51".
- Relevance: version stamps in eval results would be off by one patch if read from
  `__version__`. Eval records use the pip-reported version.
- Status: OPEN.
