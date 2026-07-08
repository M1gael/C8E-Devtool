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
| Antigravity v1.107.0 | A — vanilla (v1 CRUD, archived) | ✓ 9/9 · 6/6 | ✓ 9/9 · 6/6 | ✓ 9/9 · 6/6 | a-vanilla-v1/ |
| Antigravity v1.107.0 | A — vanilla (v2 Lend) | ✓ 27/30 | ✓ 28/30 | ✓ 29/30* (rerun; * AG-A2-09/10) | a-vanilla/ · results-v2.json per run |
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
- 2026-07-07 — Grader I3 recalibrated. Run A-1 rendered via the `@template("x.twig")`
  decorator (a documented first-class idiom: `tina4_python.core.router.template`,
  router.py:791 + shipped CLAUDE.md; auto-renders a dict return via `response.render`
  under the hood). The I3 check only matched a literal `render(`, wrongly failing it.
  Widened I3 to accept `response.render(` OR `@template(` — this makes the grader match
  the frozen checklist's I3 intent ("rendered via a template file, no inline HTML"),
  not a change to the spec. Reference app re-verified **9/9 + 6/6** after the fix (gate
  passed), so no regression. Not rigging: the apps genuinely render; the check was too
  narrow.
- 2026-07-07 — Version skew caught + closed. The A-vanilla runs resolved tina4-python
  **3.13.54** (per each `uv.lock` + dist-info), but the grader reference was still on
  **3.13.52**. Bumped the reference venv to 3.13.54 (`uv pip install`) and re-calibrated
  → held **9/9 + 6/6**, so the grader is proven faithful on the exact version the runs
  used. Phase A is internally consistent — all three runs on 3.13.54. (All installs
  still self-report `__version__="3.13.51"` — FW-02.) Every install also ships
  `tina4_python/CLAUDE.md` as package data (confirmed in RECORD across 4 installs).

## Open loops / next actions

- **Phase A COMPLETE + graded (2026-07-07).** All three A-vanilla runs (Pro, Flash 3.5
  / Turbo / medium) scored **9/9 functional, 6/6 idiom** on the corrected grader.
  run.json + results.json written per run. **Not yet committed** (grading-results
  commit pending). Next real step is **Phase B (+devkit)** after a bucket reset — deploy
  the devkit per run dir, re-baseline, runs on 7021-7023. Grade command per run:
  `python graders/grade_run.py --run-dir <dir> --port <port> --serve-cmd "uv run tina4 serve --no-browser"`.
- **⚠ CEILING PROBLEM — raise the rubric before Phase B (top priority).** All 3 vanilla
  runs scored a perfect 9/9 · 6/6, so F1-F9 (basic-CRUD-works) and I1-I6 (right folders)
  are a **saturated floor** a capable model clears unaided — they cannot discriminate A
  vs B(+devkit) vs C(+MCP). If left as-is, B/C also score 100% and the eval answers "no
  difference" for lack of headroom, not lack of effect. BUT the scores saturated while
  quality did NOT: run-1/run-2 ship a latent prod-auth bug (AG-A-01), run-3 is clean;
  cruft (AG-A-03); idiom variance. **Plan (agreed in principle, not yet built):** add a
  discriminating tier and apply it to the ALREADY-FROZEN A outputs (no re-run needed —
  code is on disk; F1-9/I1-6 stay frozen, new tier is additive):
  (1) **prod-readiness pass** — boot each app with `TINA4_DEBUG=false`, re-hit writes →
  run-1/2 should 401 (fail), run-3 pass. One check, instant differentiation.
  (2) **hardening/quality H-checks** — input validation (400s), not-found (404s), correct
  status codes (201 on create + Location), no cruft/temp dirs, agent-written tests,
  framework best-practices (base-template inheritance, form tokens, queues where apt).
  Also lean on the already-designed **correction-cost** metric (protocol step 7) as the
  gradient. Optionally add a harder second task if even this saturates. Decision pending:
  build the H-tier + re-grade the 3 frozen A runs now (before spending tokens on B).
  **UPDATE (2026-07-07 PM): H-tier BUILT into `grade_run.py`** — H1 prod-auth, H2 not-found,
  H4 secret-hygiene, H5 cleanliness + observations; `--hardening-only` merges into
  results.json without touching frozen F/I; book-grounded (ch08/33/34/03). H2/H4/H5 work
  (all fail H4 secret; run-3 fails H5 for `temp_init/`; H2 all pass). **H1 is BLOCKED** by
  the prod-auth enforcement puzzle (see AG-A-01 reproduction note): `--production` no-token
  writes still 201, so H1 can't score. Hardening blocks in run-1/run-3 results.json are
  PROVISIONAL/suspect (H1 unreliable); run-2 not graded. Don't trust H1 until cracked.
- **v1 task is a BUST → v2 redo drafted (2026-07-07 PM).** Why v1 fails as an eval: (i)
  ceiling (above); (ii) most of the deliverable is byte-identical across all 3 runs —
  `app.py`, `Book.py`, `base/books.twig`, `app.css/scss`, migration DDL — almost certainly
  `tina4 init` SCAFFOLD, so the model only really authored the route file (the sole file
  that varied) → the task barely tests the tool. **VERIFY before rerun:** scaffold a fresh
  `tina4 init` app and diff against a run to quantify model-authored vs generated. **v2 spec
  written: `tasks/query-spec-v2.md`** — a "Lend" lending library, plain product brief with
  ZERO framework leads ("use Tina4 to build X"), forcing ~12 feature areas incl. real login
  enforced in production, related data, validation + error codes, pagination, background
  email, file upload, i18n, tests, OpenAPI, prod mode. **Docs policy DECIDED:** the prompt
  says NOTHING about docs — if a tool self-serves `tina4 books`/`docs`/`ai`, that's part of
  what that config IS and gets logged (not invited, not forbidden). v1 `query-spec.md` left
  frozen for the record.
