# Finding-state schema for multi-round dedup

This document defines both of `/review-pr`'s per-PR persistence files — the state file `.claude/review-state/<pr-number>.yml` and the run-over-run cache — plus the stable finding-ID strategy that survives rewordings + line shifts across review rounds.

**Why this exists**: in real production usage, `/review-pr` ran 6 rounds on PR #4785; round 5 resolved finding M3, but round 6 still listed M3 as "deferred" — confusing the user about whether they'd shipped the fix. Root cause: dedup keyed on `(file, line, symbol)` breaks when lines shift, and there was no persistent `resolved` marker. This schema fixes both problems.

---

## The two persistence files

| File | Holds | Written by |
|---|---|---|
| `.claude/review-state/<pr-number>.yml` | Per-finding lifecycle — `active` / `resolved` / `dismissed` / `wontfix` / `regression`, plus the cascade fields — the round's coverage ledger, and the round-cap follow-up issue | Phase 4 write-back — the only automated writer (see the writer caveat at the end of "Phase 4 — write back"). The ledger it writes is **built in Phase 3**, not here: every consumer reads it before Phase 4 runs. `followup_issue` is likewise **decided in Phase 4's "File the follow-up issue" step**, before posting, and only persisted here |
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

followup_issue:                     # round-cap backlog; null until a round >= 3 ends with a finding still active
  status: filed                     # filed | incomplete | failed | declined
  number: 412
  url: https://github.com/fileseye-org/fileseye/issues/412
  round_filed: 3
  finding_ids: [9c4f2a8b1e]         # every finding active at the cap, filed or not
  missing_ids: []                   # status: incomplete only — ids the read-back could not find

findings:
  - id: 9c4f2a8b1e            # sha1(file::enclosing_symbol::rule_class), first 10 hex chars
    file: src/services/upsert-bundle.helper.ts
    enclosing_symbol: upsertBundle
    rule_class: error-code-wrong-branch
    lens_ids: [L4]                  # which ledger cells this finding answers; NOT in the id hash
    severity: Moderate
    label_history: [M3, M3, M3]    # what label each round assigned (round_first_seen → last_round)
    status: resolved                # active | resolved | dismissed | wontfix | regression
    round_first_seen: 1
    round_resolved: 5
    commit_sha_resolved: ced1f1930
    dismissal_reason: null
    last_message: "INSERT_RETURNED_NO_ROW error code/message wrong for UPDATE branch"
    github_thread_id: PRRT_kwDO123abc      # for resolveReviewThread on re-review
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
    lens_ids: [L1, L8]              # dedupe merged two lenses onto one finding; both cells read `finding`
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

ledger:
  round: 6
  head_sha: ced1f1930
  files_changed: 4                  # == len(rows), always
  cells_total: 7                    # == 5 examined + 1 cannot-assess + 1 not-examined
  cells_examined: 5                 # clean + finding + not-applicable
  cells_cannot_assess: 1
  cells_not_examined: 1
  rows:
    - file: src/services/upsert-bundle.helper.ts
      file_type: [service-or-domain-logic]
      lenses:
        - id: L4
          verdict: finding
          finding_id: 9c4f2a8b1e            # required when verdict == finding
        - id: L7
          verdict: clean
    - file: src/handlers/import-pdf.ts
      file_type: [service-or-domain-logic]
      lenses:
        - id: L1
          verdict: finding
          finding_id: 7e2b1c9f4a            # one finding, two cells — its lens_ids names both
        - id: L8
          verdict: finding
          finding_id: 7e2b1c9f4a
    - file: drizzle/0042_bundle_index.sql
      file_type: [migration, db-schema]     # a path may match several rows of the map; union, never first hit
      lenses:
        - id: L17
          verdict: not-applicable
          note: index-only DDL — no table gains a column needing a companion
        - id: L13
          verdict: cannot-assess
          note: needs a row-count and null-share query against the target table
        - id: L14
          verdict: not-examined
          note: chunk 3 reviewer returned before reaching this file
    - file: docs/architecture.png
      file_type: [binary-and-assets]
      skip_reason: binary asset — no lens applies
      lenses: []                            # a skipped file keeps its row and contributes no cells
