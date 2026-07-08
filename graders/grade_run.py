#!/usr/bin/env python3
"""Grader harness for C8E-Devtool runs.

Implements the F1-F9 functional checks and I1-I6 idiom checks from
tasks/grading-checklist.md (v1, frozen 2026-07-06) against a frozen run dir.

Usage:
    python grade_run.py --run-dir ..\\antigravity\\a-vanilla\\run-1 --port 7011
    python grade_run.py --run-dir <dir> --port <port> --serve-cmd "uv run tina4 serve"

Writes results.json into the run dir. Never modifies the app under test.
The app is booted with `tina4 serve` (the real served path), not in-process.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BOOT_TIMEOUT = 30  # seconds — F1 requirement from the checklist
HTTP_TIMEOUT = 10


# ---------------------------------------------------------------- serve

class Serve:
    """Manages the `tina4 serve` subprocess for the app under test."""

    def __init__(self, run_dir: Path, cmd: str, port: int, env=None):
        self.run_dir = run_dir
        self.cmd = cmd
        self.port = port
        self.env = env  # None -> inherit parent env (default F/I behaviour)
        self.proc = None
        self.boot_log = run_dir / "grader-serve.log"

    def start(self) -> bool:
        log = open(self.boot_log, "ab")
        self.proc = subprocess.Popen(
            shlex.split(self.cmd),
            cwd=str(self.run_dir),
            stdout=log,
            stderr=subprocess.STDOUT,
            shell=False,
            env=self.env,
        )
        return wait_port(self.port, BOOT_TIMEOUT)

    def stop(self):
        if self.proc is None:
            return
        if sys.platform == "win32":
            # terminate() leaves the CLI's python child alive on Windows;
            # kill the whole tree so the port actually frees up
            subprocess.run(
                ["taskkill", "/PID", str(self.proc.pid), "/T", "/F"],
                capture_output=True,
            )
        else:
            self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.proc = None
        # give the OS a moment to release the port before a restart check
        time.sleep(2)


def wait_port(port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False


# ---------------------------------------------------------------- http

def req(method: str, url: str, body=None):
    """Returns (status, text). Never raises on HTTP error codes."""
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        r.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(r, timeout=HTTP_TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, f"<{type(e).__name__}: {e}>"


def as_json(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


def extract_books(payload):
    """Tolerance rule: list may be a raw array or wrapped one level deep
    ({"data": [...]}, {"records": [...]}, etc.). Returns first list found."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for v in payload.values():
            if isinstance(v, list):
                return v
            if isinstance(v, dict):  # {"data": {"books": [...]}}
                for v2 in v.values():
                    if isinstance(v2, list):
                        return v2
    return None


def extract_record(payload):
    """A single record may be raw or wrapped one level."""
    if isinstance(payload, dict):
        if "title" in payload:
            return payload
        for v in payload.values():
            if isinstance(v, dict) and "title" in v:
                return v
    return None


def book_in(books, title):
    return any(
        isinstance(b, dict) and b.get("title") == title for b in books or []
    )


def book_id(books, title):
    for b in books or []:
        if isinstance(b, dict) and b.get("title") == title:
            return b.get("id")
    return None


AUTH_BLOCKED = (401, 403)


def check(passed, evidence, status=None):
    result = {"pass": bool(passed), "evidence": evidence}
    if status in AUTH_BLOCKED:
        # not a plain failure: framework write-auth default may be the cause;
        # human review judges whether the agent should have handled it
        result["auth_blocked"] = True
    return result


# ---------------------------------------------------------------- functional