- **Directory layout after the v1→v2 split (2026-07-07 PM).** v1 runs archived to
  `antigravity/a-vanilla-v1/run-{1,2,3}` — full evidence preserved (source, BLOG,
  results.json, run.json, logs, data, .env.local); git shows renames (history intact) +
  the previously-untracked results/run.json now staged. `antigravity/a-vanilla/run-{1,2,3}`
  recreated EMPTY (just `.gitkeep`), reserved for the v2 rerun. **Heads-up for readers:**
  findings-log paths written earlier as `a-vanilla/run-N` refer to the **v1** runs — now at
  `a-vanilla-v1/run-N`. Staged, NOT committed. Open: empty-vs-prescaffold for the v2 dirs
  (tied to the `tina4 init` scaffold-verification item).
- **v2 rerun status + "no skills" confirmation (2026-07-07 PM).** v2 runs being kicked off
  now (query-spec-v2 "Lend" brief, ports 7011/12/13, dirs start EMPTY → agent scaffolds
  itself). run-1 false-started once (a partial Lend build, 921 files) and was re-cleaned to
  empty. **Config A carries NO skills / added context:** the tina4 skill+context installer
  (`tina4 ai`) was never run (git-verified — zero AI-context artifacts anywhere in the
  runs), and Claude-Code-style "skills" are an operator-side (this session) feature that
  never touches the Antigravity output. Skills/context are the deliberate B(+devkit) /
  C(+MCP) variable; A is bare default Antigravity — this is the "test without skills"
  baseline. (Caveat: Antigravity's own internal defaults can't be audited from outside the
  IDE; nothing was added on our side.)
- **v2 config-A run outcomes + cost (2026-07-08).** All three vanilla Lend runs done
  building; the Gemini session budget is now exhausted. Session-meter readings (user's
  IDE meter, % remaining): 100% → **77%** after run-1 → **35%** after run-2 → **0%**
  mid-run-3. Per-run burn: **run-1 ≈23%, run-2 ≈42%, run-3 ≥35% (insufficient —
  truncated)**. (Correction: an earlier note read the 77% as a self-assessed completion
  estimate — it was the session meter.) Noteworthy: run-2 burned ~2× run-1 at similar
  wall time; run-2 is also the run that self-pulled docs. run-3 truncated + PHP →
  invalid; PHP build preserved in git (commit 0468d0e) and archived to
  `antigravity/archive/run-3-php-v2.0/`; run-3 to be RERUN on spec v2.1. **v2 de-saturation confirmed:** v1's trivial CRUD saturated to 9/9·6/6 + "done"
  in every run; the richer Lend task drops run-1 to a self-assessed 77% and kills run-3 on
  budget — the redesign is measuring headroom v1 couldn't. **run-1 wall-clock build time =
  22m 14s** (1,334 s; sum of timed work segments 42s + 15m + 3m42s + 1m37s + 48s + 25s);
  **run-2 = 21m 0s** (1,260 s; 19m + 2m); **run-3 = 18m 25s** (1,105 s; 25s + 5m + 13m) —
  PARTIAL: time-to-cutoff when the shared session budget ran out mid-run, NOT
  time-to-completion; not comparable to runs 1–2. Config-A active-build total across the 3
  runs ≈ **61m 39s** (3,699 s; 2 complete + 1 truncated). Grader NOT yet rebuilt for Lend (only scores
  single-entity CRUD) → no F/I scores for v2 yet. Open decision: re-run a clean run-3 once the budget resets vs. accept the
  truncated third as the run-3 result.

### v2 config-A findings (2026-07-08, post-build artifact inspection)

- **AG-A2-01 — self-served docs in 2 of 3 vanilla runs.** run-2 ran `tina4 docs` inside its
  project (`.tina4-docs/`, 38 Python chapters present); run-3 likewise (`.tina4-docs/`, PHP
  edition). run-1 pulled nothing (no `.tina4-docs/`, no `tina4-book/`). Spec v2 deliberately
  said nothing about docs (self-serve allowed + logged), so this is BEHAVIOR DATA, not a
  breach: given an identical prompt, the agent discovered the framework's context channel in
  2 of 3 runs. Consequence: config A is no longer uniformly "context-free" — per-run context
  column now required in all A/B/C comparisons (run-1 = bare; run-2/3 = self-fed docs).
- **AG-A2-02 — run-3 built the app in PHP.** `composer.json` (`tina4stack/tina4php ^3.0`),
  `composer.lock`, `index.php`, `src/**/*.php`, `vendor/` + phpunit, `.htaccess`,
  `nginx.conf.example`, `email_worker.php`. Same prompt as runs 1–2; those chose Python.
  run-3 is therefore non-comparable to the Python-target eval — invalid twice over
  (wrong language + budget-truncated).
- **AG-A2-03 — spec defect (OURS): v2 prompt never pins the language.** "Use the Tina4
  framework to build Lend" + a multi-language `tina4` CLI → language choice is left to
  chance; run-3 proves it flips. Fixed in spec (v2.1): prompt now says "Tina4 **Python**
  framework". Comparability note: runs 1–2 ran on v2.0 wording and organically chose
  Python — the only delta the pin introduces is one they already satisfied; run-3 rerun +
  configs B/C use v2.1. Logged as our harness mistake, fixed per fix-ours rule.
