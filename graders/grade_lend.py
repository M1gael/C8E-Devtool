"""
grade_lend.py — grader for task spec v2.1 ("Lend", tasks/query-spec-v2.md).

Scores one run directory in three tiers:
  F-tier  live functional checks over `tina4 serve` (the spec's product requirements)
  P-tier  production posture over `tina4 serve --production` + TINA4_DEBUG=false
  T-tier  the run's own test suite via `tina4 test` (book ch18: pytest over tests/)
  S-tier  static idiom checks on the untouched run dir

Every check carries the exact spec sentence it verifies (traceability rule).
Book grounding: swagger UI at /swagger, spec at /swagger/json (book ch20);
`tina4 test` auto-discovers tests/ and runs pytest (book ch18).

The run dir is grave-goods: grading happens on a fresh COPY (data/ wiped so
migrations+seeds rebuild deterministically). The only write into the real run
dir is results-v2.json.

Usage:
  python grade_lend.py <run_dir> --port 7511 [--keep] [--skip-tests]
"""

import argparse
import fnmatch
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from grade_run import Serve  # frozen v1 grader; reuse the process manager only

HTTP_TIMEOUT = 15
COPY_EXCLUDE = {".venv", "venv", "__pycache__", ".git", "node_modules",
                ".tina4-docs", ".pytest_cache", "logs"}

# ---------------------------------------------------------------- adapters

# Per-run endpoint maps. Discovered by reading each run's src/routes (2026-07-08);
# the SPEC never fixed an API shape, so each run legitimately chose its own.
ADAPTERS = {
    "run-1": {
        "login": ("/api/auth/login", {"username": "admin", "password": "staffpassword"}),
        "books": "/api/books",
        "book": "/api/books/{id}",
        "members": "/api/members",
        "loans": "/api/loans",
        "loan_return": lambda loan_id, book_id: ("/api/loans/%s/return" % loan_id, {}),
        "audit": "/api/audit-logs",
        "search_param": "q", "page_param": "page", "limit_param": "limit",
        "loan_body": lambda bid, mid: {"book_id": bid, "member_id": mid, "due_date": "2026-08-01"},
        "lang_setup": "/language/es", "lang_page": "/", "locale_file": "src/locales/es.json",
        "mail_globs": ["data/mailbox/**/*", "data/queue/**/*"],
        "staff_names": ["Library Admin", "admin"],
    },
    "run-2": {
        "login": ("/api/staff/login", {"email": "staff@library.com", "password": "password123"}),
        "books": "/api/books",
        "book": "/api/books/{id}",
        "members": "/api/members",
        "loans": "/api/loans",
        "loan_return": lambda loan_id, book_id: ("/api/loans/return", {"book_id": book_id}),
        "audit": "/api/audit-logs",
        "search_param": "q", "page_param": "page", "limit_param": "limit",
        "loan_body": lambda bid, mid: {"book_id": bid, "member_id": mid},
        "lang_setup": None, "lang_page": "/?lang=de", "locale_file": "src/locales/de.json",
        "mail_globs": ["data/queue/**/*", "data/mailbox/**/*"],
        "staff_names": ["Librarian", "staff@library.com"],
    },
    # run-3 (3rd attempt, built 2026-07-09 under guard.py isolation). Discovered by
    # reading src/routes: public reads live on /api/catalogue, staff writes on
    # /api/books — first run to split them, hence the books_read key (read-site
    # fallback added for it; other runs unaffected). Creds seeded by migration,
    # documented in its BLOG.md. Lang switch is a ?lang= query param + session.
    "run-3": {
        "login": ("/api/auth/login", {"email": "staff@library.com", "password": "password123"}),
        "books": "/api/books",
        "books_read": "/api/catalogue",
        "book": "/api/books/{id}",
        "members": "/api/members",
        "loans": "/api/loans",
        "loan_return": lambda loan_id, book_id: ("/api/loans/%s/return" % loan_id, {}),
        "audit": "/api/audit-logs",
        "search_param": "q", "page_param": "page", "limit_param": "limit",
        "loan_body": lambda bid, mid: {"book_id": bid, "member_id": mid, "due_date": "2026-08-01"},
        "lang_setup": None, "lang_page": "/?lang=es", "locale_file": "src/locales/es.json",
        "mail_globs": ["data/queue/**/*", "data/mailbox/**/*"],
        "staff_names": ["Library Staff", "staff@library.com"],
    },
}

