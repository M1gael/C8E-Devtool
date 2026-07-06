# Graders

Harness that scores a frozen run against `tasks/grading-checklist.md` (v1).

## grade_run.py

Stdlib-only Python (no pip installs needed for the grader itself).

```powershell
python grade_run.py --run-dir ..\antigravity\a-vanilla\run-1 --port 7011
```

- Boots the app with `tina4 serve` (real served path, never in-process),
  runs F1–F9 over HTTP + SQLite inspection, restarts the app for the F8
  persistence check, then runs the I1–I6 static tree checks.
- Writes `results.json` into the run dir; serve output goes to
  `run-N/grader-serve.log`. The app under test is never modified.
- `--serve-cmd` overrides the boot command when the generated app needs its
  own environment (e.g. `--serve-cmd "uv run tina4 serve"`).
- `--static-only` runs just the I-checks (for apps that cannot boot).

## Environment notes

- The run's app may bring its own venv/requirements; the grader does not
  install anything. If the app needs deps, prepare its env first exactly as
  its own README/BLOG says (that instruction quality is itself part of the
  evaluation), then grade with the matching `--serve-cmd`.
- `tina4 serve` may auto-open a browser tab per boot (CLI behavior). Harmless
  to grading; close it.

## Auth policy

Tina4 requires auth on POST/PUT/PATCH/DELETE by default. The grader calls the
API unauthenticated, like the naive client the spec implies. Checks that fail
with 401/403 are marked `auth_blocked: true` in `results.json` — scored as
fails, but flagged separately so human review can judge whether the agent
should have made the API public (`@noauth`) or documented the auth story.
Whether an assist layer teaches the agent to handle this is itself a signal.

## Calibration (required before results count)

The grader must first score a known-good reference implementation:

1. Build `graders/reference-app/` strictly from the tina4-python docs — a
   correct implementation of the frozen query spec.
2. Grade it. Required outcome: **9/9 functional, 6/6 idiom.**
3. Any shortfall = grader bug or tolerance gap → fix grader, re-calibrate.

Grader fixes are always allowed (it is harness, not subject), including after
real runs — re-score all affected runs when that happens.

## B-checks and correction cost

Blog claims audit (B1–B3) and the correction-cost pass are not automated in
v1 — done manually per `tasks/grading-checklist.md`, results recorded in the
run's `run.json` / findings log.
