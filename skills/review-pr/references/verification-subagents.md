# Phase 3 verification subagents (V1 / V2 / V3)

Loaded by main in Phase 3, at the first of steps 4.55 / 4.9 / 6 whose dispatch condition holds — keep it loaded for the others, since all three go out in one message. SKILL.md keeps the rules main itself must obey: the judgment-vs-evidence split, the 4-subagent cap, and the degraded-mode rule. This file holds each verifier's dispatch condition and its exact prompt.

All three are `general-purpose`, dispatched in ONE message so they run in parallel, and all three fetch what they need themselves (`gh pr diff`, Grep, Read) rather than being handed the diff. Each returns a compact block — no prose, no restated file contents.

V1 and V3 emit projections of `references/finding-output-format.md`: V1 the `class_completeness:` audit alone, V3 the full per-finding block. Neither prompt reproduces those shapes — it loads the file and names its subset, so main never reconciles two schemas. V2's output is not a finding shape at all: it reports on findings that already exist, so its four lines are defined here.

V3 also loads `references/lens-map.md` and `references/lenses.md`, because its gap check runs two axes and only one of them is the Q list. See "The lens axis" in its prompt below.

Substitute `<SKILL_DIR>` in every prompt below before dispatching, exactly as for Subagent 1 (SKILL.md, Phase 2). Verifiers inherit the user's repo as their working directory, so a bare `references/...` path resolves against that repo and silently finds nothing.

---

## V1 — Class-sweep verifier (step 4.55)

Dispatch when ANY finding has a missing `class_completeness` audit, a verdict of `INCOMPLETE`, a `verdict: COMPLETE` whose `search:` line names no tool call, or an `Enclosing-symbol` that is exported or lives in a shared package.

The third arm is not redundant with the first. `SKILL.md` step 4.55 treats a tool-call-free `COMPLETE` as an audit that was never run, and routes it to V1 — so a run whose only such finding sits on a local, unexported symbol matches none of the other arms, V1 never goes out, and the step cannot reach its own done-condition of a non-empty `Class-sites` on every finding.

```
SKILL_DIR: <SKILL_DIR>
Your working directory is the user's repo, not the skill directory, so the
`<SKILL_DIR>/references/...` path below is absolute and must be used as written.

For each finding below, find EVERY site in the repo matching its rule_class signature —
its whole blast radius, callers included when the symbol is exported.

## Output format
Load `<SKILL_DIR>/references/finding-output-format.md` and emit its `class_completeness:`
audit shape, once per finding, with two substitutions:
  - the `finding:` line carries the id you were passed, not the trimmed Issue text —
    main matches your report back to its findings by id, and prose does not match
  - omit the `rule_class:` line — main already holds the rule_class for each id it
    passed you

Everything else in that shape is unchanged, the `affected` / `not-affected` /
never-`handled` vocabulary included. Emit nothing outside the audit — no `Severity:`, no
prose, no restated file contents; the fields of the finding block itself are not yours to
write. Do not judge severity. Do not suggest fixes. Report sites.
```

---

## V2 — Regression sweep verifier (step 4.9)

Dispatch when `CURRENT_ROUND >= 2` and the closed set is non-empty. A finding is in the closed set when **either** its `PRIOR_STATE.status` is in `{resolved, dismissed, wontfix}` **or** its `github_thread_id` resolves to a thread GitHub reports as `isResolved: true` — the same two-arm set `SKILL.md` step 4.9 builds, and the arms must match or the step dispatches over one population and reports over another.

**Do not key the dispatch on `status` alone.** `dismissed` is written automatically when the user deselects a finding, but `resolved` has no automated writer — on any machine where nobody hand-edits the state YAML nothing is ever `resolved`, so a status-only condition never fires the GitHub arm and this verifier goes out on dismissals only, or not at all. `resolved` is the arm the regression case lives on: a finding that *was fixed* and came back. Thread state is the signal that actually moves, because merging requires resolving threads.

Read `isResolved` as evidence a thread was **closed**, never that the finding was **correct**. Where a repository ruleset requires thread resolution to merge, authors resolve findings they dispute in order to ship, so a resolved thread is a fact about the merge queue and not an agreement with the review.

Pass each entry's `id`, `rule_class`, `class_sites`, `inverse_risk`, `depends_on`, `commit_sha_resolved`, and the current `head_sha`. An entry that qualifies on thread state alone carries no `commit_sha_resolved` — pass it as null rather than substituting the head or the thread's commit. V2's lineage hop matches blame against those values, and a fabricated one attributes the reopen to a finding that never resolved it.

```
These findings were closed in earlier rounds. At the CURRENT head, verify each is still
closed. For each, check in this order:
  1. class_sites — is every listed site still handled? Are there NEW sites of this
     rule_class that the current diff introduced?
  2. inverse_risk — has that specific failure mode appeared in the resolving code?
  3. depends_on — is the code condition the dismissal rested on still true?
  4. lineage, one hop only, and only when 1-3 put this finding at `regressed` — blame the
     cited line (`git blame -L <line>,<line>` locally,
     `gh api repos/<owner>/<repo>/commits?path=<path>&sha=<head_sha>` cross-repo). Name a
     prior finding ONLY when the blame commit is one of the `commit_sha_resolved` values
     passed to you; otherwise null. Do not walk back through parent commits.
Report per finding, nothing else:
  id: <id>
  verdict: still-closed | regressed | dismissal-void
  evidence: <file:line + one sentence — REQUIRED when not still-closed>
  caused_by: <id of the prior finding whose commit_sha_resolved is the blame commit, or null>
Default to still-closed when you cannot find evidence of a regression.
```

