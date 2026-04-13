---
name: harden-plan
description: Pre-code quality gate that runs /review-pr's anti-slop lens against a written plan BEFORE any code is written. Grounds the plan against the real codebase, runs 11 category checks (security, concurrency, round-trip, control-flow, error-handling, pattern-consistency, plus /review-pr's Q1-Q6), then grills the user one question at a time until the plan is hardened. Use when the user says "harden my plan", "check my plan", "grill my plan before I code", "lint this plan", or invokes `/harden-plan` explicitly. Also invoke proactively after `/superpowers:brainstorm` or `/grill-me` completes with a written plan and before any implementation begins. Do NOT invoke after coding has started — redirect to `/review-pr` / `/fix-pr-review` in that case.
---

# /harden-plan — Pre-code Plan Quality Gate

Takes a WRITTEN plan and runs the `/review-pr` anti-slop lens against it
BEFORE any code is written. Goal: catch security, concurrency, round-trip,
and pattern-consistency issues when fixing them is a plan edit, not a code
refactor.

## Usage

```
/harden-plan <path-to-plan-file>         # file input (enables write-back)
/harden-plan "<pasted plan text>"        # inline input (print-only)
/harden-plan                             # auto-detect plan-mode buffer
/harden-plan --plan-mode                 # explicit plan-mode grab
```

This skill runs AFTER design has been settled (via `/superpowers:brainstorm`
and/or `/grill-me`) and BEFORE you start coding. For post-code review use
`/review-pr`. For fixing review findings use `/fix-pr-review`.

## When to invoke

Invoke when the user has a plan they're about to execute and says any of:
- "harden my plan"
- "check my plan before I code"
- "grill my plan"
- "lint this plan"
- "is this plan ok to execute?"

Or proactively after `/superpowers:brainstorm` or `/grill-me` completes
with a written plan and before implementation starts, if the user hasn't
already invoked `/harden-plan`.

**Do NOT invoke** after coding has started — redirect the user to
`/review-pr` / `/fix-pr-review` for post-code review.

---

## Phase 1: Gather context (main)

### Input detection

1. If `$ARG` is a file path and `[ -f "$ARG" ]` → read as plan file,
   set `PLAN_SOURCE=file`, remember `PLAN_FILE=$ARG` for Phase 5
   write-back.
2. Else if `$ARG` is empty OR `$ARG == "--plan-mode"` → if a plan-mode
   buffer is active, grab its contents. Set `PLAN_SOURCE=plan-mode`.
3. Else if `$ARG` length > 40 chars OR contains newline → treat as
   inline plan text. Set `PLAN_SOURCE=inline`.
4. Otherwise: stop-and-ask:
   > **Need a plan to harden.** Usage:
   > - `/harden-plan <path>` — harden a plan file
   > - `/harden-plan "pasted text"` — harden inline text
   > - `/harden-plan` — harden the current plan-mode buffer

Don't attempt to infer from the current branch, git status, or any
recent file. Intent grounding depends on the exact plan the user wants
checked — guessing defeats the anti-slop gate.

### Plan parsing

Extract these four fields and stash them as main-context variables:

- **`stated_goal`** — 1-sentence intent. Look (in order):
  1. Content after `## Context` / `## Goal` / `## What we're adding`
     header (first paragraph only)
  2. First H1 / H2 followed by first paragraph
  3. First sentence of the plan
  If none found, write `stated_goal: <could not extract — flag during
  grounding>` and proceed.

- **`stated_steps`** — the action list. Look (in order):
  1. Content under `## Steps`, `## Implementation`, `## Plan`,
     `## Changes`, `## Concrete changes` sections
  2. Top-level numbered lists (`1.`, `2.`, `3.`) anywhere in the body
  3. `### Step <n>` / `### Phase <n>` / `### Change <n>` headers
  Number each extracted step as `S1`, `S2`, ... for Phase 2 reference.

- **`stated_files`** — files the plan mentions creating / modifying /
  deleting. Look for:
  1. Fenced code blocks containing paths (`apps/backend/...`,
     `packages/ui/...`, `src/...`)
  2. `## Files to create`, `## Files to modify`, `## Files` sections
  3. Inline backtick references matching `*.ts`, `*.tsx`, `*.sql`,
     `*.json`, `*.md` patterns
  Deduplicate; preserve insertion order. For each file, tag as
  `create` / `modify` / `delete` based on surrounding prose.

