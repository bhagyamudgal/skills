# Phase 3 verification subagents (V1 / V2 / V3)

Loaded by main in Phase 3, at the first of steps 4.55 / 4.9 / 6 whose dispatch condition holds. Keep it loaded for the others, since all three go out in one message. This file owns the verifier orchestration main must obey: the 4-subagent cap with V1 batching, and the degraded-mode rule. The judgment-vs-evidence split lives in SKILL.md Phase 3. This file also holds each verifier's dispatch condition and its exact prompt.

Cap: **at most 4 verification subagents in total.** V2 and V3 are one each by nature: V2 reads a short prior-state list, V3 runs one gap check. Only V1 batches, so it gets at most 2, at 10 findings per subagent. Findings past V1's first 20, ordered Critical → Minor, are verified inline in main. If a verifier errors or returns empty, run its step inline in main and note `<verifier> unavailable, so verified inline` in the Phase 4 header.

All three are `general-purpose`, dispatched in ONE message so they run in parallel, and all three fetch what they need themselves (`gh pr diff`, Grep, Read) rather than being handed the diff. Each returns a compact block, no prose, no restated file contents.

Substitute `<SKILL_DIR>` in every prompt below before dispatching, exactly as defined in `<SKILL_DIR>/references/dispatch-prompts.md`. Verifiers inherit the user's repo as their working directory, so a bare `references/...` path resolves against that repo and silently finds nothing. V3's prompt also carries `<PROMPT_PREAMBLE>`: the shared reference-paths + output-format block defined in `<SKILL_DIR>/references/dispatch-prompts.md` (pointed at from SKILL.md Phase 2); substitute it there with `<SKILL_DIR>` already resolved.

---

## V1: Class-sweep verifier (step 4.55)

Dispatch when ANY finding has a missing `class_completeness` audit, a verdict of `INCOMPLETE`, or an `Enclosing-symbol` that is exported or lives in a shared package.

```
For each finding below, find EVERY site in the repo matching its rule_class signature,
meaning its whole blast radius, callers included when the symbol is exported.

Report per finding, nothing else, in the SAME shape the reviewer's `class_completeness:`
audit uses (canonical copy: `<SKILL_DIR>/references/finding-output-format.md`), so main
never reconciles two schemas:
  finding: <id>
  signature: <the literal/pattern actually searched>
  search: <tool>("<query>", "<path>") → <N> sites
  sites:
    - <file:line or symbol>: affected | not-affected, <one clause why>
  verdict: COMPLETE (all N sites reported) | INCOMPLETE (<M> unreported sites)

`affected` means the site exhibits this rule_class; `not-affected` means you looked and it
does not. Never write `handled`. That is the state file's separate, later question.

Do not judge severity. Do not suggest fixes. Report sites.
```

---

## V2: Regression sweep verifier (step 4.9)

Dispatch when `CURRENT_ROUND >= 2` and `PRIOR_STATE.findings` contains any entry with `status in {resolved, dismissed, wontfix}`. Pass each entry's `id`, `rule_class`, `class_sites`, `inverse_risk`, `depends_on`, `commit_sha_resolved`, and the current `head_sha`.

```
These findings were closed in earlier rounds. At the CURRENT head, verify each is still
closed. For each, check in this order:
  1. class_sites: is every listed site still handled? Are there NEW sites of this
     rule_class that the current diff introduced?
  2. inverse_risk: has that specific failure mode appeared in the resolving code?
  3. depends_on: is the code condition the dismissal rested on still true?
  4. lineage, one hop only, and only when 1-3 put this finding at `regressed`, blame the
     cited line (`git blame -L <line>,<line>` locally,
     `gh api repos/<owner>/<repo>/commits?path=<path>&sha=<head_sha>` cross-repo). Name a
     prior finding ONLY when the blame commit is one of the `commit_sha_resolved` values
     passed to you; otherwise null. Do not walk back through parent commits.
Report per finding, nothing else:
  id: <id>
  verdict: still-closed | regressed | dismissal-void
  evidence: <file:line + one sentence. REQUIRED when not still-closed>
  caused_by: <id of the prior finding whose commit_sha_resolved is the blame commit, or null>
Default to still-closed when you cannot find evidence of a regression.
```

---

## V3: Deep gap check (step 6)

Dispatch when `additions + deletions >= 500` **AND** main lacks the full diff, the same
pair of conditions SKILL.md step 6 states. Size alone never triggers it. When main still
holds the whole diff it runs the gap check inline. A subagent has the context budget to run
the check against the diff itself instead of guessing from a file list.

Pass `INCLUDE_SCHEMA_CHECKS` and `SCHEMA_DIR` through from Phase 1. V3 is dispatched
on the large PRs where schema changes live. A dropped flag loses Q7-Q9 where they matter most.

```
Fetch the diff yourself. The reviewers reported findings in these categories: <list>.
For each category with NO findings, check whether the diff genuinely has nothing, or
whether it was overlooked:

  Q1 intent, Q2 unnecessary, Q3 DRY, Q4 performance, Q5 security, Q6 reusability

INCLUDE_SCHEMA_CHECKS: <true|false>
SCHEMA_DIR: <path>
If true, ALSO cover Q7 (table overlap), Q8 (1:1 consolidation) and Q9 (cross-table FK):
load `<SKILL_DIR>/references/schema-design-checks.md` and follow it. If false, omit Q7-Q9
entirely; do not emit lines for them.

<PROMPT_PREAMBLE>
Report findings only; main composes the run-level verdict.

Report ONE entry per category, nothing else:
  Q<N>: no gap
  Q<N>: gap, followed by the full finding block in the shape above

A cleared category is exactly one line. Every category in scope gets exactly one entry.
"no gap" on all of them is a complete answer.
```
