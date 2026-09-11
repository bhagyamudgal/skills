# GitHub posting flow (Phase 4): REST + GraphQL hybrid

Main loads this in Phase 4 for every completed review. It owns the fresh-review path: summary body, per-finding comments, hunk validation, the three posting phases, and the write-back. Re-runs load `${CLAUDE_SKILL_DIR}/references/github-posting-rerun.md` when a prior `/review-pr` review or cache entry exists; posting failures load `${CLAUDE_SKILL_DIR}/references/github-posting-recovery.md`.

---

## Event mapping

Before posting, map the semantic verdict to its normal event and required GitHub state, then override both for a self-review:

```bash
case "$verdict" in
  approve) REVIEW_EVENT=APPROVE; REQUIRED_REVIEW_STATE=APPROVED ;;
  request-changes) REVIEW_EVENT=REQUEST_CHANGES; REQUIRED_REVIEW_STATE=CHANGES_REQUESTED ;;
  *) echo "Unsupported review verdict: $verdict" >&2; exit 1 ;;
esac

if [ "$IS_SELF_REVIEW" = "true" ]; then
  REVIEW_EVENT=COMMENT
  REQUIRED_REVIEW_STATE=COMMENTED
fi

case "$REVIEW_EVENT" in
  APPROVE) REVIEW_FLAG=--approve ;;
  REQUEST_CHANGES) REVIEW_FLAG=--request-changes ;;
  COMMENT) REVIEW_FLAG=--comment ;;
esac
```

---

## Why two APIs (READ BEFORE EDITING)

**DO NOT regress this to a single REST call with `subject_type: "file"` comments.** That shape is rejected by GitHub:

- **Line-level review comments** (`{path, line, side: "RIGHT"}`): Supported by REST `POST /pulls/:n/reviews` AND by GraphQL `addPullRequestReviewThread`.
- **File-level review comments** (no line anchor): Supported ONLY by GraphQL `addPullRequestReviewThread` with `subjectType: FILE`. The REST endpoint uses `DraftPullRequestReviewComment` which has no `subjectType` field. Passing `subject_type: "file"` returns `422 Unprocessable Entity`. This was the bug that silently collapsed past runs to a monolithic body and lost every resolvable thread.

The hybrid flow:
1. **Phase A with REST**. Create PENDING review with line-level comments.
2. **Phase B with GraphQL**. Attach file-level threads.
3. **Phase C with GraphQL**. Submit with the verdict event.

When a prior `/review-pr` review exists on the PR, the rolling path in `${CLAUDE_SKILL_DIR}/references/github-posting-rerun.md` may replace Phase A only for a body-only update whose complete current thread set already belongs to that submitted review.

---

## Step 1: Compose the summary body

Every field you compose for this body posts verbatim, and none carries an em or en dash. Text quoted from the issue or the diff stays as you found it, and the `·` separators are structure rather than prose.

Build a lean summary body (NO "Filtered out" section, internal only). **Always** include the marker comment so future runs can detect this review:

```markdown
<!-- review-pr:run sha=<head_sha> round=<round_number> -->
## PR Review: #<number>
<verdict-emoji> <verdict> | <severity-count-badges>
**Senior engineer approval**: <emoji> <Yes | No>, <one-sentence reason>

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

When there are zero findings, replace the findings table and details line with `### Findings\nNo findings.` The body posts with `APPROVE` for another author's PR or `COMMENT` for a self-review.

**Severity count badges**: `🔴 <N> Critical · 🟠 <M> Serious · 🟡 <K> Moderate · 🔵 <J> Minor`. Only include levels that have findings.

**Finding numbering**: assign sequential IDs by severity: `C1, C2…` Critical, `S1, S2…` Serious, `M1, M2…` Moderate, `m1, m2…` Minor. Use these IDs consistently in the summary table and review comments. **Note**: per-round visible labels (M3, S1, etc.) do NOT have to match across rounds. Internal stability comes from the `findings[].id` hash in `.claude/review-state/<pr>.yml` (see `references/finding-state-schema.md`).

