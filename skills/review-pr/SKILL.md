---
name: review-pr
description: Deep, anti-slop review of a GitHub PR. Grounds findings in the linked issue's intent, runs Claude + CodeRabbit reviewers in parallel, then critic-passes the findings before printing. Use when user says "review this pr", pastes a GitHub PR URL, or asks "check this pull request". NOT for local uncommitted changes — use /parallel-review for those.
---

# /review-pr — Deep GitHub PR Review

Reviews a remote GitHub PR with anti-slop filtering. Input: **PR URL only**.

The goal of this skill is simple: produce an accurate, critical, actionable PR review that surfaces what a human reviewer should double-check — and filters out the noise (style nitpicks, hallucinated references, duplicates of prior findings, generic advice).

**Use AskUserQuestion for ALL user-facing decisions** — stop-and-ask fallback, cache replay, large-PR confirmation, self-review handling, and post-review choices. Always present options as cursor-selectable choices, not plain text questions.

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
}' -F owner=<owner> -F repo=<repo> -F num=<num>
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
    # Skip subagent dispatch entirely; run the 6-question pass in main context.
    # Justification: a 50-line PR doesn't warrant 2× subagent spin-up cost (~5min wall time).
    # Main context reads the diff once, answers Q1-Q6 inline, critic pass is lighter.
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
  "last_posted_review_id": "PR_review_abc123",
  "last_posted_verdict": "request-changes",
  "last_posted_at": "2026-04-11T13:30:15Z",
  "posted_comments": [
    {
      "finding_key": "(file.ts, 47, handleerror)",
      "finding_id": "S1",
      "github_comment_id": 12345,
      "github_thread_id": "PRRT_abc123",
      "finding_severity": "Serious"
    },
    {
      "finding_key": "(config.ts, file-level, missingvalidation)",
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
- Do NOT dispatch subagents at all. Run the Claude reviewer prompt (Subagent 1 block below) inline in main context. Main reads the stashed diff once, answers Q1-Q6, does grounding pass, populates `reusability_searches:`, and outputs in the same format as the subagent version would.
- Still dispatch CodeRabbit reviewer (if not paused) and silent-failure hunter (if triggered) — these are fast fixed-cost subagents and save main context. They run in parallel with main's inline work.
- Rationale: on a 50-line PR, spinning up a dedicated reviewer subagent costs ~5 minutes wall time for work main can do in ~30 seconds.

**`SIZE_MODE == "parallel-standard"`** (100-500 lines, default):
- Dispatch Claude reviewer (Subagent 1) + CodeRabbit (Subagent 2) + conditional silent-failure hunter (Subagent 3) in parallel. Current behavior.

**`SIZE_MODE == "parallel-chunked"`** (500-2000 lines):
- Split the diff by file into chunks of ~500 lines each. Group by file boundary — don't split a file across chunks.
- Dispatch ONE Claude reviewer subagent PER CHUNK, each with:
  - Full intent model + prior review timeline + repo map (shared context)
  - Only its chunk's files listed in the prompt
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

4. Answer these 5 questions EXPLICITLY. Each must be addressed, even if just "no issues".

   Q1. Intent — Does this PR actually solve the stated goal? Where's the gap, if any?
   Q2. Unnecessary changes — Files, abstractions, config, or indirection not
       required by the goal? (This deliberately collapses scope creep +
       overengineering into one question; reporting them separately produces
       intra-reviewer duplicates.)
   Q3. DRY — Duplicated logic within the diff, or with existing code visible
       in the surrounding context?
   Q4. Performance — N+1 queries, loops over async, unbounded allocations,
       missing Promise.all, missing indices for new WHERE clauses, sequential
       awaits that could be parallel?
   Q5. Security — Injection, auth bypass, unsafe input handling, secrets in
       code, missing authorization checks, unvalidated user input reaching
       dangerous sinks?

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
             like `async findOne(...)`, `private formatPortion(...)`,
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
              a) Split name on CamelCase boundaries: `formatPortionLabel`
                 → `[format, Portion, Label]`
              b) Drop tokens that are DOMAIN nouns (Portion, MealMenu,
                 Order, Client, User, Meal, Schedule, Inbound, etc.)
              c) Keep tokens that are GENERIC verbs/nouns (format, parse,
                 validate, build, sleep, chunk, retry, merge, group,
                 sort, filter, map, find, compute, calculate, build,
                 extract)
              d) Grep each kept token against packages/ and apps/

            Worked examples:
              - `formatPortionLabel` → root = `format` → `Grep("format", "packages/")` + `Grep("Label", "packages/")`
              - `validateMealMenuPortion` → root = `validate` → `Grep("validate", "packages/")`
              - `UserBadge` (React component) → drop `User` → root = `Badge` → `Grep("Badge", "packages/ui/src/components/")`
              - `sleep` (no CamelCase) → root = `sleep` → `Grep("sleep", "packages/")`
              - `getInboundOrderSummary` → root = `get|Summary` → `Grep("getSummary", "packages/")` + `Grep("summary", "packages/")`

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
                    any type naming a business entity (Portion, MealMenu,
                    Order, Client, User, Schedule, etc.). Primitives
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
                • `function formatPortionLabel(p: Portion): string` →
                  DO NOT FLAG (Portion is domain).
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

         async getClientPortions(...) {
           const rawClients = await this.getClientsWithOffers(...)
           if (rawClients.length === 0) {
             return { components: [], mealMenuPortions: [] }  // ← hardcoded []
           }
           // ... late path ...
           const mealMenuPortions =
             await this.mealMenuPortionsService
                       .getByMenuPlanAndDateRange(...)
           return { components, mealMenuPortions }
         }

       The early return silently drops stored `mealMenuPortions` because
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

