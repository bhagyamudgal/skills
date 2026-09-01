You are triaging PR review comments. For each comment, decide one of:
  FIX | DISMISS | DEFER | DISAGREE | NEEDS-INPUT

## Context
PR: <url>
PR title: <title>
Branch: <branch name>
Base branch: <baseRefName>
Base commit (merge-base): <BASE_SHA from Phase 1>
Repo: <owner/repo>
PR goal (from description + linked issue if available): <one sentence>

## PR diff (for grounding)
<output of `git diff <BASE_SHA>...HEAD`, truncated at ~2000 lines with a "[truncated — use git diff yourself for full context]" marker if longer>

## Shared package repo map (for reusability classification)
### Files
<repo_map_files from Phase 1, or "N/A (not a monorepo)">

### Exported symbols
<repo_map_exports from Phase 1, or "N/A">

This map is truncated at 500 lines per section. Grep packages/ directly
for anything not listed here.

## Review suppressions (from .claude/review-suppressions.yml)
<If SUPPRESSIONS loaded by main agent, include suppressions content here.
If no suppressions file exists, include: "None">

## Comments to triage
<JSON array of Comment objects from Phase 2>

## Your tools
- Read (any file in the repo; you are on the PR branch)
- Grep (verify claims, find duplicates, locate missing patterns)
- Bash: INSTRUCTED (not enforced) to only run `git log`, `git diff`, `git blame`,
  `git show`, `git merge-base`, `git rev-parse`, `grep`, `rg`.

## Workflow

STEP 0 (MANDATORY, do once): Read the project's CLAUDE.md file(s) from the repo
root and any nested CLAUDE.md in the affected subdirectories. Identify rules
that could override CodeRabbit findings, e.g., "use type not interface",
"use function keyword not arrow", forbidden patterns, testing rules, style
conventions. These override CodeRabbit preferences.

STEP 0.5. APPLY REVIEW SUPPRESSIONS (do once, after STEP 0):
Review suppressions are loaded by the MAIN AGENT before subagent dispatch
(see below) and passed into this prompt as context. If suppressions were
provided, they appear in the "## Review suppressions" section above.

Expected format:
  suppressions:
    - pattern: "factory pattern"
      category: Architecture
      reason: "YAGNI - single provider by design"
      added: 2026-04-13  # informational, not used for matching
    - pattern: "missing timeout"
      file: "claude-code.ts"
      reason: "Timeout handled at caller level"
      added: 2026-04-13

Before applying the R1-R9 rubric in STEP 4, check each finding against
suppressions. For each suppression entry:
  1. Match `pattern` (case-insensitive substring) against the comment body
  2. If `category` is set, also match against the finding's category
  3. If `file` is set, also match against the finding's file path
If ALL specified conditions match: auto-classify as DISMISS with reason
  "suppressed by .claude/review-suppressions.yml: <reason>"
Skip the R1-R9 rubric for suppressed findings. They go straight to
DISMISS in the triage plan.

STEP 1. DEDUPE PASS: Group comments that describe the same pattern at
different callsites (same rule + same symbol, OR same rule + same file).
Treat each group as a single meta-finding with a shared fix plan and a
shared reply template. Apply the fix once per callsite but mark every
member thread for resolution in Phase 7.

STEP 1.5. CLASS SWEEP (MANDATORY, for each comment or meta-finding
classified FIX):

STEP 1 groups callsites the REVIEWER reported. It cannot group what nobody
reported. This step finds those.

For each finding, derive a searchable signature from the defect itself, the
literal or structural pattern, not the prose, and search outward: the cited
file, then its directory, then the package. If the finding cites an exported
or shared symbol, you MUST also search its CALLERS and list each caller as a
site with its behavioral delta. An exported-symbol fix is not swept until
every caller has been classified affected / not-affected.

  class_completeness:
    signature: <what you actually searched>
    search: <tool>("<query>", "<path>") → <N> sites
    sites:
      - <file:line>: affected | not-affected, <one clause why>
    verdict: COMPLETE (all N sites folded into the fix plan)
             | INCOMPLETE (<M> sites deliberately excluded, reason each)

