"""Run discovery + subprocess lifecycle for the C8E-Devtool hub.

Port map mirrors tasks/run-protocol.md (the frozen source of truth):
  hub                       7000
  <tool>/a-vanilla/run-N    701N
  <tool>/b-devkit/run-N     702N
  <tool>/c-mcp/run-N        703N
Future tools get their own decade block; keep this in sync with the protocol.
"""
import json
import socket
import subprocess
import sys
import shlex
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# hub/src/app/runs.py  ->  parents[3] == repo root (C8E-Devtool)
REPO_ROOT = Path(__file__).resolve().parents[3]
HUB_PORT = 7000

# config dir name -> port decade offset from 7000
CONFIG_DECADE = {"a-vanilla": 10, "b-devkit": 20, "c-mcp": 30}
CONFIG_LABEL = {"a-vanilla": "A — vanilla",
                "b-devkit": "B — + devkit",
                "c-mcp": "C — + MCP"}

DEFAULT_SERVE = "uv run tina4 serve --no-browser"

# in-memory registry: port -> Popen (hub-process lifetime only)
_procs: dict[int, subprocess.Popen] = {}


def port_for(config: str, run_n: int) -> int | None:
    dec = CONFIG_DECADE.get(config)
    return None if dec is None else HUB_PORT + dec + run_n


def is_listening(port: int) -> bool:
    # connect_ex on a closed localhost port returns immediately on refusal;
    # the short timeout only bounds the rare no-response case. A closed port
    # must never cost the full timeout (that serialised to ~4.5s over 9 ports).
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.25)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    except OSError:
        return False
    finally:
        s.close()


def _has_code(run_dir: Path) -> bool:
    if (run_dir / "app.py").is_file():
        return True
    routes = run_dir / "src" / "routes"
    if routes.is_dir() and any(routes.glob("*.py")):
        return True
    # any python file that isn't the grader's own artifacts
    return any(p.name != "grade_run.py" for p in run_dir.glob("*.py"))


def _results_summary(run_dir: Path) -> dict | None:
    # v2 grader (grade_lend.py) takes precedence when both artifacts exist
    v2 = run_dir / "results-v2.json"
    if v2.is_file():
        try:
            data = json.loads(v2.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {"kind": "v2", "error": "unreadable results-v2.json"}
        checks = data.get("checks") or {}
        tiers: dict[str, list[int]] = {}
        for cid, c in checks.items():
            if c.get("ok") is None:  # skipped checks don't count
                continue
            t = tiers.setdefault(cid[0], [0, 0])
            t[1] += 1
            t[0] += c.get("ok") is True
        return {
            "kind": "v2",
            "score": data.get("score"),
            "task": (data.get("meta") or {}).get("task", ""),
            "tiers": [{"tier": k, "score": f"{p}/{n}"}
                      for k, (p, n) in sorted(tiers.items())],
            "checks": [{"id": cid, "ok": c.get("ok"),
                        "label": f"{cid} {c.get('title', '')} — {c.get('note', '') or 'ok'}"}
                       for cid, c in checks.items()],
        }
    rf = run_dir / "results.json"
    if not rf.is_file():
        return None
    try:
        data = json.loads(rf.read_text())
    except (ValueError, OSError):
        return {"kind": "v1", "error": "unreadable results.json"}
    return {
        "kind": "v1",
        "functional_score": data.get("functional_score"),
        "idiom_score": data.get("idiom_score"),
        "auth_blocked": data.get("auth_blocked_checks", []),
        "functional": {k: v.get("pass") for k, v in
                       (data.get("functional") or {}).items()},
        "idiom": {k: v.get("pass") for k, v in
                  (data.get("idiom") or {}).items()},
    }


def discover(tool: str = "antigravity") -> list[dict]:
    """Return one dict per run-N dir under <tool>/<config>/, protocol order."""
    tool_dir = REPO_ROOT / tool
    runs = []
    for config in ("a-vanilla", "b-devkit", "c-mcp"):
        cfg_dir = tool_dir / config
        if not cfg_dir.is_dir():
            continue
        for run_dir in sorted(cfg_dir.glob("run-*")):
            try:
                run_n = int(run_dir.name.split("-")[1])
            except (IndexError, ValueError):
                continue
            port = port_for(config, run_n)
            runs.append({
                "tool": tool,
                "config": config,
                "config_label": CONFIG_LABEL.get(config, config),
                "run": run_n,
                "name": f"{config}/run-{run_n}",
                "port": port,
                "path": str(run_dir),
                "has_code": _has_code(run_dir),
                "has_blog": (run_dir / "BLOG.md").is_file(),
                "has_serve_log": (run_dir / "grader-serve.log").is_file(),
                "results": _results_summary(run_dir),
            })
    # probe all ports concurrently so a page load isn't serial socket waits
    with ThreadPoolExecutor(max_workers=len(runs) or 1) as pool:
        states = pool.map(
            lambda r: is_listening(r["port"]) if r["port"] else False, runs)
    for r, up in zip(runs, states):
        r["running"] = up
    return runs


def start(config: str, run_n: int, serve_cmd: str = DEFAULT_SERVE) -> dict:
    port = port_for(config, run_n)
    if port is None:
        return {"ok": False, "error": f"unknown config {config}"}
    run_dir = REPO_ROOT / "antigravity" / config / f"run-{run_n}"
    if not run_dir.is_dir():
        return {"ok": False, "error": "run dir missing"}
    if not _has_code(run_dir):
        return {"ok": False, "error": "no app in run dir yet"}
    if is_listening(port):
        return {"ok": True, "port": port, "note": "already up"}
    # inject the assigned port; the generated app should honour PORT (F1)
    import os
    env = dict(os.environ, PORT=str(port), TINA4_PORT=str(port),
               TINA4_OVERRIDE_CLIENT="true")
    log = open(run_dir / "hub-serve.log", "ab")
    proc = subprocess.Popen(shlex.split(serve_cmd), cwd=str(run_dir),
                            stdout=log, stderr=subprocess.STDOUT, env=env)
    _procs[port] = proc
    return {"ok": True, "port": port, "pid": proc.pid}


def stop(config: str, run_n: int) -> dict:
    port = port_for(config, run_n)
    if port is None:
        return {"ok": False, "error": f"unknown config {config}"}
    proc = _procs.pop(port, None)
    if proc is not None and sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True)
    elif proc is not None:
        proc.terminate()
    return {"ok": True, "port": port, "stopped": proc is not None}