**Comment routing, three tiers**:

- **Line-level thread** (REST, Phase A): finding has a valid `file:line` where the line exists on the post-image side of the diff → attach with `{path, line, side: "RIGHT", body}`.
- **File-level thread** (GraphQL, Phase B): finding has a file reference but no valid diff line (file/module-scope, schema overlap, line not in diff) → attach via `addPullRequestReviewThread` with `subjectType: FILE`.
- **Body fallback** (rare): finding has NO file reference at all → use `*(general)*` in the summary table and append the full detail to the body under `### Additional findings`.

All three tiers create resolvable, replyable GitHub threads. Body fallback is the only acceptable reason for a finding to lack its own thread. Never use it to work around an API error (Step 7 in `${CLAUDE_SKILL_DIR}/references/github-posting-recovery.md` covers that).

**Re-review "Resolved since last review" line**: replace the prior "Fixed" wording with explicit `resolved`. After the table:

```markdown
**Resolved since last review**: S1 (`auth.ts:47` missing null check, round 4 commit `abc1234`), S4 (`db.ts:123` N+1 query, round 5 commit `def5678`) *(threads resolved)*
```

Every finding status is exactly one of `active`, `resolved` (with commit SHA), `dismissed` (with reason), `wontfix` (with reason), or `regression`: the enum in `references/finding-state-schema.md`. "Deferred" is not one of them: it leaves the reader unable to tell a shipped fix from an open one.

---

## Step 2: Compose review comments (per finding)

Each finding with a valid file reference becomes a review comment. Format as self-contained markdown:

```markdown
<severity-emoji> **<Severity>** · <Category>

**<Issue one-sentence>**

<2-3 sentence explanation>

**Why it matters**: <one sentence>

**Suggested fix**: <one sentence, actionable>

**Inverse risk**: <the failure mode this fix trades INTO if implemented literally, or "none, pure addition">

**Class-sites**: <A>/<N> (affected sites over sites searched)
```

Severity emojis: 🔴 Critical, 🟠 Serious, 🟡 Moderate, 🔵 Minor.

**Inverse risk and Class-sites are not decoration.** They are the two cascade fields Phase 3
steps 4.56 and 4.55 derived, and `/fix-pr-review` seeds its own inverse-risk check and class
sweep straight off these two lines instead of re-deriving them. Emit both on every finding
that proposes a code change. `none, pure addition` is a valid `Inverse risk`, an omitted
line is not.

**Comment payload shape**:

- **Line-level (REST, Phase A)**: `{"path": "<file>", "line": <post-image>, "side": "RIGHT", "body": "<markdown>"}`. Goes into the `comments` array of the REST review creation call.
- **File-level (GraphQL, Phase B)**: `path: "<file>"`, `subjectType: FILE`, `body: "<markdown>"`, `pullRequestReviewId: <node_id from Phase A>`. GitHub doesn't anchor code for file-level threads. Include a brief code reference in the body (e.g., "near the `<symbol>` definition").

---

## Step 3: Pre-posting hunk validation

Before Phase A (or rolling-review path), fetch hunks once and verify each line-level comment's `(path, line)` is on the post-image side. Demote mismatches to file-level (Phase B).

```bash
gh api "repos/<owner>/<repo>/pulls/<number>/files" --paginate \
  --jq '.[] | {filename, patch}'
```

**Output format**: `--paginate` with `--jq` emits NDJSON (one `{filename, patch}` per line across pages), NOT a JSON array. Process line-by-line; do NOT pipe to another `jq '.[]'` expecting an array. Fails on page 2.

