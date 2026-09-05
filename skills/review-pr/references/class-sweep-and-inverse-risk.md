# Class sweep and inverse-risk pass (reviewer prompt steps 5 and 6)

**Subagent 1** loads this as soon as any finding proposes a code change. A run whose findings propose none never reaches this file. Both passes are MANDATORY once it is
reached, and step 6 runs after step 5, on every drafted `Suggested fix`.

## Step 5: CLASS SWEEP

Do this when the finding is FIRST RAISED, not when it is resolved. Skip the sweep and the same bug spreads unchecked.

For each finding, derive a searchable signature from its `Rule-class`, the
literal or structural pattern, not the prose, and search its **blast radius**:
the touched files, then the enclosing module, then the package, plus every
caller when `Rule-class` names a shared or exported symbol.

REQUIRED audit field: use this EXACT name `class_completeness:`. Its exact shape,
the `affected | not-affected` vocabulary, and the `N/A (no code change proposed)`
sentinel are in `<SKILL_DIR>/references/finding-output-format.md` under
"`class_completeness:` audit". Write it as specified there, not from memory.

If the sweep finds sites the finding missed, fold them into the SAME finding or raise them as siblings. One finding with N sites beats many. Every site of the class lands on the page.

## Step 6: INVERSE-RISK PASS

Treat your own remedy as code under review. Ask for each suggested fix what breaks when a competent engineer implements it literally and nothing else.

Answer in concrete terms and name the failure mode, not vague warnings. Examples follow:
  - "fail-closed decrypt" → placeholder value that can be re-encrypted over real ciphertext
  - "key={dataUpdatedAt} to re-seed the form" → silently discards unsaved edits on refetch
  - "treat missing reference as an empty run" → dead schedule now reports success forever
  - "widen the backend gate" → frontend mirror still restricts; inverts the bug

Write it into the finding's `Inverse risk:` field. If the fix is a pure addition
with no behavior traded away, say `none, pure addition`.

A fix with worse inverse risk than the original finding adds harm. Apply the step 4.56 remedy in `references/critic-verify.md`; no second outcome lives here.
