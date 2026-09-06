# R-rubric, calibrations, and reply formats

Loaded by the triage subagent at STEP 4 of `triage-prompt.md`. Main never reads this file; it works from the R-Rubric Summary table in SKILL.md.

---

## STEP 4 rubric: apply in order, first match wins

  R1. Self-contradictory or technically wrong → DISMISS
  R2. Hallucinated file:line (after dead-link re-anchor attempt failed) → DISMISS
  R4. Already fixed in current branch state (same-file or cross-file) →
      DISMISS. REQUIRES `prior_commit_sha`
  R5. Contradicts CLAUDE.md → DISMISS. REQUIRES `claude_md_quote`
  R3. Pure style/naming with no correctness implication → DISMISS (only
      reaches this rule if R1/R2/R4/R5 didn't fire; nitpicks reach this
      rule only after promotion in Step 3e)
  Note: If STEP 2.5 flagged reusability_context.flagged == true
  AND a concrete existing target was found, SKIP R3 (pure style)
  when considering the comment. A reuse-directed comment that could
  look "stylistic" (e.g., "rename to match helper X") is actually a
  R6 reusability FIX, not style.

  R10. Fixing it would change observable behavior that predates this PR →
       NEEDS-INPUT. REQUIRES `why_unclear`

       Observable means something outside the changed code sees the
       difference: UI output, an API response's shape or values, persisted
       data, a notification, a permission check, a default value, or timing
       and ordering a user notices. The current behavior may be a deliberate
       product decision that no test or comment records, so a technically
       correct fix can still ship a product regression.

       Before classifying, search for intent: a test asserting the current
       behavior, a comment or doc explaining it, and the commit that
       introduced it per `git blame` or `git log -S`. Write `why_unclear`
       in this shape:

         why_unclear: "current: <behavior>; proposed: <behavior>;
                       intent evidence: <what the search found>"

       `found nothing` is a valid evidence value and does NOT authorize
       the fix.

       An incoming finding already carrying a `product-intent` tag routes
       here regardless of its severity.

       Carve-out: when THIS PR's own diff introduced the behavior, there is
       no pre-existing product intent to protect. Classify it normally.

  R6. Real bug / security / perf / correctness / REUSABILITY issue → FIX

      Reuse problems are correctness problems. A duplicated helper drifts.
      One copy gets the fix and the other misses it. Default to FIX when ANY
      of these hold:

        (a) A concrete existing target is known (STEP 2.5 found a match
            in `repo_map_exports` or via direct grep). The FIX is just
            "delete new code + import existing". This NEVER goes to
            DEFER, even if the existing target lives in an "untouched"
            file, because replacing 10 lines with a 1-line import only
            touches files the PR already has open.

        (b) The extraction is feasible in-scope (< 50 LOC of refactor
            within files already touched by this PR).

        (c) Small-but-duplicated: even a <5-line private helper that
            duplicates a shared helper is a FIX. Never dismiss as
            "too small to matter".

  R7. Real issue but out of scope for THIS PR's stated goal → DEFER

      SPECIAL RULE. REUSABILITY CONCERNS:
      For comments about reuse / DRY / extraction / sharing / helpers,
      DO NOT route to R7 (DEFER) unless BOTH hold:
        (a) the refactoring genuinely requires changes to files NOT
            touched by this PR AND scope exceeds ~50 LOC of changes
            (strictly; small cross-file refactors stay in R6)
        (b) there is a concrete "tracked separately" reference
            (ticket, backlog, follow-up PR)

      **Gap handler**: If (a) is TRUE but (b) is MISSING (no tracking
      reference), do NOT fall through to R6. This is an honest
      out-of-scope refactor that needs a ticket. Route to R9
      (NEEDS-INPUT) with:
        why_unclear: "out-of-scope reuse refactor (<LOC estimate>
                      LOC across untouched files) needing a tracking
                      ticket reference before this can be either FIXed
                      or DEFERred"
      The user sees this at the end of the run
      and makes the call by hand.

      **Delete-new-import-existing carve-out**: if the fix action is
      "delete the new duplicate + add an `import` to the existing
      target", that goes to R6 (FIX) regardless of where the existing
      target lives: deleting and importing only touches files already
      in the PR's diff, so scope is never the reason to DEFER it. The
      one exception is STEP 5.5's shared-symbol gate: if the deleted
      duplicate is itself a shared symbol with more than 3 callers, the
      gate wins and the item routes to NEEDS-INPUT.

      "I didn't feel like doing it", "this is a small cleanup", or
      "can be done later" are NOT valid DEFER reasons for reusability.
      Default to R6 (FIX) when feasible in-scope.
  R8. Valid concern but the reviewer's recommendation is wrong for this
      codebase (legitimate technical disagreement, not style preference) →
      DISAGREE. REQUIRES `disagree_rationale` with concrete counter-argument
  R9. Ambiguous / needs user domain knowledge / needs code execution to
      verify → NEEDS-INPUT

Rubric ordering rationale: R1/R2 are objective fact-checks (first). R4/R5 are
HIGH-SIGNAL dismissals, evaluated before R3 so a style nit on already-
refactored code dismisses with the stronger "already fixed in abc123" reason
instead of the weaker "pure style" reason. R3 comes after. R10 sits above R6
because a finding can be correct and still describe deliberate product
behavior, and severity alone cannot tell those apart. R6-R9 are action
buckets.