- **`stated_out_of_scope`** — explicit exclusions. Look for:
  1. `## Out of scope`, `## Not doing`, `## Scope notes` sections
  2. The phrase "out of scope" inline
  3. "Deferred to follow-up" / "v1 only" / "v2" disclaimers

### Size warning

If plan > 1000 lines, print:
> **Plan is <N> lines.** Grounding may be slow but I'll proceed.

### Cwd / plan-repo mismatch

For each distinct top-level directory in `stated_files` (e.g., `apps/`,
`packages/`, `src/`), check `[ -d <dir> ]` in cwd. If **none** of them
exist:

> **cwd does not match the plan's target repo.**
> Plan references: `<list of top-level dirs>`
> Cwd has: `<list of top-level dirs in cwd>`
> Grounding will be unreliable — continue anyway? (y/n)

On `n`, abort with:
> Abort. `cd` into the correct clone and retry, or paste the plan inline
> to skip codebase grounding.

### Compute repo map (for grounding)

Reuse `/review-pr`'s Phase 1 repo-map bash verbatim. **Wrap in
`bash -c '...'`** — raw `packages/*/src` globs abort under zsh before
`2>/dev/null` can suppress the error, silently emptying the map.

**Repo map — files** (capped 500 lines, truncation marked):

```bash
bash -c '
if [ -d packages ] || [ -d apps ]; then
  { [ -d packages ] && find packages -type f \( -name "*.ts" -o -name "*.tsx" \) \
      -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" \
      -not -name "*.test.*" -not -name "*.spec.*" 2>/dev/null
    [ -d apps ] && find apps -type f \( -name "*.ts" -o -name "*.tsx" \) \
      -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" \
      -not -path "*/.next/*" -not -name "*.test.*" -not -name "*.spec.*" 2>/dev/null
  } | awk "NR<=500{print} END{if(NR>500)print \"[truncated at 500 of \" NR \" lines — use Glob directly for ground truth]\"}"
fi
'
```

Stash as `repo_map_files`.

**Repo map — exports** (capped 500 lines):

```bash
bash -c '
if [ -d packages ] || [ -d apps ]; then
  find packages apps 2>/dev/null -type d \( -name src -o -name lib -o -name source \) \
    -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" \
    -not -path "*/.next/*" 2>/dev/null \
    | xargs -I{} grep -rhnE "^export (default (async )?function|function|const|class|type|interface|async function) \w+" {} 2>/dev/null \
    | awk "NR<=500{print} END{if(NR>500)print \"[truncated at 500 of \" NR \" lines — grep packages/ apps/ directly for more]\"}"
fi
'
```

Stash as `repo_map_exports`.

**Non-monorepo fallback**: if neither `packages/` nor `apps/` exists, set
both maps to `N/A (not a monorepo)` and flag `IS_MONOREPO=false` —
Subagent A will reroute searches to `src/` and the repo root.

### Planning-specific inventories (run in parallel with repo map above)

**Existing services inventory** (for P11 Pattern Consistency):

```bash
bash -c '
find apps packages 2>/dev/null -type f -name "*.service.ts" \
  -not -path "*/node_modules/*" -not -path "*/dist/*" \
  -not -name "*.spec.*" -not -name "*.test.*" 2>/dev/null | head -100
'
```

Stash as `existing_services_inventory`.

**Existing history / audit tables** (for P11):

```bash
bash -c '
find apps packages 2>/dev/null -type f \
  \( -iname "*history*.ts" -o -iname "*audit*.ts" \) \
  -not -path "*/node_modules/*" -not -path "*/dist/*" \
  -not -name "*.spec.*" 2>/dev/null | head -50
'
```

Stash as `existing_history_tables`.

These two inventories ground P11 — if the plan creates a new service
and the sibling services all have matching `*-history.ts` files in the
existing_history_tables list, P11 flags the plan for missing parity.

---

## Phase 2: Parallel grounding subagents

Launch in a **single message with two Agent tool calls** — not chained.

### Degraded-mode rule

If either subagent errors out or returns empty, continue with the other
and note `<subagent> unavailable` in the Phase 4 header. Only abort if
**both** fail.

### Subagent A — Category analyzer (`general-purpose`)

Prompt template (fill in the `<placeholders>` with Phase 1 values):

