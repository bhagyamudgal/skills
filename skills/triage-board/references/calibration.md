# Calibration: estimates, priority, type

Everything here is a **proposal**. Present it, take one confirmation or amendment, then apply it unchanged for the whole batch. Reusing a prior batch's anchors without reconfirming them is how two releases stop being comparable.

## Estimate unit: human active time

Count only the hours the owner is personally engaged. Deciding, writing the spec, reviewing the diff, testing in a browser, approving and watching a production run.

Two exclusions do the real work:

- **Implementation an agent absorbs does not count.** The agent writes the code; the owner reviews the result.
- **Elapsed and waiting time does not count.** A freeze window, a long migration, or a CI run is calendar time during which the owner works on something else.

The worked case that anchors the unit: a ticket needing one to two hours of deciding and specifying, whose implementation is four to five hours an agent does, is **3**.

Read that as a sum of two measured parts, never as an uplift. Deciding and specifying is the one to two hours. Reviewing what the agent produced, and testing it, is the rest. Both are hours the owner is personally engaged, so both count. Calling the difference a buffer is what lets an estimate inflate by half again on every ticket, and it makes the number unfalsifiable because no part of it can be checked. If the two parts do not add to the number, the number is wrong.

Scale: 0.5 steps, minimum 0.5, default cap 8. A ticket whose true active time exceeds the cap is written at the cap and **named in the report**, because a capped number and a genuine one are indistinguishable on a board.

### This basis moves numbers in both directions

That two-way movement is the test that a re-estimate is real rather than a rescale.

| Shape | Direction | Why |
|---|---|---|
| Heavy implementation, settled spec | Down | The owner only reviews. Extracting one helper and repointing three call sites is about 1. |
| Trivial code, open question | Up | The ruling is the deliverable. A three-option decision producing no code at all is about 1.5. |
| Empty body | Up | Writing the spec is entirely human. About 4, with nothing coded. |
| Large mechanical sweep | Flat to down | The cost is reviewing the diff, not producing it. Three hundred files is about 4. |
| Production run or freeze window | Down sharply | Mostly elapsed, not active. Size the approval and the watching, not the duration. |

### Anchors to propose

Adjust the wording to the project, keep the spread.

| Hours | Shape |
|---|---|
| 0.5 | A one-line change matching sibling sites already fixed |
| 1 | Delete a duplicated helper and repoint five call sites |
| 1.5 | A short ruling between recorded options, then a small fix |
| 2 | One missing query predicate plus one integration test |
| 3.5 | Two scope fixes plus a test that seeds a second tenant |
| 4 | Review a three-hundred-file mechanical diff, or write a spec from an empty body |
| 8 (cap) | A multi-PR program needing a freeze window and a queue sweep |

## Priority rubric

Three bands, on severity of consequence.

- **HIGH.** Customer-reported, or a user-facing bug that loses data, leaks one account's information to another, or makes something unusable at all.
- **MED.** Not critical, still important. Wrong numbers, blocked behavior, anything real that does not meet the HIGH bar.
- **LOW.** New feature requests, and small interface bugs with no impact on data or usability.

Two habits keep this consistent:

- **Score the mechanism, not today's blast radius.** A cross-account leak with zero affected rows is still a leak; the data can change tomorrow, the code will not.
- **Latent stays latent.** A defect needing a concurrent write or an unusual state to fire is not HIGH merely because its consequence would be severe.

**Project lifts are a run input, never policy.** A project may want one module always HIGH. Take that at invocation, apply it as stated, and record it in the report so a reader knows why a cosmetic bug in that module outranks a real break elsewhere. Do not carry a lift into the next run.

## Issue type

Derive from a conventional-commit prefix found **anywhere in the title**, not only at its start, matching `\[Support\]|\b(fix|feat|chore|perf|refactor|docs|test)(\([^)]+\))?:` and taking the **first** match in the title. The word boundary and the colon both matter: an unanchored `fix` also matches inside `prefix`, `hotfix` and `suffix`, so `chore: rewrite the prefix parser` would classify as a Bug. `[Support]` is an alternative in the same pattern rather than a separate rule, so a title carrying both resolves by position instead of falling through to the body heuristic. Boards routinely carry a release tag ahead of it, as in `[26.1]->[26.2] fix(planner): ...`, and a start-anchored match silently falls through to the body heuristic on every such ticket:

| Prefix | Type |
|---|---|
| `fix`, `[Support]` | Bug |
| `feat` | Feature |
| `chore`, `perf`, `refactor`, `docs`, `test` | Task |

With no prefix, derive from the body: a described defect is a Bug, a described new capability is a Feature, everything else is a Task.

Type is an organization-level issue type set by `updateIssue(issueTypeId)`. It is not a board field, and its IDs live in a different namespace from every field ID.

## Umbrellas and parents

Classify every parent exactly once, so no hour is counted twice:

- **direct**: estimate the parent itself and exclude its children from the same total;
- **derived**: sum the eligible children and exclude the parent; or
- **excluded**: leave it outside the total with a reason.

A coordination parent is usually `direct` and small. Its work is keeping the ordering current, and anything larger double-counts the children.