---

## NEEDS-INPUT calibration

Use NEEDS-INPUT when you cannot verify WITHOUT running code or without user
domain knowledge. Concrete examples:
  - "This query is slow" → needs a benchmark run → NEEDS-INPUT
  - "This breaks test suite X" → needs test execution → NEEDS-INPUT
  - "Should we use strategy A or B here?" → needs user domain knowledge → NEEDS-INPUT

Anti-examples (these are NOT NEEDS-INPUT):
  - "Rename variable for clarity" → R3 style (or R6 if genuinely confusing)
  - "Missing null check" → you CAN verify by reading the file → R6 or R1
  - "Consider extracting helper" → R3 or R6 based on readability impact

Err toward FIX for mechanical low-risk changes you can verify. Err toward
NEEDS-INPUT when the comment hinges on domain knowledge or runtime behavior.

### Presenting NEEDS-INPUT options to the user

If you elaborate on a NEEDS-INPUT item with branching options (e.g.,
"Option A / Option B / Option C"), every unselected branch MUST be phrased
as a conditional. The user cannot tell "what I already did" from "what I'm
proposing" unless the sentence structure makes it unmistakable.

The shape to write (reads as a hypothetical future):

    Option A: Aggregate as independent intent, no cascade
    IF CHOSEN, we would:
    - Delete the cascade batch from the meal-level edit path
    - Make meal-level edits write only to gs_MealMenuPortions

Rules:
  - Every option block must open with `IF CHOSEN, we would:` before its
    action list, OR every bullet inside must start with `would <verb>` /
    `would not <verb>`.
  - Current state must be labeled separately under `What's in the code now:`
    so the user has an unambiguous baseline.
  - Keep each option block in the conditional mood from first bullet to
    last; anything already true of the code belongs under
    `What's in the code now:` instead.

## change_class calibration

Every FIX item must commit to one of:

- `hardening`: A user running their normal workflow would NOT notice
  anything different. The change affects edge cases only: adversarial
  inputs, concurrent races, malformed payloads, currently-unreachable
  branches, type-safety, defensive depth. Happy path is unchanged.
  Examples:
    - adding cross-FK validation that only fires on malformed requests
    - replacing `findExisting + branch` with atomic `onConflictDoUpdate`
      (single-user behavior identical; only matters under concurrency)
    - adding `.strict()` to a Zod schema (normal UI never sends extras)
    - narrowing a type from `string` to a union (compile-time only)
    - `Promise.all` → `Promise.allSettled` + `console.error` (happy path
      identical; only changes failure observability)

- `logic-change`: A user MIGHT observe a difference in a realistic
  scenario. Any fix that changes what the UI renders, what the API
  returns on a non-error path, what data reaches the database, or how
  errors surface to the user.
  Examples:
    - hoisting a fetch above an early-return (data now appears in an
      empty state where it was previously hidden)
    - making stored values round-trip on reload (previously dropped)
    - fixing an empty error toast to show a real message
    - adding a visual drift indicator (new UI signal)

Burden of proof is on the `hardening` claim. When in doubt, label it
`logic-change` and write a specific test scenario. A fix that is BOTH
hardening and logic-change is `logic-change`.

### test_scenario format

- For `hardening`: write exactly `smoke test, happy path unchanged`.
  (No repro steps; the intent is "confirm nothing regressed".)
- For `logic-change`: write a 1-sentence concrete repro that can be
  executed in the UI, API, or DB. Must include:
    - the trigger (what the user does)
    - the observation (what they should see differently from before)
  Example: "Set a meal-level portion, navigate to a week with no
  components scheduled; stored value should still render in the cell
  (was blank before)."

This split lands word for word in the Phase 8 final report. The user smoke-tests the hardening bucket and deliberately exercises the logic-change bucket.

## Anti-slop reply format

- FIX (placeholder only): "Fixed: <what will be changed, specific>"
- DISMISS R4: "Already fixed in <short_sha>: <what that commit did>"
- DISMISS R5: "Contradicts CLAUDE.md rule: '<verbatim quote>'. Keeping project convention."
- DISMISS R1/R2/R3: "Not changing: <specific 1-sentence rationale with concrete evidence>"
- DEFER: "Valid but out of scope for this PR (<PR focus>); <optional tracking ref>"
- DISAGREE: "Disagree: <concrete counter-argument naming the trade-off>. Keeping current approach."
- Open every reply on its evidence, never on an acknowledgement. Phase 7's
  validator mechanically rejects any reply starting with one of these, so a
  reply that opens on one is discarded work:

  ```
  Thanks · Noted · Good point · Fair · Will do
  Addressed · Done · Ok · OK · Sure · Got it
  ```

  Kept verbatim here because you write the replies and never load
  `github-reply-resolve.md`, where Step 7b's `forbidden_prefixes` is the
  authoritative copy. The two lists must stay identical.
- Write every field the way an engineer writes to another engineer. Nothing you compose carries an em or en dash, since a period or a comma does the same work and a range takes a hyphen. Text you quote from the comment or the code stays as you found it, and the template's own arrows, pipes and sentinels are structure rather than prose, so `class_completeness` keeps the arrow in its `search:` line.
- Every non-placeholder reply must cite specific evidence: file:line, CLAUDE.md
  rule quote, prior commit SHA, or a concrete verb (changed/added/removed/
  renamed/refactored/scoped).
