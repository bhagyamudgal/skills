# Phase 1 context detail

### Build the prior-review timeline

Fetch all reviews, not just the latest. The critic tracks which findings came up at which commit, whether they resolved, and whether an unresolved finding still holds on the current head.

```bash
gh api graphql -f query='
query($owner:String!, $repo:String!, $num:Int!, $after:String = null) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$num) {
      reviewThreads(first:100, after:$after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id isResolved isOutdated path line
          comments(first:20) {
            pageInfo { hasNextPage endCursor }
            nodes {
              databaseId author { __typename login } body createdAt
              pullRequestReview { id submittedAt commit { oid } state }
            }
          }
        }
      }
    }
  }
}' -f owner=<owner> -f repo=<repo> -F num=<num>   # -f for String!, -F for Int!
```

Paginate: while `pageInfo.hasNextPage` is true, repeat with `-f after=<endCursor>` and accumulate every page before building the timeline. Past 100 threads an unpaginated fetch silently drops history the dedupe needs.

Paginate thread comments the same way, per thread. After the thread list is complete, for every thread whose comments `pageInfo.hasNextPage` is true, fetch the remaining pages before classifying anything:

```bash
gh api graphql -f query='
query($threadId:ID!, $after:String = null) {
  node(id:$threadId) {
    ... on PullRequestReviewThread {
      comments(first:100, after:$after) {
        pageInfo { hasNextPage endCursor }
        nodes {
          databaseId author { __typename login } body createdAt
          pullRequestReview { id submittedAt commit { oid } state }
        }
      }
    }
  }
}' -f threadId=<thread id> -f after=<endCursor>
```

Accumulate every page per thread. Never classify a thread as having no human reply while its comments connection still has an unfetched page: an unseen page may hold the rationale.

Build:

```
prior_findings:
  - thread_id: <PRRT_...>
    first_raised_at: <review_id>
    first_raised_commit: <sha>
    file: <path>
    line: <post-image line at the time, absent for file-level threads>
    is_resolved: <bool>
    is_outdated: <bool: later commits invalidated the line>
    author_login: <thread author login>
    body_excerpt: <first 200 chars>
    owned_by_viewer: <bool: the first comment's author is VIEWER>
    author_rationale: <none | design-decision | out-of-scope | refuted-with-evidence | fix-promised | disputed, read from the newest human reply AFTER the first comment that takes a position on the finding; a reply that only thanks or acknowledges, such as "Thanks", is skipped, while one that concedes, such as "you're right", sets none>
    rationale_pointer: <doc path, ADR, issue number, test name, measurement, or file:line cited in the reply, or none>
    rationale_reply: <full text of the human reply that set author_rationale, or none>
    rationale_comment_id: <databaseId of that reply, or none>
    resolution_state: open | resolved | outdated | stale
```

This enables (a) accurate dedupe in Phase 3, (b) reply-aware reopening. A **human reply** is a comment after the first whose author `__typename` is not `Bot` and whose body carries no `review-pr:` marker, excluding the `/review-pr` `Tracked in <issue URL>` reply (a `VIEWER` comment on a thread whose first comment carries `review-pr:origin=pre-existing`).

`ANSWERED_COMMENTS` maps each author comment `/review-pr` already answered to the answer's kind. Read it from `VIEWER` content outside `PENDING` reviews only, since a leftover draft was never published: thread comments carrying `<!-- review-pr:reply to=<id> kind=<kind> -->`, and review bodies carrying `<!-- review-pr:answered <id>=<kind> ... -->`. Fetch the reviews once here, into a file, since each shell call starts fresh; the response includes the viewer's pending reviews:

```bash
REVIEWS_FILE="${TMPDIR:-/tmp}/review-pr-<owner>-<repo>-<pr-number>-reviews.json"
gh pr view <url> --json reviews > "$REVIEWS_FILE" \
  || { echo "GitHub reviews query failed; stop before reading answers" >&2; exit 1; }
```

