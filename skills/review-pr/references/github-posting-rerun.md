
# GitHub posting: re-runs and rolling reviews

Main loads this in Phase 4 only when a prior `/review-pr` review or cache entry exists for this PR. The fresh-review path stays in `${CLAUDE_SKILL_DIR}/references/github-posting.md`, already loaded.

## Step 0: Detect prior `/review-pr` review (rolling-review path)

Every review posted by `/review-pr` includes a hidden marker comment in the body:

```markdown
<!-- review-pr:run sha=<head_sha_at_post_time> round=<round_number> -->
```

Every posting run maps the semantic verdict first, per "Event mapping" in `${CLAUDE_SKILL_DIR}/references/github-posting.md`. Then query for prior tagged reviews:

```bash
PRIOR_REVIEWS_JSON=$(gh api graphql -f query='
  query($owner:String!, $repo:String!, $num:Int!) {
    repository(owner:$owner, name:$repo) {
      pullRequest(number:$num) {
        reviews(first:100) { nodes { id databaseId state submittedAt body } }
      }
    }
  }
' -f owner=<owner> -f repo=<repo> -F num=<num>)

PRIOR_REVIEW_NODE_ID=$(echo "$PRIOR_REVIEWS_JSON" | jq -r '
    [.data.repository.pullRequest.reviews.nodes[]
     | select(.body | test("<!-- review-pr:run"))]
    | sort_by(.submittedAt) | last | .id // empty
  ')
PRIOR_REVIEW_DB_ID=$(echo "$PRIOR_REVIEWS_JSON" | jq -r '
    [.data.repository.pullRequest.reviews.nodes[]
     | select(.body | test("<!-- review-pr:run"))]
    | sort_by(.submittedAt) | last | .databaseId // empty
  ')
PRIOR_REVIEW_STATE=$(echo "$PRIOR_REVIEWS_JSON" | jq -r '
    [.data.repository.pullRequest.reviews.nodes[]
     | select(.body | test("<!-- review-pr:run"))]
    | sort_by(.submittedAt) | last | .state // empty
  ')
```

Before selecting a branch, derive `CURRENT_THREADED_FINDING_IDS` from every surviving finding with a file reference; body-fallback findings are excluded because they cannot own threads. A prior review is thread-complete only when all of these are true:

- the validated current cache records `publication_evidence.publication_mode: threaded`;
- `last_posted_review_node_id` and `last_posted_review_id` equal the candidate prior review;
- when `IS_SELF_REVIEW=true`, the cache's `last_posted_verdict` equals the current semantic verdict;
- every ID in `CURRENT_THREADED_FINDING_IDS` has exactly one `posted_comments` entry with non-empty `github_thread_id`, `review_node_id == PRIOR_REVIEW_NODE_ID`, and `review_database_id == PRIOR_REVIEW_DB_ID`.

Treat missing ownership fields, multiple matches, an unvalidated cache contract, a self-review semantic-verdict mismatch, or a monolithic publication as not thread-complete. Query each cached thread ID and require it to belong to the candidate review before reuse; any absent, mismatched, or inconclusive thread makes the current run a fresh review.

**Branches**:

- **No prior tagged review** → fall through to Step 4 (Phase A: create new pending review).
- **Prior tagged review found, submittedAt is within 30 days, its state matches the required GitHub state, AND it is thread-complete** → ROLLING-REVIEW path. Skip Steps 4-6. Use Step 4-rolling only to update the body; no new thread is needed.
- **Prior self-review has a different semantic verdict** → create a fresh pending review through Step 4. Both verdicts have GitHub state `COMMENTED`, so state equality alone cannot make a reversal safe to roll onto the old threads.
- **Prior tagged review found but any current file-referenced finding lacks a thread owned by that review** → create a fresh pending review through Step 4 with the complete current finding set. This covers both line-level and file-level additions; submitted reviews cannot accept new pending-review threads.
- **Prior tagged review found but its state differs from the required GitHub state** → create a fresh review through Step 4. Updating a submitted review body cannot change its state among `APPROVED`, `CHANGES_REQUESTED`, and `COMMENTED`.
- **Prior tagged review found BUT submittedAt > 30 days ago** → treat as legacy, fall through to Step 4 (new review). Don't try to edit reviews older than a month. They likely belong to a different commit history.

