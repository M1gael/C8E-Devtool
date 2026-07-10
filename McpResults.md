# MCP Results — tina4-coder MCP on Antigravity

Method: Antigravity v1.107.0 (Gemini 3.5 Flash) builds the same app from the
same brief prompt, 3 runs per config, one frozen 30-check
grader. **Vanilla** = stock Antigravity. **MCP** = stock + the `tina4-coder`
MCP server connected. MCP usage counted from session transcripts, not
self-report.

## Sub-modes of the MCP runs (deliberate split)

| Run   | Prompt     | Mode                                                                           | tina4-python            |
| ----- | ---------- | ------------------------------------------------------------------------------ | ----------------------- |
| run-1 | v2.1, bare | undirected — does the agent reach for MCP on its own?                          | 3.13.58                 |
| run-2 | v2.2-C     | directed — `tina4_context` only for framework knowledge, all code self-written | 3.13.60                 |
| run-3 | v2.2-C     | directed (repeat)                                                              | ⛔ blocked, service down |

## Scores

| Config  | Run 1     | Run 2     | Run 3 |
| ------- | --------- | --------- | ----- |
| Vanilla | 27/30     | 28/30     | 16/30 |
| MCP     | **29/30** | **28/30** | ⛔     |

- MCP run-1 (29/30): first perfect F-tier of the eval (16/16), P 4/4, T 1/1.
  Only red: S6 — ships no .gitignore; generated `.env.local` (TINA4_SECRET)
  uncovered (AG-C1-02).
- MCP run-2 (28/30): F 14/16, P 4/4, T 1/1, S 7/7. Reds: F15 no functional
  cover upload — multipart accepted but ignored, and the default cover path
  404s since no images dir ships (AG-C2-01); F18 no API docs at all
  (AG-C2-02).

## Worth noting

*(per-run assessments from narration + shipped code + BLOG; grown as each
run's output is reviewed)*

**Vanilla run-1 (27/30)** — narration reviewed 2026-07-10 (full narration
confirmed against brain session f4ca9444: port 7011, admin/staffpassword
seed):

- "Vanilla" is not doc-less — the framework vendors its own agent docs into
  every install, and that is what grounded this build. Six web searches came
  first and yielded little; the agent then read the installed package
  wholesale: the full ~1,900-line `CLAUDE.md` that tina4-python ships as
  package data (viewed in three chunks), then the
  auth/router/middleware/session/request/server/messenger/i18n/queue/
  test_client sources. The MCP context tool therefore competes with an
  always-present in-package doc channel, not with nothing.
- Only run of the eval with a true end-to-end suite: its tests spawn the real
  server as a subprocess and hit it over HTTP (12 tests, confirmed in
  `tests/test_lend.py`). That choice paid off directly — see next point.
- It hit the exact ORM misuse that later sank vanilla run-3 to 16/30
  (AG-A2-11): passed full SQL to `load()`, got login 500s. Because its E2E
  tests exercise the real login route, it saw the failure, inspected the
  framework source (`inspect.getsource(ORM.load)`), and self-corrected to
  `Staff.select_one(...)` — shipped fixed (`src/routes/auth.py:20`). Same
  model, same pitfall, opposite outcomes: test style was the difference
  between 27/30 and 16/30.
- Platform friction handled competently: Windows subprocess pipe deadlock in
  the test runner (fixed by redirecting server output to a log file) and a
  PORT vs TINA4_PORT env-key stumble.
- Claim inflation: the closing report declares a bilingual UI and "ready for
  production deployment"; graded reality is F16 FAIL (no translated string is
  ever actually served), F15 FAIL (no upload path), S6 FAIL (secret file
  unignored).

**Vanilla run-2 (28/30)** — narration tail reviewed 2026-07-10 (identified by
port 7012, task-414 log, app.ready seeding, ServiceRunner worker):

- **Third distinct doc channel: it pulled the entire book itself.** The run
  fetched all 38 chapters into `.tina4-docs/` via the CLI's own doc-pull
  (present on disk, gitignored-by-design, logged per spec: self-fetching docs
  is part of what the config IS). The narration shows chapter-level use:
  `13-events.md` read immediately before wiring seed-on-`app.ready`,
  `27-service-runner.md` before writing the worker. Combined with run-1
  (vendored CLAUDE.md + source) and MCP run-2 (`tina4_context`), each run
  self-assembled a different doc stack — the configs differ less in available
  knowledge than in which channel the agent happens to reach for.
