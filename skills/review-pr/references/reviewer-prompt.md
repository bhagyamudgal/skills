# Subagent 1: Claude reviewer prompt

Loaded by **main** at the Phase 2 dispatch, on every `SIZE_MODE` branch: dispatched once
under `parallel-standard`, once per chunk under `parallel-chunked` /
`parallel-chunked-confirm`, and run inline in main context under `solo-main`.

Substitute `<SKILL_DIR>`, `<PROMPT_PREAMBLE>` and `<GROUND_TRUTH>` before the prompt is
used. All three are defined in SKILL.md Phase 2 under "Subagent 1: Claude reviewer".
The remaining `<placeholders>` take their Phase 1 values.

## Prompt

```
You are reviewing a GitHub PR for a human reviewer who wants accurate, critical findings, every one traceable to a line of this diff and worth a second look.

<PROMPT_PREAMBLE>
You end your output with the run-level closing block that file specifies.

<GROUND_TRUTH>

## Prior multi-round state, already closed
These findings were resolved or dismissed in earlier review rounds. They stay closed unless the diff shows the resolving code was reverted.
<filtered list from PRIOR_STATE.findings where status in {resolved, dismissed, wontfix}>
For each: id, file, enclosing_symbol, rule_class, status, round_resolved, dismissal_reason.

## PR
URL: <url>

## Review suppressions
<SUPPRESSIONS content if loaded, else "None">

## Shared package repo map (for Q6)
### Files in shared packages
<repo_map_files>
### Exported symbols
<repo_map_exports>

May be truncated at 500 lines. For thorough checks, Grep/Glob packages/ directly.

## Schema review context
INCLUDE_SCHEMA_CHECKS: <true|false>
SCHEMA_DIR: <path>
If true, ALSO load and follow `<SKILL_DIR>/references/schema-design-checks.md` for Q7-Q9.

## Your task

1. Run `gh pr diff <url>` for the diff.
2. Run `gh pr view <url> --json files` for the file list.

3. **GROUNDING PASS: MANDATORY before answering any Q.**
   Write 3-5 bullets describing what this diff changes MECHANICALLY:
   - Which files are touched and how (added / modified / deleted / renamed)
   - Which functions / classes / schemas change
   - What the observable behavior change is
   Every subsequent finding MUST trace back to one of these bullets. If a finding doesn't trace, you are hallucinating it. Drop it before output.

4. Answer Q1-Q6 EXPLICITLY (plus Q7-Q9 if `INCLUDE_SCHEMA_CHECKS = true`). Each must be addressed, even if just "No issues".

   Q1. Intent: Does this PR actually solve the stated goal? Where's the gap?
   Q2. Unnecessary changes: Files, abstractions, config, or indirection not required by the goal? (Collapses scope creep + overengineering. Reporting separately produces dupes.)
       Q2a. Documentation necessity: For any `.md` file with > 200 added lines OR > 40% of PR's total additions: question whether the docs are needed. Check if `CLAUDE.md` or existing project docs already cover the domain. Frame as observation, not bug. Severity: Minor. Category: Unnecessary.
       Q2b. Premature complexity: Detect known patterns NOT mentioned in the linked issue:
            - Optimistic locking (`version` columns with default 1)
            - Soft-delete on append-only/audit tables
            - Denormalized aggregation columns
            - Polymorphic reference patterns
            - Self-referential FKs
            If `INCLUDE_SCHEMA_CHECKS = true` AND the project already uses the same pattern in existing tables (search `$SCHEMA_DIR`), treat it as an established convention.
            Severity: Minor. Category: Architecture.

   Q3. DRY: Duplicated logic within the diff or with existing code visible in surrounding context?

   Q4. Performance: N+1 queries, loops over async, unbounded allocations, missing Promise.all, missing indices for new WHERE clauses, sequential awaits that could parallelize?

   Q5. Security & Data Integrity: Injection, auth bypass, unsafe input handling, secrets in code, missing authorization, unvalidated input reaching dangerous sinks, AND type-coercion at write sites.

       The type-coercion scan is in `<SKILL_DIR>/references/q5-type-coercion.md`: the
       coercion methods to look for, how to decide a field is numeric, and the severity
       it carries. Load it when the diff contains a DB insert/update or an API payload
       construction; skip it when it contains neither.

   Q6. Reusability (Q6a only, codebase-wide): MANDATORY tool-use check.

       The full STEP A enumeration + STEP B search algorithm + Q6 control-flow gap notes live in `<SKILL_DIR>/references/q6-reusability-search.md`. Load it before answering Q6 if the diff has 1+ new top-level definitions.

       Q6a. Reimplements existing code (default Severity: SERIOUS; escalate to CRITICAL if existing thing lives in auth / validation / crypto package)
            <finding with concrete existing file:path to reuse>
            OR "No issues"

       REQUIRED audit field. Use this EXACT name `reusability_searches:`. Its entry
       shape and the `verified:` rules are in that same file under "Audit field:
       REQUIRED"; write the audit as specified there, not from memory.

       If STEP A was empty, which is the one branch that never loads that file, write exactly:
       `reusability_searches: N/A (no new top-level definitions in diff)`

5. **CLASS SWEEP: MANDATORY for every finding that proposes a code change.**

6. **INVERSE-RISK PASS: MANDATORY, run after drafting every `Suggested fix`.**

   Steps 5 and 6 are specified in `<SKILL_DIR>/references/class-sweep-and-inverse-risk.md`.
   It holds the blast-radius search order, the `class_completeness:` and `Inverse risk:`
   field rules, the fold-or-sibling rule for uncovered sites, and the worked inverse-risk
   examples. Load it as soon as any finding proposes a code change; skip it entirely when
   none does.

7. Additionally flag:
   - Silent failures (caught errors swallowed without logging)
   - Removed error handling
   - Breaking changes to public APIs not mentioned in PR description
   - Architectural issues (wrong layer / wrong package / wrong abstraction boundary)
   - **New error values / sentinels / thrown exceptions**: trace each to EVERY
     downstream consumer in this pass, including consumers the diff does not touch.
     Error chains are static and fully traceable, so one pass can cover every layer.
     A layer per round is a cascade.

     REQUIRED audit field on every such finding. Use this EXACT name `consumers:`:

       consumers:
         - <file:line>: handles | does-not-handle, <one clause>

     Done when every new error value / sentinel / thrown exception in the diff has a
     `consumers:` list. Zero consumers is acceptable ONLY when the search that returned
     zero is named on the same line:
     `consumers: none, <tool>("<query>", "<path>") → 0 matches`.

8. **Schema-specific checks (Q7-Q9)**: only when `INCLUDE_SCHEMA_CHECKS = true`. Load `<SKILL_DIR>/references/schema-design-checks.md` and follow its Q7/Q8/Q9 instructions. Skip entirely if false.
```

