# Finding-state schema for multi-round dedup

This document defines both of `/review-pr`'s per-PR persistence files — the state file `.claude/review-state/<pr-number>.yml` and the run-over-run cache — plus the stable finding-ID strategy that survives rewordings + line shifts across review rounds.

**Why this exists**: in real production usage, `/review-pr` ran 6 rounds on a production PR; round 5 resolved finding M3, but round 6 still listed M3 as "deferred" — confusing the user about whether they'd shipped the fix. Root cause: dedup keyed on `(file, line, symbol)` breaks when lines shift, and there was no persistent `resolved` marker. This schema fixes both problems.

`converge-reviews` may add one top-level `convergence` block to this state file after Phase 4. Preserve that block during finding-state write-back. It references finding IDs from this schema; it does not copy or replace their authoritative bodies or statuses.

---

## The two persistence files

| File | Holds | Written by |
|---|---|---|
| `.claude/review-state/<pr-number>.yml` | Per-finding lifecycle — `active` / `resolved` / `dismissed` / `wontfix` / `regression`, plus the cascade fields | Phase 4 write-back — the only automated writer (see the writer caveat at the end of "Phase 4 — write back") |
| `$HOME/.claude/skills/review-pr/cache/<owner>_<repo>_<pr-number>.json` | Per-run and per-comment GitHub facts — last reviewed SHA, last posted review IDs, and `posted_comments` (for `resolveReviewThread` + dedup against re-posting) | End of Phase 4, independent of GitHub state |

`posted_comments` works alongside the state file: the cache holds per-comment GitHub IDs, the state file holds per-finding lifecycle. Both are necessary; neither is sufficient alone. The state file is the schema described first below; the cache follows under "Run-over-run cache".

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

    # --- cascade fields (see SKILL.md: "Class-completeness verification",
    #     "Inverse-risk verification", "Proactive regression sweep") ---
    inverse_risk: "returning early leaves the bundle row uncommitted"
    caused_by: null                 # id of the finding whose FIX created this one
    depends_on: null                # for dismissed/wontfix: the code condition the rationale rests on
    class_sites:                    # every site of this rule_class, not just the cited one
      - { site: "src/services/upsert-bundle.helper.ts::upsertBundle", handled: true }
      - { site: "src/services/upsert-item.helper.ts::upsertItem",     handled: true }

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

    # --- cascade fields — required here too: this finding proposes a fix ---
    inverse_risk: "logging every rejected settlement floods the batch log when a whole batch fails"
    caused_by: null
    depends_on: null
    class_sites:
      - { site: "src/handlers/import-pdf.ts::importPdfBatch",     handled: false }
      - { site: "src/handlers/import-image.ts::importImageBatch", handled: false }
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
| `findings[].inverse_risk` | string | conditional | Failure mode the suggested fix trades into. Round N+1 checks this first — a fix landing on its own inverse is one of the two cascade feeders. **Required whenever the finding carries a `Suggested fix:`**; `"none — pure addition"` when the fix trades nothing away; null ONLY when the finding proposes no code change |
| `findings[].caused_by` | string | nullable | ID of the finding whose *fix* created this one. This is what lets a later round see that a "new" finding is the previous round's remedy landing badly, instead of counting it as unrelated fresh work |
| `findings[].depends_on` | string | nullable | For `dismissed`/`wontfix` only: the code condition the rationale rests on (e.g. `"the early-break at search.ts:88 keeps serial decrypt cheap"`). When a later commit voids it, the dismissal is void and the finding reopens as `active` |
| `findings[].class_sites` | list | conditional | Every site of this `rule_class` with a `handled` flag — item schema below. Resolution is gated on ALL sites handled, not just the cited one; this is what prevents a 3-of-4-sites fix from being marked resolved. **Required whenever the finding carries a `Suggested fix:`**; null ONLY when the finding proposes no code change |
| `findings[].dismissal_reason` | string | nullable | Free-form note when status = `dismissed` or `wontfix` |
| `findings[].last_message` | string | yes | Most-recent `Issue:` text — used in audit logs / human-readable diffs |
| `findings[].github_thread_id` | string | nullable | `PRRT_...` GraphQL node ID, for resolveReviewThread / re-comments |
| `findings[].github_comment_id` | int | nullable | REST databaseId, for cache-key parity with the existing `posted_comments` array |

### Cascade fields

**`class_sites` item schema**

