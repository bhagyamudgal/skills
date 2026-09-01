# Grill loop: one finding at a time

Loaded by **main** in Phase 4 when findings remain after the Phase 3
critic pass. Walk `findings_queue` in severity order, presenting ONE
finding per message via AskUserQuestion and waiting for the user's
response before moving to the next.

### Question block format (for the AskUserQuestion question field)

```
[<id> · <severity> · <category>]  (<n> of <total>)

Finding:     <concern in 1-2 sentences>
Risk:        <why it matters — 1-2 sentences; for Critical/Serious,
              include a concrete failure scenario>
Plan step:   <plan_step_ref> — "<1-line quote from the plan>"
Grounding:   <1 sentence of concrete evidence — file:line or plan text>

Question:    <suggested_question>
Recommended: <recommended_answer>
```

Do NOT include a plain-text `(y / n / other / skip)` line. The options are encoded in the AskUserQuestion tool call.

### Response handling

**`y`: resolved (accept recommendation)**

Mark finding resolved. Append the `recommended_answer` to
`accepted_additions[]` with its `plan_step_ref`. Move to next.

**`n`: dismissed**

The reason arrives from the follow-up AskUserQuestion that fires once the
user picks Dismiss. It is REQUIRED and must be ≥ 10 characters. If missing
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

**`other <alt>`: user provides a custom answer**

Capture `alt` verbatim into `accepted_additions[]` as the resolution
instead of the `recommended_answer`. No length check. The user knows
what they want. Move to next.

**`skip`**

Finding stays unresolved. Record in `skipped[]`. Move to next.

### Self-heal branch (false-positive verification)

If the user's `n <reason>` or `other <alt>` claims "already covered by
X" or "exists in Y" (keywords: `already`, `covered in`, `exists in`,
`handled by`, `done in`), run a quick verification before accepting:

1. Extract the reference (`X` or `Y`): typically a file path, symbol
   name, or step reference
2. `Grep` the reference in cwd (if it's a symbol) or `Read` the file
   (if it's a path)
3. If found AND matches the user's claim → silently DROP the finding
   (don't count as dismissed), log `Self-heal drop: <id> — <user
   claim> verified`, move to next
4. If not found → push back:
   > Couldn't find `<X>` in the codebase. Can you point me at the exact
   > file or line? Otherwise I'll record this as dismissed.

### Abort branches

- User types `abort` / `quit` → stop grilling, jump to Phase 5 with
  remaining findings as `skipped`
- User provides 3 consecutive `skip`s → present via AskUserQuestion:
  "You've skipped 3 in a row. Want to bail out and get a summary?"
  Options: "Bail out — show summary" and "Keep going"

### One question at a time: STRICT

Do NOT batch findings into a single prompt. Do NOT emit multiple
questions in one message. Do NOT pre-answer questions for the user.
