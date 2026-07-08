# Per-run metrics — time + tokens (v1)

Not frozen (recording metadata, not eval semantics). Captured per run in `run.json`.
Model/mode are pinned across all 9 runs (see run-protocol.md), so token and time
deltas are a fair A/B/C comparison — the whole point is whether devkit/MCP change
them for the same task.

## Time

- **Wall clock (primary, manual):** note prompt-paste time → agent done-declaration.
  Goes in `run.json` as `started_at` / `ended_at` (ISO 8601) → `duration_s`.
- **mtime proxy (secondary, automatable):** earliest→latest file mtime in the run
  dir approximates build span. Planned to auto-fill in `grade_run.py` (NOT built
  yet — see open loops in findings-log.md). Rough: idle gaps count.

## Tokens — source is uncertain, capture what exists

No single reliable source. In priority order:

1. **Antigravity usage panel** — IF the IDE surfaces per-session tokens, that is the
   real number → `run.json.tokens`. UNCONFIRMED that Antigravity exposes raw tokens
   (many agentic IDEs show requests/credits instead). **Must verify in the IDE.**
   If it only shows requests/credits, record that under `tokens_note`.
2. **Tina4 portal (config C only)** — shows `requests` ("N/1000"), i.e. count of
   `tina4_code` / `tina4_review` MCP calls, NOT whole-agent tokens. Record the
   before/after request delta for a config-C run in `run.json.mcp_requests`.
3. **Network capture** — rejected: invasive, fragile, counts often not exposed.

If tokens are unobtainable, leave `tokens: null` — do not fabricate. A run with no
token number is still valid on the functional/idiom scores.

## Session-bucket % (coarse config-cost proxy)

When raw tokens aren't exposed, record the **% of the tool's rate-limit window** the
runs consume, read from the IDE's own usage meter. For Antigravity Pro this is the
5-hour session bucket. Capture it **per config phase** (cumulative across that phase's
3 runs) — too coarse to attribute per-run reliably, but a valid A-vs-B-vs-C cost
comparison for the same task. Record in the phase's Run notes, not `run.json`.
Phase A (a-vanilla): **38% of the 5h bucket** for all 3 runs (2026-07-07).

## run.json template

Written into each `run-N/` at freeze (step 4 of run-protocol.md):

```json
{
  "tool": "antigravity",
  "tool_version": "1.107.0",
  "config": "a-vanilla",
  "run": 1,
  "port": 7011,
  "model": "gemini-flash-3.5",
  "mode": "turbo",
  "started_at": "2026-07-07T09:00:00Z",
  "ended_at": "2026-07-07T09:04:30Z",
  "duration_s": 270,
  "turns": null,
  "self_tested": null,
  "tokens": null,
  "tokens_note": "",
  "mcp_requests": null,
  "asked_question": false,
  "notes": ""
}
```

- `tokens` / `turns` / `self_tested`: fill from the IDE if it shows them, else null.
- `mcp_requests`: config C only (portal request delta), else null.
- `asked_question`: true if the agent asked anything (answered only "Proceed with
  your best judgment" per protocol).
- Framework version stamp uses the **pip-reported** tina4-python version, not the
  package `__version__` string (see finding FW-02).
