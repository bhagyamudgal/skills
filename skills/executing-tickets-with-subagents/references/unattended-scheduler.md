# Unattended Scheduler

Apply this branch when the user explicitly steps away and asks work to continue. The parent skill's ledger is the sole source of run state; conversation memory, harness tasks, and status messages are projections of it.

## Kick off the run

1. Read the existing ledger. If this run has none, create the parent skill's ledger before dispatching.
2. Record the ordered task list, dependencies, acceptance criteria, authority boundaries, and an imperative next action.
3. Reserve main for orchestration, select the first runnable task, and inspect the currently available worker slots excluding main:
   - When one or more slots are available, set `worker_pool` once to the smaller of three and that availability. Record it and keep it fixed; released slots restore capacity within the pool but never enlarge it.
   - When zero slots are available, leave `worker_pool` unset, record the selected task as `waiting-capacity` with no active owner and `capacity_attempt: 1`, and wait for the next observed worker-slot state change. Retry initialization exactly once for that task. If availability is then nonzero, fix the pool at the smaller of three and that availability, then record `waiting-capacity → ready` while preserving `capacity_attempt: 1`. Its next dispatch rejection consumes attempt 2 and blocks that task for this run. If availability remains zero, record `capacity_attempt: 2`, mark only that task `blocked for this run`, select the next runnable task, and apply the same bounded initialization path. Never block other runnable tasks from one task's capacity attempts.
4. Give a task a mutation owner only after its dispatch succeeds. Independent reviewers may inspect that owner's result read-only. Apply the parent skill's wedged-owner retirement contract before `active → ready`; a replacement becomes the owner only after terminal or interrupt evidence proves the prior owner inactive and its worktree/diff location is preserved.
5. Send the kickoff update with the fixed pool size and first runnable tasks, or the failed-initialization blocker with both attempts, plus authority boundaries and the next action.

**Gate:** the ledger can reconstruct every task, dependency, state, active owner, per-task pool initialization attempt, authority boundary, and next action without conversation context; `worker_pool` remains unset until nonzero capacity fixes it, and each task receives at most one initialization retry.

## Run the scheduler

Repeat until no runnable task remains:

1. Select ready tasks in dependency order, up to the recorded pool limit.
2. Attempt one self-contained dispatch for each selected task. After a dispatch succeeds, record `ready → active` and its owner. On a capacity rejection, record `ready → waiting-capacity`, no active owner, and the capacity attempt described below.
3. On every worker result, record the transition and evidence before dispatching replacement work:
   - `active → verified` only after the task's applicable `done` lanes pass;
   - `active → ready` when a recoverable failure has a named next attempt;
   - `active → blocked` when authority, evidence, dependency, or the bounded capacity policy prevents further work in this run.
4. Continue other runnable tasks when one task blocks.

Apply the governing global unattended authority contract to commits, pushes, PRs, merges, destructive actions, irreversible actions, and schema mutations. Queue any action outside that authority with exact ready-to-run instructions.

**Gate:** every task transition is in the ledger, every active task has exactly one owner, every waiting-capacity task has none, and no dispatch exceeds the kickoff-fixed pool.

## Bound capacity failures

A dispatcher capacity rejection consumes one of two attempts for that task. Pool initialization binds the same two-attempt rule to the selected runnable task as described at kickoff.

1. Record the first rejection, its time, `capacity_attempt: 1`, state `waiting-capacity`, and no active owner; wait for the next observed worker-slot state change.
2. Retry exactly once after that state change. During pool initialization, a nonzero result records `waiting-capacity → ready`; the later successful dispatch records `ready → active` and the new owner. For an already fixed pool, success records `waiting-capacity → active`. On rejection, record `capacity_attempt: 2` while retaining no active owner.
3. If the retry is also rejected, mark the task `blocked for this run`, preserve both attempts, and continue other runnable tasks.

A capacity retry is event-driven: do not poll, nudge the rejected dispatch, or create another retry. A worker's task failure is not a capacity rejection and follows the task's ordinary recovery policy.

**Gate:** no task has more than two capacity attempts across its initialization or dispatch path, every capacity wait has no active owner, and every capacity-blocked record names both attempts.

## Surface material updates

Update the ledger after every transition. Message the user only for:

- kickoff;
- a task completion and its verification result;
- a new blocker or authority boundary;
- a materially changed plan; or
- the final handoff.

Do not send a user-facing update for routine dispatches, unchanged waits, or ledger-only bookkeeping.

## Maintain the morning handoff

Keep one current `Morning handoff` section in the ledger:

```markdown
## Morning handoff

- **Completed and verified:** <task → evidence>
- **Active owners:** <task → owner and current step>
- **Blocked:** <task → blocker; include both capacity attempts when applicable>
- **Pending decisions:** <decision → impact and safe default used, if any>
- **Uncommitted work:** <paths or commits → why not committed>
- **Opened PRs:** <URL → head and verification state>
- **NEXT ACTION:** <one imperative action naming its target>
```

Refresh this section after every transition so interruption never leaves a stale handoff. The final user update summarizes it; the ledger remains authoritative.

**Done:** every task is verified or explicitly blocked for the run, no runnable task remains, and the morning handoff matches the ledger's task records.