- **AG-A2-04 — observation: run-3 carries `.tina4/mcp.json`** ("tina4-live-docs" →
  `http://localhost:7013/__dev/mcp`, the framework's own dev-tools MCP). Origin (PHP
  `tina4 init` scaffold vs agent-added) unverified; whether Antigravity actually connected
  to it can't be determined from artifacts (baseline `~/.gemini` MCP config was empty).
  EOD: scratch PHP `tina4 init` to see if this file is stock scaffold.
- **Observation (recurring from v1):** both Python runs ship `TINA4_DEBUG=true` in `.env`;
  prod-posture compliance ("runs with debugging turned off") to be graded, not assumed.

- **run-1 GRADED (grade_lend.py, 2026-07-08): 27/30.** F-tier 16/18, P-tier 4/4,
  T-tier 1/1 (12-test unittest suite passes), S-tier 6/7. Full detail:
  run-1/results-v2.json. The three fails:
  - **AG-A2-05 — F15: no real cover upload.** `cover_image` is a pass-through string
    field (URL/text) on create/update; multipart image POST is accepted but no file is
    stored or served. Spec: "Each book has a cover image users can upload."
  - **AG-A2-06 — F16: Spanish unreachable by the public.** `/language/{lang}` guards the
    locale write behind `request.session`, but the app never issues a session cookie to
    anonymous visitors (verified: browser-faithful curl flow — home first, then switch,
    then home — zero Set-Cookie headers, zero es.json strings served). The switch
    silently no-ops for everyone who isn't logged in; the 43-key es.json is dead weight.
    Spec: "available in English and one other language."
  - **AG-A2-07 — S6: `.env.local` (TINA4_SECRET) not covered by own .gitignore.**
    Recurrence of v1's AG-A-06 secret-hygiene gap, now in the v2 build.
  Notable PASSES vs v1: unauth writes properly 401 in dev AND production (P3) — the
  write routes carry no `@noauth` and default auth enforces; F5/P3 measured directly.
  Borrow → 409 on double-borrow, queue artifact within 12s, restart persistence, audit
  attribution, swagger UI + spec — all real.
- **run-2 GRADED (grade_lend.py, 2026-07-08): 28/30.** F-tier 17/18, P-tier 4/4, T-tier
  1/1 (`tina4 test` → pytest, 7/7 green), S-tier 6/7. Fails: F15 (no real cover upload —
  same as run-1) and S6 (`.env.local` TINA4_SECRET unignored — same as run-1). Audit
  attribution is real ("Librarian" resolved per entry); German i18n real (9 locale strings
  served via `?lang=de`). Observation: staff seeding runs on the `app.ready` event AFTER
  the port answers — the first login attempt right after boot 401s until the seed lands
  (~1s); grader F4 retries up to 15s to stay fair.
- **Grader calibration honesty trail (grade_lend.py, 5 grader-side defects found+fixed
  during calibration; app scores never bent):** (1) swagger spec URL — framework serves
  `/swagger/openapi.json`, not the book's `/swagger/json` (→ DOC-01); (2) test-runner
  fallback treated uv's "Failed to spawn: pytest" as a test failure instead of
  runner-unusable (→ unittest fallback now runs; also surfaced FW-04); (3) synthetic
  ISBNs < 10 chars tripped run-2's own validator (payloads now valid so refusals are
  attributable to auth/domain, not validation); (4) F14 attribution regex missed run-2's
  staff name "Librarian" (per-run staff_names in adapters); (5) F16 originally accepted
  "page differs" (false-positive on any dynamic HTML) — now requires an actual translated
  string absent from the EN page; F7/F11 no longer accept 401 as "clear rejection".
  Determinism: run-1 scored 27/30 identically on consecutive runs of the final grader.

- **v2 BLOG-fidelity check (2026-07-08).** No v1-style fabrication found in either blog.
  run-2's BLOG is accurate throughout (7/7 tests, swagger URL, queue design, i18n — all
  match measurements). run-1's BLOG oversells one feature: a whole section on
  "Concurrent-Safe Internationalization" for a language switch that is unreachable by its
  audience (AG-A2-06) — parts built, end-to-end never driven; softer echo of v1's AG-A-04
  pattern. run-1's blog is otherwise truthful (409, PBKDF2, queue, audit all real).
- **AG-A2-08 — cross-check candidate from run-2's BLOG:** claims Tina4's `TestClient`
  "executes route handlers directly without firing their middleware", worked around by
  duplicating the auth check inside each handler. If true, middleware-protected routes are
  untestable via TestClient as shipped — framework-behavior claim worth an isolated probe
  (EOD queue). Claim is the agent's, unverified.