def functional_checks(serve: Serve, port: int, run_dir: Path) -> dict:
    f = {}
    base = f"http://127.0.0.1:{port}"
    api = f"{base}/api/books"

    booted = serve.start()
    f["F1"] = check(
        booted,
        f"port {port} {'reachable' if booted else 'not reachable'} within "
        f"{BOOT_TIMEOUT}s of `{serve.cmd}` (log: grader-serve.log)",
    )
    if not booted:
        for k in ("F2", "F3", "F4", "F5", "F6", "F7", "F8"):
            f[k] = check(False, "skipped: app never booted (F1 failed)")
        f["F9"] = f9_migration(run_dir)
        return f

    title = f"Grader Book {uuid.uuid4().hex[:8]}"

    # F3 create
    st, txt = req("POST", api, {"title": title, "author": "Grader",
                                "published_year": 2020})
    created = 200 <= st < 300
    f["F3"] = check(created, f"POST /api/books -> {st}: {txt[:200]}", st)

    # F4 list contains it
    st, txt = req("GET", api)
    books = extract_books(as_json(txt))
    listed = 200 <= st < 300 and book_in(books, title)
    f["F4"] = check(listed, f"GET /api/books -> {st}, sentinel "
                            f"{'found' if listed else 'absent'}", st)

    bid = book_id(books, title)

    # F5 fetch one
    if bid is not None:
        st, txt = req("GET", f"{api}/{bid}")
        rec = extract_record(as_json(txt))
        ok = 200 <= st < 300 and rec is not None and rec.get("title") == title
        f["F5"] = check(ok, f"GET /api/books/{bid} -> {st}", st)
    else:
        f["F5"] = check(False, "no id for sentinel record (create or list failed)")

    # F6 update — PUT first, PATCH accepted per tolerance rules
    if bid is not None:
        new_title = title + " v2"
        st, txt = req("PUT", f"{api}/{bid}", {"title": new_title,
                                              "author": "Grader",
                                              "published_year": 2021})
        if not (200 <= st < 300):
            st, txt = req("PATCH", f"{api}/{bid}", {"title": new_title})
        st2, txt2 = req("GET", f"{api}/{bid}")
        rec = extract_record(as_json(txt2))
        ok = rec is not None and rec.get("title") == new_title
        f["F6"] = check(ok, f"update -> {st}; subsequent GET shows "
                            f"{'new' if ok else 'old/missing'} title", st)
        title = new_title if ok else title
    else:
        f["F6"] = check(False, "skipped: no record id")

    # F2 page lists books (checked while a record exists)
    st, txt = req("GET", base + "/")
    ok = 200 <= st < 300 and title in txt
    f["F2"] = check(ok, f"GET / -> {st}, sentinel title "
                        f"{'present' if ok else 'absent'} in HTML", st)

    # F7 delete
    if bid is not None:
        st, _ = req("DELETE", f"{api}/{bid}")
        del_ok = st in (200, 202, 204)
        st2, txt2 = req("GET", api)
        gone = not book_in(extract_books(as_json(txt2)), title)
        f["F7"] = check(del_ok and gone,
                        f"DELETE -> {st}; sentinel "
                        f"{'gone from' if gone else 'still in'} list", st)
    else:
        f["F7"] = check(False, "skipped: no record id")

    # F8 persistence across restart
    keep = f"Grader Keep {uuid.uuid4().hex[:8]}"
    st, _ = req("POST", api, {"title": keep, "author": "Grader",
                              "published_year": 2022})
    serve.stop()
    rebooted = serve.start()
    if rebooted:
        st, txt = req("GET", api)
        ok = book_in(extract_books(as_json(txt)), keep)
        f["F8"] = check(ok, f"after restart: record "
                            f"{'survived' if ok else 'lost'}")
    else:
        f["F8"] = check(False, "app did not come back up after restart")

    f["F9"] = f9_migration(run_dir)
    return f


def f9_migration(run_dir: Path) -> dict:
    # migration artifact: framework convention is src/migrations/, but docs
    # also show top-level migrations/ — accept either
    migration_files = [
        p for d in ("src/migrations", "migrations")
        for p in (run_dir / d).glob("*")
        if p.is_file() and p.name != ".gitkeep"
    ]
    db_files = [p for pat in ("*.db", "*.sqlite", "*.sqlite3")
                for p in run_dir.rglob(pat)]
    table_ok = False
    for db in db_files:
        try:
            rows = sqlite3.connect(db).execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            if any("book" in r[0].lower() for r in rows):
                table_ok = True
                break
        except sqlite3.Error:
            continue
    # ad-hoc DDL heuristic: CREATE TABLE in python source outside migrations.
    # Vendored/env dirs are the app's dependencies, not its code — skip them.
    skip_parts = {".venv", "venv", "site-packages", ".git", "node_modules",
                  "__pycache__"}
    adhoc = []
    for p in run_dir.rglob("*.py"):
        if ("migrations" in p.parts or p.name == "grade_run.py"
                or skip_parts.intersection(p.parts)):
            continue
        try:
            if re.search(r"CREATE\s+TABLE", p.read_text(errors="replace"),
                         re.IGNORECASE):
                adhoc.append(str(p.relative_to(run_dir)))
        except OSError:
            pass
    ok = bool(migration_files) and table_ok and not adhoc
    return check(ok, f"migration files: {len(migration_files)}, "
                     f"book table in sqlite: {table_ok}, "
                     f"ad-hoc DDL in code: {adhoc or 'none'}")


# ---------------------------------------------------------------- idiom

