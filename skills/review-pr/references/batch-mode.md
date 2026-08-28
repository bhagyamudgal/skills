# Batch mode — reviewing multiple PRs in one run

Loaded by main at the start of Phase 1, and only when the user provides **2+ PR URLs** or asks to review **all open PRs**. A single-PR run never reaches any of this.

For "all open PRs", enumerate via `gh pr list --json number,url,title --limit 50`, print the list in the kickoff message, then start — no confirmation prompt (batch mode is unattended by design; a wrong list is visible in the report).

---

## Orchestration

- Main context is the **orchestrator** — oversight only. It never reviews a PR inline, regardless of `SIZE_MODE` (solo-main routing applies inside each subagent, not in main).
- Spawn **ONE `general-purpose` subagent PER PR**. Each subagent runs the single-PR flow (Phases 1–3) independently against its own PR and returns its Phase 4 terminal block as its result. Dispatch in parallel batches of 3–4.
- Subagents NEVER post to GitHub and NEVER ask questions. They return the complete surviving finding set, semantic verdict, and `IS_SELF_REVIEW` value to the orchestrator, which posts each review after every subagent has returned.

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

Do not post to GitHub and do not ask questions. Return your Phase 4 terminal block, `IS_SELF_REVIEW`, and the complete surviving finding payload the orchestrator needs to post.
```

---

## "Don't stop" semantics

The run continues unattended through the WHOLE list — batch mode implies the user may be away. Do NOT stop between PRs. Resolve review-only checkpoints as follows:

- Stop-and-ask intent gap → review with just the diff; tag that PR's report `intent not grounded — findings may be generic`.
- PR > 2000 lines → proceed with chunked review; note the size in that PR's report header.
- Completed review → queue every surviving finding for automatic posting. Queue a clean review for automatic approval, or for a comment when `IS_SELF_REVIEW=true`.
- A failed subagent doesn't stop the batch — record `<pr>: review failed (<reason>)` in the consolidated report and continue with the rest.

---

## Automatic posting

After every subagent returns, post each completed review in list order through the single-PR GitHub posting flow. For another author's PR, post all surviving findings with `REQUEST_CHANGES` and a clean review with `APPROVE`. For a self-review, post the complete result with `COMMENT`. Invoke `preflight-mutations` separately for each PR immediately before its first mutation, using the batch `/review-pr` request as the authorization source. Reconcile and record each result before moving to the next PR.

A posting failure never asks immediately. Record the exact partial GitHub state and the recovery choices from `github-posting.md` as `recovery-pending`, then continue with every untouched PR.

---

## Consolidated report

After automatic posting has attempted every completed review and recorded each current state, write ONE report document to `/tmp/review-pr-batch-<timestamp>.md` (and print it). Derive every posting-status entry from the reconciled result:

```
# Batch PR Review — <N> PRs (<date>)

| PR | Title | Approval | Verdict | C | S | M | m |
|----|-------|----------|---------|---|---|---|---|
<one row per PR; "review failed" rows included>

## Posting status
<one entry per PR: posted request-changes, posted approve, posted self-review comment, review failed, posting failed, or recovery-pending>

## Pending review context (<count>)
<one entry per review-only checkpoint that could not be resolved, such as:
  PENDING — #<num>: intent was not grounded — re-run with intent text?>

## Per-PR reviews
<each PR's full Phase 4 terminal block, in list order>
```

## Deferred posting recovery

After the report exists, walk every `recovery-pending` PR in list order through `github-posting.md` Step 7. Ask only the recovery question supported by that PR's recorded partial state. Reconcile the chosen action before advancing.

After all recovery choices settle, regenerate the same report path from the final reconciled results and print it once more. If the user leaves a recovery unanswered, preserve `recovery-pending` with the exact next action; later PRs and their posting evidence remain complete.
