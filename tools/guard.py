"""
guard.py — hide the harness from a run subject, then restore it.

Finding AG-A2-09: a run edited graders/grade_lend.py and self-graded, because
runs live INSIDE this repo — the subject can read/modify the grader, the spec's
grading map, findings-log, and the scored sibling runs.

Rather than run outside the repo, keep the layout as-is and PACK the sensitive
files into a single zip kept OUTSIDE the repo before a run, then UNPACK after.
During the run the subject sees only its own empty run-N/ plus framework/config.

  python tools/guard.py pack     # before starting a run
  python tools/guard.py unpack   # after the run finishes + is captured
  python tools/guard.py status   # what is currently exposed / packed

Git is the backstop: every packed path is also tracked, so `git checkout -- <p>`
restores it even if the zip is lost. Pack refuses to delete originals unless the
zip verifies first.
"""
import shutil
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# vault lives OUTSIDE the repo so a subject with the repo open cannot read it
VAULT = REPO.parent / ".harness-guard" / "guard.zip"

# paths (relative to repo root) the subject must not see during a run
SENSITIVE = [
    "graders",
    "tasks",
    "findings-log.md",
    "baselines",
    "hub",
    "antigravity/a-vanilla/run-1",
    "antigravity/a-vanilla/run-2",
    "antigravity/a-vanilla-v1",
    "antigravity/archive",
]


def _files(rel):
    p = REPO / rel
    if p.is_file():
        yield p
    elif p.is_dir():
        for f in p.rglob("*"):
            if f.is_file():
                yield f


def pack():
    present = [r for r in SENSITIVE if (REPO / r).exists()]
    if not present:
        print("nothing exposed — already packed?")
        return
    VAULT.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(VAULT, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in present:
            for f in _files(rel):
                z.write(f, f.relative_to(REPO).as_posix())
                n += 1
    with zipfile.ZipFile(VAULT) as z:  # verify BEFORE deleting anything
        bad = z.testzip()
        if bad:
            sys.exit("zip verify FAILED (%s) — originals kept" % bad)
        count = len(z.namelist())
    if count < n:
        sys.exit("zip short (%d < %d) — originals kept" % (count, n))
    for rel in present:
        p = REPO / rel
        shutil.rmtree(p) if p.is_dir() else p.unlink()
    print("packed %d files -> %s" % (count, VAULT))
    print("removed %d paths from tree: %s" % (len(present), ", ".join(present)))
    print("run the subject now; `git status` will show these as deleted (transient)")


def unpack():
    if not VAULT.exists():
        sys.exit("no vault at %s" % VAULT)
    with zipfile.ZipFile(VAULT) as z:
        bad = z.testzip()
        if bad:
            sys.exit("zip corrupt (%s)" % bad)
        z.extractall(REPO)
        count = len(z.namelist())
    print("restored %d files from %s" % (count, VAULT))
    print("verify `git status` clean, then delete the vault dir when satisfied")


def status():
    exposed = [r for r in SENSITIVE if (REPO / r).exists()]
    print("vault: %s (%s)" % (VAULT, "exists" if VAULT.exists() else "none"))
    print("exposed sensitive paths (%d):" % len(exposed))
    for r in exposed:
        print("  " + r)
    missing = [r for r in SENSITIVE if not (REPO / r).exists()]
    if missing:
        print("packed-away (%d): %s" % (len(missing), ", ".join(missing)))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"pack": pack, "unpack": unpack, "status": status}.get(cmd, status)()
