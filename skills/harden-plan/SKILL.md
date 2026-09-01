---
name: harden-plan
description: Hardens a written plan against the real codebase before any code exists — a plan edit is cheaper than a code refactor. Use when the user asks to harden, check, or lint a plan they are about to execute, and proactively when `/grill-me` or `/grilling` hands off a written plan. Fires while the plan is still text; once code exists the review is `/review-pr`'s.
---

# /harden-plan: Pre-code Plan Quality Gate

A shift-left gate: the fix is a plan edit, not a code refactor. Takes a
WRITTEN plan and runs the `/review-pr` anti-slop lens against it while
the plan is still text.

## Reference files

Each one is loaded only on the branch that reaches it, some by main, some by a subagent. Loader and firing condition:

- `references/subagent-prompts.md`: both Phase 2 prompt templates (Subagent A category analyzer, Subagent B pattern inventory) and the Phase 1 placeholders each takes. Loaded by **main** at the Phase 2 dispatch.
- `references/category-checks.md`: P1-P11, each category's scope, its default severity, its invalidity gate, and one worked example. Loaded by **Subagent A** before it answers any category; main never applies these categories itself.
- `references/grill-loop.md`: question-block format, the four response branches, forbidden dismiss reasons, self-heal verification, abort ramps, one-at-a-time rule. Loaded by **main** in Phase 4 when findings remain (`verdict != ready-to-code`).
- `references/write-back.md`: external-modification check, the three write-back options, the insertion format, and the write-failure fallback. Loaded by **main** in Phase 5 when `PLAN_SOURCE=file`.

One reference is not bundled here: `${CLAUDE_SKILL_DIR}/../review-pr/references/repo-map.md` holds the `repo_map_files` / `repo_map_exports` shell, the one copy this skill shares with `/review-pr` and `/fix-pr-review`. Loaded by **main** in Phase 1 when `packages/` or `apps/` exists.

## Usage

```
/harden-plan <path-to-plan-file>         # file input (enables write-back)
/harden-plan "<pasted plan text>"        # inline input (print-only)
/harden-plan                             # reuse a plan pasted earlier in
                                         # this conversation (print-only)
```

---

## Phase 1: Gather context (main)

### Input detection

1. If `$ARG` is a file path and `[ -f "$ARG" ]` → read as plan file,
   set `PLAN_SOURCE=file`, remember `PLAN_FILE=$ARG` and its mtime for
   the Phase 5 write-back check.
2. Else if `$ARG` matches `*/*` or ends in `.md` / `.txt` and
   `[ ! -f "$ARG" ]` → `Plan file not found: <path>`, abort.
3. Else if `$ARG` is empty → if the user pasted or wrote out a plan
   earlier in this conversation, use that text verbatim and set
   `PLAN_SOURCE=conversation`. Echo the first 3 lines back and confirm
   it's the plan they mean before proceeding. If no plan appears earlier
   in the conversation, fall to the stop-and-ask block (5).
4. Else if `$ARG` length > 40 chars OR contains newline → treat as
   inline plan text. Set `PLAN_SOURCE=inline`.
5. Otherwise: stop-and-ask:
   > **Need a plan to harden.** Usage:
   > - `/harden-plan <path>`: harden a plan file
   > - `/harden-plan "pasted text"`: harden inline text
   > - `/harden-plan`: harden a plan pasted earlier in this conversation

Once the plan text is in hand: if it is empty or under 10 lines, print
`Plan is too short to harden — expand it first` and abort.

Don't attempt to infer from the current branch, git status, or any
recent file. Intent grounding depends on the exact plan the user wants
checked. Guessing defeats the anti-slop gate.

### Plan parsing

Extract these four fields and stash them as main-context variables:

- **`stated_goal`**: 1-sentence intent. Look (in order):
  1. Content after `## Context` / `## Goal` / `## What we're adding`
     header (first paragraph only)
  2. First H1 / H2 followed by first paragraph
  3. First sentence of the plan
  If none found, write `stated_goal: <could not extract, flag during
  grounding>` and proceed.

