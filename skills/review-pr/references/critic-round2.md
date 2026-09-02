# Critic pass, round 2 and later

### 4.9. Proactive regression sweep (runs before prior-state suppression, 4.95)

Skip entirely when `CURRENT_ROUND == 1`.

Step 4.95 below only re-examines a resolved finding when a reviewer happens to re-raise
its exact ID: regressions caught by luck. This step catches them on purpose.

Dispatch **V2: Regression sweep verifier** over EVERY finding in `PRIOR_STATE` with
`status in {resolved, dismissed, wontfix}`, regardless of whether any reviewer mentioned it
this round. V2 gathers the evidence; main applies the rules below to its verdicts:

1. **Re-verify by `rule_class`, not by ID hash.** The ID is
   `sha1(file::enclosing_symbol::rule_class)`, so the same defect resurfacing in a
   sibling symbol produces a DIFFERENT id and escapes matching entirely. Search the
   stored `class_sites`, plus any new sites the current diff added, for the class
   signature. A resolved finding whose class has an unhandled site is not resolved:
   reopen it with `status: regression` and cite the specific site.

2. **Check the stored `inverse_risk`.** If the fix that resolved this finding recorded
   an inverse risk, confirm that failure mode is absent at the current head. This is
   the cascade caught one round early.

3. **Re-validate dismissals against `depends_on`.** A `wontfix` records the code
   condition its rationale rests on. If a later commit invalidated that condition, the
   dismissal is void. Reopen with `status: active` and note which commit voided it.

4. **Attribute the lineage: bounded to one hop.** Blame the finding's cited line
   (`git blame -L <line>,<line>` locally; `gh api repos/<owner>/<repo>/commits?path=<path>`
   in cross-repo mode). Set `caused_by: <prior finding id>` ONLY when blame lands on a
   commit recorded as some prior finding's `commit_sha_resolved`. Otherwise
   `caused_by: null`. Stop there rather than walking back through parent commits.
   This covers the findings this step REOPENS. The findings this round raised fresh get
   the same treatment at step 4.96; both feed the count at step 7.5.

Done when every `PRIOR_STATE` entry with `status in {resolved, dismissed, wontfix}` has a
recorded V2 verdict, and the verdict count equals the dispatched count. A missing verdict
means V2 dropped that entry. Re-check it inline rather than reading silence as still-closed.

### 4.95. Apply prior-state suppression (multi-round dedup)

For each remaining finding:

1. Compute `id = sha1(<file>::<enclosing_symbol>::<rule_class>).hexdigest()[:10]`.
   - If subagent failed to emit `Rule-class:` or `Enclosing-symbol:`, synthesize: `enclosing_symbol = "<module>"`, `rule_class = first 3 words of Issue (lowercased, space-joined, stop-words filtered)`. Log a warning so the prompt can be tuned.

2. Look up `id` in `PRIOR_STATE.findings`. If a match exists with `status in {resolved, dismissed, wontfix}`:

   - **`status == resolved`**: verify the diff between `commit_sha_resolved..HEAD` doesn't reintroduce the issue.
     - Re-introduced (resolving change reverted) → set this finding's status to `regression`, keep it (will be flagged as a fresh active finding with regression history in Phase 4).
     - Not re-introduced → DROP, log `prior-state suppression, resolved in round <round_resolved> by commit <commit_sha_resolved>`.

   - **`status in {dismissed, wontfix}`** → DROP, log `prior-state suppression, <status> in round <round_resolved>: "<dismissal_reason>"`.

3. Report every finding's state as exactly one of: `active`, `resolved` (with commit), `dismissed` (with reason), `wontfix` (with reason), `regression`. The enum is closed, and it is the only status vocabulary that appears in output, logs, or comments.

### 4.96. Attribute lineage on this round's findings

Skip entirely when `CURRENT_ROUND == 1`. There is no earlier fix to attribute to, and
every finding gets `caused_by: null`.

Step 4.9 attributes lineage on findings it REOPENS from prior state. This step does it for
the findings this round raised fresh, which is the case the cascade check exists to
catch: a new finding sitting on a line the previous round's fix wrote. Skip this and
`cascade_share` is 0 by construction and the trend line always reads "Converging".

Run it over the findings that SURVIVED step 4.95, one hop, same bound as step 4.9:

1. Blame the finding's cited line: `git blame -L <line>,<line>` locally,
   `gh api repos/<owner>/<repo>/commits?path=<path>&sha=<head_sha>` in cross-repo mode.

2. Set the field:

   ```
   caused_by: <id of the prior finding whose commit_sha_resolved is that blame commit, or null>
   ```

   Set an id ONLY when the blame commit is recorded as some `PRIOR_STATE` finding's
   `commit_sha_resolved`. Otherwise `null`. Do not walk back through parent commits, and
   do not guess from proximity or topic.

3. A finding with no cited line (module-scope) gets `caused_by: null`; there is no line to
   blame. Same for a finding whose blame commit predates round 1.

4. When several prior findings share the blame commit, take the single nearest cause. The
   cardinality rule in `references/finding-state-schema.md` decides which.

Done when every surviving finding carries a `caused_by` value, `null` included. Step 7.5
counts the non-null ones; Phase 4 write-back persists them.
