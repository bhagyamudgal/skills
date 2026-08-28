# Finding output format

The single shape every reviewer and verifier emits a finding in. Loaded by **Subagent 1**
(Phase 2 reviewer), **Subagent 3** (Phase 2 cross-cutting reviewer) and **V3** (Phase 3
deep gap check) — all three produce findings that Phase 3 dedupes, sweeps and persists,
and without this file each invents a shape that dedupe and step 4.55 cannot parse.
`q6-reusability-search.md` points here too, so a Q6a finding comes out in the same shape
as every other finding.

Emit the fields verbatim, one per line, in the order below.

## Line number convention

`File: <path:line>` must use the **post-image line number** — the line as it appears in
the new version (the `+` side of the unified diff hunk, or unchanged context on the new
side). NOT old-side. NOT the diff hunk header offset. Omit `:line` for module-scope
findings; they route to file-level review comments.

## Per-finding block

```
Severity:    Critical | Serious | Moderate | Minor
Confidence:  high | medium | low
File:        <path:line> (or <path> alone for module-scope)
Category:    Intent | Unnecessary | DRY | Performance | Security |
             Reusability | Silent-failure | Breaking-change |
             Architecture | Prior-finding-correction
Rule-class:  <2-3 word slug — e.g., silent-failure, n+1-query, error-code-wrong-branch>
Enclosing-symbol: <function/class/component containing the cited line, or "<module>">
Issue:       <one sentence>
Why it matters: <one sentence>
Suggested fix:  <one sentence, actionable>
Inverse risk:   <the failure mode this fix trades INTO if implemented literally,
                 or "none — pure addition">
Class-sites:    <A>/<N> — affected sites over sites searched, from the
                class_completeness audit below
```

`Inverse risk` and `Class-sites` are REQUIRED on every finding that proposes a code
change — one field per cascade feeder. `/fix-pr-review` seeds its own inverse-risk check
and class sweep from these two lines, so a finding printed without them costs the next
skill a full re-derivation.

`Rule-class` and `Enclosing-symbol` are required too — they let the critic compute a
stable finding ID (`sha1(file::enclosing_symbol::rule_class)`) that survives line shifts
and rewordings across review rounds. Load
`<SKILL_DIR>/references/finding-state-schema.md` for the exact ID derivation, the
normalization it assumes on both fields, and the `status` values a finding may carry.

## `class_completeness:` audit

Required on every finding that proposes a code change. Use this EXACT field name so
Phase 3 step 4.55 can parse it:

```
class_completeness:
  - finding: <the Issue, trimmed>
    rule_class: <slug>
    signature: <the literal/pattern actually searched>
    search: <tool>("<query>", "<path>") → <N> sites
    sites:
      - <file:line or symbol>: affected | not-affected — <one clause why>
    verdict: COMPLETE (all N sites reported) | INCOMPLETE (<M> unreported sites)
```

`affected` means the site exhibits this `rule_class`; `not-affected` means the sweep
looked and it does not. `Class-sites: <A>/<N>` is the count of `affected` entries over
the total number of entries in `sites:`.

Do NOT write `handled` in this audit. `handled` belongs to a different, later layer:
`class_sites[].handled` in `<SKILL_DIR>/references/finding-state-schema.md` records
whether the PR has since COVERED an affected site, and only affected sites are carried
into that list. One word per layer — conflating them makes a merely-swept finding look
fixed.

If the finding proposes no code change, write exactly:
`class_completeness: N/A (no code change proposed)`.

## Run-level closing block

A reviewer whose scope is the WHOLE PR (Subagent 1 in unchunked modes) ends its output
with:

```
Senior engineer approval: Yes | No
Approval reason: <one sentence>
Summary: <3 sentences — what the PR does, biggest concern, overall verdict>
Verdict: approve | request-changes
```

Chunk reviewers, Subagent 3 and V3 report findings only — their scope is partial, so main
composes the run-level verdict in Phase 3.