- **`stated_steps`**: the action list. Look (in order):
  1. Content under `## Steps`, `## Implementation`, `## Plan`,
     `## Changes`, `## Concrete changes` sections
  2. Top-level numbered lists (`1.`, `2.`, `3.`) anywhere in the body
  3. `### Step <n>` / `### Phase <n>` / `### Change <n>` headers
  Number each extracted step as `S1`, `S2`, ... for Phase 2 reference.

- **`stated_files`**: files the plan mentions creating / modifying /
  deleting. Look for:
  1. Fenced code blocks containing paths (`apps/backend/...`,
     `packages/ui/...`, `src/...`)
  2. `## Files to create`, `## Files to modify`, `## Files` sections
  3. Inline backtick references matching `*.ts`, `*.tsx`, `*.sql`,
     `*.json`, `*.md` patterns
  Deduplicate; preserve insertion order. For each file, tag as
  `create` / `modify` / `delete` based on surrounding prose.

- **`stated_out_of_scope`**: explicit exclusions. Look for:
  1. `## Out of scope`, `## Not doing`, `## Scope notes` sections
  2. The phrase "out of scope" inline
  3. "Deferred to follow-up" / "v1 only" / "v2" disclaimers

### Cwd / plan-repo mismatch

For each distinct top-level directory in `stated_files` (e.g., `apps/`,
`packages/`, `src/`), check `[ -d <dir> ]` in cwd. If **none** of them
exist:

> **cwd does not match the plan's target repo.**
> Plan references: `<list of top-level dirs>`
> Cwd has: `<list of top-level dirs in cwd>`
> Grounding will be unreliable. Continue anyway?

Present via AskUserQuestion with options: "Continue anyway" and "Abort".

On abort:
> Abort. `cd` into the correct clone and retry, or paste the plan inline
> to skip codebase grounding.

### Compute repo map (for grounding)

Load `${CLAUDE_SKILL_DIR}/../review-pr/references/repo-map.md` and run
its **Local mode** block, the one copy of this shell, shared with
`/review-pr` and `/fix-pr-review`. It carries the `bash -c` wrapping
the globs need to survive zsh, and caps each half at 500 lines with
the truncation marked. Load it when `packages/` or `apps/` exists;
when neither does there is nothing to run and the fallback below
applies.

Stash the two outputs as `repo_map_files` and `repo_map_exports`.

**Non-monorepo fallback**: if neither `packages/` nor `apps/` exists, set
both maps to `N/A (not a monorepo)` and flag `IS_MONOREPO=false`.
Subagent A will reroute searches to `src/` and the repo root. If the map
still comes back empty (not a monorepo AND no `src/`), warn and proceed
with plan-text-only grounding. Subagent A's `grounding` field will cite
plan text exclusively.

### Planning-specific inventories (run in parallel with repo map above)

Both P11 inventories are the same `find`, differing only in what they
match and how many lines they keep. Run it twice, substituting
`<MATCH>` and `<CAP>` from the table below:

```bash
bash -c '
find apps packages 2>/dev/null -type f <MATCH> \
  -not -path "*/node_modules/*" -not -path "*/dist/*" \
  -not -name "*.spec.*" 2>/dev/null | head -<CAP>
'
```

| Stash as | `<MATCH>` | `<CAP>` |
|---|---|---|
| `existing_services_inventory` (for P11 Pattern Consistency) | `-name "*.service.ts" -not -name "*.test.*"` | 100 |
| `existing_history_tables` (for P11) | `\( -iname "*history*.ts" -o -iname "*audit*.ts" \)` | 50 |

---

## Phase 2: Parallel grounding subagents

Load `${CLAUDE_SKILL_DIR}/references/subagent-prompts.md`. It holds both
templates and the Phase 1 placeholders each takes. Fill the placeholders
and dispatch both `general-purpose` agents in **one message with two
Agent tool calls**, A for category analysis, B for sibling-pattern
inventory.

