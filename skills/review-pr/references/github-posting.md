# GitHub posting flow (Phase 4) — REST + GraphQL hybrid + rolling-review

Loaded by SKILL.md when posting findings to a real PR. SKILL.md keeps a ~30-line dispatch step that delegates to this reference.

This file owns:
- Composing summary body + per-finding review comments
- Pre-posting hunk validation (line vs file-level routing)
- Three-phase REST/GraphQL posting (PENDING review → file-level threads → submit)
- **Rolling-review fix**: detect prior `/review-pr` review on the PR via marker comment, edit its body in place instead of posting a duplicate.
- Pre-posting preflight on re-runs: verdict-body sync check, thread resolution for findings now `resolved`
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

When a prior `/review-pr` review exists on the PR, **the Rolling-review path replaces Phase A** (see Step 0 below).

---

## Step 0 — Detect prior `/review-pr` review (rolling-review path)

Every review posted by `/review-pr` includes a hidden marker comment in the body:

```markdown
<!-- review-pr:run sha=<head_sha_at_post_time> round=<round_number> -->
```

Before posting a new review, query for prior tagged reviews:

```bash
PRIOR_REVIEW_NODE_ID=$(gh api graphql -f query='
  query($owner:String!, $repo:String!, $num:Int!) {
    repository(owner:$owner, name:$repo) {
      pullRequest(number:$num) {
        reviews(first:100) { nodes { id databaseId state submittedAt body } }
      }
    }
  }
' -f owner=<owner> -f repo=<repo> -F num=<num> \
  | jq -r '
      [.data.repository.pullRequest.reviews.nodes[]
       | select(.body | test("<!-- review-pr:run"))]
      | sort_by(.submittedAt) | last | .id // empty
    ')

PRIOR_REVIEW_DB_ID=$(... same query, take .databaseId ...)
```

**Branches**:

- **No prior tagged review** → fall through to Step 4 (Phase A: create new pending review).
- **Prior tagged review found AND submittedAt is within 30 days** → ROLLING-REVIEW path. Skip Step 4. Use Step 4-rolling instead: edit the body via `updatePullRequestReviewBody` GraphQL mutation, then proceed to Step 5 (attach NEW file-level threads only — see Step 5-rolling for the dedup against `posted_comments`), then skip Step 6 (no submit needed — the prior review is already submitted; we just rolled new threads onto the same review).
- **Prior tagged review found BUT submittedAt > 30 days ago** → treat as legacy, fall through to Step 4 (new review). Don't try to edit reviews older than a month — they likely belong to a different commit history.

**Rationale**: instead of N separate review entries piling up on a multi-round PR, you get ONE rolling review whose body is the latest summary and whose threads accumulate as new findings appear (resolved findings get their threads resolved via `resolveReviewThread`, see Step 7-rolling).

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

> **Previous review's body verdict (`<body>`) does NOT match GitHub state (`<state>`).** Likely cause: self-review coerced to `comment`, or manual edit in GitHub UI. The current run's output will not re-post over the previous review — add a NEW review via "Post now" if you want to update. (Rolling-review path will edit the body in place — see Step 0 above.)

---

## Step 0c — Re-review thread resolution (before posting)

If this is a re-review AND `posted_comments` cache exists:

1. **Identify resolved findings**: compare current findings against `posted_comments` via dedupe key. A cached finding NOT in current findings AND whose `id` is now `status: resolved` in `PRIOR_STATE` is "resolved this round."

   Immediately before the first `resolveReviewThread` mutation in this batch, invoke `preflight-mutations`. Pass the exact PR URL and current head SHA, the cached review and identified thread IDs to resolve, each finding's prior and current status, and the user's approved selected-finding set and posting choice. Apply its result contract before continuing.

2. **Resolve their threads** on GitHub:

   ```bash
   gh api graphql -f query='
     mutation($threadId: ID!) {
       resolveReviewThread(input: {threadId: $threadId}) {
         thread { isResolved }
       }
     }
   ' -f threadId="<thread_id>"
   ```

