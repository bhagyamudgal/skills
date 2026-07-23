---
name: executing-tickets-with-subagents
description: Use when a GitHub ticket/issue bundles multiple sub-tasks or fixes that will take hours, span context compactions, and ship as one reviewed PR — or when the user asks for subagent-driven execution, "the 4875 workflow", or proper progress tracking in the ticket.
---

# Executing Tickets with Subagents

## Overview

The main conversation is an **orchestrator only**: it holds decisions, dispatches subagents, triages their reports, and maintains durable state in files. It never implements, reviews, or QAs inline. Durable state lives on disk and GitHub — never in conversation memory, which compaction can erase at any moment.

## When to Use

- Ticket with 3+ sub-issues, a rolling PR, hours of work, human + bot review
- User asks to "work through these one by one and keep status updated"

NOT for single small fixes — the tracking overhead outweighs the work.

## Phase 0 — Intake

Before brainstorming, grilling, or asking the user anything:

1. **Fetch the full issue thread** — every comment and every attached image (`gh issue view <n> --comments`; download images and actually read them). Comments routinely override or extend the original body; an unread comment is a spec you don't have.
2. **Do your own codebase research first** — verify claims against the code before bringing questions to the user. Questions earn their place only after the thread and the code have both been read.

## Phase 1 — Lock, plan, instrument

1. **Explore** the code with parallel read-only agents; verify each sub-issue's claimed state in code first.
2. **Grill the user** (AskUserQuestion, concrete options, recommended-first): task order, PR strategy, done-bar per task, tracking method, anything user-owned (migrations, commit policy). Locked answers are law for every later dispatch.
3. **Spec then plan** (see superpowers:writing-plans): per-task briefs with exact code, locatable by symbol/content — line numbers rot.
4. **Instrument tracking** before task 1:
   - **Ledger** (e.g. `.superpowers/sdd/progress.md`) — THE recovery map, see contract below
   - `tasks/todo.md` checklist
   - **One editable GitHub checklist comment** on the issue (status + root cause per item; save its comment id in the ledger; update via `gh api ... -X PATCH -F body=@file`, verify by read-back)
   - Harness tasks (TaskCreate/TaskUpdate)

## Ledger contract

Written for a reader with **zero context** — assume the next writer remembers nothing. Update after EVERY wave, not at milestones. Must contain: per-task status with commit SHAs; the current NEXT ACTION stated imperatively; accumulated minor findings awaiting triage; standing process rules (permissions granted, environment quirks + fallbacks, QA credentials/data notes); locations of briefs/artifacts.

## Phase 2 — Per-task loop

1. **Brief to scratchpad**; if HEAD moved since planning, run an Explore **drift-check** and write an addendum (addendum wins; locate by symbol).
2. **Fresh implementer agent** — never implement in main context. Bug fixes are TDD (failing test first, watch it fail). Formatter before commit; type-check loop until clean; single conventional commit; push.
3. **Two-stage review, separate subagents** — one combined reviewer anchors on whichever lens it starts with; two fresh ones don't. Both verdicts are required; a report missing either is not a review:
   - **Stage 1 — spec compliance**: reviewer gets the task brief + diff — never the implementer's summary; agent reports are unverified claims — and verdicts against the ticket requirements: **Missing / Extra / Misunderstood**, with file:line evidence. Give it the *named risks* to verify.
   - **Stage 2 — code quality**: independent reviewer for correctness, error handling, tests that assert real behavior, and structure; findings ranked Critical / Important / Minor. AI-bot CLI review runs alongside.
4. **Triage every finding**: FIX-NOW (fix agent, then **re-review both stages until spec passes and quality approves** — a task with open Critical/Important findings is not complete) / DISMISS only with a verified rationale (check the locked design/brief first — reviewers re-litigate settled decisions) / DEFER (log in ledger minors).
5. **Browser QA agent** for UI tasks: records original data, restores it, proves restoration; artifacts to scratchpad only.
6. **Bookkeeping**: tick todo, PATCH checklist comment, TaskUpdate, ledger — then next task.

## Phase 3 — Endgame

1. **Final whole-branch review** from the *recomputed* merge-base (it moves; exclude generated files), hunting cross-task interactions no per-task reviewer could see, and triaging all ledger minors FIX-NOW / FOLLOW-UP / DROP.
2. Fix wave → reply-and-resolve every external review thread citing commit SHAs or rationale.
3. Update PR body to final state. Mark ready only with user approval; **watch CI on the final head** — drafts and merge conflicts silently skip `pull_request` workflows, so "no failures" may mean "never ran".
4. **Manual-QA handoff doc** — standard closing artifact for bundled bug-fix tickets. Per fixed item: link to the originating issue comment, what was wrong before vs what changed (plain language), and step-by-step testing instructions so the user can validate each fix.
5. **File follow-ups, never bundle them silently into the current PR**: small stray findings → ONE consolidated follow-up ticket; major findings → a dedicated issue each. Assign all of them to the user.

## Hard rules

| Rule | Why |
|---|---|
| Orchestrator never implements/reviews/QAs inline | Main context stays small; compaction loses less; fresh eyes per task |
| Ledger update after every wave | Compaction strikes without warning; the ledger is the only reliable resume point |
| Never run browser QA while an implementer edits the same app | Hot reload contaminates the session mid-test |
| Never blind-retry a mutating command (gh/API/git push) | Empty stdout ≠ failure; verify by read-back first or you double-post |
| Wedged agent → dispatch a fresh one | Re-nudging a stuck agent wastes more than restarting |
| Dispatch prompts are self-contained | Paths, env, locked decisions, verification commands, commit format, report format, environment-quirk fallbacks — the agent has no other context |
| Agent reports are raw data | SHAs, counts, file:lines, ran-vs-inspected; "should work" is not a report |
| User-owned territory (migrations, merges, un-drafting) → ask | One approval does not extend to the next category |

## Common mistakes

- **Subagents only for search, edits done inline** — the biggest regression; the loop's value is fresh implementer + independent reviewers per task.
- Treating todo.md as the recovery map — working notes are not a zero-context ledger with NEXT ACTION.
- Skipping the review wave because CI + review bot run on push — bots miss spec violations; give reviewers named risks.
- Merging spec + quality into one reviewer, or accepting a report with only one verdict — spec compliance and code quality are separate passes by separate subagents, and both must pass before the task closes.
- Trusting plan line numbers after other tasks land — drift-check, locate by content.
- Reporting "done" from type-check alone — the done-bar locked in Phase 1 decides (tests, browser QA, evidence).
