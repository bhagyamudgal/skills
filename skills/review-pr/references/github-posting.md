# GitHub posting flow (Phase 4): REST + GraphQL hybrid

Main loads this in Phase 4 for every completed review. It owns the fresh-review path: rendering every body with `scripts/render_review.py`, the three posting phases, and the write-back. Re-runs load `${CLAUDE_SKILL_DIR}/references/github-posting-rerun.md` when a prior `/review-pr` review or cache entry exists; posting failures load `${CLAUDE_SKILL_DIR}/references/github-posting-recovery.md`.

---

## Event mapping

Before posting, map the semantic verdict to its normal event and required GitHub state, then override both for a self-review and for an approval with incomplete coverage. Batch mode sets `INCOMPLETE_COVERAGE` for every PR; a single-PR run sets it to `false`:

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

if [ "${INCOMPLETE_COVERAGE:?}" = "true" ] && [ "$REVIEW_EVENT" = "APPROVE" ]; then
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

Posting a body-only review with an explicit `event` and no `comments` array, or pasting the terminal report as an issue comment, is not a degraded mode of this flow: it leaves zero resolvable threads, no run marker, and nothing the next round can build on. The only legal postings are the fresh A-B-C path below, the rolling path, the blocked-by-open-threads path from Phase 3 step 8, and the recovery-prompted fallback. Anything else ends with the Thread coverage line stating that nothing shipped and why.

The blocked-by-open-threads path is body-only by design, not by degradation: every blocker already owns an unresolved, non-outdated thread, so new threads would only duplicate them. Its body lists every blocker as `path:line` (`path` alone for file-level threads), author, and one-line issue, carries the run marker, and posts `REQUEST_CHANGES` (`COMMENT` for a self-review with a `request-changes` semantic verdict).

---

## Step 1: Render every body with the script

Every body this run posts comes from the renderer, never from hand-written markdown, so the layout is the same whichever model runs the skill. Write one review JSON file from the Phase 3 result and run:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/render_review.py" --example
python3 "${CLAUDE_SKILL_DIR}/scripts/render_review.py" <review.json> --diff <staged diff.full.patch> \
  --out <new render dir> --pr <number> --head-sha <CURRENT_HEAD> --round <CURRENT_ROUND>
```

`--example` prints a valid input file plus an `_entry_shapes` key showing a `blockers` and a `resolved` entry; drop that key before rendering. Fill `verdict`, `senior_approval`, `goal`, `summary`, every surviving finding with its state `finding_id` and its 2-3 sentence `explanation`, `blockers` on the blocked-by-open-threads path from Phase 3 step 8, and `resolved` on a re-review. A finding that proposes no code change takes `N/A (no code change proposed)` for `class_sites`. Text fields carry no em or en dash; source text quoted from the issue or the diff goes in backticks and stays as you found it. A non-zero exit lists every problem on stderr. Fix the JSON and render again into a new directory; an output file is never edited by hand.

The renderer writes `summary.md`, `line_comments.json`, `file_level.json`, `monolithic.md`, and `ids.json`. It writes the `review-pr:run` marker, labels findings by severity (`C`, `S`, `M`, `m`), computes the severity badges from introduced findings, lists pre-existing findings under `### Pre-existing`, and never emits a `Filtered out` section. It routes each finding against the staged diff: a line on the post-image side becomes a line-level thread (REST, Phase A), any other file in the diff a file-level thread (GraphQL, Phase B), and a finding with no file (shown as `*(general)*`) or with a file outside the diff (shown with its path) the body fallback. On the blocked-by-open-threads path every finding goes to the body. Each demotion prints on stderr. `ids.json` maps every `finding_id` to the label and tier this round gave it, and its `line` entries appear in the same order as `line_comments.json`, which is how Step 8b ties each posted line comment back to its `finding_id`. Phase 4 write-back reads labels from it. Body fallback is the only acceptable reason for a finding to lack its own thread. Never use it to work around an API error (Step 7 in `${CLAUDE_SKILL_DIR}/references/github-posting-recovery.md` covers that).

Every finding status is exactly one of `active`, `resolved` (with commit SHA), `dismissed` (with reason), `wontfix` (with reason), or `regression`: the enum in `references/finding-state-schema.md`. "Deferred" is not one of them: it leaves the reader unable to tell a shipped fix from an open one.

---

## Step 2: What each rendered comment carries

Each comment opens with `<severity emoji> **<Severity>** · <Category>`, then the issue in bold, the explanation, and four labelled lines: `**Why it matters**`, `**Suggested fix**`, `**Inverse risk**`, `**Class-sites**`. A pre-existing finding adds ` · Pre-existing` to that first line, a blame sentence after it, and ends with `<!-- review-pr:origin=pre-existing -->`, which Phase 1 reads to keep the thread out of `OPEN_BLOCKERS`. Step 8c links its tracking issue once it exists.

