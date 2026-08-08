# Batch mode — reviewing multiple PRs in one run

Loaded by main at the start of Phase 1, and only when the user provides **2+ PR URLs** or asks to review **all open PRs**. A single-PR run never reaches any of this.

For "all open PRs", enumerate via `gh pr list --json number,url,title --limit 50`, print the list in the kickoff message, then start — no confirmation prompt (batch mode is unattended by design; a wrong list is visible in the report).

---

## Orchestration

- Main context is the **orchestrator** — oversight only. It never reviews a PR inline, regardless of `SIZE_MODE` (solo-main routing applies inside each subagent, not in main).
- Spawn **ONE `general-purpose` subagent PER PR**. Each subagent runs the single-PR flow (Phases 1–3) independently against its own PR and returns its Phase 4 terminal block plus that round's coverage ledger (see "Ledger transport"). Dispatch in parallel batches of 3–4.
- Subagents NEVER post to GitHub and NEVER ask questions — all posting and all AskUserQuestion checkpoints belong to the orchestrator, at the end.

### `<SKILL_DIR>` on the batch branch

Every per-PR subagent runs the full single-PR flow, so it loads the same reference files main would — the Q6 search algorithm, the false-positive table, the state schema, the verifier prompts — and it dispatches its own Subagent 1 / Subagent 3 / verifiers, whose prompts carry `<SKILL_DIR>` placeholders of their own. A subagent has no way to derive that value: its working directory is the user's repo, not the skill directory, so every bare `references/...` load silently finds nothing and it reviews from memory.

The orchestrator resolves `<SKILL_DIR>` once — the absolute directory of the SKILL.md it is executing, resolved through any symlink, per "Subagent 1" in SKILL.md Phase 2 — and opens every per-PR subagent prompt with it:

```
SKILL_DIR: <SKILL_DIR>

You are running the full /review-pr single-PR flow (Phases 1-3) against <pr-url>.
Your working directory is the user's repo, not the skill directory. Load every
reference file by its absolute `<SKILL_DIR>/references/...` path — a bare relative
path resolves against the repo and silently finds nothing.

Substitute this same SKILL_DIR value into every prompt YOU dispatch — Subagent 1,
Subagent 3, and the Phase 3 verifiers all carry `<SKILL_DIR>` placeholders, and you
are the only source of the value they have.

Do not post to GitHub and do not ask questions. Return your Phase 4 terminal block,
followed by the `<!-- review-pr:ledger -->` block carrying the `ledger` object your
Phase 3 step 6.9 assembled, in the shape "Ledger transport" fixes in
`<SKILL_DIR>/references/batch-mode.md`. Without it your review cannot be posted.
```

---

## Ledger transport

Posting reads the `ledger` object Phase 3 step 6.9 assembled in memory: `references/github-posting.md` composes the body's coverage table from it, and Step 8c persists it. In batch mode that object is built inside a per-PR subagent that no longer exists when the orchestrator posts, and the terminal block carries only the `Coverage` counters line — so the rows behind the `Cov` column, and the object write-back is required to persist byte for byte, have no way home unless the subagent hands them over.

Nothing else needs a transport. Every other field the orchestrator's write-back consumes already rides on the printed findings — `Rule-class`, `Enclosing-symbol`, `Lens`, `Inverse risk` and the `class_completeness:` audit are part of the per-finding block, and the cross-round finding id is a hash over three of them. The ledger is the one input with no representation in the returned text, which is why it gets one here and nothing else does.

Each subagent appends its ledger to its terminal block, fenced and marker-led:

```
<the Phase 4 terminal block, unchanged>

<!-- review-pr:ledger -->
ledger:
  round: <n>
  head_sha: <sha>
  files_changed: <n>
  cells_total: <n>
  cells_examined: <n>
  cells_cannot_assess: <n>
  cells_not_examined: <n>
  rows: <every row, every cell, with its verdict, note and finding_id>
```

**The payload is the state file's own `ledger:` mapping, verbatim** — the shape defined under "Schema" in `references/finding-state-schema.md`, filled from the per-`(file, lens)` lines `references/finding-output-format.md` fixes under "Coverage-ledger cell verdicts". Do not summarize it, drop the notes, or re-serialize it into a batch-only form. Step 8c writes this object unchanged, so a batch-only encoding would be a third representation of a structure that already has exactly two — the schema's and the cell-verdict emission's — and it would have to track both forever.

