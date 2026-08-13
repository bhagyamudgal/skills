---
name: done
description: MANDATORY post-task acceptance verification. Fire before reporting ANY task complete. Route code, UI, documentation, global configuration or skills, external metadata or data, and publication or deployment to their user-facing boundaries.
---

# Post-Task Verification (/done)

`done` is the single completion entry point. Route verification to the surfaces the user will experience; repository checks are evidence only for surfaces they exercise.

## 1. Select acceptance lanes

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

**Gate:** all six lanes have a selection and reason, and every user-requested outcome maps to at least one required lane.

## 2. Verify each required lane

Use the narrowest check that reaches the actual acceptance boundary. Do not run code checks for a task with no code lane or use an internal proxy as proof of another lane.

| Lane | Minimum boundary evidence |
|---|---|
| Code | Run the affected repository-native type, lint, build, and test checks. Use `fix-ts-errors` when TypeScript applies, and the full workspace check when repository policy or cross-workspace impact requires it. Run `parallel-review`, apply its `converge-reviews` result, run `simplify`, scan every added comment, and account for the request against the diff. |
| UI | Run the affected flow through `browser-qa`; require every affected step to pass and record browser output, screenshots, network results, and console state. |
| Documentation | Inspect the rendered or generated final artifact and exercise affected links, assets, and navigation. Source text alone does not verify rendered output. |
| Global configuration or skills | Parse the final configuration, verify registration and discovery, then check picker visibility, manual invocation, or actual consumer behavior wherever the change affects them. |
| External metadata or data | Freshly re-fetch every changed target from the authoritative system and compare exact IDs, fields, counts, or totals with the request and mutation ledger. |
| Publication or deployment | Inspect the published consumer or live target at the exact version and environment; a successful upload or deploy command alone is insufficient. |

For the code lane, fix Critical and Serious review findings and apply `converge-reviews`: continue only on `continue`, proceed on `converged`, stop on `blocked-at-cap`, and present any `follow-up-proposed` approval boundary. Re-run only checks invalidated by a fix.

For a completed shared-state mutation, reuse the exact authoritative read-back plan and landed-item ledger produced by its execution workflow. When a lane conclusion depends on inference rather than direct observation, run `verify-claims` and preserve its evidence ceiling.

Repair a failed check and re-run only its invalidated evidence. If it remains unresolved, assign the lane `blocked`.

**Gate:** every required lane has direct boundary evidence or a concrete gap; every check named by an applicable lane has a recorded result.

## 3. Assign lane states

Assign exactly one state to every lane:

- `verified` — the minimum boundary evidence supports the requested outcome.
- `assumed` — only indirect evidence supports the outcome; name the assumption.
- `deferred` — verification was intentionally postponed; name who or what resumes it and when.
- `blocked` — required evidence failed or is unavailable; name the blocker.
- `not-applicable` — the lane was not required; repeat the exclusion reason.

Unavailable boundary evidence creates an evidence ceiling. It never becomes `verified` because another lane passed.

**Gate:** each state follows from recorded evidence, and every non-verified required lane names its exact gap and next action.

## 4. Report the evidence card

Report all six lanes in this form:

```markdown
| Lane | Required | Acceptance boundary | Evidence | State | Gap / next action |
|---|---|---|---|---|---|
| Code | yes / no | <surface> | <observation and command or artifact> | verified / assumed / deferred / blocked / not-applicable | <none or exact gap and next action> |
```

Set **Overall completion** to `verified` only when every required lane is `verified`. Otherwise set it to `not verified`, name the weakest required lane states as the **Evidence ceiling**, and state the exact next action without claiming the task complete.

After every required lane is verified, run `git-commit` when the user asked for a commit or the task is a discrete unit of work; otherwise print the two commit-message variants. A requested push, release, or deployment remains part of the publication lane and requires its own live-target read-back before the overall verdict can be `verified`.

**Done:** all six lanes are reported, every requested outcome is accounted for, and the overall completion claim does not exceed the weakest required lane.
