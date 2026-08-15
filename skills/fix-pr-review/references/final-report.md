# Phase 8 final report template

Loaded by main in Phase 8 only after every NEEDS-INPUT item has a non-pending status and the run-level stash restoration has finished. Render exactly once from final workflow state — the `Test:` lines and the three-way fix partition are how the user decides what to re-test.

---

## Failure section (TOP — only if any Phase 7 or Phase 8 GitHub op failed)

If any applicable `gh_status[idx]` has `reply_ok == false` OR `resolve_ok == false`, print this section at the **top** of the report. Exclude entries whose reply and resolution states are both `not-applicable`:

```
## ⚠ GitHub operations needing attention (<count>)

  [<idx>] <file:line>
    reply:       <reply_state> — <reply_err or authoritative observation>
    resolution:  <resolve_state> — <resolve_err or authoritative observation>
    disposition: <state-specific next action>
    thread:      <html_url>
```

Render reply and resolution independently. For `confirmed-absent` plus
`already-resolved`, report that the thread is resolved, the frozen reply is absent, and no
automatic retry is authorized. Reserve "thread is still open" for `confirmed-open` or an
authoritative open-thread read-back. For `reconcile-required`, name the indeterminate operation
and its exact settling query; authorize no retry until that query settles the state.

## Main body

