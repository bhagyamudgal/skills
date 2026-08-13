---
name: executing-tickets-with-subagents
description: Orchestrate ledger-tracked work through subagents. Use for a bundled GitHub ticket with 3+ sub-issues, a request for subagent-driven execution, resuming such a run after compaction, or explicit away/keep-going delegation even when only one task remains.
---

# Executing Tickets with Subagents

## Overview

The main conversation is an **orchestrator only**. Every edit, review, and QA pass runs in a dispatched subagent. Durable state lives on disk and GitHub — the two places compaction cannot reach.

## Select the run branch

- **Unattended:** When the user explicitly says they are stepping away and asks work to continue, read `${CLAUDE_SKILL_DIR}/references/unattended-scheduler.md` in full before the first dispatch. Its scheduling, transition, update, and handoff contract applies even to one task. Use the phases below only when the work is also a bundled GitHub ticket.
- **Bundled ticket:** Use the phases below for the ticket's intake, waves, and endgame.

**Gate:** record the selected branch in the ledger before dispatching work.

## Phase 0 — Intake

1. **Resume check** — if a ledger exists for this ticket, read it before anything else and execute its NEXT ACTION. The ledger is the only source of run state; conversation memory is not. Reconcile the four trackers (todo, checklist comment, harness tasks, ledger) before the next wave.
2. **Fetch the full issue thread** — read `${CLAUDE_SKILL_DIR}/../audit-ticket/references/ticket-evidence.md` in full, then fetch structured issue JSON with `gh issue view <n> --json number,title,body,author,createdAt,updatedAt,state,assignees,url,comments`. Build the source map from the issue body and every comment's `body`, `author`, `createdAt`, and `url`; download every attached image and actually read it. Comments routinely override or extend the original body; an unread comment is a spec you don't have.
3. **Research the codebase** — verify claims against the code before bringing questions to the user.

## Phase 1 — Lock, plan, instrument

1. **Explore** the code with parallel read-only agents. Produce a per-sub-issue verdict — already-done / partially-done / not-started — each with file:line evidence.
2. **Grill the user** (`grill-me`): task order, PR strategy, done-bar per task, tracking method, anything user-owned (migrations, commit policy). Grilling ends when every item above has a locked answer written into the ledger. Locked answers are law for every later dispatch.
3. **Spec then plan**: one brief per sub-issue, every sub-issue covered — each with exact code and 2-3 **named risks** the reviewer must check. Briefs locate by symbol; line numbers **drift** as tasks land. Then run `harden-plan` against the brief set before task 1.
4. **Instrument tracking** before task 1:
   - **Ledger** (e.g. `docs/<ticket>-progress.md`) — THE recovery map, see contract below
   - `tasks/todo.md` checklist
   - **One editable GitHub checklist comment** on the issue (status + root cause per item; save its comment id in the ledger; update via `gh api ... -X PATCH -F body=@file`). Immediately before creating it, invoke `preflight-mutations` with the exact issue URL, comment body, issue state/assignees, locked tracking decision, and planned read-back. Apply its result contract before continuing. Read back after every mutating command; retry only when the read-back shows no effect — empty stdout is not failure.
   - The harness todo list (`TodoWrite`)

## Ledger contract

Written for a reader with **zero context** — assume the next writer remembers nothing. Update after EVERY wave. Must contain: per-task status with commit SHAs; the current NEXT ACTION stated imperatively; accumulated deferred Moderate and Minor findings awaiting triage; standing process rules (permissions granted, environment quirks + fallbacks, QA credentials/data notes); locations of briefs/artifacts and the ticket source map.

## Phase 2 — The wave (one per task)