3. **Track resolved findings** for the "Resolved since last review" line in the summary body. Use exact wording: `Resolved since last review: S1 (<file:line> <one-line issue>, round 4 commit <sha>), ...`. NEVER use "deferred", "fixed", or other ambiguous wording — use `resolved` with the commit SHA.

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

### Findings
| # | Sev | File | Issue |
|---|-----|------|-------|
| S1 | 🟠 | `<path:line>` | <one-line issue> |
| M1 | 🟡 | `<path>` | <one-line issue (file-level)> |
| m1 | 🔵 | *(general)* | <one-line issue (body-fallback)> |

*Details in review comments below.*  <!-- omit if ALL findings are body-fallback -->
```

**Severity count badges**: `🔴 <N> Critical · 🟠 <M> Serious · 🟡 <K> Moderate · 🔵 <J> Minor` — only include levels that have findings.

**Finding numbering**: assign sequential IDs by severity: `C1, C2…` Critical, `S1, S2…` Serious, `M1, M2…` Moderate, `m1, m2…` Minor. Use these IDs consistently in the summary table and review comments. **Note**: per-round visible labels (M3, S1, etc.) do NOT have to match across rounds — internal stability comes from the `findings[].id` hash in `.claude/review-state/<pr>.yml` (see `references/finding-state-schema.md`).

**Comment routing — three tiers**:

- **Line-level thread** (REST, Phase A): finding has a valid `file:line` where the line exists on the post-image side of the diff → attach with `{path, line, side: "RIGHT", body}`.
- **File-level thread** (GraphQL, Phase B): finding has a file reference but no valid diff line (file/module-scope, schema overlap, line not in diff) → attach via `addPullRequestReviewThread` with `subjectType: FILE`.
- **Body fallback** (rare): finding has NO file reference at all → use `*(general)*` in the summary table and append the full detail to the body under `### Additional findings`.

All three tiers create resolvable, replyable GitHub threads. Body fallback is the only acceptable reason for a finding to lack its own thread — never use it to work around an API error (Step 7 covers that).

**Re-review "Resolved since last review" line**: replace the prior "Fixed" wording with explicit `resolved`. After the table:

```markdown
**Resolved since last review**: S1 (`auth.ts:47` missing null check, round 4 commit `abc1234`), S4 (`db.ts:123` N+1 query, round 5 commit `def5678`) *(threads resolved)*
```

Every finding status is exactly one of `active`, `resolved` (with commit SHA), `dismissed` (with reason), `wontfix` (with reason), or `regression` — the enum in `references/finding-state-schema.md`. "Deferred" is not one of them: it leaves the reader unable to tell a shipped fix from an open one.

---

## Step 2 — Compose review comments (per finding)

Each finding with a valid file reference becomes a review comment. Format as self-contained markdown:

```markdown
<severity-emoji> **<Severity>** · <Category>

**<Issue one-sentence>**

<2-3 sentence explanation>

**Why it matters**: <one sentence>

**Suggested fix**: <one sentence, actionable>

**Inverse risk**: <the failure mode this fix trades INTO if implemented literally, or "none — pure addition">

**Class-sites**: <A>/<N> — affected sites over sites searched
```

Severity emojis: 🔴 Critical, 🟠 Serious, 🟡 Moderate, 🔵 Minor.

**Inverse risk and Class-sites are not decoration.** They are the two cascade fields Phase 3
steps 4.56 and 4.55 derived, and `/fix-pr-review` seeds its own inverse-risk check and class
sweep straight off these two lines instead of re-deriving them. Emit both on every finding
that proposes a code change — `none — pure addition` is a valid `Inverse risk`, an omitted
line is not.

**Comment payload shape**:

