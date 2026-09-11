#!/usr/bin/env python3
"""Check the steering folder for internal contradictions.

A note claims one status, the index claims another; a number is used twice; a
link leads nowhere. None of this shows up when reading, and all of it costs
later. This says so in a second.

    python3 steering/bin/coherence.py            # exits 1 if anything is off
    python3 steering/bin/coherence.py --quiet    # print only the discrepancies

What it checks:

1. every note carries a date and a status from the closed vocabulary;
2. its number is in range 001-099 and is used once;
3. filename, title and number agree;
4. every note appears exactly once in the index, and the index has no ghosts;
5. index and note agree on the status;
6. every relative link to a file in this folder leads somewhere;
7. no note carries a dated "Révision du" section — a note states today's
   state, and a change is made in place (see ../README.md).

This is ldpy's own copy, trimmed to a single project: the notes live flat in
steering/design/ rather than under one directory per project.
"""

import argparse
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DESIGN = os.path.join(ROOT, "design")
INDEX = "design/README.md"

#: CLOSED vocabulary of statuses, least to most settled. A note's status is
#: one of these, optionally followed by " — nuance".
STATUSES = {
    "ébauche": "written; the decision is not made",
    "à trancher": "the question is posed, the answer is missing",
    "chantier ouvert": "decided; the work remains",
    "constats établis": "an observation note: it reports, it does not decide",
    "acté": "decided; no code to write, or not yet",
    "tranché": "settled on the merits",
    "implémenté": "decided and carried out in the code",
}

#: Statuses that flag remaining work (see ouvert.py).
OPEN = ("ébauche", "à trancher", "chantier ouvert")

LOW, HIGH = 1, 99

RE_DATE = re.compile(r"\*\*Date\*\*\s*:\s*(\d{4}-\d{2}-\d{2})")
RE_STATUS = re.compile(r"\*\*Statut\*\*\s*:\s*([^\n]+)")
RE_TITLE = re.compile(r"^#\s*(\d{3})\s*[—-]\s*(.+)$", re.M)
RE_REVISION = re.compile(r"^##+\s*R[ée]vision du (\d{4}-\d{2}-\d{2})", re.M)
RE_INDEX_ROW = re.compile(
    r"^\|\s*(\d{3})\s*\|\s*\[[^\]]*\]\(([^)]+)\)\s*\|([^|]*)\|([^|]*)\|\s*$", re.M)
RE_LINK = re.compile(r"\[[^\]]*\]\(([^)#][^)]*)\)")


class Report:
    def __init__(self):
        self.issues = []

    def issue(self, where, what):
        self.issues.append((where, what))

    def render(self, quiet=False):
        if not self.issues:
            if not quiet:
                print("coherent.")
            return 0
        width = max(len(w) for w, _ in self.issues)
        for where, what in self.issues:
            print(f"{where:<{width}}  {what}")
        print(f"\n{len(self.issues)} discrepancy(ies).")
        return 1


def canonical(status):
    """The closed-vocabulary word a status starts with, or None."""
    for word in sorted(STATUSES, key=len, reverse=True):
        if status == word or status.startswith(word + " "):
            return word
    return None


def notes():
    """[(relative path, number, text)] for every design note."""
    out = []
    for name in sorted(os.listdir(DESIGN)):
        # A note carries a three-digit number. Anything else — a TODO.md
        # dropped in the folder, the index itself — is a working note:
        # ouvert.py surfaces it, this checker has nothing to say about it.
        if not name.endswith(".md") or not name[:3].isdigit():
            continue
        rel = os.path.join("design", name)
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            out.append((rel, name[:3], f.read()))
    return out


def check_note(rel, num, text, r):
    date = RE_DATE.search(text)
    if not date:
        r.issue(rel, "no « **Date** : YYYY-MM-DD »")
    status = RE_STATUS.search(text)
    if not status:
        r.issue(rel, "no « **Statut** : … »")
        return None
    word = canonical(status.group(1).strip())
    if word is None:
        r.issue(rel, f"status outside the vocabulary: {status.group(1).strip()!r} "
                     f"(expected one of: {', '.join(STATUSES)})")

    if not LOW <= int(num) <= HIGH:
        r.issue(rel, f"number {num} outside the {LOW:03d}-{HIGH:03d} range")
    title = RE_TITLE.search(text)
    if not title:
        r.issue(rel, "no « # NNN — … » title on the first line")
    elif title.group(1) != num:
        r.issue(rel, f"the title says {title.group(1)}, the filename says {num}")

    for rev in RE_REVISION.findall(text):
        r.issue(rel, f"« Révision du {rev} » section: a note states today's "
                     f"state, and a change is made in place")
    return word


def check_index(by_number, r):
    with open(os.path.join(ROOT, INDEX), encoding="utf-8") as f:
        text = f.read()
    seen = set()
    for num, path, summary, status in RE_INDEX_ROW.findall(text):
        if not os.path.isfile(os.path.join(DESIGN, path)):
            r.issue(INDEX, f"row {num}: {path} does not exist")
            continue
        if num in seen:
            r.issue(INDEX, f"number {num} is indexed twice")
        seen.add(num)
        if not summary.strip():
            r.issue(INDEX, f"row {num}: no one-line decision")
        expected = by_number.get(num)
        if expected is None:
            continue
        word = canonical(status.strip())
        if word is None:
            r.issue(INDEX, f"row {num}: status outside the vocabulary "
                           f"({status.strip()!r})")
        elif word != expected[0]:
            r.issue(INDEX, f"row {num}: the index says « {word} », the note "
                           f"says « {expected[0]} »")
    for num, (_, rel) in sorted(by_number.items()):
        if num not in seen:
            r.issue(rel, f"missing from the index ({INDEX})")


def check_links(r):
    """Every relative link to a file in this folder must lead somewhere."""
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for name in files:
            if not name.endswith(".md"):
                continue
            p = os.path.join(dirpath, name)
            rel = os.path.relpath(p, ROOT)
            with open(p, encoding="utf-8") as f:
                text = f.read()
            for link in RE_LINK.findall(text):
                if re.match(r"[a-z][a-z0-9+.-]*:", link) or link.startswith("//"):
                    continue                      # http:, mailto:…
                target = link.split("#", 1)[0]
                if not target:
                    continue
                path = os.path.normpath(os.path.join(os.path.dirname(p), target))
                if not os.path.exists(path):
                    r.issue(rel, f"dead link: {link}")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Check the notes, the index and the relative links.")
    ap.add_argument("--quiet", action="store_true",
                    help="print nothing when all is well")
    ap.add_argument("--no-links", action="store_true",
                    help="skip the relative-link check")
    args = ap.parse_args(argv)

    r = Report()
    by_number = {}
    for rel, num, text in notes():
        word = check_note(rel, num, text, r)
        if num in by_number:
            r.issue(rel, f"number {num} is already taken by {by_number[num][1]}")
        elif word:
            by_number[num] = (word, rel)
    check_index(by_number, r)
    if not args.no_links:
        check_links(r)
    return r.render(args.quiet)


if __name__ == "__main__":
    sys.exit(main())
