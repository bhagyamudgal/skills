---
name: triage-board
description: Triage a project board in one pass. Find the candidate tickets, label each agent-ready or need-human, set priority and issue type, and calibrate estimates against approved anchors before any write.
disable-model-invocation: true
---

# Triage board

I fill the board fields that decide what gets worked on next: whether a coding agent can close a ticket unaided, how urgent it is, what kind of work it is, and how much of the owner's own time it will cost. I read, judge, and reconcile. `preflight-mutations` authorizes every write.

I work five concepts. I resolve each against the live board rather than assuming an ID, so I run on any project with this shape:

| Concept | Usual shape | Missing? |
|---|---|---|
| Triage label | Two repository labels, `agent-ready` and `need-human` | I show the name and color and ask once before creating |
| Priority | A single-select board field | I stop and name it |
| Estimate | A number board field | I stop and name it |
| Type | An org-level issue type, not a board field | I stop and name it |
| Release | An iteration board field that bounds the scope | I require an explicit scope instead |

Ordering matters. Scope, then calibration, then judgment, then authorization, then writes, then reconciliation. A judgment made before the calibration is approved is thrown away.

## 1. Resolve the board and the ledger's home

I read the project's fields, the repository's labels, the organization's issue types, and the requester's own login, and record the stable ID of each. I never carry an ID between runs; a board that gained a field or renamed an option would make a cached ID write to the wrong place.

Load `${CLAUDE_SKILL_DIR}/references/board-queries.md` now. It holds the exact queries, each with the assertion that proves it read everything.

I also settle **where the ledger lives** before anything else, because `preflight-mutations` blocks a multi-batch run that has no already-authorized durable home and is forbidden from creating one. I name an existing artifact the requester has authorized this run to write, or I ask for one. I do not invent a file to clear the gate.

The ledger carries one row per candidate and is the run's memory across interruption:

```markdown
| Item ID | Issue | Owner | Kind | Field | Current | Proposed | Basis | Status |
|---|---|---|---|---|---|---|---|---|
| <item ID> | #<n> | <login> | leaf / umbrella | label / priority / estimate / type | <value> | <value> | <evidence> | candidate / pending / landed / failed / skipped / reconcile-required / conflicted / excluded |
```

**Gate.** Every concept the run needs has a resolved ID, the requester's identity is known, and the ledger has an authorized home. Otherwise the run stops naming what is missing.

## 2. Fix the scope

With no argument I take every open issue where the requester is the **sole** assignee, on any iteration whose start date is later than today. An argument narrows that to one release, one status, or an explicit list of numbers.

I drop pull requests and draft items, which share the board with issues and carry none of the fields being set.

I apply the board's ownership policy without being asked. A co-assigned, unassigned, or ambiguously owned ticket is read-only, however wide my technical access is. I record every exclusion with its reason rather than dropping it silently, because a total that quietly omits items is worse than a smaller total that says what it left out.

**Gate.** The candidate set is exact, every excluded item carries a reason, and each candidate is a ledger row at `candidate`.

## 3. Confirm the calibration, then preview it

I ask **once**, in a single question, before judging the batch. `${CLAUDE_SKILL_DIR}/references/calibration.md` carries the defaults I propose: the estimate unit, scale, rounding and cap; worked anchors spanning the range; the priority rubric; and any project-specific priority lift the requester wants for this run.

The estimate unit defaults to **human active time**, which `${CLAUDE_SKILL_DIR}/references/calibration.md` defines and anchors.

Approving a rubric is not the same as approving a number. So I then estimate **three to five real tickets** from this scope, covering the smallest, the typical, the largest, and any umbrella, and show those with their reasoning and their subtotal. Only after the requester approves that preview do ledger rows move from `candidate` to `pending`. Without it the first applied number they ever see arrives after every write has landed.

A changed unit, scale, anchor, rubric, ownership boundary, or umbrella treatment invalidates every row not yet written.

**Gate.** The requester approved both the calibration and a preview against their own tickets.

## 4. Judge every candidate

I read each ticket's full body and record four values: the triage label, the priority, the estimate, and the type.

The triage label answers one question: **is the correct behavior already decided?** `${CLAUDE_SKILL_DIR}/references/triage-rubric.md` carries the five conditions that force `need-human` however well written a ticket is, and the wording tells that settle it cheaply. Difficulty never enters. A tedious ticket that touches three hundred files is `agent-ready` when its outcome is pinned; a one-line fix is `need-human` when nobody has said which line.

**Fan-out is by threshold, not by default.** Under about forty candidates I read inline. Above that I write the rubric to one file and give batches of about thirty to parallel readers, each returning only its verdicts. I re-use those same readers for any second pass rather than re-reading the bodies, since they already hold them.

Every batch gets a coverage diff against the list it was given. A reader that returns twenty-nine verdicts for thirty tickets has dropped one silently, and only the diff catches it.

**Gate.** Every candidate has all four values, and every batch covers its list exactly.

## 5. Authorize the writes

I invoke `preflight-mutations` with the board and field IDs, the item IDs, current and proposed values, the ownership policy, the approved calibration and preview, reversibility, the recovery plan, the invalidators, and the authoritative read-back plan.

**One card per action class, not one per run.** `preflight-mutations` splits a card by target and action, and this skill performs three distinct actions across two surfaces: repository labels, board field values, and organization issue types. Each gets its own card and its own read-back plan. Within a class, one card covers the whole batch rather than one item.

**Gate.** Every intended write sits under a current `ready` card for its action class.

## 6. Write, then prove it landed

I perform only the authorized writes, tee every response to a log, then re-read every touched field from the authoritative source and compare it field by field against the ledger.

Two failure modes make this mandatory rather than tidy, and `${CLAUDE_SKILL_DIR}/references/board-queries.md` carries the evidence for both: a board mutation can report success without persisting, and the issue search index both lags and truncates. So a zero exit code is never evidence, and labels are verified by reading the issue object rather than any list.

I grep the whole write log for failures rather than reading its tail, because a malformed value fails one row in the middle of a run that otherwise looks clean.

Every row then takes a terminal status from observed state:

- `landed`, `failed`, or `skipped` where the read-back settles it;
- `reconcile-required` where the read-back **cannot** establish whether the write landed. I stop that item, and I neither retry it nor call it `failed` until an authoritative query resolves it;
- `conflicted` where the read-back shows a value that changed after I measured it, meaning somebody edited the board during the run. I never overwrite it. I report both values and let the requester rule.

**Gate.** Every attempted write carries one of those statuses, taken from observed state and never from command output.

## 7. Report

I give the requester:

- counts by triage label, by priority, and by type;
- the estimate total **split by triage label**, because the two are not interchangeable. Hours sitting in `need-human` tickets have to be spent before an agent can start, so only the `agent-ready` subtotal predicts throughput;
- every ticket whose estimate hit the cap, named, since a cap hides its real size and usually means the ticket wants splitting;
- every `conflicted`, `reconcile-required`, `failed`, and `excluded` row; and
- any judgment I found genuinely close, so the requester can overturn it.

Totals come only from `landed` rows. Where read-back was unavailable I report intended values and the `reconcile-required` list, and I claim no confirmed total.

The run is done when every candidate has a terminal status and every reported total is reproducible from landed values.
