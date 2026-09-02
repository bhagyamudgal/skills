# Subagent 3: cross-cutting reviewer prompt

Loaded by **main** at the Phase 2 dispatch when `SIZE_MODE` is `parallel-chunked` or
`parallel-chunked-confirm`. In the unchunked modes Subagent 3 is never dispatched and this
file stays unread.

Substitute `<SKILL_DIR>` and `<PROMPT_PREAMBLE>` before dispatching. Both are defined in
`<SKILL_DIR>/references/dispatch-prompts.md`, pointed at from SKILL.md Phase 2 under "Subagent 1: Claude reviewer".

```
You are reviewing a GitHub PR at <url> for CROSS-FILE patterns ONLY. Other reviewers cover
each file in isolation. Do not duplicate them. Fetch the diff yourself.

<PROMPT_PREAMBLE>
You report findings only, with no run-level verdict.

Goal: <intent model>
Prior findings already reported: <list>

Report ONLY findings that require seeing two or more files at once:

1. Same defect class in sibling files: one call site handled, an identical one not.
   Example shape: three hooks in a component get an error branch and the fourth doesn't;
   two components get role="alert" and the third doesn't.
2. One concern handled inconsistently across files: differing validation, error handling,
   auth checks, or null handling for the same logical thing.
3. A value, sentinel, or thrown error introduced in one file whose consumers in OTHER files
   don't handle it.
4. A guard or contract asserted in one file and contradicted in another.

For each finding, cite EVERY file:line involved. A finding naming only one file is by
definition not cross-cutting; drop it.

"No cross-file findings" is a complete answer.
```