---

## V3 — Deep gap check (step 6)

Dispatch when `additions + deletions >= 500` **AND** main lacks the full diff — the same
pair of conditions SKILL.md step 6 states. Size alone is not the trigger: when main still
holds the whole diff it runs the gap check inline. A subagent has the context budget to run
the check against the diff itself where main would be guessing from a file list.

Pass `INCLUDE_SCHEMA_CHECKS` and `SCHEMA_DIR` through from Phase 1. V3 is dispatched
precisely on the large PRs where schema changes live, so a dropped flag drops Q7–Q9 exactly
where they were most likely to fire.

**The gap check has two axes and the Q list is only one of them.** Most of the lens
catalogue is marked `q_map: new-ground` — no Q-number reaches it — so a gap check that walks
Q1–Q9 and stops returns "no gap" over ground it never looked at. That is `L15` (a check that
cannot fail) inside the verifier whose job is to catch it, and it is why the prompt below
loads the map and iterates the lens axis explicitly.

```
Fetch the diff yourself. Cover EVERY category below and emit an entry for each. The
reviewers already reported findings in these categories: <list> — that list tells you
where a reviewer has already been, not which categories to skip. For a category on it,
"no gap" means you found nothing FURTHER; for one absent from it, "no gap" means you
checked and the diff genuinely has nothing:

  Q1 intent, Q2 unnecessary, Q3 DRY, Q4 performance, Q5 security, Q6 reusability

Answering only the categories nobody reported is the failure this check exists to catch:
a reviewer that stopped early reports one shallow finding in a category and clears it.

INCLUDE_SCHEMA_CHECKS: <true|false>
SCHEMA_DIR: <path>
If true, ALSO cover Q7 (table overlap), Q8 (1:1 consolidation) and Q9 (cross-table FK) —
load `<SKILL_DIR>/references/schema-design-checks.md` and follow it. If false, omit Q7-Q9
entirely; do not emit lines for them.

## The lens axis — the second half of this check
Load `<SKILL_DIR>/references/lens-map.md` and read its `lens_index`. Every entry whose
`q_map` is `new-ground` sits outside Q1-Q9 entirely: no question above can clear it, and
clearing the Q list says nothing about it. Take that set and cover it over the same diff,
one entry per lens, in `lens_index` order.

Load `<SKILL_DIR>/references/lenses.md` for each one's trigger, its question, and its "not
a finding" list before you judge it. The trigger is what keeps this axis cheap — most
lenses have no trigger present in a given diff, and a lens whose trigger is absent is one
line. Do not answer from the lens NAME; the names are mnemonics and several of them read
as broader or narrower than the lens actually is.

Skip the `META` entry. It is an attention rule, not a defect class — it raises the tier of
a silent finding rather than producing findings of its own — so apply it when you write
`Severity:` and emit no entry for it.

You are checking the diff as a whole, not per-file cells. The map's `always_on`,
`file_types` and `signals` sections decide which cells each file owes, and that ledger
belongs to the Phase 2 reviewers: do not fill it, do not contradict it, do not report
verdicts in its vocabulary. Your question is narrower — did anything of this lens's shape
enter this diff that no reviewer reported?

## Output format
SKILL_DIR: <SKILL_DIR>
Your working directory is the user's repo, not the skill directory, so the
`<SKILL_DIR>/references/...` paths above and below are absolute and must be used as
written. Load `<SKILL_DIR>/references/finding-output-format.md` before you write any
finding and emit the FULL per-finding block defined there plus its `class_completeness:`
audit — every field, none omitted. A finding in any other shape is unparseable to the
Phase 3 critic and is dropped. Report findings only; the run-level header is main's.

The block's `Lens:` field carries the lens id you were on when you raised it. A finding
raised off the Q axis, which no lens produced, writes `none — Q<N>`. That field is what
links a finding to its ledger cell; a lens-axis finding that leaves it blank reports a gap
the ledger cannot account for.

Report ONE entry per Q category and ONE per `new-ground` lens, nothing else. Q entries
first, then lens entries in `lens_index` order:
  Q<N>: no gap
  Q<N>: gap — followed by the full finding block in the shape above
  L<N>: no gap
  L<N>: gap — followed by the full finding block in the shape above

A cleared entry is exactly one line. Every category and every `new-ground` lens in scope
gets exactly one entry, and both counts are checkable against the lists you read them from
— a short report is a dropped axis, not a clean one. "no gap" on all of them is a complete
answer.
```

Main reconciles the returned entries against both lists before folding the findings in — Q
entries against the full in-scope category list (Q1–Q6, plus Q7–Q9 when
`INCLUDE_SCHEMA_CHECKS` is true), lens entries against `lens_index`'s `new-ground` set less
`META`. **Not** against the already-reported-categories list it passed in: that list is the
complement of what a skip-the-covered-ones reading would return, so reconciling against it
flags every entry V3 sends. A missing entry on either axis is re-run inline, never read as
`no gap`:
silence from a verifier is the same failure as silence from a reviewer, one layer up, and
this verifier's whole purpose is to catch that shape.