## Anti-slop rules (MANDATORY)

- Do NOT report style, formatting, or naming preferences.
- Do NOT re-report Prior findings. **Exception**: if you believe a prior
  finding was wrong, you MAY report it with `Category: Prior-finding-correction`
  and a concrete explanation of why.
- Do NOT report hypothetical issues ("this COULD become a problem if X") unless
  X is plausible given the actual codebase signals visible in the diff.
- Do NOT report issues you cannot point to with `File: <path>` — ideally
  `File: <path:line>`. Line number is optional only for `Category: Architecture`
  findings that are genuinely file- or module-scope.
- Do NOT report generic advice ("consider adding tests") unless tests were
  expected and omitted.
- If a question (Q1–Q5) has NO issues, write "No issues" — do not invent
  findings to fill the slot.
- **Permission to abstain**: if answering Q1–Q5 requires code you haven't
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
  File:       <path:line> (or <path> alone for Architecture)
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

**Dedupe key**: `(file_path, post_image_line, normalized_symbol_name)` — NOT `Category`. For findings without a valid diff line (file-level findings), use `"file-level"` in place of `post_image_line`. Two findings on the same `(file, line-or-file-level, symbol)` are duplicates regardless of whether one is `Category: DRY` (within-diff) and the other is `Category: Reusability` (cross-codebase). Merge them, keep the higher-severity category on the merged finding, and concatenate their reasoning into the `Issue:` field.

Normalize symbol names by lowercasing and stripping CamelCase boundaries (`formatPortionLabel` → `formatportionlabel`) so minor label variants still match.

Dedupe priority when merging:
1. **Severity wins**: keep `Serious > Moderate > Minor`.
2. **Category precedence for ties**: `Security > Reusability > Silent-failure > Breaking-change > Performance > DRY > Unnecessary > Intent > Architecture`.
3. **Confidence**: keep highest.

### 1.5. Cheap mechanical pre-checks (line-count sanity)

Before the expensive Step 2 diff verification, do a cheap mechanical pre-check on EVERY finding (not just Critical/Serious). This catches hallucinated line numbers that were a real issue on PR #4560 (Claude reviewer produced `SettingsTab.tsx:839-853` for a 258-line file — a hallucinated reference that slipped past Step 2's top-severity-only check).

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
- **Verification rule**: the `File: <path:line>` must refer to a line present on the **post-image / new side** of the hunk (a `+` line or unchanged context on the new side). References to old-side-only lines, deleted lines, or lines not present in any hunk → **DROP** and log `hallucinated reference`.
- **File-level findings** (no line number): verify that the referenced `path` appears in the PR's changed files list (from `gh pr view --json files` already fetched in Phase 1). If the path is not in the changed files → **DROP** and log `hallucinated file reference`.

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
4. **Class methods inside class bodies** — `private formatPortion()`, `async findOne()`, `public validate()`. This is the critical pattern for NestJS-style services where new "functions" live as class methods. Only count method declarations that appear INSIDE a class block (track `{`/`}` nesting from the nearest `class X {` on the new side of the hunk).

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

### 6. Gap check (Q1–Q6)

For any question category where BOTH reviewers said nothing, briefly think about whether the diff has anything in that category. Add findings if you spot something they missed.

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
Phase 3: <elapsed>s (dedupe + verify + challenge + reusability audit + gap check + verdict)
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
   ' -F threadId="<thread_id>"
   ```

3. **Track resolved findings**: collect the finding IDs (e.g., S1, S4, S5) of resolved threads for the "Fixed since last review" line in the summary body.

4. **Filter review comments**: only post review comments (line-level or file-level) for findings that are NEW or STILL PRESENT — do NOT re-post findings that were already posted in a previous review and are still unresolved (they already have comment threads on GitHub). A finding is "still present" if its dedupe key matches a cached `posted_comments` entry AND it still appears in the current findings — skip its comment (the existing one is sufficient).

5. **Error handling**: if a `resolveReviewThread` mutation fails (e.g., thread already resolved, or permission issue), log the failure but continue with posting. Thread resolution is best-effort — it should never block the review.

### If yes — Hybrid posting (summary body + review comments)

Post the review as a **single atomic API call** using the GitHub REST API. This creates a review with a summary body AND review comments (line-level on specific diff lines, file-level on files).

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
| M1 | 🟡 | `<path:line>` | <one-line issue> |

*Details in review comments below.*
```