Parse each `patch`: each `@@ -<oldStart>,<oldLen> +<newStart>,<newLen> @@` header starts a new hunk. Within the hunk, `+` lines and space-prefixed context lines advance the post-image counter (start at `newStart`); `-` lines do not. A line is "in the diff" only if it matches a counter value on some hunk for that file.

For each line-level finding: is `line` present on `path`'s post-image counter? If yes → keep. If no → demote to file-level + log the demotion.

With routing now exact, render the complete summary body, canonical ordered line-comment set `(path, line, side, body)`, canonical ordered file-level set `(finding ID, path, body)`, and monolithic recovery body to files and freeze their SHA-256 digests. The file-level set is the posting ledger: Phase B posts and reconciles each exact frozen entry rather than rebuilding a path/body from live findings. Refresh the PR URL, base and current head SHA, and any prior review's ID, state, body, author, and submitted time. Invoke `preflight-mutations` immediately before Step 4 or Step 4-rolling (in `${CLAUDE_SKILL_DIR}/references/github-posting-rerun.md`) performs the posting batch's first mutation. Pass those target guards, all frozen payload paths and digests, every surviving finding ID, the semantic verdict, `IS_SELF_REVIEW`, `REVIEW_EVENT`, line/file targets, prior review ID or new-review action, subsequent add/submit/resolve targets, and the originating `/review-pr` request as the authorization source. Apply its result contract before continuing.

---

## Step 4, Phase A: create PENDING review with line-level comments (REST)

**Skip this step only if rolling-review path is active (Step 0 in `${CLAUDE_SKILL_DIR}/references/github-posting-rerun.md` proved a recent prior review has the required GitHub state and owns every current thread).** Use Step 4-rolling there instead.

Pass ALL fields in a single `--input` JSON. **Omit the `event` field** so the review stays PENDING while Phase B attaches file-level threads:

**Note**: call Phase A even with zero line-level findings. Pass `comments: []`. The REST endpoint accepts an empty array with a body-only PENDING review; this is the only way to get the `pullRequestReviewId` Phase B's mutations need.

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
  # → reconcile the create before Step 7 in `${CLAUDE_SKILL_DIR}/references/github-posting-recovery.md`
fi

ATTACHED_THREADS=0
```

Capture BOTH IDs: `node_id` (GraphQL) for Phases B/C, `id` (integer) for caching. Read the review and its review comments back by ID and require its author, `PENDING` state, complete summary body, head SHA, and complete canonical line-comment set to match the frozen create before Phase B.

A timeout, interrupted response, or missing ID is `reconcile-required`, not proof that creation failed. Query the PR's reviews authoritatively, fetch every current-author `PENDING` review and all of its review comments, then compare author, exact frozen summary body, exact head SHA, and complete canonical line-comment set. One exact match restores both review IDs and continues Phase B. One candidate that matches the head and summary but has a different line-comment set preserves its IDs and enters Step 7 in `${CLAUDE_SKILL_DIR}/references/github-posting-recovery.md`'s pending-review branch. If any other current-author pending review exists, preserve all candidate IDs and block for reconciliation; a nonmatching body or head is still external state, not evidence that no pending review exists. Set `NO_PENDING_REVIEW=true` only after a complete query proves there are zero current-author pending reviews on the PR. Multiple exact or partial candidates, or an inconclusive query, block the run. Never create or fall back to another review while any pending create remains unresolved.

---

## Step 5, Phase B: attach file-level threads to the fresh pending review (GraphQL)

**Skip if `ROLLING_PATH=true`**: rolling eligibility proves there are no new threads to attach.

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

# gh api graphql exits 0 even when GraphQL returns errors. Check both .errors AND thread.id
if echo "$THREAD_RESP" | jq -e '.errors' >/dev/null \
   || [ -z "$THREAD_NODE_ID" ] || [ -z "$THREAD_COMMENT_ID" ]; then
  echo "Phase B failed on thread $((ATTACHED_THREADS + 1)). Response: $THREAD_RESP" >&2
  # → reconcile the thread before Step 7 in `${CLAUDE_SKILL_DIR}/references/github-posting-recovery.md`
else
  ATTACHED_THREADS=$((ATTACHED_THREADS + 1))
fi
```

