# GitHub reply + resolve mechanics (Phase 7)

Loaded by main in Phase 7, once the local-file skip check has passed. SKILL.md keeps the skip condition and the batch-failure rule; this file holds the four steps. None of it runs for local-file input.

---

## Step 7a: Regenerate FIX replies from actual diff

The classifier wrote `reply_placeholder` during Phase 3 BEFORE fixes existed. Between Phase 3 and now, fixes were applied (Phase 5) and possibly modified by self-heal (Phase 6). The placeholder may no longer match reality.

For each FIX item with `fix_status ∈ {ok, retried_ok, inconclusive, type_check_skipped}`:

1. Compute the diff for its target file(s): `git diff HEAD -- <file1> <file2>` (nothing is committed yet, so HEAD = pre-Phase-5 state; the diff IS the applied fix).
2. Extract the relevant hunk(s) for the referenced file:line.
3. Synthesize `reply_final[idx]` from the actual diff, in the form:

   ```
   Fixed: <1-sentence description of what the diff actually changed, 
   citing the new post-image line number and a concrete verb>
   ```

4. Store as `reply_final[idx]`.

`type_check_skipped` is a landed fix, not a failure. It means the repo has no TS tooling for the narrow check to run (Phase 5 step 4), and `/done` in Phase 6 still covered it. Excluding it would leave every fix in a non-TypeScript repo without a reply, so it replies like any other landed fix.

Skipped/aborted FIX items get no reply (they land in NEEDS-INPUT for the final report instead). The same applies to Phase 5.5's outcomes: `fix_status ∈ {partial, reverted_inverse_risk, inverse_risk_applied}` gets no reply and no thread resolution. A partial, reverted, or known-risk fix must not close the reviewer's conversation. All three surface in the Phase 8 report. So the no-reply set is exactly `fix_status ∈ {skipped, aborted, partial, reverted_inverse_risk, inverse_risk_applied}`; Step 7c excludes it.

## Step 7b: Reply validator (pre-post mechanical check)

Before posting any reply, validate it against forbidden-phrase / must-contain rules:

```
forbidden_prefixes = [
    "Thanks", "Noted", "Good point", "Fair", "Will do",
    "Addressed", "Done", "Ok", "OK", "Sure", "Got it"
]
min_length = 40 characters
must_contain_any_of = [
    a file path  (e.g., /\w+\.\w{1,4}/)
    a line reference (e.g., /:\d+/ or /\bline \d+/)
    a quoted string (e.g., /"[^"]+"/ or /'[^']+'/, for CLAUDE.md quotes)
    a short commit SHA (/\b[a-f0-9]{7,}\b/)
    a concrete verb ("changed", "added", "removed", "renamed", "refactored",
                     "fixed", "scoped", "extracted", "inlined")
]
```

A reply passes if: starts with none of the forbidden prefixes, length ≥ 40, AND matches at least ONE of the `must_contain_any_of` patterns.

**Reusability-specific rule** (mechanically enforced via `reusability_context`):

The validator reads the `reusability_context:` field stored on each comment during Phase 3 STEP 2.5. If `reusability_context.flagged == true`, the reusability-specific rule activates and is AND-combined with the generic rule above.

```
if comment.reusability_context?.flagged:
    reusability_rule_passes =
        (classification == "FIX" AND reply contains a destination file path
            that points at an existing module, one of:
              - a `@<scope>/...` package reference
              - a `packages/.../<file>.ts` path
              - an `apps/.../<file>.ts` path
              - a relative import path pattern `from './...'` or `from '../...'`)
        OR
        (classification == "DEFER" AND reply contains a concrete
            out-of-scope reason: ticket ref, file path outside the PR diff,
            OR the phrase "tracked in <ref>")
        OR
        (classification == "DISMISS" AND reply cites a specific reason:
            CLAUDE.md quote, prior commit sha, or factual refutation)

    if NOT reusability_rule_passes:
        reject reply; dispatch rewriter subagent with failing rule cited
```

Concretely this catches:
- `"Fixed: now importing from @<scope>/utils/format.ts:45 instead of reimplementing"` → PASSES (FIX with destination)
- `"Fixed: refactored to a helper"` → FAILS (no destination)
- `"Moved to helpers"` → FAILS (no concrete target)
- `"Valid but requires packages/shared refactor; tracking in #4321"` → PASSES (DEFER with scope reason)
- `"Will do later"` → FAILS (no reason, no target)

**Missing `reusability_context` field**: if the classifier omitted the field entirely (Phase 3 non-compliance), default to `reusability_context = { flagged: false }` and fall through to the generic validator. But log a `reusability_context missing — Phase 3 schema gap` warning in the final report so the user knows the reusability check didn't gate this reply.