- **Framework-idiom high-water mark of the eval:** credentials seeded on the
  `app.ready` event (found by grepping the GLOBAL site-packages for the
  hook), and the email worker is a proper ServiceRunner service — class with
  `__call__(ctx)`, `ctx.stop_event`-driven loop, retry-capped queue
  (`max_retries=3`). Doc-driven idiom, visibly downstream of the two chapters
  it had just read.
- **Auth-test fidelity, the middle of the spectrum:** suite is in-process
  (framework `Test` base, 7 tests, 1.19s) but every staff test logs in
  through the real `/api/staff/login` route. Run-1 tested login over real
  HTTP; run-3 minted tokens directly and shipped login broken. Both runs that
  exercised their login path shipped it working; the one that bypassed it
  did not.
- **Two framework-behavior claims ship in its report, both unverified,
  both probe-worthy:** (a) "TestClient bypasses route middleware" → added
  per-endpoint auth fallbacks (corroborates open finding AG-A2-08); (b) a
  combined up+down migration file "creates and immediately drops tables" →
  split into `.sql` / `.down.sql` pair (new claim, now queued for a probe).
  Plus a hand-rolled dotenv bootstrap (`src/__init__.py`: `load_env()`),
  implying `.env` wasn't loaded early enough for its import graph.
- **Claims vs grade:** closes with all requirements satisfied; reds are F15
  (multipart accepted but no stored cover path) and S6 (`.env.local`
  unignored) — the same F15+S6 pair as vanilla run-1, and upload is again
  the thing its own suite never asserts.

**MCP run-1 (29/30)** — narration tail reviewed 2026-07-10 (supplied
mislabeled as vanilla; identified by its c-mcp file paths, port 7031, brain
id):

- Confirms the zero-MCP transcript finding behaviorally: framework knowledge
  came from reading the framework source directly — `server.py` handler
  dispatch, `_invoke_handler`, `Request.param` — from the GLOBAL Python
  site-packages, never from any of the 7 connected tools.
- The 927 KB `default-cover.jpg` is AI-generated (Antigravity's
  `generate_image` tool) — a media-generation tool was used while the MCP's
  own `tina4_image` tool sat unused.
- Its three headline BLOG decisions are visible in-process: handler
  signatures standardized to `(request, response)` for TestClient
  compatibility, audit ordering switched to `ORDER BY id DESC` after
  observing same-second timestamps, drop-tables added to the test fixture.
- Credentials (admin/admin123) are documented only in the session's closing
  message — not in the BLOG or any shipped file.

**Cross-run: the `load()` sharp edge as an MCP test case.** Four runs, four
paths past the same framework pitfall: vanilla run-1 fell in and climbed out
via E2E tests + source inspection; vanilla run-3 fell in and shipped it
(16/30); MCP run-1 never touched the ORM for login (raw SQL via
`Database.fetch_one`); MCP run-2 — the only run that retrieved auth guidance
from `tina4_context` — used the `load("email = ?", [email])` signature
correctly first try. One data point in the MCP's favor on exactly the kind of
API sharp edge retrieval should defuse; n=1, noted not concluded.

## Actual MCP usage (transcript-verified)

| Run                | `call_mcp_tool` | Breakdown                                                     |
| ------------------ | --------------- | ------------------------------------------------------------- |
| run-1 (undirected) | **0**           | 7 tools connected and listed; never touched                   |
| run-2 (directed)   | **14**          | all `tina4_context` — 11 answered + 3 failed; 0 codegen tools |

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
- The model's prior Tina4 knowledge — reinforced by the ~1,900-line
  `CLAUDE.md` tina4-python vendors into every install and by direct source
  introspection — is strong enough on this task that MCP retrieval had
  nothing obvious to add. The discriminating value of the MCP would have to
  show on framework versions/features newer than the model cutoff or absent
  from the vendored docs, which this task does not force.
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
