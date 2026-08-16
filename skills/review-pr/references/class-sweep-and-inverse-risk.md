# Class sweep and inverse-risk pass (reviewer prompt steps 5 and 6)

Loaded by **Subagent 1** as soon as any finding proposes a code change; a run whose
findings propose none never reaches this file. Both passes are MANDATORY once it is
reached, and step 6 runs after step 5, on every drafted `Suggested fix`.

## Step 5 — CLASS SWEEP

Do this when the finding is FIRST RAISED, not when it is resolved — an unswept
finding is a cascade waiting to happen.

For each finding, derive a searchable signature from its `Rule-class` — the
literal or structural pattern, not the prose — and search its **blast radius**:
the touched files, then the enclosing module, then the package, plus every
caller when `Rule-class` names a shared or exported symbol.

REQUIRED audit field — use this EXACT name `class_completeness:`. Its exact shape,
the `affected | not-affected` vocabulary, and the `N/A (no code change proposed)`
sentinel are in `<SKILL_DIR>/references/finding-output-format.md` under
"`class_completeness:` audit" — write it as specified there, not from memory.

If the sweep finds sites the finding did not cover, fold them into the SAME
finding (preferred — one finding, N sites) or raise them as siblings, so every
site of the class is on the page.

## Step 6 — INVERSE-RISK PASS

Treat your own remedy as code under review. Ask, for each suggested fix:
*if a competent engineer implements this literally and nothing else, what breaks?*

Answer concretely, naming the failure mode — not "could have issues". Worked
examples:
  - "fail-closed decrypt" → placeholder value that can be re-encrypted over real ciphertext
  - "key={dataUpdatedAt} to re-seed the form" → silently discards unsaved edits on refetch
  - "treat missing reference as an empty run" → dead schedule now reports success forever
  - "widen the backend gate" → frontend mirror still restricts; inverts the bug

Write it into the finding's `Inverse risk:` field. If the fix is a pure addition
with no behavior traded away, say `none — pure addition`.

A fix whose inverse risk is worse than the original finding is the cascade with
extra steps. Rewrite the suggestion or downgrade the finding to an observation.
