# steering — how ldpy's decisions and sessions are recorded

Two folders and two rules.

**`design/`** — one file per decision, numbered `001`–`099`. A note states
**today's state**: the decision in force, the defects not yet resolved, the
open questions. Not the history — that is in `git log` and in `steps/`.

Header, normed, because the scripts read it:

    # NNN — Title

    **Date** : YYYY-MM-DD · **Statut** : <status> — <nuance>

The date is that of the **last update**. The status comes from a closed
vocabulary, least to most settled:

| status | meaning |
|---|---|
| `ébauche` | written; the decision is not made |
| `à trancher` | the question is posed, the answer is missing |
| `chantier ouvert` | decided; the work remains |
| `constats établis` | an observation note: it reports, it does not decide |
| `acté` | decided; no code to write, or not yet |
| `tranché` | settled on the merits |
| `implémenté` | decided and carried out in the code |

A change is made **in place**, as if the note had always said so. No
`Révision du …` section, no account of a request and how it was handled, no
discarded option kept for the record, no corrected defect — a pointer to the
commit that fixes it, or nothing. `coherence.py` refuses a note that carries
a revision section.

Every note appears exactly once in [design/README.md](design/README.md),
with the same status it states itself.

**`steps/`** — the journal, one file per session
(`YYYY-MM-DD-session-N.md`): what was done, what was learned, the exact state
at the stop, and **the next concrete action**. Unlike a note, a journal entry
is dated and **never rewritten**. Parallel sessions: sort the existing names
before creating yours, never overwrite someone else's.

## The two scripts

    python3 steering/bin/coherence.py     # must exit 0 before any commit
    python3 steering/bin/ouvert.py        # everything still open

`coherence.py` catches notes and index that contradict each other, numbers
taken twice, statuses outside the vocabulary, and dead links. `ouvert.py`
gathers what remains: open statuses, inline markers, the journal's next
action, and — `--what maxime` — what Maxime wrote since an agent last passed.

## Language

The notes and the journal stay in **French**: internal reasoning, not the
product. Everything else a third party reads — this file, the scripts, the
code, the documentation — is in **English**.

## Where the rest lives

These notes were kept until 2026-09-11 in a private steering repository
shared by the nine repositories of the workspace, and moved here so that the
decisions travel with the code they decide. Two things stayed there, on
purpose: the journal from before that date, which interleaves ldpy with the
other projects and cannot be split without rewriting dated documents; and the
cross-project TODO, which is what such a repository is for. Notes belonging
to other projects are referenced by number, without a link — they are not
public.