```
# Fix PR Review — PR #<num>: <title>

Convergence: converged — all <F> fixes class-complete, inverse risk absent, no new siblings
             | NOT converged — <n> of <F> fixes partial or reverted (see below)

## Fixes applied (<count>)

### Hardening-only fixes (<H count>) — no user-visible change expected, smoke-test the happy path
  [1] ✓ src/modules/.../meal-menu-portions.service.ts:26 — atomic onConflictDoUpdate replaces findExisting+branch
      type-check (this file): pass
      convergence: class-complete 2/2, inverse risk absent, no new siblings
      Test: smoke test — happy path unchanged
  [2] ✓ src/modules/.../meal-menu-portions-validation-helper.ts:9 — cross-FK ownership validation added
      type-check (this file): pass
      convergence: class-complete 1/1, inverse risk absent, no new siblings
      Test: smoke test — happy path unchanged

### Logic-changing fixes (<L count>) — user-visible behavior differs, exercise each scenario below
  [3] ✓ src/modules/.../client-portions.service.ts:100 — hoist mealMenuPortions fetch above early exits
      type-check (this file): pass
      convergence: class-complete 3/3, inverse risk absent, no new siblings
      Test: Set a meal-level portion, navigate to a week where no components are scheduled;
            stored value should still render in the cell (was blank before).
  [4] ✓ src/.../planned-aggregation.ts:94 — round-trip stored ordered/produced/sold fields
      type-check (this file): pass
      convergence: class-complete 1/1, inverse risk absent, no new siblings
      Test: Edit a meal-row ordered value, reload the page; the value should persist
            in the cell (was resetting to child-sum before).

### Skipped / not landed clean (<S count>)
  [5] ⚠ src/utils/parser.ts:88 — narrow type-check failed twice, needs manual attention
      convergence: not run (fix reverted before Phase 5.5)
  [6] ⚠ src/api/session.ts:44 — partial: 2 of 3 sites fixed after one re-verify pass
      convergence: class-complete NO — src/api/session-worker.ts:91 still unfixed
  [7] ⚠ src/cache/store.ts:30 — reverted: inverse risk confirmed present in applied code
      convergence: inverse risk PRESENT at src/cache/store.ts:38 — stale entry served
                   forever after a failed refresh; fix reverted by inverting its own hunks

# Rendering rules for this section:
#   - Every item whose final classification is FIX MUST appear in exactly one
#     of the three subsections above. Partition on fix_status alone. Membership
#     in Phase 5's authoritative `landed_fix_statuses` set is landed; split it
#     by change_class:
#       change_class=hardening     → Hardening-only
#       change_class=logic-change  → Logic-changing
#     Every other Phase 5 fix_status is not landed clean and renders under
#     Skipped / not landed clean. The two sets cover the whole fix_status enum,
#     so every item lands in exactly one subsection. fix_status carries the
#     type-check result already (a type-check that failed twice ends the item
#     as `skipped` or `aborted`), and it outranks that result — a fix that
#     type-checked clean but was reverted or left partial by Phase 5.5 belongs
#     in the third subsection, never in the first two.
#   - The `type-check (this file):` line renders the Phase 5 outcome for that
#     item — `pass`, `inconclusive — preexisting errors`, or `skipped (no TS
#     tooling)` for fix_status=type_check_skipped. Never print `pass` for a
#     check that did not run.
#   - The `Convergence:` line under the title reads `converged` only when
#     EVERY fix is class-complete with inverse risk absent and no new
#     siblings. Otherwise `NOT converged`, with the count that fell short.
#   - For each fix, render a `convergence:` line from `convergence[idx]`
#     (Phase 5.5). If Phase 5.5 did not run for that fix, render
#     `convergence: not run (<reason>)`. For fix_status=reverted_inverse_risk
#     where no safe revert path existed, the line MUST state that the risky
#     fix is STILL APPLIED.
#   - For each fix, render the `Test:` line using the `test_scenario` field
#     from the classifier plan verbatim. Do NOT paraphrase — the user needs
#     the exact repro they approved.
#   - If a subsection's count is 0, omit the subsection entirely (do not
#     print an empty header).

## Dismissed (<count>)
  [D1] src/db/schema/index.ts:41 (nitpick) — export ordering matches alphabetical pattern
       Original (first 80 chars): "Consider maintaining consistent schema export ordering..."
  [D2] src/auth/util.ts:12 — contradicts CLAUDE.md: "use type not interface"
       Original: "Consider using interface for User type..."

## Deferred (<count>)
  [E1] src/legacy/parser.ts:210 — streaming refactor out of scope for this PR

## Disagree (<count>)
  [G1] src/api/routes.ts:55 — inlining is clearer here than extraction

# Render a DEFER or DISMISS item under its classification only when its
# required GitHub operations are successful or not applicable. An unsettled
# item renders under NEEDS INPUT instead; an applicable GitHub failure also
# renders in the top failure section.

## /done results
  /fix-ts-errors:   clean
  /parallel-review: 1 Moderate finding — consider extracting helper (see output above)
  /simplify:        no changes suggested
  Remaining after self-heal: <list or "none">

## GitHub reply/resolve (<count>)
  [1]  posted ✓  resolved ✓  — src/db/schema/meal-menu-portions.ts:53
  [2]  posted ✓  resolved ✓  — src/modules/.../meal-menu-portions.service.ts:143
  [D1] (nitpick — no GitHub op)
  [D2] posted ✓  resolved ✓  — src/auth/util.ts:12
  [E1] posted ✓  resolved ✓  — src/legacy/parser.ts:210

# Omit every entry whose reply_state and resolve_state are both not-applicable;
# `has_github_surface=false` means there is no GitHub acceptance surface,
# regardless of whether the input came from GitHub or a local file.

## Promoted nitpicks — no GitHub thread (<count>)
  [F4] src/foo.ts:22 — promoted from nitpick (sanity scan caught a real issue)
       Fix applied. No inline thread to resolve. Mention in commit message;
       CodeRabbit's next review will regenerate the body.

## NEEDS INPUT — handle manually (<count>)
  [N1] https://github.com/owner/repo/pull/123#discussion_r<id>
       CodeRabbit: <short description>
       Why unclear: <reason from classifier>
       Re-triage: /fix-pr-review https://github.com/owner/repo/pull/123#discussion_r<id>

# Render every entry whose final needs_input_status is skipped, failed, or
# reconcile-required. Also render any DEFER or DISMISS whose required
# GitHub operations did not settle, even if it entered Phase 7 directly.
# Fixed, deferred, and dismissed entries render under their final
# classification instead. Applicable failed or reconcile-required GitHub
# states also render independently in the top failure section.

## Suggested commit message

Detailed:
  git commit -m "fix: address CodeRabbit review on PR #<num>

  - <fix 1 description>
  - <fix 2 description>
  - <fix N description>"

One-liner:
  git commit -m "fix: address CodeRabbit review on PR #<num>"

## Stashed work

Stashed: <yes | no>
Restored: <yes | no | conflict>

<If conflict:>
  Your working tree now contains:
    • Phase 5 fixes (applied, not committed)
    • Conflict markers from your stashed WIP
    • Any untracked files from the stash
  Resolve stash conflicts before any commit or push; it is the only
  dependency-ready next action.
  Your original stash is still available as `git stash list` entry
  `fix-pr-review auto-stash <timestamp>`.
```
