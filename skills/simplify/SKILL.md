---
name: simplify
description: Reduce unnecessary complexity in a completed code or workflow diff without changing intended behavior. Use after implementation and review, or when a fix grew beyond the request.
---

# Simplify

I make the smallest behavior-preserving cleanup that leaves the finished change easier to maintain. Less code, same behavior. That is the whole job.

## 1. Bind the change

I record the originating request, review baseline, changed paths, and current diff or content hash. I read the complete diff and the surrounding code for every cleanup I propose.

The cleanup scope is the current task diff. Unrelated pre-existing code stays untouched, and I say so as the gate. I do not wander.

## 2. Find removable complexity

I inspect only for these.

- Duplication the change introduced.
- Abstractions, branches, configuration, or error handling the request does not need.
- Dead imports, variables, functions, files, or indirection the change introduced.
- Control flow or naming that can turn clearer without changing the public contract.
- Added comments that fail the added-comment scan below.

I prefer deletion and direct code over a new helper. I reuse an existing local pattern when it removes a fork. I preserve required guards, evidence, recovery behavior, tests, and user-confirmed decisions.

### Added-comment scan

I inspect every comment the change adds. A comment stays only when it states a non-obvious WHY, a gotcha, a workaround, a constraint, or a reason the code cannot express itself. I delete on sight comments that narrate WHAT the code does, JSDoc on obvious functions, and section dividers.

Where the repository states its own comment rule, that rule governs and this list is its floor. Deleting these is part of this pass, not a suggestion for later.

Every proposed edit names what turns simpler and why observable behavior stays equivalent, and no comment the change adds is still a WHAT-comment, obvious-function JSDoc, or section divider. This scan blocks. The caller cannot report the work complete while one remains in the diff.

## 3. Apply and verify

I apply only cleanups whose equivalence the code and existing tests support. When a cleanup changes behavior, requirements, public output, persistence, authorization, or failure semantics, I return it as a separate proposal instead of applying it.

I re-run the checks my cleanup invalidated and compare the final diff with the originating request. When the cleanup changes content a completed review covered, I invalidate and rerun only that coverage through `converge-reviews`. A stale convergence result cannot verify the simplified diff. I report the edits I made, or `No simplification needed`, plus the exact verification results.

I call the diff done when it runs no broader than the request, every retained line has a task reason, and applicable checks still pass.