```yaml
- { site: "<repo-relative-file>::<enclosing_symbol>", handled: <bool> }
```

`site` anchors on `<file>::<symbol>`, never on a line number — a stored site list is re-checked one or more rounds later, by which time every line number in it is stale. Same anchoring rule as the finding ID, for the same reason.

`handled: true` means **this PR's changes cover that site** — the defect of this `rule_class` is not present there at the current head. It is not "someone looked at it" and not "it's fixed on main".

Phase 4 write-back is the only writer. It records the list when the finding is first appended (every affected site in the finding's `class_completeness:` audit, `handled: false` unless the diff already covers it) and rewrites the flags on every later round from the Phase 3 sweep verdicts. Flags move in both directions: a site handled in round 3 goes back to `handled: false` in round 4 if a commit reverted it.

**`caused_by` cardinality**

One id, not a list — the single *nearest* cause. When several closed findings could plausibly have spawned this one, pick the one whose `commit_sha_resolved` introduced the cited lines; if that is still ambiguous, pick the most recent and leave the rest out. A chain is represented by following `caused_by` from entry to entry, never by widening the field.

`caused_by` records history, not a live pointer. If the referenced finding is later dismissed, or its entry is dropped by garbage collection, leave the id in place — a dangling `caused_by` is not an error, and the cascade check simply skips links it cannot resolve.

### Status state machine

```
                          (subagent emits a new finding with this id)
                           │
         ┌─────────────────▼─────────────────┐
┌───────►│             active                │
│        └────┬─────────┬──────────────┬─────┘
│             │         │              │
│             │         │              │
│  (fix landed,         │      (explicit external  (subagent emits SAME id
│   confirmed in        │       disposition)       after status was resolved
│   diff, AND every     │                          — code regressed)
│   class_sites entry   │
│   handled)            │
│             ▼         ▼              ▼
│      ┌──────────┐ ┌──────────┐  ┌──────────┐
│      │ resolved │ │ dismissed│  │regression│
│      └──────────┘ │ wontfix  │  └────┬─────┘
│                   └────┬─────┘       │
│                        │             │  (external triage marks the regression
│                        │             │   resolved or dismissed)
│                        │             ▼
│                        │        back to resolved/dismissed
│                        │
└────────────────────────┘
  (the depends_on condition is voided by a later commit —
   the dismissal is void, the finding reopens as active)
```

- **`resolved`**: subagent saw the fix in the diff between `commit_sha_resolved` and the prior round's HEAD, **and** every `class_sites` entry is `handled: true`. A fix that lands on the cited site while a sibling site stays unhandled leaves the finding `active`. No automated writer sets this today — see the writer caveat at the end of "Phase 4 — write back".
- **`dismissed`**: an explicit disposition imported from prior state or a downstream triage workflow. `dismissal_reason` is required. `/review-pr` never creates this status by deselecting a finding.
- **`wontfix`**: user rejected the finding as wrong / out-of-scope. `dismissal_reason` is required (e.g., "intentional design — see the linked design issue").
- **`regression`**: subagent emits a finding whose `id` matches an existing `resolved` entry, AND the diff shows the resolving code was reverted/edited. Treat as a fresh active finding but keep the history.
- **`dismissed`/`wontfix` → `active`**: the code condition recorded in `depends_on` no longer holds at the current head, so the rationale that closed the finding no longer applies. Reopen as `active`; keep `dismissal_reason` and the original `round_resolved` as history, and note which commit voided the condition. There is no separate "voided" status — a void dismissal is just an open finding again.

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
- **Same logical issue in two different functions**: distinct IDs (different `enclosing_symbol`), correctly treated as separate findings for reporting and suppression — fixing one doesn't auto-resolve the other. They are not fully independent, though: the class sweep puts both sites in the `class_sites` list of whichever finding cited the class first, so that finding cannot reach `resolved` until the sibling site is handled too. Distinct IDs, shared resolution gate.

---

## Run-over-run cache

Phase 1 computes `$CACHE_FILE` and `CURRENT_HEAD`; everything below describes what that file contains and which of three replay branches the comparison selects.

```bash
REVIEW_CACHE_CONTRACT_VERSION=2
```

```json
{
  "contract_version": 2,
  "last_run_sha": "abc123...",
  "last_run_timestamp": "2026-04-11T13:29:50Z",
  "last_run_verdict": "request-changes",
  "findings": [...],
  "filtered_out": [...],
  "last_posted_review_id": 12345678,
  "last_posted_review_node_id": "PRR_kwDO...",
  "last_posted_verdict": "request-changes",
  "last_posted_at": "2026-04-11T13:30:15Z",
  "publication_evidence": {
    "publication_mode": "threaded",
    "review_node_id": "PRR_kwDO...",
    "review_database_id": 12345678
  },
  "posted_comments": [
    { "finding_key": "(file.ts, 47, processrequest)", "finding_id": "<id-hash>",
      "github_comment_id": 12345, "github_thread_id": "PRRT_abc123",
      "review_database_id": 12345678, "review_node_id": "PRR_kwDO...",
      "finding_severity": "Serious" }
  ]
}
```

`REVIEW_CACHE_CONTRACT_VERSION` is the automatic-posting contract. Before reading any replay or `posted_comments` data, require `.contract_version == REVIEW_CACHE_CONTRACT_VERSION`. A missing or mismatched value marks the cache as legacy: ignore all of its contents, run a full fresh review, and replace it atomically only after the fresh run succeeds. Do not migrate `filtered_out` or thread ownership from a legacy cache.

### Three replay branches

These branches apply only after the contract-version check succeeds.

1. **`last_run_sha == CURRENT_HEAD`** — no new commits. Reuse the cached review result. If authoritative cache evidence confirms the same review body, head SHA, required GitHub state, and threaded publication ownership are already posted, print the cached result and exit. Otherwise continue directly to Phase 4 and post the cached complete finding set; do not ask whether to replay or post.

2. **New commits since last run** (cached SHA is an ancestor of HEAD) — PARTIAL re-review:
   - `git diff <last_run_sha>..<CURRENT_HEAD>` (or `gh api compare` cross-repo) for new-commits diff.
   - Dispatch Phase 2 with NEW diff + FULL file context, prompted to ONLY report findings on new commits.
   - Phase 3 merges new findings with cached findings still applicable (re-verify each cached finding against current HEAD; drop with `stale after new commits` if changed).
   - Phase 4 header: `Mode: partial re-review (N new commits since cached run at <sha>)`.

3. **Cache exists but `last_run_sha` is NOT an ancestor** (force-push, branch reset): invalidate cache, full fresh run.

---

## Integration points

### Phase 1 — load

Both files load in Phase 1: the cache check above (compare `last_run_sha` to `CURRENT_HEAD`, pick a branch) and the state-file read below.

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

The same filtered set — plus each entry's `class_sites`, `inverse_risk`, `depends_on`, and `commit_sha_resolved` — goes to the regression-sweep verifier in Phase 3, which re-checks every closed finding at the current head. Those four fields are the entire reason the state file persists them. A round that loads the state file but drops them degrades the sweep to an ID-hash match, which is exactly what the sweep exists to replace.

### Phase 3 — filter

After existing critic-pass steps 1–4 + 4.5 + unified rules table (4.6), add:

Ahead of suppression, the regression sweep re-checks every entry with `status in {resolved, dismissed, wontfix}` against the current head, using the fields loaded in Phase 1: is every `class_sites` entry still handled, has the recorded `inverse_risk` failure mode appeared, does the `depends_on` condition still hold? Its per-entry verdicts are what Phase 4 (step 4 below) writes back.

**Step 4.95 — Apply prior-state suppression**

For each remaining finding:
1. Compute its `id` from the subagent-emitted `(file, enclosing_symbol, rule_class)`.
2. Look up `id` in `PRIOR_STATE.findings`.
3. If a match exists with `status in {resolved, dismissed, wontfix}`:
   - If `status == resolved`: verify the diff doesn't reintroduce the issue at `commit_sha_resolved..HEAD`. If reintroduced → mark as `regression`, keep the finding. Otherwise drop with reason: `prior-state suppression — resolved in round <round_resolved> (commit <commit_sha_resolved>)`.
   - If `status in {dismissed, wontfix}`: drop with reason: `prior-state suppression — <status> in round <round_resolved>: "<dismissal_reason>"`.

### Phase 4 — write back

After successful posting:

1. For each finding currently posted/active in this round:
   - If `id` not in `PRIOR_STATE.findings`: append new entry with `status: active`, `round_first_seen: <current_round>`, and the cascade fields taken straight off the printed finding: `inverse_risk` from its `Inverse risk:` line, `class_sites` from the site list in its `class_completeness:` audit as verified in Phase 3 (each site `handled: false` unless this PR's diff already covers it), `caused_by` from the regression sweep's lineage attribution (null when it attributed none), `depends_on: null`.
   - If `id` already exists with `status: active`: append `<this-round-label>` to `label_history`, update `last_message`. Status stays `active`. Also refresh `inverse_risk` when the suggested fix changed this round, and rewrite `class_sites` with this round's `handled` flags — including sites the current diff newly introduced.
   - If `id` already exists with `status: regression` (entered via Phase 3 step 4.95 because the resolving code was reverted): treat exactly like `active` — append to `label_history`, update `last_message`, refresh `class_sites`. Set `caused_by` when the sweep traced the reopen to another finding's fix. The finding stays in `regression` until the user resolves OR dismisses it (rules below). The history of `round_resolved` + `commit_sha_resolved` is **preserved** (do NOT clear them — they document the prior resolve that got reverted).
2. Preserve existing `dismissed` and `wontfix` entries unless the regression sweep reopens them. Automatic posting never converts a surviving finding to either status; every surviving finding remains `active` or `regression` and is posted.
3. For each finding whose fix has shipped (writer caveat below — this transition is currently made by hand): `status: resolved` + `commit_sha_resolved: <sha of the resolving commit>` regardless of prior status — but **only when every `class_sites` entry is `handled: true`**. If any site is still unhandled, keep the prior status (`active` / `regression`), write the updated `handled` flags, and leave `commit_sha_resolved` untouched: a fix covering part of the class is not a resolution. A regression that gets fully re-fixed goes back to `resolved` with the *new* commit SHA; the prior `commit_sha_resolved` is overwritten (only the latest resolving commit is kept — `label_history` retains the full timeline).
4. For each closed finding the Phase 3 regression sweep reopened: an entry reopened because a `class_sites` site went unhandled or its `inverse_risk` failure mode materialized becomes `status: regression`; a `dismissed`/`wontfix` entry whose `depends_on` condition was voided becomes `status: active`, keeping `dismissal_reason` and `round_resolved` as history and naming the voiding commit in `last_message`.
5. Increment `last_round`. Update `updated_at`.
6. Write the file atomically (temp + rename).

State transitions written by Phase 4:

| Prior status     | Subagent emits finding? | Fix shipped? | New status           |
|------------------|-------------------------|--------------|----------------------|
| (no entry)       | yes                     | no           | `active` (new entry) |
| `active`         | yes                     | no           | `active`             |
| `active`         | (n/a)                   | yes — every `class_sites` entry `handled: true` | `resolved`  |
| `active`         | (n/a)                   | yes — some `class_sites` entry still unhandled  | `active` (partial fix is not a resolution; `handled` flags updated) |
| `resolved`       | yes (regression)        | no           | `regression`         |
| `regression`     | yes                     | no           | `regression`         |
| `regression`     | (n/a)                   | yes — every `class_sites` entry `handled: true` | `resolved` (new SHA) |
| `dismissed`/`wontfix` | yes (suppressed)   | (n/a)        | unchanged (suppressed in Phase 3 step 4.95) |
| `dismissed`/`wontfix`, `depends_on` condition voided at current head | (n/a) | (n/a) | `active` (reopened; `dismissal_reason` + `round_resolved` kept as history) |

An external triage workflow may import `dismissed` or `wontfix` before Phase 4 loads prior state. Phase 4 preserves those dispositions or reopens them when `depends_on` no longer holds; it never creates either disposition.

**Writer caveat — `resolved` has no automated writer yet.** Every other transition in the table above is written by Phase 4 write-back, which is also the only writer of `class_sites`. `resolved` is the exception: `/fix-pr-review` applies fixes and resolves the GitHub threads, but it never opens this file — it has no `review-state` code path at all. Wiring that write-back into `/fix-pr-review` (locate the state file, match its FIX items to entries, check the gate, write) is follow-up work, out of scope here.

Until it lands, set the transition by hand: edit the YAML, flip `status` to `resolved`, record the resolving commit SHA in `commit_sha_resolved`, and do it **only once every `class_sites` entry is `handled: true`** — a partial-class fix is not a resolution. Everything downstream reads only what is written here: round-over-round dedup (Phase 3 step 4.95), the regression sweep's `{resolved, dismissed, wontfix}` input set, and the thread resolution in `github-posting.md` step 8d. A state file where nothing is ever marked `resolved` degrades all three to user dismissals alone.

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