- **Line-level (REST, Phase A)**: `{"path": "<file>", "line": <post-image>, "side": "RIGHT", "body": "<markdown>"}` — goes into the `comments` array of the REST review creation call.
- **File-level (GraphQL, Phase B)**: `path: "<file>"`, `subjectType: FILE`, `body: "<markdown>"`, `pullRequestReviewId: <node_id from Phase A or rolling>`. GitHub doesn't anchor code for file-level threads — include a brief code reference in the body (e.g., "near the `<symbol>` definition").

---

## Step 3 — Pre-posting hunk validation

Before Phase A (or rolling-review path), fetch hunks once and verify each line-level comment's `(path, line)` is on the post-image side. Demote mismatches to file-level (Phase B).

```bash
gh api "repos/<owner>/<repo>/pulls/<number>/files" --paginate \
  --jq '.[] | {filename, patch}'
```

**Output format**: `--paginate` with `--jq` emits NDJSON (one `{filename, patch}` per line across pages), NOT a JSON array. Process line-by-line; do NOT pipe to another `jq '.[]'` expecting an array — fails on page 2.

Parse each `patch`: each `@@ -<oldStart>,<oldLen> +<newStart>,<newLen> @@` header starts a new hunk. Within the hunk, `+` lines and space-prefixed context lines advance the post-image counter (start at `newStart`); `-` lines do not. A line is "in the diff" only if it matches a counter value on some hunk for that file.

For each line-level finding: is `line` present on `path`'s post-image counter? If yes → keep. If no → demote to file-level + log the demotion.

With routing now exact, render the complete summary body, canonical ordered line-comment set `(path, line, side, body)`, canonical ordered file-level set `(finding ID, path, body)`, and monolithic recovery body to files and freeze their SHA-256 digests. The file-level set is the posting ledger: Phase B posts and reconciles each exact frozen entry rather than rebuilding a path/body from live findings. Refresh the PR URL, base and current head SHA, and any prior review's ID, state, body, author, and submitted time. Invoke `preflight-mutations` immediately before Step 4 or Step 4-rolling performs the posting batch's first mutation. Pass those target guards, all frozen payload paths and digests, selected finding IDs, verdict, line/file targets, prior review ID or new-review action, subsequent add/submit/resolve targets, and the user's `Post now` or post-edit approval. Apply its result contract before continuing.

---

## Step 4 — Phase A: create PENDING review with line-level comments (REST)

**Skip this step if rolling-review path is active (Step 0 found a recent prior review).** Use Step 4-rolling instead.

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
  # → reconcile the create before Step 7
fi