```

### Field reference

| Field | Type | Required | Notes |
|---|---|---|---|
| `pr` | int | yes | PR number |
| `repo` | string | yes | `<owner>/<name>` form |
| `created_at` | ISO 8601 UTC | yes | When the state file was first written |
| `updated_at` | ISO 8601 UTC | yes | Last write timestamp |
| `last_round` | int | yes | Highest round number observed (1-indexed) |
| `followup_issue` | map | nullable | The one follow-up issue the round cap files for this PR, or the record of why there isn't one. `null` until a round `>= 3` ends with a finding still active. Written by Phase 4 write-back from the outcome `SKILL.md` Phase 4's "File the follow-up issue" step resolved — that step decides, write-back persists, and nothing else touches the key. A `filed` entry is never overwritten by a later round; `declined` / `failed` / `incomplete` may be replaced by a later round's `filed` |
| `followup_issue.status` | enum | yes | `filed` (created AND read back with every finding present) \| `incomplete` (created, read-back short — treated as NOT filed) \| `failed` (creation errored, nothing exists) \| `declined` (user chose not to file). The four are not interchangeable: `incomplete` and `failed` differ by whether there is a URL to clean up, and `declined` is a user decision a later round must not re-litigate |
| `followup_issue.number` | int | conditional | Issue number. Required for `filed` and `incomplete`; null for `failed` and `declined` |
| `followup_issue.url` | string | conditional | Issue URL, as `gh issue create` returned it. Same requirement as `number` |
| `followup_issue.round_filed` | int | conditional | Round that OPENED the issue. Required for `filed` and `incomplete`; a later round appending to the same issue does not reset it |
| `followup_issue.finding_ids` | string[] | yes | The `findings[].id` of every finding still active when the round cap fired, whatever the status. Accumulates across rounds — an appending round adds its ids rather than replacing the list, or the earlier rounds' findings read as never filed. On `declined` / `failed` this is the list of findings tracked nowhere, the record of what the cap released into nothing. The round `> 3` branch compares it against that round's active set to decide whether anything is still uncovered |
| `followup_issue.missing_ids` | string[] | conditional | `status: incomplete` only: ids the read-back could not find in the created issue. Forbidden on the other three |
| `findings[].id` | string | yes | First 10 hex chars of `sha1(...)` — see ID strategy below |
| `findings[].file` | string | yes | Repo-relative path |
| `findings[].enclosing_symbol` | string | yes | Function/class/component containing the finding |
| `findings[].rule_class` | string | yes | 2–3-word slug categorizing the issue (see vocabulary below) |
| `findings[].lens_ids` | string[] | yes | Lens ids from `lens-map.md`'s `lens_index` that produced this finding, off the finding's `Lens:` line. Each `(file, lens)` it names is the cell the write-back sets to `finding`. `[]` for a finding no lens raised — one off the Q axis, or a gap-check finding raised on the Q axis rather than the lens axis — which answers no cell and is not counted as coverage. **Never carried in `rule_class`**: `rule_class` is the third component of the id hash, so a lens id inside it changes every finding id and breaks cross-round matching |
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
| `ledger.round` | int | yes | Round this ledger describes — equals `last_round` after Phase 4 |
| `ledger.head_sha` | string | yes | Head commit the cells were examined against |
| `ledger.files_changed` | int | yes | Files in the PR diff at `head_sha`. Must equal `len(ledger.rows)` — a shortfall means files were dropped before they were ever assigned a lens. A file the map skips still gets a row (`lenses: []` + `skip_reason`), so the equality holds for every PR containing an image, a lockfile or a build artifact |
| `ledger.cells_total` | int | yes | Count of `(file, lens)` cells — the sum of `len(lenses)` over all rows |
| `ledger.cells_examined` | int | yes | Cells with verdict in `{clean, finding, not-applicable}` |
| `ledger.cells_cannot_assess` | int | yes | Cells with verdict `cannot-assess`. Printed alongside the others; does **not** forbid `approve` |
| `ledger.cells_not_examined` | int | yes | Cells with verdict `not-examined`. Non-zero forbids an `approve` verdict — see "Coverage ledger" below |
| `ledger.rows[].file` | string | yes | Repo-relative path. One row per changed file, including files no lens applies to |
| `ledger.rows[].file_type` | string[] | yes | The `file_types[].id` values from `lens-map.md` whose `detect` block matched this path, plus any `skip_paths[].id` that short-circuited it. A **list**, because the map takes the union of every matching row rather than the first hit. `[other]` when nothing matched — that file still gets the `always_on` and signal lenses. This file states no vocabulary of its own; `lens-map.md` is the operational one and the only place a type is added |
| `ledger.rows[].skip_reason` | string | conditional | **Required when `lenses` is empty because `lens-map.md` skipped the path**, forbidden otherwise. A skipped file recorded as skipped is auditable; one that vanishes from `rows` breaks the `files_changed` equality and reads as a lost file |
| `ledger.rows[].lenses[].id` | string | yes | Lens identifier from `references/lens-map.md`'s `lens_index` (`L4`); what each lens asks is in `references/lenses.md`. An id absent from `lens_index` is malformed — do not invent one |
| `ledger.rows[].lenses[].verdict` | enum | yes | `clean \| finding \| not-applicable \| cannot-assess \| not-examined` — a third verdict vocabulary, distinct from `status` and `handled`; see the disambiguation below |
| `ledger.rows[].lenses[].finding_id` | string | conditional | The `findings[].id` this cell produced. **Required when `verdict == finding`**; omitted otherwise. The reverse pointer is `findings[].lens_ids`, and the two must agree |
| `ledger.rows[].lenses[].note` | string | conditional | One line. **Required for `not-applicable`** (why the assigned lens found no trigger here), **for `cannot-assess`** (naming the artifact that would answer it) **and for `not-examined`** (why it did not run). A cell in any of those three states without a note is malformed |

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
│  (fix landed,         │      (user dismisses     (subagent emits SAME id
│   confirmed in        │       in post-review     after status was resolved
│   diff, AND every     │       prompt)            — code regressed)
│   class_sites entry   │
│   handled)            │
│             ▼         ▼              ▼
│      ┌──────────┐ ┌──────────┐  ┌──────────┐
│      │ resolved │ │ dismissed│  │regression│
│      └──────────┘ │ wontfix  │  └────┬─────┘
│                   └────┬─────┘       │
│                        │             │  (user re-flags the regression
│                        │             │   as resolved or dismissed)
│                        │             ▼
│                        │        back to resolved/dismissed
│                        │
└────────────────────────┘
  (the depends_on condition is voided by a later commit —
   the dismissal is void, the finding reopens as active)
```