On failure: dispatch a 1-off `general-purpose` subagent with the original comment + failing reply + which rule failed, ask for a compliant rewrite. Max 1 rewrite. If the rewrite still fails, log as `reply_invalid` and SKIP posting for this item (thread stays unresolved; surfaced in the top of the final report).

## Step 7c: Post loop

Immediately before the first reply in this authorized batch, invoke `preflight-mutations`. Pass the exact PR URL, base and current head SHA, every target thread ID, ordered reply/resolve actions, final validated reply text and classification per item, and the authorization evidence that covers each item. FIX items use `execution_authorization_evidence`, plus their per-fix confirmation when `--interactive` was set. DISMISS, DEFER, and DISAGREE items use their contested-item confirmation. Apply the result contract before continuing.

For each item with a non-null `thread_id` (actionables only, NOT nitpicks, NOT NEEDS-INPUT, NOT `reply_invalid`, and NOT any FIX item Step 7a left without a `reply_final`, i.e. `fix_status ∈ {skipped, aborted, partial, reverted_inverse_risk, inverse_risk_applied}`):

1. Re-fetch the PR head and exact thread. Freeze the validated reply body and identify the authenticated user. If `isResolved: true`, paginate the complete current comment set and search for that author and the exact frozen body. Record exactly one match as `reply_state=verified-existing`; record zero as `confirmed-absent`, and multiple matches or an inconclusive query as `reconcile-required`. Record `resolve_state=already-resolved` independently, perform no mutation unless the user separately authorizes replying to that resolved thread, retire the current card, and preflight the remaining items without this thread before the next write. If the thread is open, compare the current head and complete comment-ID set with the ready card. A mismatch stops the pending item and returns the unexecuted remainder to `preflight-mutations`; a match freezes the before-write comment IDs.
2. Post the reply below. Then query the exact thread by `thread_id` and require one new comment, absent from the before-write ID set, whose ID matches the mutation response when present and whose author and complete body match the current user and frozen reply. Record one exact match as `landed`; zero matches as `confirmed-absent`; multiple matches or an inconclusive query as `reconcile-required`. On either non-landed result, skip this item's dependent resolve, retire the current card, and preflight the remaining items without this unresolved thread before the next write. Do not retry a `reconcile-required` reply.
3. Resolve only after the reply is `landed`. Advance the ready card's item ledger and thread guards from the authoritative reply read-back, then refresh the PR head and exact thread immediately before resolution. Reuse the card when the head, `isResolved`, and complete comment-ID set match those advanced guards; re-run `preflight-mutations` for this remaining resolve action only when an unexpected change invalidates it.
4. Run the resolve mutation below, then query the exact thread by `thread_id`. Record `resolved` only when the authoritative result has `isResolved: true`; record an authoritative `false` as `confirmed-open`, and a failed or inconclusive query as `reconcile-required`. On either non-resolved result, retire the current card and preflight the remaining items without this unresolved thread before the next write. Never infer resolution from the mutation response or retry an indeterminate result.

```bash
# 1. Post reply. Pass every ID with -f (raw string); -F applies JSON type
#    coercion and mangles all-numeric IDs into numbers
gh api graphql \
  -f threadId="<thread_id>" \
  -f body="<reply text>" \
  -f query='mutation($threadId: ID!, $body: String!) {
    addPullRequestReviewThreadReply(input: {
      pullRequestReviewThreadId: $threadId,
      body: $body
    }) {
      comment { id url }
    }
  }'

# 2. Resolve (only if reply succeeded)
gh api graphql \
  -f threadId="<thread_id>" \
  -f query='mutation($threadId: ID!) {
    resolveReviewThread(input: { threadId: $threadId }) {
      thread { id isResolved }
    }
  }'
```

After an expected `landed` reply and authoritative `resolved` result, advance the card's ledger and guards and reuse that same `ready` card for the next pending item while its invalidators still match. Use a replacement card only on a branch that explicitly retired the current one above. Carry every `confirmed-absent`, `confirmed-open`, and `reconcile-required` item in the batch ledger and Phase 8 failure report; include the exact settling query for `reconcile-required`. Never execute dependent or later writes under a retired card.

## Step 7d: Promoted nitpicks handling

Promoted nitpicks (sanity-flagged in Phase 3, STEP 3(e)) have `thread_id = null` because they live only in the review body. Phase 5 applies the fix for them; Phase 7 has **nothing to post**. They are tracked separately for the final report so the user sees: "fix applied, no thread to resolve — mention in commit message; CodeRabbit's next review will regenerate the body and the old nitpick disappears."
