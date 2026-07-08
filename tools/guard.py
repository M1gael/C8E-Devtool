"""
guard.py — zip away everything except the active run dir, restore after.

Finding AG-A2-09: a run edited graders/grade_lend.py and self-graded, because
runs live INSIDE this repo. The first version of this script curated a
"sensitive paths" list — and missed tina4-book/, tools/ itself, README.md,
.gitignore, .git. A hand-maintained allow-list of what to hide keeps missing
things. Inverted: allow-list the ONE path the subject needs (the active run
dir), zip literally everything else, including this script's own directory
and .git.

  python tools/guard.py pack <run-rel-path>   # e.g. antigravity/a-vanilla/run-3
  python tools/guard.py unpack                # after the run finishes + is captured
  python tools/guard.py status

Because tools/ itself gets zipped away, pack() writes a standalone restore
script next to the vault (outside the repo) — use THAT to unpack once this
copy of guard.py no longer exists on disk.

Zip is verified (testzip + file count) before any original is deleted. pack()
refuses to run on a dirty working tree — the commit made right before pack is
the real backstop; the zip is just convenience.
"""
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
VAULT_DIR = REPO.parent / ".harness-guard"
VAULT = VAULT_DIR / "guard.zip"
MARKER = VAULT_DIR / "active_run.txt"
STUB = VAULT_DIR / "unpack.py"

STUB_SRC = '''"""Standalone restore -- use when tools/guard.py has been zipped away.
Auto-written by guard.py pack(); do not edit."""
import zipfile
from pathlib import Path
REPO = Path(r"%(repo)s")
VAULT = Path(r"%(vault)s")
with zipfile.ZipFile(VAULT) as z:
    bad = z.testzip()
    if bad:
        raise SystemExit("zip corrupt (%%s)" %% bad)
    z.extractall(REPO)
    print("restored %%d files from %%s" %% (len(z.namelist()), VAULT))
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


def _files(p: Path):
    if p.is_file():
        yield p
    elif p.is_dir():
        for f in p.rglob("*"):
            if f.is_file():
                yield f


def pack(keep_rel: str):
    if VAULT.exists():
        sys.exit("vault already exists at %s — unpack first" % VAULT)
    if not _git_clean():
        sys.exit("working tree not clean — commit first (that commit is the backstop)")
    chain, rel_parts = _keep_chain(keep_rel)
    to_zip = []
    for depth, parent in enumerate(chain):
        keep_child = rel_parts[depth]
        for entry in sorted(parent.iterdir()):
            if entry.name == keep_child:
                continue
            to_zip.append(entry)
    if not to_zip:
        print("nothing to pack — is everything already packed away?")
        return
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(VAULT, "w", zipfile.ZIP_DEFLATED) as z:
        for entry in to_zip:
            for f in _files(entry):
                z.write(f, f.relative_to(REPO).as_posix())
                n += 1
    with zipfile.ZipFile(VAULT) as z:  # verify BEFORE deleting anything
        bad = z.testzip()
        if bad:
            VAULT.unlink()
            sys.exit("zip verify FAILED (%s) — originals kept, vault discarded" % bad)
        count = len(z.namelist())
    if count < n:
        VAULT.unlink()
        sys.exit("zip short (%d < %d) — originals kept, vault discarded" % (count, n))
    MARKER.write_text(keep_rel, encoding="utf-8")
    STUB.write_text(STUB_SRC % {"repo": str(REPO), "vault": str(VAULT)}, encoding="utf-8")
    for entry in to_zip:
        shutil.rmtree(entry) if entry.is_dir() else entry.unlink()
    print("packed %d files -> %s" % (count, VAULT))
    print("kept live: %s (only this is visible in the repo now)" % keep_rel)
    print("tools/guard.py is zipped too — to restore later run:")
    print("  python %s" % STUB)


def unpack():
    if not VAULT.exists():
        sys.exit("no vault at %s" % VAULT)
    with zipfile.ZipFile(VAULT) as z:
        bad = z.testzip()
        if bad:
            sys.exit("zip corrupt (%s)" % bad)
        z.extractall(REPO)
        count = len(z.namelist())
    kept = MARKER.read_text(encoding="utf-8").strip() if MARKER.exists() else "?"
    print("restored %d files from %s" % (count, VAULT))
    print("was kept live during the run: %s" % kept)
    print("verify `git status` clean, then delete %s when satisfied" % VAULT_DIR)


def status():
    print("vault: %s (%s)" % (VAULT, "exists" if VAULT.exists() else "none"))
    if VAULT.exists() and MARKER.exists():
        print("kept live during current pack: %s" % MARKER.read_text(encoding="utf-8").strip())
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