- **`resolved`**: subagent saw the fix in the diff between `commit_sha_resolved` and the prior round's HEAD, **and** every `class_sites` entry is `handled: true`. A fix that lands on the cited site while a sibling site stays unhandled leaves the finding `active`. No automated writer sets this today — see the writer caveat at the end of "Phase 4 — write back".
- **`dismissed`**: user explicitly dropped the finding via the post-review AskUserQuestion. `dismissal_reason` is required.
- **`wontfix`**: user rejected the finding as wrong / out-of-scope. `dismissal_reason` is required (e.g., "intentional design — see issue #4001").
- **`regression`**: subagent emits a finding whose `id` matches an existing `resolved` entry, AND the diff shows the resolving code was reverted/edited. Treat as a fresh active finding but keep the history.
- **`dismissed`/`wontfix` → `active`**: the code condition recorded in `depends_on` no longer holds at the current head, so the rationale that closed the finding no longer applies. Reopen as `active`; keep `dismissal_reason` and the original `round_resolved` as history, and note which commit voided the condition. There is no separate "voided" status — a void dismissal is just an open finding again.

### Coverage ledger

The ledger makes coverage **enumerable** instead of assumed: one row per changed file, one cell per `(file, lens)` pair, every cell carrying an explicit verdict. What a round did not look at is a value in the file, not something a reader has to infer from what is missing.

