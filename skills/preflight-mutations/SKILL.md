---
name: preflight-mutations
description: Prepare or block a batch that will change shared or remote state, published Git history, production-like data, live services, or off-box copies. Use immediately before issue, PR, board, publication, production UI, service, or published-history mutations. Do not use for read-only work, isolated worktree edits, or unpublished local commits.
---

# Preflight Mutations

Resolve permission, current state, dependencies, and recovery before a shared-state write. This skill produces a decision record; it never performs the mutation.

## 1. Define the mutation batch

Record one batch whose items share the same authorization and guards. Split actions with different targets, owners, environments, reversibility, or confirmation requirements into separate cards.

Render a simple card inline. For a multi-step or multi-batch run, persist it only in an existing artifact the user has already authorized this workflow to write. Do not create a file, comment, issue, or other external artifact merely to store a preflight.

```markdown
### Mutation card

- **Surface / environment:** <system and local | staging | production | shared>
- **Action:** <exact mutation verb and delta; no combined “update as needed” language>
- **Targets:** <stable IDs, URLs, refs, fields, recipients, or services>
- **Ownership policy:** <governing policy and owner/assignee/author/environment boundary>
- **Authorization source:** <user request or later explicit confirmation, quoted narrowly>
- **Current guards:** <state, base/head SHA, version, field, environment, or other compare-before-write facts>
- **Dependencies / consumers:** <direct dependencies; transitive consumers when destructive or history-rewriting>
- **Preview / exclusions:** <proposed delta, blast radius, and what will not change>
- **Reversibility:** reversible | compensating-only | irreversible
- **Recovery plan:** <undo, backup, compensation, or explicit absence>
- **Invalidators:** <facts that make this preflight stale>
- **Read-back plan:** <authoritative post-write query and expected result>
- **Batch items:** <stable item ID → pending | landed | failed | skipped | reconcile-required>
- **Verdict:** ready | confirmation-required | blocked
- **Next action:** <one action permitted by the verdict>
```

**Gate:** action, targets, environment, and batch-item IDs are exact enough that another agent cannot select a broader resource by inference; a multi-step or multi-batch card has an authorized durable home.

Name every target and guarded dependency by stable ID in **Read-back plan**; do not collapse them into “all targets,” “consumers,” or another referential phrase.

## 2. Resolve authority and ownership

Apply the target surface's governing ownership policy. Technical write access does not expand the user's requested scope or override assignee, author, resource-owner, or environment boundaries.

State that access-versus-authority distinction in **Ownership policy** whenever the evidence shows technical access beyond the authorized boundary.

A specific user request authorizes ordinary `reversible` writes only within its named action and targets. Fresh explicit confirmation is required for:

- splitting, grouping, closing-with-successor, rebasing a dependency, or other restructuring;
- production data or operations, service downtime, and off-box recipients;
- resources outside the governing ownership boundary;
- `compensating-only` or `irreversible` actions; and
- rewriting or deleting published history.

Do not treat approval for one action class as approval for another. Record the exact authorization source in the card.

**Gate:** ownership is resolved and authorization covers the exact batch, or the verdict cannot be `ready`.

## 3. Inspect guards, dependencies, and publication

Read current state from the authoritative system immediately before the batch:

- **Ordinary writes:** inspect direct dependencies and current compare-before-write guards.
- **Deletion, closure, base changes, and history rewrites:** traverse transitive consumers such as stacked PRs, dependent branches, linked issues, workflows, releases, umbrella records, and downstream services.
- **Git history:** compare local refs with their upstreams and consumers. If a commit or ref is published or consumed, put the append-only corrective commit or successor-ref alternative in **Preview / exclusions** and surface that choice in **Next action**. Classify its rewrite or deletion as `compensating-only` at best because restoring a ref cannot undo publication or downstream consumption; it remains `confirmation-required`.
- **Production-like UI or operations:** verify environment, record ownership, snapshot affected records when possible, and name the captured prior values plus restoration or compensation steps. When downstream billing, entitlement, notification, or audit effects persist after restoring the primary record, classify the action as `compensating-only`.
- **Off-box copies:** resolve the recipient, included sensitive material, retention, and revocation or deletion path.

