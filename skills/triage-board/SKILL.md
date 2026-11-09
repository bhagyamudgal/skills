---
name: triage-board
description: Triage a project board in one pass. Find the candidate tickets, label each agent-ready or need-human, set priority and issue type, and calibrate estimates against approved anchors before any write.
disable-model-invocation: true
---

# Triage board

I fill the board fields that decide what gets worked on next: whether a coding agent can close a ticket unaided, how urgent it is, what kind of work it is, and how much of the owner's own time it will cost. I read, judge, and reconcile. `preflight-mutations` authorizes every write.

I resolve five concepts against the live board instead of assuming IDs, so I run on any project with this shape:

| Concept | Usual shape | Missing? |
|---|---|---|
| Triage label | Two repository labels, `agent-ready` and `need-human` | I raise a label-bootstrap card before the gate, below |
| Priority | A single-select board field | I stop and name it |
| Estimate | A number board field | I stop and name it |
| Type | An org-level issue type, not a board field | I stop and name it |
| Release | An iteration board field that bounds the scope | I require an explicit scope instead |

The order is scope, calibration, judgment, authorization, writes, reconciliation. I discard any judgment made before the calibration is approved.

## 1. Resolve the board and the ledger's home

I settle which board this is first, because nothing else in section 1 can start without it. A board is an owner plus a number. Project numbers restart per owner, so a bare number names a different board under every account. An argument decides the board only when it carries both or is a URL I parse into both. With no argument I list the boards linked to the repository I am running in and keep the open ones:

- exactly one open board, I take it and say which;
- more than one, I ask, showing each number and title;
- none, I ask for the owner and project number, since the board may be owned by the organization and linked to no repository.

I never guess from the working directory or from a board I used before. A repository with two open boards is common, so asking is a normal outcome, not a failure.

I then read the project's fields, the repository's labels, the organization's issue types, and the authenticated login, and record each stable ID. The login belongs to the token, not necessarily the requester, so I confirm they are the same person before the ownership boundary keys on it. A bot or shared credential stops the run. I never carry an ID between runs, because a board that gained a field or renamed an option would send a cached ID's write to the wrong place.

Load `${CLAUDE_SKILL_DIR}/references/board-queries.md` now. It holds the exact queries, each with the assertion that proves it read everything.

**A missing label gets its own card.** Creating a repository label is a shared-state write, so a bare yes from the requester does not authorize it. When either label is absent I raise a label-creation card through `preflight-mutations` naming both labels, their colors and every repository in scope, create only on a `ready` verdict, then re-read the repository's labels and record the resulting IDs. It is a separate card from the label edits in section 5: the target is the repository rather than an issue, and the reversibility differs.

I also settle where the ledger lives before anything else. `preflight-mutations` blocks a multi-batch run with no already-authorized durable home and may not create one. I name an existing artifact the requester has authorized this run to write, or I ask for one. I never invent a file to clear the gate.

The ledger is the run's memory across interruption. It has one row per candidate field, keyed by `Field`, not one per candidate. Each candidate takes four writes across three action classes that fail independently, so one status per candidate would hide a failed write or drop a landed estimate from the landed-only totals. Each row carries its own current value, proposed value, basis, and status. A partial run keeps its landed rows and re-cards only the pending ones, the resume shape `preflight-mutations` expects:

```markdown
| Item ID | Issue | Owner | Kind | Field | Current | Proposed | Basis | Status |
|---|---|---|---|---|---|---|---|---|
| <item ID> | #<n> | <login> | leaf / umbrella | label / priority / estimate / type | <value> | <value> | <evidence> | candidate / pending / landed / failed / skipped / reconcile-required / conflicted / excluded |
```

An excluded item gets exactly one row, not four: `Field: none`, empty `Current` and `Proposed`, the exclusion reason in `Basis`, and `Status: excluded`. Without that row an interrupted run loses the reasons section 2 requires and reports a different exclusion count on resume than on the first pass.

**Gate.** The board is named rather than inferred, every concept the run needs has a resolved ID, the requester's identity is known, and the ledger has an authorized home. Otherwise the run stops naming what is missing.

## 2. Fix the scope

With no argument I take every open issue where the requester is the **sole** assignee, on any iteration in the board's live `iterations` list. That list holds the running iteration and every future one, so I triage work already underway too. A completed iteration sits in a separate list, and I reach it only when the requester names it. An argument narrows that to one release, one status, or an explicit list of numbers.

I drop pull requests and draft items, which share the board with issues and carry none of the fields being set.