Loop **sequentially, not in parallel**: thread order in the submitted review follows call order. Capture each returned `thread.id` and `comments.nodes[0].databaseId` for caching.

An ambiguous thread result stops the sequential loop and requires an authoritative query of that review's threads for the exact review ID, path, and frozen comment body. Reconcile the result back to the one frozen `(finding ID, path, body)` ledger entry; do not substitute another finding merely because its path matches. One exact match captures its IDs against that finding ID, increments `ATTACHED_THREADS`, and resumes the loop. Confirmed absence permits Step 7 in `${CLAUDE_SKILL_DIR}/references/github-posting-recovery.md` without incrementing; multiple matches or inconclusive state blocks posting. Never retry the thread or enter recovery while its placement is unresolved.

## Step 6, Phase C: submit the review (GraphQL)

**Skip if `ROLLING_PATH=true`**: the prior review is already submitted; rolling onto it doesn't re-submit.

```bash
SUBMIT_RESP=$(gh api graphql -f query='
  mutation($reviewId: ID!, $event: PullRequestReviewEvent!) {
    submitPullRequestReview(input: { pullRequestReviewId: $reviewId, event: $event }) {
      pullRequestReview { id databaseId state submittedAt }
    }
  }
' -f reviewId="$REVIEW_NODE_ID" -f event="$REVIEW_EVENT")

SUBMIT_RESPONSE_ID=$(echo "$SUBMIT_RESP" | jq -r '.data.submitPullRequestReview.pullRequestReview.databaseId // empty')
SUBMIT_RESPONSE_STATE=$(echo "$SUBMIT_RESP" | jq -r '.data.submitPullRequestReview.pullRequestReview.state // empty')
SUBMIT_RESPONSE_HAS_ERRORS=$(echo "$SUBMIT_RESP" | jq -r 'has("errors")')

SUBMIT_READBACK=$(gh api graphql -f query='
  query($reviewId: ID!) {
    node(id: $reviewId) {
      ... on PullRequestReview { id databaseId state submittedAt }
    }
  }
' -f reviewId="$REVIEW_NODE_ID")

if echo "$SUBMIT_READBACK" | jq -e '.errors' >/dev/null \
   || [ "$(echo "$SUBMIT_READBACK" | jq -r '.data.node.id // empty')" != "$REVIEW_NODE_ID" ] \
   || [ "$(echo "$SUBMIT_READBACK" | jq -r '.data.node.databaseId // empty')" != "$REVIEW_DB_ID" ] \
   || [ "$(echo "$SUBMIT_READBACK" | jq -r '.data.node.state // empty')" != "$REQUIRED_REVIEW_STATE" ] \
   || [ "$(echo "$SUBMIT_READBACK" | jq -r '.data.node.submittedAt // empty')" = "" ] \
   || { [ -n "$SUBMIT_RESPONSE_ID" ] && [ "$SUBMIT_RESPONSE_ID" != "$REVIEW_DB_ID" ]; } \
   || { [ -n "$SUBMIT_RESPONSE_STATE" ] && [ "$SUBMIT_RESPONSE_STATE" != "$REQUIRED_REVIEW_STATE" ]; }; then
  echo "Phase C read-back did not confirm $REQUIRED_REVIEW_STATE. Response: $SUBMIT_READBACK" >&2
  # → reconcile review state before Step 7 in `${CLAUDE_SKILL_DIR}/references/github-posting-recovery.md`
elif [ "$SUBMIT_RESPONSE_HAS_ERRORS" = "true" ] \
   || [ -z "$SUBMIT_RESPONSE_ID" ] \
   || [ -z "$SUBMIT_RESPONSE_STATE" ]; then
  echo "Phase C response was ambiguous; authoritative read-back confirmed $REQUIRED_REVIEW_STATE." >&2
fi
```