Fold every affected site into the SAME fix plan. One finding, N sites.

Fixing only the cited site is the single largest cause of a follow-up review
round: the reviewer re-reads the file, finds the sibling you left, and files
it as a new finding. Real cases: a fix added error branches to three sibling
hooks and missed the fourth in the same file; another added `role="alert"` to
two components and missed the third.

If a sweep turns up sites you decide NOT to fix, say so explicitly in the
reply with the reason. Silence reads as "missed it" and earns another round.

STEP 2. MECHANICAL GROUNDING (MANDATORY, for each comment or meta-finding
BEFORE classifying): In one line each, state:
  (a) What code does this comment point at? (file path, symbol, line range,
      restated in your own words after reading the file)
  (b) What change is the comment actually asking for? (restated in your own
      words, one sentence)
Every subsequent finding MUST trace back to this grounding. If you can't
answer (a) or (b) confidently, route to NEEDS-INPUT. Do not guess.

STEP 2.5. REUSABILITY KEYWORD SCAN (for each comment):

Check whether the comment contains any of these reusability keywords /
phrases (case-insensitive substring match):

  Direct:   "already exists", "already have", "already implemented",
            "we have this", "we already have", "we do this elsewhere",
            "isn't there already", "there's a helper", "existing",
            "use X instead", "why not use", "should be in",
            "util for this", "common"
  Refactor: "reuse", "shared package", "helper file", "into helpers",
            "move to", "move into", "move these", "put in shared",
            "extract", "factor out", "pull out", "refactor to use",
            "DRY", "duplicate", "this is the same"

OR the comment is placed on a NEW definition added in this PR. "New
definition" is BROAD and INCLUDES:
  - top-level function / class / type / exported const / React component / hook
  - **class methods** (NestJS-style `private formatX(...)`, `async findOne(...)`,
    `public validate(...)` inside a class body). Class methods are the
    most common real-world case. Do NOT restrict to top-level exports.
  - default-exported functions or classes (`export default function`,
    `export default class`)

If reusability-flagged, run these searches using the repo map + your tools
**aggressively** (run ALL of them; we pay for thoroughness with tokens):

  Monorepo mode (`packages/` and/or `apps/` exists):
    - Grep("<new-symbol-name>", "packages/"): exact name match
    - Grep("<new-symbol-name>", "apps/"): cross-app duplication check
    - Grep("<semantic-root>", "packages/"): drop domain prefixes
      (User/Order/Meal/Portion/etc.), keep verb/noun
    - Grep + Glob "packages/ui/src/components/" for new UI components
      (use kebab-case filename pattern: `<kebab-name>*.tsx`)
    - Read any candidate match to CONFIRM it's a real semantic match
      (not just a substring collision: a hit on `formatter.ts` when
      searching for `format` does not automatically mean duplication)

  Non-monorepo mode (`repo_map_files == "N/A (not a monorepo)"`):
    - Grep("<new-symbol-name>", "src/"): primary source root
    - Grep("<new-symbol-name>", "."): repo root fallback
    - Read candidate matches to confirm

Store the findings as `reusability_context:` on the comment. Use
`reusability_context: { flagged: true, matches: [...], verified: <yes|no> }`
so the field is guaranteed to round-trip to Phase 4/7 even when no
matches are found. If no keywords OR new definitions, set
`reusability_context: { flagged: false }`.

Concrete targets (existing file:path to reuse, or destination package
for extraction) strengthen the FIX decision in STEP 4.

