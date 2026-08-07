# GitHub posting flow (Phase 4) — REST + GraphQL hybrid

Loaded by SKILL.md when posting findings to a real PR. SKILL.md keeps a ~30-line dispatch step that delegates to this reference.

This file owns:
- Composing summary body (findings table + collapsed coverage ledger) + per-finding review comments
- Pre-posting hunk validation (line vs file-level routing)
- Three-phase REST/GraphQL posting (PENDING review → file-level threads → submit)
- **Prior-review detection**: read the marker comment on earlier `/review-pr` reviews to number the round and dedupe threads — read-only, never to edit them
- Pre-posting preflight on re-runs: verdict-body sync check, thread resolution for findings closed since the last round
- Post-submit assertion: the review is really `SUBMITTED` and carries every thread we intended
- Failure recovery (Phase A/B/C disclosed partial state)
- State + cache write-back

---

## Why two APIs (READ BEFORE EDITING)

**DO NOT regress this to a single REST call with `subject_type: "file"` comments.** That shape is rejected by GitHub:

- **Line-level review comments** (`{path, line, side: "RIGHT"}`): Supported by REST `POST /pulls/:n/reviews` AND by GraphQL `addPullRequestReviewThread`.
- **File-level review comments** (no line anchor): Supported ONLY by GraphQL `addPullRequestReviewThread` with `subjectType: FILE`. The REST endpoint uses `DraftPullRequestReviewComment` which has no `subjectType` field — passing `subject_type: "file"` returns `422 Unprocessable Entity`. This was the bug that silently collapsed past runs to a monolithic body and lost every resolvable thread.

The hybrid flow:
1. **Phase A (REST)** — create PENDING review with line-level comments.
2. **Phase B (GraphQL)** — attach file-level threads.
3. **Phase C (GraphQL)** — submit with the verdict event.

Every round runs all three phases. There is no path that reuses a previous round's review.

---

## A posted review body is immutable (READ BEFORE EDITING)

**Once a review is submitted, its body is never edited — a later round supersedes it with a NEW review.** No step in this file may call `updatePullRequestReviewBody`, and no step may re-submit or re-target a review from an earlier round.

The body is that round's evidence: it carries the round's verdict, its findings table, and its coverage ledger — what that round actually examined. An in-place edit overwrites that record with a different round's, and has twice been observed destroying a round report and corrupting the `<!-- review-pr:run -->` marker. Accumulation is cheap in exchange: rounds are capped at 3, so a PR collects at most three review entries.

---

## Step 0 — Detect prior `/review-pr` reviews (round number + dedupe)

Every review posted by `/review-pr` includes a hidden marker comment in the body:

```markdown
<!-- review-pr:run sha=<head_sha_at_post_time> round=<round_number> -->
```

Before posting a new review, query for prior tagged reviews:

```bash
PRIOR_REVIEWS=$(gh api graphql -f query='
  query($owner:String!, $repo:String!, $num:Int!) {
    repository(owner:$owner, name:$repo) {
      pullRequest(number:$num) {
        reviews(first:100) { nodes { id databaseId state submittedAt body } }
      }
    }
  }
' -f owner=<owner> -f repo=<repo> -F num=<num> \
  | jq -c '
      [.data.repository.pullRequest.reviews.nodes[]
       | select(.body | test("<!-- review-pr:run"))]
      | sort_by(.submittedAt)
    ')

PRIOR_ROUND=$(echo "$PRIOR_REVIEWS" | jq -r '
  (last // {}) | (.body // "") | (capture("round=(?<r>[0-9]+)").r // "0")')
```

**This query is read-only.** Nothing downstream may pass a prior review's `id` to a mutation. What the result is for:

- **Round continuity** — `PRIOR_ROUND + 1` must equal the `CURRENT_ROUND` SKILL.md passed in. A mismatch means a round was posted by a run whose state file was lost; take the higher of the two so the marker never repeats a round number.
- **Dedupe** — findings already carrying a thread from an earlier round are filtered out before the lists are built (Step 0c step 4, Step 3b). Prior reviews are how you tell a genuinely new finding from a re-emitted one when the cache is missing: fetch those reviews' comments and recompute each id from the `<!-- review-pr:finding -->` marker Step 2 puts on every one. The marker is the whole reason that fallback is possible — a comment posted without it is undedupable and will be re-raised next round.
- **Round count against the cap** — `length` of `PRIOR_REVIEWS` is how many review entries `/review-pr` has already left on this PR. **The cap does not read it**: `SKILL.md` keys the cap on `CURRENT_ROUND`, derived from the state file alone. So this count is a cross-check for the one case the state file cannot cover — it was lost, `CURRENT_ROUND` restarts at 1, and the PR already carries three reviews. Report the discrepancy rather than acting on it; capping is `SKILL.md`'s call, not posting's.

