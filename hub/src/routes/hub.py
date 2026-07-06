"""C8E-Devtool hub — browse and drive generated run apps from one page.

Local tooling only (localhost). Control routes use @noauth() deliberately:
this hub is not a subject under test, it is the operator's console.
"""
from tina4_python.core.router import get, post, noauth

from src.app import runs


@get("/")
async def dashboard(request, response):
    all_runs = runs.discover("antigravity")
    # ordered list of {label, runs} — avoids relying on dict.items() in Frond
    groups = []
    for r in all_runs:
        if not groups or groups[-1]["label"] != r["config_label"]:
            groups.append({"label": r["config_label"], "runs": []})
        groups[-1]["runs"].append(r)
    summary = {
        "total": len(all_runs),
        "with_code": sum(1 for r in all_runs if r["has_code"]),
        "graded": sum(1 for r in all_runs if r["results"]),
        "running": sum(1 for r in all_runs if r["running"]),
    }
    return response.render("hub.twig", {
        "groups": groups,
        "summary": summary,
        "hub_port": runs.HUB_PORT,
    })


@get("/api/runs")
async def api_runs(request, response):
    return response({"runs": runs.discover("antigravity")})


@noauth()
@post("/api/start/{config}/{run_n:int}")
async def api_start(config, run_n, request, response):
    return response(runs.start(config, run_n))


@noauth()
@post("/api/stop/{config}/{run_n:int}")
async def api_stop(config, run_n, request, response):
    return response(runs.stop(config, run_n))


@get("/log/{config}/{run_n:int}")
async def serve_log(config, run_n, request, response):
    run_dir = runs.REPO_ROOT / "antigravity" / config / f"run-{run_n}"
    for name in ("grader-serve.log", "hub-serve.log"):
        f = run_dir / name
        if f.is_file():
            text = f.read_text(errors="replace")[-20000:]
            return response(f"<pre>{text}</pre>")
    return response("no log for this run", 404)