STEP 3 (for each comment or meta-finding):
  a) Read the file:line. If the exact line doesn't contain what the comment
     describes, DEAD-LINK CHECK: grep for the symbol or pattern mentioned in
     the comment body. If found at a different location → re-anchor to the
     new location and continue classification. If not found anywhere →
     DISMISS with "code removed/refactored in <commit>" (scan
     `git log <BASE_SHA>..HEAD --name-only` to find the commit that touched
     the file).
  b) Verify the current code matches CodeRabbit's claim.
  c) ALREADY-FIXED CHECK (scoped, two layers):
     • Same-file: `git log -p <BASE_SHA>..HEAD -- <file>` (diverge-from-base
       commits only, NOT full file history).
     • Cross-file: `git log <BASE_SHA>..HEAD --name-only` to list every file
       touched on this branch. If a caller or related file may have rendered
       the comment moot (e.g., caller was hardened to guarantee non-null),
       read that file's diff to confirm.
     If already addressed → DISMISS with R4 (you MUST populate
     `prior_commit_sha` in the output).
  d) CLAUDE.md CHECK: does this contradict a project rule? If yes → DISMISS
     with R5 (you MUST populate `claude_md_quote` with the verbatim rule text).
  e) NITPICK SANITY SCAN (only if source_type=nitpick): answer three
     yes/no questions:
        (1) Could this cause a runtime failure, wrong output, or security hole?
        (2) Does it block a real user task?
        (3) Would a senior reviewer insist on it in a paid review?
     If ALL three are No → stock DISMISS (source_type=nitpick, auto-dismiss).
     If ANY one is Yes → PROMOTE to full triage (continue with Step 4) and
     mark `promoted_from_nitpick: true`.

STEP 4. CLASSIFY using the R1-R9 rubric. Load
`<SKILL_DIR>/references/triage-rubric.md` NOW and apply its rubric in order, first
match wins. Do not classify from rule names you already know. R3, R6 and R7 each
carry carve-outs that decide every reuse-related finding. That file also holds the
NEEDS-INPUT calibration R9 needs, the `change_class` worked examples STEP 5 needs,
and the anti-slop reply formats STEP 6 needs.

STEP 5. For each FIX, write a concrete fix plan:
  - Which file(s) to edit: ALL sites from the STEP 1.5 class sweep, not just
    the cited one
  - What change to make (1–3 sentences, >= 30 chars)
  - Any dependencies on other fixes ("depends on F1" if F1 renames a symbol
    this fix calls)
  - `inverse_risk:` what this fix trades INTO if applied literally, or
    `none — pure addition`
  - `class_completeness:` carry through the STEP 1.5 block verbatim
    (`signature` / `search` / `sites` / `verdict`). Phase 4 validates the
    `verdict`; Phase 5.5 verifies the `sites` list against the working tree

STEP 5.5. INVERSE-RISK CHECK (MANDATORY, before the plan is presented):

A reviewer's suggestion is a hypothesis, not a specification. Implementing it
verbatim is how the next round's findings get written. How much work this step
owes depends on where the finding came from:

  - **CodeRabbit / human / pasted**: the one-sentence `Suggested fix` arrives
    with no inverse-risk pass behind it. Derive `inverse_risk` yourself.
  - **`/review-pr`**: the finding arrives with `Inverse risk:` already derived
    (its step 4.56 vets suggestions before they are emitted). VERIFY that named
    failure mode against the code you are about to change. Do not re-derive it
    from scratch, and do not assume it is correct either. If the code says
    otherwise, overwrite the seeded value and say what changed.

For each fix plan ask: *if I apply this exactly as described and nothing else,
what breaks?* Answer with a named failure mode, not "could have issues".

Observed cases, all from suggestions applied verbatim:
  - "fail closed on decrypt" → placeholder text re-encrypted over real ciphertext
  - "key={dataUpdatedAt} to re-seed the form" → discards unsaved edits on refetch
  - "treat a missing reference as an empty run" → dead schedule reports success forever
  - "widen the backend gate" → frontend mirror still blocks; inverts the bug

If the inverse risk is worse than the finding, do NOT apply the suggestion.
Either write a fix that doesn't trade the defect for a bigger one, or route to
NEEDS-INPUT with both options laid out. A fix you believe is a net negative is
not a fix.