**Event mapping**: another author's `approve` verdict uses `APPROVE`, and `request-changes` uses `REQUEST_CHANGES`. A self-review uses `COMMENT` for either semantic verdict because GitHub forbids authors from approving their own pull requests.

A Phase C failure is the worst case: pending review has all threads but is never submitted, lingering as a draft.

Phase C succeeds when the authoritative read-back equals `REQUIRED_REVIEW_STATE` and no explicit response field contradicts it. A missing or error response is settled by that read-back. An exact `PENDING` read-back permits Step 7 in `${CLAUDE_SKILL_DIR}/references/github-posting-recovery.md`; another state, a response/read-back contradiction, or an inconclusive read-back is `reconcile-required` and blocks recovery. Do not submit again.

---

## Quick-reference: rolling-review decision tree

Step 0 and Step 4-rolling live in `${CLAUDE_SKILL_DIR}/references/github-posting-rerun.md`; the rest is here.

```
                    Step 0: rolling eligibility
                                  │
                  ┌───────────────┴───────────────┐
                  │                               │
                  ▼                               ▼
     same state + threaded +             any failed condition
      owns every current thread          or any new finding
                  │                               │
                  ▼                               ▼
          Step 4-rolling                       Step 4
         update body only              create pending review with
                  │                    all current line comments
                  │                               │
                  │                               ▼
                  │                             Step 5
                  │                    attach all file threads
                  │                               │
                  │                               ▼
                  │                             Step 6
                  │                        submit verdict
                  └───────────────┬───────────────┘
                                  │
                                  ▼
                               Step 8
```

Net effect: only a thread-complete body update reuses a submitted review. A new or unowned finding, monolithic predecessor, required-state change, self-review semantic-verdict reversal, legacy cache, or aged review creates a fresh pending review with every current finding, while resolved prior threads remain collapsed.

---

## Step 8: Cache + state write-back

After successful Phase C or Step 4-rolling (rerun file):

### 8a. Update `posted_comments` in `$CACHE_FILE`

Merge into existing cache (do NOT overwrite). Add/update:

- `contract_version`: `REVIEW_CACHE_CONTRACT_VERSION`; a successful write upgrades the complete cache atomically.
- `last_posted_review_id`: integer `databaseId` from Phase C, `PRIOR_REVIEW_DB_ID` only when `ROLLING_PATH=true`, or the new `REVIEW_DB_ID` when `FRESH_REVIEW_FALLBACK=true`. Never cache the stale prior ID after Step 4 creates a fallback review.
- `last_posted_review_node_id`: GraphQL node ID
- `last_posted_verdict`: verdict string
- `last_posted_at`: ISO timestamp
- `publication_evidence`: authoritative review facts with `publication_mode: threaded` for successful Phase C or rolling publication.
- `posted_comments`: array of comment entries (preserve existing entries; merge new ones)

For each newly-posted comment, construct `finding_key` using the dedupe key format (line-level: `(file, line, symbol)`, file-level: `(file, file-level:<category>, symbol)`) and record `review_node_id: REVIEW_NODE_ID` plus `review_database_id: REVIEW_DB_ID`. These ownership fields decide whether a later submitted review is thread-complete; legacy or cross-review entries never qualify.

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

`references/finding-state-phase4.md` is the single source of truth for what Phase 4 writes: the full entry shape, which fields are required, and every status transition. Follow its "Phase 4: write back" section; do NOT reconstruct the entry shape from this file. An entry written without `file`, `enclosing_symbol`, and `rule_class` breaks the next round's ID computation, and one written without the cascade fields silently disables the next round's regression sweep.

The only part specific to posting: `github_thread_id` (from 8b) and `github_comment_id` (REST `databaseId`) are written onto the entry of each finding posted this round.