```
You are grounding a WRITTEN PLAN against a real codebase to identify
execution anti-patterns BEFORE any code is written. Your job is to
identify concrete, evidence-backed concerns across 11 categories —
NOT style nitpicks, NOT generic advice, NOT hypothetical issues.

## Plan being hardened

### Stated goal
<stated_goal>

### Stated steps (numbered S1..Sn for reference)
<stated_steps with line numbers>

### Stated files to create / modify / delete
<stated_files>

### Stated out of scope
<stated_out_of_scope>

### Full plan text (for reference)
<full plan text>

## Codebase context

### Files in shared roots (may be truncated)
<repo_map_files, or "N/A (not a monorepo)">

### Exported symbols in shared roots (may be truncated)
<repo_map_exports, or "N/A">

### Existing NestJS-style services
<existing_services_inventory>

### Existing history / audit tables
<existing_history_tables>

## Your task

1. **GROUNDING PASS — MANDATORY, before answering any category.**
   Write 3–5 bullets describing what this plan MECHANICALLY proposes to
   do: which files are created/modified, which endpoints/functions are
   added, which schemas change, which UI components render. Every
   subsequent finding MUST trace back to one of these bullets AND to a
   specific `Sn` step. If a finding doesn't trace to a grounding bullet
   + step, drop it before outputting.

2. Answer all 11 categories EXPLICITLY. Each must be addressed even if
   just `"No concerns for P<n>"`.

   [See the "11 category definitions" section below for full text.]

3. For each category, use the tools available to you (Grep, Glob, Read,
   Bash) to verify your findings against the actual codebase. Don't
   guess at symbol names — search for them. Don't assume a helper
   exists — grep for it.

## Output format

Produce ONLY YAML, no prose preamble or closing summary:

grounding_bullets:
  - <bullet 1 — what the plan mechanically does>
  - <bullet 2>
  - ...

findings:
  - id: P<n>-<i>                    # P5-1, P7-2, etc. i starts at 1 per category
    category: <Intent | Unnecessary | DRY | Performance | Security |
               Reusability | Concurrency | Round-trip | Control-flow |
               Error-handling | Pattern-consistency>
    severity: Critical | Serious | Moderate | Minor
    plan_step_ref: "S<n> — <short quote from that step, max 80 chars>"
    concern: <1 sentence — what's wrong or missing>
    grounding: <evidence from plan text OR from repo_map_files /
                repo_map_exports / existing_services_inventory /
                existing_history_tables — cite specific paths/symbols>
    suggested_question: <what you'd ask the user to resolve this>
    recommended_answer: <concrete action if user agrees — file:symbol
                         level where possible>
    severity_reasoning: <why this severity level — REQUIRED for
                         Critical and Serious>

For each category with no concerns, emit ONE marker line:
  - category: P<n>
    status: no_concerns

## Anti-slop rules (MANDATORY)

- NO style / formatting / naming nitpicks
- NO generic advice ("consider adding tests", "think about performance")
- NO hypothetical issues — only flag what the plan explicitly says OR
  explicitly omits, grounded against the real codebase
- Every finding needs a `plan_step_ref` matching a real `Sn` from
  stated_steps — no free-floating findings
- Every finding needs `grounding` citing a real plan line OR a real
  entry in the repo map
- Default to "no concerns" when in doubt — false positives waste user
  time
- **For P5 (Security)** on any new write endpoint, you MUST address
  cross-FK validation explicitly. "No concerns" is invalid unless the
  plan proves every FK in the write body is validated against the
  owned tenant root.
- **For P7 (Concurrency)** on any new write, you MUST address atomicity.
  "No concerns" is invalid unless the plan explicitly uses
  `onConflictDoUpdate` / `db.transaction(...)` / a CAS primitive.
- **For P8 (Round-trip)**, you MUST enumerate every new persisted field
  and check for a corresponding read-path step.
- **For P6 (Reusability)**, if the plan creates new symbols, populate a
  `reusability_searches:` audit field listing the Grep / Glob calls you
  ran. Empty audit = P6 findings are invalid.

Produce ONLY the YAML output. No prose preamble, no closing summary.
```

The 11 category definitions are injected into this prompt inline — see
the "## 11 category definitions" section at the bottom of this skill
file.

### Subagent B — Pattern inventory (`general-purpose`)

Prompt template:

```
You are building a "conventions map" for a plan about to be executed.
For every file the plan proposes to CREATE, find 2–3 existing files of
the same shape and extract their common patterns. This feeds pattern-
consistency checks in the main flow.

## Files the plan proposes to create

<stated_files, filtered to files that do NOT yet exist in cwd>

## Repo inventories

### Existing services
<existing_services_inventory>

### Existing history tables
<existing_history_tables>

### Files in shared roots
<repo_map_files>

## Your task

For each proposed new file, do the following:

1. Identify the file's shape. Use filename heuristics:
   - `*.service.ts` → NestJS service
   - `*.controller.ts` → NestJS controller
   - `use<Name>.ts` in `hooks/` → React hook
   - `*.schema.ts` or file in `schema/` → Drizzle schema
   - `*.tsx` in `components/` → React component
   - `*-validator.ts` / `*-helper.ts` → utility helper
   - `*.module.ts` → NestJS module
   - Something else → use your judgment from the path

2. Find 2–3 existing files of the same shape. Prefer sibling files in
   the same module / domain directory. Use Grep / Glob / Read.

3. Read each sibling in full and extract COMMON patterns — patterns
   that appear in 2 or more siblings. Examples:
   - History table via `writeHistoryRecord` helper
   - `@fileseye/try-catch` or project-equivalent try-catch utility
   - Logger imports (Pino, Winston, etc.)
   - DTO location (in `./dto/` vs inline)
   - Validation helper in `./helpers/`
   - Error-factory usage
   - Transaction wrapping for writes
   - Early-exit fetch-before-filter pattern

4. Skip patterns present in only ONE sibling — those are noise.

## Output format

Produce ONLY YAML:

patterns:
  "<proposed_file_path>":
    shape: <nestjs-service | nestjs-controller | react-hook |
            drizzle-schema | react-component | utility-helper | other>
    similar_files:
      - <path>
      - <path>
      - <path>
    common_patterns:
      - "<short description of pattern + path where it lives in the
         sibling, e.g. 'history table via writeHistoryRecord from
         apps/backend/src/modules/v1/client-portions/helpers/
         write-history-record.ts'>"
      - "<pattern 2>"
      - ...

  "<next proposed file>":
    shape: ...
    ...

If the plan proposes zero new files (only modifications), output:
patterns: {}

Produce ONLY the YAML output.
```

### Why two subagents

Clean separation: Subagent A does plan-vs-codebase category lint;
Subagent B extracts sibling conventions specifically for P11. Running
them in parallel halves wall time and keeps each subagent's prompt
focused. Phase 3 merges their outputs.

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
from `stated_steps`. Drop any finding whose `Sn` doesn't exist — that's
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
severity: Moderate
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
plan plainly touches that category — if so, that's a contradiction:

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
- **P11 Pattern-consistency gap**: if Subagent B returned non-empty
  `patterns` AND P11 has no findings → contradiction.

On any contradiction, re-dispatch Subagent A ONCE with a specific
nudge pointing at the contradiction. Example:

> You previously returned `P5: no_concerns` but the plan creates an
> upsert endpoint at Step S3 that accepts a foreign `menuPlanSheetId`
> without specifying a validation step. Re-examine P5 and return
> findings for this specific concern or explain why it's not
> applicable.

Accept the retry output. Do not retry more than once per category.

### 8. Final verdict (pre-grill)

- Any **Critical** finding open → `verdict: needs-work` (grill runs)
- Any **Serious** finding open → `verdict: needs-work` (grill runs)
- Only Moderate / Minor findings → `verdict: likely-ready` (grill
  still runs — warns are cheap)
- Zero findings → `verdict: ready-to-code` (skip grill, go to Phase 5)

Stash `findings_queue` (sorted) and `verdict`.

---

## Phase 4: Interactive grill (main context)

If `verdict: ready-to-code`, skip to Phase 5.

Otherwise, walk `findings_queue` in order, emitting ONE question per
message and waiting for user response before moving to the next. Mirror
`/grill-me`'s "one question at a time" discipline.

### Question block format

```
[<id> · <severity> · <category>]  (<n> of <total>)

Finding:     <concern in 1-2 sentences>
Risk:        <why it matters — 1-2 sentences; for Critical/Serious,
              include a concrete failure scenario>
Plan step:   <plan_step_ref> — "<1-line quote from the plan>"
Grounding:   <1 sentence of concrete evidence — file:line or plan text>

Question:    <suggested_question>
Recommended: <recommended_answer>

(y / n / other / skip)
```

### Response handling

**`y` — resolved (accept recommendation)**

Mark finding resolved. Append the `recommended_answer` to
`accepted_additions[]` with its `plan_step_ref`. Move to next.

**`n <reason>` — dismissed**

Dismissal reason is REQUIRED and must be ≥ 10 characters. If missing
or shorter, reject with:
> Dismiss reason must be at least 10 chars. Try again or type `skip`.