I apply the board's ownership policy unprompted. A co-assigned, unassigned, or ambiguously owned ticket is read-only whatever my technical access. I record every exclusion with its reason and never drop one silently.

**Gate.** The candidate set is exact, every excluded item carries a reason, and each candidate is a ledger row at `candidate`.

## 3. Confirm the calibration, then preview it

I ask **once**, in a single question, before judging the batch. `${CLAUDE_SKILL_DIR}/references/calibration.md` carries the defaults I propose: the estimate unit, scale, rounding and cap; worked anchors spanning the range; the priority rubric; and any project-specific priority lift the requester wants for this run.

The estimate unit defaults to human active time, which `calibration.md` defines and anchors.

An approved rubric is not an approved number. So I then estimate three to five real tickets from this scope, covering the smallest, the typical, the largest, and any umbrella, and show them with their reasoning and subtotal. A scope with fewer than three candidates previews all of them. A scope with none skips calibration, judgment, and every write, and goes straight to a report with zero totals and its exclusion list. Ledger rows move from `candidate` to `pending` only after the requester approves the preview. Without it, the first applied number they see arrives after every write has landed.

A changed unit, scale, anchor, rubric, ownership boundary, or umbrella treatment invalidates every row not yet written.

**Gate.** The requester approved both the calibration and a preview against their own tickets.

## 4. Judge every candidate

I read each ticket's full body and record four values: the triage label, the priority, the estimate, and the type.

The triage label answers one question: **is the correct behavior already decided?** `${CLAUDE_SKILL_DIR}/references/triage-rubric.md` carries the five conditions that force `need-human` however well written a ticket is, and the wording tells that settle it cheaply. Difficulty never enters. A tedious ticket that touches three hundred files is `agent-ready` when its outcome is pinned; a one-line fix is `need-human` when nobody has said which line.

**Fan-out is by threshold, not by default.** Under 40 candidates I read inline. At 40 or more I write the rubric to one file and give batches of 30 to parallel readers, each returning only its verdicts. I reuse those readers for any second pass, since they already hold the bodies.

During any wait longer than 10 minutes anywhere in the run, such as parallel readers or API pacing, I post a one-line status, attended or not.

Every batch gets a coverage diff against the list it was given. A reader that returns twenty-nine verdicts for thirty tickets has dropped one silently, and only the diff catches it.

**Gate.** Every candidate has all four values, and every batch covers its list exactly.

## 5. Authorize the writes

I invoke `preflight-mutations` with the board and field IDs, the item IDs, current and proposed values, the ownership policy, the approved calibration and preview, reversibility, the recovery plan, the invalidators, and the authoritative read-back plan.

**One card per action class, not one per run.** `preflight-mutations` splits a card by target and action, and this skill performs three distinct actions across two surfaces: repository labels, board field values, and organization issue types. Each gets its own card and its own read-back plan. Within a class, one card covers the whole batch rather than one item.

**Gate.** Every intended write sits under a current `ready` card for its action class.

## 6. Write, then prove it landed

I perform only the authorized writes, tee every response to a log, then re-read every touched field from the authoritative source and compare it field by field against the ledger.

A board mutation can report success without persisting, and the issue search index lags and truncates. `${CLAUDE_SKILL_DIR}/references/board-queries.md` carries the evidence for both. So a zero exit code is never evidence, and I verify labels by reading the issue object, never a list.

I grep the whole write log for failures rather than reading its tail, because a malformed value fails one row in the middle of a run that otherwise looks clean.

Every row then takes a terminal status from observed state:

- `landed`, `failed`, or `skipped` where the read-back settles it;
- `reconcile-required` where the read-back **cannot** establish whether the write landed. I stop that item, and I neither retry it nor call it `failed` until an authoritative query resolves it;
- `conflicted` where the read-back shows a value that changed after I measured it, meaning somebody edited the board during the run. I never overwrite it. I report both values and let the requester rule.

**Gate.** Every attempted write carries one of those statuses, taken from observed state and never from command output.

## 7. Report

I give the requester:

- counts by triage label, by priority, and by type;
- the estimate total split by triage label, because only the `agent-ready` subtotal predicts throughput. `need-human` hours must be spent before an agent can start;
- every ticket whose estimate hit the cap, named, since a cap hides its real size and usually means the ticket wants splitting;
- every `conflicted`, `reconcile-required`, `failed`, and `excluded` row; and
- any judgment I found genuinely close, so the requester can overturn it.

Totals come only from `landed` rows. Where read-back was unavailable I report intended values and the `reconcile-required` list, and I claim no confirmed total.

The run is done when every candidate has a terminal status and every reported total is reproducible from landed values.