**Inverse risk and Class-sites are not decoration.** They are the two cascade fields Phase 3
steps 4.56 and 4.55 derived, and `/fix-pr-review` seeds its own inverse-risk check and class
sweep straight off these two lines instead of re-deriving them. The renderer rejects a finding
without them; `none, pure addition` is a valid `Inverse risk`.

**Comment payload shape**:

- **Line-level (REST, Phase A)**: each `line_comments.json` entry is `{"path", "line", "side": "RIGHT", "body"}` and goes into the `comments` array of the REST review creation call.
- **File-level (GraphQL, Phase B)**: each `file_level.json` entry gives `path` and `body` for `addPullRequestReviewThread` with `subjectType: FILE` and `pullRequestReviewId: <node_id from Phase A>`.

**Never load bodies with `-f body=@file`.** The `@path` file-reading convention works only with `-F/--field`; `-f/--raw-field` posts the literal `@...` string, which renders as a dead link instead of the finding. This happened live on gastrosmart/GSM3#6274, where twenty threads posted as `@/var/...` paths and had to be rewritten with PATCH. Build the Phase A payload from the rendered files, as Step 4 does. A body typed into a shell JSON literal breaks on its first raw newline or tab with `jq: Invalid string: control characters`.

---

## Step 3: Freeze the rendered files

Freeze the files Step 1 rendered from the staged `diff.full.patch`. No fetch: the OID check and posting guards already cover movement since Phase 1. Freeze the rendered files and their SHA-256 digests. `file_level.json` is the posting ledger: Phase B posts and reconciles each exact frozen entry rather than rebuilding a path/body from live findings. Refresh the PR URL, base and current head SHA, and any prior review's ID, state, body, author, and submitted time. Invoke `preflight-mutations` immediately before Step 4 or Step 4-rolling (in `${CLAUDE_SKILL_DIR}/references/github-posting-rerun.md`) performs the posting batch's first mutation. Pass those target guards, all frozen payload paths and digests, every surviving finding ID, the semantic verdict, `IS_SELF_REVIEW`, `REVIEW_EVENT`, line/file targets, prior review ID or new-review action, subsequent add/submit/resolve targets, and the originating `/review-pr` request as the authorization source. Apply its result contract before continuing.

---

## Step 4, Phase A: create PENDING review with line-level comments (REST)

**Skip this step only if rolling-review path is active (Step 0 in `${CLAUDE_SKILL_DIR}/references/github-posting-rerun.md` proved a recent prior review has the required GitHub state and owns every current thread).** Use Step 4-rolling there instead.

Pass ALL fields in a single `--input` JSON. **Omit the `event` field** so the review stays PENDING while Phase B attaches file-level threads:

**Note**: call Phase A even with zero line-level findings. Pass `comments: []`. The REST endpoint accepts an empty array with a body-only PENDING review; this is the only way to get the `pullRequestReviewId` Phase B's mutations need.

The line-comment file holds `[]` when every finding is file-level.

```bash
REVIEW_RESP=$(jq -n \
    --rawfile body "<frozen summary body file>" \
    --arg commit_id "<head SHA>" \
    --slurpfile comments "<frozen line-comment JSON file>" \
    '{body: $body, commit_id: $commit_id, comments: $comments[0]}' \
  | gh api "repos/<owner>/<repo>/pulls/<number>/reviews" --method POST --input -)

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

A timeout, interrupted response, missing ID, or any HTTP error is `reconcile-required`, not proof that creation failed: a bare `HTTP 422` can still have created the review, and a second POST then fails with `User can only have one pending review per pull request`. Query the PR's reviews authoritatively with `gh api 'repos/<owner>/<repo>/pulls/<number>/reviews?per_page=100' --paginate`, fetch every current-author `PENDING` review and all of its review comments, then compare author, exact frozen summary body, exact head SHA, and complete canonical line-comment set. One exact match restores both review IDs and continues Phase B. One candidate that matches the head and summary but has a different line-comment set preserves its IDs and enters Step 7 in `${CLAUDE_SKILL_DIR}/references/github-posting-recovery.md`'s pending-review branch. If any other current-author pending review exists, preserve all candidate IDs and block for reconciliation; a nonmatching body or head is still external state, not evidence that no pending review exists. A current-author submitted review matching the frozen summary, head, and complete line-comment set, in `REQUIRED_REVIEW_STATE`, means the create landed and was then submitted. Capture its `node_id` and `id` and enter Step 7's submitted-review branch. A submitted match on summary and head that differs in line comments or state is `reconcile-required`. Set `NO_PENDING_REVIEW=true` only after a complete query proves there are zero current-author pending reviews and no such submitted match on the PR. Multiple exact or partial candidates, or an inconclusive query, block the run. Never create or fall back to another review while any pending create remains unresolved.

---

## Step 5, Phase B: attach file-level threads to the fresh pending review (GraphQL)

**Skip if `ROLLING_PATH=true`**: rolling eligibility proves there are no new threads to attach.

For each entry in the frozen canonical file-level set, in order (the rendered `file_level.json`), run `INDEX` from 0 to the file's length minus 1 and send that entry's exact path and body, recording the returned IDs against its `finding_id`. jq reads all three from the frozen file, so the shell never parses a body:

```bash
THREAD_RESP=$(jq -n \
    --arg reviewId "$REVIEW_NODE_ID" \
    --slurpfile entries "<frozen file_level.json>" \
    --argjson index "${INDEX:?}" \
    '{query: "mutation($reviewId: ID!, $path: String!, $body: String!) { addPullRequestReviewThread(input: {pullRequestReviewId: $reviewId, path: $path, body: $body, subjectType: FILE}) { thread { id comments(first: 1) { nodes { databaseId } } } } }",
      variables: {reviewId: $reviewId, path: $entries[0][$index].path, body: $entries[0][$index].body}}' \
  | gh api graphql --input -)

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

