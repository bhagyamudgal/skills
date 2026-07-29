# Finding-state schema for multi-round dedup

This document defines the per-PR state file `.claude/review-state/<pr-number>.yml` and the stable finding-ID strategy that survives rewordings + line shifts across review rounds.

**Why this exists**: in real production usage, `/review-pr` ran 6 rounds on PR #4785; round 5 resolved finding M3, but round 6 still listed M3 as "deferred" — confusing the user about whether they'd shipped the fix. Root cause: dedup keyed on `(file, line, symbol)` breaks when lines shift, and there was no persistent `resolved` marker. This schema fixes both problems.

---

## File location

```
<repo-root>/.claude/review-state/<pr-number>.yml
```

One file per PR, scoped to the repo's working tree. The file is local-only: Phase 1 seeds `review-state/.gitignore` with `*` when it creates the directory, so the whole dir self-ignores. Don't assume `.claude/` is already ignored — many repos commit it for settings and skills, and unignored state files show up as untracked noise in `git status`.

In **cross-repo mode** (running `/review-pr` from a directory that's not the PR's repo), state lives at `~/.claude/review-state/<owner>__<repo>__<pr-number>.yml` (double underscore separator to avoid path collisions).

---

## Schema

```yaml
pr: 4785
repo: fileseye-org/fileseye
created_at: 2026-04-12T13:29:50Z
updated_at: 2026-05-08T19:11:42Z
last_round: 6

findings:
  - id: 9c4f2a8b1e            # sha1(file::enclosing_symbol::rule_class), first 10 hex chars
    file: src/services/upsert-bundle.helper.ts
    enclosing_symbol: upsertBundle
    rule_class: error-code-wrong-branch
    severity: Moderate
    label_history: [M3, M3, M3]    # what label each round assigned (round_first_seen → last_round)
    status: resolved                # active | resolved | dismissed | wontfix | regression
    round_first_seen: 1
    round_resolved: 5
    commit_sha_resolved: ced1f1930
    dismissal_reason: null
    last_message: "INSERT_RETURNED_NO_ROW error code/message wrong for UPDATE branch"
    github_thread_id: PRRT_kwDO123abc      # for resolveReviewThread on rolling re-review
    github_comment_id: 2145678901          # for follow-up comments

    # --- convergence fields (see SKILL.md steps 4.55, 4.56, 4.9) ---
    inverse_risk: "returning early leaves the bundle row uncommitted"
    caused_by: null                 # id of the finding whose FIX created this one
    depends_on: null                # for dismissed/wontfix: the code condition the rationale rests on
    class_sites:                    # every site of this rule_class, not just the cited one
      - { site: "upsert-bundle.helper.ts:118", handled: true }
      - { site: "upsert-item.helper.ts:64",   handled: true }

  - id: 7e2b1c9f4a
    file: src/handlers/import-pdf.ts
    enclosing_symbol: importPdfBatch
    rule_class: silent-failure
    severity: Serious
    label_history: [S2, S2]
    status: active
    round_first_seen: 5
    round_resolved: null
    commit_sha_resolved: null
    dismissal_reason: null
    last_message: "Promise.allSettled errors swallowed — failed names never logged"
    github_thread_id: PRRT_kwDO456def
    github_comment_id: 2145678902
```

### Field reference

| Field | Type | Required | Notes |
|---|---|---|---|
| `pr` | int | yes | PR number |
| `repo` | string | yes | `<owner>/<name>` form |
| `created_at` | ISO 8601 UTC | yes | When the state file was first written |
| `updated_at` | ISO 8601 UTC | yes | Last write timestamp |
| `last_round` | int | yes | Highest round number observed (1-indexed) |
| `findings[].id` | string | yes | First 10 hex chars of `sha1(...)` — see ID strategy below |
| `findings[].file` | string | yes | Repo-relative path |
| `findings[].enclosing_symbol` | string | yes | Function/class/component containing the finding |
| `findings[].rule_class` | string | yes | 2–3-word slug categorizing the issue (see vocabulary below) |
| `findings[].severity` | enum | yes | `Critical \| Serious \| Moderate \| Minor` |
| `findings[].label_history` | string[] | yes | Per-round label (e.g., `M3`) — useful for debugging label drift |
| `findings[].status` | enum | yes | `active \| resolved \| dismissed \| wontfix \| regression` |
| `findings[].round_first_seen` | int | yes | Round number when the finding was first emitted |
| `findings[].round_resolved` | int | nullable | Round when status flipped to `resolved` |
| `findings[].commit_sha_resolved` | string | nullable | Head commit SHA when the resolving change landed |
| `findings[].inverse_risk` | string | nullable | Failure mode the suggested fix trades into. Round N+1 checks this FIRST — it is the highest-yield regression predictor in the file. `"none — pure addition"` when the fix trades nothing away |
| `findings[].caused_by` | string | nullable | ID of the finding whose *fix* created this one. Drives the convergence trend line and the regression-dominance signal |
| `findings[].depends_on` | string | nullable | For `dismissed`/`wontfix` only: the code condition the rationale rests on (e.g. `"the early-break at search.ts:88 keeps serial decrypt cheap"`). When a later commit voids it, the dismissal is void |
| `findings[].class_sites` | list | nullable | Every site of this `rule_class` with a `handled` flag. Resolution is gated on ALL sites handled — not just the cited one. This is what prevents a 3-of-4-sites fix from being marked resolved |
| `findings[].dismissal_reason` | string | nullable | Free-form note when status = `dismissed` or `wontfix` |
| `findings[].last_message` | string | yes | Most-recent `Issue:` text — used in audit logs / human-readable diffs |
| `findings[].github_thread_id` | string | nullable | `PRRT_...` GraphQL node ID, for resolveReviewThread / re-comments |
| `findings[].github_comment_id` | int | nullable | REST databaseId, for cache-key parity with the existing `posted_comments` array |