# ---------------------------------------------------------------- helpers

_cookie_opener = None  # only F16 uses cookies; auth checks must stay cookie-free


def req2(method, url, body=None, token=None, raw=None, ctype=None, cookies=False):
    """(status, text). Adds Bearer auth + optional raw (multipart) bodies."""
    global _cookie_opener
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(url, data=data, method=method)
    if token:
        r.add_header("Authorization", "Bearer " + token)
    if data is not None:
        r.add_header("Content-Type", ctype or "application/json")
    if cookies:
        if _cookie_opener is None:
            import http.cookiejar
            _cookie_opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        opener = _cookie_opener.open
    else:
        opener = urllib.request.urlopen
    try:
        with opener(r, timeout=HTTP_TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, "<%s: %s>" % (type(e).__name__, e)


def jload(text):
    try:
        return json.loads(text)
    except Exception:
        return None


def find_id(obj):
    """Dig a record id out of whatever JSON shape the run returns."""
    if isinstance(obj, dict):
        for k in ("id", "book_id", "loan_id", "member_id"):
            if k in obj and isinstance(obj[k], int):
                return obj[k]
        for v in obj.values():
            got = find_id(v)
            if got is not None:
                return got
    if isinstance(obj, list) and obj:
        return find_id(obj[-1])
    return None


def multipart(fields, filefield, filename, blob):
    """Minimal multipart/form-data encoder."""
    bnd = uuid.uuid4().hex
    out = b""
    for k, v in fields.items():
        out += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                % (bnd, k, v)).encode()
    out += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"; filename=\"%s\"\r\n"
            "Content-Type: %s\r\n\r\n"
            % (bnd, filefield, filename,
               mimetypes.guess_type(filename)[0] or "application/octet-stream")).encode()
    out += blob + ("\r\n--%s--\r\n" % bnd).encode()
    return out, "multipart/form-data; boundary=" + bnd


def copy_run(run_dir: Path, dest: Path, port: int):
    """Fresh grading copy: code+config only, data/ wiped, port forced."""
    def ignore(d, names):
        return [n for n in names if n in COPY_EXCLUDE]
    shutil.copytree(run_dir, dest, ignore=ignore)
    if (dest / "data").exists():
        shutil.rmtree(dest / "data", ignore_errors=True)
    (dest / "data").mkdir(exist_ok=True)
    (dest / "logs").mkdir(exist_ok=True)
    env_file = dest / ".env"
    lines = env_file.read_text().splitlines() if env_file.exists() else []
    lines = [l for l in lines if not l.startswith("TINA4_PORT")]
    lines.append("TINA4_PORT=%d" % port)
    env_file.write_text("\n".join(lines) + "\n")


def set_env_flag(dest: Path, key: str, value: str):
    env_file = dest / ".env"
    lines = env_file.read_text().splitlines() if env_file.exists() else []
    lines = [l for l in lines if not l.startswith(key + "=")]
    lines.append("%s=%s" % (key, value))
    env_file.write_text("\n".join(lines) + "\n")


def snapshot_files(dest: Path, globs):
    seen = set()
    for g in globs:
        for p in dest.glob(g):
            if p.is_file():
                seen.add(str(p.relative_to(dest)))
    return seen

# ---------------------------------------------------------------- grader