Each rendered summary carries every prior entry forward, so a body update never loses one. Read every human reply on every prior thread, open or resolved, before any prior finding is carried, re-verified, or re-raised. An author who answers a finding often leaves the thread open for a human reviewer. Code that still exhibits the issue is not by itself grounds to raise it again. A thread is **answered** when its `author_rationale` is design-decision (points at a doc, ADR, or issue), out-of-scope (points at a follow-up issue), or refuted-with-evidence (names a test, measurement, counterexample, or file:line). A thread whose `rationale_comment_id` `ANSWERED_COMMENTS` records as `correction` or `needs-pointer` is not answered: `/review-pr` already ruled that reply insufficient. A reply that disagrees with the finding but cites no pointer sets `disputed`, which is not answered; any other reply without a pointer sets `none`. Record an answered finding as `dismissed` or `wontfix` in the state file with that rationale in `dismissal_reason` and the code condition it rests on in `depends_on`, and do not re-raise it. "The new commits did not touch this code" is never a reason to re-raise an answered finding. The author already said why the code stays. Re-raise with `Category: Prior-finding-correction` only when the thread is not answered, the reply promised a fix the diff shows never landed, a later commit voided `depends_on`, or you have new evidence that a specific claim in `rationale_reply` is false. A correction on an answered thread quotes the claim it refutes, names the new evidence, and links the prior thread.

### Derive `OPEN_BLOCKERS`

From the same list, collect every entry with `is_resolved == false` AND `is_outdated == false`,
keeping its `file`, `line` (absent for file-level threads), `author_login`, and `body_excerpt`.
Outdated threads stay out: the code moved under them, so they no longer describe the head
under review. A viewer-owned thread whose newest comment in `ANSWERED_COMMENTS` is recorded as `accepted`
stays out too: `/review-pr` already withdrew that finding, even if resolving its thread failed. A later `correction` or `needs-pointer` answer on the same thread puts it back. Threads whose first comment carries `<!-- review-pr:origin=pre-existing -->` stay out too: that code
predates the PR, so its thread is never this PR's to clear. The marker lives in the comment,
so this works before the state file loads and when no state file exists. `OPEN_BLOCKERS` never feeds dedupe. Dedupe still drops re-reported findings
so no duplicate threads are created. `OPEN_BLOCKERS` feeds the Phase 3 step 8 and step 9
verdict guards: neither an approve nor a senior-engineer Yes may stand while blockers are open.

### Load review-state (multi-round dedup)

Load `${CLAUDE_SKILL_DIR}/references/finding-state-schema.md` before reading the state file. It defines the schema, the legal `status` values, and the finding-ID strategy every later phase writes against.

```bash
# Local mode: state lives next to the working tree
STATE_FILE=".claude/review-state/<pr-number>.json"
# Cross-repo mode: state is keyed by owner__repo__pr in the user's home
[ "$CROSS_REPO_MODE" = "true" ] && \
  STATE_FILE="$HOME/.claude/review-state/<owner>__<repo>__<pr-number>.json"

STATE_DIR="$(dirname "$STATE_FILE")"
mkdir -p "$STATE_DIR"
# Review state is per-machine scratch, never shared. A self-ignoring dir keeps it
# out of `git status` in repos that DO commit `.claude/` (settings, skills).
[ -f "$STATE_DIR/.gitignore" ] || printf '*\n' > "$STATE_DIR/.gitignore"

STATE_SCRIPT="${CLAUDE_SKILL_DIR:?}/scripts/review_state.py"
python3 "$STATE_SCRIPT" round --repo <owner>/<repo> --pr <pr-number> --file "$STATE_FILE" \
  || { code=$?; echo "round lookup failed (exit $code); stop before reviewing" >&2; exit $code; }
HANDOFF_DIR="${STATE_FILE%.json}-handoff"
mkdir -p "$HANDOFF_DIR"
python3 "$STATE_SCRIPT" read --repo <owner>/<repo> --pr <pr-number> --file "$STATE_FILE" > "$HANDOFF_DIR/prior-state.json" \
  || { code=$?; echo "state read failed (exit $code); never continue as if no state exists" >&2; exit $code; }
echo "PRIOR_STATE: $HANDOFF_DIR/prior-state.json"
```

Read the state and the round only through `review_state.py`, never with `cat`, `yq`, or a parser you write. The first line printed is `CURRENT_ROUND`, and `PRIOR_STATE` is the JSON file the last line names; each shell call starts fresh, so carry the round from this output and read that file before Phase 2. `read` writes the empty state `{pr, repo, findings: [], last_round: 0}` when this PR has none. When only a legacy `<pr-number>.yml` exists, it converts that file on every read until Phase 4 saves JSON. Exit 3 means the legacy file does not convert: follow the advice on stderr, which names the ruby version, and never write JSON over it. Exit 2 from `round` with a `gh` error on stderr is a GitHub failure: retry, the state file is untouched. Any other exit 2 names a corrupt state file or one that belongs to another PR: stop the run and report it, never delete or replace it. `round` prints one past the higher of the GitHub `review-pr:run` markers, which it fetches in full itself, and the state file's `last_round`.

