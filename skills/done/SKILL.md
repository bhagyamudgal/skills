---
name: done
description: MANDATORY post-task verification. Fire before reporting ANY task complete — including single-line edits and "trivial" fixes.
---

# Post-Task Verification (/done)

## Workflow

Every step is **blocking**: the task is not complete until the last one runs clean.

### Step 1: Type Check

Run `/fix-ts-errors` — this runs the workspace type-check and loops until it exits 0.

If the task only touched a specific app, you may scope the first pass (`--filter=frontend` or `--filter=backend`), but always run the full check at least once.

If you already ran `/fix-ts-errors` during implementation, run it again — new issues may have been introduced.

**Proceed to Step 2 when the type-check reports zero errors.**

### Step 2: Parallel Code Review

Run `/parallel-review`.

Fix every critical and serious finding, then re-run `/parallel-review` until it returns zero of both. List every moderate and minor finding with one line each: fixed, or why deferred.

Re-run `/fix-ts-errors` after the fixes.

### Step 3: Simplify

Run `/simplify` — this reviews changed code for reuse, quality, and efficiency.

Apply every suggested improvement, or state why one was rejected. Re-run `/fix-ts-errors` after changes.

#### Comment Scan (mandatory — blocking)

Run `git diff` on the changed code and inspect **every ADDED comment**. A comment may stay only if it states a non-obvious WHY — a gotcha, a workaround, a constraint, or a reason the code cannot express itself.

Delete on sight:

- Comments that narrate WHAT the code does
- JSDoc on obvious functions
- Section dividers

**Do not call the task done while any such comment remains in the diff.** Deleting them is part of this step, not a suggestion for later.

### Step 4: Verify Correctness

1. Restate the original request as a checklist; account for every item against the final diff
2. If tests cover the changed code, run them — this step ends when they pass

### Step 5: Report

Roll-call all six steps — one line each, in order, naming the step and either its result or `skipped, because <reason>`. A step missing from the list is a step you did not run.

- **Type check**: errors found, errors fixed, exit 0
- **Parallel review**: critical/serious counts (must be 0), moderate/minor fixed or deferred
- **Simplify**: what changed, plus comments deleted in the scan
- **Verify correctness**: checklist items accounted for, tests run and their result
- **Report**: this roll-call
- **Commit**: committed, or variants printed

Close with the final status: clean, or the remaining concerns.

### Step 6: Commit

Run `/git-commit` if the user asked to commit, or the task is a discrete unit of work. Otherwise print the two message variants and stop.
