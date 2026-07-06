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
| Antigravity v1.107.0 | A — vanilla | — | — | — | (pending) |
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