**Forbidden dismiss reasons** (borrowed from `/fix-pr-review` reply
validator): `ok`, `fine`, `no`, `nah`, `skip`, `later`, `wont`, `won't`,
`nope`, `ignore`, `thanks`, `noted`, `good point`, `fair`, `will do`,
`addressed`, `done`, `sure`, `got it`. If the reason matches one of
these (case-insensitive, after trimming), reject with:
> That's not a real reason. Be specific about WHY this doesn't apply —
> cite the step it's covered by, the CLAUDE.md rule it contradicts, or
> the concrete constraint that makes it inapplicable.

Valid dismissals require a SPECIFIC counter-argument:
- "already covered in Step S1a via existing middleware"
- "endpoint is internal-only / not user-facing"
- "field is optional and backfilled by a cron in a separate PR"
- "this is the exact pattern used in UsersService and is intentional"

Record in `dismissed[]` with the reason. Move to next.

**`other <alt>` — user provides a custom answer**

Capture `alt` verbatim into `accepted_additions[]` as the resolution
instead of the `recommended_answer`. No length check — the user knows
what they want. Move to next.

**`skip`**

Finding stays unresolved. Record in `skipped[]`. Move to next.

### Self-heal branch (false-positive verification)

If the user's `n <reason>` or `other <alt>` claims "already covered by
X" or "exists in Y" (keywords: `already`, `covered in`, `exists in`,
`handled by`, `done in`), run a quick verification before accepting:

1. Extract the reference (`X` or `Y`) — typically a file path, symbol
   name, or step reference