### Degraded-mode rule

If either subagent errors out or returns empty, continue with the other
and note `<subagent> unavailable` in the Phase 4 header. Only abort if
**both** fail.

---

## Phase 3: Critic pass (main context)

Mirror `/review-pr` Phase 3 discipline. Run these steps in order on the
findings from Subagent A (+ merge Subagent B in step 5):

### 1. Dedupe

Merge findings with the same `(plan_step_ref, category)`. Keep the
highest severity and the most specific `grounding`. Union the
`suggested_question` text into one combined question.

### 2. Verify plan-step references

For each finding's `plan_step_ref`, check that it matches a real `Sn`
from `stated_steps`. Drop any finding whose `Sn` doesn't exist. That's
a hallucination. Log the drop in `Filtered out: hallucinated step ref
<ref>`.

### 3. Verify grounding

For each finding's `grounding`:

- If it cites a file path, check the path exists in `repo_map_files`,
  OR is in `stated_files` (a file the plan proposes to create)
- If it cites a symbol, check the symbol exists in `repo_map_exports`
  OR is defined in `stated_steps`
- If it cites a line from the plan, check the quoted text matches the
  actual plan text (case-insensitive substring match)

Drop any finding whose grounding can't be verified. Log the drop.

### 4. 3-prong challenge

For each surviving finding, apply three tests:

- **(a) Reachable?** Is the concern reachable given the plan's stated
  scope? If `stated_out_of_scope` explicitly excludes it, drop.
- **(b) Severity justified?** Does the `severity_reasoning` actually
  support the assigned severity? Downgrade if not (Critical → Serious,
  Serious → Moderate). Log any downgrade.
