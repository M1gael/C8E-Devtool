# Hub

Operator console for the eval — one page to browse every run, drive its app, and
read its grader result. A tina4-python app itself (dogfooding), served on port 7000.

## Start

```powershell
cd hub
uv run tina4 serve --no-browser     # first run: uv venv; uv pip install tina4-python
```

Open http://localhost:7000.

## What it shows

- Every `antigravity/<config>/run-N` discovered in protocol order, grouped by config.
- Per run: a status chip (running / stopped / empty), `code` / `blog` chips, and the
  grader scores (`F x/9`, `I x/6`) with a per-check pass/fail grid (F1–F9, I1–I6) read
  live from that run's `results.json`. `auth-blocked` checks are flagged amber.
- **Start / Stop** buttons launch or kill the run's app on its assigned port
  (`701N`/`702N`/`703N`, matching `tasks/run-protocol.md`). Start is disabled until a
  run has code.
- When a run is up: **Open**, **page ↗**, **/api/books ↗**, **swagger ↗** links go
  straight into the live app so you can click through it by hand. **grader log** shows
  the captured serve output.

Both the operator (browser) and the grader hit the same served instances on the same
ports, so what you click through by hand is exactly what got scored.

## Notes

- The hub launches each app with `PORT` injected and `TINA4_OVERRIDE_CLIENT=true`; a
  generated app that ignores `PORT` and binds elsewhere is itself an F1/idiom finding.
- Port state is probed concurrently, so a page load is ~300 ms even with all 9 runs
  checked. The process registry is in-memory (hub lifetime) — Stop only tracks apps
  this hub started; an app started elsewhere still shows as running (port-based) but
  must be stopped where it was launched.
- Runs with `TINA4_DEBUG=true` also open an agent server (~90NN) and a stable test
  port (~80NN); these are outside the 70xx eval range and don't collide.
