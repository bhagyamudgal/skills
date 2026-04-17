---
name: review-pr
description: Deep, anti-slop review of a GitHub PR. Grounds findings in the linked issue's intent, runs Claude + CodeRabbit reviewers in parallel, then critic-passes the findings before printing. Use when user says "review this pr", pastes a GitHub PR URL, or asks "check this pull request". NOT for local uncommitted changes — use /parallel-review for those.
---

# /review-pr — Deep GitHub PR Review

Reviews a remote GitHub PR with anti-slop filtering. Input: **PR URL only**.

The goal of this skill is simple: produce an accurate, critical, actionable PR review that surfaces what a human reviewer should double-check — and filters out the noise (style nitpicks, hallucinated references, duplicates of prior findings, generic advice).

**Use AskUserQuestion for ALL user-facing decisions** — stop-and-ask fallback, cache replay, large-PR confirmation, self-review handling, post-review choices, post-failure recovery, and post-completion next-action. Always present options as cursor-selectable choices, not plain text questions.

**Anti-patterns — NEVER do these:**
- NEVER present choices as a numbered markdown list in terminal text (e.g., `1. Post all / 2. Post criticals / 3. Keep local / 4. Fix them`). That short-circuits the tool call.
- NEVER end a response with `Would you like me to... ?` followed by a list of options in prose.
- NEVER ask `What's next — do X, or are we done?` after a tool-call decision. The prior AskUserQuestion is the last word.
- Self-test: if you catch yourself writing a sentence that asks the user to pick between 2+ labeled paths, STOP and use `AskUserQuestion` instead.

## Superpowers planning pipeline (optional pre-review context)

Some PRs may have been shaped by a multi-phase superpowers planning pipeline before code was written. If the repo contains these artifacts, they provide useful context for design decisions:

- **`docs/superpowers/specs/`** — design spec documents produced by `/brainstorming` and stress-tested by `/grill-me`
- **Plan files** (e.g., `~/.claude/plans/`) — step-by-step implementation plans produced by `/writing-plans` after `/harden-plan` validation

The typical pipeline when used: `/brainstorming` → `/grill-me` → `/harden-plan` → `/writing-plans` → `/executing-plans` → `/done`.

**If spec/plan files exist**: check whether the PR aligns with documented design decisions. Deviations without justification can be flagged under Q1 (Intent). **If they don't exist**: the PR author may not use this workflow — skip this check entirely.

## Usage

```
/review-pr https://github.com/owner/repo/pull/123
```

If no URL is provided, ask the user for one. Don't attempt to infer from the current branch.

---

## Phase 1: Gather context (main)

Run these as **two separate Bash tool calls in a single assistant message** (not `&&` chained in one shell call — true parallelism requires separate tool_use blocks):

```bash
gh pr view <url> --json number,title,body,author,baseRefName,headRefName,additions,deletions,changedFiles,files,closingIssuesReferences,reviews,comments,state,isDraft
gh pr diff <url>
```

Phase 1 fetches the **full diff** (not `--name-only`). The diff is needed for the error-handling content scan below AND for the Phase 3 critic's reference verification. Stash it in main context.

### Empty-diff short-circuit

If `changedFiles == 0` OR `additions + deletions == 0` (merge-only, empty, or binary-only PR), print:

> **Nothing to review** — this PR contains no reviewable file changes.

Stop immediately. Do not dispatch Phase 2.

### Private-repo / access-error handling

If `gh pr view` returns a GraphQL resolution error or HTTP 404:

> **Couldn't access PR** — check you have repo access. Try `gh auth refresh -s repo` and retry.

Fail fast.

### Extract linked issues