The state and ownership checks keep body-only re-reviews compact without dropping new findings or attempting to attach them to a submitted review.

---

## Step 0b: Verdict-body sync check (re-runs)

If `last_posted_review_id` exists in cache, map the last-posted body verdict through the current self-review status before comparing it with GitHub state:

```bash
LAST_POSTED_REVIEW_ID=$(jq -r '.last_posted_review_id // empty' "$CACHE_FILE")
if [ -n "$LAST_POSTED_REVIEW_ID" ]; then
  LAST_POSTED_STATE=$(gh api "repos/<owner>/<repo>/pulls/<num>/reviews/$LAST_POSTED_REVIEW_ID" --jq .state)
  LAST_POSTED_BODY_VERDICT=$(
    gh api "repos/<owner>/<repo>/pulls/<num>/reviews/$LAST_POSTED_REVIEW_ID" --jq .body |
      awk '/^## PR Review: #[0-9]+$/ { if (getline > 0 && (($1 == "✅" && $2 == "approve") || ($1 == "❌" && $2 == "request-changes")) && $3 == "|") print $2; exit }'
  )
  case "$LAST_POSTED_BODY_VERDICT" in
    approve) LAST_POSTED_BODY_REQUIRED_STATE=APPROVED ;;
    request-changes) LAST_POSTED_BODY_REQUIRED_STATE=CHANGES_REQUESTED ;;
    *) LAST_POSTED_BODY_REQUIRED_STATE=UNKNOWN ;;
  esac
  if [ "$IS_SELF_REVIEW" = "true" ] && [ "$LAST_POSTED_BODY_REQUIRED_STATE" != "UNKNOWN" ]; then
    LAST_POSTED_BODY_REQUIRED_STATE=COMMENTED
  fi
fi
```

If `LAST_POSTED_BODY_REQUIRED_STATE` differs from `LAST_POSTED_STATE`:

> **Previous review's body verdict (`<body>`) implies `<expected-state>`, but GitHub reports `<state>`.** The current run will create a fresh review when the required state differs; it will not preserve a mismatched rolling review.

---

## Step 0c: Re-review thread resolution (before posting)

If this is a re-review AND `posted_comments` cache exists:

1. **Identify resolved findings**: compare current findings against `posted_comments` via dedupe key. A cached finding NOT in current findings AND whose `id` is now `status: resolved` in `PRIOR_STATE` is "resolved this round."

   Immediately before the first `resolveReviewThread` mutation in this batch, invoke `preflight-mutations`. Pass the exact PR URL and current head SHA, the cached review and identified thread IDs to resolve, each finding's prior and current status, the complete surviving finding set, and the originating `/review-pr` request as the authorization source. Apply its result contract before continuing.

2. **Resolve their threads** on GitHub. Immediately before each mutation, refresh the PR head and query the exact thread ID. If `isResolved: true`, record the thread as resolved from that authoritative read-back, skip the mutation, retire the current card, and preflight the remaining items without this thread before the next write. Otherwise compare the head, `isResolved`, and complete comment-ID set with the ready card. If any guard changed, re-run `preflight-mutations` for the pending remainder before writing:

   ```bash
   gh api graphql -f query='
     mutation($threadId: ID!) {
       resolveReviewThread(input: {threadId: $threadId}) {
         thread { isResolved }
       }
     }
   ' -f threadId="<thread_id>"
   ```