class Grader:
    def __init__(self, run_dir, adapter, port, keep, skip_tests):
        self.run_dir = run_dir
        self.a = adapter
        self.port = port
        self.base = "http://127.0.0.1:%d" % port
        self.keep = keep
        self.skip_tests = skip_tests
        self.results = {}
        self.token = None
        self.book_id = None      # the book we create + track through the flow
        self.member_id = None
        self.loan_id = None

    def check(self, cid, title, quote, fn):
        try:
            ok, note = fn()
        except Exception as e:
            ok, note = False, "grader exception: %s: %s" % (type(e).__name__, e)
        self.results[cid] = {"ok": bool(ok), "title": title, "note": note, "spec": quote}
        print("  %-4s %s %-38s %s" % (cid, "PASS" if ok else "FAIL", title, ("- " + note) if note else ""))
        return ok

    def url(self, path):
        return self.base + path

    # ---------------- F-tier ----------------
    def run_functional(self, dest):
        a = self.a
        print("F-tier (dev server, fresh copy):")
        srv = Serve(dest, "uv run tina4 serve", self.port,
                    env=dict(os.environ, TINA4_PORT=str(self.port)))
        booted = self.check("F1", "boots under tina4 serve",
                            "It must run under `tina4 serve` on port {PORT}.",
                            lambda: (srv.start(), ""))
        if not booted:
            srv.stop()
            return srv, False

        def f2():
            st, tx = req2("GET", self.url("/"))
            return st == 200 and "<" in tx, "status %s" % st
        self.check("F2", "website serves a home page",
                   "Lend must work both as a website and as a JSON API.", f2)

        # read-site endpoint: runs may split public reads from staff writes
        # (run-3: GET /api/catalogue vs POST /api/books); default = same path
        books_read = a.get("books_read", a["books"])

        def f3():
            st, tx = req2("GET", self.url(books_read))
            j = jload(tx)
            return st == 200 and j is not None, "status %s" % st
        self.check("F3", "public JSON catalogue, no auth",
                   "The public can browse and search the catalogue.", f3)

        def f5():
            # fully VALID payload: the refusal must be attributable to auth, not validation
            st, tx = req2("POST", self.url(a["books"]),
                          {"title": "NoAuth Probe", "author": "X Author",
                           "published_year": 2020, "isbn": "978-0-00-000009-9", "cover_image": ""})
            return 400 <= st < 500, "status %s (2xx here = unauthenticated write accepted)" % st
        self.check("F5", "unauthenticated write refused",
                   "Anyone who is not signed in must be refused from those actions — "
                   "not merely hidden in the interface, but actually refused by the API.", f5)

        def f4():
            # seeds may land asynchronously after the port answers (run-2 seeds on the
            # app.ready event) — retry up to 15s; a genuinely broken login still fails
            path, creds = a["login"]
            deadline, st, tries = time.time() + 15, 0, 0
            while time.time() < deadline:
                tries += 1
                st, tx = req2("POST", self.url(path), creds)
                self.token = (jload(tx) or {}).get("token")
                if st == 200 and self.token:
                    return True, "status 200 (attempt %d)" % tries
                time.sleep(1)
            return False, "status %s after %d attempts over 15s, token MISSING" % (st, tries)
        self.check("F4", "staff login with seeded creds",
                   "Staff must sign in before they can add, edit, or remove books or members.", f4)

        def f6():
            st, tx = req2("POST", self.url(a["books"]),
                          {"title": "GRADERBOOK-Alpha Zebra", "author": "Ada Marple",
                           "published_year": 1984, "isbn": "978-0-11-111111-1", "cover_image": ""},
                          token=self.token)
            self.book_id = find_id(jload(tx))
            if not (200 <= st < 300 and self.book_id):
                return False, "status %s id %s" % (st, self.book_id)
            st2, tx2 = req2("GET", self.url(a["book"].format(id=self.book_id)))
            return st2 == 200 and "GRADERBOOK-Alpha Zebra" in tx2, "created id %s, detail %s" % (self.book_id, st2)
        self.check("F6", "authenticated create persists + is retrievable",
                   "Staff must sign in before they can add, edit, or remove books.", f6)

        def f7():
            if not self.token:
                return False, "blocked: no staff token (F4 failed)"
            st, tx = req2("POST", self.url(a["books"]), {}, token=self.token)
            j = jload(tx)
            # 401/403 would mean auth refusal, not input validation
            return (400 <= st < 500 and st not in (401, 403)) and j is not None, \
                "status %s (needs non-auth 4xx + JSON error body)" % st
        self.check("F7", "invalid input rejected clearly (not 5xx, not 2xx)",
                   "Incomplete or invalid input is rejected with clear, correct error responses.", f7)

        def f8():
            req2("POST", self.url(a["books"]),
                 {"title": "GRADERBOOK-Quiet Garden", "author": "Boris Yellnikov",
                  "published_year": 2001, "isbn": "978-0-22-222222-2", "cover_image": ""},
                 token=self.token)
            st, tx = req2("GET", self.url(books_read) + "?%s=Zebra" % a["search_param"])
            hit_title = "GRADERBOOK-Alpha Zebra" in tx and "Quiet Garden" not in tx
            st2, tx2 = req2("GET", self.url(books_read) + "?%s=Yellnikov" % a["search_param"])
            hit_author = "GRADERBOOK-Quiet Garden" in tx2
            st3, tx3 = req2("GET", self.url(books_read) + "?%s=1984" % a["search_param"])
            hit_year = "GRADERBOOK-Alpha Zebra" in tx3
            note = "title:%s author:%s year:%s" % (hit_title, hit_author, hit_year)
            return hit_title and hit_author and hit_year, note
        self.check("F8", "search by title, author, year",
                   "Browse and search the catalogue by title, author, or year.", f8)

        def f9():
            for i in range(25):
                req2("POST", self.url(a["books"]),
                     {"title": "GRADERBOOK-Bulk %03d" % i, "author": "Bulk Writer",
                      "published_year": 1990, "isbn": "978-1-00-%06d-0" % i, "cover_image": ""},
                     token=self.token)
            q = "?%s=Bulk&%s=10&%s=" % (a["search_param"], a["limit_param"], a["page_param"])
            st1, p1 = req2("GET", self.url(books_read) + q + "1")
            st2, p2 = req2("GET", self.url(books_read) + q + "2")
            ids1 = set(re.findall(r"GRADERBOOK-Bulk \d+", p1))
            ids2 = set(re.findall(r"GRADERBOOK-Bulk \d+", p2))
            ok = st1 == st2 == 200 and ids1 and ids2 and ids1 != ids2 and len(ids1) <= 10
            return ok, "page1 %d items, page2 %d, overlap %d" % (len(ids1), len(ids2), len(ids1 & ids2))
        self.check("F9", "pagination pages through a big catalogue",
                   "Page smoothly through tens of thousands of titles.", f9)

        def f10():
            st, tx = req2("POST", self.url(a["members"]),
                          {"name": "Jane Reader", "email": "jane.reader@example.com"},
                          token=self.token)
            self.member_id = find_id(jload(tx))
            if not self.member_id:
                return False, "member create failed: %s" % st
            before = snapshot_files(self.run_copy, a["mail_globs"])
            t0 = time.time()
            st2, tx2 = req2("POST", self.url(a["loans"]),
                            a["loan_body"](self.book_id, self.member_id), token=self.token)
            dt = time.time() - t0
            self.loan_id = find_id(jload(tx2))
            self._mail_before = before
            if not (200 <= st2 < 300):
                return False, "loan status %s" % st2
            st3, tx3 = req2("GET", self.url(a["book"].format(id=self.book_id)))
            gone = re.search(r'"(available|is_available)"\s*:\s*(false|0)', tx3, re.I) or \
                   "on loan" in tx3.lower() or "unavailable" in tx3.lower() or \
                   '"active_loan"' in tx3
            return dt < 3.0 and bool(gone), "loan in %.2fs, availability flipped: %s" % (dt, bool(gone))
        self.check("F10", "borrow returns immediately + availability flips",
                   "Recording the loan must return immediately — nobody should wait for the "
                   "email. / Lend must always know a book's current availability.", f10)

        def f13():
            deadline = time.time() + 12
            while time.time() < deadline:
                now = snapshot_files(self.run_copy, a["mail_globs"])
                new = now - getattr(self, "_mail_before", set())
                if new:
                    return True, "evidence: %s" % sorted(new)[0]
                time.sleep(0.5)
            return False, "no queue/mailbox artifact within 12s of borrow"
        self.check("F13", "email receipt queued in background",
                   "When a member borrows a book, they are emailed a receipt showing the due date.", f13)

        def f11():
            if not self.loan_id:
                return False, "blocked: no live loan to double-borrow against (F10 failed)"
            st, tx = req2("POST", self.url(a["loans"]),
                          a["loan_body"](self.book_id, self.member_id), token=self.token)
            j = jload(tx)
            # 401/403 = auth refusal, not the domain rule under test
            return (400 <= st < 500 and st not in (401, 403)) and j is not None, "status %s" % st
        self.check("F11", "double-borrow clearly rejected",
                   "A book that is already out on loan cannot be borrowed again until it is "
                   "returned; the API must reject that attempt clearly.", f11)

        def f12():
            path, body = a["loan_return"](self.loan_id, self.book_id)
            st, tx = req2("POST", self.url(path), body, token=self.token)
            if not (200 <= st < 300):
                return False, "return status %s" % st
            st2, tx2 = req2("GET", self.url(a["book"].format(id=self.book_id)))
            avail = re.search(r'"(available|is_available)"\s*:\s*(true|1)', tx2, re.I) or \
                    "available" in tx2.lower()
            hist = "Jane Reader" in tx2 or '"loans"' in tx2 or '"history"' in tx2
            if not hist:  # history may live on the web detail page instead
                st3, tx3 = req2("GET", self.url("/book/%s" % self.book_id))
                if st3 != 200:
                    st3, tx3 = req2("GET", self.url("/books/%s" % self.book_id))
                hist = st3 == 200 and "Jane Reader" in tx3
            return bool(avail and hist), "available again: %s, history visible: %s" % (bool(avail), hist)
        self.check("F12", "return frees the book + history retained",
                   "A book can be borrowed by different members over time. Lend must always "
                   "know ... its full borrowing history.", f12)

        def f14():
            st, tx = req2("GET", self.url(a["audit"]), token=self.token)
            if st != 200:
                return False, "status %s" % st
            attributed = any(n in tx for n in a["staff_names"])
            about_us = "GRADERBOOK" in tx or "loan" in tx.lower()
            return bool(attributed and about_us), "attributed to %s: %s" % (a["staff_names"], attributed)
        self.check("F14", "audit log records changes with staff attribution",
                   "Every change is attributed to the staff member who made it and recorded "
                   "so it can be reviewed later.", f14)

        def f15():
            png = b"\x89PNG\r\n\x1a\n" + os.urandom(64)
            for field in ("cover_image", "file", "cover"):
                raw, ct = multipart({"title": "GRADERBOOK-Upload", "author": "Up Loader",
                                     "published_year": 2010, "isbn": "978-0-00-000002-4"},
                                    field, "cover.png", png)
                st, tx = req2("POST", self.url(a["books"]), raw=raw, ctype=ct, token=self.token)
                if 200 <= st < 300:
                    bid = find_id(jload(tx))
                    st2, tx2 = req2("GET", self.url(a["book"].format(id=bid or 0)))
                    m = re.search(r'"cover[^"]*"\s*:\s*"([^"]+)"', tx2)
                    if m and m.group(1).strip():
                        loc = m.group(1)
                        st3, _ = req2("GET", self.url(loc) if loc.startswith("/") else loc)
                        return st3 == 200, "multipart accepted (field %s), cover at %s -> %s" % (field, loc, st3)
                    return False, "multipart accepted but no stored cover path returned"
            return False, "no endpoint accepts a multipart image; cover_image is a pass-through string"
        self.check("F15", "cover image can actually be uploaded",
                   "Each book has a cover image users can upload.", f15)

        def f16():
            en_st, en_tx = req2("GET", self.url("/"))
            loc = jload((self.run_copy / a["locale_file"]).read_text(encoding="utf-8")) or {}
            vals = [v for v in loc.values() if isinstance(v, str) and 3 < len(v) < 60]
            if a["lang_setup"]:
                req2("GET", self.url(a["lang_setup"]), cookies=True)
            st, tx = req2("GET", self.url(a["lang_page"]), cookies=True)
            # strict: an actual translated string must appear that the EN page lacks;
            # "pages differ" alone false-positives on any dynamic HTML
            hits = [v for v in vals if v in tx and v not in en_tx]
            return st == 200 and bool(hits), \
                "%d locale strings served (e.g. %r)" % (len(hits), hits[0] if hits else None)
        self.check("F16", "second language actually served",
                   "Available in English and one other language.", f16)

        def f17():
            if not self.book_id:
                return False, "blocked: no created book to check (F6 failed)"
            srv.stop()
            time.sleep(1)
            ok = srv.start()
            if not ok:
                return False, "did not reboot"
            st, tx = req2("GET", self.url(a["book"].format(id=self.book_id)))
            return st == 200 and "GRADERBOOK-Alpha Zebra" in tx, "after restart: %s" % st
        self.check("F17", "data survives an application restart",
                   "All data must persist and survive an application restart.", f17)

        def f18():
            st, _ = req2("GET", self.url("/swagger"))
            # framework 3.13.54 serves /swagger/openapi.json; book ch20 still says
            # /swagger/json (logged doc drift) — accept either
            spec_url, st2, tx2 = None, 0, ""
            for cand in ("/swagger/openapi.json", "/swagger/json"):
                st2, tx2 = req2("GET", self.url(cand))
                if st2 == 200:
                    spec_url = cand
                    break
            j = jload(tx2) or {}
            paths = j.get("paths", {})
            covered = sum(1 for p in (a["books"], a["loans"], a["login"][0]) if p in paths)
            return st == 200 and st2 == 200 and covered >= 2, \
                "/swagger %s, spec %s %s, own routes in spec: %d" % (st, spec_url, st2, covered)
        self.check("F18", "interactive API docs served",
                   "Provide interactive documentation for the API.", f18)

        return srv, True

    # ---------------- P-tier ----------------
    def run_production(self, dest, srv):
        print("P-tier (same copy, TINA4_DEBUG=false, --production):")
        srv.stop()
        time.sleep(1)
        set_env_flag(dest, "TINA4_DEBUG", "false")
        penv = dict(os.environ, TINA4_DEBUG="false", TINA4_PORT=str(self.port))
        prod = Serve(dest, "uv run tina4 serve --production", self.port, env=penv)

        booted = self.check("P1", "boots in production configuration",
                            "It must also run correctly in production configuration — with "
                            "debugging turned off, a real secret configured, and all data intact.",
                            lambda: (prod.start(), ""))
        if not booted:
            prod.stop()
            return

        def p2():
            if not self.book_id:
                return False, "blocked: no created book to check (F6 failed)"
            st, tx = req2("GET", self.url(self.a["book"].format(id=self.book_id)))
            return st == 200 and "GRADERBOOK-Alpha Zebra" in tx, "status %s" % st
        self.check("P2", "data intact across the mode switch",
                   "...and all data intact.", p2)

        def p3():
            st, tx = req2("POST", self.url(self.a["books"]),
                          {"title": "ProdNoAuth Probe", "author": "X Author",
                           "published_year": 2020, "isbn": "978-0-00-000008-2", "cover_image": ""})
            return 400 <= st < 500, "status %s (2xx = unauthenticated write accepted in prod)" % st
        self.check("P3", "unauthenticated write refused in production",
                   "Anyone who is not signed in must be refused ... actually refused by the API. "
                   "(graded again with debugging off)", p3)

        def p4():
            path, creds = self.a["login"]
            st, tx = req2("POST", self.url(path), creds)
            tok = (jload(tx) or {}).get("token")
            if not tok:
                return False, "login failed in prod: %s" % st
            st2, tx2 = req2("POST", self.url(self.a["books"]),
                            {"title": "GRADERBOOK-Prod", "author": "P Author", "published_year": 2024,
                             "isbn": "978-0-00-000001-7", "cover_image": ""}, token=tok)
            return 200 <= st2 < 300, "authed write status %s" % st2
        self.check("P4", "staff flow still works in production",
                   "Staff must sign in before they can add, edit, or remove books. "
                   "(graded again with debugging off)", p4)

        prod.stop()

    # ---------------- T-tier ----------------
    def run_tests(self, dest):
        print("T-tier (their suite, `tina4 test` per book ch18):")
        if self.skip_tests:
            self.results["T1"] = {"ok": None, "title": "their tests", "note": "skipped", "spec": ""}
            print("  T1   SKIP")
            return

        def t1():
            # Canonical runner first (book ch18: `tina4 test` = pytest over tests/);
            # fall back only when the RUNNER is unusable, never because tests are red.
            runners = ["tina4 test", "uv run pytest tests/ -q",
                       "uv run python -m unittest discover -s tests -v"]
            log, verdict, tail = "", None, ""
            for cmd in runners:
                p = subprocess.run(cmd, cwd=str(dest), capture_output=True,
                                   text=True, timeout=420, shell=True)
                out = (p.stdout or "") + (p.stderr or "")
                log += "\n===== %s (exit %s) =====\n%s" % (cmd, p.returncode, out)
                low = out.lower()
                unusable = ("no module named" in low or "not recognized" in low
                            or "failed to spawn" in low or "program not found" in low
                            or "no tests ran" in low or "collected 0 items" in low
                            or "ran 0 tests" in low or "usage:" in low[:400]
                            or p.returncode in (4, 5))
                if not unusable:
                    verdict = (p.returncode == 0)
                    tail = "%s -> %s" % (cmd, " ".join(out.replace("\n", " ").split()[-22:]))
                    break
            (dest / "grader-tests.log").write_text(log, encoding="utf-8")
            if verdict is None:
                return False, "no runner could execute the suite (see grader-tests.log)"
            return verdict, tail[:240]
        self.check("T1", "their own test suite passes",
                   "Include an automated test suite that proves the behaviour described above.", t1)

    # ---------------- S-tier ----------------
    def run_static(self):
        print("S-tier (static idiom, real run dir):")
        rd = self.run_dir

        def s1():
            sqls = list((rd / "migrations").glob("*.sql")) if (rd / "migrations").exists() else []
            tables = sum(len(re.findall(r"CREATE TABLE", p.read_text(encoding="utf-8", errors="replace"), re.I))
                         for p in sqls)
            return bool(sqls) and tables >= 3, "%d migration file(s), %d CREATE TABLE" % (len(sqls), tables)
        self.check("S1", "schema via migrations (book ch06)", "", s1)

        def s2():
            orm = list((rd / "src" / "orm").glob("*.py")) if (rd / "src" / "orm").exists() else []
            models = [p for p in orm if "class" in p.read_text(encoding="utf-8", errors="replace")]
            return len(models) >= 4, "%d ORM models" % len(models)
        self.check("S2", "entities as ORM models (book ch06)", "", s2)

        def s3():
            pats = re.compile(r"tina4_python\.queue|ServiceRunner|background\(")
            hits = [p.name for p in rd.rglob("*.py")
                    if ".venv" not in p.parts and pats.search(p.read_text(encoding="utf-8", errors="replace"))]
            return bool(hits), ", ".join(sorted(set(hits))[:4])
        self.check("S3", "background work via framework queue/runner (book ch12/27)", "", s3)

        def s4():
            tdir = rd / "src" / "templates"
            tmpl = list(tdir.rglob("*.twig")) + list(tdir.rglob("*.html")) if tdir.exists() else []
            inline = [p.name for p in (rd / "src" / "routes").glob("*.py")
                      if "<html" in p.read_text(encoding="utf-8", errors="replace").lower()]
            return bool(tmpl) and not inline, "%d templates, inline html in: %s" % (len(tmpl), inline or "none")
        self.check("S4", "UI via template files, not inline HTML (book ch04)", "", s4)

        def s5():
            blob = ""
            for p in list(rd.rglob("*.py")) + list((rd / "migrations").glob("*.sql")):
                if ".venv" in p.parts:
                    continue
                blob += p.read_text(encoding="utf-8", errors="replace")
            hashed = re.search(r"check_password|verify_password|set_password|get_password_hash|pbkdf2", blob)
            plain = re.search(r"INSERT[^;]{0,200}VALUES[^;]{0,200}'(password|admin|secret)123?'", blob, re.I)
            return bool(hashed) and not plain, "hash api: %s, plaintext seed: %s" % (bool(hashed), bool(plain))
        self.check("S5", "passwords hashed via framework auth (book ch08)", "", s5)

        def s6():
            gi = rd / ".gitignore"
            rules = [l.strip() for l in gi.read_text().splitlines()
                     if l.strip() and not l.startswith("#")] if gi.exists() else []
            secretful = []
            for p in list(rd.glob(".env*")) + list((rd / "secrets").rglob("*") if (rd / "secrets").exists() else []):
                if p.is_file() and "TINA4_SECRET" in p.read_text(encoding="utf-8", errors="replace"):
                    secretful.append(p.relative_to(rd).as_posix())
            def ignored(f):
                return any(fnmatch.fnmatch(f, r) or fnmatch.fnmatch(f, r.rstrip("/") + "/*")
                           or f == r.rstrip("/") or f.startswith(r.rstrip("/") + "/") for r in rules)
            leaking = [f for f in secretful if not ignored(f)]
            return not leaking, "secret-bearing: %s, unignored: %s" % (secretful or "none", leaking or "none")
        self.check("S6", "TINA4_SECRET files covered by own .gitignore", "", s6)

        def s7():
            ldir = rd / "src" / "locales"
            locs = list(ldir.glob("*.json")) if ldir.exists() else []
            sizes = [len(jload(p.read_text(encoding="utf-8")) or {}) for p in locs]
            return len(locs) >= 2 and min(sizes or [0]) >= 5, \
                "%s keys per file" % dict(zip([p.name for p in locs], sizes))
        self.check("S7", "two real locale files (book ch14)", "", s7)

    # ---------------- driver ----------------
    def grade(self):
        stamp = {"graded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                 "task": "query-spec-v2.md v2.1", "port": self.port}
        lock = self.run_dir / "uv.lock"
        if lock.exists():
            m = re.search(r'name = "tina4-python"\s*\nversion = "([^"]+)"', lock.read_text())
            stamp["tina4_python"] = m.group(1) if m else "?"
        tmp = Path(tempfile.mkdtemp(prefix="lend-grade-"))
        self.run_copy = tmp / self.run_dir.name
        print("Grading %s on :%d (copy: %s)" % (self.run_dir.name, self.port, self.run_copy))
        copy_run(self.run_dir, self.run_copy, self.port)

        srv, booted = self.run_functional(self.run_copy)
        if booted:
            self.run_production(self.run_copy, srv)
        srv.stop()
        time.sleep(1)
        self.run_tests(self.run_copy)
        self.run_static()

        scored = {k: v for k, v in self.results.items() if v["ok"] is not None}
        passed = sum(1 for v in scored.values() if v["ok"])
        summary = {"meta": stamp, "score": "%d/%d" % (passed, len(scored)), "checks": self.results}
        out = self.run_dir / "results-v2.json"
        out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print("== %s: %d/%d -> %s" % (self.run_dir.name, passed, len(scored), out))

        if not self.keep:
            shutil.rmtree(tmp, ignore_errors=True)
        else:
            print("kept copy: %s" % self.run_copy)
        return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--port", type=int, default=7511)
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--skip-tests", action="store_true")
    args = ap.parse_args()
    run_dir = Path(args.run_dir).resolve()
    adapter = ADAPTERS.get(run_dir.name)
    if not adapter:
        sys.exit("no adapter for %s (known: %s)" % (run_dir.name, list(ADAPTERS)))
    Grader(run_dir, adapter, args.port, args.keep, args.skip_tests).grade()


if __name__ == "__main__":
    main()
