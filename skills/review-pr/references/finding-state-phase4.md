
# Finding-state write-back and sweep (Phase 4)

Main loads this in Phase 4 after posting succeeds. The schema, ID strategy, cache, and read path stay in `${CLAUDE_SKILL_DIR}/references/finding-state-schema.md`, already loaded since Phase 1. The sweep below also runs on Phase 1 startup when the state directory is non-empty.

### Phase 4: write back

After posting succeeds:

1. For each finding currently posted/active in this round:
   - If `id` not in `PRIOR_STATE.findings`: append new entry with `status: active`, `round_first_seen: <current_round>`, and the cascade fields taken straight off the printed finding: `inverse_risk` from its `Inverse risk:` line, `class_sites` from the site list in its `class_completeness:` audit as verified in Phase 3 (each site `handled: false` unless this PR's diff already covers it), `caused_by` from the regression sweep's lineage attribution (null when it attributed none), `depends_on: null`.
   - If `id` already exists with `status: active`: append `<this-round-label>` to `label_history`, update `last_message`. Status stays `active`. Also refresh `inverse_risk` when the suggested fix changed this round, and rewrite `class_sites` with this round's `handled` flags, including sites the current diff newly introduced.
   - If `id` already exists with `status: regression` (entered via Phase 3 step 4.95 because the resolving code was reverted): treat exactly like `active`, append to `label_history`, update `last_message`, refresh `class_sites`. Set `caused_by` when the sweep traced the reopen to another finding's fix. The finding stays in `regression` until the user resolves OR dismisses it (rules below). The history of `round_resolved` + `commit_sha_resolved` is **preserved** (do NOT clear them; they document the prior resolve that got reverted).
2. Preserve existing `dismissed` and `wontfix` entries unless the regression sweep reopens them. Automatic posting never converts a surviving finding to either status; every surviving finding remains `active` or `regression` and is posted.
3. For each finding whose fix has shipped (writer caveat below; this transition is currently made by hand): `status: resolved` + `commit_sha_resolved: <sha of the resolving commit>` regardless of prior status, but **only when every `class_sites` entry is `handled: true`**. If any site is still unhandled, keep the prior status (`active` / `regression`), write the updated `handled` flags, and leave `commit_sha_resolved` untouched: a fix covering part of the class is not a resolution. A regression that gets fully re-fixed goes back to `resolved` with the *new* commit SHA; the prior `commit_sha_resolved` is overwritten (only the latest resolving commit is kept; `label_history` retains the full timeline).
4. For each closed finding the Phase 3 regression sweep reopened: an entry reopened because a `class_sites` site went unhandled or its `inverse_risk` failure mode materialized becomes `status: regression`; a `dismissed`/`wontfix` entry whose `depends_on` condition was voided becomes `status: active`, keeping `dismissal_reason` and `round_resolved` as history and naming the voiding commit in `last_message`.
5. Increment `last_round`. Update `updated_at`.
6. Write the file atomically with temp and rename.

Phase 4 writes these state transitions:

| Prior status     | Subagent emits finding? | Fix shipped? | New status           |
|------------------|-------------------------|--------------|----------------------|
| (no entry)       | yes                     | no           | `active` (new entry) |
| `active`         | yes                     | no           | `active`             |
| `active`         | (n/a)                   | yes: every `class_sites` entry `handled: true` | `resolved`  |
| `active`         | (n/a)                   | yes: some `class_sites` entry still unhandled  | `active` (partial fix is not a resolution; `handled` flags updated) |
| `resolved`       | yes (regression)        | no           | `regression`         |
| `regression`     | yes                     | no           | `regression`         |
| `regression`     | (n/a)                   | yes: every `class_sites` entry `handled: true` | `resolved` (new SHA) |
| `dismissed`/`wontfix` | yes (suppressed)   | (n/a)        | unchanged (suppressed in Phase 3 step 4.95) |
| `dismissed`/`wontfix`, `depends_on` condition voided at current head | (n/a) | (n/a) | `active` (reopened; `dismissal_reason` + `round_resolved` kept as history) |

An external triage workflow may import `dismissed` or `wontfix` before Phase 4 loads prior state. Phase 4 preserves those dispositions or reopens them when `depends_on` no longer holds; it never creates either disposition.

**Writer caveat: `resolved` has no automated writer yet.** Every other transition in the table above is written by Phase 4 write-back, which is also the only writer of `class_sites`. `resolved` is the exception: `/fix-pr-review` applies fixes and resolves the GitHub threads, but it never opens this file. It has no `review-state` code path at all. Wiring that write-back into `/fix-pr-review` (locate the state file, match its FIX items to entries, check the gate, write) is follow-up work, out of scope here.

Until it lands, set the transition by hand: edit the YAML, flip `status` to `resolved`, record the resolving commit SHA in `commit_sha_resolved`, and do it **only once every `class_sites` entry is `handled: true`**. A partial-class fix is not a resolution. Everything downstream reads only what is written here: round-over-round dedup (Phase 3 step 4.95), the regression sweep's `{resolved, dismissed, wontfix}` input set, and the thread resolution in `${CLAUDE_SKILL_DIR}/references/github-posting-rerun.md` step 8d. A state file where nothing is ever marked `resolved` degrades all three to user dismissals alone.

---

## Garbage collection

Once `$STATE_FILE` is defined, remove state files untouched for 30 days. Age on disk is the whole signal, so this makes no network calls: a PR untouched that long is merged, closed, or abandoned, and a fresh run rebuilds state from the cache and GitHub threads.

```bash
find "$STATE_DIR" -maxdepth 1 -name '*.yml' -mtime +30 2>/dev/null \
  | head -n 50 | while IFS= read -r stale; do rm -- "$stale"; done
```

Cap at 50 files per run. Skip the sweep when the directory holds no `.yml` files. Repeated runs converge: anything stale eventually ages out.