def idiom_checks(run_dir: Path, f1_pass: bool) -> dict:
    i = {}
    route_files = [p for p in (run_dir / "src" / "routes").glob("*.py")] \
        if (run_dir / "src" / "routes").is_dir() else []
    route_src = "\n".join(p.read_text(errors="replace") for p in route_files)

    i["I1"] = check(
        bool(route_files) and bool(
            re.search(r"@?(get|post|put|patch|delete)\s*\(", route_src, re.I)),
        f"route files in src/routes/: {[p.name for p in route_files]}")

    orm_dir = run_dir / "src" / "orm"
    orm_files = [p for p in orm_dir.glob("*.py")] if orm_dir.is_dir() else []
    orm_src = "\n".join(p.read_text(errors="replace") for p in orm_files)
    i["I2"] = check(
        bool(orm_files) and "tina4" in orm_src.lower(),
        f"orm files in src/orm/: {[p.name for p in orm_files]}, "
        f"tina4 import: {'tina4' in orm_src.lower()}")

    tpl_dir = run_dir / "src" / "templates"
    tpl_files = [p for p in tpl_dir.rglob("*") if p.is_file()] \
        if tpl_dir.is_dir() else []
    inline_html = bool(re.search(r"<(html|body|table|div)\b", route_src, re.I))
    # Template-render idiom, either documented form (calibrated 2026-07-07 after
    # AG-A run 1 used the decorator form): response.render(...) OR the @template(...)
    # decorator (tina4_python.core.router.template — auto-renders a dict return via
    # response.render under the hood; router.py docstring + shipped CLAUDE.md). The
    # frozen checklist I3 asks only for "rendered via a template file (no inline HTML
    # in routes)" — both forms satisfy that; matching only "render" was too narrow.
    renders = bool(re.search(r"\.render\s*\(|@\s*template\s*\(", route_src))
    i["I3"] = check(
        bool(tpl_files) and renders and not inline_html,
        f"templates: {[p.name for p in tpl_files]}, template render "
        f"(render()/@template): {renders}, inline HTML in routes: {inline_html}")

    i["I4"] = check(
        bool(re.search(r"async\s+def\s+\w+\s*\(\s*request\s*,\s*response",
                       route_src)),
        "async (request, response) handler signature "
        + ("found" if re.search(r"async\s+def", route_src) else "not found"))

    mig = [p for d in ("src/migrations", "migrations")
           for p in (run_dir / d).glob("*")
           if p.is_file() and p.name != ".gitkeep"]
    i["I5"] = check(bool(mig),
                    f"migration artifacts: {[p.name for p in mig] or 'none'}")

    i["I6"] = check(f1_pass, "mirrors F1: app "
                    + ("starts" if f1_pass else "does not start")
                    + " via `tina4 serve` unpatched")
    return i


# ---------------------------------------------------------------- hardening (H-tier)
# ADDITIVE prod-readiness / quality tier. Grades the SAME frozen output harder;
# it never changes the frozen F1-F9 / I1-I6 scores. Checks are grounded in
# book-1-python (pulled via `tina4 books`), cited per check. Scored: H1,H2,H4,H5.

PROD_SKIP = {".venv", "venv", "logs", "__pycache__", ".git", "site-packages",
             "node_modules", ".tina4"}


def _copy_for_prod(run_dir: Path, dest: Path, port: int):
    """Copy the run to a throwaway dir and force PRODUCTION in the COPY's .env
    only — the frozen run is never mutated. Book ch34 "Deployment" (L15,L21):
    the first deployment step is `.env` for production, `TINA4_DEBUG=false`;
    ch33 (L27): debug default false, "Never set to `true` in production"."""
    def ignore(_d, names):
        return [n for n in names
                if n in PROD_SKIP or n.endswith((".pyc", ".log"))]
    shutil.copytree(run_dir, dest, ignore=ignore)
    envf = dest / ".env"
    lines, saw_debug, saw_port = [], False, False
    if envf.exists():
        for ln in envf.read_text(errors="replace").splitlines():
            u = ln.strip().upper()
            if u.startswith("TINA4_DEBUG"):
                lines.append("TINA4_DEBUG=false"); saw_debug = True
            elif u.startswith("TINA4_PORT"):
                lines.append(f"TINA4_PORT={port}"); saw_port = True
            else:
                lines.append(ln)
    if not saw_debug:
        lines.append("TINA4_DEBUG=false")
    if not saw_port:
        lines.append(f"TINA4_PORT={port}")
    envf.write_text("\n".join(lines) + "\n")


