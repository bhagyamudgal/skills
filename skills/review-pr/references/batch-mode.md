# Batch mode — reviewing multiple PRs in one run

Loaded by main at the start of Phase 1, and only when the user provides **2+ PR URLs** or asks to review **all open PRs**. A single-PR run never reaches any of this.

For "all open PRs", enumerate via `gh pr list --json number,url,title --limit 50`, print the list in the kickoff message, then start — no confirmation prompt (batch mode is unattended by design; a wrong list is visible in the report).

---

## Orchestration

- Main context is the **orchestrator** — oversight only. It never reviews a PR inline, regardless of `SIZE_MODE` (solo-main routing applies inside each subagent, not in main).
- Spawn **ONE `general-purpose` subagent PER PR**. Each subagent runs the single-PR flow (Phases 1–3) independently against its own PR and returns its Phase 4 terminal block as its result. Dispatch in parallel batches of 3–4.
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

Do not post to GitHub and do not ask questions. Return your Phase 4 terminal block.
```

---

## "Don't stop" semantics

The run continues unattended through the WHOLE list — batch mode implies the user may be away. Do NOT stop between PRs. Every would-be checkpoint is collected as a **pending decision** instead of asked:

- Stop-and-ask intent gap → review with just the diff; tag that PR's report `intent not grounded — findings may be generic`.
- PR > 2000 lines → proceed with chunked review; note the size in that PR's report header.
- Findings selection + post decision → deferred to end-of-run.
- A failed subagent doesn't stop the batch — record `<pr>: review failed (<reason>)` in the consolidated report and continue with the rest.

---

## Consolidated report

After all subagents return, write ONE report document to `/tmp/review-pr-batch-<timestamp>.md` (and print it):

```
# Batch PR Review — <N> PRs (<date>)

| PR | Title | Approval | Verdict | C | S | M | m |
|----|-------|----------|---------|---|---|---|---|
<one row per PR; "review failed" rows included>

## Pending decisions (<count>)
<one entry per deferred checkpoint, clearly marked:
  PENDING — #<num>: post decision (<verdict>, <F> findings)
  PENDING — #<num>: intent was not grounded — re-run with intent text?>

## Per-PR reviews
<each PR's full Phase 4 terminal block, in list order>
```

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

On "Triage now": for each PR with findings, run the single-PR "Select findings to post" multiSelect followed by its "Post review" prompt, in list order. On "Report only": exit — pending decisions remain marked in the report for a later run.
