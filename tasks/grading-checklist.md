# Grading Checklist (v1 — FROZEN 2026-07-06)

Frozen before the first config-A run. The grader harness in `graders/` implements the
F-checks; I-checks are static inspections of the generated tree; B-checks are the
blog claims audit. Every run of every config is scored against this exact list.

## Functional checks (scripted — grader harness)

Each check is pass/fail. Functional score = passed / 9.

| # | Check |
|---|-------|
| F1 | App boots under `tina4 serve` on the assigned port within 30 s |
| F2 | `GET /` returns 200 and the HTML contains the book listing |
| F3 | `POST /api/books` creates a record (2xx, record subsequently retrievable) |
| F4 | `GET /api/books` returns JSON containing the created record |
| F5 | `GET /api/books/{id}` returns that record |
| F6 | `PUT /api/books/{id}` updates a field (change visible on subsequent GET) |
| F7 | `DELETE /api/books/{id}` removes it (absent from list; direct GET fails) |
| F8 | Data survives an app restart (stop serve, start serve, records still present) |
| F9 | Migration applied for real: the table exists in the SQLite file and was created via the framework's migration mechanism, not ad-hoc DDL at boot |

### Tolerance rules

The grader tests semantics, not envelope shape:

- JSON list may be a raw array or wrapped (`{"data": [...]}` etc.).
- 200 and 201 both accepted for create; 200/202/204 for update/delete.
- `PATCH` accepted where `PUT` was asked, if update semantics work.
- Trailing-slash variants accepted.
- Anything outside these tolerances that still "works" by hand = grader bug; fix
  grader, re-run scoring (grader fixes are allowed — it is harness, not subject).

## Idiom checks (static — tree inspection)

Each check is yes/no. Idiom score = yes / 6.

| # | Check |
|---|-------|
| I1 | Routes defined in `src/routes/*.py` (drop-in routing) |
| I2 | ORM model in `src/orm/`, using the tina4 ORM base class |
| I3 | Page rendered via a template file in `src/templates/` (no inline HTML strings in routes) |
| I4 | Route handlers are `async (request, response)` per framework convention |
| I5 | Table created through the framework's migrations mechanism (migration artifact present) |
| I6 | App starts via `tina4 serve` with no manual patching needed |

## Blog audit (manual — assisted)

| # | Check |
|---|-------|
| B1 | BLOG.md exists in project root |
| B2 | Every factual claim extracted and mapped against code + grader results: true / false / unverifiable |
| B3 | Self-report accuracy = true / (true + false). Fabricated claims additionally logged as findings |

Process: claims extracted and pre-verified by the harness side; user spot-checks
verdicts. Config A blogs are expected to show generic reasoning; B/C blogs showing
Tina4-specific reasoning is direct evidence the assist layer entered the agent's
thinking — note it either way.

## Correction cost (recorded, not scored)

Number of files touched and lines changed to bring all F-checks green, starting from
the frozen first output. Measures distance-from-working. Recorded per run for
cross-config comparison.

## Secondary metrics (recorded per run)

- Wall-clock time from prompt paste to agent's done-declaration
- Agent turns / self-iterations
- Whether the agent ran/tested its own code before declaring done
- Files created (count + tree)
- Tool version, config, date (in the run's `run.json`)