2. `Grep` the reference in cwd (if it's a symbol) or `Read` the file
   (if it's a path)
3. If found AND matches the user's claim → silently DROP the finding
   (don't count as dismissed), log `Self-heal drop: <id> — <user
   claim> verified`, move to next
4. If not found → push back:
   > Couldn't find `<X>` in the codebase. Can you point me at the exact
   > file or line? Otherwise I'll record this as dismissed.

This prevents the user from having to justify findings the skill could
verify itself.

### Abort branches

- User types `abort` / `quit` → stop grilling, jump to Phase 5 with
  remaining findings as `skipped`
- User provides 3 consecutive `skip`s → prompt:
  > You've skipped 3 in a row. Want to bail out and get a summary?
  > (y = bail, n = keep going)

### One question at a time — STRICT

Do NOT batch findings into a single prompt. Do NOT emit multiple
questions in one message. Do NOT pre-answer questions for the user.
Mirrors `/grill-me`'s explicit rule: the user must think about each
finding independently. Pre-batched questions will be rejected.

---

## Phase 5: Finalize (main context)

### 1. Print summary

```
# /harden-plan results — <PLAN_SOURCE>

**Verdict**: <ready-to-code | partial | needs-work>

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

## Skipped — still need your decision (<count>)

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

**Only if `PLAN_SOURCE=file`**:

Prompt:
> Apply accepted plan additions back to `<PLAN_FILE>`?
> (a) **write** — insert additions as sub-steps in place
> (b) **diff** — print unified diff only; you apply manually
> (c) **exit** — leave the plan file untouched

On `(a)`:
  - For each `accepted_additions[]` entry, locate its `plan_step_ref`
    in the plan file using the step quote
  - Insert the addition as a new sub-bullet or sub-heading BELOW the
    original step, marked with a `(harden-plan)` tag so it's traceable:
    - For H3 steps: `### (harden-plan) <addition>`
    - For numbered list items: append `  - (harden-plan) <addition>`
  - Preserve all existing structure, headings, formatting, and
    unchanged text
  - Print per-step edit confirmations:
    > S3 → added: cross-FK validation step
    > S5 → added: use onConflictDoUpdate pattern

On `(b)`:
  - Generate a unified diff showing what WOULD be inserted
  - Print to terminal, do NOT write anything
  - Remind user: `git apply` does not work on printed diffs — they
    must save to a file first

On `(c)`: exit cleanly with the summary already printed.

**If `PLAN_SOURCE=inline` or `PLAN_SOURCE=plan-mode`**:

Skip the write-back prompt. Print the accepted additions in a copy-
pasteable code block so the user can splice them into their plan
manually:

```
<copy-paste block>
Plan additions from /harden-plan:

S3 (Security): Add cross-FK validation step...
S5 (Concurrency): Replace findExisting+branch with onConflictDoUpdate...
S6 (Round-trip): Add UI read-aggregation step for portionsOrdered/
                 portionsProduced/portionsSold...
```

### 3. Verdict recommendation

Print a final recommendation based on `skipped[]` content:

- **`ready-to-code`** — zero skipped OR only Minor skipped:
  > Plan is hardened. You can start coding.

- **`partial`** — some Moderate skipped but no Critical/Serious:
  > Plan is mostly hardened but has <N> open Moderate findings
  > (skipped). Safe to proceed but consider addressing during
  > implementation.

- **`needs-work`** — any Critical or Serious in `skipped[]`:
  > Plan has <N> open Critical/Serious findings. Recommend you iterate
  > on the plan and re-run `/harden-plan` before coding.

### 4. Exit

Do not commit. Do not create files (other than the plan file write-
back). Do not run builds or tests. The skill only reports + optionally
edits the plan file.

---

## 11 category definitions

These are injected verbatim into Subagent A's prompt in Phase 2. Each
category has a default severity that Subagent A can escalate with
`severity_reasoning`.

### P1. Intent coverage

Does the plan deliver the `stated_goal`? Trace each clause of the
goal to at least one step in `stated_steps`. Gaps are findings.

**Default severity**: Moderate (Serious if the gap is the stated
primary outcome of the PR).

**Worked example**:
- Goal: "Persist meal-level portion numbers in orders"
- Plan has steps for the write path but no step for the UI read path
- Finding: "Goal mentions persistence but plan has no step for
  reading the persisted values back into the UI. S3 persists 4
  fields; no step reads them on UI reload."
- Severity: Serious

### P2. Unnecessary complexity

Abstractions, config, or indirection not required by the goal.
Collapses scope-creep + overengineering into one bucket (same as
`/review-pr` Q2).

**Default severity**: Moderate.

**Worked example**:
- Plan creates a `PortionAggregationBuilder` class for a task that
  only needs one function call
- Finding: "Step S4 introduces a builder class for a one-shot
  aggregation. Goal doesn't require reusable aggregation; a function
  is simpler."
- Severity: Moderate

### P3. DRY (within-plan)

Duplicated logic across the plan's own steps. Not codebase-wide — P6
handles that.

**Default severity**: Moderate.

**Worked example**:
- Step S3 and Step S5 both describe validating `menuPlanId →
  accountId` with different wording
- Finding: "S3 and S5 duplicate the menu-plan ownership check.
  Extract to a shared helper referenced from both."

### P4. Performance

N+1 queries in plan steps, missing indexes for new WHERE clauses,
sequential awaits that should be `Promise.all`, unbounded
allocations.

**Default severity**: Serious if production-path, Moderate otherwise.

**Worked example**:
- Plan says "for each client, fetch their portions one at a time"
- Finding: "S6 loops over clients calling `getPortions` per client.
  Batch with an `IN` clause or a single JOIN."
- Severity: Serious

### P5. Security / multi-tenancy

**Default severity: Critical** for missing cross-FK validation on
write endpoints. Also covers: auth check coverage, input
sanitization, tenant isolation, secrets in code, unvalidated user
input reaching dangerous sinks.

**Required behavior**: for every new write endpoint, you MUST
address cross-FK validation. "No concerns" is invalid unless the
plan proves the endpoint is single-tenant-scoped or all FKs in the
request body are validated against the owned tenant root.

**Worked example (PR #4587 F1)**:
- Plan creates an upsert endpoint accepting `menuPlanId`,
  `menuPlanSheetId`, `accountMealId`, `menuPlanMealMenuId`
- Plan's auth step only validates `menuPlanId → accountId`
- Finding: "Upsert endpoint at S2 accepts 4 foreign keys but only
  validates ownership on `menuPlanId`. An authenticated attacker
  sends their own menuPlanId + a victim's sheetId/mealId — the row
  lands because FKs accept it, and the partial unique index prevents
  the victim's next legitimate save."
- Severity: Critical
- Recommended: "Add a step to validateMenuPlanOwnership that joins
  menuPlanSheetTable, menuPlanMealTable, and menuPlanMealMenuTable
  and asserts each belongs to the owned menuPlanId. One Promise.all
  of 3 SELECT 1 queries."

### P6. Reusability (codebase-wide)

Plan-declared symbols (functions, classes, components, hooks) that
already exist in shared packages. Uses the `/review-pr` Q6 STEP A /
STEP B algorithm, scoped to the plan's stated new symbols.

**Default severity**: Serious. Escalate to Critical if the existing
thing is in an auth / validation / crypto package.

**STEP A — Enumerate new symbols**: for every function / class /
interface / type / component / hook / method the plan proposes to
create, write one line `added <kind> <name> in <file>`.

**STEP B — Search aggressively**: for each enumerated item, run
exact-name `Grep` in `packages/` + `apps/`, plus semantic-root
`Grep` (drop domain prefixes/suffixes and search the remaining
verb/noun). Read candidate matches to verify they're real matches,
not substring collisions.

**Required audit field** — include `reusability_searches:` listing
the Grep/Glob calls you ran for STEP B. Empty = invalid.

**Worked example**:
- Plan says "create `tryCatch` helper at S7"
- Grep finds `packages/try-catch/src/index.ts` exports `tryCatch`
- Finding: "S7 creates `tryCatch`, but `@fileseye/try-catch` already
  exports it. Reuse instead."
- Severity: Serious

**Known limitation** — same as documented in `/review-pr` Q6:
P6 does NOT catch the case where an existing helper is called on
SOME code paths but should also be called on others. Flag those
under P9 Control-flow hazards instead.

### P7. Concurrency / atomicity

**Default severity: Serious**. Escalate to **Critical** if the write
is user-triggered on a concurrent cascade path (e.g., a single user
action fires 2+ parallel writes to the same row).

Every new write endpoint must be atomic or explicitly transaction-
wrapped. Flag:
- `findExisting + branch to create/update` patterns
- Sequential `SELECT → INSERT` without a transaction
- Race-prone duplicate detection via application logic
- Missing `ON CONFLICT DO UPDATE` / upsert primitives
- `setState → dispatch → setState` chains that could race on the
  frontend

**Required behavior**: for every new write step, you MUST address
atomicity. "No concerns" is invalid unless the plan explicitly uses
`onConflictDoUpdate`, `db.transaction(...)`, or a CAS primitive.

**Worked example (PR #4587 F2)**:
- Plan says "check if row exists via findExisting; if yes, update;
  if no, create"
- Finding: "S3 specifies `findExisting + branch` for the upsert.
  Two concurrent callers both miss in findExisting and both call
  create, hitting a unique-constraint violation (23505). Use
  `db.insert(...).onConflictDoUpdate(...)` with the partial-index
  targetWhere clause instead."
- Severity: Critical (UI has a cascade path firing concurrent
  writes on a single user gesture)
- Recommended: "Replace findExisting+branch in S3 with
  `onConflictDoUpdate` targeting the natural key. Inside a
  `db.transaction` so the history record write is atomic too."

### P8. Intent round-trip

**Default severity: Serious**.

For every new persisted field, the plan must specify the read path
that surfaces it. Flag fields that appear in a write step but have
no matching read-path step.

**Required behavior**: enumerate every new persisted field from the
plan's schema changes. For each, find the step that reads it.
Missing read-path is a finding.

**Worked example (PR #4587 F3)**:
- Plan schema step S1 adds 4 columns: `portionsPlanned`,
  `portionsOrdered`, `portionsProduced`, `portionsSold`
- Plan read step S6 only reads `portionsPlanned`
- Finding: "S1 persists 4 portion fields but S6 read aggregation
  only reads `portionsPlanned`. The other 3 fields will be write-
  only — their stored values won't surface on reload."
- Severity: Serious
- Recommended: "Update S6 to thread all 4 portion fields through
  the aggregation helper so all persisted values round-trip."

### P9. Control-flow hazards

**Default severity: Serious**.

Early returns that build synthetic empty responses (`return { x: [],
y: null, z: {} }`). Check `stated_files` imports vs the function's
injected services: if an early return hardcodes empty state for a
field that another branch populates via an injected helper, flag.

**This is the Q6-known-limitation gap** from `/review-pr` — P9
specifically catches what P6 misses.

**Worked example (PR #4587 F4)**:
- Plan says: "if rawClients.length === 0, early-return with
  `{ components: [], mealMenuPortions: [] }`"
- Plan also says: "inject mealMenuPortionsService and use
  `getByMenuPlanAndDateRange` on the happy path"
- Finding: "S4 early-returns with hardcoded `mealMenuPortions: []`,
  but S5's happy path fetches this from `mealMenuPortionsService`.
  The early-return silently drops stored meal-level portions in
  the empty-client state — exactly the state where stored
  aggregates should still surface."
- Severity: Serious
- Recommended: "Hoist the `mealMenuPortionsService` fetch above the
  early return (ideally in parallel with `getClientsWithOffers`
  via `Promise.all`) and return its result in both the early-exit
  and happy-path branches."

### P10. Error handling

**Default severity: Moderate**. Escalate to **Serious** if the error
path leaks user data, drops a write silently, or fires an empty
user-visible toast.

Flag:
- Silent failures (caught errors swallowed without logging)
- Bare `catch { }` blocks
- Empty error toasts (`message: undefined` fallthrough)
- `Promise.all` for independent mutations (recommend
  `Promise.allSettled` + per-rejection logging)
- Removed error handling in modified code
- Swallowed errors in mutation hooks (`onError: () => {}`)
- Raw DB errors leaking to user via general exception filter

**Worked example (PR #4587 F6)**:
- Plan says "wrap cascade batch + upsert in `Promise.all` with bare
  catch that just refetches"
- Finding: "S7 wraps two independent mutations (cascade batch +
  aggregate upsert) in `Promise.all` and catches errors silently
  with a bare refetch. Use `Promise.allSettled` + `console.error`
  per rejection so a failed upsert doesn't get lost when the
  cascade batch succeeds."
- Severity: Serious (a dropped write is user-visible on the next
  save attempt)

### P11. Pattern consistency

**Default severity: Moderate**. Escalate to **Serious** if the
missing pattern is security-relevant (e.g., sibling services use an
auth middleware this plan skips).

New files must match conventions of sibling files. Grounded by
Phase 2 Subagent B's `patterns` map. If sibling services all have
a history table via `writeHistoryRecord` and the new service plan
doesn't mention one, flag.

**Worked example (PR #4587 E2)**:
- Plan creates `MealMenuPortionsService`
- Subagent B finds 3 sibling services, all using `writeHistoryRecord`
  to persist audit rows on mutation
- Plan has no history-table step
- Finding: "S1 creates `MealMenuPortionsService` without a history
  table. 3 sibling services (`ClientPortionsService`,
  `OrderItemsService`, `MealPlansService`) all write to `gs_*History`
  tables via `writeHistoryRecord`. Missing parity means audits will
  have a gap at this endpoint."
- Severity: Moderate
- Recommended: "Add a step for `gs_MealMenuPortionsHistory` schema
  (matching `client-component-portions-history.ts` structure) +
  `writeMealMenuPortionHistoryRecord` helper matching sibling
  pattern. Wire it into the upsert transaction."

---

## Error handling

- **Input missing / unparseable** → stop-and-ask (Phase 1)
- **File path doesn't exist** → `Plan file not found: <path>`, abort
- **Plan is empty / < 10 lines** → `Plan is too short to harden —
  expand it first`, abort
- **Phase 2 subagent fails (one)** → degraded mode; run with the
  other and note in output header
- **Phase 2 both subagents fail** → abort with error message
- **Phase 3 critic pass drops all findings** → print `verdict:
  ready-to-code (no grounded concerns)`, skip Phase 4, go straight
  to Phase 5 summary
- **Phase 4 user types `abort`** → jump to Phase 5 with remaining
  as `skipped`
- **Phase 5 write-back fails (file locked, perms)** → print diff
  instead and tell user to apply manually
- **Repo map empty** (not a monorepo AND no `src/`) → warn and
  proceed with plan-text-only grounding; Subagent A's `grounding`
  field will cite plan text exclusively
- **Plan file modified externally during Phase 4** → detect via
  mtime check before Phase 5 write-back; if changed, skip write-
  back and print diff instead with warning

---

## Rules

- **NEVER** invoke `/harden-plan` after coding has started — redirect
  the user to `/review-pr` / `/fix-pr-review`.
- **NEVER** write code, run builds, commit, or push as part of this
  skill. The skill only reports + optionally edits the plan file.
- **NEVER** skip the Phase 1 grounding computation (repo map +
  service inventory + history inventory) — findings without repo
  grounding are hallucinations.
- **NEVER** skip the Phase 3 critic pass — ungrounded findings are
  slop. Dedupe, verify step refs, verify grounding, 3-prong
  challenge, gap check are all mandatory.
- **NEVER** accept a dismiss reason shorter than 10 chars or matching
  the forbidden-words list.
- **NEVER** batch multiple findings into one grill question. One
  question at a time, always, in severity order.
- **NEVER** proceed past Phase 4 without addressing (resolve /
  dismiss / skip / self-heal-drop) every finding in the queue.
- **NEVER** write-back to a plan file without explicit `(a)`
  approval — options `(b)` and `(c)` are read-only.
- **NEVER** silently drop a finding during the critic pass without
  logging it in the `Critic-pass drops` section of Phase 5.
- **NEVER** grill findings out of severity order — Critical →
  Serious → Moderate → Minor is mandatory.
- **NEVER** re-dispatch a Phase 2 subagent more than once per
  category during the Phase 3 gap check.
- **NEVER** invoke `/harden-plan` recursively (skill calling skill).