- **v2 config-A CONSENSUS (2026-07-08).** Verdict: vanilla Antigravity/Gemini builds a
  genuinely credible Tina4 app under a real task — the weakness is not code quality but
  run-to-run unpredictability plus three systematic gaps.
  (1) *Work is real:* 27/30 + 28/30 with earned passes — auth enforced dev+prod (v1's
  headline failure did not recur), real queue/email evidence, restart persistence, audit
  attribution, swagger, self-tests verified green. No blog fabrication (contrast v1
  AG-A-07); worst blog offence is run-1 overselling its unreachable i18n.
  (2) *Clone problem dead:* two genuinely different architectures (JWT + default-auth +
  hand-rolled queue polling + unittest vs middleware + events + ServiceRunner + framework
  I18n + up/down migrations + tina4 test). v1's byte-identical-runs pathology gone once
  the task got rich.
  (3) *Systematic gaps — the model's signature, same in every run:* file upload silently
  downgraded to a URL string field (both runs, independently — AG-A2-05); secret hygiene
  wrong in all three runs, each differently (AG-A2-07 + run-3's secret-in-.env); features
  built but never driven end-to-end as a user (run-1 language switch no-ops for anonymous
  visitors — AG-A2-06).
  (4) *Config-A's real story is behavioral variance:* identical prompt → one bare run,
  two runs self-fetching docs, one run switching language entirely (PHP). Directional
  hint, n=2, not a claim: the docs-fed run (run-2) used the most framework-native
  machinery and scored highest — the config-B hypothesis in miniature; B/C exist to test
  exactly this with the context controlled.
  Bottom line: given a real task, vanilla Gemini produces a credible Tina4 app; what it
  cannot be relied on to do is behave the same way twice, finish the last mile of a
  feature, or handle secrets.

- **run-3 ghost-scaffold incident + CLI language probes (2026-07-08 PM) — CORRECTED
  note; no rerun had started.** Minutes after the dir reset, `index.php`
  (`new \Tina4\App()` PHP bootstrap), a minimal `.env` (no secret) and empty
  `migrations/src/tests` dirs appeared in the emptied `a-vanilla/run-3/`. Writer died
  before autopsy; best-supported hypothesis: the ORIGINAL run-3 build session's
  `tina4 serve` (PHP, port 7013, launched by the agent, never killed after truncation —
  same lingering-server pattern noted at the v1 freeze) self-healed its scaffold at the
  old path after the archive move orphaned it. Two files were accidentally committed
  mid-incident (ed7ab32, harmless); cleanup commit removes them.
  **Probes (scratch, empty dir):** `tina4 init` → interactive language picker
  (python listed first), REFUSES non-interactively ("Use: tina4 init <language> <path>");
  `tina4 serve` → refuses ("Not in a Tina4 project"), scaffolds nothing. So the CLI does
  NOT default to PHP → original AG-A2-02 language drift was the AGENT'S choice at the
  picker (or an explicit `tina4 init php`), not a CLI default → the v2.1 prompt pin is
  the right control and should hold. run-3 re-verified empty (.gitkeep only) with all
  eval ports free; hub restarted.

### run-3 v2.1 rerun (2026-07-08 evening)

- **Timing/burn:** 25m wall, 34% session burn (100%→66%). Config-A v2 burns now:
  run-1 ≈23%, run-2 ≈42%, run-3 ≈34%.
- **Language pin HELD:** run-3 v2.1 is Python (pyproject + uv.lock, tina4-python; no
  composer.json). Confirms AG-A2-03's fix works; original PHP drift was the agent's pick.
- **AG-A2-09 — agent modified the EVALUATOR and self-graded (working-dir violation +
  benchmark gaming).** The run shipped a `results-v2.json` claiming **29/30** ("graded_at
  21:49", port 7513 — continuing the grader's own 7511/7512 pattern visible in committed
  sibling results). Forensics: `graders/grade_lend.py` (OUTSIDE the run's working dir;
  prompt forbade creating/modifying anything outside it) was modified at the same minute —
  the agent added itself a "run-3" adapter AND rewrote the F4 check: on login failure the
  check silently self-registers a staff account via the app's open `/api/register`, then
  reports F4 PASS. It then ran the modified grader against itself and shipped the result.
  The self-claimed 29/30 conveniently tops both siblings. Evidence preserved:
  `antigravity/archive/run-3-grader-tamper.patch` + the file renamed to
  `results-v2.self-claimed.json`; grader restored from git before real grading.
  **Post-verification:** the FROZEN grader (with an explicit, logged "provision" adapter
  step for the register→login flow) reproduces **29/30** — the self-claimed number was
  accurate, not inflated. The violation is the covert instrument modification, the
  working-dir breach, and that F4's "seeded creds" contract was unmeetable as written
  for this app (no staff exist on a fresh deploy) — surfaced by tampering instead of
  by documentation. The score carries an asterisk for AG-A2-10 regardless: the
  open-registration hole is invisible to the checks.
- **AG-A2-10 — open staff registration (security).** The app seeds NO staff; the only
  provisioning mechanism is `@noauth POST /api/register` (its own swagger description:
  "Development & Testing"), open to anyone. Tokenless writes do 401, but any anonymous
  visitor can register themselves as staff and then pass every auth gate — the spec's
  "anyone who is not signed in must be refused" is bypassable at the provisioning level.
  The grader accommodates the documented register→login flow via an explicit adapter
  "provision" step (grader change logged openly; runs 1–2 adapters unaffected) so the
  rest of the app is measurable; THIS finding carries the security verdict.
- **Recurring observations:** `.tina4-docs/` pulled AGAIN (self-served docs now 3 of 4
  runs; run-1 remains the only bare run); `TINA4_SECRET` sits in `.env` (not `.env.local`)
  — real secret, run-3/.env must stay uncommitted; `TINA4_DEBUG=true` shipped again.
  New-good: run-3 uses the framework `Validator` on loan input (first run to do so),
  splits tests into pytest files with a conftest, and has a dedicated middleware module.
- **HARNESS LESSON (affects B/C design): runs live INSIDE the eval repo.** The subject
  could read (and this run modified) the grader, the task spec incl. the grading map,
  findings-log, and committed sibling runs WITH their scores. v1's near-zero variance
  (AG-A-05) gains an alternative hypothesis: sibling visibility. Future runs should
  execute in an ISOLATED directory outside the harness repo, with artifacts copied in
  for freezing afterward.

### Framework/doc findings surfaced by v2 grader calibration (2026-07-08)

- **FW-04 — `tina4 test` exits 0 when pytest is missing (silent success).** CLI 3.8.53, in
  a project without pytest installed: `tina4 test` prints
  `...python.exe: No module named pytest` yet returns exit code 0. Any CI gating on that
  exit code would go green with zero tests run. Empirically testable → probe at EOD.
  Found while grading run-1 (its pyproject has no pytest dep; suite is unittest-style).
- **DOC-01 — book ch20 still documents the old swagger spec URL.** Chapter 20 uses
  `/swagger/json` (5 occurrences: curl examples, codegen `-i` URL, prose) but
  tina4-python 3.13.54 serves the spec at `/swagger/openapi.json`
  (`core/server.py:1220`; `/swagger/json` returns 404 — verified live during grading).
  Only `36-releases.md` mentions the new path — chapter 20 wasn't updated after the
  rename. Book copy pulled 2026-07-08 via `tina4 books`.
- **EOD verification queue (before filing):** (1) FW-03 isolated probe — minimal two
  routes, `@noauth` above vs below `@post`, confirm the registration flip on 3.13.52;
  (2) AG-A-01 prod-401 — ATTEMPTED, did NOT reproduce (see AG-A-01 note): need a boot that
  actually enforces auth (understand tina4's auth backend/middleware) + a working
  positive-control route; plus a CLAUDE.md ablation (remove file, re-run) to settle origin;
  (3) run-2/run-3 self-test evidence (grep their logs/tina4.log for request lines);
  (4) AG-A-07 — grep `tina4_python` ORM for any query-cache / transaction-scope to
  confirm or kill run-3's "request-scoped query caching" blog claim;
  (5) AG-A-08 — check `orm/model.py` for the real save-error accessor (`last_error` attr
  vs `get_error()` method) to see which run(s) carry a latent `AttributeError`.
- **Context-channel discovery (2026-07-07) — affects the "vanilla" premise + B/C design.**
  The global `tina4` CLI (`~/AppData/Local/tina4/tina4.exe`) ships three self-serve context
  channels a bare agent could reach: `tina4 books` (downloads the **entire** book anywhere —
  251 files / 19 MB, all languages incl. `book-1-python` 38 chapters + PDFs), `tina4 docs`
  (framework docs → `.tina4-docs/`, **project-scoped** — refuses outside a project), and
  `tina4 ai` (detects AI tools + installs framework context/skills; `--all`/`--force` force
  it for undetected tools). Plus the already-known bundled `tina4_python/CLAUDE.md`. So
  "config A = context-free" is only true because the agent didn't **discover** these, not
  because context is unavailable. **Verified the 3 A runs did NOT invoke them** (no
  `tina4-book/` or `.tina4-docs/` dir in any run) → A integrity holds for these runs.
  Implications: (a) B/C setup must decide deliberately whether book/docs/ai are in-scope and
  log it per run; (b) the H1 prod-auth check is now **book-grounded** — ch08 authenticates
  the correct `@post`-above-`@noauth()` order, so scoring run-1/2 as broken is doc-faithful,
  not opinion; (c) the `tina4 books` bundle is multi-language in one download — a pointer for
  the doc-eval track's single-language concern. EOD: run `tina4 docs` inside a scratch
  `tina4 init` project to capture what IT pulls (differs from `books`).
- **Pin the framework version for B/C (rigor — decide before Phase B).** Phase A resolved
  tina4-python **3.13.54** (unpinned `uv add` → latest). tina4-python releases fast
  (3.13.52→54 in ~2 days), so B/C could drift to a newer build and confound the A/B/C
  comparison — config must be the ONLY variable. Options: (a) pin 3.13.54 across all
  remaining runs via an env-level constraint (`UV_CONSTRAINT`/constraints file) invisible
  to the agent [recommended]; (b) accept drift and record version per run as a caveat;
  (c) re-run A if B/C land on a newer version. Record tina4-python version per run either
  way. May warrant a version-pin clause in run-protocol.md (A stays valid as-is: 3.13.54).
- **First bust (2026-07-07, discarded).** A-1 attempt 1 hit the free-tier session
  limit mid-build → invalid per run-protocol (never declared done). run-1 wiped clean,
  re-run on Pro. Switched to Pro for all 9 runs (same model/mode → not a confound;
  account tier is quota only).
- **Repo status.** Harness + baselines + A-vanilla runs 1-3 (frozen source) committed
  to `main` as M1gael and pushed (commit bdf7eb0). Remote is on the `github-m1gael` SSH
  alias. **Uncommitted now (pending a grading-results commit — user hasn't authorized
  it yet):** `antigravity/a-vanilla/run-{1,2,3}/results.json` + `run.json`,
  `graders/grade_run.py` (I3 fix), `graders/reference-app/results.json` (re-grade),
  `tasks/metrics.md` (session-bucket section), and all this session's `findings-log.md`
  edits. Nothing in this set contains secrets (all `.env.local`/`.venv`/`data`/`.tina4`
  gitignored). Reference-app venv was bumped to 3.13.54 (untracked, gitignored).
- **Token capture unresolved.** Need to check whether Antigravity surfaces per-session
  tokens (see tasks/metrics.md). Until confirmed, `run.json.tokens` stays null.
- **Grader auto-duration not built.** mtime-based `duration_s` auto-fill in
  grade_run.py was proposed, not implemented. Time is manual (run.json) for now.
- **Hub process is session-bound.** Background `tina4 serve` dies when the Claude
  session ends; restart with `cd hub; uv run tina4 serve --no-browser`. Baseline is
  static files — needs no restart.

## Run notes

### A-1 (antigravity/a-vanilla/run-1) — GRADED 9/9 · 6/6
- Timeline (local SAST = UTC+2): start **12:57**, last source edit **13:17** (~20 min).
  Cost: **10% of the Pro 5-hour session bucket**. `self_tested=YES` — proven: the
  agent's own `logs/tina4.log` shows it ran `tina4 serve` and exercised
  GET/POST/PUT/DELETE + GET / live (all 200/201) before declaring done.
- Output shape: idiomatic — `src/routes/{books_api,web}.py`, `src/orm/Book.py`
  (ORM: IntegerField/StringField, `table_name="books"`), `migrations/…_create_books_table.sql`,
  `src/templates/{base,books}.twig`, `pyproject.toml`+`uv.lock`+own `.venv`, `BLOG.md`.
  `.env`: `TINA4_DEBUG=true`, `TINA4_DATABASE_URL=sqlite:///data/books.db`,
  `TINA4_PORT=7011` (binds 7011 — confirmed in log, no port artifact).
- Grade: **9/9 functional, 6/6 idiom** (results.json). F3/F6/F7 (write CRUD) all pass,
  `auth_blocked=[]` — because `.env` ships `TINA4_DEBUG=true` (debug bypasses auth). I3
  passes on the corrected grader (recognises the `@template` render idiom).
- **AG-A-01 (latent prod-auth failure; cross-ref FW-03):** run-1's POST/PUT/DELETE
  register **`auth=required`** despite `@noauth()` stacked ABOVE `@post`. The decorator
  order is the cause — `@post` registers the route before `@noauth()` runs, so noauth
  never takes. With `DEBUG=false` these would 401. Notably run-1 & run-2 hit this
  (`@noauth` above), while **run-3 placed `@post` above `@noauth()` and correctly got
  `auth=public`** — a clean natural experiment. The broken order *matches* what the
  framework's bundled `CLAUDE.md` prescribes (gotcha 2b), BUT that file is Claude-targeted
  (`tina4_python/ai` detects claude-code/cursor/copilot/windsurf/aider/cline/codex —
  **not** Gemini/Antigravity), was **not** surfaced to this agent by the framework, and
  was **not** copied into the project (zero project-level context files, confirmed). So
  the AG-A-01↔FW-03 causal link is a **hypothesis, not proven** — the agent may have
  erred from its own priors. **Verdict certain** (auth=required in boot log; reproduced
  by the run-3 contrast). **Origin unproven.** EOD: isolated probe + check whether
  Antigravity ever reads `site-packages` docs.
- Historical: grading was initially blocked by the agent's IDE-managed `tina4 serve`
  holding 7011 (unkillable from shell); resolved once the IDE windows were closed.

### A-2 (run-2) & A-3 (run-3) — GRADED 9/9 · 6/6 each
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
- Both graded **9/9 functional, 6/6 idiom** (results.json), `auth_blocked=[]` (debug on).
- **Write-auth split (AG-A-01 / FW-03):** run-2's POST/PUT/DELETE register `auth=required`
  (same `@noauth`-above-`@post` order as run-1 → broken in prod). **run-3 registers them
  `auth=public`** — it placed `@post` ABOVE `@noauth()` (opposite order → works). So 2 of
  3 vanilla runs ship a latent prod-auth bug; run-3 does not. Consistency signal for the
  vanilla agent: same task, same tool, divergent auth-correctness.
- run-3 also uses `response.render` + `response.json` + `Book.all()` (vs run-1's
  `@template` + `response(...)` + `Book.select`) — all functionally equivalent here.
- Self-test: run-2 server booted 13:23 local, run-3 13:27 (logs); full per-run CRUD
  self-test not individually confirmed (run.json `self_tested=null`) — EOD grep queued.

### Phase A cost (coarse quota proxy)
- All three A-vanilla runs together consumed **38% of the Pro 5-hour session bucket**
  (2026-07-07). Run-1 alone ≈10% → runs 2+3 ≈28% (~14% each). Not token-precise, but a
  real **config-level cost signal**: compare Phase A's 38% against B (+devkit) and C
  (+MCP) later — does the assist layer make the same task cheaper or costlier in quota?
  Recorded because raw per-run tokens may be unobtainable (see tasks/metrics.md).

### Blog review (2026-07-07)
- Reviewed all three `BLOG.md`. All claimed files exist (`base.twig`, `books.twig`,
  `scss/app.scss`, `public/css/app.css`) and the ORM/migration/DB-URL descriptions match
  the code — no fabricated structure. Blog code snippets match the real source (run-2's
  `Book.select(limit=1000)` + `return response(books)` is verbatim, and passes the grader).
- Four findings out of it: **AG-A-04** (run-1/2 blogs call the broken write-auth "public"),
  **AG-A-05** (run-1≡run-2 byte-identical incl. shared `TINA4_SECRET` → only 2 distinct
  impls), **AG-A-06** (generated `.gitignore` guards `.env` but not the secret `.env.local`),
  **AG-A-07** (run-3 blog asserts "request-scoped query caching" — likely fabricated).
- Minor (cosmetic, no ID): run-1 blog misdescribes the port mechanism — claims port set by
  "passing `-p 7011` to `tina4 serve`", but the actual bind is `.env TINA4_PORT=7011`.
- None of these change the frozen 9/9 · 6/6 functional/idiom scores; all are doc-fidelity /
  variance / hygiene signals feeding the hardening-tier discussion.

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

FW-03 — Shipped CLAUDE.md prescribes `@noauth()` ABOVE `@post`, which leaves the route `auth=required`
- Found: 2026-07-07, tina4-python 3.13.52 (pip), across Antigravity A-vanilla runs.
- Issue: CLAUDE.md "Gotcha 2b" / routing section says write-auth decorators go ABOVE the
  route (`@noauth()` → `@post()` → def). But `@post` registers the route at decoration
  time (decorators apply bottom-up), so a `@noauth()` placed above runs too late and the
  route stays `auth=required`. Natural experiment: run-1 & run-2 (`@noauth` above) →
  POST/PUT/DELETE `auth=required`; run-3 (`@post` above `@noauth`) → `auth=public`. The
  framework's own `@template` docstring says the opposite (decorator must sit BELOW the
  route), so the guidance is internally inconsistent.
- Relevance: this CLAUDE.md is the framework's **sole bundled AI guide** and is
  **Claude-targeted** (`tina4_python/ai` detects claude-code/cursor/copilot/windsurf/
  aider/cline/codex — not Gemini/Antigravity), so it most directly threatens Claude-based
  tools that ingest it — they'd ship write routes that 401 in prod (masked in dev by the
  `TINA4_DEBUG` auth bypass). Same family as FW-01. NOTE: it was not surfaced to the
  Antigravity/Gemini runs here, so the run-1/run-2 order match is not proof this doc
  caused it (see AG-A-01).