def _own_gitignore_matches(run_dir: Path, rel: str) -> bool:
    """True if `rel` (posix, relative to run_dir) is matched by the run's OWN
    .gitignore, evaluated as if the run dir were its own repo — NOT the parent
    eval repo. Pragmatic matcher (exact name, *.ext globs, dir/ prefixes)."""
    import fnmatch
    gi = run_dir / ".gitignore"
    if not gi.exists():
        return False
    name = rel.rsplit("/", 1)[-1]
    for raw in gi.read_text(errors="replace").splitlines():
        pat = raw.strip()
        if not pat or pat.startswith("#"):
            continue
        pat = pat.lstrip("/")
        if pat.endswith("/"):
            if rel == pat[:-1] or rel.startswith(pat):
                return True
        elif fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel, pat):
            return True
    return False


def h_secret_hygiene(run_dir: Path) -> dict:
    """H4 (static). Book ch33 (L447): a production deploy must "Set a real
    secret". Any file carrying TINA4_SECRET must be ignored by the run's OWN
    .gitignore, else the secret ships to git when the run is a standalone repo
    (which the task frames: "build it in the current directory")."""
    leaks = []
    for p in run_dir.rglob("*"):
        if not p.is_file() or PROD_SKIP.intersection(p.parts):
            continue
        try:
            if re.search(r"TINA4_SECRET\s*=\s*\S", p.read_text(errors="replace")):
                rel = p.relative_to(run_dir).as_posix()
                if not _own_gitignore_matches(run_dir, rel):
                    leaks.append(rel)
        except OSError:
            continue
    return check(
        not leaks,
        f"secret-bearing files NOT protected by the run's own .gitignore: "
        f"{leaks or 'none'}")


def h_cleanliness(run_dir: Path) -> dict:
    """H5 (static). Build hygiene: no nested duplicate scaffold left behind
    (a subdir carrying its own app.py + pyproject.toml, e.g. run-3's temp_init/)."""
    cruft = []
    for p in run_dir.rglob("app.py"):
        if p.parent == run_dir or PROD_SKIP.intersection(p.parts):
            continue
        if (p.parent / "pyproject.toml").exists():
            cruft.append(p.parent.relative_to(run_dir).as_posix())
    return check(not cruft, f"nested scaffold/cruft dirs: {cruft or 'none'}")


def h_error_accessor(run_dir: Path) -> dict:
    """Observation (not scored). Which ORM error accessor the save-failure branch
    uses. At most one of `.last_error` / `.get_error()` is the real API; the other
    raises AttributeError. F1-F9 never exercise a genuine save failure, so it is
    latent (AG-A-08). EOD: confirm against tina4_python/orm/model.py."""
    rd = run_dir / "src" / "routes"
    src = "\n".join(p.read_text(errors="replace") for p in rd.glob("*.py")) \
        if rd.is_dir() else ""
    used = []
    if re.search(r"\.last_error\b", src):
        used.append("last_error")
    if re.search(r"\.get_error\s*\(", src):
        used.append("get_error()")
    return {"accessor": used or ["none"],
            "note": "untested save-failure branch; >=1 accessor may raise "
                    "AttributeError in prod (AG-A-08)"}