The `review-pr:run` markers on GitHub are the round every reviewer and machine shares; the state file is this machine's copy, missing on any other machine or worktree. A leftover pending review's marker counts too, so this run's summary can never equal an earlier run's draft and Phase A reconciliation never adopts that draft as its own.

`PRIOR_STATE.findings` is passed into Subagent 1's prompt (filtered to `status in {resolved, dismissed, wontfix}`, minus `origin: pre-existing` entries) so the reviewer suppresses already-handled findings upfront. Pre-existing entries stay reportable so Phase 3 step 4.57 can notice a later commit rewriting their line. Phase 3 step 4.95 enforces this as a safety net.

### Record author rationale (reply-aware dispositions)

Do this after state load, before Phase 2 dispatch. Start `ANSWERED_THREADS` as an empty list; it is a Phase 3 and Phase 4 input only. For every answered timeline entry:

1. Match the timeline `thread_id` to the state entry whose `github_thread_id` equals it. No match happens when the state file is missing, comes from another worktree, or was written without thread IDs. The reply still holds: add the thread to `ANSWERED_THREADS` with its `thread_id`, `file`, `line`, `body_excerpt`, `author_rationale`, `rationale_reply`, `dismissal_reason` (the rationale plus its pointer), and `depends_on` (the code condition the rationale rests on). Phase 3 drops findings that match it per `critic-verify.md` step 3, and Phase 4 writes the state entry from the dropped finding's identity. Never fall back to letting reviewers raise an answered thread again.
2. On a match, set the entry deterministically: `out-of-scope` becomes `wontfix`; `design-decision` or `refuted-with-evidence` becomes `dismissed`. Write `dismissal_reason` as the rationale plus its pointer, `depends_on` as the code condition the rationale rests on, and refresh `updated_at`. Leave round counters untouched.
3. Entries written here enter Phase 3 as `dismissed`/`wontfix` and suppress normally, except an `answered-correction` per `critic-round2.md` step 4.95; a later commit that voids `depends_on` reopens them through the existing rule, not through a new finding.

Then build `DISPUTE_REPLIES`, the answers Phase 4 lists in the review body and, when it creates a pending review, attaches to the disputed threads. Add one entry per `owned_by_viewer` timeline entry on an unresolved, non-outdated thread whose `rationale_comment_id` is not in `ANSWERED_COMMENTS` and whose `author_rationale` is answered or `disputed`. A thread someone already resolved needs no answer. Each entry has `thread_id`, `answers_comment_id` (its `rationale_comment_id`), `location` (`file:line`, or `file` for a file-level thread), and `kind`: `accepted` for answered with `reason` (the rationale plus its pointer, one line), `needs-pointer` for `disputed`. Phase 3 step 3 turns an entry into `correction` when it keeps an `answered-correction` for that thread. Threads other reviewers opened get no reply. `ANSWERED_COMMENTS` is the dedup record: an answered comment never enters this list again, and a new reply from the author is a new comment ID.

### Run-over-run cache check

```bash
CACHE_DIR="$HOME/.claude/skills/review-pr/cache"
mkdir -p "$CACHE_DIR"
CACHE_FILE="$CACHE_DIR/<owner>_<repo>_<pr-number>.json"
```

Use the `CURRENT_HEAD` pinned in Phase 1. Do not re-read it here: a fresh read can move past the stashed diff and select a cache branch for a different revision.

Use `REVIEW_CACHE_CONTRACT_VERSION` from `references/finding-state-schema.md`, already loaded for the review-state read. Validate `contract_version` before reading any cache field. A missing or mismatched version invalidates the complete cache and starts a full fresh review. For a current cache, comparing `last_run_sha` to `CURRENT_HEAD` and the stored `base_sha` to the pinned base OID selects one of three branches: replay the cached run unchanged, re-review only the new commits, or invalidate and start fresh. An unanswered dispute, or a human reply newer than the cached post, blocks the replay, per the reply check in branch 1. The cache schema and the full body of each branch live in that reference under "Run-over-run cache".

After a successful run, write `contract_version: REVIEW_CACHE_CONTRACT_VERSION` with the result plus `last_run_sha`, `base_sha` (the pinned base OID), and `incomplete_coverage` with `skipped_lenses` (`true` and each skipped lens with its reason when `INCOMPLETE_COVERAGE=true`, else `false` and `[]`) in `$CACHE_FILE` at the end of Phase 4. The cache stays local and never touches GitHub state.
