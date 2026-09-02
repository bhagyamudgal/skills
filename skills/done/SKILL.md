---
name: done
description: MANDATORY post-task acceptance verification. Fire before reporting ANY task complete. Route code, UI, documentation, global configuration or skills, external metadata or data, and publication or deployment to their user-facing boundaries.
---

# Post-Task Verification (/done)

`done` is the single completion entry point. Route verification to the surfaces the user will experience; repository checks are evidence only for surfaces they exercise.

## 1. Bind the run and select acceptance lanes

Record the originating request as a stable, complete summary. Preserve later user corrections in that summary before continuing.

For an initial Git run, record the exact outputs of `git rev-parse --abbrev-ref HEAD` as the branch and `git rev-parse HEAD` as the pre-verification head. A branch rename or switch invalidates the card. A post-publication run resumes the same card and preserves its branch, pre-verification head, base, and verified snapshot, except for the explicit existing-PR base-rebind path below.

For PR-bound work, resolve the intended base once here. Apply an explicit repository policy when one exists. Otherwise inspect the default and integration candidates:

```bash
gh repo view --json defaultBranchRef -q .defaultBranchRef.name
git ls-remote --heads origin 'refs/heads/dev*' 'refs/heads/develop*'
```

Choose the single unambiguous active `dev` or `develop` integration branch; use the default when none exists. Stop and ask when multiple candidates remain plausible. Refresh only the exact chosen `origin` ref, then record its name, remote base-tip SHA, merge-base SHA, and exact commands used:

```bash
git fetch --no-tags origin "+refs/heads/<base-ref>:refs/remotes/origin/<base-ref>"
git rev-parse "refs/remotes/origin/<base-ref>"
git merge-base HEAD "refs/remotes/origin/<base-ref>"
```

For external-only work, bind currency to the authoritative targets instead: record each stable target ID or URL, environment, version or revision when the system exposes one, and the exact read-back ledger. Git fields and commits are not applicable. Mixed Git and external work records both forms of currency.

Infer the required lanes from the originating request, changed artifacts, and actions already performed. Show the six-lane selection before running checks, with one reason for every required or not-applicable lane. Continue without requiring routine confirmation; apply any user correction before the final verdict.

| Lane | Select when |
|---|---|
| Code | Source, tests, scripts, build behavior, or runtime logic changed |
| UI | A user-visible interface or interaction changed |
| Documentation | A document, generated artifact, link, asset, or navigation path changed |
| Global configuration or skills | Agent rules, configuration, registration, discovery, or invocation changed |
| External metadata or data | A board, issue, PR, database, remote record, or computed external result changed |
| Publication or deployment | A release, deploy, push, published package, hosted artifact, or live consumer changed |

An unselected lane is `not-applicable`, with its exclusion reason. A selected lane is required even when its boundary is unavailable.

**Gate:** request summary and applicable currency are exact; all six lanes have a selection and reason; and every user-requested outcome maps to every lane that applies to that outcome. Do not require unrelated lanes.

## 2. Verify each required lane

Use the narrowest check that reaches the actual acceptance boundary. Do not run code checks for a task with no code lane or use an internal proxy as proof of another lane.

When Code or Global configuration or skills is required, run `simplify` once after the applicable review and parse checks. If it edits content, invalidate every acceptance observation that depends on the changed content across all lanes and evidence facets. Rerun affected code and global checks, review coverage, browser/UI flows, rendered documents/assets/links, external data or metadata read-backs, and publication or live-consumer checks. Route affected review coverage through `converge-reviews` before assigning any affected lane `verified`.

| Lane | Minimum boundary evidence |
|---|---|
| Code | Run the affected repository-native type, lint, build, and test checks. Use `fix-ts-errors` when TypeScript applies; a scoped first pass is allowed, but always run the full workspace check at least once. Run `parallel-review`, apply its `converge-reviews` result, and account for the request against the diff. `simplify`'s added-comment scan is blocking here: a comment narrating WHAT the code does, JSDoc on an obvious function, or a section divider still in the diff leaves this lane unverified. Run `reuse-first` in sweep mode and record what it returned, including nothing: `simplify` is scoped by its own gate to duplication *introduced by the change*, so duplication that already existed is invisible to every other check in this lane. |
| UI | Run the affected flow through `browser-qa`; require every affected step to pass and record browser output, screenshots, network results, and console state. |
| Documentation | Inspect the rendered or generated final artifact and exercise affected links, assets, and navigation. Source text alone does not verify rendered output. |
| Global configuration or skills | Parse the final configuration, verify registration and discovery, then check picker visibility, manual invocation, or actual consumer behavior wherever the change affects them. |
| External metadata or data | Freshly re-fetch every changed target from the authoritative system and compare exact IDs, fields, counts, or totals with the request and mutation ledger. |
| Publication or deployment | Inspect the published consumer or live target at the exact version and environment; a successful upload or deploy command alone is insufficient. |

For the code lane, fix Critical and Serious review findings and apply `converge-reviews`: continue only on `continue`, proceed on `converged`, stop on `blocked-at-cap`, and present any `follow-up-proposed` approval boundary. Re-run only checks invalidated by a fix.

For a completed shared-state mutation, reuse the exact authoritative read-back plan and landed-item ledger produced by its execution workflow. When a lane conclusion depends on inference rather than direct observation, run `verify-claims` and preserve its evidence ceiling.

Repair a failed check and re-run only its invalidated evidence. If it remains unresolved, assign the lane `blocked`.

**Gate:** every required lane has direct boundary evidence or a concrete gap; every check named by an applicable lane has a recorded result.

## 3. Assign states

Use this vocabulary for every request item, lane, and evidence facet:

- `verified`: the minimum boundary evidence supports the requested outcome.
- `pending`: required work or evidence has not been attempted or is waiting on an unmet prerequisite. PR-dependent CI or review before a PR exists is `pending`.
- `assumed`: only indirect evidence supports the outcome; name the assumption.
- `deferred`: verification was intentionally postponed; name who or what resumes it and when.
- `blocked`: a prerequisite-ready action was attempted and failed or cannot proceed; name the blocker.
- `not-applicable`: allowed only for a lane or evidence facet genuinely outside the request and changed surfaces; repeat the exclusion reason. Request items never use this state.

Unavailable boundary evidence creates an evidence ceiling. It never becomes `verified` because another lane passed.

**Gate:** each state follows from recorded evidence, and every non-verified required row names its exact gap and next action.

## 4. Build the readiness card

Declare the in-scope set, seal it as an isolated snapshot, then render the card per `${CLAUDE_SKILL_DIR}/references/readiness-card.md`. Load it now. It holds the worktree inventory, the isolated-snapshot procedure, both card templates, the file-pr handoff, post-publication re-verification, and the no-PR commit path. Nothing below runs without it.


**Done:** card currency is recorded, every request item appears once with every applicable lane, all six lanes and five evidence facets are reported, the exact next action is dependency-ready, and the verdict does not exceed the weakest required row. `ready-to-publish` hands off to `file-pr`; only `ready` permits reporting task completion.
