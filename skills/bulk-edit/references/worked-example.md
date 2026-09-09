# Worked example: collapsing release chains in 638 issue titles

The run this skill was written from, 2026-09-09, on a repository of 3253 issues. Included because each gate in `SKILL.md` earned its place here, and the near-misses are more instructive than the result.

## The request

Titles carried a release-deferral log in the title string. Every time a ticket slipped a release, someone appended the new release as a bracket:

```
[15.2]->[22.2]->[23.1]->[23.2]->[24.2]->[25.2]->[19.2]->[21.2]->[22.1]->[25.2]->[26.2] chore(clients): run the individual eater import ...
```

Wanted: keep the first and last bracket only.

```
[15.2] -> [26.2] chore(clients): run the individual eater import ...
```

## What characterizing the population changed

A first regex suggested 545 candidates. That number was wrong in both directions, and four passes over the full dump were needed before the transform was safe.

**Not every leading bracket is a release.** `[Support]`, `[FE]`, `[BE]`, `[BUG]`, `[@next]`, `[0.6.0]` and `[Create Account]` all appear in leading runs. "Keep first and last" would have deleted a `[Support]` tag on 58 issues.

**The joiner vocabulary was 25 distinct strings**, not one. `->` (3200), `&` (271), ` -> ` (154), bare space (126), `-->`, `->>`, `->...->`, `>`, `..>`, `+`, `/`, and a non-breaking space. Frequency counting found these; reading examples did not.

**Two joiners meant different things.** `->` is "then deferred to". `&` is "shipped in both". Collapsing `[19.1]&[19.2]->[20.1]&[20.2]&[21.1]&[27.1]` to first and last would destroy the second relationship. 138 issues used `&` inside the run and were held back rather than guessed at.

**`[...]` was an existing elision marker.** Someone had already shortened some titles by hand. It carries no release and is safely dropped, but only once identified.

**Some records had the pattern outside the leading run.** `#4695` ends with `[Migration GS2 ID: 17 I GS3 ID: 55`, and `#3256` had `->[12.1]->[16.1]` appended *after* the title text. Structural anchoring made both unreachable. A "find release-looking brackets" regex would have eaten them.

Final classification: 638 clean, 142 held (135 conjunctions, 7 leading tags), the rest below the 3-bracket threshold and untouched.

## What the dry run caught

Two records failed an equality check against the exploration dump. Both were trailing-whitespace artifacts, not real edits. Re-deriving the transform from the live value and comparing the *result* passed both, and that became the permanent guard. It is the stricter check: it validates against what exists rather than what was remembered.

## What went wrong

**Rate limits, twice.** The first runner used `gh issue view` plus `gh issue edit` plus a read-back, three GraphQL points per issue, and died at 220 errors. The second attempt tripped the secondary limit, which reported itself as GraphQL exhaustion while `rate_limit` showed every bucket full. The third runner used REST `PATCH`, whose response is the read-back, and finished 638 renames on about 570 of 5000 core.

**An import-ordering bug in the runner.** It aborted on the first record and wrote nothing. Failing closed on a bulk mutation is the correct outcome and worth designing for.

## What verification found

638 of 638 matched. Zero unplanned title changes. One survivor showing three release brackets, correctly: `#3256`, where the trailing `->[12.1]->[16.1]` sat outside the anchored run and was left alone by design.

The collateral check is the one that would have caught an over-broad anchor, and it is the one that reports nothing interesting when the run is correct. That is not a reason to skip it.

## What the run did not fix

**The trailing bracket duplicated a board field, and had already drifted.** Comparing the last title bracket against the project board's Release field across 768 candidates: 559 matched, 209 disagreed, board ahead every time. The title was a lagging copy of data the board already owned. Worth surfacing as a decision rather than silently preserving.

**A weekly automation regrows the chains.** Clustering rename events found 21 edits on consecutive Thursdays between 01:03 and 01:26 Berlin, under a `User` account, so not a repository workflow. The maintainer named a cron ID, a skill path and a wrapper script; none existed on the host they named, though the schedule they described matched the evidence exactly. Schedule and location are independent claims and were verified independently.

**The sequencing trap.** The recommended follow-up was to strip the trailing bracket entirely, leaving origin only. Running that *before* the automation stopped would have made every one of the 638 disagree with the board, so the next scheduled run would have appended a bracket to all 638 instead of the 209 that disagree today. The cleanup would have caused more churn than doing nothing. The order matters, and saying so was more valuable than executing quickly.