1. **Brief to scratchpad**; if HEAD moved since planning, run an Explore **drift-check** and write an addendum (addendum wins).
2. **Fresh implementer agent** — the orchestrator dispatches, the agent edits. Bug fixes are TDD (failing test first, watch it fail). Formatter before commit; type-check loop until green; single conventional commit. Immediately before the wave's first push, the implementer invokes `preflight-mutations` with the exact remote branch, local/upstream SHAs and commit range, PR base/head and dependencies, and the locked push permission. Apply its result contract before pushing. Dispatch prompts are self-contained: paths, env, locked decisions, verification commands, commit format, report format, environment-quirk fallbacks — the agent has no other context.
3. **Two-stage review, separate subagents** — one combined reviewer anchors on whichever lens it starts with; two fresh ones don't. A review is two reports, one per stage:
   - **Stage 1 — spec compliance**: reviewer gets the task brief + diff, and the named risks to verify. Its inputs are exactly those two. Verdicts against the ticket requirements: **Missing / Extra / Misunderstood**, with file:line evidence.
   - **Stage 2 — code quality**: independent reviewer for correctness, error handling, tests that assert real behavior, and structure; findings ranked Critical / Serious / Moderate / Minor. `parallel-review` runs alongside and covers style and convention; Stage 1 is what catches spec violations.
4. **Triage every finding**: FIX-NOW (fix agent, then **re-review both stages until spec passes and quality approves** — a task closes at zero open Critical and Serious findings) / DISMISS only with a verified rationale (check the locked design/brief first — reviewers re-litigate settled decisions) / DEFER (Moderate and Minor only; log in ledger minors).

   Reports arrive **unverified** — SHAs, counts, file:lines, and ran-vs-inspected are the evidence that clears them.
5. **`browser-qa`** for UI tasks: records original data, restores it, proves restoration; artifacts to scratchpad only. Run it between waves, with no implementer active — hot reload contaminates the session mid-test.
6. **Bookkeeping**: tick `tasks/todo.md`; immediately before each wave's checklist PATCH, invoke `preflight-mutations` with the exact issue and comment IDs, replacement body, current comment version/body, locked tracking permission, and read-back, then apply its result contract; update the harness todo list and ledger before the next task.

A **wedged** agent gets replaced, not re-nudged: dispatch a fresh one.

## Phase 3 — Endgame

1. **Final whole-branch review** from the *recomputed* merge-base (it moves; exclude generated files). Report every cross-task interaction found, or state explicitly that none were. Triage **all** ledger minors FIX-NOW / FOLLOW-UP / DROP.
2. Fix pass → `fix-pr-review` to reply-and-resolve every external review thread citing commit SHAs or rationale.
3. Immediately before updating the PR body or marking it ready, invoke `preflight-mutations` for that external-metadata batch with the exact PR URL, current base/head SHA and draft state, final body delta, update/ready actions, dependent PRs/workflows, and the user's ready approval. Apply its result contract before updating the body or ready state. **Watch CI on the final head** — drafts and merge conflicts silently skip `pull_request` workflows, so "no failures" may mean "never ran". Confirm the workflow ran on the final head, then confirm it passed.
4. **Manual-QA handoff doc** — standard closing artifact for bundled bug-fix tickets. Per fixed item: link to the originating issue comment, what was wrong before vs what changed (plain language), and step-by-step testing instructions so the user can validate each fix.
5. **Every stray finding leaves as its own ticket**: small ones → ONE consolidated follow-up ticket; major findings → a dedicated issue each. Before composing any rewritten, split, or follow-up issue, reread `${CLAUDE_SKILL_DIR}/../audit-ticket/references/ticket-evidence.md`; its provenance graph and rendered closeout gate apply to the original and every successor. Immediately before the first write, invoke `preflight-mutations` once for the complete batch: exact repository; current original issue state and guards; the original issue's complete investigation update or comment payload; every successor create payload; original-to-successor, successor-to-predecessor, and dependency-relevant sibling links; source finding and evidence IDs; assignees; authorization; and the rendered issue-and-image read-back plan. Apply its result contract, then execute only the writes in that batch. Re-fetch and reread the rendered issue set and images against the source map before reporting the tickets complete.

## Hard rules

| Rule | Why |
|---|---|
| Wedged agent → dispatch a fresh one | Re-nudging a stuck agent wastes more than restarting |
| User-owned territory (migrations, merges, un-drafting) → ask | One approval does not extend to the next category |
