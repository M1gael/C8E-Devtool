"""
guard.py — move everything except the active run dir out of the repo, restore after.

Finding AG-A2-09: a run edited graders/grade_lend.py and self-graded, because
runs live INSIDE this repo. v1 zipped a curated list (missed things), v2 zipped
everything (slow: compressing .git + a run's .venv took minutes). v3 MOVES the
files instead — same-volume renames, near-instant, no compression — to a stash
far outside the repo AND outside the projects tree entirely.

  python tools/guard.py pack <run-rel-path>   # e.g. antigravity/c-mcp/run-1
  python tools/guard.py unpack                # after the run finishes + is captured
  python tools/guard.py status

Because tools/ itself moves away, pack() writes a standalone restore.py next to
the stash — use THAT to unpack while this copy of guard.py is stashed.

pack refuses on a dirty working tree (the commit right before pack is the
backstop). Every move is recorded in a manifest; a failed pack rolls back the
moves already made.
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
# far outside the repo and outside Documents/projects entirely
STASH_ROOT = Path.home() / ".harness-guard"
STASH = STASH_ROOT / "stash"
MANIFEST = STASH_ROOT / "manifest.json"
RESTORE = STASH_ROOT / "restore.py"

RESTORE_SRC = '''"""Standalone restore -- use while tools/guard.py is stashed away.
Auto-written by guard.py pack(); do not edit."""
import json
import shutil
from pathlib import Path
REPO = Path(r"%(repo)s")
STASH = Path(r"%(stash)s")
MANIFEST = Path(r"%(manifest)s")
rels = json.loads(MANIFEST.read_text(encoding="utf-8"))["moved"]
back = 0
for rel in rels:
    src, dst = STASH / rel, REPO / rel
    if not src.exists():
        raise SystemExit("MISSING in stash: %%s -- stopped after %%d restores" %% (rel, back))
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    back += 1
MANIFEST.unlink()
shutil.rmtree(STASH, ignore_errors=True)
print("restored %%d entries from %%s" %% (back, STASH))
'''


def _git_clean() -> bool:
    r = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"],
                        capture_output=True, text=True)
    return r.returncode == 0 and not r.stdout.strip()


def _keep_chain(keep_rel: str):
    keep = (REPO / keep_rel).resolve()
    if not keep.is_dir():
        sys.exit("keep path not found or not a dir: %s" % keep_rel)
    rel_parts = keep.relative_to(REPO).parts
    if not rel_parts:
        sys.exit("keep path can't be the repo root")
    chain = [REPO]
    cur = REPO
    for part in rel_parts[:-1]:
        cur = cur / part
        chain.append(cur)
    return chain, rel_parts


def pack(keep_rel: str):
    if MANIFEST.exists():
        sys.exit("stash already active (%s) — unpack first" % MANIFEST)
    if not _git_clean():
        sys.exit("working tree not clean — commit first (that commit is the backstop)")
    chain, rel_parts = _keep_chain(keep_rel)
    to_move = []
    for depth, parent in enumerate(chain):
        keep_child = rel_parts[depth]
        for entry in sorted(parent.iterdir()):
            if entry.name == keep_child:
                continue
            to_move.append(entry)
    if not to_move:
        print("nothing to move — is everything already stashed?")
        return
    STASH.mkdir(parents=True, exist_ok=True)
    moved = []
    try:
        for entry in to_move:
            rel = entry.relative_to(REPO).as_posix()
            dst = STASH / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(entry), str(dst))
            moved.append(rel)
    except Exception as e:
        for rel in reversed(moved):  # roll back what already moved
            (REPO / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(STASH / rel), str(REPO / rel))
        sys.exit("move FAILED (%s) — rolled %d entries back, repo unchanged" % (e, len(moved)))
    # verify before declaring success
    bad = [r for r in moved if not (STASH / r).exists() or (REPO / r).exists()]
    if bad:
        sys.exit("verify FAILED for: %s — inspect %s manually" % (bad, STASH))
    MANIFEST.write_text(json.dumps({"kept": keep_rel, "moved": moved}, indent=1),
                        encoding="utf-8")
    RESTORE.write_text(RESTORE_SRC % {"repo": str(REPO), "stash": str(STASH),
                                      "manifest": str(MANIFEST)}, encoding="utf-8")
    print("moved %d top-level entries -> %s" % (len(moved), STASH))
    print("kept live: %s (only this is visible in the repo now)" % keep_rel)
    print("tools/guard.py moved too — to restore run:")
    print("  python %s" % RESTORE)


def unpack():
    if not MANIFEST.exists():
        sys.exit("no active stash manifest at %s" % MANIFEST)
    rels = json.loads(MANIFEST.read_text(encoding="utf-8"))["moved"]
    back = 0
    for rel in rels:
        src, dst = STASH / rel, REPO / rel
        if not src.exists():
            sys.exit("MISSING in stash: %s — stopped after %d restores" % (rel, back))
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        back += 1
    MANIFEST.unlink()
    shutil.rmtree(STASH, ignore_errors=True)
    print("restored %d entries; verify `git status` clean" % back)


def status():
    active = MANIFEST.exists()
    print("stash: %s (%s)" % (STASH, "ACTIVE" if active else "none"))
    if active:
        m = json.loads(MANIFEST.read_text(encoding="utf-8"))
        print("kept live: %s | stashed entries: %d" % (m["kept"], len(m["moved"])))
    top = sorted(p.name for p in REPO.iterdir())
    print("currently in repo root (%d): %s" % (len(top), ", ".join(top)))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "pack":
        if len(sys.argv) < 3:
            sys.exit("usage: python tools/guard.py pack <run-rel-path>")
        pack(sys.argv[2])
    elif cmd == "unpack":
        unpack()
    else:
        status()