### Status state machine

```
                          (subagent emits a new finding with this id)
                           │
         ┌─────────────────▼─────────────────┐
         │             active                │
         └────┬─────────┬──────────────┬─────┘
              │         │              │
              │         │              │
   (fix landed,         │      (user dismisses     (subagent emits SAME id
    confirmed in        │       in post-review     after status was resolved
    diff)               │       prompt)            — code regressed)
              ▼         ▼              ▼
       ┌──────────┐ ┌──────────┐  ┌──────────┐
       │ resolved │ │ dismissed│  │regression│
       └──────────┘ │ wontfix  │  └────┬─────┘
                    └──────────┘       │
                                       │  (user re-flags the regression
                                       │   as resolved or dismissed)
                                       ▼
                                  back to resolved/dismissed
```

- **`resolved`**: subagent saw the fix in the diff between `commit_sha_resolved` and the prior round's HEAD. `/fix-pr-review` writes this when it ships a fix.
- **`dismissed`**: user explicitly dropped the finding via the post-review AskUserQuestion. `dismissal_reason` is required.
- **`wontfix`**: user rejected the finding as wrong / out-of-scope. `dismissal_reason` is required (e.g., "intentional design — see issue #4001").
- **`regression`**: subagent emits a finding whose `id` matches an existing `resolved` entry, AND the diff shows the resolving code was reverted/edited. Treat as a fresh active finding but keep the history.

---

## Finding-ID strategy

```python
id = sha1(f"{file}::{enclosing_symbol}::{rule_class}").hexdigest()[:10]
```

### Why this combination

- **`file`**: stable across line shifts, breaks only on file rename (acceptable — rename = legit new finding scope).
- **`enclosing_symbol`**: function/class/component containing the cited line. Subagent extracts via tree-sitter / regex match for `function|class|const|export default function|const X = (` upward from the cited line. Stable across line shifts within the same function.
- **`rule_class`**: a 2-3 word slug emitted by the subagent describing the *kind* of issue, independent of wording. This is the key insight: the subagent rephrases the issue text every round (`"wrong error code"` → `"incorrect error message"`), but the rule class stays the same.

### Required `rule_class` vocabulary

The subagent prompt MUST emit `rule_class` for every finding. Use a slug from this controlled list whenever possible — extending the list is allowed, but consistency across rounds matters.

| Category | Slugs |
|---|---|
| Errors / failures | `silent-failure`, `swallowed-exception`, `error-code-wrong-branch`, `unhandled-rejection`, `missing-error-wrap`, `untyped-error` |
| Performance | `n+1-query`, `sequential-await`, `unbounded-loop`, `missing-index`, `oversized-payload` |
| Security | `injection-risk`, `auth-bypass`, `unvalidated-input`, `secret-in-code`, `cross-tenant-leak`, `type-coercion-write` |
| Reusability | `reimplements-existing` |
| Schema / data | `schema-overlap`, `table-consolidation-candidate`, `cross-table-fk-mismatch` |
| Intent | `feature-flagged-as-bug`, `out-of-scope`, `unmet-goal` |
| Quality | `magic-number`, `dead-code`, `unused-import`, `dead-import`, `obsolete-comment` |
| Architecture | `wrong-layer`, `breaking-api-change` |
| Prior-finding | `unresolved-prior-finding`, `regressed-prior-finding` |

### Edge cases

- **Cited line is a top-level statement** (no enclosing function): use `enclosing_symbol = "<module>"`.
- **Subagent fails to emit `rule_class`**: critic-pass synthesizes one from the `Issue:` first 3 keywords (lowercased, space-joined, stripped of stopwords). Log a warning so the prompt can be tuned.
- **Same logical issue in two different functions**: distinct IDs (different `enclosing_symbol`), correctly treated as separate findings. This is the desired behavior — fixing one doesn't auto-resolve the other.

---

## Integration points

### Phase 1 — load

After PR-metadata fetch and before subagent dispatch:

```bash
STATE_FILE=".claude/review-state/<pr-number>.yml"   # or cross-repo path
if [ -f "$STATE_FILE" ]; then
  PRIOR_STATE=$(cat "$STATE_FILE")
else
  PRIOR_STATE='{ pr: <number>, repo: "<owner>/<repo>", findings: [], last_round: 0 }'
fi
```

Pass `PRIOR_STATE.findings` (filtered to status in `{resolved, dismissed, wontfix}`) into Subagent 1's prompt as:

> The following findings were resolved or dismissed in earlier rounds. Do NOT re-report them unless the diff shows the fix was reverted or the underlying code regressed:
> ```
> - id: <id>, file: <file>, enclosing_symbol: <sym>, rule_class: <class>, status: <status>, last_round: <n>
> ...
> ```

### Phase 3 — filter

After existing critic-pass steps 1–4 + 4.5 + unified rules table (4.6), add:

**Step 4.95 — Apply prior-state suppression**

For each remaining finding:
1. Compute its `id` from the subagent-emitted `(file, enclosing_symbol, rule_class)`.
2. Look up `id` in `PRIOR_STATE.findings`.
3. If a match exists with `status in {resolved, dismissed, wontfix}`:
   - If `status == resolved`: verify the diff doesn't reintroduce the issue at `commit_sha_resolved..HEAD`. If reintroduced → mark as `regression`, keep the finding. Otherwise drop with reason: `prior-state suppression — resolved in round <round_resolved> (commit <commit_sha_resolved>)`.
   - If `status in {dismissed, wontfix}`: drop with reason: `prior-state suppression — <status> in round <round_resolved>: "<dismissal_reason>"`.

### Phase 4 — write back

After successful posting (or after "Keep local"):

1. For each finding currently posted/active in this round:
   - If `id` not in `PRIOR_STATE.findings`: append new entry with `status: active`, `round_first_seen: <current_round>`.
   - If `id` already exists with `status: active`: append `<this-round-label>` to `label_history`, update `last_message`. Status stays `active`.
   - If `id` already exists with `status: regression` (entered via Phase 3 step 4.95 because the resolving code was reverted): treat exactly like `active` — append to `label_history`, update `last_message`. The finding stays in `regression` until the user resolves OR dismisses it (rules below). The history of `round_resolved` + `commit_sha_resolved` is **preserved** (do NOT clear them — they document the prior resolve that got reverted).
2. For each finding the user explicitly dismissed via the post-review AskUserQuestion: write `status: dismissed` + `dismissal_reason: <user reason>` regardless of prior status (including `regression`). A regression that the user dismisses goes to `dismissed` (the prior `round_resolved` + `commit_sha_resolved` from before the regression are kept in the entry as historical context).
3. For each finding that `/fix-pr-review` ships a fix for: it writes `status: resolved` + `commit_sha_resolved: <new HEAD sha>` regardless of prior status. A regression that gets re-fixed goes back to `resolved` with the *new* commit SHA; the prior `commit_sha_resolved` is overwritten (only the latest resolving commit is kept — `label_history` retains the full timeline).
4. Increment `last_round`. Update `updated_at`.
5. Write the file atomically (temp + rename).

State transitions in Phase 4:

| Prior status     | Subagent emits finding? | User dismisses? | `/fix-pr-review` ships fix? | New status           |
|------------------|-------------------------|-----------------|------------------------------|----------------------|
| (no entry)       | yes                     | no              | no                           | `active` (new entry) |
| `active`         | yes                     | no              | no                           | `active`             |
| `active`         | yes                     | yes             | no                           | `dismissed`          |
| `active`         | (n/a)                   | no              | yes                          | `resolved`           |
| `resolved`       | yes (regression)        | no              | no                           | `regression`         |
| `regression`     | yes                     | no              | no                           | `regression`         |
| `regression`     | yes                     | yes             | no                           | `dismissed`          |
| `regression`     | (n/a)                   | no              | yes                          | `resolved` (new SHA) |
| `dismissed`/`wontfix` | yes (suppressed)   | (n/a)           | (n/a)                        | unchanged (suppressed in Phase 3 step 4.95) |

`/fix-pr-review` is responsible for setting `status: resolved` + `commit_sha_resolved` when it ships a fix. (Implementation note for follow-up — out of scope for the initial change. Until that lands, `status: resolved` transitions can be set manually by editing the YAML file.)

---

## Garbage collection

On Phase 1 startup, scan `.claude/review-state/*.yml`:

```bash
for f in .claude/review-state/*.yml; do
  pr_num=$(yq '.pr' "$f")
  repo=$(yq '.repo' "$f")
  state=$(gh pr view "$pr_num" --repo "$repo" --json state,closedAt -q '.')
  if [[ "$(jq -r .state <<<"$state")" =~ ^(CLOSED|MERGED)$ ]]; then
    closed_at=$(jq -r .closedAt <<<"$state")
    if older-than-30-days "$closed_at"; then
      rm "$f"
    fi
  fi
done
```

Cap at 50 files; oldest deleted first. Run lazily (skip if it would add > 1s to Phase 1).
