---
name: executing-tickets-with-subagents
description: Orchestrate a bundled GitHub ticket through subagents — one wave per sub-task, ledger-tracked. Use when a ticket carries 3+ sub-issues shipping as one reviewed PR, when the user asks for subagent-driven execution, or when resuming such a run after a compaction.
---

# Executing Tickets with Subagents

## Overview

The main conversation is an **orchestrator only**. Every edit, review, and QA pass runs in a dispatched subagent. Durable state lives on disk and GitHub — the two places compaction cannot reach.

## Phase 0 — Intake

1. **Resume check** — if a ledger exists for this ticket, read it before anything else and execute its NEXT ACTION. The ledger is the only source of run state; conversation memory is not. Reconcile the four trackers (todo, checklist comment, harness tasks, ledger) before the next wave.
2. **Fetch the full issue thread** — every comment and every attached image (`gh issue view <n> --comments`; download images and actually read them). Comments routinely override or extend the original body; an unread comment is a spec you don't have.
3. **Research the codebase** — verify claims against the code before bringing questions to the user.

## Phase 1 — Lock, plan, instrument

1. **Explore** the code with parallel read-only agents. Produce a per-sub-issue verdict — already-done / partially-done / not-started — each with file:line evidence.
2. **Grill the user** (`grill-me`): task order, PR strategy, done-bar per task, tracking method, anything user-owned (migrations, commit policy). Grilling ends when every item above has a locked answer written into the ledger. Locked answers are law for every later dispatch.
3. **Spec then plan**: one brief per sub-issue, every sub-issue covered — each with exact code and 2-3 **named risks** the reviewer must check. Briefs locate by symbol; line numbers **drift** as tasks land. Then run `harden-plan` against the brief set before task 1.
4. **Instrument tracking** before task 1:
   - **Ledger** (e.g. `docs/<ticket>-progress.md`) — THE recovery map, see contract below
   - `tasks/todo.md` checklist
   - **One editable GitHub checklist comment** on the issue (status + root cause per item; save its comment id in the ledger; update via `gh api ... -X PATCH -F body=@file`). Read back after every mutating command; retry only when the read-back shows no effect — empty stdout is not failure.
   - The harness todo list (`TodoWrite`)

## Ledger contract

Written for a reader with **zero context** — assume the next writer remembers nothing. Update after EVERY wave. Must contain: per-task status with commit SHAs; the current NEXT ACTION stated imperatively; accumulated deferred Moderate and Minor findings awaiting triage; standing process rules (permissions granted, environment quirks + fallbacks, QA credentials/data notes); locations of briefs/artifacts.

## Phase 2 — The wave (one per task)

1. **Brief to scratchpad**; if HEAD moved since planning, run an Explore **drift-check** and write an addendum (addendum wins).
2. **Fresh implementer agent** — the orchestrator dispatches, the agent edits. Bug fixes are TDD (failing test first, watch it fail). Formatter before commit; type-check loop until green; single conventional commit; push. Dispatch prompts are self-contained: paths, env, locked decisions, verification commands, commit format, report format, environment-quirk fallbacks — the agent has no other context.
3. **Two-stage review, separate subagents** — one combined reviewer anchors on whichever lens it starts with; two fresh ones don't. A review is two reports, one per stage:
   - **Stage 1 — spec compliance**: reviewer gets the task brief + diff, and the named risks to verify. Its inputs are exactly those two. Verdicts against the ticket requirements: **Missing / Extra / Misunderstood**, with file:line evidence.
   - **Stage 2 — code quality**: independent reviewer for correctness, error handling, tests that assert real behavior, and structure; findings ranked Critical / Serious / Moderate / Minor. `parallel-review` runs alongside and covers style and convention; Stage 1 is what catches spec violations.
4. **Triage every finding**: FIX-NOW (fix agent, then **re-review both stages until spec passes and quality approves** — a task closes at zero open Critical and Serious findings) / DISMISS only with a verified rationale (check the locked design/brief first — reviewers re-litigate settled decisions) / DEFER (Moderate and Minor only; log in ledger minors).

   Reports arrive **unverified** — SHAs, counts, file:lines, and ran-vs-inspected are the evidence that clears them.
5. **`browser-qa`** for UI tasks: records original data, restores it, proves restoration; artifacts to scratchpad only. Run it between waves, with no implementer active — hot reload contaminates the session mid-test.
6. **Bookkeeping**: tick `tasks/todo.md`, PATCH the checklist comment, update the harness todo list, write the ledger — then next task.

A **wedged** agent gets replaced, not re-nudged: dispatch a fresh one.

## Phase 3 — Endgame

1. **Final whole-branch review** from the *recomputed* merge-base (it moves; exclude generated files). Report every cross-task interaction found, or state explicitly that none were. Triage **all** ledger minors FIX-NOW / FOLLOW-UP / DROP.
2. Fix pass → `fix-pr-review` to reply-and-resolve every external review thread citing commit SHAs or rationale.
3. Update PR body to final state. Mark ready only with user approval; **watch CI on the final head** — drafts and merge conflicts silently skip `pull_request` workflows, so "no failures" may mean "never ran". Confirm the workflow ran on the final head, then confirm it passed.
4. **Manual-QA handoff doc** — standard closing artifact for bundled bug-fix tickets. Per fixed item: link to the originating issue comment, what was wrong before vs what changed (plain language), and step-by-step testing instructions so the user can validate each fix.
5. **Every stray finding leaves as its own ticket**: small ones → ONE consolidated follow-up ticket; major findings → a dedicated issue each. Assign all of them to the user.

## Hard rules

| Rule | Why |
|---|---|
| Wedged agent → dispatch a fresh one | Re-nudging a stuck agent wastes more than restarting |
| User-owned territory (migrations, merges, un-drafting) → ask | One approval does not extend to the next category |