Put every target's stable ID plus every mutable fact that protects its write in **Current guards** and **Invalidators**.

**Gate:** required dependencies and consumers are enumerated from current evidence; an unknown dependency on a destructive action yields `blocked`.

## 4. Preview blast radius and recovery

Show a user-visible preview before ambiguous restructuring, high-volume changes, production operations, ownership expansion, and `compensating-only` or `irreversible` actions. Include targets, proposed delta, exclusions, dependencies, blast radius, and recovery path.

Classify recovery:

- `reversible` — a direct undo restores the captured prior state.
- `compensating-only` — the original event remains, but a follow-up action can restore its practical effect.
- `irreversible` — no reliable restoration exists.

For `reversible`, identify the captured prior value or exact undo. For `compensating-only`, name every recovery target by stable ID and its captured prior value in **Recovery plan**, then specify the compensation and residual trace. For `irreversible`, state the permanent loss. Missing recovery evidence yields `blocked`, not optimistic classification.

**Gate:** the preview and recovery evidence match the mutation's volume, environment, ambiguity, and reversibility class.

## 5. Assign one verdict

- `ready` — exact batch, ownership, authorization, current guards, dependency evidence, recovery, and read-back plan all satisfy the gates; no fresh confirmation category applies.
- `confirmation-required` — the evidence and preview are complete, but this action class requires a fresh explicit user decision. Present the card and ask for that decision; do not mutate.
- `blocked` — required target, ownership, authorization, dependency, recovery, or guard evidence is missing or unsafe. Name the evidence or authority needed; do not mutate.

A multi-step or multi-batch run without an already-authorized durable home is `blocked`. **Next action** names the existing workflow artifact to use or the authorization needed to write it; do not create persistence state merely to clear this gate.

Fresh confirmation updates **Authorization source** but does not waive any other gate. Re-read the invalidators after confirmation before changing the verdict to `ready`.

Write **Next action** as a self-contained instruction naming the exact action and targets. Do not hide them behind “this operation,” “the above,” or another referential phrase.

## 6. Hand off execution and preserve partial state

Pass the `ready` card to the workflow that owns the mutation. Immediately before each write, compare its guards. Any changed target, action, ownership, dependency, head, publication status, environment, or approval invalidates `ready`: stop the unexecuted remainder and re-preflight it.

Every caller follows the same result contract: continue only when **Verdict** is `ready` and **Invalidators** still match. On `confirmation-required`, present the card and wait for the named confirmation. On `blocked`, stop the mutation and report **Next action**.

The execution handoff must use the surface's native conditional-write mechanism when one exists: expected versions, compare-and-swap tokens, exact-SHA leases, or idempotency keys. A recovery push for published Git history must also be lease-guarded against the re-read remote head.

After each attempted item, record `landed`, `failed`, `skipped`, or `reconcile-required`. Use `reconcile-required` when the command result and authoritative read-back cannot establish whether the write landed. Stop that item: do not retry it or classify it as `failed` until an authoritative query resolves its state.

On interruption, invalidation, or `reconcile-required`:

1. preserve the item ledger;
2. authoritatively re-read every `landed` item;
3. record the observed partial external state; and
4. create a new card whose **Targets** cover only the safe `pending` remainder, while **Batch items** carries the authoritative `landed`, `failed`, `skipped`, and unresolved `reconcile-required` history alongside those pending items.

Exclude every `reconcile-required` item from the new card's write targets. Its **Next action** is the exact authoritative query needed to resolve that item; only the observed result may move it to `landed`, `failed`, or `pending`.

Never restart from an assumed zero state. The execution workflow owns writes; `verify-claims` may validate consequential post-write claims, and the final completion workflow owns its acceptance-surface verdict.

**Done:** the card is populated, its verdict matches the gates, and no shared-state mutation has been performed by this skill.
