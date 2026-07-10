# Tina4 MCP Evaluation — Results (interim)

**Question:** does connecting the `tina4-coder` MCP server to an AI coding
tool make it build better Tina4 applications than the same tool out of the
box?

Test subject: Google Antigravity v1.107.0 (Gemini 3.5 Flash). Five of six
planned runs are complete; the last is blocked by an MCP server outage, so
conclusions are provisional.

## What I did, and how

- **Wrote a realistic build brief** — "Lend", a community lending-library
  app: public catalogue with search and pagination, staff sign-in, loans
  and returns, emailed receipts that must not block the request, an audit
  trail, two languages, an automated test suite, interactive API docs, and
  it must also run in production mode. The brief is written purely in
  product language — it never names a framework feature, so nothing steers
  the agent toward or away from any tool.
- **Ran the same brief under two configurations, three runs each:**
  **Vanilla** = stock Antigravity. **MCP** = identical, plus the
  tina4-coder server (7 tools) connected and verified working beforehand.
- **Split the MCP runs deliberately:** run-1 got the bare brief — measuring
  whether the agent reaches for the MCP on its own. Runs 2–3 add one
  sentence directing it to source framework knowledge only from the MCP's
  documentation-retrieval tool (`tina4_context`) and to write all code
  itself.
- **Isolated every run:** each build happens in a fresh directory with the
  rest of the repository moved out of reach, so no run can crib from a
  previous one.
- **Graded every run with the same frozen 30-check grader** built for this
  evaluation: it boots each app on a throwaway copy and exercises it live
  (login with the seeded credentials, search, pagination, borrowing and
  double-loan rejection, whether unauthenticated writes are actually
  refused, whether data survives a restart), re-checks the critical paths
  in production mode, runs the app's own test suite, and checks code
  conventions. Checks never change between runs, so scores are comparable.
- **Verified what each run actually did from Antigravity's own session
  transcripts** — MCP usage is counted from logged tool calls, never from
  what the agent claims. Each run's full session narration, shipped code,
  and write-up were reviewed against each other.

## Scores

| Config  | Run 1     | Run 2     | Run 3      |
| ------- | --------- | --------- | ---------- |
| Vanilla | 27/30     | 28/30     | 16/30      |
| MCP     | **29/30** | **28/30** | ⛔ blocked |

- MCP run-1 (29/30) is the best build of the evaluation — every live
  functional check passed. Its one miss: it ships no `.gitignore`, leaving
  its generated secret file uncovered.
- MCP run-2 (28/30): cover-image upload doesn't actually work (the uploaded
  file is ignored, and even the default cover is a broken link), and it
  ships no API documentation.
- Vanilla run-3 (16/30) shipped a broken login — see finding 6 for how that
  happened under a fully green test suite.

## How much the MCP was actually used

| Run                    | MCP calls | What happened                                                                 |
| ---------------------- | --------- | ----------------------------------------------------------------------------- |
| MCP run-1 (bare brief) | **0**     | The tools never entered the agent's reasoning — no mention, no call, start to finish. |
| MCP run-2 (directed)   | **14**    | All to the documentation tool, exactly as instructed; 11 answered, 3 failed when the server dropped mid-session. |

## Findings

1. **Left to itself, the agent doesn't use the MCP — and didn't need it.**
   The bare-brief MCP run made zero calls and still produced the best app
   of the evaluation from prior model knowledge plus the framework's own
   bundled documentation.
2. **The MCP competes with documentation that already ships inside the
   framework.** Every run converged on the same information sources: a
   quick web search (soon abandoned), then the ~1,900-line AI-oriented
   reference (`CLAUDE.md`) that tina4-python installs with the package,
   then reading the framework source directly. One run also downloaded the
   full 38-chapter documentation book with the CLI's own `tina4 docs`
   command. A "stock" agent is never actually documentation-less.
3. **When the MCP answered, it once answered wrongly — teaching an API that
   doesn't exist.** The retrieval tool described `Producer`/`Consumer`
   classes with a `.poll()` method; the installed framework has neither
   (the real call is `queue.pop()`). The run built its email worker and
   tests on the phantom API, its own tests caught the failure, and the
   agent recovered by reading the framework source. Cost: two broken
   files, one failed server boot, three fix cycles. Every call had
   requested Python explicitly, so this points at stale or cross-language
   content on the server side (to confirm when the service returns).
4. **The MCP service itself proved unreliable and is currently down.** It
   passed verification the morning of 9 July, dropped mid-session that
   evening (three consecutive failed calls, no recovery), and since
   10 July refuses connections outright — confirmed with an independent
   probe outside Antigravity. This blocks the final run.
5. **One genuine point in the MCP's favor:** the framework's ORM `load()`
   method takes a filter clause, not full SQL — a known sharp edge. The
   only run that retrieved auth guidance from the MCP used it correctly on
   the first try; two vanilla runs got it wrong, and one shipped its login
   broken because of it. A single data point, but exactly the kind of
   mistake retrieval exists to prevent.
6. **What actually decided the scores was each run's own test design, not
   the configuration.** Runs whose test suites exercised the real login
   path shipped working authentication (27–29/30). The 16/30 run generated
   auth tokens directly inside its tests, never drove its own login route,
   verified only that the server boots — and shipped a broken front door
   under a green suite. It was also the fastest and cheapest run: the
   session budget the better runs spent went into verification loops.
7. **The agent consistently overstates completion.** Every run signs off
   "production ready" / "all requirements satisfied"; recurring unfixed
   gaps include the cover-upload feature and secret-file hygiene, and one
   run documents its seeded admin credentials only in the chat window, not
   in any shipped file.
8. **Two framework claims made by runs still need verification:** that the
   framework's test client bypasses route middleware, and that a migration
   file combining up- and down-SQL creates and then immediately drops its
   tables. Both are queued as isolated probes.

## Bottom line (interim)

On this task the MCP provided no measurable quality lift: unused when
optional, roughly score-neutral when mandated — while introducing one real
correctness cost (the phantom queue API) and one availability cost (the
outage). Its clearest value signal is finding 5. For the MCP to earn its
place, the service needs to be reliable and its content version-accurate;
its natural advantage would show on framework features newer than the
model's knowledge or absent from the bundled docs — which this task did
not force.

## Remaining work

- Final MCP run (directed) once the server accepts connections again.
- Replay the queue question against the live server to pin down the
  wrong-API origin (finding 3).
- Verify the two framework claims in finding 8.
- Complete the timing/cost comparison (two runs still missing wall-clock
  data).
