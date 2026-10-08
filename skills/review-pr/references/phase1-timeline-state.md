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
              databaseId author { login } body createdAt
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
          databaseId author { login } body createdAt
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
    author_rationale: <none | design-decision | out-of-scope | refuted-with-evidence | fix-promised, read from human replies AFTER the first comment; bot replies never count>
    rationale_pointer: <doc path, ADR, issue number, test name, measurement, or file:line cited in the reply, or none>
    reply_excerpt: <first 300 chars of the human reply that set author_rationale, or none>
    resolution_state: open | resolved | outdated | stale
```

This enables (a) accurate dedupe in Phase 3, (b) reply-aware reopening. Read every human reply on every prior thread, open or resolved, before any prior finding is carried, re-verified, or re-raised. An author who answers a finding often leaves the thread open for a human reviewer. Code that still exhibits the issue is not by itself grounds to raise it again. A thread is **answered** when its `author_rationale` is design-decision (points at a doc, ADR, or issue), out-of-scope (points at a follow-up issue), or refuted-with-evidence (names a test, measurement, counterexample, or file:line). A reply without a pointer sets `none`. Record an answered finding as `dismissed` or `wontfix` in the state file with that rationale in `dismissal_reason` and the code condition it rests on in `depends_on`, and do not re-raise it. "The new commits did not touch this code" is never a reason to re-raise an answered finding. The author already said why the code stays. Re-raise with `Category: Prior-finding-correction` only when the thread is not answered, the reply promised a fix the diff shows never landed, a later commit voided `depends_on`, or you have new evidence that a specific claim in `reply_excerpt` is false. A correction on an answered thread quotes the claim it refutes, names the new evidence, and links the prior thread.

### Derive `OPEN_BLOCKERS`

From the same list, collect every entry with `is_resolved == false` AND `is_outdated == false`,
keeping its `file`, `line` (absent for file-level threads), `author_login`, and `body_excerpt`.
Outdated threads stay out: the code moved under them, so they no longer describe the head
under review. `OPEN_BLOCKERS` never feeds dedupe. Dedupe still drops re-reported findings
so no duplicate threads are created. `OPEN_BLOCKERS` feeds the Phase 3 step 8 and step 9
verdict guards: neither an approve nor a senior-engineer Yes may stand while blockers are open.

### Load review-state (multi-round dedup)

Load `${CLAUDE_SKILL_DIR}/references/finding-state-schema.md` before reading the state file. It defines the schema, the legal `status` values, and the finding-ID strategy every later phase writes against.

```bash
# Local mode: state lives next to the working tree
STATE_FILE=".claude/review-state/<pr-number>.yml"
# Cross-repo mode: state is keyed by owner__repo__pr in the user's home
[ "$CROSS_REPO_MODE" = "true" ] && \
  STATE_FILE="$HOME/.claude/review-state/<owner>__<repo>__<pr-number>.yml"

STATE_DIR="$(dirname "$STATE_FILE")"
mkdir -p "$STATE_DIR"
# Review state is per-machine scratch, never shared. A self-ignoring dir keeps it
# out of `git status` in repos that DO commit `.claude/` (settings, skills).
[ -f "$STATE_DIR/.gitignore" ] || printf '*\n' > "$STATE_DIR/.gitignore"

if [ -f "$STATE_FILE" ]; then
  PRIOR_STATE=$(cat "$STATE_FILE")
else
  PRIOR_STATE='{ pr: <num>, repo: "<owner>/<repo>", findings: [], last_round: 0 }'
fi

CURRENT_ROUND=$(( $(echo "$PRIOR_STATE" | yq '.last_round') + 1 ))
```

`PRIOR_STATE.findings` is passed into Subagent 1's prompt (filtered to `status in {resolved, dismissed, wontfix}`) so the reviewer suppresses already-handled findings upfront. Phase 3 step 4.95 enforces this as a safety net.

### Record author rationale (reply-aware dispositions)

Do this after state load, before Phase 2 dispatch. Start `ANSWERED_THREADS` as an empty list; it is a Phase 3 and Phase 4 input only. For every answered timeline entry:

1. Match the timeline `thread_id` to the state entry whose `github_thread_id` equals it. No match happens when the state file is missing, comes from another worktree, or was written without thread IDs. The reply still holds: add the thread to `ANSWERED_THREADS` with its `thread_id`, `file`, `line`, `body_excerpt`, `author_rationale`, `dismissal_reason` (the rationale plus its pointer), and `depends_on` (the code condition the rationale rests on). Phase 3 drops findings that match it per `critic-verify.md` step 3, and Phase 4 writes the state entry from the dropped finding's identity. Never fall back to letting reviewers raise an answered thread again.
2. On a match, set the entry deterministically: `out-of-scope` becomes `wontfix`; `design-decision` or `refuted-with-evidence` becomes `dismissed`. Write `dismissal_reason` as the rationale plus its pointer, `depends_on` as the code condition the rationale rests on, and refresh `updated_at`. Leave round counters untouched.
3. Entries written here enter Phase 3 as `dismissed`/`wontfix` and suppress normally; a later commit that voids `depends_on` reopens them through the existing rule, not through a new finding.

### Run-over-run cache check

```bash
CACHE_DIR="$HOME/.claude/skills/review-pr/cache"
mkdir -p "$CACHE_DIR"
CACHE_FILE="$CACHE_DIR/<owner>_<repo>_<pr-number>.json"
```

Use the `CURRENT_HEAD` pinned in Phase 1. Do not re-read it here: a fresh read can move past the stashed diff and select a cache branch for a different revision.

Use `REVIEW_CACHE_CONTRACT_VERSION` from `references/finding-state-schema.md`, already loaded for the review-state read. Validate `contract_version` before reading any cache field. A missing or mismatched version invalidates the complete cache and starts a full fresh review. For a current cache, comparing `last_run_sha` to `CURRENT_HEAD` and the stored `base_sha` to the pinned base OID selects one of three branches: replay the cached run unchanged, re-review only the new commits, or invalidate and start fresh. The cache schema and the full body of each branch live in that reference under "Run-over-run cache".

After a successful run, write `contract_version: REVIEW_CACHE_CONTRACT_VERSION` with the result plus `last_run_sha` and `base_sha` (the pinned base OID) in `$CACHE_FILE` at the end of Phase 4. The cache stays local and never touches GitHub state.
