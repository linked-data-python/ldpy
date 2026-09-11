#!/usr/bin/env python3
"""Gather everything still open in ldpy's steering folder.

Things stay open in three places and nobody rereads all of them: the status
line of a design note, an inline marker left mid-sentence, the next action at
the end of the latest journal entry. This collects them.

    python3 steering/bin/ouvert.py             # everything
    python3 steering/bin/ouvert.py --what notes
    python3 steering/bin/ouvert.py --what maxime

`--what maxime` is the one to run when picking work up: it shows what Maxime
wrote since an agent last passed — the repository's uncommitted changes under
steering/ (an agent always commits, so whatever is loose came from him) and
the commits that carry no `Claude` co-author. What he adds to a note is an
instruction: answer it in the note, and say so in the journal.
"""

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(ROOT)
HERE = os.path.basename(ROOT)

#: Statuses that mean work remains (kept in step with coherence.py).
OPEN = ("ébauche", "à trancher", "chantier ouvert")

RE_STATUS = re.compile(r"\*\*Statut\*\*\s*:\s*([^\n]+)")
RE_TITLE = re.compile(r"^#\s*(\d{3}\s*[—-]\s*.+)$", re.M)
RE_MARKER = re.compile(
    r"(TODO|FIXME|XXX|À TRANCHER|à trancher par|point ouvert|reste ouvert)",
    re.I)


def md_files(sub):
    d = os.path.join(ROOT, sub)
    if not os.path.isdir(d):
        return []
    return [os.path.join(sub, n) for n in sorted(os.listdir(d))
            if n.endswith(".md")]


def source_notes():
    """Design notes whose status still announces work."""
    out = []
    for rel in md_files("design"):
        name = os.path.basename(rel)
        if not name[:3].isdigit():
            continue
        text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
        m = RE_STATUS.search(text)
        if not m:
            continue
        status = m.group(1).strip()
        if status.startswith(OPEN):
            title = RE_TITLE.search(text)
            out.append((rel, status, title.group(1) if title else ""))
    return out


def source_markers():
    """Inline markers, anywhere under the steering folder."""
    out = []
    for sub in ("design", "steps"):
        for rel in md_files(sub):
            for n, line in enumerate(
                    open(os.path.join(ROOT, rel), encoding="utf-8"), 1):
                if RE_MARKER.search(line):
                    out.append((f"{rel}:{n}", "", line.strip()[:300]))
    return out


def source_journal():
    """The next action at the end of the latest journal entry."""
    files = [os.path.basename(p) for p in md_files("steps")
             if os.path.basename(p)[:1].isdigit()]
    if not files:
        return []
    latest = sorted(files, key=lambda n: [
        int(x) if x.isdigit() else x for x in re.split(r"(\d+)", n)])[-1]
    text = open(os.path.join(ROOT, "steps", latest), encoding="utf-8").read()
    m = re.search(r"^##+.*(prochaine action|next action).*$", text,
                  re.M | re.I)
    body = text[m.start():][:400] if m else text[-400:]
    return [(f"steps/{latest}", latest[:10], body.strip())]


def git(*args):
    r = subprocess.run(["git", "-C", REPO] + list(args),
                       capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def source_maxime():
    """What Maxime wrote since an agent last passed."""
    out = []
    for line in git("status", "--short", "--", HERE).splitlines():
        out.append((line[3:].strip(), "non commité", line[:2].strip()))
    log = git("log", "--format=%h%x1f%an%x1f%s%x1f%b%x1e", "-40", "--", HERE)
    for entry in log.split("\x1e"):
        if not entry.strip():
            continue
        sha, author, subject, body = (entry.strip().split("\x1f") + ["", "", ""])[:4]
        if "Claude" not in body:
            out.append((sha, author, subject))
    return out


SOURCES = {
    "notes": ("Design notes still open", source_notes),
    "markers": ("Inline markers", source_markers),
    "journal": ("Next action in the journal", source_journal),
    "maxime": ("Written by Maxime since an agent last passed", source_maxime),
}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Gather what is still open: note statuses, inline "
                    "markers, the journal's next action.")
    ap.add_argument("--what", choices=sorted(SOURCES), action="append",
                    help="restrict to one source (repeatable)")
    args = ap.parse_args(argv)

    chosen = args.what or ["maxime", "notes", "markers", "journal"]
    empty = True
    for key in chosen:
        title, fn = SOURCES[key]
        rows = fn()
        if not rows:
            continue
        empty = False
        print(f"\n{title}\n{'-' * len(title)}")
        width = max(len(a) for a, _, _ in rows)
        for a, b, c in rows:
            print(f"{a:<{width}}  {b}  {c}" if b else f"{a:<{width}}  {c}")
    if empty:
        print("nothing open.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
