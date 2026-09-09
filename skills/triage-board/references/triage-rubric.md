# Triage rubric: agent-ready or need-human

## The one question

**Is the correct behavior already decided?**

Yes, so a coding agent can close it unaided: `agent-ready`.
No: `need-human`.

The label marks decidedness, never difficulty. A ticket that rewrites three hundred files is `agent-ready` when its outcome is pinned. A one-line change is `need-human` when nobody has said which line.

## Five conditions that force need-human

However well written a ticket is, any one of these makes it `need-human`.

1. **An open product or commercial decision.** The body offers two or more end behaviors and picks none, or says outright that a choice is a product decision, needs a ruling, or is not the author's to take.
2. **A live production data run.** Closing it means running a repair, backfill, migration, or DDL against production, which needs a human to approve and watch.
3. **A spec that exists only as screenshots or a customer report, with no traced root cause.** No file, line, or mechanism is named. An empty body is the extreme case and is common in old tickets.
4. **A parent or epic whose job is coordination**, or work spanning many pull requests that needs scheduling judgment: a freeze window, timing against the open-PR queue, or a merge order.
5. **It cannot be completed today.** Two shapes, both decided but not closable:
   - waiting on something outside the repository, such as a dependency publishing a release, a license, a credential being minted, or a settings change only an admin can make;
   - sequenced behind another ticket, most often a data repair that has to run first.

Condition 5 is the one people forget. Those tickets flip to `agent-ready` the moment their blocker clears, often with no edit to the ticket at all.

## Wording tells

Most repositories converge on a house style that states decidedness outright. Read for it before reasoning from scratch.

**Decided.** A section naming one outcome: "What should happen instead", "Done looks like", "Acceptance", "Fix direction", "Suggested fix". One outcome is the test, not the heading.

**Not decided.** "What needs deciding", "Decide before coding", "needs product input", "needs a ruling before a fix", "Two decisions are needed", "Either is acceptable", "Pick one", "Options to consider", "Do not fix this first", "verify with PM".

## The distinction that decides most close calls

Two **implementation routes** to the same stated outcome is still decided. "Either throw or roll the insert back" reaches one contract by two means, so an agent picks one: `agent-ready`.

Two **end behaviors** with no choice made is not decided. "Either fall back to live data with a note, or render an explicit empty state. Pick one and apply it to both consumers" leaves the user-visible result open: `need-human`.

## An escape hatch is not a decision

Acceptance criteria that read "fix it, or record why it should not be fixed" leave the outcome open. Treat as `need-human`. Say so in the reason, because a reader may disagree and the ticket is one sentence away from being `agent-ready`.

## Labels go stale, so re-run rather than trust

A `need-human` becomes `agent-ready` the moment its decision is recorded on the issue, and nothing updates the label when that happens. Re-judge the whole scope on each run instead of skipping the already-labeled. Report any verdict that flipped since last time.

## Reporting

Give every verdict a reason of at most fifteen words. For `need-human`, name which of the five conditions applies and quote the phrase from the body where one exists. For `agent-ready`, name the section that settles it. A verdict without a reason cannot be overturned by a reader who disagrees.