**Event mapping**: another author's `approve` verdict uses `APPROVE`, and `request-changes` uses `REQUEST_CHANGES`. A self-review uses `COMMENT` for either semantic verdict because GitHub forbids authors from approving their own pull requests. An `approve` with `INCOMPLETE_COVERAGE=true`, which batch mode sets when a required lens did not run, also uses `COMMENT`.

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

### 8c. Track pre-existing findings in their own issues

Covers every finding posted this round with `Origin: pre-existing`, plus every prior state entry with `origin: pre-existing` and no `tracking_issue`, which is how a failed filing gets retried, plus every entry still at `origin: pre-existing` with a `tracking_issue` whose thread is still unresolved, which reuses that URL and redoes only step 3. An entry reactivated as `introduced` keeps its old URL as history but never enters this set, so its blocking thread stays open. Dedupe the set by finding `id`. Skip when it is empty. For each:

1. Invoke `file-issue` for the PR's repository. The issue names the file, line, blame commit, and the finding's issue, why, and suggested fix, and links the review thread as the place it was found. When `file-issue` resolves it as a duplicate of an existing issue, that issue is the tracking issue. The `/review-pr` invocation authorizes this filing, and `preflight-mutations` still runs before it.
2. Record the issue URL for 8e the moment it exists, before any reply, so a later failure never files twice.
3. Reply on the finding's thread: `Tracked in <issue URL>. Pre-existing code, so it does not block this PR.` Then resolve the thread. The next round drops the finding as already reported, and `/fix-pr-review` skips resolved threads.

On the blocked-by-open-threads path the finding has no thread: file the issue and skip the reply. When filing fails, leave the thread open, report `not tracked (<reason>)` in the Pre-existing section, and let the next round retry. When the reply or resolve fails after filing, keep the URL and report `tracked, thread left open (<reason>)`. The marker still keeps that thread out of `OPEN_BLOCKERS`. A failure in this step never changes the verdict.

### 8e. Update `.claude/review-state/<pr>.yml`

Step 8d lives in `github-posting-rerun.md` and runs on re-runs only.

`references/finding-state-phase4.md` is the single source of truth for what Phase 4 writes: the full entry shape, which fields are required, and every status transition. Follow its "Phase 4: write back" section; do NOT reconstruct the entry shape from this file. An entry written without `file`, `enclosing_symbol`, and `rule_class` breaks the next round's ID computation, and one written without the cascade fields silently disables the next round's regression sweep.

The only part specific to posting: `github_thread_id` (from 8b) and `github_comment_id` (REST `databaseId`) are written onto the entry of each finding posted this round.

## Step 9: Emit the review URL

After Step 8 reconciles, build the clickable review URL from the reconciled database ID and print it as the `**Review URL**` line in the Phase 4 header block:

```bash
REVIEW_URL="https://github.com/<owner>/<repo>/pull/<number>#pullrequestreview-$REVIEW_DB_ID"
```

Use `REVIEW_DB_ID` for a fresh review, or `PRIOR_REVIEW_DB_ID` (copied into `REVIEW_DB_ID`) when `ROLLING_PATH=true`. Never print a URL from an unreconciled mutation response alone; the Phase C read-back or the Step 4-rolling authoritative body match is what confirms the ID. When the user keeps a pending draft, print the pending review URL with a `(pending draft)` suffix. When the run posts nothing, print `not posted (<reason>)` instead.

