---
name: simplify
description: Reduce unnecessary complexity in a completed code or workflow diff without changing intended behavior. Use after implementation and review, when done requires its cleanup pass, or when a fix grew beyond the request. Do not use to redesign requirements or expand scope.
---

# Simplify

Make the smallest behavior-preserving cleanup that leaves the completed change easier to maintain.

## 1. Bind the change

Record the originating request, review baseline, changed paths, and current diff or content hash. Read the complete diff and the surrounding code for every proposed cleanup.

**Gate:** the cleanup scope is the current task diff; unrelated pre-existing code stays untouched.

## 2. Find removable complexity

Inspect only for:

- duplication introduced by the change;
- abstractions, branches, configuration, or error handling the request does not need;
- dead imports, variables, functions, files, or indirection introduced by the change;
- control flow or naming that can become clearer without changing the public contract; and
- added comments that fail the repository's comment rule.

Prefer deletion and direct code over a new helper. Reuse an existing local pattern when it removes a fork. Preserve required guards, evidence, recovery behavior, tests, and user-confirmed decisions.

**Gate:** every proposed edit names what becomes simpler and why observable behavior remains equivalent.

## 3. Apply and verify

Apply only cleanups whose equivalence is supported by the code and existing tests. If a cleanup changes behavior, requirements, public output, persistence, authorization, or failure semantics, return it as a separate proposal instead of applying it.

Re-run the checks invalidated by the cleanup and compare the final diff with the originating request. When the cleanup changes content covered by a completed review, invalidate and rerun only that coverage through `converge-reviews`; a stale convergence result cannot verify the simplified diff. Report the edits made, or `No simplification needed`, plus the exact verification results.

**Done:** the final diff is no broader than the request, every retained line has a task reason, and applicable checks still pass.