3. **Reconcile every result** by querying that exact thread ID after the mutation, including when the mutation command failed or returned an ambiguous response. Mark the finding resolved only when the authoritative query returns `isResolved: true`. Record an authoritative `false` as `confirmed-open`; record a failed or inconclusive query as `reconcile-required`, preserve the exact settling query, and do not retry that thread. On either non-resolved result, retire the current card and preflight the remaining items without this unresolved thread before the next write.

4. **Track resolved findings** for the "Resolved since last review" line in the summary body only after the authoritative `isResolved: true` read-back. Use exact wording: `Resolved since last review: S1 (<file:line> <one-line issue>, round 4 commit <sha>), ...`. NEVER use "deferred", "fixed", or other ambiguous wording. Use `resolved` with the commit SHA.

5. **Preserve the complete payload decision**: `ROLLING_PATH=true` already proves every current file-referenced finding has a thread owned by the reused review, so Steps 4-6 add no comments. A fresh review posts the complete surviving finding set even when older reviews or cache entries contain matching IDs.

6. **Continue the batch** only under the replacement `ready` card required after a non-resolved outcome. Carry `confirmed-open` and `reconcile-required` outcomes into the posting ledger and terminal report; neither may appear in the resolved summary line or any dependent publication state. Never execute later writes under a retired card.

---

## Step 4-rolling: Update existing review's body (GraphQL)

When Step 0 found a recent prior `/review-pr` review whose state matches the required GitHub state and proved it owns every current thread:

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

After every rolling update result, fetch the prior review authoritatively by `PRIOR_REVIEW_NODE_ID`. Only an exact complete-body match with the frozen new summary records the update landed, sets `ATTACHED_THREADS=0` and `ROLLING_PATH=true`, and proceeds directly to Step 8. Step 0 already proved that no new thread is needed, and existing threads on that review remain attached.

If the complete body still equals the guarded old body, set `ROLLING_PATH=false` and `FRESH_REVIEW_FALLBACK=true`; only that confirmed-not-landed state permits a fresh review. Any other body, missing target, or inconclusive read-back remains `reconcile-required` and blocks posting.

For `FRESH_REVIEW_FALLBACK=true`, refresh the PR and review guards and treat the fallback as a new batch: invoke `preflight-mutations` with the failed update result, confirmed read-back, and exact frozen fresh-review actions, then run Step 4. Its exact read-back must overwrite `REVIEW_NODE_ID` and `REVIEW_DB_ID` with the newly created IDs before Phase B. Never create a fallback review from the mutation response alone.

---

### 8d. Resolve threads for findings now in `status: resolved`

For each finding transitioning to `resolved` this round (a fix shipped between rounds and the state file records it; see the writer caveat in `${CLAUDE_SKILL_DIR}/references/finding-state-phase4.md`; that transition is currently made by hand), first refresh the current PR head, review ID/state/body, and every target thread's exact `isResolved` value and complete comment-ID set. Invoke `preflight-mutations` immediately before this resolution batch with those current guards, exact thread IDs, prior/current finding states, and the posting authorization. This is a fresh card: Steps 4-6 changed publication and review state, so the posting card is stale.

Immediately before each resolution write, refresh the PR head and thread. If `isResolved: true`, record the thread as resolved from that authoritative read-back, skip the mutation, retire the current card, and preflight the remaining items without this thread before the next write. Otherwise compare the current guards with the fresh card and re-run preflight for the pending remainder when a guard changed. Then call:

```bash
gh api graphql -f query='
  mutation($threadId: ID!) {
    resolveReviewThread(input: {threadId: $threadId}) { thread { isResolved } }
  }
' -f threadId="<github_thread_id>"
```

After every mutation attempt, query the exact thread ID. Record `resolved` only when the authoritative result has `isResolved: true`; record an authoritative `false` as `confirmed-open`, and a failed or inconclusive query as `reconcile-required` with the exact settling query. Do not retry an indeterminate thread. On either non-resolved result, retire the current card and preflight the remaining items without this unresolved thread before the next write. Report every non-resolved outcome and exclude it from claims that GitHub resolution completed; never execute later writes under a retired card.

