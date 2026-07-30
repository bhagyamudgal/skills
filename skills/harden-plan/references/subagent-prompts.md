# Phase 2 subagent prompt templates

Loaded by **main** at the Phase 2 dispatch. Both templates below take
Phase 1 values in their `<placeholders>` — `stated_goal`, `stated_steps`,
`stated_files`, `stated_out_of_scope`, `repo_map_files`,
`repo_map_exports`, `existing_services_inventory`,
`existing_history_tables`.

## Subagent A — Category analyzer (`general-purpose`)

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

   Load `<SKILL_DIR>/references/category-checks.md` before answering
   anything. It holds P1–P11: each category's scope, its default
   severity, its invalidity gate, and one worked example. Answer all 11
   from that file — a category you did not open is a category you did
   not answer.

3. Verify every finding against the actual codebase. Don't guess at
   symbol names — search for them. Don't assume a helper exists — grep
   for it.

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
```

## Subagent B — Pattern inventory (`general-purpose`)

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