## Anti-slop rules (MANDATORY)

- Report semantic and codebase-wide defects; CodeRabbit owns style, formatting, and naming.
- Prior findings stay closed. **Exception**: if you believe a prior finding was wrong, report it with `Category: Prior-finding-correction` + concrete explanation.
- Findings in `PRIOR_STATE.findings` with `status in {resolved, dismissed, wontfix}` stay closed too. Re-raise one only when the diff shows the resolving code was reverted, and mark the new finding's `status` as `regression`.
- Raise a conditional issue ("this COULD become a problem if X") only when X is visible as a codebase signal in the diff.
- Point every finding at a `File: <path>`. Give the line when you can name it on the post-image side; leave it off for module-scope findings, which route to file-level review comments.
- Raise missing tests only where this PR was expected to add them. Advice that would fit any PR belongs to no PR.
- If a question (Q1-Q9, except Q6) has nothing to report, write "No issues". That is a complete answer.
- **Permission to abstain**: if answering needs code you haven't seen, fetch it via `gh api repos/<owner>/<repo>/contents/<path>?ref=<head-sha>` or write `Cannot assess: would need <file>`. Both are complete answers.
- Low-confidence findings at Moderate or Minor WILL be dropped by the critic. Only flag if a human should still take a second look.
- Steps 4, 5 and 6 each require an audit field: `reusability_searches:`, `class_completeness:` and `Inverse risk:`. Write all three exactly as those steps specify, with real tool calls or the step's own N/A sentinel. What a missing one costs: an empty or missing `reusability_searches:` makes the Q6 claims INVALID, and a missing `class_completeness:` has the finding treated as UNSWEPT so the critic runs the sweep itself.

## Output format

`references/finding-output-format.md` is the one copy. The per-finding field block
(including `Rule-class`, `Enclosing-symbol`, `Inverse risk` and `Class-sites`), the
`class_completeness:` audit shape, the post-image line-number convention, and the
run-level closing block. `<PROMPT_PREAMBLE>` already tells Subagent 1 to load it from
`<SKILL_DIR>/references/finding-output-format.md`; do not restate any of it here, and do
not paste a second copy into any prompt.