The orchestrator parses the block back into memory and passes that object everywhere a single-PR run passes step 6.9's — the `Cov` column, the posted body's coverage table, and that PR's Step 8c write-back. It re-asserts the counter partition on parse; a payload that does not total was mutated in transit and its coverage claim is void, which is the no-ledger case below.

**A subagent that returns no ledger has returned no coverage claim, and absent is not zero-gap.** The counters missing are exactly the ones that decide whether an approval was earned, so an orchestrator that synthesizes an empty ledger grants that approval on the run with the least evidence behind it. Instead: render the row's `Cov` as `—`, cap its `Approval` at `With changes` and its `Verdict` at `comment` whatever the returned block claimed, and defer its posting as `PENDING — #<num>: coverage ledger not returned — the body cannot render it and write-back has nothing to persist`. The full block still prints under "Per-PR reviews" — the findings are not what went missing, and dropping them would punish the PR for the reviewer's failure.

---

## "Don't stop" semantics

The run continues unattended through the WHOLE list — batch mode implies the user may be away. Do NOT stop between PRs. Every would-be checkpoint is collected as a **pending decision** instead of asked:

- Stop-and-ask intent gap → review with just the diff, and set that PR's `Mode` header field to `intent not grounded — findings may be generic` (the value is defined in `references/finding-output-format.md`).
- PR > 2000 lines → proceed with chunked review; the `Size` header field carries it, as in a single-PR run.
- Findings selection + post decision → deferred to end-of-run.
- A failed subagent doesn't stop the batch — record `<pr>: review failed (<reason>)` in the consolidated report and continue with the rest.

---

## Consolidated report

After all subagents return, write ONE report document to `/tmp/review-pr-batch-<timestamp>.md` (and print it):

```
# Batch PR Review — <N> PRs (<date>)

| PR | Title | Approval | Verdict | Cov | C | S | M | m |
|----|-------|----------|---------|-----|---|---|---|---|
<one row per PR; "review failed" rows included>

## Pending decisions (<count>)
<one entry per deferred checkpoint, clearly marked:
  PENDING — #<num>: post decision (<verdict>, <F> findings)
  PENDING — #<num>: intent was not grounded — re-run with intent text?>

## Per-PR reviews
<each PR's full Phase 4 terminal block, in list order>
```

### The table is a projection of the canonical header

Each row projects one PR's run-level header from `references/finding-output-format.md`. It carries `Number` (as `PR`), `Title`, `Senior engineer approval`, `Verdict`, `Coverage` (as `Cov`, rendered `<cells_examined>/<cells_total>`) and `Severity counts` split into the four tier columns. No column exists that is not one of those fields.

`Cov` is in the table rather than only in the per-PR block below it because the same rule that governs a single review governs a batch: `approve` is forbidden while `cells_not_examined > 0`. A verdict column with no coverage beside it invites the reader to trust an approval the review never earned, and in a 20-PR list nobody scrolls to each block to check. It is filled from the transported ledger, never from that PR's state file — the file has not been written when the report is composed, so at round 1 it would render the seed's zeros as full coverage.

The remaining seven canonical header fields — `Goal`, `Summary`, `Size`, `Reviewers`, `Round`, `Convergence`, `Mode` — are omitted from the row and appear only in that PR's full block below. The row's job is to rank a list by whether it needs attention; none of the seven changes that ranking, and a `Mode` or `Summary` string long enough to be honest would break the column layout at 20 rows. Nothing is lost: every row's full header is reproduced verbatim under "Per-PR reviews", which is what lets the row be this thin.

A `review failed` row fills `Approval`, `Verdict`, `Cov` and the tier columns with `—` and puts the reason in `Title`. It never renders as a zero-finding pass. A row whose review returned but whose ledger did not fills only `Cov` with `—`, under the caps stated in "Ledger transport".

---

## End-of-run decisions

Ask ONCE, only after the consolidated report is written — so if the user is away, the complete report with clearly-marked pending decisions is already on disk and nothing is lost:

```
header: "Batch done"
text: "<N> PRs reviewed — <M> have findings to post, <K> pending decisions. Walk through them now?"
options:
  - "Triage now (Recommended)" — Walk each PR's findings selection + post decision in turn
  - "Report only" — Keep the consolidated report; posting decisions stay pending
```

On "Triage now": for each PR with findings, run the single-PR "Select findings to post" multiSelect followed by its "Post review" prompt, in list order, handing that PR's transported ledger to posting wherever a single-PR run hands over step 6.9's object. A PR whose ledger did not come back is skipped here and keeps its pending decision — posting it would publish a verdict whose evidence section cannot be rendered. On "Report only": exit — pending decisions remain marked in the report for a later run.