ATTACHED_THREADS=0
```

Capture BOTH IDs: `node_id` (GraphQL) for Phases B/C, `id` (integer) for caching. Read the review and its review comments back by ID and require its author, `PENDING` state, complete summary body, head SHA, and complete canonical line-comment set to match the frozen create before Phase B.

A timeout, interrupted response, or missing ID is `reconcile-required`, not proof that creation failed. Query the PR's reviews authoritatively, fetch every current-author `PENDING` review and all of its review comments, then compare author, exact frozen summary body, exact head SHA, and complete canonical line-comment set. One exact match restores both review IDs and continues Phase B. One candidate that matches the head and summary but has a different line-comment set preserves its IDs and enters Step 7's pending-review branch. If any other current-author pending review exists, preserve all candidate IDs and block for reconciliation; a nonmatching body or head is still external state, not evidence that no pending review exists. Set `NO_PENDING_REVIEW=true` only after a complete query proves there are zero current-author pending reviews on the PR. Multiple exact or partial candidates, or an inconclusive query, block the run. Never create or fall back to another review while any pending create remains unresolved.

---

## Step 4-rolling — Update existing review's body (GraphQL)

When Step 0 found a recent prior `/review-pr` review:

```bash
UPDATE_RESP=$(gh api graphql -f query='
  mutation($id: ID!, $body: String!) {
    updatePullRequestReviewBody(input: { pullRequestReviewId: $id, body: $body }) {
      pullRequestReview { id databaseId state submittedAt }
    }
  }
' -f id="$PRIOR_REVIEW_NODE_ID" -f body="$NEW_SUMMARY_BODY")

if echo "$UPDATE_RESP" | jq -e '.errors' >/dev/null \
   || [ "$(echo "$UPDATE_RESP" | jq -r '.data.updatePullRequestReviewBody.pullRequestReview.id // empty')" = "" ]; then
  echo "updatePullRequestReviewBody returned an ambiguous result: $UPDATE_RESP" >&2
  ROLLING_RECONCILE_REQUIRED=true
else
  REVIEW_NODE_ID="$PRIOR_REVIEW_NODE_ID"
  REVIEW_DB_ID="$PRIOR_REVIEW_DB_ID"
fi
```

After every rolling update result, fetch the prior review authoritatively by `PRIOR_REVIEW_NODE_ID`. Only an exact complete-body match with the frozen new summary records the update landed, sets `ATTACHED_THREADS=0` and `ROLLING_PATH=true`, and proceeds to Phase B. Existing threads on that review remain attached.

If the complete body still equals the guarded old body, set `ROLLING_PATH=false` and `FRESH_REVIEW_FALLBACK=true`; only that confirmed-not-landed state permits a fresh review. Any other body, missing target, or inconclusive read-back remains `reconcile-required` and blocks posting.

For `FRESH_REVIEW_FALLBACK=true`, refresh the PR and review guards and treat the fallback as a new batch: invoke `preflight-mutations` with the failed update result, confirmed read-back, and exact frozen fresh-review actions, then run Step 4. Its exact read-back must overwrite `REVIEW_NODE_ID` and `REVIEW_DB_ID` with the newly created IDs before Phase B. Never create a fallback review from the mutation response alone.

---

## Step 5 — Phase B: attach file-level threads (GraphQL)

For each entry in the frozen canonical file-level set, in order (originals + Step 3 demotions), use that entry's exact finding ID, path, and body:

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

THREAD_NODE_ID=$(echo "$THREAD_RESP" | jq -r '.data.addPullRequestReviewThread.thread.id // empty')
THREAD_COMMENT_ID=$(echo "$THREAD_RESP" | jq -r '.data.addPullRequestReviewThread.thread.comments.nodes[0].databaseId // empty')

# gh api graphql exits 0 even when GraphQL returns errors — check both .errors AND thread.id
if echo "$THREAD_RESP" | jq -e '.errors' >/dev/null \
   || [ -z "$THREAD_NODE_ID" ] || [ -z "$THREAD_COMMENT_ID" ]; then
  echo "Phase B failed on thread $((ATTACHED_THREADS + 1)). Response: $THREAD_RESP" >&2
  # → reconcile the thread before Step 7
else
  ATTACHED_THREADS=$((ATTACHED_THREADS + 1))
fi
```

Loop **sequentially, not in parallel** — thread order in the submitted review follows call order. Capture each returned `thread.id` and `comments.nodes[0].databaseId` for caching.

An ambiguous thread result stops the sequential loop and requires an authoritative query of that review's threads for the exact review ID, path, and frozen comment body. Reconcile the result back to the one frozen `(finding ID, path, body)` ledger entry; do not substitute another finding merely because its path matches. One exact match captures its IDs against that finding ID, increments `ATTACHED_THREADS`, and resumes the loop. Confirmed absence permits Step 7 without incrementing; multiple matches or inconclusive state blocks posting. Never retry the thread or enter recovery while its placement is unresolved.

### Step 5-rolling — Skip already-posted threads

When `ROLLING_PATH=true`, before issuing each `addPullRequestReviewThread`, look up the finding's `id` (per `references/finding-state-schema.md`) in `$CACHE_FILE`'s `posted_comments[]` array (canonical path: `$HOME/.claude/skills/review-pr/cache/<owner>_<repo>_<pr-number>.json`, set in SKILL.md Phase 1). If a prior comment exists with the same dedupe key AND matches the current `id`, skip the mutation — the thread is already on the review.

```bash
# Pseudocode per finding:
existing_thread_id=$(jq -r --arg id "$finding_id" \
  '.posted_comments[] | select(.finding_id == $id) | .github_thread_id // empty' \
  "$CACHE_FILE")
if [ -n "$existing_thread_id" ]; then
  echo "Skipping already-posted thread for finding $finding_id (thread $existing_thread_id)" >&2
  continue
fi
# Otherwise, proceed with addPullRequestReviewThread
```

This is the core dedup that prevents duplicate posting on rolling re-review.

---

## Step 6 — Phase C: submit the review (GraphQL)

**Skip if `ROLLING_PATH=true`** — the prior review is already submitted; rolling onto it doesn't re-submit.

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
  # → reconcile review state before Step 7
fi
```

**Event mapping**: `approve` → `APPROVE`, `comment` → `COMMENT`, `request-changes` → `REQUEST_CHANGES`.

A Phase C failure is the worst case: pending review has all threads but is never submitted, lingering as a draft.

An ambiguous submit result requires authoritative read-back of `REVIEW_NODE_ID`. The intended submitted state records the submit landed; exact `PENDING` state permits Step 7; any other or inconclusive state is `reconcile-required` and blocks recovery. Do not submit again.

---

## Step 7 — Posting failed recovery (NEVER silent)

If Phase A, B, or C fails: **DO NOT silently collapse to a monolithic body.** The prior silent fallback was the root cause of past zero-resolvable-comment runs.

### Rolling or submitted review exists

If authoritative read-back shows the target review is already submitted — including `ROLLING_PATH=true` — do not enter either cleanup branch below. Preserve the submitted review and query its complete body, line comments, and file-level threads. Reconcile every thread against the frozen canonical file-level entries and classify each entry as exactly one of `landed`, `confirmed-absent`, or `ambiguous`; cache exact landed IDs immediately. A body mismatch, multiple matches, or inconclusive query is `reconcile-required` and blocks further mutation.

When one or more entries are `confirmed-absent`, offer only `Attach confirmed-absent threads`, `Abort — preserve submitted review`, or `Show payload & preserve review`. Before attaching, refresh the submitted-review guard and invoke `preflight-mutations` with the exact remaining frozen entries and digests; post them sequentially through Phase B and reconcile each result before advancing. Abort and show-payload leave the submitted review unchanged. Never delete a submitted review, route it through pending cleanup, or replace it with a monolithic review.

### No pending review

When Phase A reconciliation set `NO_PENDING_REVIEW=true`, use a distinct recovery prompt: `Post frozen monolithic review` or `Abort — keep local`. Before a post, refresh the PR guards and invoke `preflight-mutations` with the complete zero-match reconciliation evidence plus the exact frozen monolithic body and digest; then post without calling `cleanup_pending_review`. Reconcile an ambiguous post by exact author, head, verdict, and body before any retry. Abort performs no mutation. This branch ends here.

### Pending review exists

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

Immediately before the chosen recovery's first delete or fallback-post mutation, refresh the PR and pending review. Freeze a canonical pending-review snapshot containing the exact review ID, author, `PENDING` state, head SHA, complete review body, and every attached comment and thread's IDs, path, line, side, and body; digest that snapshot. Invoke `preflight-mutations` with the exact PR and head SHA, the snapshot path and digest, selected recovery action, frozen monolithic body path and digest, and the user's Step 7 choice. Re-fetch and require an exact snapshot match immediately before deletion. Apply the preflight result contract before continuing; a count match is never sufficient.

**Cleanup helper** (used by "Post as monolithic" + "Abort"):

```bash
cleanup_pending_review() {
  local out readback
  out=$(gh api graphql -f query='
    mutation($id: ID!) {
      deletePullRequestReview(input: {pullRequestReviewId: $id}) { clientMutationId }
    }
  ' -f id="$REVIEW_NODE_ID" 2>&1) || true

  readback=$(gh api graphql -f query='
    query($id: ID!) {
      node(id: $id) { ... on PullRequestReview { id state body } }
    }
  ' -f id="$REVIEW_NODE_ID") || return 2

  if echo "$readback" | jq -e '.errors' >/dev/null; then
    echo "Pending review cleanup read-back was inconclusive: $out / $readback" >&2
    return 2
  fi

  if [ "$(echo "$readback" | jq -r '.data.node.id // empty')" != "" ]; then
    echo "Pending review cleanup did not land or changed ambiguously: $out / $readback" >&2
    return 1
  fi
}
```

The cleanup result is authoritative only when the exact pending review node is absent. A surviving node, failed read-back, or changed review remains `reconcile-required`; preserve its IDs and stop without fallback posting.

**On "Post as monolithic"**: require `cleanup_pending_review` to confirm absence, refresh the PR guard, then invoke a new preflight for the exact frozen monolithic body before `gh pr review <url> <verdict-flag> --body-file /tmp/review-pr-<num>-monolithic.md`. Reconcile an ambiguous monolithic post by exact author, head, verdict, and body before any retry.

**On "Abort"**: require authoritative cleanup read-back, then stop. Report `reconcile-required` instead of claiming an abort when cleanup is unresolved.

**On "Show payload"**: print the offending JSON/mutation. Do NOT clean up — user explicitly chose to keep the draft. Print the pending review URL.

---

## Step 8 — Cache + state write-back

After successful Phase C (or rolling Step 5):

### 8a. Update `posted_comments` in `$CACHE_FILE`

Merge into existing cache (do NOT overwrite). Add/update:

- `last_posted_review_id` — integer `databaseId` from Phase C, `PRIOR_REVIEW_DB_ID` only when `ROLLING_PATH=true`, or the new `REVIEW_DB_ID` when `FRESH_REVIEW_FALLBACK=true`. Never cache the stale prior ID after Step 4 creates a fallback review.
- `last_posted_review_node_id` — GraphQL node ID
- `last_posted_verdict` — verdict string
- `last_posted_at` — ISO timestamp
- `posted_comments` — array of comment entries (preserve existing entries; merge new ones)

For each newly-posted comment, construct `finding_key` using the dedupe key format (line-level: `(file, line, symbol)`, file-level: `(file, file-level:<category>, symbol)`).

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

### 8d. Resolve threads for findings now in `status: resolved`

For each finding transitioning to `resolved` this round (a fix shipped between rounds and the state file records it — see the writer caveat in `references/finding-state-schema.md`; that transition is currently made by hand), call:

```bash
gh api graphql -f query='
  mutation($threadId: ID!) {
    resolveReviewThread(input: {threadId: $threadId}) { thread { isResolved } }
  }
' -f threadId="<github_thread_id>"
```

Failures here are best-effort — log and continue. Don't block posting on thread-resolution errors.

---

## Quick-reference: rolling-review decision tree

```
                     /review-pr posts findings
                              │
                              ▼
                   Step 0: query reviews for marker
                              │
            ┌─────────────────┼─────────────────┐
            │                 │                 │
            ▼                 ▼                 ▼
       no prior         prior < 30d         prior > 30d
            │                 │                 │
            ▼                 ▼                 ▼
        Step 4         Step 4-rolling        Step 4
   (create review)   (update body only)  (create new review)
            │                 │                 │
            └─────────────────┴─────────────────┘
                              │
                              ▼
                    Step 5 + 5-rolling
              (attach NEW threads, skip dups)
                              │
            ┌─────────────────┴─────────────────┐
            │                                   │
            ▼                                   ▼
       Step 6 (submit)               (skip if rolling — already submitted)
            │                                   │
            └─────────────────┬─────────────────┘
                              │
                              ▼
                          Step 8
                  (cache + state write-back +
                   resolve threads for fixed)
```

Net effect: PR shows ONE review entry per `/review-pr` user, body always reflects the latest run, threads accumulate non-destructively, resolved findings have collapsed threads.