| Verdict | Means | Terminal |
|---|---|---|
| `clean` | the lens ran over the file and found nothing | yes |
| `finding` | the lens ran and produced a finding; `finding_id` links the `findings[]` entry | yes |
| `not-applicable` | the map assigned the lens, the reviewer opened the file, and the lens's trigger is absent; `note` carries the one-line reason. Detection globs and signal regexes over-fire deliberately, so this is a real reviewer verdict, not a bookkeeping artifact — a lens the map never assigned has no cell at all | yes — legitimate, not a gap |
| `cannot-assess` | the lens applies and answering it needs an artifact this run cannot obtain — a Tier 3 execution, a cross-repo file, a query against production data; `note` names the artifact | yes — a known limit, not a gap |
| `not-examined` | the lens never ran over this file; `note` says why | no — a coverage gap |

**Counter partition — the ledger's one arithmetic invariant:**

```
cells_total == cells_examined + cells_cannot_assess + cells_not_examined
```

`cells_examined` covers exactly `{clean, finding, not-applicable}`. Every cell falls in one bucket and no cell falls in two. **A violation means cells were dropped between assembly and write-back** — the counters must be recomputed from `rows`, never adjusted to make the sum work. This is the check that catches the failure the ledger exists to prevent: a partition that does not total is the arithmetic signature of coverage silently going missing.

- **`approve` is forbidden while any cell is `not-examined`; `cannot-assess` does not block it.** The two are different obligations. An unrunnable check is a limit of this review that the PR author cannot act on, so holding the PR for it asks them to fix something that is not theirs. An unexamined cell is work the reviewer can still do, so approving over it certifies code nobody read. Both counters print on every surface regardless — a review that cannot assess half its cells is a weak review, and hiding that behind an unblocked verdict is the same dishonesty one layer down.
- **`not-applicable` and `cannot-assess` are legitimate terminal states; `not-examined` is not.** A cell in any of the three without a `note` is malformed — absent the reason it is indistinguishable from a skipped cell, which is exactly the ambiguity the ledger exists to remove. A `not-examined` cell is reported every round until something examines it. Never drop a cell, and never rewrite one to `not-applicable` or `cannot-assess`, to bring `cells_not_examined` to zero.
- **The ledger carries forward across rounds.** A round rewrites only the cells whose file is in that round's delta (`git diff <last_run_sha>..<CURRENT_HEAD>`); every other cell inherits its earlier verdict verbatim, including `not-examined`. Coverage is cumulative over the PR, not per-round — a gap opened in round 1 is still a gap in round 6 unless a later round closes it, and a file re-touched by a new commit loses its inherited verdicts and is re-examined.

**Three verdict vocabularies live in this file. They describe different layers and must never be cross-read.** `findings[].status` (`active | resolved | dismissed | wontfix | regression`) is the lifecycle of one finding across rounds. `class_sites[].handled` (bool) is whether this PR's changes cover an affected site of that finding's `rule_class`. `ledger.rows[].lenses[].verdict` (`clean | finding | not-applicable | cannot-assess | not-examined`) is whether a lens was applied to a file, and says nothing about whether anything was found elsewhere or fixed anywhere. A `clean` cell is not a `resolved` finding; a `not-applicable` cell is not a `handled: true` site; a `not-examined` cell is not a `dismissed` finding. `finding-output-format.md`, under "`class_completeness:` audit", records the same failure mode one layer up — `class_completeness.sites[].affected` vs `class_sites[].handled` — for the same reason: one word per layer, because a conflated read makes an unexamined file look reviewed.

---

## Finding-ID strategy

```python
id = sha1(f"{file}::{enclosing_symbol}::{rule_class}").hexdigest()[:10]
```

### Why this combination