def hardening_checks(run_dir: Path, base_port: int, serve_cmd: str) -> dict:
    """Returns {checks: {H1,H2,H4,H5}, score, observations}. One production boot
    (DEBUG=false) of a throwaway copy drives H1/H2; H4/H5 are static."""
    h = {}
    h["H4"] = h_secret_hygiene(run_dir)
    h["H5"] = h_cleanliness(run_dir)
    obs = {"error_accessor": h_error_accessor(run_dir)}

    hport = base_port + 900          # 7011 -> 7911, collision-free with the F-run
    tmp = Path(tempfile.mkdtemp(prefix="grader-prod-"))
    dest = tmp / (run_dir.name + "-prod")
    try:
        _copy_for_prod(run_dir, dest, hport)
        penv = dict(os.environ, TINA4_DEBUG="false", TINA4_PORT=str(hport))
        # `tina4 serve` alone is the DEV server (serves writes regardless of
        # DEBUG); production auth enforcement needs `--production` (CLI help +
        # `tina4 routes` banner). Book ch34 boots prod explicitly.
        prod_cmd = serve_cmd + " --production"
        pserve = Serve(dest, prod_cmd, hport, env=penv)
        booted = pserve.start()
        try:
            if not booted:
                h["H1"] = check(False, f"prod boot (DEBUG=false) not reachable on "
                                       f"{hport} — see {dest/'grader-serve.log'}")
                h["H2"] = check(False, "skipped: prod boot failed")
            else:
                api = f"http://127.0.0.1:{hport}/api/books"
                gst, _ = req("GET", api)                       # reads are public
                st, txt = req("POST", api, {"title": "H1 prod probe",
                                            "author": "H", "published_year": 2020})
                public = 200 <= st < 300
                blocked = st in AUTH_BLOCKED
                # H1 — book ch08: a public write route is @post ABOVE @noauth();
                # under prod (ch34 DEBUG=false) a mis-ordered route stays auth=required.
                h["H1"] = check(
                    public,
                    f"prod (DEBUG=false) POST no-token -> {st} [GET control -> {gst}]: "
                    + ("PUBLIC, write works in prod (correct order)" if public
                       else "AUTH-REQUIRED, would 401 in prod (AG-A-01)" if blocked
                       else f"unexpected: {txt[:120]}"),
                    st)
                obs["prod_write_status"] = st
                # H2 — book ch03 §4 (L477/L503): missing resource -> 404.
                nst, _ = req("GET", f"{api}/999999999")
                h["H2"] = check(
                    nst == 404,
                    f"prod GET /api/books/999999999 -> {nst} "
                    f"({'404 as book ch03 prescribes' if nst == 404 else 'not 404'})",
                    nst)
                # observation: malformed-body handling, only reachable if writes public
                if public:
                    mst, _ = req("POST", api, {"title": "x"})  # missing author/year
                    obs["malformed_post_status"] = mst
                    obs["malformed_gives_400"] = (mst == 400)
                else:
                    obs["malformed_post_status"] = \
                        "not observable (writes auth-blocked in prod)"
        finally:
            pserve.stop()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    score = sum(1 for v in h.values() if v["pass"])
    return {"checks": h, "score": f"{score}/{len(h)}", "observations": obs}


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--serve-cmd", default="tina4 serve",
                    help="override boot command, e.g. 'uv run tina4 serve'")
    ap.add_argument("--static-only", action="store_true",
                    help="skip serve + F-checks; run I-checks only")
    ap.add_argument("--skip-hardening", action="store_true",
                    help="skip the additive H-tier (prod-readiness / hygiene)")
    ap.add_argument("--hardening-only", action="store_true",
                    help="compute ONLY the H-tier and merge into existing "
                         "results.json, preserving the frozen F/I scores")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.is_dir():
        sys.exit(f"run dir not found: {run_dir}")

    out = run_dir / "results.json"

    if args.hardening_only:
        results = json.loads(out.read_text()) if out.exists() else {}
        hardening = hardening_checks(run_dir, args.port, args.serve_cmd)
        results["hardening"] = hardening["checks"]
        results["hardening_score"] = hardening["score"]
        results["hardening_observations"] = hardening["observations"]
        out.write_text(json.dumps(results, indent=2))
        print(json.dumps(
            {"hardening_score": hardening["score"],
             "hardening": {k: v["pass"] for k, v in hardening["checks"].items()},
             "observations": hardening["observations"],
             "results": str(out)}, indent=2))
        return

    serve = Serve(run_dir, args.serve_cmd, args.port)
    try:
        if args.static_only:
            functional = {k: check(False, "static-only mode")
                          for k in [f"F{n}" for n in range(1, 10)]}
        else:
            functional = functional_checks(serve, args.port, run_dir)
    finally:
        serve.stop()

    idiom = idiom_checks(run_dir, functional["F1"]["pass"])

    f_score = sum(1 for v in functional.values() if v["pass"])
    i_score = sum(1 for v in idiom.values() if v["pass"])
    results = {
        "checklist_version": "v1 (frozen 2026-07-06)",
        "run_dir": str(run_dir),
        "port": args.port,
        "serve_cmd": args.serve_cmd,
        "functional": functional,
        "functional_score": f"{f_score}/9",
        "idiom": idiom,
        "idiom_score": f"{i_score}/6",
        "auth_blocked_checks": [k for k, v in functional.items()
                                if v.get("auth_blocked")],
    }

    if not (args.static_only or args.skip_hardening):
        hardening = hardening_checks(run_dir, args.port, args.serve_cmd)
        results["hardening"] = hardening["checks"]
        results["hardening_score"] = hardening["score"]
        results["hardening_observations"] = hardening["observations"]

    out.write_text(json.dumps(results, indent=2))
    summary = {"functional_score": results["functional_score"],
               "idiom_score": results["idiom_score"],
               "auth_blocked": results["auth_blocked_checks"],
               "results": str(out)}
    if "hardening_score" in results:
        summary["hardening_score"] = results["hardening_score"]
        summary["hardening"] = {k: v["pass"]
                                for k, v in results["hardening"].items()}
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
