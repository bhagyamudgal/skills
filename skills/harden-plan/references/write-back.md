# Write-back — applying accepted additions to the plan file

Loaded by **main** in Phase 5 when `PLAN_SOURCE=file`.

**External-modification check — before anything else**: compare
`PLAN_FILE`'s current mtime against the one stashed in Phase 1. If it
changed, the plan was edited during Phase 4 — skip write-back, print the
diff instead, and say why.

**Only if `PLAN_SOURCE=file`**:

Present via AskUserQuestion: "Apply accepted plan additions back to `<PLAN_FILE>`?"

Options:
- "Write — insert additions in place" — inserts additions as sub-steps directly into the plan file
- "Diff — print only" — shows a unified diff; you apply manually
- "Exit — leave untouched" — keeps the plan file as-is

On **Write**:
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
  - If the write fails (file locked, permissions), print the diff
    instead and tell the user to apply it manually

On **Diff**:
  - Generate a unified diff showing what WOULD be inserted
  - Print to terminal, do NOT write anything
  - Remind user: `git apply` does not work on printed diffs — they
    must save to a file first

On **Exit**: print nothing; leave the plan file untouched.

**If `PLAN_SOURCE=inline` or `PLAN_SOURCE=conversation`**:

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