- **`file`**: stable across line shifts, breaks only on file rename (acceptable — rename = legit new finding scope).
- **`enclosing_symbol`**: function/class/component containing the cited line. Subagent extracts via tree-sitter / regex match for `function|class|const|export default function|const X = (` upward from the cited line. Stable across line shifts within the same function.
- **`rule_class`**: a 2-3 word slug emitted by the subagent describing the *kind* of issue, independent of wording. This is the key insight: the subagent rephrases the issue text every round (`"wrong error code"` → `"incorrect error message"`), but the rule class stays the same.

**Never put a lens id in `rule_class`.** It is a hash component, so an `L8` prefix changes every id the finding will ever have, and the round that adds it sees a repo full of "new" findings while every prior entry becomes unmatchable — the regression sweep degrades to nothing on the round it is needed most. It is also a closed vocabulary describing the defect, not the instrument: two lenses routinely surface the same `rule_class`, and one lens surfaces many. The lens ids travel in `findings[].lens_ids`, off the finding's own `Lens:` line, and take no part in identity.

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

```json
{
  "last_run_sha": "abc123...",
  "last_run_timestamp": "2026-04-11T13:29:50Z",
  "last_run_verdict": "request-changes",
  "findings": [...],
  "filtered_out": [...],
  "last_posted_review_id": 12345678,
  "last_posted_review_node_id": "PRR_kwDO...",
  "last_posted_verdict": "request-changes",
  "last_posted_at": "2026-04-11T13:30:15Z",
  "posted_comments": [
    { "finding_key": "(file.ts, 47, processrequest)", "finding_id": "<id-hash>",
      "github_comment_id": 12345, "github_thread_id": "PRRT_abc123",
      "finding_severity": "Serious" }
  ]
}
```

### Three replay branches

1. **`last_run_sha == CURRENT_HEAD`** — no new commits. AskUserQuestion: `Replay cached (Recommended)` vs `Fresh review`. On replay, print cached findings and exit (Phase 2/3/4 skipped).

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
  PRIOR_STATE='{ pr: <number>, repo: "<owner>/<repo>", findings: [], last_round: 0,
                 ledger: { round: 0, rows: [], cells_total: 0, cells_examined: 0,
                           cells_cannot_assess: 0, cells_not_examined: 0 } }'