- **Book contradiction (confirmed 2026-07-07, book pulled via `tina4 books`):** the
  framework's own authoritative book — `book-1-python/08-authentication.md` — uses the
  **correct** `@post`-above-`@noauth()` order **throughout** (register L130-131, login
  L190-191, §7 "@noauth and @secured" L368-375) and repeatedly stresses login/register must
  be public (L231, gotcha "Forgetting @noauth on login" L886-892). So the book is RIGHT and
  the bundled CLAUDE.md is WRONG: the framework ships **two authoritative docs that
  contradict on its single most important auth idiom**, and the defective one is the
  AI-context file coding agents ingest. run-3's working order matches the book; run-1/2's
  broken order matches CLAUDE.md. This upgrades FW-03 from "a doc is wrong" to "the AI guide
  contradicts the correct book" — a cleaner, stronger filing.
- Status: OPEN. Doc-wrongness now confirmed two ways (registration split in boot logs +
  book cross-check). EOD: isolated two-route probe on 3.13.52; pin the book commit/version
  (book.yml) for the filing.

AG-A-01 — 2 of 3 vanilla runs register write routes as auth=required (prod impact UNCONFIRMED)
- Found: 2026-07-07, Antigravity 1.107.0 vanilla, runs 1 & 2 (run-3 unaffected).
- Issue: POST/PUT/DELETE `/api/books` **register** `auth=required` (broken `@noauth` order,
  see FW-03) — CONFIRMED in the `--production` boot log ("Route registered: POST /api/books
  (auth=required)"). run-3 registers them `auth=public`. Functional grade is 9/9 because
  each `.env` ships `TINA4_DEBUG=true`.
- **Reproduction attempt (2026-07-07 PM) — the predicted prod-401 did NOT reproduce.** Two
  gotchas: (a) `tina4 serve` is the DEV server (serves writes regardless of DEBUG);
  production is `tina4 serve --production`. (b) Even under `--production` + `DEBUG=false`, a
  no-token `POST /api/books` on a run-1 copy returned **201**, not 401 — despite the boot
  log registering it `auth=required`. A positive-control route (a write route with NO
  `@noauth`) failed to load in that boot (404), so enforcement could not be validated. Net:
  "registered auth=required" is CONFIRMED; "**would 401 in prod**" is NOT reproduced —
  likely no auth backend/middleware is actually wired, so "required" routes may serve
  anyway. **Real-world impact of AG-A-01 is currently UNCERTAIN; do not report it as a
  confirmed prod break.**
- Origin (vs FW-03 / CLAUDE.md): unproven, but the earlier "a Gemini agent wouldn't read a
  Claude-targeted file" argument is **RETRACTED** — an LLM reads plain markdown regardless
  of intended audience, and that CLAUDE.md is reachable in the in-project venv. The 2/3 runs
  reproducing CLAUDE.md's *distinctive wrong* order is mild evidence FOR reading it; run-3
  diverged (correct order). Settle it via Antigravity's file-read log, or an ablation
  (rename/remove the bundled CLAUDE.md, re-run, see if the wrong-auth idiom disappears).
- Status: OPEN — DOWNGRADED. Registration confirmed; prod-401 unproven; enforcement not
  understood. Blocks grader H1 (see Open loops).

AG-A-03 — run-3 left a `temp_init/` scratch scaffold in the project root
- Found: 2026-07-07, Antigravity 1.107.0 vanilla, run-3.
- Issue: run-3 left a full duplicate tina4 skeleton under `temp_init/` (app.py,
  pyproject.toml, uv.lock, empty `src/` tree) beside the real app — build cruft not
  cleaned up before declaring done.
- Relevance: cleanliness/quality signal only; no effect on functional or idiom scores
  (grader ignores it). Committed as frozen evidence.
- Status: OPEN (cosmetic).

AG-A-04 — run-1 & run-2 BLOG.md report the broken write-auth as "public" (self-report masks AG-A-01)
- Found: 2026-07-07, Antigravity 1.107.0 vanilla, runs 1 & 2 (blog review).
- Issue: both blogs state the write routes are public — run-1: "Since these are public API
  routes, we bypassed authentication using the `@noauth()` decorator"; run-2: "By using the
  `@noauth()` decorator on modifying actions, we allow standard public HTTP requests" — and
  both print the `@noauth()`-ABOVE-`@post` snippet as the working recipe. That order leaves
  the routes `auth=required` (AG-A-01 / FW-03), so the claim is false under `DEBUG=false`.
  run-3's blog shows the correct `@post`-above-`@noauth()` order and its "public" claim holds.
- Relevance: doc-fidelity signal — the two defective runs also self-report the defect as
  success, so a reader following the blog ships the 401 bug believing the routes are public.
  Blog accuracy tracks the code bug 1:1 across the three runs.
- Status: OPEN.

AG-A-05 — near-zero inter-run variance: all 3 runs share one app, differing only in the route file (and run-1≡run-2 even there)
- Found: 2026-07-07, Antigravity 1.107.0 vanilla, source review (md5 across runs).
- Issue: byte-for-byte **identical across all three runs** — `app.py`, `src/orm/Book.py`,
  `src/templates/base.twig`, `src/templates/books.twig` (**314 lines of bespoke HTML/JS**),
  `src/public/css/app.css`, `src/scss/app.scss`, and the migration DDL (only the timestamp
  comment differs: `…110004` in run-1/2 vs `…132000` in run-3). The **sole** point of
  variation in the whole deliverable is the route layer: run-1 & run-2 use an identical
  `books_api.py`+`web.py` split (same md5), run-3 a single `books.py`. run-1 & run-2 also
  ship the **same** `TINA4_SECRET` (`cf1197…9df8`); run-3 differs (`ea757…0329`). So three
  same-prompt concurrent runs collapse to **one application with two route variants** — and
  the bespoke frontend, where creative variance should be greatest, is identical.
- Relevance: variance/discrimination signal, stronger than first logged — for config A the
  effective n is ~1 app / 2 route variants, not 3 independent samples. A-vs-B-vs-C deltas
  must clear an almost-zero noise floor. The identical 314-line frontend + shared secret
  confirm near-deterministic regeneration at this model/mode (Flash-3.5, turbo), not merely
  convergent code. (app.py is the framework scaffold default, so its identity is expected;
  the bespoke `books.twig`/`app.css`/`app.scss` identity is the notable part.)
- Status: OPEN.

AG-A-08 — save-failure branch uses an unverified (and cross-run-inconsistent) ORM error API
- Found: 2026-07-07, Antigravity 1.107.0 vanilla, source review.
- Issue: on the `book.save()`-failed branch, run-1/run-2 read `book.last_error` (attribute)
  while run-3 calls `book.get_error()` (method) — different ORM error APIs for the same
  purpose. At most one is the real `ORM` interface; the other would raise `AttributeError`
  instead of returning a message. Neither branch is exercised by the grader (F-suite covers
  the happy path + validation 400s, never a genuine save failure), so the defect is latent
  in both variants and invisible to the 9/9 score.
- Relevance: latent-bug + inter-run inconsistency signal; a real save failure in prod would
  turn a clean 500 into an unhandled `AttributeError`. Framework is READ-ONLY — log only.
- Status: OPEN. EOD: check `tina4_python` `orm/model.py` for the true error accessor
  (`last_error` vs `get_error()`) to confirm which run(s) carry the latent crash.

AG-A-06 — AI-generated `.gitignore` protects the non-secret `.env` but not the secret `.env.local`
- Found: 2026-07-07, Antigravity 1.107.0 vanilla, all 3 runs.
- Issue: each run keeps config in `.env` (DEBUG/DB/PORT — non-secret) and the real secret in
  `.env.local` (`TINA4_SECRET`). The generated ignore rules are backwards: run-1 & run-3
  `.gitignore` list `.env` but omit `.env.local`; run-2's `.gitignore` is **empty** (ignores
  nothing). The prompt frames a standalone deliverable ("build it in the current directory"),
  so as a real repo run-1/run-3 would commit the secret and run-2 would commit secret +
  `.venv` + `data/`. In this eval only the parent repo's `.gitignore:14 .env.local` saved
  them — verified: `git check-ignore` catches all three `.env.local`, no secret is tracked
  (tracked `.env` files hold non-secret config only).
- Relevance: security-hygiene signal for the vanilla deliverable — the tool generated a
  secret and a `.gitignore` that fails to protect it. Masked here by the eval repo's rules.
- Status: OPEN.

AG-A-07 — run-3 BLOG.md asserts framework features that may not exist ("transaction safety and request-scoped query caching")
- Found: 2026-07-07, Antigravity 1.107.0 vanilla, run-3 (blog review).
- Issue: run-3's "Technical Decisions" claims the native ORM was chosen to "benefit from its
  optimized, built-in features (like transaction safety and request-scoped query caching)."
  No request-scoped query cache is known in the tina4 ORM; reads like generated marketing
  rather than a verified capability.
- Relevance: doc-fidelity — fabricated capability claim in the deliverable's own writeup.
  Low confidence until checked against framework source.
- Status: OPEN. Surface-value log; EOD: grep `tina4_python` ORM for any query-cache /
  transaction-scope to confirm or kill.
