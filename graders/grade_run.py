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
import re
import shlex
import socket
import sqlite3
import subprocess
import sys
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

    def __init__(self, run_dir: Path, cmd: str, port: int):
        self.run_dir = run_dir
        self.cmd = cmd
        self.port = port
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
    i["I3"] = check(
        bool(tpl_files) and "render" in route_src and not inline_html,
        f"templates: {[p.name for p in tpl_files]}, render() used: "
        f"{'render' in route_src}, inline HTML in routes: {inline_html}")

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


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--port", type=int, required=True)
    ap.add_argument("--serve-cmd", default="tina4 serve",
                    help="override boot command, e.g. 'uv run tina4 serve'")
    ap.add_argument("--static-only", action="store_true",
                    help="skip serve + F-checks; run I-checks only")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.is_dir():
        sys.exit(f"run dir not found: {run_dir}")

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

    out = run_dir / "results.json"
    out.write_text(json.dumps(results, indent=2))
    print(json.dumps({"functional_score": results["functional_score"],
                      "idiom_score": results["idiom_score"],
                      "auth_blocked": results["auth_blocked_checks"],
                      "results": str(out)}, indent=2))


if __name__ == "__main__":
    main()