fi
```

**The empty `ledger` key in the seed is load-bearing.** Round 1 has no prior state file, and the Phase 3 coverage gate reads `ledger.cells_not_examined` before any write-back has run. Seed the key absent and that read resolves to nothing, nothing is not greater than zero, and the gate passes — silently, on the permissive side, on exactly the run where the reviewer has the least prior coverage to inherit. The seed is the prior round's ledger, not this round's; this round's is built in Phase 3 below and always overwrites it.

Pass `PRIOR_STATE.findings` (filtered to status in `{resolved, dismissed, wontfix}`) into Subagent 1's prompt as:

> The following findings were resolved or dismissed in earlier rounds. Do NOT re-report them unless the diff shows the fix was reverted or the underlying code regressed:
> ```
> - id: <id>, file: <file>, enclosing_symbol: <sym>, rule_class: <class>, status: <status>, last_round: <n>
> ...
> ```

The closed set `SKILL.md` step 4.9 builds — the status arm **plus** the GitHub thread-resolution arm — with each entry's `class_sites`, `inverse_risk`, `depends_on`, and `commit_sha_resolved`, goes to the regression-sweep verifier in Phase 3, which re-checks every closed finding at the current head. Those four fields are the entire reason the state file persists them. A round that loads the state file but drops them degrades the sweep to an ID-hash match, which is exactly what the sweep exists to replace.

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

### Phase 3 — assemble the ledger

**The ledger is built here, in main, and Phase 4 only persists it.** Every consumer reads it before Phase 4 runs: the coverage gate (`SKILL.md` step 9.5) decides the verdict from `cells_not_examined`, and both the terminal header and the posted body print the counters. Assembling it after posting means the gate reads the *previous* round's ledger, or at round 1 no ledger at all — and an absent counter fails permissive, granting the approval the mechanism exists to withhold.

Runs as **`SKILL.md` Phase 3 step 6.9**, after cross-finding reconciliation (6.5) and before ranking (7). That is the earliest point at which the finding set is final: step 6 still adds findings and 6.5 still merges them, so a ledger built any earlier links cells to findings that no longer exist under those ids.

Three inputs, all already in main:

| Input | From | Supplies |
|---|---|---|
| `LENS_ASSIGNMENTS` | Phase 1 lens selection | the cell set — one entry per `(file, lens)`, fixed before any reviewing happened |
| Phase 2 reviewer returns | the per-`(file, lens)` verdicts each reviewer was required to emit | `clean` / `finding` / `not-applicable` / `cannot-assess` and their notes |
| the final finding set | Phase 3 steps 1–6.5 | each finding's `id` and its `Lens:` line, whose ids name the cells that read `finding` |

Assemble in this order:

1. **Rows from `LENS_ASSIGNMENTS`, not from the reviewers.** One row per changed file, in diff order, carrying the file's matched `file_type` list. A file the map skipped gets a row with `lenses: []` and a `skip_reason`. Reviewer output can only fill cells in, never create or delete them — a reviewer that invents a `(file, lens)` pair gets it recorded (the map is a floor, not a ceiling) and flagged as a missing map row; a reviewer that omits one does not get the cell deleted.
2. **Fill each cell from the reviewer that owned the pair.** Its stated `clean` / `not-applicable` / `cannot-assess` verdict, with the reviewer's note attached where the verdict requires one.
3. **Overwrite with `finding` wherever a surviving finding names the cell.** For each finding, for each id in its `lens_ids`, set the `(finding.file, lens)` cell to `finding` and write its `findings[].id` into `finding_id`. This runs after step 2 so that a lens one reviewer called `clean` while another found something on the same pair resolves to `finding` — the positive claim wins. A finding with empty `lens_ids` — raised by the Q axis, or by a reviewer with no lens scope, not by a lens — names no cell and changes no counter; it is a finding the ledger does not account for, and that is correct, because the ledger measures lens coverage and not the run's whole yield.
4. **Inherit from the prior ledger** for cells whose file is outside this round's delta (`git diff <last_run_sha>..<CURRENT_HEAD>`), verbatim, `not-examined` included. A file the delta re-touches loses its inherited verdicts and is re-examined. Inheritance runs before the fill below so an inherited verdict is never overwritten by this round's silence.
5. **Write `not-examined` into every cell still unfilled**, with the reason it is missing: the file was in no chunk, its chunk reviewer errored or truncated, degraded mode dropped the lens, or the reviewer simply said nothing about the pair. A missing verdict is never `clean`.
6. **Recompute all four counters from `rows`** and assert the partition. Never carry a prior round's counts forward; never adjust a counter to make the sum total.

The result is `ledger` in memory, with `round` and `head_sha` set. The gate, the terminal block and the posted body all read it from there. Phase 4 writes exactly this object to the state file, unchanged.

### Phase 4 — write back

After successful posting (or after "Keep local"):

1. For each finding currently posted/active in this round:
   - If `id` not in `PRIOR_STATE.findings`: append new entry with `status: active`, `round_first_seen: <current_round>`, `lens_ids` off the finding's `Lens:` line, and the cascade fields taken straight off the printed finding: `inverse_risk` from its `Inverse risk:` line, `class_sites` from the site list in its `class_completeness:` audit as verified in Phase 3 (each site `handled: false` unless this PR's diff already covers it), `caused_by` from the regression sweep's lineage attribution (null when it attributed none), `depends_on: null`.
   - If `id` already exists with `status: active`: append `<this-round-label>` to `label_history`, update `last_message`. Status stays `active`. Also refresh `inverse_risk` when the suggested fix changed this round, and rewrite `class_sites` with this round's `handled` flags — including sites the current diff newly introduced.
   - If `id` already exists with `status: regression` (entered via Phase 3 step 4.95 because the resolving code was reverted): treat exactly like `active` — append to `label_history`, update `last_message`, refresh `class_sites`. Set `caused_by` when the sweep traced the reopen to another finding's fix. The finding stays in `regression` until the user resolves OR dismisses it (rules below). The history of `round_resolved` + `commit_sha_resolved` is **preserved** (do NOT clear them — they document the prior resolve that got reverted).
2. For each finding the user explicitly dismissed via the post-review AskUserQuestion: write `status: dismissed` + `dismissal_reason: <user reason>` regardless of prior status (including `regression`). A regression that the user dismisses goes to `dismissed` (the prior `round_resolved` + `commit_sha_resolved` from before the regression are kept in the entry as historical context). Write `depends_on` at the same moment — the code condition the rationale rests on, in the user's own terms. It is required for `wontfix` and for any `dismissed` whose reason rests on how the code behaves today; a dismissal with `depends_on: null` can never be voided and will outlive the condition that justified it.
3. For each finding whose fix has shipped (writer caveat below — this transition is currently made by hand): `status: resolved` + `commit_sha_resolved: <sha of the resolving commit>` regardless of prior status — but **only when every `class_sites` entry is `handled: true`**. If any site is still unhandled, keep the prior status (`active` / `regression`), write the updated `handled` flags, and leave `commit_sha_resolved` untouched: a fix covering part of the class is not a resolution. A regression that gets fully re-fixed goes back to `resolved` with the *new* commit SHA; the prior `commit_sha_resolved` is overwritten (only the latest resolving commit is kept — `label_history` retains the full timeline).
4. For each closed finding the Phase 3 regression sweep reopened: an entry reopened because a `class_sites` site went unhandled or its `inverse_risk` failure mode materialized becomes `status: regression`; a `dismissed`/`wontfix` entry whose `depends_on` condition was voided becomes `status: active`, keeping `dismissal_reason` and `round_resolved` as history and naming the voiding commit in `last_message`.
5. Persist the `ledger` object Phase 3 step 6.9 assembled, byte for byte. Phase 4 is not a second construction site: the gate has already ruled on these counters and both the terminal and the posted body have already printed them, so a ledger rebuilt here could contradict a verdict that has shipped. Re-assert the partition before writing; a violation means the object was mutated between the gate and the disk, and the round's coverage claim is void.
6. Persist `followup_issue` from the outcome `SKILL.md` Phase 4's "File the follow-up issue" step resolved — `filed`, `incomplete`, `failed` or `declined`, with `finding_ids` set in every case. Write it on **every** path that reaches write-back, "Keep local" and a declined offer included: the point of the key is that round 4 can tell an issue that exists from one the user declined from a state file that was lost, and only the first of those three is self-evident from GitHub. Never synthesize it here from a URL the step did not return, and never write `filed` for an issue whose read-back was short — that is `incomplete`, and the distinction is the entire complete-or-not-at-all guarantee.
7. Increment `last_round`. Update `updated_at`.
8. Write the file atomically (temp + rename).

State transitions in Phase 4:

| Prior status     | Subagent emits finding? | User dismisses? | Fix shipped? | New status           |
|------------------|-------------------------|-----------------|------------------------------|----------------------|
| (no entry)       | yes                     | no              | no                           | `active` (new entry) |
| `active`         | yes                     | no              | no                           | `active`             |
| `active`         | yes                     | yes             | no                           | `dismissed`          |
| `active`         | (n/a)                   | no              | yes — every `class_sites` entry `handled: true` | `resolved`  |
| `active`         | (n/a)                   | no              | yes — some `class_sites` entry still unhandled  | `active` (partial fix is not a resolution; `handled` flags updated) |
| `resolved`       | yes (regression)        | no              | no                           | `regression`         |
| `regression`     | yes                     | no              | no                           | `regression`         |
| `regression`     | yes                     | yes             | no                           | `dismissed`          |
| `regression`     | (n/a)                   | no              | yes — every `class_sites` entry `handled: true` | `resolved` (new SHA) |
| `dismissed`/`wontfix` | yes (suppressed)   | (n/a)           | (n/a)                        | unchanged (suppressed in Phase 3 step 4.95) |
| `dismissed`/`wontfix`, `depends_on` condition voided at current head | (n/a) | (n/a) | (n/a)  | `active` (reopened; `dismissal_reason` + `round_resolved` kept as history) |

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