1. Prefer `closingIssuesReferences` from the JSON (GitHub's first-class link). Each reference carries its own `repository.nameWithOwner` — **use that per-issue**, not the PR's repo, so cross-repo issues resolve correctly.
2. Fall back to regex on the body: `(?i)(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)` (same-repo only — document the limitation in the intent model note).
3. For each linked issue, fetch with the canonical form:
   ```bash
   gh issue view <num> --repo <owner>/<repo> --json title,body,state
   ```
4. If **≥ 2 linked issues**, add `multiple linked issues — intent may be ambiguous` to the intent model. If their goals plainly contradict, route to the stop-and-ask fallback.

### Build the intent model

Keep it short — stays in main context.

```
Goal: <one sentence from issue + PR description>
Expected touches: <what files/areas should be changed to accomplish this>
Out of scope: <anything the issue explicitly excludes, or "none">
Size: <additions>/<deletions> lines across <N> files
Draft: <yes|no>
```

### Build the prior-review timeline (richer than a bullet list)

Instead of a flat "Prior findings: \<bullet list\>", build a structured timeline fetching ALL reviews (not just the latest) so the critic can track which findings were raised at which commit, whether they were resolved, and whether an unresolved finding is still valid on the current head.

Fetch:

```bash
gh pr view <url> --json reviews,reviewDecision -q '{
  reviews: .reviews,
  decision: .reviewDecision
}'

# For review comments + their thread resolution state
gh api graphql -f query='
query($owner:String!, $repo:String!, $num:Int!) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$num) {
      reviewThreads(first:100) {
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

Build this structure in main context:

```
prior_review_timeline:
  - review_id: <id>
    reviewer: <login>
    submitted_at: <iso>
    commit_sha: <sha at time of review — from pullRequestReview.commit.oid>
    state: APPROVED | CHANGES_REQUESTED | COMMENTED | DISMISSED
    body_excerpt: <first 200 chars of the review body>

prior_findings:
  - thread_id: <PRRT_...>
    first_raised_at: <review_id>
    first_raised_commit: <sha>
    file: <path>
    line: <post-image line at the time>
    is_resolved: <bool>
    is_outdated: <bool — true if later commits invalidated the line>
    body_excerpt: <first 200 chars of the comment body>
    resolution_state:
      - open       (not resolved, not outdated, still points at valid line)
      - resolved   (marked resolved on GitHub)
      - outdated   (later commits changed the code but comment wasn't explicitly resolved)
      - stale      (open but the referenced code is gone — must re-check)
```

Pass both `prior_review_timeline` and `prior_findings` into the Phase 2 reviewer subagent prompt. This enables:

1. **Better Prior-finding-correction (R4)** — the reviewer can cite a specific prior finding by thread_id and note "still unresolved on current head (<sha>)" when the timeline shows `is_resolved: false` AND the code is still present.
2. **Accurate dedupe in Phase 3 Step 3** — drop a finding only if its normalized symbol/file/line matches a prior `open` or `resolved` finding. An `outdated` prior finding is no longer authoritative — the reviewer can re-raise on the new code without being dropped.
3. **"Resolved but still present" detection** — if a thread is marked `resolved` on GitHub but the code matches the original concern, the reviewer should flag it with `Category: Prior-finding-correction` and note "thread was closed but code still exhibits the issue".

**Cross-repo mode note**: the GraphQL query works identically in cross-repo mode (no local checkout needed). The only thing that's harder is the "still present on current head" check — in local mode we can `git show HEAD:<path>`, in cross-repo mode we need `gh api contents/<path>?ref=<sha>`.

### Stop-and-ask fallback

Trigger the fallback if **no linked issue** AND the PR description **lacks all** of these grounding signals:

- A file path or directory reference (e.g., `src/auth/cache.ts`)
- A function / class / symbol name (e.g., `handleEviction`, `UserRole`)
- An error message or stack trace reference
- A reproduction command (e.g., `make stress-test-auth`)
- A linked issue URL in body (even one outside `closingIssuesReferences`)

Thin descriptions like "update X", "fix bug", or "wip" fail the signal check. Terse-but-grounded descriptions like "Fix race condition in `auth/cache.ts` eviction (repros with `make stress-test-auth`)" pass.

On trigger, use AskUserQuestion:

   Question:
     header: "Intent"
     text: "Intent is unclear — no linked issue and the description lacks grounding signals. How should I proceed?"
     options:
       - label: "Proceed anyway"
         description: "Review with just the diff — findings will be generic without intent grounding"
       - label: "Skip this PR"
         description: "Abort the review entirely"
       - label: "I'll provide intent"
         description: "Let me type the intent/goal now so findings can be grounded"

On "Proceed anyway": continue with empty intent model (set Goal to "not stated"). On "Skip this PR": exit 0. On "I'll provide intent": wait for the user's follow-up text input, then build the intent model from it. On "Other": treat as freeform intent text.

Do not proceed silently with weak intent. This is your first anti-slop gate.

### Size warning

If `additions + deletions > 2000`:

> This PR touches **X lines across Y files**. Review may be noisy and slow. Proceeding.

Then continue.

### Wall-time instrumentation (start)

Capture `PHASE_START_TIME=$(date +%s)` at the top of Phase 1 and similar timestamps at the start of each later phase. Print the elapsed total at the end of Phase 4's Filtered Out section (format: `Phase 1: Xs · Phase 2: Xs (parallel wall) · Phase 3: Xs · Phase 4: Xs · Total: Xs`). This is cheap and gives visibility into where time is going for future tuning.

### Detect cwd-vs-PR-repo mismatch (cross-repo mode)

If the current working directory is a git repo BUT its `nameWithOwner` doesn't match the PR URL's `owner/repo`, we're running in **cross-repo mode**. This affects Phase 1's repo map computation and Phase 3's already-fixed checks.

```bash
CWD_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
PR_REPO="<owner>/<repo>"  # parsed from the PR URL
if [ -z "$CWD_REPO" ] || [ "$CWD_REPO" != "$PR_REPO" ]; then
  CROSS_REPO_MODE=true
else
  CROSS_REPO_MODE=false
fi
```

Cross-repo mode changes two things downstream:
1. **Repo map computation** — falls back to remote `gh api` tree fetch instead of local `find` (see next section).
2. **Phase 3 already-fixed check** — can't use `git log` locally; falls back to comparing the PR's commit range against comments via `gh pr view --json reviews,commits`.

Note `CROSS_REPO_MODE` in the Phase 4 output header so the user knows the run didn't have a local checkout advantage.

### Detect CodeRabbit paused state

If any recent CodeRabbit review or comment body contains the string `"Reviews paused"` (CodeRabbit's auto-pause message when a branch has rapid churn), set `CODERABBIT_PAUSED=true` and DO NOT dispatch the CodeRabbit subagent in Phase 2. The degraded-mode rule handles missing CodeRabbit reviewer gracefully.

Detect via:
```bash
gh pr view <url> --json reviews -q '.reviews[].body' | grep -q "Reviews paused" && CODERABBIT_PAUSED=true
```

Note in Phase 4 output header: `CodeRabbit: skipped (paused — active development)`.

### Size-based routing (determine SIZE_MODE)

Based on `additions + deletions`, set the dispatch strategy for Phase 2. Smaller PRs don't need the full heavy-subagent pipeline; larger PRs benefit from chunked parallelism.

```
SIZE = additions + deletions

if SIZE < 100:
    SIZE_MODE = "solo-main"
    # Skip subagent dispatch entirely; run Q1-Q6 (+ Q7-Q9 if schema PR) in main context.
    # Justification: a 50-line PR doesn't warrant 2× subagent spin-up cost (~5min wall time).
    # Main context reads the diff once, answers questions inline, critic pass is lighter.
elif SIZE <= 500:
    SIZE_MODE = "parallel-standard"
    # Current behavior: Claude reviewer + CodeRabbit (if not paused) + conditional silent-failure hunter
elif SIZE <= 2000:
    SIZE_MODE = "parallel-chunked"
    # Claude reviewer receives a file-split assignment: group files into ~500-line chunks,
    # dispatch one Claude reviewer subagent PER CHUNK, each with the same ground truth +
    # intent model but scoped to its chunk. Still dispatch CodeRabbit + silent-failure hunter
    # at full PR scope. Main-context critic merges findings across chunks in Phase 3.
else:
    # > 2000 lines
    SIZE_MODE = "parallel-chunked-confirm"
    # AskUserQuestion: Continue vs Cancel (see below)
```

Phase 2 reads `SIZE_MODE` and dispatches accordingly. For `solo-main`, Phase 2's Subagent 1 section is replaced by inline main-context execution with the same prompt body (no Agent tool call).

### Run-over-run cache check

Before dispatching anything in Phase 2, check for a cached prior run:

```bash
CACHE_DIR="$HOME/.claude/skills/review-pr/cache"
mkdir -p "$CACHE_DIR"
CACHE_FILE="$CACHE_DIR/<owner>_<repo>_<pr-number>.json"

CURRENT_HEAD=$(gh pr view <url> --json headRefOid -q .headRefOid)
```

If `$CACHE_FILE` exists:

```json
{
  "last_run_sha": "abc123...",
  "last_run_timestamp": "2026-04-11T13:29:50Z",
  "last_run_verdict": "request-changes",
  "findings": [ ... ],
  "filtered_out": [ ... ],
  "last_posted_review_id": 12345678,
  "last_posted_review_node_id": "PRR_kwDO...",
  "last_posted_verdict": "request-changes",
  "last_posted_at": "2026-04-11T13:30:15Z",
  "posted_comments": [
    {
      "finding_key": "(file.ts, 47, processrequest)",
      "finding_id": "S1",
      "github_comment_id": 12345,
      "github_thread_id": "PRRT_abc123",
      "finding_severity": "Serious"
    },
    {
      "finding_key": "(config.ts, file-level:Architecture, missingvalidation)",
      "finding_id": "M2",
      "github_comment_id": 12346,
      "github_thread_id": "PRRT_def456",
      "finding_severity": "Moderate"
    }
  ]
}
```

The `posted_comments` array tracks review comments from the hybrid posting (see Phase 4). Each entry maps a finding's dedupe key to its GitHub comment and thread IDs, enabling thread resolution on re-reviews. The `last_posted_*` fields track the most recent posted review for verdict-body sync checks.

Three branches:

1. **`last_run_sha == CURRENT_HEAD`** — no new commits since last run. Use AskUserQuestion:

   Question:
     header: "Cache"
     text: "Cached review found for this commit (<sha>, <timestamp>). <N> findings. What would you like to do?"
     options:
       - label: "Replay cached (Recommended)"
         description: "Show the cached findings without re-running — saves tokens"
       - label: "Fresh review"
         description: "Discard cache and run a full new review from scratch"

   On "Replay cached": print the cached findings and exit (Phase 2/3/4 skipped). On "Fresh review": proceed with full run. On "Other": treat as fresh review.

2. **New commits since last run** (cached `last_run_sha` is an ancestor of `CURRENT_HEAD`) — PARTIAL re-review mode:
   - Compute `git diff <last_run_sha>..<CURRENT_HEAD>` to get only the new commits' diff (via `gh api compare` in cross-repo mode).
   - Dispatch Phase 2 subagents with the NEW diff + the FULL file context, but prompt them to ONLY report findings on the new commits.
   - In Phase 3, merge new findings with cached findings that still apply (re-verify each cached finding against the current HEAD — is its file:line still valid? has the underlying code changed? if changed, drop with `stale after new commits`).
   - Note in Phase 4 output header: `Mode: partial re-review (N new commits since cached run at <sha>)`.

3. **Cache exists but `last_run_sha` is NOT an ancestor** (force-push, branch reset, etc.): invalidate cache, full fresh run.

After a successful run, write the result to `$CACHE_FILE` at end of Phase 4 (even if the user chose not to post to GitHub — the cache is local, independent of GitHub state).

### Compute shared-package repo map (for Q6 Reusability check)

Inventory the shared packages AND apps in the repo so the Phase 2 reviewer can cross-check new additions against what already exists. Scan BOTH `packages/` and `apps/` — a helper added in `apps/web` may duplicate one in `apps/cli`, and fileseye / next-forge style monorepos split reusable code across both roots.

**Branch on `CROSS_REPO_MODE`**:

- **Local mode** (`CROSS_REPO_MODE=false`): use the local `find` + `grep` approach below. Fast, zero API calls, works offline.
- **Cross-repo mode** (`CROSS_REPO_MODE=true`): use `gh api git/trees` for file inventory and `gh api contents` for on-demand reads. One upfront API call gives you the full tree; exports grep happens per-file during Phase 2 via the reviewer subagent.

```bash
# Cross-repo mode: fetch entire tree of monorepo roots remotely (one API call)
if [ "$CROSS_REPO_MODE" = "true" ]; then
  # Head branch of the PR
  HEAD_BRANCH=$(gh pr view <url> --json headRefName -q .headRefName)

  # Fetch the tree recursively, filter to TS/TSX under packages/ or apps/, cap at 500 entries
  gh api "repos/<owner>/<repo>/git/trees/${HEAD_BRANCH}?recursive=1" \
    --jq '.tree[] | select(.type == "blob" and (.path | test("^(packages|apps)/.*\\.(ts|tsx)$")) and (.path | test("node_modules|dist|build|\\.test\\.|\\.spec\\.") | not)) | .path' \
    | awk 'NR<=500{print} END{if(NR>500)print "[truncated at 500 of " NR " lines — fetch specific paths via gh api contents for details]"}'

  # In cross-repo mode, we DO NOT pre-fetch exports — the reviewer subagent will fetch
  # candidate files via `gh api contents` on-demand during Q6 STEP B. Set:
  repo_map_files="<output above>"
  repo_map_exports="N/A (cross-repo mode — fetch via 'gh api repos/<owner>/<repo>/contents/<path>?ref=<sha>' on-demand)"
  # Note in output header: Mode: cross-repo (no local checkout of <owner>/<repo>)
  exit_this_section
fi

# Local mode (default): scan the cwd with bash-safe globs
```

Run both Bash calls below. **IMPORTANT**: wrap in `bash -c '...'` when shelling out from zsh — raw `packages/*/src` globs abort under zsh with `zsh: no matches found` BEFORE `2>/dev/null` can suppress it, silently emptying the map. Use `find` for robustness against non-standard package layouts (`src/`, `lib/`, `source/`).

```bash
# Repo map files — inventory of TS/TSX files in shared roots (capped 500 lines, truncation marked)
bash -c '
if [ -d packages ] || [ -d apps ]; then
  { [ -d packages ] && find packages -type f \( -name "*.ts" -o -name "*.tsx" \) \
      -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" \
      -not -name "*.test.*" -not -name "*.spec.*" 2>/dev/null
    [ -d apps ] && find apps -type f \( -name "*.ts" -o -name "*.tsx" \) \
      -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" \
      -not -path "*/.next/*" -not -name "*.test.*" -not -name "*.spec.*" 2>/dev/null
  } | awk "NR<=500{print} END{if(NR>500)print \"[truncated at 500 of \" NR \" lines — use Glob directly for ground truth]\"}"
fi
'

# Repo map exports — top-level exports from shared roots (capped 500 lines, truncation marked)
bash -c '
if [ -d packages ] || [ -d apps ]; then
  # find all source-root directories: packages/*/src, packages/*/lib, apps/*/src, apps/backend/src/modules/v1/*/helpers.ts, etc.
  find packages apps 2>/dev/null -type d \( -name src -o -name lib -o -name source \) \
    -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" \
    -not -path "*/.next/*" 2>/dev/null \
    | xargs -I{} grep -rhnE "^export (default (async )?function|function|const|class|type|interface|async function) \w+" {} 2>/dev/null \
    | awk "NR<=500{print} END{if(NR>500)print \"[truncated at 500 of \" NR \" lines — grep packages/ apps/ directly for more]\"}"
fi
'
```

Stash both outputs in main context as `repo_map_files` and `repo_map_exports`. If neither `packages/` nor `apps/` exists (non-monorepo), explicitly set both to `N/A (not a monorepo)` and flag `IS_MONOREPO=false` — the Phase 2 subagent prompt uses this to reroute greps to `src/` and the repo root instead.

**Cross-app helper duplication**: the scan includes `apps/` specifically to catch the case where a new helper in one app duplicates one in another (e.g., `apps/backend/src/modules/v1/feature-a/helpers.ts` vs `apps/backend/src/modules/v1/feature-b/helpers.ts`). The file inventory surfaces both, giving the reviewer visibility into cross-feature duplication that a packages-only scan would miss.

### Check for error-handling touches (flag for Phase 2)

**Grep the diff content** (not filenames) for error-handling patterns in **added or modified lines** (lines starting with `+`):

```
try \{ | catch \( | catch \{ | throw new | throw \s | \.catch\( | Result< | rescue | err := | raise
```

If any pattern appears, OR the user explicitly mentions error handling, set `INCLUDE_SILENT_FAILURE_HUNTER = true`. Otherwise false. Filename-based detection is unreliable — a silent `catch {}` added to `user-service.ts` would never trigger it.

### Check for new database tables (flag for Phase 2)

**Grep the diff content** for new table definitions in **added lines** (lines starting with `+`):

```
pgTable\( | createTable\( | CREATE TABLE | knex\.schema\.createTable | Schema\.create\(
```

If any pattern appears, set `INCLUDE_SCHEMA_CHECKS = true`. Otherwise false.

When true, also extract the **schema directory path** for use in Q7-Q9 searches: look for where existing table definitions matching the detected pattern live (typically `db/schema/`, `drizzle/schema/`, `src/schema/`, or `migrations/`). Stash as `SCHEMA_DIR`. If no schema directory can be identified, set `SCHEMA_DIR = "."` (repo root) and limit Q7-Q9 grepping to files matching the detected table definition pattern (e.g., `Grep("pgTable", ".", glob: "**/*.ts")`) to avoid noise.

**Cross-repo mode**: if `CROSS_REPO_MODE = true`, there is no local repo to scan. Use `gh api git/trees/<head-sha>?recursive=1` to list files and identify the schema directory from the tree. Q7-Q9 searches use `gh api repos/<owner>/<repo>/contents/<path>?ref=<head-sha>` to read schema files remotely.

### Load project-level review suppressions

Check for a `.claude/review-suppressions.yml` file in the project root. This file allows teams to suppress known-acceptable patterns that would otherwise be flagged repeatedly.

```bash
SUPPRESSIONS_FILE=".claude/review-suppressions.yml"
if [ -f "$SUPPRESSIONS_FILE" ]; then
  SUPPRESSIONS=$(cat "$SUPPRESSIONS_FILE")
fi
```

Expected format:

```yaml
suppressions:
  - pattern: "factory pattern"
    category: Architecture
    reason: "YAGNI - single provider by design decision"
    added: 2026-04-13

  - pattern: "missing timeout"
    file: "claude-code.ts"
    reason: "Timeout handled at caller level"
    added: 2026-04-13
```

Fields:
- `pattern` (required): case-insensitive substring matched against a finding's `Issue` text
- `category` (optional): if set, only suppress findings with this exact Category
- `file` (optional): if set, only suppress findings whose `File` path contains this string
- `reason` (required): why this pattern is suppressed — logged in Filtered Out for auditability
- `added` (optional): when the suppression was added — helps with periodic cleanup

If the file exists, pass its contents into the Phase 2 reviewer subagent prompt as:

```
## Review suppressions (from .claude/review-suppressions.yml)
The following patterns are intentionally suppressed — do NOT flag them:
<suppressions content>
```

This lets the reviewer skip suppressed patterns upfront, reducing noise before the critic pass. Phase 3 also applies suppressions as a safety net (see Step 5.5).

**Cross-repo mode**: in `CROSS_REPO_MODE=true`, the local filesystem check won't find the PR repo's suppressions file. Fetch it via `gh api repos/<owner>/<repo>/contents/.claude/review-suppressions.yml?ref=<head-sha>` instead. If the file doesn't exist (404), skip suppressions as normal.

---

## Phase 2: Parallel review (subagents)

Launch in a **single message with multiple Agent tool calls** — but the dispatch strategy depends on `SIZE_MODE` (set in Phase 1).

### Dispatch strategy by SIZE_MODE

**`SIZE_MODE == "solo-main"`** (PR < 100 lines):
- Do NOT dispatch subagents at all. Run the Claude reviewer prompt (Subagent 1 block below) inline in main context. Main reads the stashed diff once, answers Q1-Q6 (and Q7-Q9 if `INCLUDE_SCHEMA_CHECKS = true`), does grounding pass, populates `reusability_searches:`, and outputs in the same format as the subagent version would.
- Still dispatch CodeRabbit reviewer (if not paused) and silent-failure hunter (if triggered) — these are fast fixed-cost subagents and save main context. They run in parallel with main's inline work.
- Rationale: on a 50-line PR, spinning up a dedicated reviewer subagent costs ~5 minutes wall time for work main can do in ~30 seconds.

**`SIZE_MODE == "parallel-standard"`** (100-500 lines, default):
- Dispatch Claude reviewer (Subagent 1, includes Q7-Q9 if `INCLUDE_SCHEMA_CHECKS = true`) + CodeRabbit (Subagent 2) + conditional silent-failure hunter (Subagent 3) in parallel.

**`SIZE_MODE == "parallel-chunked"`** (500-2000 lines):
- Split the diff by file into chunks of ~500 lines each. Group by file boundary — don't split a file across chunks.
- Dispatch ONE Claude reviewer subagent PER CHUNK, each with:
  - Full intent model + prior review timeline + repo map + schema context (shared context)
  - Only its chunk's files listed in the prompt (Q7-Q9 included if `INCLUDE_SCHEMA_CHECKS = true`)
  - Instruction: "Your scope is the files listed above. Do not report findings in other files. Cross-file references are allowed if they help contextualize a finding within your scope."
- Still dispatch ONE CodeRabbit (full PR scope, it handles size internally) and ONE silent-failure hunter (full PR scope).
- Main-context critic in Phase 3 Step 1 dedupes across chunks using the existing `(file, line, symbol)` dedupe key — chunks were file-disjoint so no dupes within-chunk are possible; cross-chunk dupes only occur for findings that span files.

**`SIZE_MODE == "parallel-chunked-confirm"`** (> 2000 lines):

Use AskUserQuestion:

   Question:
     header: "Large PR"
     text: "This PR is <N> lines. Chunked review will dispatch <M> parallel reviewer subagents (one per ~500-line chunk) plus CodeRabbit and silent-failure hunter. Expected wall time: 2-4 minutes."
     options:
       - label: "Continue"
         description: "Proceed with chunked parallel review"
       - label: "Cancel"
         description: "Abort — consider breaking into smaller PRs or re-run with --force-chunked"

On "Continue": proceed with `parallel-chunked` behavior. On "Cancel" or "Other": print suggestion and exit.

### Degraded-mode rule

If **any** Phase 2 subagent errors out or returns empty, continue with the remaining reviewers and note `<reviewer> unavailable` in the Phase 4 output header. **Only abort** if ALL Phase 2 subagents fail.

**CodeRabbit paused special case**: if `CODERABBIT_PAUSED=true` (set in Phase 1), skip Subagent 2 dispatch entirely. This is not a failure — it's a known state. Note in header: `CodeRabbit: skipped (paused — active development)`.

### Subagent 1 — Claude reviewer (`general-purpose`)

Prompt:

```
You are reviewing a GitHub PR for a human reviewer who wants accurate, critical
findings — NOT style nitpicks, NOT generic praise, NOT hallucinated issues.

## Ground truth (from linked issue + PR description)
Goal: <from Phase 1>
Expected touches: <from Phase 1>
Out of scope: <from Phase 1>
Prior findings already reported (do NOT re-report unless you have a correction): <from Phase 1>

PR URL: <url>

## Review suppressions (from .claude/review-suppressions.yml)
<If SUPPRESSIONS loaded in Phase 1, include: "The following patterns are intentionally suppressed — do NOT flag them:" followed by the suppressions content. If no suppressions file exists, include: "None">

## Shared package repo map (for Q6 reusability check)

### Files in shared packages
<repo_map_files from Phase 1, or "N/A (not a monorepo)">

### Exported symbols in shared packages
<repo_map_exports from Phase 1, or "N/A">

This map is your baseline for Q6. It may be truncated at 500 lines — for
thorough checks you may Grep/Glob packages/ directly.

## Schema review context
INCLUDE_SCHEMA_CHECKS: <true|false, from Phase 1>
SCHEMA_DIR: <path from Phase 1, "." if directory unknown, or "N/A" if INCLUDE_SCHEMA_CHECKS is false>

## Your task

1. Run `gh pr diff <url>` to fetch the full diff.
2. Run `gh pr view <url> --json files` to get the file list.

3. **GROUNDING PASS — MANDATORY, do this BEFORE answering any Q.**
   Write 3–5 bullets describing what this diff changes MECHANICALLY:
   - Which files are touched and in what way (added / modified / deleted / renamed)
   - Which functions / classes / schemas change and how
   - What the observable behavior change is
   Every subsequent finding MUST trace back to one of these bullets. If a
   finding doesn't trace to a grounding bullet, you are hallucinating it —
   drop it before outputting.

4. Answer Q1–Q6 EXPLICITLY (plus Q7–Q9 if `INCLUDE_SCHEMA_CHECKS` is true). Each must be addressed, even if just "no issues".

   Q1. Intent — Does this PR actually solve the stated goal? Where's the gap, if any?
   Q2. Unnecessary changes — Files, abstractions, config, or indirection not
       required by the goal? (This deliberately collapses scope creep +
       overengineering into one question; reporting them separately produces
       intra-reviewer duplicates.)
       Q2a. Documentation necessity — For any `.md` file with > 200 added lines
            OR accounting for > 40% of the PR's total additions: question whether
            the documentation is needed. Check if `CLAUDE.md` or existing project
            docs already cover the domain. Frame as observation, not bug.
            Severity: Minor. Category: Unnecessary.
       Q2b. Premature complexity — Detect known complexity patterns in the diff
            that are NOT mentioned or implied in the linked issue:
            - Optimistic locking (`version` columns with default 1)
            - Soft-delete on append-only/audit tables
            - Denormalized aggregation columns (e.g., `totalPrice` alongside line items)
            - Polymorphic reference patterns
            - Self-referential FKs (e.g., `parentOrderId`)
            If `INCLUDE_SCHEMA_CHECKS` is true AND the project already uses the
            same pattern in existing tables (detectable via `$SCHEMA_DIR` search),
            do NOT flag it as premature. If `INCLUDE_SCHEMA_CHECKS` is false, skip
            the existing-pattern search and flag the pattern as-is.
            Flag as: "Design decision — [pattern] is not mentioned in the linked
            issue. Confirm this complexity is needed."
            Severity: Minor. Category: Architecture.
   Q3. DRY — Duplicated logic within the diff, or with existing code visible
       in the surrounding context?
   Q4. Performance — N+1 queries, loops over async, unbounded allocations,
       missing Promise.all, missing indices for new WHERE clauses, sequential
       awaits that could be parallel?
   Q5. Security & Data Integrity — Injection, auth bypass, unsafe input handling, secrets in
       code, missing authorization checks, unvalidated user input reaching
       dangerous sinks, AND type-coercion bugs at data boundaries.

       **Type-coercion at write sites** (subtle, test-only-caught bug class):
       scan every DB insert/update / API payload construction in the diff for
       expressions like `field: value?.toFixed(N)`, `field: String(value)`, or
       `field: \`${value.toFixed(N)}\`` being written into fields typed as
       numeric. Because `.toFixed()` returns a string, this silently stores a
       string in a numeric column (or ships a string in a number-typed API field).
       Pattern:
       ```ts
       quantity: input.quantity?.toFixed(1)          // BUG: stores "2.6"
       quantity: `${input.quantity?.toFixed(1)}`     // BUG: template literal also string
       quantity: Number(input.quantity?.toFixed(1))  // OK
       ```
       Coercion methods to scan: `.toFixed`, `.toString`, `.toLocaleString`,
       `String(...)`, and any template-literal `` `${...}` `` containing those.
       Flag when the expression is NOT wrapped in `Number(...)` / `parseFloat(...)` /
       `parseInt(...)` / unary `+(...)`.

       **How to determine "numeric field" type**:
       - **DB writes**: read the schema file at `$SCHEMA_DIR` (from Phase 1 `INCLUDE_SCHEMA_CHECKS` gating) OR grep the repo for the field name's column definition (`<fieldName>: numeric|integer|real|decimal|double|float|bigint`). If `$SCHEMA_DIR` is unset AND the field's column type cannot be determined, **skip this check for that field** — do not guess.
       - **API payloads / DTOs**: read the matching Zod schema (`z.number()`, `z.coerce.number()`) or TypeScript type (`: number`). If the DTO can't be located, skip the check.

       Severity: Serious. Category: Breaking-change.

   Q6. Reusability (codebase-wide) — MANDATORY tool-use check.

       BEFORE answering, perform tool-based discovery. An empty or missing
       `reusability_searches:` audit field means this check was not
       performed; the critic will drop your "No issues" claim and flag it
       as shallow.

       STEP A — Enumerate NEW definitions added in the diff.
         For each new definition of the following kinds, write one line:
           "added <kind> <name> in <file>"

         Kinds to enumerate (do NOT restrict to top-level exports):
           - function (top-level: `function x()`, `const x = () =>`, `const x = function`)
           - class
           - interface, type alias
           - exported const (including React components as arrow-function consts)
           - React component (function or const form)
           - React hook (name starts with `use`)
           - **class method** (IMPORTANT — this includes NestJS service methods
             like `async findOne(...)`, `private formatInvoice(...)`,
             `protected validate(...)`. These are inside existing classes but
             are still new code that can duplicate shared helpers. The user's
             primary real-world example was a private method on a NestJS
             service — do NOT skip these.)
           - default-exported function or class (`export default function X`,
             `export default class X`)

         Skip ONLY when ALL THREE hold:
           (a) the definition is < 5 lines of real logic, AND
           (b) its name does NOT match any symbol in `repo_map_exports`
               (case-insensitive root match), AND
           (c) it's purely a re-export, type alias trivially renaming
               another type, or a one-line wrapper.

         If ANY of (a)/(b)/(c) fails, enumerate the item. This catches
         the "4-line private helper that duplicates a 4-line shared
         helper" case — small-but-duplicated is still slop.

       STEP A-2 — Scan for raw HTML elements in JSX/TSX files.
         For each file in the diff that is .tsx or .jsx, scan for
         usage of FLAGGED elements in JSX expressions (return
         statements, variable assignments, ternaries, array maps):
           div, span, button, input, a, img, p, h1-h6,
           ul, ol, li, textarea, select, label
         This feeds Q6d — skip if the file is inside the component
         library directory (e.g., packages/ui/src/) or no component
         library is detected in the project.

       STEP B — For each enumerated item, run searches AGGRESSIVELY.
         Run ALL of the following; do NOT stop at the first hit. We pay
         for thoroughness with tokens, not with missed findings.

         1. Exact-name search:
            - Grep("<name>", "packages/")
            - Grep("<name>", "apps/")     (for cross-app duplication)

         2. Semantic-root search — extract the root by DROPPING domain
            prefixes/suffixes and searching the remaining verb/noun:

            Algorithm for deriving the root:
              a) Split name on CamelCase boundaries: `renderUserCard`
                 → `[render, User, Card]`
              b) Drop tokens that are DOMAIN nouns (Order, Invoice,
                 Product, Customer, Account, User, Subscription, etc.
                 — any business-entity noun specific to the project)
              c) Keep tokens that are GENERIC verbs/nouns (format, parse,
                 validate, build, sleep, chunk, retry, merge, group,
                 sort, filter, map, find, compute, calculate, build,
                 extract)
              d) Grep each kept token against packages/ and apps/

            Worked examples:
              - `renderUserCard` → drop `User` (domain) → roots = `render`, `Card` → `Grep("render", "packages/")` + `Grep("Card", "packages/")`
              - `validateOrderInvoice` → drop `Order`, `Invoice` (domain) → root = `validate` → `Grep("validate", "packages/")`
              - `UserBadge` (React component) → drop `User` → root = `Badge` → `Grep("Badge", "packages/ui/src/components/")`
              - `sleep` (no CamelCase) → root = `sleep` → `Grep("sleep", "packages/")`
              - `getMonthlyOrderSummary` → drop `Order` (domain) → roots = `get`, `Monthly`, `Summary` → `Grep("getSummary", "packages/")` + `Grep("summary", "packages/")`

         3. UI component search (for any new React component added in
            apps/*/src/components/ or packages/*/src/components/):
            - Grep("<ComponentName>", "packages/ui/src/components/")
            - Glob("packages/ui/src/components/**/<kebab-case-name>*.tsx")
            - Glob("packages/ui/src/components/**/<kebab-case-name>*.ts")

         4. For each candidate hit from the above, Read the file and
            confirm it is a REAL semantic match (not a substring
            collision — e.g., `formatter.ts` matching on `format` does
            NOT automatically mean the new code duplicates the existing
            one). Record `verified: yes — <what the existing impl does>`
            or `verified: no — substring collision`.

       STEP C — Report findings in four sub-buckets:

         Q6a. Reimplements existing code (default Severity: SERIOUS;
              escalate to CRITICAL if the existing thing lives in an
              auth / validation / crypto package)
              <finding with concrete existing file:path to reuse>
              OR "No issues"

         Q6b. Candidate for extraction to a shared package
              (default Severity: SERIOUS)
              Flag ONLY if ALL three hold:
                (1) fully generic — NO domain types anywhere in the
                    SIGNATURE **or the function body**. "Domain type" =
                    any type naming a business entity (Order, Invoice,
                    Product, Customer, Account, User, etc.). Primitives
                    (`string`, `number`, `boolean`, `Date`) and
                    parametric generics (`T[]`, `Record<K,V>`) ARE
                    generic. Important: if the signature is generic but
                    the body reads domain-specific properties
                    (`arg.portionId`, `order.items[i].quantity`), it is
                    NOT generic. READ the body before flagging.
                (2) > 10 lines of real logic (not a type alias or
                    one-line wrapper)
                (3) a suitable shared package ALREADY exists to host it
                    (e.g., @fileseye/utils, @fileseye/try-catch,
                    @fileseye/errors). Suggesting "create a new shared
                    package" is NOT Q6b — that's scope creep.

              Worked examples:
                • `function chunk<T>(arr: T[], size: number): T[][]`
                  with 12 lines of pure array logic → FLAG (generic,
                  utils package exists).
                • `function renderUserCard(u: User): string` →
                  DO NOT FLAG (User is domain).
                • `function sleep(ms: number): Promise<void>` → DO NOT
                  FLAG (< 10 lines of real logic).
                • `function groupBy<T, K>(arr: T[], key: (x: T) => K)`
                  with 15 lines → FLAG if shared utils exists.
                • `function summarize(items: unknown[])` that reads
                  `items[i].quantity` internally → DO NOT FLAG (body
                  knows about domain shape).

              When in doubt, prefer "No issues" — false positives here
              waste the user's time arguing about extraction.
              <finding with target package path>
              OR "No issues"

         Q6c. Inline block should be extracted as a local helper
              (default Severity: MODERATE)
              3+ lines of similar logic repeated within a single file,
              should be extracted as a local helper function.
              <finding with suggested helper name>
              OR "No issues"

         Q6d. Raw HTML element should use design system component
              (default Severity: MODERATE; escalate to SERIOUS when
              the element is used for layout/structure — e.g., div as
              container, wrapper, or layout grid — where Box/Stack/Flex/
              Grid equivalents are standard)

              FLAGGED ELEMENTS (check only these in JSX):
                div, span, button, input, a, img, p, h1-h6,
                ul, ol, li, textarea, select, label

              EXEMPT — never flag these (semantic/specialized, no
              typical component equivalent):
                canvas, video, audio, table, thead, tbody, tr, td,
                th, form, svg, nav, header, footer, main, section,
                article, aside, dialog, details, summary, fieldset,
                legend, pre, code, blockquote, hr, br, iframe

              BUILT-IN EXCLUSIONS — skip the check when:
                (a) The file is INSIDE the component library itself
                    (e.g., packages/ui/src/, or the project's design
                    system source directory). These files BUILD the
                    primitives — raw HTML is expected.
                (b) The project has NO component library detected
                    (no packages/ui/, no design-system directory,
                    no imports from a component library in the diff).
                    Do not flag raw HTML if there's nothing to
                    replace it with.

              DETECTION — for each flagged element found in STEP A-2:
                1. Check if the project's component library exports
                   a matching component (search packages/ui/src/
                   or the project's component library path).
                2. Check if the diff already imports from a component
                   library (e.g., imports from @project/ui, shadcn,
                   chakra, etc.) — this signals a library IS in use
                   and raw HTML is likely a miss.
                3. Only report if a concrete component alternative
                   exists. Do NOT guess — if no match is found,
                   write "No issues".

              Finding format example:
                Severity:    Moderate (or Serious for layout/structure)
                Confidence:  high | medium
                File:        <path:line>
                Category:    Reusability
                Issue:       Raw `<div>` used for layout — use `<Box>` / `<Stack>` from the design system instead.
                Why it matters: Raw HTML bypasses design system tokens (spacing, theming, responsive behavior), creating visual inconsistency and maintenance burden.
                Suggested fix: Replace `<div className="...">` with the matching component from the component library.

              OR "No issues"

       REQUIRED audit field — use this EXACT name `reusability_searches:`
       (not `reuse_searches` or any variant) so the Phase 3 critic can
       parse it:

         reusability_searches:
           - <tool>("<query>", "<path>") → <N> matches
             verified: <yes|no> — <if yes: what the existing impl does
                                    and whether it's a real match;
                                    if no: substring collision or wrong
                                    semantic>
           - ...

         AT LEAST one entry per item enumerated in STEP A.
         For each search where N > 0, `verified:` is MANDATORY — the
         critic rejects audits that claim "0 matches" for all searches
         as shallow / suspicious. If N == 0, write `verified: n/a`.

         For Q6d, include component library searches in the audit:
           - Grep("<ComponentName>", "packages/ui/src/components/") → N matches
             verified: yes — <ComponentName> exists at <path>
         If no component library detected, write:
           "Q6d: N/A (no component library detected in project)"
         If STEP A-2 found no flagged elements, write:
           "Q6d: N/A (no flagged raw HTML elements in diff)"

         If STEP A was empty AND STEP A-2 was empty, write EXACTLY:
           "reusability_searches: N/A (no new top-level definitions or raw HTML elements in diff)"

       ### Non-monorepo fallback (when `repo_map_files == "N/A"`)

       If the Phase 1 repo map is `N/A (not a monorepo)`, the project
       has no `packages/` or `apps/` directory. Reroute your searches:
         - Grep("<name>", "src/") — primary source root
         - Grep("<name>", ".") — repo root (will include node_modules;
           filter mentally)
         - Still run the dead-link check and verified: sub-field.
       Don't claim "No issues" just because the default `packages/`
       search returns zero — it doesn't exist. Search where the code
       actually lives.

       ### Q6 known limitation — existing helpers on alternate code paths

       Q6's STEP A / STEP B enumerates NEW definitions and checks whether
       they duplicate EXISTING shared code. It does NOT catch the case
       where an existing helper is already called on SOME code paths in
       the same file but should ALSO be called on others — e.g., an
       early-return that hardcodes a synthetic response for a field that
       a helper computes on the happy path.

       Worked example (the class of bug Q6 misses):

         async getUserInvoices(...) {
           const activeUsers = await this.getActiveUsers(...)
           if (activeUsers.length === 0) {
             return { summary: [], invoiceItems: [] }  // ← hardcoded []
           }
           // ... late path ...
           const invoiceItems =
             await this.invoiceItemsService
                       .getByUserAndDateRange(...)
           return { summary, invoiceItems }
         }

       The early return silently drops stored `invoiceItems` because
       the helper is only invoked on the late-path. Q6's
       `reusability_searches:` audit won't flag this — nothing was NEWLY
       added, so STEP A enumerates nothing to search for. The gap exists
       in control flow, not in symbol duplication. The class is
       discoverable only by pattern-matching on MODIFIED or NEW
       early-return / alternate-branch statements.

       When you see a NEW or MODIFIED early-return that builds a
       synthetic response object with empty fields (`[]`, `null`, `{}`,
       `undefined`) — especially inside a function that imports or
       injects a service — check whether any of those empty fields are
       populated by a helper already used on another branch in the same
       function. If so, flag it under:

         - **Q3 (DRY)** — when the duplication is within the current
           diff, OR
         - **Prior-finding-correction** — when a prior reviewer raised
           it and the author did not address it, OR
         - **Silent-failure** — when the synthetic empty value causes a
           user-visible behavior gap (e.g., stored values disappear from
           the UI in empty states).

       Do NOT flag it under Q6 — the reusability_searches audit has no
       field to record a control-flow finding, and the Phase 3 critic
       will drop Q6 findings that lack a matching audit entry. Populate
       grounding and evidence in the main finding body instead. If you
       uncover this class, include it in your grounding pass bullets so
       the critic can verify it against the diff directly.

5. Additionally flag:
   - Silent failures (caught errors swallowed without logging)
   - Removed error handling
   - Breaking changes to public APIs not mentioned in the PR description
   - Architectural issues (wrong layer / wrong package / wrong abstraction boundary)

6. **Schema-specific checks (Q7–Q9)** — only when `INCLUDE_SCHEMA_CHECKS = true` (PR adds new database tables). Skip entirely if false.

   Q7. Schema Overlap — Does a new table duplicate an existing table's domain?

       For each new `pgTable()` (or equivalent) definition in the diff:
       a. Extract domain keywords from the table name (e.g., `gs_KioskItems` →
          `kiosk`, `item`).
       b. Add FK target roots as additional keywords (e.g., FKs `recipeId`,
          `articleId` → keywords `recipe`, `article`).
       c. Search `$SCHEMA_DIR` for tables with matching keywords:
          ```
          Grep("<keyword>", "$SCHEMA_DIR", type: "ts")
          ```
       d. For each hit, read the file and compare FK targets and field names.
       e. Flag ONLY if an existing table has **3+ matching FK targets** AND a
          similar domain purpose (both tables serve the same feature area — e.g.,
          both handle ordering, both handle menu planning). Substring matches
          alone (e.g., "item" matching many unrelated tables) are NOT sufficient
          — verify by FK comparison AND domain overlap.

       Severity: Moderate. Category: Architecture.
       Format: "Existing table `<existing>` in `<path>` has overlapping domain —
       shares FKs [list]. Is `<new table>` intentionally separate?"

   Q8. Table Consolidation — Could a simple 1:1 table be a column on an existing table?

       For each new table definition in the diff, detect where:
       a. The PK is also an FK to another table (pattern: `accountId` / `clientId`
          as both primary key and foreign key).
       b. The table has fewer than 5 data columns beyond the PK (exclude standard
          audit columns like `createdAt`, `updatedAt`, `createdBy`, `updatedBy`
          from this count).

       If both conditions are met:
       c. Search for existing settings/config tables for the same parent entity:
          ```
          Grep("<parent>.*setting|<parent>.*config", "$SCHEMA_DIR", type: "ts")
          ```
       d. Flag ONLY if a candidate settings/config table EXISTS. Do NOT suggest
          "create a settings table" — that is scope creep.

       Severity: Moderate. Category: Architecture.
       Format: "1:1 table `<new>` has only N data columns — could this be a
       column on existing `<settings table>` in `<path>`?"

   Q9. Cross-Table Field Consistency — Are entity reference columns complete?

       When a new table has entity reference FKs (to `recipeTable`, `articleTable`,
       `foodItemTable`, `dishTable`, etc.):
       a. Identify the "entity reference set" — which entity types does it reference?
       b. Search for related tables in the same domain (tables sharing the same
          parent FK or domain name keywords).
       c. Compare entity reference sets between the new table and related tables.
       d. Flag ONLY when a related table in the SAME domain has MORE entity types.
          Do NOT flag cross-domain differences (e.g., procurement items vs shop items
          may intentionally support different entity types).

       Severity: Moderate. Category: Architecture.
       Format: "New table references [recipe, article] but related `<table>` in
       `<path>` also references [foodItem, dish] — are these intentionally omitted?"

## Anti-slop rules (MANDATORY)

- Do NOT report style, formatting, or naming preferences.
- Do NOT re-report Prior findings. **Exception**: if you believe a prior
  finding was wrong, you MAY report it with `Category: Prior-finding-correction`
  and a concrete explanation of why.
- Do NOT report hypothetical issues ("this COULD become a problem if X") unless
  X is plausible given the actual codebase signals visible in the diff.
- Do NOT report issues you cannot point to with `File: <path>` — ideally
  `File: <path:line>`. Line number is optional for findings that are genuinely
  file- or module-scope (these route to file-level review comments in Phase 4).
- Do NOT report generic advice ("consider adding tests") unless tests were
  expected and omitted.
- If a question (Q1–Q9, except Q6 which has dedicated audit rules) has NO issues,
  write "No issues" — do not invent findings to fill the slot.
- **Permission to abstain**: if answering Q1–Q9 (except Q6) requires code you haven't
  seen (e.g., a callee not in the diff), either fetch it via
  `gh api repos/<owner>/<repo>/contents/<path>?ref=<head-sha>` or write
  `Cannot assess — would need <file>` and move on. DO NOT guess.
- Low-confidence findings at Moderate or Minor severity WILL be dropped by
  the critic. Only flag them if you think a human should still take a second
  look.
- For Q6, you MUST populate `reusability_searches:` with actual tool calls
  or write "N/A (no new top-level definitions or raw HTML elements in diff)". Empty or missing
  audit = Q6 claims are INVALID and the critic will drop them.
- Q6b (extraction to shared package) has a HIGH BAR — flag only when ALL
  three conditions hold. Do NOT flag domain-specific code as "should be
  shared". When in doubt, prefer "No issues".
- Q6d (raw HTML elements) requires a CONFIRMED component library match.
  Do NOT flag raw HTML if the project has no component library or the
  specific element has no matching component. When in doubt, skip.

## Line number convention

Any `File: <path:line>` reference must use the **post-image line number** —
the line number as it appears in the new version of the file (the `+` side
of the unified diff hunk, or unchanged-context on the new side). Do NOT use
the old-side line number. Do NOT use a diff hunk header offset.

## Output format

For each finding:
  Severity:   Critical | Serious | Moderate | Minor
  Confidence: high | medium | low
  File:       <path:line> (or <path> alone for file/module-scope findings)
  Category:   Intent | Unnecessary | DRY | Performance | Security |
              Reusability | Silent-failure | Breaking-change |
              Architecture | Prior-finding-correction
  Issue:       <one sentence>
  Why it matters: <one sentence>
  Suggested fix:  <one sentence, actionable>

End with:
  Senior engineer approval: Yes | No | With changes
  Approval reason: <one sentence>
  Summary: <3 sentences — what the PR does, biggest concern, overall verdict>
  Verdict: approve | comment | request-changes
```

### Subagent 2 — CodeRabbit reviewer (`coderabbit:code-reviewer`)

Pass the intent model + prior findings so CodeRabbit can filter its own output upfront (reduces critic workload).

Prompt:

```
Review the GitHub PR at <url> for bugs, security issues, and quality problems.
Focus on concrete, actionable findings with file:line references (use post-image
line numbers — the new-file side of the diff).

Ground truth for this review:
Goal: <from Phase 1>
Out of scope: <from Phase 1>
Prior findings already reported (do not re-report): <from Phase 1>

Skip style / nitpick findings unless they mask a behavior bug.
```

### Subagent 3 (conditional) — Silent-failure hunter

Only dispatch if `INCLUDE_SILENT_FAILURE_HUNTER = true`.

- `subagent_type`: `pr-review-toolkit:silent-failure-hunter`
- Prompt: `"Check for silent failures, swallowed errors, and inadequate error handling in the GitHub PR at <url>. Fetch the diff yourself via 'gh pr diff <url>'."`

---

## Phase 3: Critic pass (main context)

After ALL subagents return, main Claude does the critic pass directly. **No subagent.** Main context already holds the intent model and prior reviews — no point re-loading them into a fresh subagent context.

Execute in order:

### 1. Dedupe

Merge findings that describe the same issue **both** across reviewers AND within a single reviewer's output.

**Dedupe key**: `(file_path, post_image_line, normalized_symbol_name)` — NOT `Category`. For findings without a valid diff line (file-level findings), use `"file-level:<category>"` in place of `post_image_line` (e.g., `(config.ts, file-level:Architecture, missingvalidation)`) — the category suffix prevents two different file-level findings on the same file from colliding. For line-level findings, two findings on the same `(file, line, symbol)` are duplicates regardless of category — merge them, keep the higher-severity category, and concatenate their reasoning into the `Issue:` field. For file-level findings, the category is part of the key, so findings with different categories on the same file are distinct (not merged).

Normalize symbol names by lowercasing and stripping CamelCase boundaries (`renderUserCard` → `renderusercard`) so minor label variants still match.

Dedupe priority when merging:
1. **Severity wins**: keep `Serious > Moderate > Minor`.
2. **Category precedence for ties**: `Security > Reusability > Silent-failure > Breaking-change > Performance > DRY > Unnecessary > Intent > Architecture`.
3. **Confidence**: keep highest.

### 1.5. Cheap mechanical pre-checks (line-count sanity)

Before the expensive Step 2 diff verification, do a cheap mechanical pre-check on EVERY finding (not just Critical/Serious). This catches a common hallucination pattern where the reviewer produces a line reference far beyond the file's actual length (e.g., citing `SomeComponent.tsx:839-853` for a 258-line file) — a reference that slips past Step 2's top-severity-only check but is obviously invalid on a cheap line-count sanity test.

For each finding with a `File: <path:line>` reference:

1. Compute `max_valid_line(path)` from the `gh pr view --json files` data already fetched in Phase 1:
   ```
   max_valid_line = file.additions_total + max(0, existing_lines_before_pr)
   ```
   For a NEW file: `max_valid_line = file.additions`.
   For a MODIFIED file: `max_valid_line ≈ file.additions + file.deletions_original_side + ~200 buffer` — to be safe, fetch the HEAD file length via `gh api repos/<owner>/<repo>/contents/<path>?ref=<head-sha>` when the finding's line is suspicious.
   Cheap heuristic: if `line > (file.additions + 500)` for a NEW file, it's almost certainly hallucinated.

2. If `cited_line > max_valid_line`:
   - Drop the finding
   - Log in Filtered Out: `hallucinated reference (line <N> exceeds file's <M> available lines)`
   - Do NOT automatically escalate by shifting lines — a line-number-off-by-hundreds finding should be dropped, not rescued. The reviewer subagent was confused.

3. If `cited_line <= max_valid_line`, the finding passes the sanity check and flows into Step 2 for real diff verification.

This pre-check is zero-cost (uses data already in main context from Phase 1's `files` query) and catches the most egregious class of hallucination before the more expensive diff verification fires.

### 2. Verify `file:line`

The full diff is already in main context (stashed in Phase 1). This is *not* token waste — it's the only way main can verify references independently of the subagent's now-discarded context.

- For PRs with `additions + deletions < 500`: verify **all** findings against the stashed diff.
- For PRs `>= 500` lines: verify all Critical + Serious findings. For Moderate/Minor findings on files not fully in the stash, fetch the per-file patch via:
  ```bash
  gh api repos/<owner>/<repo>/pulls/<num>/files --jq '.[] | select(.filename=="<path>") | .patch'
  ```
  (The endpoint returns a per-file `patch` field — that's the full unified diff for that file, capped at ~3000 lines per file by GitHub.)
- **Routing**: if the finding has a line number → apply line verification (below). If no line number → skip to file-level verification (below). These are mutually exclusive paths.
- **Line verification rule**: the `File: <path:line>` must refer to a line present on the **post-image / new side** of the hunk (a `+` line or unchanged context on the new side). References to old-side-only lines, deleted lines, or lines not present in any hunk → **DROP** and log `hallucinated reference`.
- **File-level verification rule** (no line number): verify that the referenced `path` appears in the PR's changed files list (from `gh pr view --json files` already fetched in Phase 1). If the path is not in the changed files → **DROP** and log `hallucinated file reference`.

### 3. Drop already-known

If a finding matches "Prior findings" from Phase 1 (and is NOT marked `Prior-finding-correction`): **DROP** and log `already reported in prior review`.

### 4. Challenge with the concrete 3-prong test

For each remaining finding, drop it **only if ALL three** hold:

- (a) the symptom is purely cosmetic or a nit
- (b) no user-visible behavior changes if ignored
- (c) no downstream refactor cost

Keep the finding if **ANY one** of the three fails. Log drops as `noise / 3-prong test`. This replaces vibes-based "would a senior engineer care?" with a falsifiable test.

### 4.5. Reusability audit verification

For each reviewer's "Q6 No issues" response, execute the verification below. The goal is to catch four distinct failure modes: missing audit field, insufficient search count, class-method definitions not being counted, and raw HTML elements not checked against the component library (Q6d).

#### Step 4.5a — Count new definitions in the diff

Count added lines (starting with `+`) in the stashed diff that match ANY of these patterns:

```
+\s*(export\s+(default\s+)?)?(async\s+)?(function|class|interface|type)\s+\w+
+\s*(export\s+)?const\s+\w+\s*(:\s*[^=]+)?=\s*(async\s+)?(\([^)]*\)|[a-zA-Z_$][\w$]*)\s*=>
+\s*(export\s+default\s+function|export\s+default\s+class|export\s+default\s+async\s+function)\s+\w+
+\s+(private|protected|public|async|static)(\s+(private|protected|public|async|static))*\s+\w+\s*\(
```

The four patterns cover:
1. Standard `function`/`class`/`interface`/`type` (with optional `export`, `export default`, `async`)
2. Arrow-function const exports: `export const myFn = () =>` (React component / hook form)
3. Default-exported functions/classes (Next.js pages, default React components)
4. **Class methods inside class bodies** — `private formatInvoice()`, `async findOne()`, `public validate()`. This is the critical pattern for NestJS-style services where new "functions" live as class methods. Only count method declarations that appear INSIDE a class block (track `{`/`}` nesting from the nearest `class X {` on the new side of the hunk).

Combine the four pattern counts into `new_definitions_count`.

#### Step 4.5b — Count and parse the audit

Look for the audit field using a lenient match: `(?:reusability|reuse)_searches?:`. The canonical form is `reusability_searches:` but accept `reuse_searches:` and `reusability_search:` as typos.

Three outcomes to distinguish:

1. **Field entirely missing** (not present in any form): this is PROMPT NON-COMPLIANCE, not a shallow audit. Drop ALL Q6 "No issues" claims AND add a finding:
   ```
   Severity:   Serious
   Confidence: high
   File:       <PR as a whole>
   Category:   Reusability
   Issue:      Reviewer did not include a `reusability_searches:` audit field — Q6 was not performed at all.
   Why:        The reviewer subagent skipped the mandatory Q6 audit. All claims in Q6a/b/c/d are unverified.
   Fix:        Re-run the review, or manually grep packages/ and apps/ for each new definition in this diff before merging.
   ```

2. **Field present with sentinel `N/A (no new top-level definitions or raw HTML elements in diff)`**: verify BOTH `new_definitions_count == 0` (STEP A empty) AND no .tsx/.jsx files in the diff contain flagged raw HTML elements (STEP A-2 empty). If both hold, audit is valid (no action). If either fails, treat as shallow and drop the "No issues" claim per outcome 3 below — the reviewer mis-claimed there was nothing to enumerate.

3. **Field present with entries**: count entries. If `searches_count < new_definitions_count`, drop "Q6 No issues" claims AND add:
   ```
   Severity:   Moderate
   Confidence: medium
   File:       <PR as a whole>
   Category:   Reusability
   Issue:      Reusability check was shallow (<searches_count> searches for <new_definitions_count> new definitions) — manual scan recommended before merging.
   Why:        The reviewer subagent did not run at least one search per new top-level definition. Reusability may have been missed on the unsearched items.
   Fix:        Before merging, grep packages/ and apps/ for each new function / class / component / class method name to confirm no existing implementation is being duplicated.
   ```

   Additionally, for each search entry where `N > 0` but `verified:` is missing or says `no`, mark the reviewer's corresponding Q6a/b claim (if any) as low-confidence. Don't drop it — but note "search returned hits but reviewer did not verify semantic match" in the Filtered Out section.

#### Step 4.5c — Log the drop

Every drop/warning from 4.5a–4.5b goes to the Phase 4 Filtered Out section with its specific reason, so critic behavior is auditable.

```
Severity:   Moderate
Confidence: medium
File:       <the PR as a whole — no single line>
Category:   Reusability
Issue:      reusability check was shallow (<S> searches for <N> new definitions) — manual scan recommended before merging
Why:        The reviewer subagent skipped tool-based discovery for some new definitions; shared-package reuse may have been missed.
Fix:        Before merging, grep packages/ for each new function/component name to confirm no existing implementation is being duplicated.
```

4. Log the drop in the Filtered Out section so over-filtering is auditable.

#### Step 4.5d — Verify Q6d (raw HTML element) claims

If the reviewer reported Q6d findings, verify each one:
  1. Confirm the flagged file is NOT inside the component library directory
     (packages/ui/src/ or equivalent). If it is, drop the finding as
     "Q6d false positive — file is inside component library".
  2. Confirm the `reusability_searches:` audit includes a component library
     search for the suggested replacement component. If missing, mark the
     Q6d finding as low-confidence.
  3. If the reviewer wrote "Q6d: N/A (no component library detected)" but
     the diff imports from a component library (e.g., `import { Box } from
     '@project/ui'`), drop the N/A claim and flag as shallow — a library
     IS in use.

If the reviewer wrote "Q6d: No issues" for a .tsx/.jsx diff that contains
flagged elements AND the project has a component library, mark as suspicious
but do NOT auto-add a finding — the reviewer may have confirmed no match.

### 4.6. Wrapped-coercion false-positive filter

Drop findings that claim a numeric-coercion method returns a string when the
immediate enclosing expression already coerces it back to a number. This is a
class of false positive observed on real PRs where a reviewer saw `.toFixed(4)`
in isolation and flagged it, missing the surrounding `Number(...)` wrapper.

For each finding where the `Issue` mentions one of:
  - `.toFixed(` returning a string
  - `.toString(` returning a string (in a numeric context)
  - `.toLocaleString(` returning a string
  - `String(` coercing to string

Verify the cited code against the stashed diff. The wrapper must be **structurally enclosing**, not just lexically nearby. Match with these anchored patterns on the cited line:

  - `=\s*(Number|parseFloat|parseInt|\+)\s*\(\s*<call>` — assignment RHS starts with a wrapper call that contains `<call>`
  - `:\s*(Number|parseFloat|parseInt|\+)\s*\(\s*<call>` — object literal value starts with wrapper
  - `return\s+(Number|parseFloat|parseInt|\+)\s*\(\s*<call>` — return-statement wrapper
  - `<call>` directly followed by arithmetic `*`/`+`/`-`/`/` with a literal number (e.g., `.toFixed(1) * 1` — rare but explicit coercion)

**Do NOT match when**:
  - `<call>` is a sibling argument to `Number(...)` (e.g., `foo(bar.toFixed(1), Number(y))` — `Number` wraps `y`, not `bar.toFixed`)
  - The wrapper appears on a DIFFERENT line than the cited `.toFixed` call (multi-line wrapper pattern — reviewer can't confirm coverage without AST; leave to human)

→ **DROP** the finding and log in Filtered Out: `wrapped-coercion false positive — .toFixed(N) is inside Number(...) on the same line`.

**Line-local limitation**: this filter only catches same-line wrappers. A multi-line case like `const x = v?.toFixed(1); ...; field: Number(x)` is NOT dropped — the critic can't safely infer the wrapper's coverage across lines without an AST. Such findings fall through to manual review.

**Interaction with Q5 Type-coercion at write sites**: for same-line cases, the two rules are mutually exclusive — Q5 fires when the wrapper is absent (bug), 4.6 fires when the wrapper is present (false positive). For multi-line cases, there's a shared blind spot (Q5 may flag an already-wrapped value whose wrapper is off-line, and 4.6 won't rescue it). Flag the interaction explicitly in the Filtered Out log when relevant.

### 4.7. Intent-alignment filter for "unscoped" findings

Drop/downgrade findings that call a change "unscoped", "semantic drift",
"not in PR description", or "scope creep" when the change IS the PR's intent.
This is a critic failure where the reviewer flagged a feature as a bug.

For each finding with a phrase matching `(?i)unscoped|semantic (drift|change)|not mentioned|not in (the )?description|scope creep|out of scope|outside (the )?stated goal|beyond PR scope|undeclared change|silently changes behavior` in its `Issue` or `Why` field:

1. Tokenize the PR's intent model (title + linked-issue title + first 200 chars of PR body) into keywords:
   - Split on whitespace AND `[_\-\.\/]` AND camelCase transitions
   - Lowercase all tokens
   - Drop tokens ≤ 2 characters (too generic)
   - Filter out stop words (`add`, `fix`, `update`, `refactor`, `use`, `new`, `the`, `a`, `of`, `in`, `for`, `to`, `and`, `or`, `is`, `be`)

2. Tokenize the finding's core claim (the cited `File:` path + the symbol/function name from `Issue`) using the same rules.

3. Compute overlap ratio = `|intent_tokens ∩ finding_tokens| / |finding_tokens|`.

4. **Precondition**: this filter only applies when BOTH `|finding_tokens| >= 3` AND `|intent_tokens| >= 3`. If either side has fewer than 3 tokens after filtering, SKIP this filter entirely — the signal is too noisy to trust.

5. If overlap ≥ 0.5 (at least half the finding's core tokens appear in PR intent):
   - **DOWNGRADE** by one severity level (Serious → Moderate, Moderate → Minor, Minor → stays Minor but add note)
   - Prepend to `Why`: `Note: this change aligns with PR intent ("<intent keywords matched>"). Re-verify before merging — may be intentional.`
   - Log in Filtered Out: `intent-alignment downgrade — <N>/<M> finding tokens match PR intent`

6. If overlap is 1.0 (every finding token is a PR intent token) **AND severity is Minor**:
   - **DROP** entirely. Log: `intent-alignment drop — finding IS the PR's stated goal`
   - **Do NOT drop Moderate or higher** — those surface to the user with the downgrade note; the human can confirm intent

This filter protects against misreading a feature as a bug. Common example: a `COALESCE` / override / new-field / renamed-function change gets flagged as "unscoped semantic change" when the PR title/body makes clear that IS the PR's central mechanism. The reviewer pattern-matched on the change shape without cross-checking intent.

### 4.8. Library-behavior citation filter

Downgrade findings that claim a library has an edge case / bug / quirk
without citing concrete evidence. Reviewers sometimes reason from general
language knowledge (e.g., "JS floats are fragile") without verifying the
specific library's handling.

For each finding where the `Issue` asserts behavior of a named library,
framework, or helper — signals include phrases like:
  - `<Library> does X (wrongly / fragile / unsafe)`
  - `<method>(<args>) returns <unexpected>`
  - `float precision will break this`
  - `IEEE 754 / floating-point / NaN / Infinity` concerns

Check whether the `Why` or `Fix` field contains ANY of:
  - A file path pointing to the library's implementation inside `node_modules/<lib>/` (the path's `<lib>` segment must match the library name in the finding)
  - A URL whose host contains the library name, points to an official docs domain (e.g., `github.com/<org>/<lib>`, `<lib>.dev`, `docs.<lib>.io`), or links to a spec/RFC
  - A reproducible code snippet showing the claim with actual input/output values (not pseudo-code, not prose-only)
  - A linked repo issue or failing test case with a concrete reproduction

**Severity ladder** (tuned to drop low-confidence library claims that lack any concrete evidence — e.g., "`z.number().multipleOf(0.1)` is fragile for floats" flagged as Moderate with no repro, which the library may actually handle internally):

| Original | With citation | Without citation |
|----------|---------------|------------------|
| Critical | Keep as-is | Downgrade to Serious + note |
| Serious  | Keep as-is | Downgrade to Moderate + note |
| Moderate | Keep as-is | **DROP** — log `library-claim drop — Moderate with no citation` |
| Minor    | Keep as-is | **DROP** — log `library-claim drop — Minor with no citation` |

The rationale for dropping at Moderate+Minor: unverified library-quirk claims waste reviewer attention at low severity. At Serious/Critical they're important enough to surface despite uncertainty — with a clear "unverified" note.

On downgrade, prepend to `Why`: `Note: unverified library-behavior claim — requires empirical check (run the code / read the library source) before acting.`

Example class: a reviewer flags `z.number().multipleOf(0.1)` or similar as "fragile for floats" based on general JS float knowledge, without testing. A library that handles IEEE 754 tolerance internally (like Zod does for `.multipleOf`) makes this a false positive — requiring a citation before acting cuts this class of finding.

### 4.9. Default-fallback filter for "dropped field" findings

Downgrade findings that claim a field is "dropped", "not propagated", or
"lost during transformation" when a named constant/default handles the
missing value. Presence of a named default is a strong signal of intentional
design.

For each finding with a phrase matching `(?i)\b(dropped|stripped|lost in|never propagated|not (propagated|passed|forwarded|carried))\b|falls? back to|fallback to` in `Issue` (the identifier usually appears right before these verbs, e.g., `` `someField` is dropped ``):

1. Extract the claimed-dropped field name from the `Issue` text (backtick-quoted identifier, or first camelCase/snake_case token near the matched verb).

2. Search the **stashed diff first** (free — already in context). Only if stashed diff doesn't contain the candidate file's full content, fetch with `gh api contents` (rate-limited — one call per file, cache within the critic pass). Look for:
   - An ALL_CAPS constant whose name contains a segment of the field name: compute the uppercase-joined variants of the field's camelCase tokens (e.g., field `currencyCode` → segments `CURRENCY`, `CURRENCY_CODE`, `CODE`), then match `[A-Z][A-Z0-9_]*<segment>[A-Z0-9_]*` — catches `DEFAULT_CURRENCY_CODE`, `FALLBACK_CURRENCY`, `PRIMARY_CODE`, etc.
   - A camelCase default: regex `\b(default|fallback|initial)[A-Z]\w*\b` whose suffix contains a segment of the field (e.g., `fallbackCurrency`, `defaultCode`, `initialLocale`).
   - A config-object default: `config\.(default|fallback)\w*`, `defaults\.\w+`, `<obj>\.fallback\w*`.
   - An explicit coalesce pattern on the receiving side: `??\s*<const>`, `||\s*<const>`, or `<const>\s*??\s*value`.
   - A comment or JSDoc within 10 lines of the "drop" site saying `(?i)defaults? to|always|intentionally|by design|only\s+\w+\s+(makes sense|is supported|applies)`.

3. If ANY named-default signal is found → **DOWNGRADE** by one severity AND prepend to `Why`: `Note: a named default (<CONST>) handles the absent value — likely intentional design, not a propagation bug.` Log: `default-fallback downgrade — found <CONST>`.

4. If the named default is explicitly documented with `"by design"` / `"only <X> makes sense here"` / `"always <X>"` → **DROP** entirely. Log: `default-fallback drop — documented intentional`.

This filter catches domain-semantics calls the reviewer can't know without
project knowledge. Common example: a field like `localeId` is intentionally
dropped before reaching an exporter that only supports one locale, with a
`DEFAULT_LOCALE_ID` constant handling the absence — the reviewer flags this
as "field dropped" without noticing the named default that makes the drop
intentional.

### 5. Confidence-based drop

Drop all `Confidence: low` findings at Moderate or Minor severity. Log as `low-confidence filler`. **Keep** low-confidence Critical/Serious findings — humans want to see risky-but-uncertain flags even if the reviewer wasn't sure.

### 5.5. Apply project-level suppressions

If `SUPPRESSIONS` was loaded in Phase 1, match each remaining finding against the suppressions list:

For each suppression entry:
1. Check if the finding's `Issue` text contains `pattern` (case-insensitive substring match)
2. If `category` is set, also check that the finding's `Category` matches exactly
3. If `file` is set, also check that the finding's `File` path contains the string

If ALL specified conditions match: **DROP** the finding and log in Filtered Out:
```
suppressed by .claude/review-suppressions.yml: "<reason>" (pattern: "<pattern>")
```

**Critical/Serious override**: suppressions can drop findings at ANY severity. If a team has explicitly decided a pattern is acceptable, that decision should be respected even for Serious findings. The `reason` field in the log ensures this is auditable.

### 6. Gap check (Q1–Q6, Q7–Q9 if schema PR)

For any question category where BOTH reviewers said nothing, briefly think about whether the diff has anything in that category. Add findings if you spot something they missed. Include Q7–Q9 in the gap check only if `INCLUDE_SCHEMA_CHECKS = true`.

**Large-PR caveat**: if `additions + deletions >= 500` AND you don't have the full diff fully loaded in main (e.g., you truncated after stashing), **skip Step 6** and log `gap check not run — PR too large for main context`. Do NOT hallucinate gaps from the file list alone.

### 7. Rank by severity

Critical > Serious > Moderate > Minor.

### 8. Decide verdict (category-aware)

- Any **Critical** → `request-changes`
- Any **Serious** in `Category = Security | Silent-failure | Breaking-change | Reusability` → `request-changes` (category-based escalation — these are never "just a comment"; Reusability is escalated because duplicated/reimplemented code is a correctness risk via divergent fixes and skill drift)
- Any other Serious → `comment` (default — human decides whether to block)
- Only Moderate/Minor → `approve` (with comments)
- No findings → `approve`

### 9. Decide Senior-engineer approval

A binary verdict (with a middle option) that's shown prominently in Phase 4:

- **No** — if verdict is `request-changes`, OR if Q1 identified an intent gap (PR doesn't solve the stated goal), OR if any Critical finding exists
- **With changes** — if Serious findings exist in any category, OR if there are 3+ Moderate findings
- **Yes** — otherwise

Write a one-sentence approval reason grounded in the most important finding (or the absence of findings — e.g., "Does what the issue asks, no Serious issues, no scope creep").

---

## Phase 4: Output

### Print this block to the terminal, always

```
# PR Review: <title> (#<number>)

**Senior engineer approval**: <emoji> <Yes | No | With changes> — <one-sentence reason>
**Verdict**: <emoji> <approve | comment | request-changes>
**Goal**: <intent goal>
**Size**: <additions>/<deletions> across <N> files
**Reviewers**: <list, with "(unavailable)" marker for any failed subagent>

## Summary
<2-3 sentence summary>

## Findings (<count>)

### Critical
<entries>

### Serious
<entries>

### Moderate
<entries>

### Minor
<entries>

## Filtered out (<count>)
<dropped findings with reasons — for auditability>
```

### Verdict and approval emoji mapping

Use these emojis for instant visual scanning — the emoji MUST appear before the text:

**Senior engineer approval:**
- Yes → ✅ Yes
- No → ❌ No
- With changes → ⚠️ With changes

**Verdict:**
- approve → ✅ `approve`
- comment → 💬 `comment`
- request-changes → ❌ `request-changes`

**Finding severity headers** (in the ## Findings section):
- Critical → 🔴 Critical
- Serious → 🟠 Serious
- Moderate → 🟡 Moderate
- Minor → 🔵 Minor

The **Senior engineer approval** line goes on top for fast scanning — it's the single field a human wants to see first. The **Filtered out** section is mandatory in the terminal output — without it, you can't tell when the critic is over-filtering.

### Wall-time instrumentation (end)

Before printing the Filtered Out section, compute total elapsed time and per-phase breakdown from the `PHASE_START_*` timestamps captured in Phase 1/2/3/4. Append to the audit section:

```
## Timing
Phase 1: <elapsed>s (metadata + diff + intent model + repo map)
Phase 2: <elapsed>s wall / <sum>s CPU (parallel: <N> subagents)
Phase 3: <elapsed>s (dedupe + verify + challenge + reusability audit + false-positive sweep + gap check + verdict)
Phase 4: <elapsed>s
Total:   <total>s
```

This gives visibility into where time is spent and helps calibrate when `SIZE_MODE=solo-main` would save time.

### Self-review detection

Before asking whether to post to GitHub, check if the reviewer IS the PR author:

```bash
VIEWER=$(gh api user -q .login)
AUTHOR=$(gh pr view <url> --json author -q .author.login)
if [ "$VIEWER" = "$AUTHOR" ]; then
  SELF_REVIEW=true
fi
```

**GitHub silently coerces `--request-changes` to `--comment` when the reviewer is the PR author.** This is a GitHub quirk, not a skill bug — you can't formally request changes on your own PR.

If `SELF_REVIEW=true`:

If the review has **zero findings** (verdict is `approve` with no comments), skip the self-review prompt entirely — there is nothing to fix or post. Print "No findings — nothing to fix." and exit.

Otherwise, skip the normal "Post review" prompt entirely. Instead, use AskUserQuestion:

   Question:
     header: "Self-review"
     text: "Self-review detected — you're the PR author. Posting to GitHub is unnecessary. Fix these findings directly?"
     options:
       - label: "Fix now (Recommended)"
         description: "Auto-invoke /fix-pr-review to fix findings directly — no GitHub posting"
       - label: "Keep local only"
         description: "Review stays in your terminal — no posting, no fixing"
       - label: "Post anyway"
         description: "Post to GitHub as COMMENT state (GitHub coerces self-reviews)"

On "Fix now":
1. Write findings to `/tmp/review-pr-<number>-findings.md` in the per-finding structured format (NOT the summary table — use the explicit field labels that `/fix-pr-review` expects to parse):
   ```
   ## Findings
   
   Severity: Serious
   File: src/auth.ts:47
   Category: Silent-failure
   Issue: Unhandled stdin error can crash process
   Why it matters: Production crash on communication failure
   Suggested fix: Add error event handler
   
   Severity: Moderate
   ...
   ```
2. Invoke `/fix-pr-review /tmp/review-pr-<number>-findings.md`
3. Skip the "Then ask" prompt, skip posting, skip the "Post-completion next actions" prompt — `/fix-pr-review` handles its own workflow from here via the local file input path (Phase 7 GitHub ops are automatically skipped for local files).

On "Keep local only": skip the post-review prompt entirely and exit. On "Post anyway": proceed to the normal "Then ask" prompt below (the review will be posted as COMMENT due to GitHub's coercion). On "Other": treat as "Fix now" (the most useful default for self-reviews).

### Verdict-body sync check (re-runs)

If the run is a re-run on the same PR AND the skill has previously posted a review for this PR:

```bash
LAST_POSTED_REVIEW_ID=$(cat "$CACHE_FILE" | jq -r '.last_posted_review_id // empty')
if [ -n "$LAST_POSTED_REVIEW_ID" ]; then
  LAST_POSTED_STATE=$(gh api "repos/<owner>/<repo>/pulls/<num>/reviews/$LAST_POSTED_REVIEW_ID" --jq .state)
  LAST_POSTED_BODY_VERDICT=$(gh api "repos/<owner>/<repo>/pulls/<num>/reviews/$LAST_POSTED_REVIEW_ID" --jq .body | grep -oE '\*\*Verdict\*\*:\s*`?(approve|comment|request-changes)`?' | sed 's/.*\(approve\|comment\|request-changes\).*/\1/')
  
  # Compare: LAST_POSTED_STATE (from GitHub, e.g. "COMMENTED") vs LAST_POSTED_BODY_VERDICT (from body text)
  # If they drifted (e.g. body says "request-changes" but state is "COMMENTED"), warn:
fi
```

If the body verdict and GitHub state drifted:

> **Previous review's body verdict (`<body_verdict>`) does NOT match its GitHub state (`<state>`).** Likely cause: you posted a self-review that GitHub coerced to `comment`, or you manually edited the review state in the GitHub UI afterward. The current run's output will not re-post over the previous review — add a NEW review via the "Post now" option below if you want to update.

### Then ask

**Reminder:** Use AskUserQuestion — cursor-selectable options, not a plain-text `1. / 2. / 3.` list. Do NOT precede this with a prose question like "Would you like me to..." — the tool call itself is the question.

Use AskUserQuestion:

   Question:
     header: "Post review"
     text: "Post this review to the PR as a GitHub review? Verdict: <verdict>"
     options:
       - label: "Post now"
         description: "Submit as a <verdict> review to GitHub immediately"
       - label: "Keep local"
         description: "Don't post — review stays in your terminal only"
       - label: "Edit first"
         description: "Open the review body in $EDITOR for tweaks before posting"

On "Post now": proceed to resolve threads (if re-review) then compose and post (the "If yes" section below). On "Keep local": skip posting. On "Edit first": proceed to the "If edit first" section below. On "Other": treat as freeform instruction (e.g., the user might say "change the verdict to comment before posting").

### Re-review thread resolution (before posting)

If this is a re-review AND the cache has `posted_comments` from a previous run, resolve threads for findings that were fixed:

1. **Identify fixed findings**: compare the current run's findings (after Phase 3 critic pass) against `posted_comments` in the cache using the dedupe key (defined in Phase 3 step 1). A cached finding NOT present in the current findings is considered "fixed".

2. **Resolve their threads** on GitHub:
   ```bash
   # For each fixed finding's thread_id
   gh api graphql -f query='
     mutation($threadId: ID!) {
       resolveReviewThread(input: {threadId: $threadId}) {
         thread { isResolved }
       }
     }
   ' -f threadId="<thread_id>"
   ```

3. **Track resolved findings**: collect the finding IDs (e.g., S1, S4, S5) of resolved threads for the "Fixed since last review" line in the summary body.

4. **Filter review comments**: only post review comments (line-level or file-level) for findings that are NEW or STILL PRESENT — do NOT re-post findings that were already posted in a previous review and are still unresolved (they already have comment threads on GitHub). A finding is "still present" if its dedupe key matches a cached `posted_comments` entry AND it still appears in the current findings — skip its comment (the existing one is sufficient).

5. **Error handling**: if a `resolveReviewThread` mutation fails (e.g., thread already resolved, or permission issue), log the failure but continue with posting. Thread resolution is best-effort — it should never block the review.

### If yes — Hybrid posting (summary body + review comments)

Post the review as a **three-phase flow** that creates a PENDING review, attaches line-level and file-level threads, then submits atomically. The cross-API split (REST for creation, GraphQL for file-level threads) exists because of a hard GitHub platform constraint — see the callout below.

#### GitHub API reference — why two APIs (READ BEFORE EDITING THIS SECTION)

**DO NOT regress this to a single REST call with `subject_type: "file"` comments.** That shape is rejected by GitHub:

- **Line-level review comments** (`{path, line, side: "RIGHT"}`): Supported by REST `POST /pulls/:n/reviews` AND by GraphQL `addPullRequestReviewThread`.
- **File-level review comments** (no line anchor): Supported ONLY by GraphQL `addPullRequestReviewThread` with `subjectType: FILE`. The REST `POST /pulls/:n/reviews` endpoint uses the `DraftPullRequestReviewComment` validator which has NO `subjectType` field — passing `subject_type: "file"` returns `422 Unprocessable Entity` with error `Field is not defined on DraftPullRequestReviewComment, ..., position`. This was the bug that silently collapsed past review runs to a monolithic body and lost every resolvable thread.

The three-phase flow below works around the split:
1. **Phase A (REST)** — create the review in PENDING state with line-level comments.
2. **Phase B (GraphQL)** — attach file-level threads to that pending review.
3. **Phase C (GraphQL)** — submit the review with the final verdict event.

#### Step 1 — Compose the summary body (Part 1 of the review)

Build a lean summary body **without the "Filtered out" section** (internal only) but **including the Senior engineer approval line with emojis**:

```markdown
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

*Details in review comments below.* <!-- omit if ALL findings are body-fallback -->
```

**Severity count badges**: `🔴 <N> Critical · 🟠 <M> Serious · 🟡 <K> Moderate · 🔵 <J> Minor` — only include severity levels that have findings.

**Finding numbering**: assign sequential IDs by severity: C1, C2... for Critical, S1, S2... for Serious, M1, M2... for Moderate, m1, m2... for Minor. Use these IDs consistently in the summary table and review comments.

**Comment routing — three tiers based on file/line validity**:
- **Line-level thread** (REST, Phase A): finding has a valid `file:line` where the line exists on the post-image side of the diff → attach to the pending review with `{path, line, side: "RIGHT", body}`.
- **File-level thread** (GraphQL, Phase B): finding has a file reference but no valid diff line (e.g., file/module-scope issues, schema overlap findings, or line not in the diff) → attach via `addPullRequestReviewThread` mutation with `subjectType: FILE` (no line/side). If the finding spans multiple files, pick the most relevant changed file and reference other files in the comment body.
- **Body fallback** (rare): finding has no file reference at all → use `*(general)*` in the File column of the summary table and append the full finding detail to the body under a `### Additional findings` section after the table.

All three tiers create full GitHub conversation threads that are resolvable and replyable. The body-fallback tier is the ONLY acceptable reason for a finding to not have its own thread — never use it to work around an API error (see Step 7 for failure recovery).

**Re-review "Fixed since last review" line**: if this is a re-review and previous findings were resolved (see Re-review thread resolution), append after the table. Use the previous run's finding ID with its one-line issue text to avoid confusion with the current run's numbering:
```markdown
**Fixed since last review**: S1 (`auth.ts:47` missing null check), S4 (`db.ts:123` N+1 query) *(threads resolved)*
```

#### Step 2 — Compose review comments (Part 2 of the review)

Each finding with a valid file reference becomes a review comment. Format each comment as self-contained markdown:

```markdown
<severity-emoji> **<Severity>** · <Category>

**<Issue one-sentence>**

<2-3 sentence explanation of what's wrong and how it manifests>

**Why it matters**: <one sentence>

**Suggested fix**: <one sentence, actionable>
```

Severity emojis: 🔴 Critical, 🟠 Serious, 🟡 Moderate, 🔵 Minor.

**Comment payload shape** — build each comment for its target API:
- **Line-level (REST, Phase A)**: `{"path": "<file>", "line": <post-image line>, "side": "RIGHT", "body": "<markdown>"}` — goes into the `comments` array of the REST review creation call.
- **File-level (GraphQL, Phase B)**: passed as separate mutation arguments — `path: "<file>"`, `subjectType: FILE`, `body: "<markdown>"`, `pullRequestReviewId: <node_id from Phase A>`. Since GitHub doesn't anchor code for file-level threads, include a brief code reference in the body (e.g., `` near the `<symbol>` definition in `<file>` ``) so the reader has enough context.

#### Step 3 — Pre-posting hunk validation

Before Phase A, fetch the PR's diff hunks once and verify that each line-level comment's `(path, line)` is on the post-image side of a hunk. Demote any mismatches to file-level (Phase B). This prevents REST rejections and makes tier routing deterministic instead of hopeful.

```bash
gh api "repos/<owner>/<repo>/pulls/<number>/files" --paginate \
  --jq '.[] | {filename, patch}'
```

**Output format:** `--paginate` with `--jq` emits **NDJSON** (one `{filename, patch}` object per line across all pages), NOT a single JSON array. Process line-by-line (e.g., `while read -r line; do …; done`); do NOT pipe the combined output to another `jq '.[]'` expecting an array — that fails on the second page.

Parse each file's `patch`: each `@@ -<oldStart>,<oldLen> +<newStart>,<newLen> @@` header starts a new hunk. Within the hunk, `+` lines and space-prefixed context lines advance the post-image counter (starting at `newStart`); `-` lines do NOT. A line is "in the diff" for posting purposes only if it matches a counter value on some hunk for that file.

For each line-level finding, check: is `line` present on `path`'s post-image counter? If yes → keep as line-level. If no → demote to file-level (add to Phase B batch) and log the demotion so the reviewer can see why a line-cited finding became file-scoped.

#### Step 4 — Phase A: create PENDING review with line-level comments (REST)

Pass ALL fields in a single `--input` JSON — do NOT mix `--input` with `-f` flags. **Omit the `event` field** so the review stays PENDING while Phase B attaches file-level threads:

**Note — call Phase A even with zero line-level findings.** If all findings are file-level (after Step 3 demotions), pass `comments: []`. The REST endpoint accepts an empty `comments` array with a body-only PENDING review — this is the only way to get the `pullRequestReviewId` that Phase B's mutations require.

```bash
# Build comments array dynamically — empty [] is valid when all findings are file-level
COMMENTS_JSON='[
  {
    "path": "<file path>",
    "line": <post-image line number>,
    "side": "RIGHT",
    "body": "<line-level comment from Step 2>"
  }
]'
# OR: COMMENTS_JSON='[]'  when all findings are file-level

REVIEW_RESP=$(gh api "repos/<owner>/<repo>/pulls/<number>/reviews" \
  --method POST \
  --input <(jq -n \
    --arg body "<summary body from Step 1>" \
    --arg commit_id "<head SHA>" \
    --argjson comments "$COMMENTS_JSON" \
    '{body: $body, commit_id: $commit_id, comments: $comments}'))

REVIEW_NODE_ID=$(echo "$REVIEW_RESP" | jq -r '.node_id // empty')   # e.g. PRR_kwDO...
REVIEW_DB_ID=$(echo "$REVIEW_RESP" | jq -r '.id // empty')          # integer, for cache

if [ -z "$REVIEW_NODE_ID" ] || [ -z "$REVIEW_DB_ID" ]; then
  echo "Phase A returned no node_id/id. Full response:" >&2
  echo "$REVIEW_RESP" >&2
  # Treat as failure → go to Step 7 with error text "$REVIEW_RESP"
fi

ATTACHED_THREADS=0   # Step 7 uses this to disclose partial Phase B success count
```

Capture BOTH IDs: `node_id` (GraphQL ID) is needed for Phases B and C; `id` (integer) is needed for caching. If the `gh api` call fails OR if the null guard fires → go to Step 7.

#### Step 5 — Phase B: attach file-level threads (GraphQL)

For each file-level finding (original file-level findings + any demoted in Step 3), call `addPullRequestReviewThread`:

```bash
THREAD_RESP=$(gh api graphql -f query='
  mutation($reviewId: ID!, $path: String!, $body: String!) {
    addPullRequestReviewThread(input: {
      pullRequestReviewId: $reviewId,
      path: $path,
      body: $body,
      subjectType: FILE
    }) {
      thread { id comments(first: 1) { nodes { databaseId } } }
    }
  }
' -f reviewId="$REVIEW_NODE_ID" -f path="<file path>" -f body="<file-level comment body>")   # -f (lowercase) forces string; -F would coerce numeric-looking paths/bodies to JSON numbers

# gh api graphql exits 0 even when GraphQL returns errors — check both .errors and thread.id
if echo "$THREAD_RESP" | jq -e '.errors' >/dev/null \
   || [ "$(echo "$THREAD_RESP" | jq -r '.data.addPullRequestReviewThread.thread.id // empty')" = "" ]; then
  echo "Phase B failed on thread $((ATTACHED_THREADS + 1)). Response: $THREAD_RESP" >&2
  # Go to Step 7 with error text and current ATTACHED_THREADS count
fi
ATTACHED_THREADS=$((ATTACHED_THREADS + 1))
```

Loop **sequentially, not in parallel** — thread order in the submitted review follows call order. Capture each returned `thread.id` and `comments.nodes[0].databaseId` for caching. On failure mid-loop, Step 7's question text must disclose how many threads succeeded (see `ATTACHED_THREADS`) so the user knows the pending review has partial state.

#### Step 6 — Phase C: submit the review (GraphQL)

```bash
SUBMIT_RESP=$(gh api graphql -f query='
  mutation($reviewId: ID!, $event: PullRequestReviewEvent!) {
    submitPullRequestReview(input: {
      pullRequestReviewId: $reviewId,
      event: $event
    }) {
      pullRequestReview { id databaseId state submittedAt }
    }
  }
' -f reviewId="$REVIEW_NODE_ID" -f event="<APPROVE|COMMENT|REQUEST_CHANGES>")   # -f forces string; GraphQL coerces the enum from the declared $event type

# Same error-check pattern as Phase B: gh exits 0 on GraphQL errors
if echo "$SUBMIT_RESP" | jq -e '.errors' >/dev/null \
   || [ "$(echo "$SUBMIT_RESP" | jq -r '.data.submitPullRequestReview.pullRequestReview.databaseId // empty')" = "" ]; then
  echo "Phase C submit failed. Response: $SUBMIT_RESP" >&2
  # Go to Step 7 with error text — review is still PENDING with all attached threads
fi
```

**Event mapping**: `approve` → `APPROVE`, `comment` → `COMMENT`, `request-changes` → `REQUEST_CHANGES`. If the mutation fails (HTTP error OR GraphQL error OR missing `databaseId`) → go to Step 7. A Phase C failure is the worst case: the pending review has ALL threads attached but is never submitted, so it lingers as a draft until Step 7 cleans it up or the user submits it manually.

#### Step 7 — Posting failed recovery (NEVER silent)

If Phase A, B, or C fails at any point, **DO NOT silently collapse to a monolithic body.** The prior silent fallback was the root cause of posting zero resolvable comments on past runs — the user must explicitly CHOOSE to degrade.

**Reminder:** Use AskUserQuestion — cursor-selectable options, not a plain-text `1. / 2. / 3.` list.

**Disclose partial state in the question text.** The `text` must name which phase failed AND report how many threads/comments are already attached to the pending review, e.g.:

> "Phase B failed on thread 3 of 8. Pending review `<REVIEW_NODE_ID>` already has 2 file-level threads + <N> line-level comments attached from Phase A. GitHub error: `<error>`. How should I proceed?"

The user cannot choose intelligently between "Post monolithic", "Abort", and "Show payload" without knowing there's partial state.

   Question:
     header: "Post failed"
     text: "<phase>. Pending review has <K> thread(s) attached. GitHub error: <error>. How should I proceed?"
     options:
       - label: "Post as monolithic body"
         description: "Delete the pending review, then post via `gh pr review --body-file` with all findings inline — loses resolvable threads but the review still appears on GitHub"
       - label: "Abort — keep local"
         description: "Delete the pending review; nothing is posted. The review stays in your terminal only"
       - label: "Show payload & keep draft"
         description: "Print the failing request body/mutation and leave the pending review as a draft on GitHub so you can submit/edit it manually in the UI"

**Cleanup helper** — used by "Post as monolithic" and "Abort" branches. Capture stderr so failures are visible, not silently swallowed:

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

**On "Post as monolithic body"**: call `cleanup_pending_review` (best-effort; if cleanup fails, continue but keep the warning visible to the user), then post via `gh pr review <url> <verdict-flag> --body-file /tmp/review-pr-<number>-monolithic.md` with the full findings list inline in the body.

**On "Abort — keep local"**: call `cleanup_pending_review` and stop. If cleanup fails, surface the warning so the user knows a draft is lingering.

**On "Show payload & keep draft"**: print the offending JSON/mutation that failed. Do NOT clean up the pending review — the user explicitly chose to keep the draft so they can retry manually via the GitHub UI or CLI. Print the pending review URL (`https://github.com/<owner>/<repo>/pull/<n>` → "Finish your review" banner) so they can find it.

#### Step 8 — Cache the result

After successful Phase C, **merge** the posting metadata into the existing `$CACHE_FILE` (do NOT overwrite — the cache already has `last_run_sha`, `findings`, etc. from the end-of-Phase-4 write). Add/update these fields:

- `last_posted_review_id`: the integer `databaseId` from Phase C's response (REST-compatible — matches what Phase 1's prior-review timeline query uses)
- `last_posted_review_node_id`: the GraphQL `node_id` from Phase A (useful for follow-up GraphQL mutations)
- `last_posted_verdict`: the verdict string
- `last_posted_at`: ISO timestamp
- `posted_comments`: array of comment entries (see Phase 1 cache schema for the full structure)

For each posted comment, construct the `finding_key` using the dedupe key format from Phase 3 step 1 (line-level: `(file, line, symbol)`, file-level: `(file, file-level:<category>, symbol)`).

**To populate `github_thread_id`** — this needs two sources because REST and GraphQL return different identifiers:

- **File-level threads**: the thread's GraphQL node ID (e.g., `PRRT_kwDO...`) is returned directly by Phase B's mutation at `data.addPullRequestReviewThread.thread.id`. No follow-up query needed.
- **Line-level comments**: Phase A's REST response returns each comment's numeric `id` (e.g., `2145678901`) in `.comments[].id`, but NOT the thread's node ID. GitHub wraps every comment in an auto-created thread with its own node ID that's needed for `resolveReviewThread`. Run one follow-up GraphQL query to correlate REST comment IDs to thread node IDs:

```bash
gh api graphql -f query='
  query($owner: String!, $repo: String!, $num: Int!) {
    repository(owner: $owner, name: $repo) {
      pullRequest(number: $num) {
        reviewThreads(last: 100) {
          nodes {
            id
            comments(first: 1) { nodes { databaseId } }
          }
        }
      }
    }
  }
' -f owner=<owner> -f repo=<repo> -F num=<number>   # -f for String!, -F for Int!
```

Match each line-level comment's `databaseId` (from Phase A's REST response `.comments[].id`) to a thread via `reviewThreads.nodes[].comments.nodes[0].databaseId`; take that thread's `id` as `github_thread_id`. This is the same prior-review-timeline query pattern used in Phase 1 — reuse it.

### If edit first

Write the composed summary body to a temp file (e.g. `/tmp/review-pr-<number>.md`), open it in `${EDITOR:-vi}`, then post after the user closes the editor. Review comments (line-level and file-level) are NOT editable via this flow — only the summary body. If the user needs to remove a specific comment, they should edit the findings list before choosing "Post now".

### Post-completion next actions (context-aware)

**Reminder:** Use AskUserQuestion — cursor-selectable options. This is the LAST interaction gate of the skill; do NOT add a freeform `What's next — do X or are we done?` prose question after it.

After the review is posted or kept local, use AskUserQuestion. Skip this prompt entirely if:
- The review had zero findings (verdict was `approve` with no comments)
- The user chose "Fix now" or "Keep local only" from the self-review prompt
- `/fix-pr-review` was already invoked (it handles its own workflow)

**For external PRs** (reviewer is NOT the author):

   Question:
     header: "Next"
     text: "Review posted. What would you like to do next?"
     options:
       - label: "Re-review later"
         description: "Re-run /review-pr after author pushes fixes"
       - label: "Done"
         description: "Nothing more — end the session"

On "Re-review later": print "Run `/review-pr <url>` again after the author pushes fixes." and exit — do NOT immediately re-invoke (the author hasn't pushed yet). On "Done": exit. On "Other": follow the user's freeform instruction.

**The AskUserQuestion above is the final turn of this skill.** Do not follow it with any freeform text question (e.g., "What's next?", "Want me to re-review later?", "Are we done?"). The tool call itself terminates the skill's interaction — any extra prose question re-introduces the very anti-pattern the top-level rule forbids.

**For self-reviews** (reviewer IS the author, and user chose "Post anyway"):

   Question:
     header: "Next"
     text: "Review posted. What would you like to do next?"
     options:
       - label: "Fix findings"
         description: "Run /fix-pr-review on this PR to address the posted findings"
       - label: "Done"
         description: "Nothing more — end the session"

On "Fix findings": invoke `/fix-pr-review <url>`. On "Done": exit. On "Other": follow the user's freeform instruction.

**The AskUserQuestion above is the final turn of this skill.** Do not follow it with any freeform text question. The tool call itself terminates the skill's interaction.

---

## Error handling

- **`gh` not installed / not authed** → fail fast with `Run 'gh auth login' and retry.`
- **Invalid PR URL** → fail fast with `Couldn't parse PR URL. Expected format: https://github.com/owner/repo/pull/NUMBER`.
- **PR not accessible (404 / GraphQL resolution error)** → `Couldn't access PR. Check repo access; try 'gh auth refresh -s repo'.`
- **PR is closed/merged** → warn but proceed (user may be doing post-mortem review).
- **PR is a draft** → note it in the output header but proceed.
- **PR has no changes** → short-circuit with "Nothing to review" (see Phase 1).
- **Phase 2 subagent failure** → continue with remaining reviewers; note `<reviewer> unavailable` in header. Abort only if ALL fail.
- **Network errors on `gh`** → surface the error, don't silently fall back.

## Rules

- **NEVER** run the review twice in a single invocation (don't retry on empty findings).
- **NEVER** post to the PR without explicit user confirmation via the "Post now" or "Edit first" AskUserQuestion options (except self-reviews where "Fix now" skips posting entirely).
- **NEVER** post the "Filtered out" section to GitHub — it's for local audit only.
- **NEVER** fabricate file:line references; if unsure, omit the line and use file-only (these route to file-level review comments).
- **NEVER** skip Phase 1's stop-and-ask fallback — weak intent is the biggest slop source.
- **NEVER** skip the grounding pass in the reviewer subagent — findings that don't trace back to the mechanical grounding bullets are hallucinations and must be dropped before output.
- **NEVER** skip the critic pass — it's the second biggest anti-slop lever after the reviewer prompt.
- **NEVER** re-post review comments for findings that already have active (unresolved) threads from a previous review — this creates duplicate noise.
- **ALWAYS** use `gh api` for posting reviews (hybrid: summary body + review comments). Fall back to `gh pr review --body` only if the API call fails.
- **ALWAYS** resolve threads for fixed findings on re-reviews before posting new findings. Thread resolution is best-effort — failures should not block posting.