**Severity count badges**: `🔴 <N> Critical · 🟠 <M> Serious · 🟡 <K> Moderate · 🔵 <J> Minor` — only include severity levels that have findings.

**Finding numbering**: assign sequential IDs by severity: C1, C2... for Critical, S1, S2... for Serious, M1, M2... for Moderate, m1, m2... for Minor. Use these IDs consistently in the summary table and review comments.

**Comment routing — three tiers based on file/line validity**:
- **Line-level comment**: finding has a valid `file:line` where the line exists in the diff → post as a line-level review comment with `line`, `side: "RIGHT"`.
- **File-level comment**: finding has a file reference but no valid diff line (e.g., Architecture-category findings, file/module-scope issues, or line not in the diff) → post as a file-level review comment with `subject_type: "file"` (no `line` or `side`). If the finding spans multiple files, pick the most relevant changed file and reference other files in the comment body.
- **Body fallback** (rare): finding has no file reference at all → include in the summary table and append the full finding detail to the body under a `### Additional findings` section after the table.

Both line-level and file-level comments use the same comment body format (see Step 2) and create full GitHub conversation threads — resolvable, replyable.

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

**Comment JSON shape** — build each comment object for the `comments` array:
- **Line-level**: `{"path": "<file>", "line": <post-image line>, "side": "RIGHT", "body": "<markdown>"}`
- **File-level**: `{"path": "<file>", "subject_type": "file", "body": "<markdown>"}` — no `line` or `side` fields.

#### Step 3 — Post via GitHub REST API

Use `gh api` to submit the review with all review comments (line-level and file-level) in one atomic call. Pass ALL fields in a single `--input` JSON — do NOT mix `--input` with `-f` flags (when `--input` is used, `-f` fields go to the query string, not the body):

```bash
gh api "repos/<owner>/<repo>/pulls/<number>/reviews" \
  --method POST \
  --input <(jq -n \
    --arg body "<summary body from Step 1>" \
    --arg event "<APPROVE|COMMENT|REQUEST_CHANGES>" \
    --arg commit_id "<head SHA>" \
    --argjson comments '[
      {
        "path": "<file path>",
        "line": <post-image line number>,
        "side": "RIGHT",
        "body": "<line-level comment from Step 2>"
      },
      {
        "path": "<file path>",
        "subject_type": "file",
        "body": "<file-level comment from Step 2>"
      }
    ]' \
    '{body: $body, event: $event, commit_id: $commit_id, comments: $comments}')
```

**Event mapping**: `approve` → `APPROVE`, `comment` → `COMMENT`, `request-changes` → `REQUEST_CHANGES`.

**Fallback**: if the `gh api` call fails (e.g., line number out of range for a line-level comment, or invalid path for a file-level comment), retry WITHOUT the failing comment(s) — log which comments were dropped. If the entire call fails, fall back to `gh pr review <url> <verdict-flag> --body "<full monolithic body>"` (the old approach, with all findings in the body).

#### Step 4 — Cache the result

After successful post, **merge** the posting metadata into the existing `$CACHE_FILE` (do NOT overwrite — the cache already has `last_run_sha`, `findings`, etc. from the end-of-Phase-4 write). Add/update these fields:

- `last_posted_review_id`: review ID from the API response
- `last_posted_verdict`: the verdict string
- `last_posted_at`: ISO timestamp
- `posted_comments`: array of comment entries (see Phase 1 cache schema for the full structure)

To populate `github_thread_id` for each posted comment, run the review threads GraphQL query (same as Phase 1's prior-review timeline fetch) immediately after posting and match by comment `databaseId` — the REST API response includes each comment's ID which can be correlated with the GraphQL thread query's `comments.nodes[].databaseId` field. This avoids ambiguity when multiple findings share the same `path` + `line`.

### If edit first

Write the composed summary body to a temp file (e.g. `/tmp/review-pr-<number>.md`), open it in `${EDITOR:-vi}`, then post after the user closes the editor. Review comments (line-level and file-level) are NOT editable via this flow — only the summary body. If the user needs to remove a specific comment, they should edit the findings list before choosing "Post now".

### Post-completion next actions (context-aware)

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
- **NEVER** fabricate file:line references; if unsure, omit the line and use file-only for Architecture-category findings.
- **NEVER** skip Phase 1's stop-and-ask fallback — weak intent is the biggest slop source.
- **NEVER** skip the grounding pass in the reviewer subagent — findings that don't trace back to the mechanical grounding bullets are hallucinations and must be dropped before output.
- **NEVER** skip the critic pass — it's the second biggest anti-slop lever after the reviewer prompt.
- **NEVER** re-post review comments for findings that already have active (unresolved) threads from a previous review — this creates duplicate noise.
- **ALWAYS** use `gh api` for posting reviews (hybrid: summary body + review comments). Fall back to `gh pr review --body` only if the API call fails.
- **ALWAYS** resolve threads for fixed findings on re-reviews before posting new findings. Thread resolution is best-effort — failures should not block posting.
