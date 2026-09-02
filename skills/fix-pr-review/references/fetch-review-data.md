# Fetching and normalising review data (Phase 2)

Loaded by main in Phase 2. Run only the section for the input type Phase 1 detected, then normalise everything into the `Comment` schema at the bottom. Those field names are what Phases 3-8 read.

---

## Real CodeRabbit structure (for reference)

A CodeRabbit PR review is a single `PullRequestReview` submission containing:

1. **Review `body`** (markdown) with collapsed sections:
   - `Actionable comments posted: N` header
   - `🧹 Nitpick comments (M)`: nitpicks live here as **text only**, NOT as inline comments. No thread to resolve.
   - **`🤖 Prompt for all review comments with AI agents`**: a pre-formatted plain-text block listing ALL findings in AI-consumable form. **This is the primary parsing target.**
   - `🪄 Autofix (Beta)` with task-list checkboxes
   - `ℹ️ Review info`

2. **N inline `PullRequestReviewComment`s** (actionables only; nitpicks don't get inline comments):
   - Attached to `path` + `line`
   - Wrapped in `PullRequestReviewThread` with `isResolved` state
   - Independently resolvable via GraphQL `resolveReviewThread(input:{threadId})`
   - Bodies tagged with severity: `_⚠️ Potential issue_ | _🔴 Critical_`, `_🛠️ Refactor suggestion_ | _🟠 Major_`, etc.

**Severity taxonomy**: `🔴 Critical`, `🟠 Major`, `🟡 Minor`, `🔵 Refactor`, `🧹 Nitpick`.

---

## For PR URL (paginated unresolved threads)

Loop with `after:` cursor until `hasNextPage == false`:

```bash
gh api graphql \
  -f owner=<owner> -f repo=<repo> -F num=<num> [-f after=<cursor>] \
  -f query='
query($owner:String!, $repo:String!, $num:Int!, $after:String) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$num) {
      title url baseRefName
      reviewThreads(first:100, after:$after) {
        nodes {
          id isResolved isOutdated path line
          comments(first:10) {
            nodes {
              databaseId author { login } body createdAt url
              pullRequestReview { id state body }
            }
          }
        }
        pageInfo { hasNextPage endCursor }
      }
    }
  }
}'
```

Accumulate across pages. Filter to `isResolved == false` after pagination completes.

**Also** fetch the latest CodeRabbit review body and pull the Prompt for AI agents block. That block holds nitpicks that never show up as threads:

```bash
gh api "repos/<owner>/<repo>/pulls/<num>/reviews" --paginate
```

Select the latest review where `user.login == coderabbitai[bot]` and `state ∈ {CHANGES_REQUESTED, COMMENTED}`.

## For review URL (`#pullrequestreview-<id>`)

```bash
gh api "repos/<owner>/<repo>/pulls/<num>/reviews/<review_id>"
gh api "repos/<owner>/<repo>/pulls/<num>/reviews/<review_id>/comments"
```

Then run the paginated GraphQL `reviewThreads` query (same as above) and match inline comments to their thread by `databaseId`.

## For discussion URL (`#discussion_r<id>`)

```bash
gh api "repos/<owner>/<repo>/pulls/comments/<comment_id>"
```

(Note: endpoint has NO pull-number; it's `/pulls/comments/<id>`, not `/pulls/<num>/comments/<id>`.)

Then run the paginated GraphQL `reviewThreads` query and match the comment's `databaseId` inside `reviewThreads.nodes[].comments.nodes[].databaseId`. Scope the rest of the flow to just that one thread.

## Parse CodeRabbit body's AI prompt block when present

If any fetched review's body contains `🤖 Prompt for all review comments with AI agents`, extract that section. It's a pre-formatted plain-text block with ALL findings in AI-consumable form, more reliable than HTML-unwrapping collapsibles. The block contains:

- `Inline comments:` section → maps to actionable items (match to inline comments by file:line)
- `Nitpick comments:` section → body-only nitpicks with file + line
---

## Normalize to internal `Comment` list

```
Comment {
  id:           <GraphQL thread node_id, OR synthetic for local/nitpick>
  thread_id:    <GraphQL PRRT_ id, NULL for nitpicks and local>
  review_id:    <parent review node_id, if applicable>
  author:       <coderabbit | human | review-pr | pasted>
  source_type:  <actionable | nitpick | local>
  path:         <file path>
  line:         <post-image line, NULL for body-only nitpicks without clear line>
  severity:     <critical | serious | major | moderate | minor | refactor | nitpick>
  body:         <full comment text>
  html_url:     <direct URL to the comment, or review body URL for nitpicks>
  can_resolve:  <true if thread_id exists>
  can_reply:    <true if thread_id exists>
}
```