**Branch**: there is exactly one. Always continue to Step 4 and create a fresh review. Age of the prior review is irrelevant — nothing is being edited, so there is no stale-commit-history hazard to guard against.

---

## Step 0b — Verdict-body sync check (re-runs)

If `last_posted_review_id` exists in cache, compare last-posted body verdict against GitHub state:

```bash
LAST_POSTED_REVIEW_ID=$(jq -r '.last_posted_review_id // empty' "$CACHE_FILE")
if [ -n "$LAST_POSTED_REVIEW_ID" ]; then
  LAST_POSTED_STATE=$(gh api "repos/<owner>/<repo>/pulls/<num>/reviews/$LAST_POSTED_REVIEW_ID" --jq .state)
  LAST_POSTED_BODY_VERDICT=$(gh api "repos/<owner>/<repo>/pulls/<num>/reviews/$LAST_POSTED_REVIEW_ID" --jq .body | grep -oE '\*\*Verdict\*\*:\s*`?(approve|comment|request-changes)`?' | sed 's/.*\(approve\|comment\|request-changes\).*/\1/')
fi
```

If they drifted:

> **Previous review's body verdict (`<body>`) does NOT match GitHub state (`<state>`).** Likely cause: self-review coerced to `comment`, or manual edit in GitHub UI. The current run does not touch that review — its body stays as posted. This round's "Post now" adds a NEW review carrying the corrected verdict.

---

## Step 0c — Re-review thread resolution (before posting)

If this is a re-review AND `posted_comments` cache exists:

1. **Identify findings closed this round**: compare current findings against `posted_comments` via dedupe key. A cached finding NOT in this round's finding set is closed this round when **either**:

   - its `github_thread_id` resolves to a thread GitHub reports as `isResolved: true` (query thread state; Step 0's review query does not carry it), **or**
   - its `id` carries `status in {resolved, dismissed, wontfix}` in `PRIOR_STATE`.

   **Do not key on `status: resolved` alone.** `dismissed` is written automatically when the user deselects a finding, but `resolved` has no automated writer — it is set by hand, so on any machine where nobody edits the state YAML nothing is ever `resolved`, and this step plus Step 8d never fire at all. Every thread then stays open however many rounds fixed the code. Thread state is the signal that actually moves, because merging requires resolving threads. `SKILL.md` step 4.9 builds its closed set from the same two arms; they must stay aligned or the two steps disagree about which findings are open.

   **`isResolved` is evidence a thread was closed, never that a finding was correct.** Where a repository ruleset requires thread resolution to merge, authors resolve findings they dispute in order to ship. So it may corroborate a finding the reviewer no longer sees at head; it may never remove one the reviewer still does. A finding present in this round's set keeps its row in the findings table and its thread whatever GitHub says about resolution.

   **Absence counts only where the file was examined.** If the finding's file carries a `not-examined` cell for the lens that raised it, no reviewer looked this round, and its absence from the set is silence rather than a fix — leave it open and do not resolve its thread. A finding with empty `lens_ids` names no cell, so fall back to its file's ledger row: if the file has no row, or every cell on it is `not-examined`, treat the absence as silence too. That fallback is what keeps the guard from passing vacuously on exactly the gap-check findings least likely to have been looked at twice.

2. **Resolve their threads** on GitHub, skipping any already `isResolved`:

   ```bash
   gh api graphql -f query='
     mutation($threadId: ID!) {
       resolveReviewThread(input: {threadId: $threadId}) {
         thread { isResolved }
       }
     }
   ' -f threadId="<thread_id>"
   ```

3. **Track them** for the "Resolved since last review" line in the summary body. Use exact wording: `Resolved since last review: S1 (<file:line> <one-line issue>, round 4 commit <sha>), ...`. NEVER use "deferred", "fixed", or other ambiguous wording — use `resolved` with the commit SHA. A finding closed on the thread arm has no `commit_sha_resolved`: name the head SHA this round read and write `thread resolved` in place of the commit, rather than attributing the close to a commit nobody identified.

4. **Filter review comments**: only post comments for findings NEW or STILL ACTIVE — do NOT re-post findings already present from a previous round (they already have threads). A finding is "still present" if its `id` matches a cached `posted_comments` entry — skip the comment.

5. **Error handling**: failed `resolveReviewThread` (already resolved, permission issue) is best-effort — log and continue. Never blocks posting.

---

## Step 1 — Compose the summary body

Build a lean summary body (NO "Filtered out" section — internal only). **Always** include the marker comment so future runs can detect this review:

```markdown
<!-- review-pr:run sha=<head_sha> round=<round_number> -->
## PR Review: #<number>
<verdict-emoji> <verdict> | <severity-count-badges>
**Senior engineer approval**: <emoji> <Yes | No | With changes> — <one-sentence reason>

**Goal**: <intent goal>
**Summary**: <2-3 sentences>
**Round**: <round> (<active>/<resolved>/<dismissed> carried)  <!-- omit at round 1 -->
**Convergence**: <N> new · <C> caused by earlier fixes · <R> regressions reopened · <F> carried — <trend sentence>  <!-- omit at round 1 -->
**Mode**: <mode line>  <!-- omit when no mode applies -->

### Findings
| # | Sev | File | Issue |
|---|-----|------|-------|
| S1 | 🟠 | `<path:line>` | <one-line issue> |
| M1 | 🟡 | `<path>` | <one-line issue (file-level)> |
| m1 | 🔵 | *(general)* | <one-line issue (body-fallback)> |

*Details in review comments below.*  <!-- omit if ALL findings are body-fallback -->

<resolved-since-last-review line — wording below; omit on round 1>

### Additional findings  <!-- body-fallback findings only; omit the heading when there are none -->
<each finding with no file reference, rendered with the Step 2 comment projection>

**Coverage**: <cells_examined>/<cells_total> cells examined across <files_changed> files changed. <cells_cannot_assess> cells cannot be assessed without <artifact>.  <!-- second sentence omitted entirely when cells_cannot_assess == 0 --> **<cells_not_examined> cells NOT examined — this review does not cover them.**  <!-- third sentence omitted entirely when cells_not_examined == 0 -->

<details>
<summary>Coverage ledger — round <round>, head <head_sha></summary>

| File | Type | Examined | Cannot assess | Not examined |
|---|---|---|---|---|
| `<path>` | `<file_type>` | L4 clean · L7 finding (S1) · L9 not-applicable (<note>) | — | — |
| `<path>` | `<file_type>` | L4 not-applicable (<note>) | L13 — <artifact> | **L9** — <note> |
| `<path>` | skipped — <skip_reason> | — | — | — |

</details>
```

**This template is the only place a review body is assembled.** Main passes the content — verdict, findings, intent, counters, the in-memory ledger — and Step 1 lays it out; main never hands over a pre-composed body. Every block the body can carry has a slot here; the sections below fill slots, they never append. A body specified in two places is how the ledger and the findings table drift out of sync.

### What the body projects from the canonical header

The template above renders the run-level header field list defined in `references/finding-output-format.md`. It carries `Number`, `Verdict`, `Severity counts`, `Senior engineer approval`, `Goal`, `Summary`, `Round`, `Convergence`, `Mode` and `Coverage`. Three canonical fields are deliberately absent:

- **`Title`** — GitHub renders the PR title directly above every review on the page. Repeating it costs a line and can contradict the page after a retitle.
- **`Size`** — the Files-changed tab states additions, deletions and file count more accurately than a review body can, and restates them after every push.
- **`Reviewers`** — subagent topology is an implementation detail of this skill and means nothing to a PR author. Where a degraded reviewer actually cost coverage, the loss surfaces in the always-visible `Coverage` line and in the ledger's `not-examined` cells, which is the form the reader can act on. A `<verifier> unavailable — verified inline` note is not reported here at all: that check ran, so there is nothing for a reader to do about it.

`Round`, `Convergence` and `Mode` are on the body deliberately, and were absent from it for some time. A reader on the PR page could not tell a first look from a third, nor see that the fixes were generating the findings, nor learn that a partial re-review had read only the newest commits. All three change how much weight the verdict deserves, and all three were available while only the terminal saw them. `Mode` here carries the partial-re-review and intent-not-grounded values; the cross-repo value is suppressed on this surface alone. Its real cost is a thinner reusability index, and that cost already lands where a reader can use it — as `not-examined` or `cannot-assess` cells in the ledger. What remains is a fact about the reviewer's working directory, which no PR author can act on.

The heading is `##`, not the terminal block's `#`. A review body is a comment inside a page that already has an H1; an H1 here renders at page-title size against the PR's own title.

**Coverage line rules**:

- Counters are `files_changed`, `cells_total`, `cells_examined`, `cells_cannot_assess`, `cells_not_examined`, read verbatim from the in-memory `ledger` object Phase 3 step 6.9 assembled and main passes in — **not** from the state file, which Step 8c has not written yet when this body is composed. Reading the file here renders the previous round's coverage under this round's verdict, and at round 1 renders the seed's zeros, which look like full coverage on the run that has the least of it.
- Cell verdicts are the five values `clean | finding | not-applicable | cannot-assess | not-examined`, the vocabulary fixed in `references/finding-state-schema.md` — never substitute "skipped", "partial", "TODO", or "n/a".
- `cells_examined` covers `{clean, finding, not-applicable}` only. With `cells_cannot_assess` and `cells_not_examined` it partitions `cells_total`, which is why all three print: render the counters, never re-derive one by subtracting the others. A body that shows `cells_examined` alone reads as full coverage on a run where a third of the cells resolved to an artifact nobody could obtain.
- The gap sentence is **outside** the `<details>`, in the always-visible line. A reader deciding whether to merge must see an unexamined cell without opening anything; `approve` is forbidden while `cells_not_examined > 0` and the visible line is what makes that check auditable from the PR page alone.
- The `cannot-assess` sentence sits on that same visible line and does **not** gate the verdict — the missing artifact is the review's limit, not something the author can supply. It prints anyway: a review that could not assess much of its cell set is a weak review, and a reader weighing an `approve` needs to tell that from a thorough one.
- Inside the ledger, a `not-examined` cell renders as **bold lens id** plus its `note`. A `cannot-assess` cell renders as lens id plus the artifact its note names — the artifact is the whole content of the cell, since without it a reader cannot judge whether obtaining it was reasonable. `not-applicable` carries its note too; without it a legitimate skip reads identically to a gap.
- One row per changed file, including files no lens applied to (all three cell columns `—`) and files the map skipped, whose `Type` column carries `skipped — <skip_reason>`. `len(rows)` must equal `files_changed`; if it doesn't, the ledger lost a file and the body must say so rather than silently render a short table. That equality is the ledger's own lost-a-file detector, so a skipped row is never dropped to keep the table short — dropping it trips the check on every PR that touches an image or a lockfile, and an alarm that fires constantly is one nobody reads when it is real.
- The rendered table is a digest. The machine-readable ledger — every cell, every note, carried forward across rounds — lives in `.claude/review-state/<pr>.yml`; never trim the state file to match what the body shows.
- Keep the blank line after `<summary>` and before `</details>`. GitHub renders the enclosed markdown table only when the HTML block is separated that way; without it the table posts as literal pipes.

**Severity count badges**: the `Severity counts` field, rendered `🔴 <N> Critical · 🟠 <M> Serious · 🟡 <K> Moderate · 🔵 <J> Minor` — only tiers that have findings. Tier emoji are fixed in `references/finding-output-format.md`; do not pick your own.

**Finding numbering**: the ids in the `#` column are the run's canonical finding ids, assigned by main in Phase 3 — `references/finding-output-format.md` defines them and their per-round scope. Posting neither invents nor renumbers them: the same id must appear in this table, in that finding's review comment, and in the ledger cell that reports it, or a reader cannot walk from the table to the thread.

**Comment routing — three tiers**:

- **Line-level thread** (REST, Phase A): finding has a valid `file:line` where the line exists on the post-image side of the diff → attach with `{path, line, side: "RIGHT", body}`.
- **File-level thread** (GraphQL, Phase B): finding has a file reference but no valid diff line (file/module-scope, schema overlap, line not in diff) → attach via `addPullRequestReviewThread` with `subjectType: FILE`.
- **Body fallback** (rare): finding has NO file reference at all → use `*(general)*` in the summary table and put the full detail in the template's `### Additional findings` slot.

All three tiers create resolvable, replyable GitHub threads. Body fallback is the only acceptable reason for a finding to lack its own thread — never use it to work around an API error (Step 7 covers that).

**Re-review "Resolved since last review" line**: replace the prior "Fixed" wording with explicit `resolved`. Fills the template slot under the findings table:

```markdown
**Resolved since last review**: S1 (`auth.ts:47` missing null check, round 4 commit `abc1234`), S4 (`db.ts:123` N+1 query, round 5 commit `def5678`) *(threads resolved)*
```

**The ids on this line are the labels those findings carried when they were raised, taken from each entry's `label_history` in the state file — not this round's ids.** A finding on this line is by definition absent from this round's set, so main assigned it no id this round; ids are per-round labels and `S1` in round 4 is not `S1` in round 5. The label is what makes the line usable: it is what the reader saw in the round-4 body and on the round-4 thread. Where an entry has no `label_history` — closed before labels were persisted — write the `file:line` and the issue text alone and omit the id rather than minting one, which would collide with a live finding in this round's table.

Every finding status is exactly one of `active`, `resolved` (with commit SHA), `dismissed` (with reason), `wontfix` (with reason), or `regression` — the enum in `references/finding-state-schema.md`. "Deferred" is not one of them: it leaves the reader unable to tell a shipped fix from an open one.

---

## Step 2 — Compose review comments (per finding)

Each finding with a valid file reference becomes a review comment. Format as self-contained markdown:

```markdown
<!-- review-pr:finding id=<hash> rule-class=<slug> symbol=<enclosing-symbol> -->
<severity-emoji> **<Severity>** `<C1|S1|M1|m1>` · <Category><confidence-suffix>

**<Issue one-sentence>**

<2-3 sentence explanation>

**Why it matters**: <one sentence>

**Suggested fix**: <one sentence, actionable>

**Inverse risk**: <the failure mode this fix trades INTO if implemented literally, or "none — pure addition">

**Class-sites**: <A>/<N> — affected sites over the entries in the sweep's site list
```

### What the comment projects from the per-finding block

The comment renders the canonical per-finding block from `references/finding-output-format.md`: `Severity` (as emoji + word, per that file's tier mapping), the finding's id, `Category`, `Issue`, `Why it matters`, `Suggested fix`, `Inverse risk` and `Class-sites`. `File` is not printed — the thread is anchored to it, and for a file-level thread the body names the symbol instead (see the payload shape below).

Four canonical fields are handled specially:

- **`Confidence`** renders as ` · <medium|low> confidence` appended to the category line, and is omitted only when the finding is `high`. A hedged claim posted with no hedge reads as certain, and the author cannot weigh a `low` against their own knowledge of the code if the comment never tells them it was one. High is the unmarked default, so marking it adds noise on the majority of comments and signal on none.
- **`Lens`** is not printed on the comment at all. The link between a finding and the lens that raised it is already on this page in a form a reader can use: the ledger's `Examined` column renders the cell as `<lens> finding (<id>)`, so the same id walks from the findings table to the thread and back to the lens. Repeating it per comment restates the ledger one row at a time and answers a question no author asks about their own code.
- **`Rule-class`** and **`Enclosing-symbol`** are carried in the leading HTML marker rather than as visible lines. They exist for the ID derivation in `references/finding-state-schema.md`, and a reader has no use for either — but Step 0 treats prior review bodies as the fallback dedupe source when the cache is missing, and without these two the id cannot be recomputed from what is on the PR. Visible prose would pay a per-comment readability cost for a field only a parser reads; the marker pays nothing and matches the `<!-- review-pr:run -->` convention already in the body.

**Inverse risk and Class-sites are not decoration.** They are the two cascade fields Phase 3
steps 4.56 and 4.55 derived, and `/fix-pr-review` seeds its own inverse-risk check and class
sweep straight off these two lines instead of re-deriving them. Emit both on every finding
that proposes a code change — `none — pure addition` is a valid `Inverse risk`, an omitted
line is not.

**Comment payload shape**:

- **Line-level (REST, Phase A)**: `{"path": "<file>", "line": <post-image>, "side": "RIGHT", "body": "<markdown>"}` — goes into the `comments` array of the REST review creation call.
- **File-level (GraphQL, Phase B)**: `path: "<file>"`, `subjectType: FILE`, `body: "<markdown>"`, `pullRequestReviewId: <node_id from Phase A>`. GitHub doesn't anchor code for file-level threads — include a brief code reference in the body (e.g., "near the `<symbol>` definition").

---

## Step 3 — Pre-posting hunk validation

Before Phase A, fetch hunks once and verify each line-level comment's `(path, line)` is on the post-image side. Demote mismatches to file-level (Phase B).

```bash
gh api "repos/<owner>/<repo>/pulls/<number>/files" --paginate \
  --jq '.[] | {filename, patch}'
```

**Output format**: `--paginate` with `--jq` emits NDJSON (one `{filename, patch}` per line across pages), NOT a JSON array. Process line-by-line; do NOT pipe to another `jq '.[]'` expecting an array — fails on page 2.

Parse each `patch`: each `@@ -<oldStart>,<oldLen> +<newStart>,<newLen> @@` header starts a new hunk. Within the hunk, `+` lines and space-prefixed context lines advance the post-image counter (start at `newStart`); `-` lines do not. A line is "in the diff" only if it matches a counter value on some hunk for that file.

For each line-level finding: is `line` present on `path`'s post-image counter? If yes → keep. If no → demote to file-level + log the demotion.

---

## Step 3b — Dedupe against threads posted in earlier rounds

Findings that already carry a thread from an earlier round keep it; a new review does not re-raise them (this is the mechanics behind Step 0c's "only post comments for findings NEW or STILL ACTIVE"). **Apply the filter here, while the lists are still being built — never inside the Phase B loop.** A skip inside the loop would leave `ATTACHED_THREADS` legitimately short of the list length, and Step 6b would then have to tell a deliberate skip apart from a lost thread.

For each finding, look up its `id` (per `references/finding-state-schema.md`) in `$CACHE_FILE`'s `posted_comments[]` array (canonical path: `$HOME/.claude/skills/review-pr/cache/<owner>_<repo>_<pr-number>.json`, set in SKILL.md Phase 1). A hit means the thread is already on GitHub — drop the finding from both lists:

```bash
# Pseudocode, once per finding, before COMMENTS_JSON is frozen:
existing_thread_id=$(jq -r --arg id "$finding_id" \
  '.posted_comments[] | select(.finding_id == $id) | .github_thread_id // empty' \
  "$CACHE_FILE")
if [ -n "$existing_thread_id" ]; then
  echo "Finding $finding_id already has thread $existing_thread_id — not re-posting" >&2
  # exclude from COMMENTS_JSON and from the file-level list
fi
```

The finding still appears in the summary table and in the state file — only its thread is not duplicated. After this filter, `COMMENTS_JSON` and the file-level list hold exactly what this round intends to post, which is what Step 6b asserts against.

---

## Step 4 — Phase A: create PENDING review with line-level comments (REST)

Run this every round, prior reviews or not.

Pass ALL fields in a single `--input` JSON. **Omit the `event` field** so the review stays PENDING while Phase B attaches file-level threads:

**Note**: call Phase A even with zero line-level findings — pass `comments: []`. The REST endpoint accepts an empty array with a body-only PENDING review; this is the only way to get the `pullRequestReviewId` Phase B's mutations need.

```bash
COMMENTS_JSON='[
  {"path": "<file path>", "line": <post-image line>, "side": "RIGHT", "body": "<line-level comment>"}
]'
# OR: COMMENTS_JSON='[]'  when all findings are file-level

REVIEW_RESP=$(gh api "repos/<owner>/<repo>/pulls/<number>/reviews" \
  --method POST \
  --input <(jq -n \
    --arg body "<summary body from Step 1>" \
    --arg commit_id "<head SHA>" \
    --argjson comments "$COMMENTS_JSON" \
    '{body: $body, commit_id: $commit_id, comments: $comments}'))

REVIEW_NODE_ID=$(echo "$REVIEW_RESP" | jq -r '.node_id // empty')
REVIEW_DB_ID=$(echo "$REVIEW_RESP" | jq -r '.id // empty')

if [ -z "$REVIEW_NODE_ID" ] || [ -z "$REVIEW_DB_ID" ]; then
  echo "Phase A returned no node_id/id. Full response:" >&2
  echo "$REVIEW_RESP" >&2
  # → Step 7
fi

ATTACHED_THREADS=0
```

Capture BOTH IDs: `node_id` (GraphQL) for Phases B/C, `id` (integer) for caching.

---

## Step 5 — Phase B: attach file-level threads (GraphQL)

For each file-level finding (originals + Step 3 demotions):

```bash
THREAD_RESP=$(gh api graphql -f query='
  mutation($reviewId: ID!, $path: String!, $body: String!) {
    addPullRequestReviewThread(input: {
      pullRequestReviewId: $reviewId, path: $path, body: $body, subjectType: FILE
    }) {
      thread { id comments(first: 1) { nodes { databaseId } } }
    }
  }
' -f reviewId="$REVIEW_NODE_ID" -f path="<file>" -f body="<file-level body>")
# -f (lowercase) forces string; -F would coerce numeric-looking values to JSON numbers

# gh api graphql exits 0 even when GraphQL returns errors — check both .errors AND thread.id
if echo "$THREAD_RESP" | jq -e '.errors' >/dev/null \
   || [ "$(echo "$THREAD_RESP" | jq -r '.data.addPullRequestReviewThread.thread.id // empty')" = "" ]; then
  echo "Phase B failed on thread $((ATTACHED_THREADS + 1)). Response: $THREAD_RESP" >&2
  # → Step 7 with current ATTACHED_THREADS count
fi
ATTACHED_THREADS=$((ATTACHED_THREADS + 1))
```

Loop **sequentially, not in parallel** — thread order in the submitted review follows call order. Capture each returned `thread.id` and `comments.nodes[0].databaseId` for caching.

---

## Step 6 — Phase C: submit the review (GraphQL)

```bash
SUBMIT_RESP=$(gh api graphql -f query='
  mutation($reviewId: ID!, $event: PullRequestReviewEvent!) {
    submitPullRequestReview(input: { pullRequestReviewId: $reviewId, event: $event }) {
      pullRequestReview { id databaseId state submittedAt }
    }
  }
' -f reviewId="$REVIEW_NODE_ID" -f event="<APPROVE|COMMENT|REQUEST_CHANGES>")

if echo "$SUBMIT_RESP" | jq -e '.errors' >/dev/null \
   || [ "$(echo "$SUBMIT_RESP" | jq -r '.data.submitPullRequestReview.pullRequestReview.databaseId // empty')" = "" ]; then
  echo "Phase C submit failed. Response: $SUBMIT_RESP" >&2
  # → Step 7 — review is still PENDING with all attached threads
fi
```

**Event mapping**: `approve` → `APPROVE`, `comment` → `COMMENT`, `request-changes` → `REQUEST_CHANGES`.

A Phase C failure is the worst case: pending review has all threads but is never submitted, lingering as a draft.

---

## Step 7 — Posting failed recovery (NEVER silent)

If Phase A, B, or C fails, or Step 6b's assertion fails: **DO NOT silently collapse to a monolithic body.** The prior silent fallback was the root cause of past zero-resolvable-comment runs.

Use AskUserQuestion (cursor-selectable, NOT a numbered prose list).

**Disclose partial state in the question text**: name which phase failed AND report how many threads/comments are already attached, e.g.:

> "Phase B failed on thread 3 of 8. Pending review `<REVIEW_NODE_ID>` has 2 file-level threads + N line-level comments attached from Phase A. GitHub error: `<error>`. How should I proceed?"

```
Question:
  header: "Post failed"
  text: "<phase>. Pending review has <K> thread(s) attached. Error: <error>. How should I proceed?"
  options:
    - label: "Post as monolithic body"
      description: "Delete the pending review, then post via gh pr review --body-file with all findings inline — loses resolvable threads but the review still appears on GitHub"
    - label: "Abort — keep local"
      description: "Delete the pending review; nothing is posted. Review stays in your terminal only"
    - label: "Show payload & keep draft"
      description: "Print the failing request body/mutation and leave the pending review as a draft on GitHub for manual submit"
```

**Cleanup helper** (used by "Post as monolithic" + "Abort"):

```bash
cleanup_pending_review() {
  local out
  if ! out=$(gh api graphql -f query='
    mutation($id: ID!) {
      deletePullRequestReview(input: {pullRequestReviewId: $id}) { clientMutationId }
    }
  ' -f id="$REVIEW_NODE_ID" 2>&1); then
    echo "WARNING: could not delete pending review $REVIEW_NODE_ID — $out" >&2
    echo "Manually clean up at https://github.com/<owner>/<repo>/pull/<n> → Files changed → Pending review" >&2
    return 1
  fi
}
```

**On "Post as monolithic"**: call `cleanup_pending_review` (best-effort), then `gh pr review <url> <verdict-flag> --body-file /tmp/review-pr-<num>-monolithic.md`.

**On "Abort"**: `cleanup_pending_review` and stop.

**On "Show payload"**: print the offending JSON/mutation. Do NOT clean up — user explicitly chose to keep the draft. Print the pending review URL.

---

## Step 6b — Assert SUBMITTED state and thread count

Phase C returning a `databaseId` is not proof the review left `PENDING`. A run that stayed pending lost ten findings, a full authorization analysis among them, with no error raised anywhere — the local record said "posted" and GitHub showed nothing. Re-query and assert before anything is written back.

```bash
LINE_COMMENTS=$(echo "$COMMENTS_JSON" | jq 'length')
EXPECTED_THREADS=$((LINE_COMMENTS + ATTACHED_THREADS))

ASSERT_JSON=$(gh api graphql -f query='
  query($owner:String!, $repo:String!, $num:Int!) {
    repository(owner:$owner, name:$repo) {
      pullRequest(number:$num) {
        reviews(last: 20) { nodes { id state } }
        reviewThreads(last: 100) {
          nodes { id comments(first: 1) { nodes { pullRequestReview { id } } } }
        }
      }
    }
  }
' -f owner=<owner> -f repo=<repo> -F num=<number>)

OBSERVED_STATE=$(echo "$ASSERT_JSON" | jq -r --arg id "$REVIEW_NODE_ID" \
  '.data.repository.pullRequest.reviews.nodes[] | select(.id == $id) | .state // empty')

OBSERVED_THREADS=$(echo "$ASSERT_JSON" | jq --arg id "$REVIEW_NODE_ID" \
  '[.data.repository.pullRequest.reviewThreads.nodes[]
    | select(.comments.nodes[0].pullRequestReview.id == $id)] | length')

if [ -z "$OBSERVED_STATE" ] || [ "$OBSERVED_STATE" != "SUBMITTED" ] \
   || [ "$OBSERVED_THREADS" -ne "$EXPECTED_THREADS" ]; then
  echo "POST ASSERTION FAILED: review $REVIEW_NODE_ID state=${OBSERVED_STATE:-MISSING} threads=$OBSERVED_THREADS expected=SUBMITTED/$EXPECTED_THREADS" >&2
  # → Step 7, with this line as <error>. Do NOT continue to Step 8.
fi
```

Three assertions, all of which must hold:

1. **The review exists** — empty `OBSERVED_STATE` means the node id we hold matches nothing on the PR.
2. **State is `SUBMITTED`** — `PENDING` means the review is a private draft nobody but the author can see. This is the failure that ate the ten findings.
3. **`OBSERVED_THREADS == EXPECTED_THREADS`** — every line-level comment in `COMMENTS_JSON` and every file-level thread counted by `ATTACHED_THREADS` landed. Nothing is subtracted: Step 3b filters already-posted findings out of both lists before Phase A, so both counts describe only what this round set out to post.

**On failure**: go to Step 7 and surface the assertion line as the error. Never swallow it, never downgrade it to a warning, and never fall through to Step 8 — a write-back past a failed assertion records `github_thread_id`s and a `last_posted_verdict` for findings that are not on the PR, and round N+1 then treats them as already-raised and stays silent about them. If the user picks a Step 7 recovery, write back only what that recovery actually landed.

Paginate `reviewThreads` past 100 on long-lived PRs; an under-count here raises a false alarm that looks identical to a real one.

---

## Step 8 — Cache + state write-back

Only reachable after Step 6b passed. After successful Phase C:

### 8a. Update `posted_comments` in `$CACHE_FILE`

Merge into existing cache (do NOT overwrite). Add/update:

- `last_posted_review_id` — integer `databaseId` of the review this round created (Phase C's response, equal to `REVIEW_DB_ID` from Phase A). Never a prior round's ID: this field is what Step 0b re-queries, and pointing it at an older review makes the next run's drift check read a body this run never wrote.
- `last_posted_review_node_id` — GraphQL node ID
- `last_posted_verdict` — verdict string
- `last_posted_at` — ISO timestamp
- `posted_comments` — array of comment entries (preserve existing entries; merge new ones)

Each entry is keyed on `finding_id` — the `sha1(file::enclosing_symbol::rule_class)` hash from `references/finding-state-schema.md`. That is the field Step 3b and Step 0c look entries up by, and the only key either reads. Do **not** also store a positional `(file, line, symbol)` key: it is the shape the hash replaced, it breaks the moment lines shift, and a second key nothing reads is a second thing to keep in sync.

### 8b. Populate `github_thread_id` (line-level requires correlation query)

REST and GraphQL return different identifiers:

- **File-level threads**: `data.addPullRequestReviewThread.thread.id` is the GraphQL node ID. Use directly.
- **Line-level comments**: Phase A's REST response has `.comments[].id` (numeric `databaseId`), NOT the thread node ID. Run one follow-up query to correlate:

```bash
gh api graphql -f query='
  query($owner:String!, $repo:String!, $num:Int!) {
    repository(owner:$owner, name:$repo) {
      pullRequest(number:$num) {
        reviewThreads(last: 100) {
          nodes { id comments(first: 1) { nodes { databaseId } } }
        }
      }
    }
  }
' -f owner=<owner> -f repo=<repo> -F num=<number>
```

Match each line-level comment's `databaseId` (from REST `.comments[].id`) to a thread via `reviewThreads.nodes[].comments.nodes[0].databaseId`; take that thread's `id` as `github_thread_id`.

### 8c. Update `.claude/review-state/<pr>.yml`

`references/finding-state-schema.md` is the single source of truth for what Phase 4 writes — the full entry shape, which fields are required, and every status transition. Follow its "Phase 4 — write back" section; do NOT reconstruct the entry shape from this file. An entry written without `file`, `enclosing_symbol`, and `rule_class` breaks the next round's ID computation, and one written without the cascade fields silently disables the next round's regression sweep.

The only part specific to posting: `github_thread_id` (from 8b) and `github_comment_id` (REST `databaseId`) are written onto the entry of each finding posted this round.

### 8d. Resolve threads for findings closed this round

Operate on the closed set Step 0c built, **not** on `status: resolved`. That key has no automated writer — see the writer caveat in `references/finding-state-schema.md` — so a step written against it alone never fires, and every thread this skill ever opened stays open regardless of what shipped.

Skip any whose thread already reports `isResolved: true`. `resolveReviewThread` on a resolved thread succeeds and returns the same payload as a real close, so a run that calls it on everything cannot tell afterwards which threads it actually closed — and the author who resolved that thread to satisfy a merge rule gets no signal either way.

For each of the rest, call:

```bash
gh api graphql -f query='
  mutation($threadId: ID!) {
    resolveReviewThread(input: {threadId: $threadId}) { thread { isResolved } }
  }
' -f threadId="<github_thread_id>"
```

Failures here are best-effort — log and continue. Don't block posting on thread-resolution errors.

---

## Quick-reference: posting flow

```
                     /review-pr posts findings
                              │
                              ▼
             Step 0: query reviews for marker (READ-ONLY)
              round number · dedupe · rounds-so-far count
                              │
                              ▼
        Steps 1-3: compose body (findings + coverage ledger),
        compose comments, hunk-validate, then Step 3b drop
        findings that already have threads from earlier rounds
                              │
                              ▼
                 Step 4 — Phase A (REST, PENDING)
              body + line-level comments (COMMENTS_JSON)
                              │
                              ▼
                 Step 5 — Phase B (GraphQL)
           attach file-level threads → ATTACHED_THREADS
                              │
                              ▼
                 Step 6 — Phase C (GraphQL submit)
                              │
                              ▼
                 Step 6b — ASSERT (re-query)
          exists? SUBMITTED? threads == LINE + ATTACHED?
                    │                       │
                 pass│                      │fail
                    ▼                       ▼
                 Step 8                  Step 7
        (cache + state write-back +   (disclosed partial state,
         resolve threads for fixed)    NO write-back)
```

Net effect: each round leaves its own review entry — at most three per PR under the round cap — and no round's body, verdict or coverage ledger is ever overwritten by a later one. Threads accumulate across rounds because earlier ones are never re-posted, and findings that got fixed have their threads resolved in Step 8d.
