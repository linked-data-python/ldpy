# Instructions for Claude — linked-data-python (ldpy)

## What this is

`ldpy` is an extension of Python that brings Turtle notation into the
language's syntax, transpiled to pure Python. The parser is island parsing,
written by hand, with **no dependency on rdflib for parsing** — rdflib is an
oracle in the tests and a backend at runtime, never a parser.

## Before changing anything

**Read what Maxime wrote since an agent last passed, and deal with it:**

```sh
python3 steering/bin/ouvert.py --what maxime
```

It shows the uncommitted changes under `steering/` — an agent always commits,
so whatever is loose came from him — and the commits carrying no `Claude`
co-author. What he adds to a design note is an **instruction**: answer it in
the note itself, and say so in the journal. Never build on top without having
read them.

## Picking work back up

1. `steering/steps/` — the **most recent** file: state at the stop, and the
   next action.
2. `python3 steering/bin/ouvert.py` — everything still open, gathered.
3. `steering/design/README.md` — the decisions in force.
4. `git status && git log --oneline -5`.
5. Tests: `python -m pytest tests -q`. Locally Maxime uses a single venv,
   `~/.venvs/ldpy/bin/python`, with rdflib pinned to 7.2.1 so that the corpus
   studies stay reproducible. A bare checkout needs `pip install -e .[dev]`.

## Keeping the records (mandatory, every session)

`steering/` holds the decisions and the journal — its
[README](steering/README.md) states the header format, the closed status
vocabulary and the two rules that matter:

- a **design note states today's state**, and is changed **in place**, as if
  it had always said so — no `Révision du …` section, no discarded option
  kept for the record, no corrected defect;
- a **journal entry is dated and never rewritten**.

`python3 steering/bin/coherence.py` must exit 0 before any commit that
touches `steering/`. Any non-trivial choice gets a design note, before or
just after the implementation.

Design notes belonging to the other repositories of the workspace — the VS
Code extension, the corpus study, the article — live in a private steering
repository. Reference them by number, never by link.

## Language

**Everything a third party can read is in English**: code (comments,
docstrings, test names, error messages), documentation, configuration, this
file. **The design notes and the journal stay in French** — internal
reasoning, not the product — and so do commit messages, for now.

## Working rules

- Every feature arrives **with its tests**; the suite stays green at each
  commit. The three that carry the parser's invariants are golden output,
  identity (transpile→detranspile round-trip) and execution against rdflib as
  oracle — a change that touches the parser and leaves all three untouched is
  a change that was not tested.
- Atomic commits, in French, signed
  `Co-Authored-By: Claude <noreply@anthropic.com>`.
- Reference benchmark: the legacy ANTLR implementation ran at ≈ 170 lines/s.
  The target here is > 10 000 lines/s; `bench/` measures it.

## What does not push itself

This repository is public on GitHub (`origin`) and a `vX.Y.Z` tag triggers
publication to PyPI and to both marketplaces — so a tag is a deliberate act,
never a step in a routine. The `gitlab` remote has **never been pushed to**;
that first push is Maxime's to make.
