# MCP Results — tina4-coder MCP on Antigravity

Method: Antigravity v1.107.0 (Gemini 3.5 Flash) builds the same app from the
same brief (`tasks/query-spec-v2.md`), 3 runs per config, one frozen 30-check
grader. **Vanilla** = stock Antigravity. **MCP** = stock + the `tina4-coder`
MCP server connected. MCP usage counted from session transcripts, not
self-report.

## Sub-modes of the MCP runs (deliberate split)

| Run | Prompt | Mode | tina4-python |
|-----|--------|------|--------------|
| run-1 | v2.1, bare | undirected — does the agent reach for MCP on its own? | 3.13.58 |
| run-2 | v2.2-C | directed — `tina4_context` only for framework knowledge, all code self-written | 3.13.60 |
| run-3 | v2.2-C | directed (repeat) | ⛔ blocked, service down |

## Scores

| Config | Run 1 | Run 2 | Run 3 |
|--------|-------|-------|-------|
| Vanilla | 27/30 | 28/30 | 16/30 |
| MCP | **29/30** | **28/30** | ⛔ |

- MCP run-1 (29/30): first perfect F-tier of the eval (16/16), P 4/4, T 1/1.
  Only red: S6 — ships no .gitignore; generated `.env.local` (TINA4_SECRET)
  uncovered (AG-C1-02).
- MCP run-2 (28/30): F 14/16, P 4/4, T 1/1, S 7/7. Reds: F15 no functional
  cover upload — multipart accepted but ignored, and the default cover path
  404s since no images dir ships (AG-C2-01); F18 no API docs at all
  (AG-C2-02).

## Actual MCP usage (transcript-verified)

| Run | `call_mcp_tool` | Breakdown |
|-----|-----------------|-----------|
| run-1 (undirected) | **0** | 7 tools connected and listed; never touched |
| run-2 (directed) | **14** | all `tina4_context` — 11 answered + 3 failed; 0 codegen tools |

The headline of the undirected mode: **available MCP ≠ used MCP.** The agent
built the best-scoring app of the whole eval from prior model knowledge and
never issued a single call. The directed run complied with the directive
(zero codegen-tool use) but ran local source introspection
(`dir()` / `inspect.signature()` on the installed package) as a co-equal
knowledge channel throughout — the directed sub-mode is in practice
MCP-first, not MCP-only.

## MCP service findings

- **MCP-01 — `tina4_context` served an API that does not exist in the
  installed framework.** Queue guidance taught
  `from tina4_python.queue import Queue, Producer, Consumer` +
  `Consumer(...).poll()`; `tina4_python.queue` (verified on 3.13.58; run-2
  pinned 3.13.60) exports only `Job`, `Queue`, and backend classes — the real
  interface is `queue.pop()`. All calls passed `language: "python"`. Cost to
  the run: email worker + tests written on the phantom API, own pytest caught
  the ImportError, one `tina4 serve` boot crashed, three fix cycles. The
  correct facts came from the agent's own introspection, not the server.
  Origin (stale docs vs cross-language grounding) unverified — probe when the
  service returns.
- **MCP-02 — service instability, now a full outage.** Timeline:
  - 2026-07-09 morning: initialize handshake 200, tools listed (setup check).
  - 2026-07-09 evening, mid-run-2: three consecutive `tina4_context` calls
    fail — "connection to the tina4-coder MCP server is closed or not
    responding"; no reconnect for the rest of the run.
  - 2026-07-10: independent probe (curl, outside Antigravity) — DNS resolves
    (`mcp.tina4.com` → CNAME `andrevanzuydam.com` → 41.71.84.173) but port
    443 **refuses connections**; `tina4.com` itself is up on separate infra.
  The independent-client refusal shifts attribution to the service side
  (daemon down / firewalled), not the Antigravity MCP client. **Run-3 is
  blocked on this.**
- **Retrieval friction (answered calls):** queue topic queried 3× with
  progressively narrower instructions before (wrong) usable content came
  back; template rendering never answered (the 3 failed calls) → the run
  hand-rolled its own `render()` helper. One oddity: the agent mid-run
  addressed the operator, asking them to "trigger the tina4_context tool".

## Interpretation (provisional, n=2)

- No measurable score benefit from the MCP in either sub-mode on this task:
  the undirected run ignored it and set the eval's best score; the directed
  run matched the vanilla best while paying a real correctness tax (MCP-01)
  and an availability tax (MCP-02).
- The model's prior Tina4 knowledge is strong enough on this task that
  retrieval had nothing obvious to add — the discriminating value of the MCP
  would have to show on framework versions/features newer than the model
  cutoff, which this task does not force.
- Caveats before any firm claim: two runs, one task, one model; tina4-python
  version skew across runs (3.13.54–.60); run-2's directive changed agent
  behaviour beyond tool choice (research-then-plan pattern); scores saturate
  near the top so headroom is thin.

## Open items

- run-3 (directed, port 7033) — blocked until mcp.tina4.com accepts
  connections again; re-probe before packing.
- MCP-01 origin probe (replay the queue instruction against the live server
  and inspect the returned grounding) — when service returns.
- run-2 wall-clock segments (user-timed) outstanding; run-1 timing/burn
  unknown (built in a session that predates timing capture).
