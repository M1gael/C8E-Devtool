# Run Protocol (v1 — FROZEN 2026-07-06)

How a single run is executed. Deviating from this protocol invalidates the run
(mark it ⛔ in the progress table with the reason; start a fresh run dir).

## Port table

| Workspace | App port |
|-----------|----------|
| hub | 7000 |
| antigravity/a-vanilla/run-1..3 | 7011, 7012, 7013 |
| antigravity/b-devkit/run-1..3 | 7021, 7022, 7023 |
| antigravity/c-mcp/run-1..3 | 7031, 7032, 7033 |

Future tools get their own decade blocks (7041+).

## Config sequencing (one-way — do not interleave)

Extensions and MCP settings are IDE-global; headless uninstall is unverified.

1. All three **A — vanilla** runs complete and are graded first.
2. Then the devkit is applied → all three **B** runs.
3. Then the MCP is connected → all three **C** runs.

Before each config phase: snapshot tool state (extension list, settings, `~/.gemini`)
into `baselines/`.

## Agent settings (pinned per tool evaluation)

Model and mode are fixed for all nine runs of a tool — changing them mid-evaluation
confounds the config comparison and invalidates cross-config deltas.

Antigravity v1.107.0: **Turbo mode, out-of-box settings, Gemini Flash 3.5, medium**.
Recorded in each run's `run.json` (`model`, `mode` fields).

## Per-run steps

1. **Workspace**: open the IDE with the run's empty `run-N/` directory as the
   project root. The dir must contain nothing but `.gitkeep` (config B: plus the
   devkit-deployed `AGENTS.md` / `.agents/` / `.vscode/`, deployed via
   `-TargetRepo` before the run).
   - **Isolation**: run `git init` inside `run-N/` before opening the IDE. This
     stops git's upward directory walk at the run dir, so the agent cannot
     discover the parent C8E-Devtool repo (and the grading rubric in `tasks/`)
     via `git status`/`git log`. Never open the C8E-Devtool root in the tested
     IDE. An agent reading outside its project root anyway is observable and is
     logged as a finding.
2. **Prompt**: paste the frozen query spec prompt verbatim, `{PORT}` filled from
   the port table. Nothing else.
3. **Hands off**: zero human input until the agent declares done. Agent may
   self-iterate, run code, read errors — that is tool capability. If it asks a
   question, the answer is always: "Proceed with your best judgment." (record that
   this happened). Note start/end time.
4. **Freeze**: when the agent declares done, stop. Commit nothing, edit nothing.
   Delete `run-N/.git` (the isolation repo from step 1) so the parent repo can
   version the frozen output as plain files. Write `run.json` in the run dir:
   date, tool + version, config, port, wall time, turns, self-tested (yes/no),
   notes.
5. **Grade**: run the grader harness against the frozen output. Results land in
   `run-N/results.json`. Blog audit follows.
6. **Log**: update the progress table in `findings-log.md`; log findings with the
   run's ID (e.g. `AG-A-01`).
7. **Correction pass** (after grading only): apply minimal edits to reach all-green
   F-checks, counting files/lines — recorded as correction cost. Work happens on a
   copy (`run-N-corrected/`), never in the frozen run dir.

## Invalidation examples

- Human typed anything beyond the prompt + "Proceed with your best judgment"
- Run dir was not clean at start
- Prompt text edited beyond the `{PORT}` substitution
- Grader run against a modified (non-frozen) output
