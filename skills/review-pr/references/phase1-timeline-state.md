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
          comments(first:5) {
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

Build:

```
prior_findings:
  - thread_id: <PRRT_...>
    first_raised_at: <review_id>
    first_raised_commit: <sha>
    file: <path>
    line: <post-image line at the time>
    is_resolved: <bool>
    is_outdated: <bool: later commits invalidated the line>
    body_excerpt: <first 200 chars>
    resolution_state: open | resolved | outdated | stale
```

This enables (a) accurate dedupe in Phase 3, (b) "Resolved but still present" detection (thread closed but code still exhibits the issue → flag with `Category: Prior-finding-correction`).

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

### Run-over-run cache check

```bash
CACHE_DIR="$HOME/.claude/skills/review-pr/cache"
mkdir -p "$CACHE_DIR"
CACHE_FILE="$CACHE_DIR/<owner>_<repo>_<pr-number>.json"
```

Use the `CURRENT_HEAD` pinned in Phase 1. Do not re-read it here: a fresh read can move past the stashed diff and select a cache branch for a different revision.

Use `REVIEW_CACHE_CONTRACT_VERSION` from `references/finding-state-schema.md`, already loaded for the review-state read. Validate `contract_version` before reading any cache field. A missing or mismatched version invalidates the complete cache and starts a full fresh review. For a current cache, comparing `last_run_sha` to `CURRENT_HEAD` and the stored `base_sha` to the pinned base OID selects one of three branches: replay the cached run unchanged, re-review only the new commits, or invalidate and start fresh. The cache schema and the full body of each branch live in that reference under "Run-over-run cache".

After a successful run, write `contract_version: REVIEW_CACHE_CONTRACT_VERSION` with the result plus `last_run_sha` and `base_sha` (the pinned base OID) in `$CACHE_FILE` at the end of Phase 4. The cache stays local and never touches GitHub state.