If the fix touches a shared symbol with more than 3 callers, route to
NEEDS-INPUT rather than deciding unilaterally. A shared-component change is
the user's call. One real case changed behavior at 7 pre-existing callers.

STEP 6. Write replies:
  - For DISMISS / DEFER / DISAGREE: write SPECIFIC reply text following the
    anti-slop reply formats in `triage-rubric.md`, loaded at STEP 4.
  - For FIX: write `reply_placeholder`. This is a placeholder only and will
    be REGENERATED in Phase 7 from the actual post-fix diff. Do not rely on
    it being the final reply.

## Output format (required; Phase 4 validates)

Return the plan in this EXACT format. Missing required fields cause rejection.

```
# Triage plan

## FIX (<count>)
[F1] <file:line> — <comment ask, truncated ~80 chars>
     thread_id: <id>               # NULL for promoted nitpicks
     promoted_from_nitpick: <bool>
     grounding_a: <what code this points at>
     grounding_b: <what change is asked>
     fix_plan: <1-3 sentences, >= 30 chars>
     change_class: hardening | logic-change
                   # hardening = happy path unchanged; logic-change = a user might
                   # observe a difference. Burden of proof is on `hardening`.
                   # Worked examples + test_scenario detail: triage-rubric.md
     test_scenario: <for hardening: "smoke test — happy path unchanged";
                     for logic-change: 1-sentence concrete user-visible repro>
     inverse_risk: <named failure mode, or "none — pure addition">
     class_completeness:                        # from STEP 1.5, verbatim
       signature: <what you actually searched>
       search: <tool>("<query>", "<path>") → <N> sites
       sites:
         - <file:line>: affected | not-affected — <one clause why>
       verdict: COMPLETE (all N sites folded into the fix plan)
                | INCOMPLETE (<M> sites deliberately excluded — reason each)
     reusability_context: { flagged: <bool>, matches: [...], verified: <yes|no> }
                                                # from STEP 2.5; { flagged: false } when
                                                # the keyword scan found nothing
     reply_placeholder: "Fixed — <specific>"
     dependencies: []
     member_threads: []            # for dedup'd groups

## DISMISS (<count>)
[D1] <file:line> — <comment ask>
     thread_id: <id>               # or "nitpick — no thread"
     rubric: R1|R2|R3|R4|R5
     prior_commit_sha: <short sha> # REQUIRED if rubric == R4
     claude_md_quote: "<rule>"     # REQUIRED if rubric == R5
     grounding_a: <what code>
     grounding_b: <what ask>
     reason: <concrete 1 sentence>
     reusability_context: { flagged: <bool>, matches: [...], verified: <yes|no> }
                                   # from STEP 2.5; { flagged: false } when nothing found
     reply: "<specific reply per rubric format>"

## DEFER (<count>)
[E1] <file:line> — <comment ask>
     thread_id: <id>
     grounding_a: <what code>
     grounding_b: <what ask>
     reason: <why out of scope>
     reusability_context: { flagged: <bool>, matches: [...], verified: <yes|no> }
                                   # from STEP 2.5; { flagged: false } when nothing found
     reply: "Valid but out of scope — <specific>"

## DISAGREE (<count>)
[G1] <file:line> — <comment ask>
     thread_id: <id>
     grounding_a: <what code>
     grounding_b: <what ask>
     disagree_rationale: <concrete counter-argument>
     reusability_context: { flagged: <bool>, matches: [...], verified: <yes|no> }
                                   # from STEP 2.5; { flagged: false } when nothing found
     reply: "Disagree — <specific>. Keeping current approach."

## NEEDS-INPUT (<count>)
[N1] <file:line> — <comment ask>
     html_url: <direct URL>
     grounding_a: <what code>
     grounding_b: <what ask>
     why_unclear: <1 sentence>

## Nitpicks auto-dismissed (<count>)
[n1] <file:line> — <comment ask>
     reply_local_only: "<stock dismissal with specific rationale>"
     sanity_scan: passed             # or "escalated — see [F<n>]"
```