- **(c) Concrete evidence?** Is the evidence specific enough to act on?
  Vague findings ("consider adding validation") → drop. Specific
  findings ("Step S2 accepts menuPlanSheetId without validating it
  belongs to menuPlanId") → keep.

### 5. Merge Subagent B patterns into P11 findings

For each entry in Subagent B's `patterns` map:

- For each `common_patterns` item, check if the plan explicitly mentions
  adopting that pattern (grep `full_plan_text` for the pattern name or
  sibling-file reference). If NOT mentioned AND the pattern appears in
  the common_patterns list, synthesize a P11 finding:

```
id: P11-<i>
category: Pattern-consistency
severity: Moderate (Serious if the missing pattern is security-
          relevant: auth middleware, ownership validation, tenant
          scoping)
plan_step_ref: "<S for the file creation>"
concern: "Plan creates <file> without <pattern>, which sibling files
          all use"
grounding: "Siblings with this pattern: <list from Subagent B>"
suggested_question: "Should this file follow the sibling pattern and
                     include <pattern>?"
recommended_answer: "Add a step matching <sibling's approach>"
```

If Subagent A already flagged this same pattern under P11, dedupe
(keep Subagent A's version since it has more context).

### 6. Severity rank

Sort findings: Critical → Serious → Moderate → Minor. Within each
severity, group by category (Security first, then Concurrency, then
Round-trip, then Control-flow, then the rest).

### 7. Gap check

For each category that returned `status: no_concerns`, check if the
plan plainly touches that category. If so, that's a contradiction:

- **P5 Security gap**: `stated_steps` contains "upsert", "create",
  "update", "delete", or `stated_files` contains `*.controller.ts` /
  `*.service.ts` with a write method → P5 must have findings or a
  justified "all endpoints are read-only" explanation.
- **P7 Concurrency gap**: if the Security gap check found a write
  endpoint AND P7 says `no_concerns` → contradiction unless the plan
  explicitly uses `onConflictDoUpdate` / `db.transaction(...)`.
- **P8 Round-trip gap**: if `stated_steps` / `stated_files` include
  any Drizzle schema changes OR new persisted fields AND P8 says
  `no_concerns` → contradiction unless the plan has an explicit read-
  path step per field.

On any contradiction, re-dispatch Subagent A ONCE with a specific
nudge pointing at the contradiction. Example:

> You previously returned `P5: no_concerns` but the plan creates an
> upsert endpoint at Step S3 that accepts a foreign `menuPlanSheetId`
> without specifying a validation step. Re-examine P5 and return
> findings for this specific concern or explain why it's not
> applicable.

Accept the retry output. Do not retry more than once per category.

### 8. Queue the findings

Zero findings → skip Phase 4 and go straight to Phase 5.

Stash `findings_queue` (sorted).

---

## Phase 4: Interactive grill (main context)

If `findings_queue` is empty, skip to Phase 5.

Findings remain. Load `${CLAUDE_SKILL_DIR}/references/grill-loop.md` and run its
loop over `findings_queue` in severity order, one AskUserQuestion per
finding, until **every** finding is resolved, dismissed, skipped, or
self-heal-dropped.

**ALWAYS use the AskUserQuestion tool** for every finding presented to
the user, **one question at a time**. Never batch findings, never stack
two questions in one message. Each finding opens with an AskUserQuestion
carrying these options:
- "Accept recommendation (y)", description includes the recommended_answer text
- "Dismiss (n)", description: "Provide a specific reason why this doesn't apply (≥10 chars required)"
- "Custom answer (other)", description: "Provide your own resolution instead of the recommendation"
- "Skip", description: "Leave unresolved for now, revisit later"

AskUserQuestion returns only the selected option's label, no free text.
So **Dismiss routes to a follow-up AskUserQuestion that collects the
dismissal reason**, asked after the user picks Dismiss, never alongside
the first question. `references/grill-loop.md` holds the ≥10-character
rule and the forbidden-reason list that reason is validated against; a
rejected reason re-prompts through that same follow-up question.

Never fall back to plain-text "(y / n / other / skip)" prompts. The
question block format in `references/grill-loop.md` defines the CONTENT
of the AskUserQuestion's `question` field, not standalone text output.

---

## Phase 5: Finalize (main context)

### 1. Print summary

```
# /harden-plan results: <PLAN_SOURCE>

**Verdict**: <computed in Phase 5 step 3>

**Findings**: <total raised> raised / <resolved> resolved /
              <dismissed> dismissed / <skipped> skipped /
              <self-healed> self-healed-dropped

## Accepted plan additions (<count>)

  [<id>] <plan_step_ref>
    → <resolution text>

  [<id>] <plan_step_ref>
    → <resolution text>
  ...

## Dismissed with justification (<count>)

  [<id>] <plan_step_ref>
    Reason: <user's dismissal reason>

  ...

## Skipped, still need your decision (<count>)

  [<id>] <plan_step_ref>
    Finding:     <concern>
    Risk:        <risk>
    Recommended: <recommended_answer>

  ...

## Critic-pass drops (debug info, <count>)

  [<original id>] <reason for drop>
  ...
```

### 2. Write-back option

If `PLAN_SOURCE=file`, load `${CLAUDE_SKILL_DIR}/references/write-back.md`. It
holds the external-modification check, the three write-back options, and
the insertion format. For `inline` / `conversation`, print the accepted
additions as a copy-paste block and stop.

### 3. Verdict recommendation

Print a final recommendation based on `skipped[]` content:

- **`ready-to-code`**: zero skipped OR only Minor skipped:
  > Plan is hardened. You can start coding.

- **`partial`**: some Moderate skipped but no Critical/Serious:
  > Plan is mostly hardened but has <N> open Moderate findings
  > (skipped). Safe to proceed but consider addressing during
  > implementation.

- **`needs-work`**: any Critical or Serious in `skipped[]`:
  > Plan has <N> open Critical/Serious findings. Recommend you iterate
  > on the plan and re-run `/harden-plan` before coding.

### 4. Exit

Do not commit. Do not create files (other than the plan file write-
back). Do not run builds or tests. The skill only reports + optionally
edits the plan file.
