# Phase 3 verification subagents (V1 / V2 / V3)

Loaded by main in Phase 3, at the first of steps 4.55 / 4.9 / 6 whose dispatch condition holds — keep it loaded for the others, since all three go out in one message. SKILL.md keeps the rules main itself must obey: the judgment-vs-evidence split, the 4-subagent cap, and the degraded-mode rule. This file holds each verifier's dispatch condition and its exact prompt.

All three are `general-purpose`, dispatched in ONE message so they run in parallel, and all three fetch what they need themselves (`gh pr diff`, Grep, Read) rather than being handed the diff. Each returns a compact block — no prose, no restated file contents.

---

## V1 — Class-sweep verifier (step 4.55)

Dispatch when ANY finding has a missing `class_completeness` audit, a verdict of `INCOMPLETE`, or an `Enclosing-symbol` that is exported or lives in a shared package.

```
For each finding below, find EVERY site in the repo matching its rule_class signature —
its whole blast radius, callers included when the symbol is exported.

Report per finding, nothing else — the SAME shape the reviewer's `class_completeness:`
audit uses, so main never reconciles two schemas:
  finding: <id>
  signature: <the literal/pattern actually searched>
  search: <tool>("<query>", "<path>") → <N> sites
  sites:
    - <file:line or symbol>: affected | not-affected — <one clause why>
  verdict: COMPLETE (all N sites reported) | INCOMPLETE (<M> unreported sites)

Do not judge severity. Do not suggest fixes. Report sites.
```

---

## V2 — Regression sweep verifier (step 4.9)

Dispatch when `CURRENT_ROUND >= 2` and `PRIOR_STATE.findings` contains any entry with `status in {resolved, dismissed, wontfix}`. Pass each entry's `id`, `rule_class`, `class_sites`, `inverse_risk`, `depends_on`, `commit_sha_resolved`, and the current `head_sha`.

```
These findings were closed in earlier rounds. At the CURRENT head, verify each is still
closed. For each, check in this order:
  1. class_sites — is every listed site still handled? Are there NEW sites of this
     rule_class that the current diff introduced?
  2. inverse_risk — has that specific failure mode appeared in the resolving code?
  3. depends_on — is the code condition the dismissal rested on still true?
Report per finding, nothing else:
  id: <id>
  verdict: still-closed | regressed | dismissal-void
  evidence: <file:line + one sentence — REQUIRED when not still-closed>
Default to still-closed when you cannot find evidence of a regression.
```

---

## V3 — Deep gap check (step 6)

Dispatch when `additions + deletions >= 500` — the case where main lacks the full diff. A subagent has the context budget to run the gap check against the diff itself.

```
Fetch the diff yourself. The reviewers reported findings in these categories: <list>.
For each category with NO findings — Q1 intent, Q2 unnecessary, Q3 DRY, Q4 performance,
Q5 security, Q6 reusability — check whether the diff genuinely has nothing, or whether it
was overlooked.

Report ONE line per category, nothing else:
  Q<N>: no gap | gap — <finding in the standard output format>

Every category in the list above gets exactly one line, including the ones you clear.
"no gap" on all of them is a complete answer.
```
