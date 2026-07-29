---
name: review-pr
description: Deep, anti-slop review of a GitHub PR. Grounds findings in the linked issue's intent, runs a Claude reviewer (+ conditional silent-failure hunter) in parallel with existing CodeRabbit comments fetched from the PR, then critic-passes the findings before printing. Use when user says "review this pr", pastes a GitHub PR URL, or asks "check this pull request". Also handles multiple PRs or "review all open PRs" via batch mode — one subagent per PR, consolidated report, decisions deferred to the end. NOT for local uncommitted changes — use /parallel-review for those.
---

# /review-pr — Deep GitHub PR Review

Reviews a remote GitHub PR with anti-slop filtering. Input: **PR URL only**.

Goal: produce an accurate, critical, actionable PR review that surfaces what a human reviewer should double-check — and filters out noise (style nitpicks, hallucinated references, duplicates, generic advice).

This skill assumes CodeRabbit is configured on the repo via `.coderabbit.yaml` (template at `~/.claude/skills/coderabbit-config/`). CodeRabbit catches style + convention findings before this skill runs; `/review-pr` focuses on what only deep semantic + codebase-wide review can do.

**Use AskUserQuestion for ALL user-facing decisions** — stop-and-ask, cache replay, large-PR confirmation, self-review, findings selection, post-review, post-failure, post-completion. Always cursor-selectable, never plain-text numbered lists. Options must be concrete, considered answers — never generic placeholders. Put the strongest option first and mark it "(Recommended)".

**Anti-patterns — NEVER do these:**
- NEVER present choices as a numbered markdown list in terminal text. That short-circuits the tool call.
- NEVER end a response with `Would you like me to... ?` followed by options in prose.
- NEVER ask `What's next — do X or are we done?` after a tool-call decision.
- Self-test: if you catch yourself writing a sentence that asks the user to pick between 2+ labeled paths, STOP and use `AskUserQuestion`.

## Reference files (loaded on demand by subagent)

The Claude reviewer subagent loads these when relevant — keep them in mind so this file stays small:

- `references/q6-reusability-search.md` — STEP A enumeration + STEP B search algorithm + Q6 control-flow gap. Loaded when the diff has 1+ new top-level definitions.
- `references/schema-design-checks.md` — Q7 (overlap), Q8 (1:1 consolidation), Q9 (cross-table FK) checks. Loaded when `INCLUDE_SCHEMA_CHECKS = true`.
- `references/github-posting.md` — three-phase REST/GraphQL posting flow + rolling-review fix + failure recovery. Loaded by Phase 4 when posting.
- `references/finding-state-schema.md` — `.claude/review-state/<pr>.yml` schema + finding-ID strategy + state machine.

## Superpowers planning pipeline (optional pre-review context)

If the repo has `docs/superpowers/specs/` or `~/.claude/plans/*.md` referencing this PR, the typical pipeline is `/brainstorming` → `/grill-me` → `/harden-plan` → `/writing-plans` → `/executing-plans` → `/done`.

If spec/plan files exist, check whether the PR aligns with documented design decisions. Deviations without justification can be flagged under Q1 (Intent). If they don't exist, skip this check.

## Usage

```
/review-pr https://github.com/owner/repo/pull/123
```

If no URL is provided, ask the user for one. Don't infer from the current branch.

## Batch mode (multiple PRs)

Triggers when the user provides **2+ PR URLs** or asks to review **all open PRs**. For "all open PRs", enumerate via `gh pr list --json number,url,title --limit 50`, print the list in the kickoff message, then start — no confirmation prompt (batch mode is unattended by design; a wrong list is visible in the report).

### Orchestration

- Main context is the **orchestrator** — oversight only. It never reviews a PR inline, regardless of `SIZE_MODE` (solo-main routing applies inside each subagent, not in main).
- Spawn **ONE `general-purpose` subagent PER PR**. Each subagent runs the single-PR flow (Phases 1–3) independently against its own PR and returns its Phase 4 terminal block as its result. Dispatch in parallel batches of 3–4.
- Subagents NEVER post to GitHub and NEVER ask questions — all posting and all AskUserQuestion checkpoints belong to the orchestrator, at the end.

### "Don't stop" semantics

The run continues unattended through the WHOLE list — batch mode implies the user may be away. Do NOT stop between PRs. Every would-be checkpoint is collected as a **pending decision** instead of asked:

- Stop-and-ask intent gap → review with just the diff; tag that PR's report `intent not grounded — findings may be generic`.
- PR > 2000 lines → proceed with chunked review; note the size in that PR's report header.
- Findings selection + post decision → deferred to end-of-run.
- A failed subagent doesn't stop the batch — record `<pr>: review failed (<reason>)` in the consolidated report and continue with the rest.

### Consolidated report

After all subagents return, write ONE report document to `/tmp/review-pr-batch-<timestamp>.md` (and print it):

```
# Batch PR Review — <N> PRs (<date>)

| PR | Title | Approval | Verdict | C | S | M | m |
|----|-------|----------|---------|---|---|---|---|
<one row per PR; "review failed" rows included>

## Pending decisions (<count>)
<one entry per deferred checkpoint, clearly marked:
  PENDING — #<num>: post decision (<verdict>, <F> findings)
  PENDING — #<num>: intent was not grounded — re-run with intent text?>

## Per-PR reviews
<each PR's full Phase 4 terminal block, in list order>
```

### End-of-run decisions

Ask ONCE, only after the consolidated report is written — so if the user is away, the complete report with clearly-marked pending decisions is already on disk and nothing is lost:

```
header: "Batch done"
text: "<N> PRs reviewed — <M> have findings to post, <K> pending decisions. Walk through them now?"
options:
  - "Triage now (Recommended)" — Walk each PR's findings selection + post decision in turn
  - "Report only" — Keep the consolidated report; posting decisions stay pending
```

On "Triage now": for each PR with findings, run the single-PR "Select findings to post" multiSelect followed by its "Post review" prompt, in list order. On "Report only": exit — pending decisions remain marked in the report for a later run.

---

## Phase 1: Gather context (main)

Run these as **two separate Bash tool calls in a single assistant message** (true parallelism requires separate tool_use blocks, not `&&` chained):

```bash
gh pr view <url> --json number,title,body,author,baseRefName,headRefName,additions,deletions,changedFiles,files,closingIssuesReferences,reviews,comments,state,isDraft
gh pr diff <url>
```

Phase 1 fetches the **full diff**. Stash it in main context — needed for the error-handling content scan AND Phase 3 critic's reference verification.

### Empty-diff short-circuit

If `changedFiles == 0` OR `additions + deletions == 0`:

> **Nothing to review** — this PR contains no reviewable file changes.

Stop immediately.

### Private-repo / access-error handling

If `gh pr view` returns a GraphQL resolution error or HTTP 404:

> **Couldn't access PR** — check repo access. Try `gh auth refresh -s repo` and retry.

Fail fast.

### Extract linked issues

1. Prefer `closingIssuesReferences` (each carries its own `repository.nameWithOwner` — use that, not the PR's repo).
2. Fall back to body regex: `(?i)(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s+#(\d+)` (same-repo only).
3. For each linked issue: `gh issue view <num> --repo <owner>/<repo> --json title,body,state`.
4. If ≥ 2 linked issues, note `multiple linked issues — intent may be ambiguous`. If their goals plainly contradict, route to stop-and-ask fallback.

### Build the intent model

```
Goal: <one sentence from issue + PR description>
Expected touches: <what files/areas should be changed>
Out of scope: <anything the issue explicitly excludes, or "none">
Size: <additions>/<deletions> lines across <N> files
Draft: <yes|no>
```

### Build the prior-review timeline

Fetch ALL reviews (not just latest) so the critic can track which findings were raised at which commit, whether they were resolved, and whether an unresolved finding is still valid on the current head.

```bash
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

Build:

```
prior_findings:
  - thread_id: <PRRT_...>
    first_raised_at: <review_id>
    first_raised_commit: <sha>
    file: <path>
    line: <post-image line at the time>
    is_resolved: <bool>
    is_outdated: <bool — later commits invalidated the line>
    body_excerpt: <first 200 chars>
    resolution_state: open | resolved | outdated | stale
```

This enables (a) accurate dedupe in Phase 3, (b) "Resolved but still present" detection (thread closed but code still exhibits the issue → flag with `Category: Prior-finding-correction`).

### Load review-state (multi-round dedup)

This is the fix for the "M3 deferred" multi-round bug. See `references/finding-state-schema.md` for the full schema.

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

### Stop-and-ask fallback

Trigger if **no linked issue** AND the PR description **lacks all** of these:

- A file path or directory reference
- A function / class / symbol name
- An error message or stack trace
- A reproduction command
- A linked issue URL in body (even outside `closingIssuesReferences`)

Thin descriptions ("update X", "fix bug", "wip") fail. Terse-but-grounded ("Fix race in `auth/cache.ts` eviction; repros with `make stress-test-auth`") pass.

On trigger, AskUserQuestion:

```
header: "Intent"
text: "Intent is unclear — no linked issue and the description lacks grounding signals. How should I proceed?"
options:
  - "Proceed anyway" — Review with just the diff; findings will be generic without grounding
  - "Skip this PR" — Abort the review
  - "I'll provide intent" — Wait for user to type intent text
```

On "I'll provide intent": wait for follow-up text, then build the intent model from it. This is your first anti-slop gate.

### Size warning

If `additions + deletions > 2000`:

> This PR touches **X lines across Y files**. Review may be noisy and slow. Proceeding.

### Wall-time instrumentation (start)

Capture `PHASE_START_TIME=$(date +%s)` at the top of Phase 1 and similar at each later phase. Print elapsed total in Phase 4.

### Detect cwd-vs-PR-repo mismatch (cross-repo mode)

```bash
CWD_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
PR_REPO="<owner>/<repo>"
[ -z "$CWD_REPO" ] || [ "$CWD_REPO" != "$PR_REPO" ] && CROSS_REPO_MODE=true || CROSS_REPO_MODE=false
```

Cross-repo mode changes:
1. Repo map computation falls back to remote `gh api` tree fetch.
2. Phase 3 already-fixed check uses `gh api` instead of local `git log`.

Note in Phase 4 output header.

### CodeRabbit config check (one-time hint)

Once per `(owner, repo)` per session, check whether `.coderabbit.yaml` exists in the PR repo:

```bash
gh api "repos/<owner>/<repo>/contents/.coderabbit.yaml" >/dev/null 2>&1 \
  && CR_CONFIG_PRESENT=true \
  || CR_CONFIG_PRESENT=false
```

If `CR_CONFIG_PRESENT=false` AND this is the first run of `/review-pr` against this repo in the current session, hint once after Phase 4 output:

> No `.coderabbit.yaml` in `<owner>/<repo>` — see `~/.claude/skills/coderabbit-config/` for a template that pushes style + convention checks into CodeRabbit. Future `/review-pr` runs in this repo will be tighter.

Don't gate posting on the hint. It's purely informational.

### Size-based routing (determine SIZE_MODE)

```
SIZE = additions + deletions

if SIZE < 100:        SIZE_MODE = "solo-main"             # Skip subagent dispatch; run inline
elif SIZE <= 500:     SIZE_MODE = "parallel-standard"     # Claude reviewer + conditional silent-failure hunter
elif SIZE <= 2000:    SIZE_MODE = "parallel-chunked"      # Per-chunk Claude reviewers + silent-failure hunter
else:                 SIZE_MODE = "parallel-chunked-confirm"  # AskUserQuestion: Continue vs Cancel
```

For `solo-main`, Phase 2's Subagent 1 section runs inline in main context (no Agent tool call) with the same prompt body.

### Run-over-run cache check

```bash
CACHE_DIR="$HOME/.claude/skills/review-pr/cache"
mkdir -p "$CACHE_DIR"
CACHE_FILE="$CACHE_DIR/<owner>_<repo>_<pr-number>.json"
CURRENT_HEAD=$(gh pr view <url> --json headRefOid -q .headRefOid)
```

Cache schema:

```json
{
  "last_run_sha": "abc123...",
  "last_run_timestamp": "2026-04-11T13:29:50Z",
  "last_run_verdict": "request-changes",
  "findings": [...],
  "filtered_out": [...],
  "last_posted_review_id": 12345678,
  "last_posted_review_node_id": "PRR_kwDO...",
  "last_posted_verdict": "request-changes",
  "last_posted_at": "2026-04-11T13:30:15Z",
  "posted_comments": [
    { "finding_key": "(file.ts, 47, processrequest)", "finding_id": "<id-hash>",
      "github_comment_id": 12345, "github_thread_id": "PRRT_abc123",
      "finding_severity": "Serious" }
  ]
}
```

`posted_comments` works alongside `.claude/review-state/<pr>.yml` — the cache holds per-comment GitHub IDs (for resolveReviewThread + dedup against re-posting), the state file holds per-finding lifecycle (active/resolved/dismissed). Both are necessary; neither is sufficient alone.

Three branches:

1. **`last_run_sha == CURRENT_HEAD`** — no new commits. AskUserQuestion: `Replay cached (Recommended)` vs `Fresh review`. On replay, print cached findings and exit (Phase 2/3/4 skipped).

2. **New commits since last run** (cached SHA is an ancestor of HEAD) — PARTIAL re-review:
   - `git diff <last_run_sha>..<CURRENT_HEAD>` (or `gh api compare` cross-repo) for new-commits diff.
   - Dispatch Phase 2 with NEW diff + FULL file context, prompted to ONLY report findings on new commits.
   - Phase 3 merges new findings with cached findings still applicable (re-verify each cached finding against current HEAD; drop with `stale after new commits` if changed).
   - Phase 4 header: `Mode: partial re-review (N new commits since cached run at <sha>)`.

3. **Cache exists but `last_run_sha` is NOT an ancestor** (force-push, branch reset): invalidate cache, full fresh run.

After successful run, write result to `$CACHE_FILE` at end of Phase 4 (cache is local, independent of GitHub state).

### Compute shared-package repo map (for Q6)

Inventory shared packages AND apps so Phase 2 reviewer can cross-check new additions. Scan BOTH `packages/` and `apps/` — a helper in `apps/web` may duplicate one in `apps/cli`, and monorepos split reusable code across both.

**Branch on `CROSS_REPO_MODE`**:

```bash
if [ "$CROSS_REPO_MODE" = "true" ]; then
  HEAD_BRANCH=$(gh pr view <url> --json headRefName -q .headRefName)
  gh api "repos/<owner>/<repo>/git/trees/${HEAD_BRANCH}?recursive=1" \
    --jq '.tree[] | select(.type == "blob" and (.path | test("^(packages|apps)/.*\\.(ts|tsx)$")) and (.path | test("node_modules|dist|build|\\.test\\.|\\.spec\\.") | not)) | .path' \
    | awk 'NR<=500{print} END{if(NR>500)print "[truncated at 500 of " NR " lines]"}'
  repo_map_files="<output>"
  repo_map_exports="N/A (cross-repo mode — fetch via 'gh api repos/<owner>/<repo>/contents/<path>?ref=<sha>' on-demand)"
fi
```

Local mode (default) — wrap globs in `bash -c '...'` (zsh aborts on `packages/*/src` before `2>/dev/null` can suppress):

```bash
# Repo map files
bash -c '
if [ -d packages ] || [ -d apps ]; then
  { [ -d packages ] && find packages -type f \( -name "*.ts" -o -name "*.tsx" \) \
      -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" \
      -not -name "*.test.*" -not -name "*.spec.*" 2>/dev/null
    [ -d apps ] && find apps -type f \( -name "*.ts" -o -name "*.tsx" \) \
      -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" \
      -not -path "*/.next/*" -not -name "*.test.*" -not -name "*.spec.*" 2>/dev/null
  } | awk "NR<=500{print} END{if(NR>500)print \"[truncated at 500 of \" NR \" lines]\"}"
fi
'
# Repo map exports
bash -c '
if [ -d packages ] || [ -d apps ]; then
  find packages apps 2>/dev/null -type d \( -name src -o -name lib -o -name source \) \
    -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" \
    -not -path "*/.next/*" 2>/dev/null \
    | xargs -I{} grep -rhnE "^export (default (async )?function|function|const|class|type|interface|async function) \w+" {} 2>/dev/null \
    | awk "NR<=500{print} END{if(NR>500)print \"[truncated at 500 of \" NR \" lines]\"}"
fi
'
```

Stash as `repo_map_files`, `repo_map_exports`. If neither `packages/` nor `apps/` exists, set both to `N/A (not a monorepo)` and flag `IS_MONOREPO=false` — Subagent 1 reroutes greps to `src/`.

### Check for error-handling touches (flag for Phase 2)

Grep the diff content for error-handling patterns in **added or modified lines**:

```
try \{ | catch \( | catch \{ | throw new | throw \s | \.catch\( | Result< | rescue | err := | raise
```

If any pattern appears OR user mentions error handling, set `INCLUDE_SILENT_FAILURE_HUNTER = true`. Filename-based detection is unreliable.

### Check for new database tables (flag for Phase 2)

Grep the diff content in **added lines**:

```
pgTable\( | createTable\( | CREATE TABLE | knex\.schema\.createTable | Schema\.create\(
```

If any pattern appears, set `INCLUDE_SCHEMA_CHECKS = true`. Also extract `SCHEMA_DIR` (typical: `db/schema/`, `drizzle/schema/`, `src/schema/`, `migrations/`). If unidentifiable, set `SCHEMA_DIR = "."` and limit Q7-Q9 grepping to files matching the table-definition pattern (e.g., `Grep("pgTable", ".", glob: "**/*.ts")`).

Cross-repo: use `gh api git/trees/<head-sha>?recursive=1` for file listing; Q7-Q9 reads via `gh api repos/<owner>/<repo>/contents/<path>?ref=<head-sha>`.

### Load project-level review suppressions

Check for `.claude/review-suppressions.yml` in the project root.

```bash
SUPPRESSIONS_FILE=".claude/review-suppressions.yml"
[ -f "$SUPPRESSIONS_FILE" ] && SUPPRESSIONS=$(cat "$SUPPRESSIONS_FILE")
```

Schema:

```yaml
suppressions:
  - pattern: "factory pattern"
    category: Architecture
    reason: "YAGNI - single provider by design"
    added: 2026-04-13
  - pattern: "missing timeout"
    file: "claude-code.ts"
    reason: "Timeout handled at caller level"
```

`pattern` (required): case-insensitive substring matched against finding's `Issue` text. `category`/`file` (optional): scope the suppression. `reason` (required): logged in Filtered Out for auditability.

If file exists, pass into Subagent 1 prompt as "Review suppressions — do NOT flag these patterns". Phase 3 step 5.5 also applies as safety net.

Cross-repo: fetch via `gh api repos/<owner>/<repo>/contents/.claude/review-suppressions.yml?ref=<head-sha>`. Skip on 404.

---

## Phase 2: Reviewer subagents

Launch in a **single message with multiple Agent tool calls** based on `SIZE_MODE`.

### Dispatch strategy

**`SIZE_MODE == "solo-main"`** (PR < 100 lines):
- Run Subagent 1 prompt inline in main context (no Agent tool call). Main reads stashed diff once, answers questions, populates `reusability_searches:`, outputs in same format as subagent.
- Still dispatch silent-failure hunter (if triggered) — fixed-cost subagent saves main context, runs in parallel.
- Rationale: 50-line PR doesn't warrant ~5min subagent spin-up for work main does in ~30s.

**`SIZE_MODE == "parallel-standard"`** (100–500 lines, default):
- Dispatch Subagent 1 (Claude reviewer) + conditional Subagent 2 (silent-failure hunter) in parallel.

**`SIZE_MODE == "parallel-chunked"`** (500–2000 lines):
- Split diff by file into ~500-line chunks (don't split a file across chunks).
- Dispatch ONE Subagent 1 PER CHUNK with full intent model + prior review timeline + repo map + schema context, but only its chunk's files in scope. Prompt: "Your scope is the files listed above. Do not report findings in other files."
- Dispatch ONE silent-failure hunter at full PR scope.
- Dispatch ONE **cross-cutting reviewer** (Subagent 3) at full PR scope — see below. Chunk
  reviewers are forbidden from reporting across files, so without this nothing in the run
  can see a defect class that spans two chunks. That blind spot is a documented source of
  repeat rounds: a fix lands on the sites in one chunk while identical sites in another go
  untouched and resurface as "new" findings a round later.
- Phase 3 critic dedupes across chunks via the existing `(file, line, symbol)` key — chunks are file-disjoint so within-chunk dupes are impossible; cross-chunk dupes only occur when findings span files.

**`SIZE_MODE == "parallel-chunked-confirm"`** (> 2000 lines):

```
header: "Large PR"
text: "This PR is <N> lines. Chunked review will dispatch <M> reviewer subagents (one per ~500-line chunk) plus silent-failure hunter. Expected wall: 2-4 minutes."
options:
  - "Continue" — Proceed with chunked parallel review
  - "Cancel" — Abort; consider breaking into smaller PRs
```

### Degraded-mode rule

If any subagent errors out or returns empty, continue with the remaining and note `<reviewer> unavailable` in Phase 4 output header. Abort only if ALL fail.

**Note on CodeRabbit**: this skill no longer dispatches a CodeRabbit subagent. CodeRabbit's findings are pulled from the PR's existing comments via the prior-review timeline in Phase 1 (assuming `.coderabbit.yaml` is configured — see the one-time hint above). If the PR's latest commit has no CodeRabbit comment yet, that's fine — Subagent 1 carries the load and the next round picks up CR's input.

### Subagent 1 — Claude reviewer (`general-purpose`)

Prompt:

```
You are reviewing a GitHub PR for a human reviewer who wants accurate, critical findings — NOT style nitpicks, NOT generic praise, NOT hallucinated issues.

## Ground truth
Goal: <from Phase 1>
Expected touches: <from Phase 1>
Out of scope: <from Phase 1>
Prior findings already reported (do NOT re-report unless you have a correction): <from Phase 1>

## Prior multi-round state — DO NOT re-report these
The following findings were already resolved or dismissed in earlier review rounds. Do NOT re-report them unless the diff shows the resolving code was reverted.
<filtered list from PRIOR_STATE.findings where status in {resolved, dismissed, wontfix}>
For each: id, file, enclosing_symbol, rule_class, status, round_resolved, dismissal_reason.

## PR
URL: <url>

## Review suppressions
<SUPPRESSIONS content if loaded, else "None">

## Shared package repo map (for Q6)
### Files in shared packages
<repo_map_files>
### Exported symbols
<repo_map_exports>

May be truncated at 500 lines — for thorough checks, Grep/Glob packages/ directly.

## Schema review context
INCLUDE_SCHEMA_CHECKS: <true|false>
SCHEMA_DIR: <path>
If true, ALSO load and follow `references/schema-design-checks.md` for Q7-Q9.

## Your task

1. Run `gh pr diff <url>` for the diff.
2. Run `gh pr view <url> --json files` for the file list.

3. **GROUNDING PASS — MANDATORY before answering any Q.**
   Write 3-5 bullets describing what this diff changes MECHANICALLY:
   - Which files are touched and how (added / modified / deleted / renamed)
   - Which functions / classes / schemas change
   - What the observable behavior change is
   Every subsequent finding MUST trace back to one of these bullets. If a finding doesn't trace, you are hallucinating it — drop before output.

4. Answer Q1–Q6 EXPLICITLY (plus Q7–Q9 if `INCLUDE_SCHEMA_CHECKS = true`). Each must be addressed, even if just "No issues".

   Q1. Intent — Does this PR actually solve the stated goal? Where's the gap?
   Q2. Unnecessary changes — Files, abstractions, config, or indirection not required by the goal? (Collapses scope creep + overengineering — reporting separately produces dupes.)
       Q2a. Documentation necessity — For any `.md` file with > 200 added lines OR > 40% of PR's total additions: question whether the docs are needed. Check if `CLAUDE.md` or existing project docs already cover the domain. Frame as observation, not bug. Severity: Minor. Category: Unnecessary.
       Q2b. Premature complexity — Detect known patterns NOT mentioned in the linked issue:
            - Optimistic locking (`version` columns with default 1)
            - Soft-delete on append-only/audit tables
            - Denormalized aggregation columns
            - Polymorphic reference patterns
            - Self-referential FKs
            If `INCLUDE_SCHEMA_CHECKS = true` AND the project already uses the same pattern in existing tables (search `$SCHEMA_DIR`), do NOT flag as premature.
            Severity: Minor. Category: Architecture.

   Q3. DRY — Duplicated logic within the diff or with existing code visible in surrounding context?

   Q4. Performance — N+1 queries, loops over async, unbounded allocations, missing Promise.all, missing indices for new WHERE clauses, sequential awaits that could parallelize?

   Q5. Security & Data Integrity — Injection, auth bypass, unsafe input handling, secrets in code, missing authorization, unvalidated input reaching dangerous sinks, AND type-coercion at write sites.

       **Type-coercion at write sites** (subtle, test-only-caught bug):
       Scan every DB insert/update / API payload construction in the diff for expressions like `field: value?.toFixed(N)`, `field: String(value)`, or `field: \`${value.toFixed(N)}\`` being written into NUMERIC fields. `.toFixed()` returns a string — silently stores "2.6" in a numeric column.

       Coercion methods to scan: `.toFixed`, `.toString`, `.toLocaleString`, `String(...)`, template-literal `\`${...}\`` containing those.
       Flag when NOT wrapped in `Number(...)` / `parseFloat(...)` / `parseInt(...)` / unary `+(...)`.

       Determining "numeric field":
       - **DB writes**: read schema at `$SCHEMA_DIR` OR grep the field name's column definition (`<fieldName>: numeric|integer|real|decimal|double|float|bigint`). If unset / undeterminable, SKIP — do not guess.
       - **API payloads / DTOs**: read the matching Zod schema (`z.number()`, `z.coerce.number()`) or TypeScript type. If unlocatable, SKIP.

       Severity: Serious. Category: Breaking-change.

   Q6. Reusability (Q6a only — codebase-wide) — MANDATORY tool-use check.

       The full STEP A enumeration + STEP B search algorithm + Q6 control-flow gap notes live in `references/q6-reusability-search.md`. Load it before answering Q6 if the diff has 1+ new top-level definitions.

       Q6a. Reimplements existing code (default Severity: SERIOUS; escalate to CRITICAL if existing thing lives in auth / validation / crypto package)
            <finding with concrete existing file:path to reuse>
            OR "No issues"

       The other Q6 sub-buckets (extract candidate, raw HTML, inline-block) were retired — they produced too many dismissed findings in real usage. Q6a is the high-signal kernel: reimplementation of existing shared code.

       REQUIRED audit field — use this EXACT name `reusability_searches:`:

         reusability_searches:
           - <tool>("<query>", "<path>") → <N> matches
             verified: <yes|no> — <if yes: what existing impl does and whether real match;
                                    if no: substring collision / wrong semantic>
           - ...

         AT LEAST one entry per item enumerated in STEP A.
         For each search where N > 0, `verified:` is MANDATORY.
         If STEP A was empty: `reusability_searches: N/A (no new top-level definitions in diff)`

5. **CLASS SWEEP — MANDATORY for every finding that proposes a code change.**

   Do this when the finding is FIRST RAISED, not when it is resolved. A finding
   reported at one site while three identical sites go unmentioned is the single
   most common cause of an extra review round.

   For each finding, derive a searchable signature from its `Rule-class` — the
   literal or structural pattern, not the prose — and search the blast radius:
   the touched files first, then the enclosing module, then the package.

   REQUIRED audit field — use this EXACT name `class_completeness:`:

     class_completeness:
       - finding: <the Issue, trimmed>
         rule_class: <slug>
         signature: <the literal/pattern actually searched>
         search: <tool>("<query>", "<path>") → <N> sites
         sites:
           - <file:line or symbol>: affected | not-affected — <one clause why>
         verdict: COMPLETE (all N sites reported) | INCOMPLETE (<M> unreported sites)

   If the sweep finds sites the finding did not cover, either fold them into the
   SAME finding (preferred — one finding, N sites) or raise them as siblings. Never
   report one site and stay silent about the others.

   Sweep at least the files in the diff. If `Rule-class` names a shared or exported
   symbol, extend to every caller — a fix to shared code changes behavior at call
   sites nobody asked about.

   If a finding proposes no code change: `class_completeness: N/A (no code change proposed)`.

6. **INVERSE-RISK PASS — MANDATORY, run after drafting every `Suggested fix`.**

   Treat your own remedy as code under review. Ask, for each suggested fix:
   *if a competent engineer implements this literally and nothing else, what breaks?*

   Answer concretely, naming the failure mode — not "could have issues". Real
   examples from this skill's own history:
     - "fail-closed decrypt" → placeholder value that can be re-encrypted over real ciphertext
     - "key={dataUpdatedAt} to re-seed the form" → silently discards unsaved edits on refetch
     - "treat missing reference as an empty run" → dead schedule now reports success forever
     - "widen the backend gate" → frontend mirror still restricts; inverts the bug

   Write it into the finding's `Inverse risk:` field. If the fix is a pure addition
   with no behavior traded away, say `none — pure addition` and mean it.

   A fix whose inverse risk is worse than the original finding is not a fix. Rewrite
   the suggestion or downgrade the finding to an observation.

7. Additionally flag:
   - Silent failures (caught errors swallowed without logging)
   - Removed error handling
   - Breaking changes to public APIs not mentioned in PR description
   - Architectural issues (wrong layer / wrong package / wrong abstraction boundary)
   - **New error values / sentinels / thrown exceptions**: trace each to EVERY
     downstream consumer in this pass, including consumers the diff does not touch.
     Deep error chains are static and fully traceable — reviewing them one layer per
     round is what turns a two-round PR into a five-round one.

8. **Schema-specific checks (Q7–Q9)** — only when `INCLUDE_SCHEMA_CHECKS = true`. Load `references/schema-design-checks.md` and follow its Q7/Q8/Q9 instructions. Skip entirely if false.
```

#### Anti-slop rules (MANDATORY)

- Do NOT report style, formatting, or naming preferences.
- Do NOT re-report Prior findings. **Exception**: if you believe a prior finding was wrong, report with `Category: Prior-finding-correction` + concrete explanation.
- Do NOT re-report findings from `PRIOR_STATE.findings` with `status in {resolved, dismissed, wontfix}` unless the diff shows the resolving code was reverted (then mark the new finding's `status` as `regression`).
- Do NOT report hypothetical issues ("this COULD become a problem if X") unless X is plausible given actual codebase signals in the diff.
- Do NOT report issues you cannot point to with `File: <path>` (line optional for module-scope findings — these route to file-level review comments).
- Do NOT report generic advice ("consider adding tests") unless tests were expected and omitted.
- If a question (Q1–Q9, except Q6) has NO issues, write "No issues" — do not invent findings.
- **Permission to abstain**: if answering needs code you haven't seen, either fetch via `gh api repos/<owner>/<repo>/contents/<path>?ref=<head-sha>` or write `Cannot assess — would need <file>`. DO NOT guess.
- Low-confidence findings at Moderate or Minor WILL be dropped by the critic. Only flag if a human should still take a second look.
- For Q6, populate `reusability_searches:` with actual tool calls or the N/A sentinel. Empty/missing audit = Q6 claims INVALID.
- Populate `class_completeness:` with actual tool calls or the N/A sentinel. Missing audit = the finding is treated as UNSWEPT and the critic runs the sweep itself.
- Never emit a `Suggested fix:` without an `Inverse risk:`. "I didn't think about it" is not an answer; `none — pure addition` is, when true.

#### Line number convention

`File: <path:line>` must use the **post-image line number** — line as it appears in the new version (the `+` side of the unified diff hunk, or unchanged-context on the new side). NOT old-side. NOT diff hunk header offset.

#### Output format

For each finding:

```
Severity:    Critical | Serious | Moderate | Minor
Confidence:  high | medium | low
File:        <path:line> (or <path> alone for module-scope)
Category:    Intent | Unnecessary | DRY | Performance | Security |
             Reusability | Silent-failure | Breaking-change |
             Architecture | Prior-finding-correction
Rule-class:  <2-3 word slug — e.g., silent-failure, n+1-query, error-code-wrong-branch>
Enclosing-symbol: <function/class/component containing the cited line, or "<module>">
Issue:       <one sentence>
Why it matters: <one sentence>
Suggested fix:  <one sentence, actionable>
Inverse risk:   <the failure mode this fix trades INTO if implemented literally,
                 or "none — pure addition">
Class-sites:    <H handled / N total> — from the class_completeness audit below
```

`Inverse risk` and `Class-sites` are REQUIRED on every finding that proposes a code
change. They exist because the two largest sources of repeat review rounds are
(a) the reviewer's own suggested fix introducing a new defect, and (b) a fix landing
on the cited site while identical sibling sites go untouched.

`Rule-class` and `Enclosing-symbol` are NEW required fields — they let the critic compute a stable finding ID (`sha1(file::enclosing_symbol::rule_class)`) that survives line shifts and rewordings across review rounds. See `references/finding-state-schema.md`.

End with:

```
Senior engineer approval: Yes | No | With changes
Approval reason: <one sentence>
Summary: <3 sentences — what the PR does, biggest concern, overall verdict>
Verdict: approve | comment | request-changes
```

### Subagent 2 (conditional) — Silent-failure hunter

Only dispatch if `INCLUDE_SILENT_FAILURE_HUNTER = true`.

- `subagent_type`: `pr-review-toolkit:silent-failure-hunter`
- Prompt: `"Check for silent failures, swallowed errors, and inadequate error handling in the GitHub PR at <url>. Fetch the diff yourself via 'gh pr diff <url>'."`

Pass it the SAME context packet as Subagent 1 — intent model, prior findings, and the
resolved `rule_class` list from `PRIOR_STATE`. Dispatched with only a URL it re-finds
already-settled issues and misses anything the diff doesn't make obvious, because it has no
idea what the PR is for or what earlier rounds already closed.

### Subagent 3 (conditional) — Cross-cutting reviewer

Dispatch when `SIZE_MODE` is `parallel-chunked` or `parallel-chunked-confirm`. Skip otherwise
— in unchunked modes Subagent 1 already sees every file.

- `subagent_type`: `general-purpose`
- Scope: the WHOLE PR. It is the only reviewer permitted to report across file boundaries.

```
You are reviewing a GitHub PR at <url> for CROSS-FILE patterns ONLY. Other reviewers cover
each file in isolation — do not duplicate them. Fetch the diff yourself.

Goal: <intent model>
Prior findings already reported: <list>

Report ONLY findings that require seeing two or more files at once:

1. Same defect class in sibling files — one call site handled, an identical one not.
   Example shape: three hooks in a component get an error branch and the fourth doesn't;
   two components get role="alert" and the third doesn't.
2. One concern handled inconsistently across files — differing validation, error handling,
   auth checks, or null handling for the same logical thing.
3. A value, sentinel, or thrown error introduced in one file whose consumers in OTHER files
   don't handle it.
4. A guard or contract asserted in one file and contradicted in another.

For each finding, cite EVERY file:line involved — a finding naming only one file is by
definition not cross-cutting; drop it. Use the standard output format including
`Rule-class`, `Class-sites`, `Inverse risk`, and the `class_completeness:` audit.

"No cross-file findings" is a complete and acceptable answer. Do not manufacture one.
```

---

## Phase 3: Critic pass (main context)

After ALL subagents return, main Claude runs the critic pass, splitting the work on one line:

- **Judgment stays in main.** Dedupe, the 3-prong test, false-positive rules, suppressions,
  ranking, verdict. These need the intent model and the prior-review timeline, which main
  already holds. Shipping them to a subagent would mean re-sending all of it.
- **Evidence-gathering goes to subagents.** Anything that means grepping the repo,
  enumerating callers, or re-reading files at HEAD. These burn context proportional to the
  codebase and return a few lines of verdict. Main should hold the verdict, not the search.

Steps 4.55, 4.9 and 6 dispatch subagents (see **Phase 3 verification subagents** below).
Everything else runs inline. The subagent returns a compact structured verdict; main decides
what to do with it. Never let a verification subagent decide severity, drop a finding, or
write to the state file — it reports, main rules.

Execute in order:

### Phase 3 verification subagents

All three are `general-purpose`, dispatched in ONE message so they run in parallel, and all
three fetch what they need themselves (`gh pr diff`, Grep, Read) rather than being handed the
diff. Each returns a compact block — no prose, no restated file contents.

Cap: batch findings into at most 4 subagents. If a batch would exceed ~12 findings, split it.
If a verifier errors or returns empty, run its step inline in main and note
`<verifier> unavailable — verified inline` in the Phase 4 header. Never skip the step.

**V1 — Class-sweep verifier** (step 4.55). Dispatch when ANY finding has a missing
`class_completeness` audit, a verdict of `INCOMPLETE`, or an `Enclosing-symbol` that is
exported or lives in a shared package.

```
For each finding below, find EVERY site in the repo matching its rule_class signature —
not just the cited one. If the symbol is exported, include its callers.
Report per finding, nothing else:
  finding: <id>
  signature: <what you actually searched>
  searches: <tool>("<query>", "<path>") → <N>
  sites:
    - <file:line>: affected | not-affected — <one clause>
  unreported_sites: <count of affected sites the finding did not mention>
Do not judge severity. Do not suggest fixes. Report sites.
```

**V2 — Regression sweep verifier** (step 4.9). Dispatch when `CURRENT_ROUND >= 2` and
`PRIOR_STATE.findings` contains any entry with `status in {resolved, dismissed, wontfix}`.
Pass each entry's `id`, `rule_class`, `class_sites`, `inverse_risk`, `depends_on`,
`commit_sha_resolved`, and the current `head_sha`.

```
These findings were closed in earlier rounds. At the CURRENT head, verify each is still
closed. For each, check in this order:
  1. class_sites — is every listed site still handled? Are there NEW sites of this
     rule_class that the current diff introduced?
  2. inverse_risk — has that specific failure mode appeared in the resolving code?
  3. depends_on — is the code condition the dismissal rested on still true?
Report per finding, nothing else:
  id: <id>
  verdict: still-closed | regressed | dismissal-void
  evidence: <file:line + one sentence — REQUIRED when not still-closed>
Default to still-closed when you cannot find evidence of a regression. Do not speculate.
```

**V3 — Deep gap check** (step 6). Dispatch when `additions + deletions >= 500` — exactly
the case where step 6's own caveat tells main to skip the gap check. A subagent has the
context budget main lacks, so the gap check runs on big PRs instead of being skipped.

```
Fetch the diff yourself. The reviewers reported findings in these categories: <list>.
For each category with NO findings — Q1 intent, Q2 unnecessary, Q3 DRY, Q4 performance,
Q5 security, Q6 reusability — check whether the diff genuinely has nothing, or whether it
was overlooked. Report ONLY genuine gaps, in the standard finding format. "No gaps" is a
complete and acceptable answer.
```

### 1. Dedupe

Merge findings describing the same issue across reviewers AND within a reviewer's output.

**Dedupe key**: `(file_path, post_image_line, normalized_symbol_name)` — NOT `Category`. For findings without a valid diff line, use `"file-level:<category>"` in place of `post_image_line` (e.g., `(config.ts, file-level:Architecture, missingvalidation)`). Two findings on the same `(file, line, symbol)` are duplicates regardless of category — merge, keep higher severity, concatenate reasoning.

Normalize symbol names: lowercase + strip CamelCase boundaries (`renderUserCard` → `renderusercard`).

Dedupe priority when merging:
1. Severity wins: `Serious > Moderate > Minor`.
2. Category precedence for ties: `Security > Reusability > Silent-failure > Breaking-change > Performance > DRY > Unnecessary > Intent > Architecture`.
3. Confidence: keep highest.
4. **Site list always survives.** When a cross-file finding (Subagent 3) merges with a
   single-file one, keep the UNION of their sites in `Class-sites`. Collapsing a
   "3 of 4 hooks handled" finding down to the one hook a chunk reviewer happened to cite
   re-creates the exact blind spot Subagent 3 exists to close.

### 1.5. Cheap line-count sanity

For each finding with a `File: <path:line>` reference, before expensive Step 2 verification:

1. Compute `max_valid_line(path)` from `gh pr view --json files`:
   - NEW file: `max_valid_line = file.additions`
   - MODIFIED file: `max_valid_line ≈ file.additions + file.deletions_original_side + ~200 buffer`. When suspicious, fetch HEAD file length via `gh api repos/<owner>/<repo>/contents/<path>?ref=<head-sha>`.
   - Cheap heuristic: if `line > (file.additions + 500)` for a NEW file, almost certainly hallucinated.

2. If `cited_line > max_valid_line`: drop and log `hallucinated reference (line <N> exceeds <M> available)`. Do NOT auto-shift lines — drop, don't rescue.

### 2. Verify `file:line`

The full diff is in main context (stashed in Phase 1). Not token waste — only way main can verify references independently of the subagent's now-discarded context.

- PRs `< 500` lines: verify ALL findings.
- PRs `>= 500` lines: verify all Critical + Serious; for Moderate/Minor on files not fully stashed, fetch per-file patch:
  ```bash
  gh api repos/<owner>/<repo>/pulls/<num>/files --jq '.[] | select(.filename=="<path>") | .patch'
  ```
- **Routing**: line-numbered finding → line verification. No line number → file-level verification. Mutually exclusive.
- **Line verification**: `<path:line>` must refer to a line on the **post-image / new side** of the hunk. References to old-side-only, deleted lines, or lines not in any hunk → DROP, log `hallucinated reference`.
- **File-level verification**: verify `path` appears in PR's changed files. Not in changed files → DROP, log `hallucinated file reference`.

### 3. Drop already-known

If a finding matches "Prior findings" from Phase 1 AND is NOT marked `Prior-finding-correction`: DROP, log `already reported in prior review`.

### 4. Challenge with the 3-prong test

For each remaining finding, drop **only if ALL three** hold:
- (a) symptom is purely cosmetic or a nit
- (b) no user-visible behavior changes if ignored
- (c) no downstream refactor cost

Keep if **ANY one** fails. Log drops as `noise / 3-prong test`. Replaces vibes-based "would a senior engineer care?" with falsifiable test.

### 4.5. Reusability audit verification

For each reviewer's "Q6 No issues" response, verify the audit. Catches: missing audit field, insufficient search count, class-method definitions not counted.

#### 4.5a — Count new definitions in the diff

Match added lines (starting with `+`) against:

```
+\s*(export\s+(default\s+)?)?(async\s+)?(function|class|interface|type)\s+\w+
+\s*(export\s+)?const\s+\w+\s*(:\s*[^=]+)?=\s*(async\s+)?(\([^)]*\)|[a-zA-Z_$][\w$]*)\s*=>
+\s*(export\s+default\s+function|export\s+default\s+class|export\s+default\s+async\s+function)\s+\w+
+\s+(private|protected|public|async|static)(\s+(private|protected|public|async|static))*\s+\w+\s*\(
```

Patterns cover: standard function/class/interface/type, arrow-function consts, default exports, **class methods inside class bodies** (NestJS-style services). Track `{`/`}` nesting from the nearest `class X {` to count only methods inside class blocks.

Combine into `new_definitions_count`.

#### 4.5b — Count and parse the audit

Match `(?:reusability|reuse)_searches?:` (canonical: `reusability_searches:`).

Three outcomes:

1. **Field entirely missing** — PROMPT NON-COMPLIANCE. Drop ALL Q6 "No issues" claims AND add a Serious finding "Reviewer did not include `reusability_searches:` audit — Q6 was not performed."

2. **Field present with sentinel `N/A (no new top-level definitions in diff)`** — verify `new_definitions_count == 0`. If holds, audit is valid. If not, treat as shallow per outcome 3.

3. **Field present with entries** — count entries. If `searches_count < new_definitions_count`, drop "Q6 No issues" claims AND add a Moderate finding "Reusability check was shallow (<S> searches for <N> new definitions) — manual scan recommended before merging."

   Additionally: for each entry where `N > 0` but `verified:` is missing or says `no`, mark the corresponding Q6a claim (if any) as low-confidence and log `search returned hits but reviewer did not verify semantic match`.

#### 4.5c — Log all drops to Filtered Out for auditability.

### 4.55. Class-completeness verification

For each surviving finding that proposes a code change, check its `class_completeness:` audit.

Batch every finding needing verification into **V1 — Class-sweep verifier** and dispatch it
alongside V2/V3. Main applies the rules below to what V1 returns.

1. **Field missing entirely** — the sweep was not run. Do NOT drop the finding; V1 runs the
   sweep. Derive the signature from `Rule-class`, and append V1's result to the finding. Log
   `class sweep run by verifier — reviewer omitted audit`.

2. **`verdict: INCOMPLETE`** — the reviewer found sites it did not report. Fold every
   unreported site into the finding's `Class-sites` count and list them in the finding
   body. A finding covering 1 of 4 sites, reported as if it covered the defect, is how a
   round-N finding becomes a round-N+1 finding.

3. **`verdict: COMPLETE` with `search:` naming zero tool calls** — treat as missing (case 1).

4. **Shared-symbol escalation**: if the finding's file sits in a shared package (use the
   Phase 1 repo map) OR `Enclosing-symbol` is exported, the sweep MUST cover callers, not
   just the defining file. If it doesn't, run the caller search yourself and note the
   behavioral delta at each call site. Fixes to shared code change behavior at call sites
   nobody asked about — enumerate them before the fix ships, not after.

Findings are never dropped by this step; they are widened. Log every widening.

### 4.56. Inverse-risk verification

For each surviving finding with a `Suggested fix:`:

1. **`Inverse risk:` missing** — derive it yourself before printing. Ask what breaks if
   the suggestion is implemented literally and nothing else changes.

2. **Inverse risk is worse than the finding** — the suggestion is not a fix. Either
   rewrite it into one that doesn't trade the defect for a bigger one, or keep the
   finding and replace the suggestion with `no safe one-line fix — needs design`.
   Never ship a remedy the review itself believes is a net negative.

3. **Record it.** The `inverse_risk` string is persisted to `.claude/review-state/<pr>.yml`
   on the finding. Round N+1 checks it FIRST, before hunting anything new — see step 4.9.

This step exists because the reviewer's own suggestions are implemented verbatim by
`/fix-pr-review`. An unvetted one-sentence remedy becomes production code.

### 4.6. Apply false-positive rules table

A unified iterator over a rules table (replaces the prior 4.6/4.7/4.8/4.9 individual filters). Each rule has: `id`, `trigger` (regex matched against `Issue` or `Why`), `evidence_check` (a callable that returns `evidence_present | evidence_absent | inapplicable`), `action` (`drop` / `downgrade-1` / `downgrade-1-and-note`).

Apply each rule in order. A rule fires when (1) `trigger` regex matches AND (2) `evidence_check` returns the expected branch. Log each fire to Filtered Out with the rule `id` + reason.

Rules:

```yaml
rules:
  - id: wrapped-coercion
    trigger: |
      (?i)\.toFixed\(|\.toString\(|\.toLocaleString\(|String\(
    evidence_check: |
      Verify cited line in stashed diff. Drop if the call is structurally enclosed by
      Number(...) / parseFloat(...) / parseInt(...) / unary +(...) on the SAME line.
      Anchored patterns:
        =\s*(Number|parseFloat|parseInt|\+)\s*\(\s*<call>
        :\s*(Number|parseFloat|parseInt|\+)\s*\(\s*<call>
        return\s+(Number|parseFloat|parseInt|\+)\s*\(\s*<call>
      Do NOT match across lines, do NOT match sibling args (e.g., foo(bar.toFixed(1), Number(y))).
    action: drop
    log_reason: "wrapped-coercion FP — call wrapped in Number(...) on same line"

  - id: intent-alignment
    trigger: |
      (?i)unscoped|semantic (drift|change)|not mentioned|not in (the )?description|scope creep|out of scope|outside (the )?stated goal|beyond PR scope|undeclared change|silently changes behavior
    evidence_check: |
      Tokenize PR intent (title + linked-issue title + first 200 chars body):
        - Split on whitespace, [_\-\.\/], camelCase boundaries
        - Lowercase, drop tokens <= 2 chars, drop stop words (add fix update refactor use new the a of in for to and or is be)
      Tokenize finding's claim (cited File: + symbol from Issue) same way.
      Precondition: |finding_tokens| >= 3 AND |intent_tokens| >= 3. If either < 3, INAPPLICABLE.
      Compute overlap = |intent ∩ finding| / |finding|.
      If overlap >= 0.5 → return evidence_present (downgrade).
      If overlap = 1.0 AND severity = Minor → return evidence_present_drop (drop).
    action: downgrade-1-and-note   # plus drop-if-Minor for overlap=1.0 case
    note: "Note: this change aligns with PR intent (\"<keywords>\"). Re-verify before merging — may be intentional."
    log_reason: "intent-alignment downgrade — <N>/<M> finding tokens match PR intent"

  - id: library-behavior-citation
    trigger: |
      (?i)<Library> (does|returns|is)|float precision|IEEE 754|floating-point|fragile|unsafe edge case
    evidence_check: |
      Check if Why or Fix contains a citation:
        - node_modules/<lib>/ path matching the library named in Issue
        - URL on official docs (github.com/<org>/<lib>, <lib>.dev, docs.<lib>.io) or spec/RFC
        - Reproducible code snippet with concrete input/output values
        - Linked repo issue or failing test case
      If NO citation found:
        Critical → downgrade to Serious + note (evidence_present_partial)
        Serious  → downgrade to Moderate + note
        Moderate → DROP
        Minor    → DROP
    action: severity-conditional   # see severity ladder above
    note: "Note: unverified library-behavior claim — empirical check required before acting."
    log_reason: "library-claim — <severity> with no citation"

  - id: default-fallback
    trigger: |
      (?i)\b(dropped|stripped|lost in|never propagated|not (propagated|passed|forwarded|carried))\b|falls? back to|fallback to
    evidence_check: |
      Extract claimed-dropped field name (backtick-quoted ID, or first camelCase/snake_case token near matched verb).
      Search stashed diff first; fetch via gh api contents only if needed (cache per critic pass).
      Look for ANY of:
        - ALL_CAPS constant whose name contains a camelCase segment of the field
          (e.g., field currencyCode → match DEFAULT_CURRENCY_CODE, FALLBACK_CURRENCY)
        - camelCase default: \b(default|fallback|initial)[A-Z]\w*\b ending with field segment
        - config-object default: config\.(default|fallback)\w*, defaults\.\w+, <obj>\.fallback\w*
        - Coalesce on receiving side: ??\s*<const>, ||\s*<const>
        - Comment within 10 lines: (?i)defaults? to|always|intentionally|by design|only\s+\w+\s+(makes sense|is supported|applies)
      If a "by design" / "only X makes sense" / "always X" comment is found → evidence_present_drop (DROP).
      Else if any named-default signal → evidence_present (downgrade).
    action: downgrade-1-and-note   # plus DROP if "by design" comment found
    note: "Note: a named default (<CONST>) handles the absent value — likely intentional design, not a propagation bug."
    log_reason: "default-fallback — found <CONST>"
```

Apply each rule sequentially. Log every fire. The rules table is the single source of truth for false-positive filtering — adding a new false-positive class is a one-row YAML edit, not a new prose section.

### 4.9. Proactive regression sweep (runs BEFORE suppression)

Skip entirely when `CURRENT_ROUND == 1`.

Step 4.95 below only re-examines a resolved finding if a reviewer happened to re-raise
its exact ID. That catches regressions by luck. This step catches them on purpose.

Dispatch **V2 — Regression sweep verifier** over EVERY finding in `PRIOR_STATE` with
`status in {resolved, dismissed, wontfix}`, regardless of whether any reviewer mentioned it
this round. V2 gathers the evidence; main applies the rules below to its verdicts:

1. **Re-verify by `rule_class`, not by ID hash.** The ID is
   `sha1(file::enclosing_symbol::rule_class)`, so the same defect resurfacing in a
   sibling symbol produces a DIFFERENT id and escapes matching entirely. Search the
   stored `class_sites` — plus any new sites the current diff added — for the class
   signature. A resolved finding whose class has an unhandled site is not resolved:
   reopen it with `status: regression` and cite the specific site.

2. **Check the stored `inverse_risk`.** If the fix that resolved this finding recorded
   an inverse risk, verify that failure mode has NOT appeared. This is the single
   highest-yield check in the whole pass — the dominant cause of round-N findings is
   round-N−1's fix landing on its own inverse.

3. **Re-validate dismissals against `depends_on`.** A `wontfix` records the code
   condition its rationale rests on. If a later commit invalidated that condition, the
   dismissal is void — reopen with `status: still-active` and note which commit voided it.

4. **Attribute the lineage.** Any finding this sweep reopens, or any new finding whose
   cited lines were introduced by a commit that fixed an earlier finding, gets
   `caused_by: <prior finding id>`. Phase 4 reports the count. The lineage is already
   visible in practice — recording it is what lets the verdict act on it.

### 4.95. Apply prior-state suppression (multi-round dedup)

For each remaining finding:

1. Compute `id = sha1(<file>::<enclosing_symbol>::<rule_class>).hexdigest()[:10]`.
   - If subagent failed to emit `Rule-class:` or `Enclosing-symbol:`, synthesize: `enclosing_symbol = "<module>"`, `rule_class = first 3 words of Issue (lowercased, space-joined, stop-words filtered)`. Log a warning so the prompt can be tuned.

2. Look up `id` in `PRIOR_STATE.findings`. If a match exists with `status in {resolved, dismissed, wontfix}`:

   - **`status == resolved`**: verify the diff between `commit_sha_resolved..HEAD` doesn't reintroduce the issue.
     - Re-introduced (resolving change reverted) → set this finding's status to `regression`, keep it (will be flagged as a fresh active finding with regression history in Phase 4).
     - Not re-introduced → DROP, log `prior-state suppression — resolved in round <round_resolved> by commit <commit_sha_resolved>`.

   - **`status in {dismissed, wontfix}`** → DROP, log `prior-state suppression — <status> in round <round_resolved>: "<dismissal_reason>"`.

3. NEVER use the word "deferred" in any output, log, or comment. Use exactly one of: `resolved` (with commit), `dismissed` (with reason), `wontfix` (with reason), `still-active`, `regression`.

### 5. Confidence-based drop

Drop all `Confidence: low` findings at Moderate or Minor. Log as `low-confidence filler`. **Keep** low-confidence Critical/Serious — humans want risky-but-uncertain flags.

### 5.5. Apply project-level suppressions

If `SUPPRESSIONS` was loaded in Phase 1, match each remaining finding:

1. Check if `Issue` text contains `pattern` (case-insensitive substring).
2. If `category` set, also check finding's `Category` matches exactly.
3. If `file` set, also check finding's `File` path contains the string.

If ALL specified conditions match: DROP, log `suppressed by .claude/review-suppressions.yml: "<reason>" (pattern: "<pattern>")`.

**Critical/Serious override**: suppressions can drop findings at any severity. If a team explicitly decided a pattern is acceptable, respect that even for Serious. The `reason` field makes it auditable.

### 6. Gap check (Q1–Q6, Q7–Q9 if schema PR)

For any question category where Subagent 1 said nothing, briefly think about whether the diff has anything in that category. Add findings if you spot misses. Include Q7–Q9 only if `INCLUDE_SCHEMA_CHECKS = true`.

**Large-PR routing**: if `additions + deletions >= 500` AND you don't have the full diff
loaded in main, do NOT hallucinate gaps from the file list — but do NOT skip the check
either. Route it to **V3 — Deep gap check** instead, and fold its findings in here.
Skipping the gap check on large PRs meant the check was absent exactly when it mattered
most; delegating it costs one subagent and restores coverage.

### 7. Rank by severity

Critical > Serious > Moderate > Minor.

### 8. Decide verdict (category-aware)

- Any **Critical** → `request-changes`
- Any **Serious** in `Category = Security | Silent-failure | Breaking-change | Reusability` → `request-changes` (these are never "just a comment"; Reusability is escalated because reimplemented code is a correctness risk via divergent fixes)
- Any other Serious → `comment`
- Only Moderate/Minor → `approve` (with comments)
- No findings → `approve`

#### Severity ratchet (`CURRENT_ROUND >= 3`)

From round 3 onward, **only Critical and Serious may block.** Moderate and Minor
findings do NOT hold the PR: route them to `ship-with-followups` — report them in the
body under a `Follow-ups (non-blocking)` heading and offer to file them as issues in
the Phase 4 post-review prompt.

Rationale: a PR that has already absorbed two rounds of fixes is being held by a
long tail, and each additional round of Moderate-chasing has a measurable chance of
introducing a Serious defect. The tail is worth less than the churn it costs.

The ratchet changes the VERDICT only. It never suppresses a finding, never lowers a
severity, and never applies to Critical or Serious.

#### Regression-dominance signal

Compute `regression_share` = (findings with `caused_by` set) / (total active findings).

If `regression_share > 0.5` at any round, prepend to the verdict reason:

> Over half of this round's findings were introduced by the previous round's fixes.
> Patching site-by-site is not converging — this module needs a design pass.

Say it plainly. A reviewer that documents a fix-cascade round after round without
naming it lets the loop continue unchallenged.

### 9. Decide Senior-engineer approval

A binary verdict (with middle option):

- **No** — verdict is `request-changes`, OR Q1 identified an intent gap, OR any Critical exists
- **With changes** — Serious findings exist in any category, OR 3+ Moderate findings
- **Yes** — otherwise

Write a one-sentence approval reason grounded in the most important finding (or absence — e.g., "Does what the issue asks, no Serious issues").

---

## Phase 4: Output

### Print this block to terminal, always

```
# PR Review: <title> (#<number>)

**Senior engineer approval**: <emoji> <Yes | No | With changes> — <one-sentence reason>
**Verdict**: <emoji> <approve | comment | request-changes>
**Goal**: <intent goal>
**Size**: <additions>/<deletions> across <N> files
**Reviewers**: <list, with "(unavailable)" marker for any failed subagent>
**Round**: <CURRENT_ROUND> (<active>/<resolved>/<dismissed> findings carried across rounds)
**Convergence**: <N> new · <C> caused by earlier fixes · <R> regressions reopened · <F> carried
<trend line — omit at round 1>

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

## Follow-ups (non-blocking)
<round >= 3 only: Moderate/Minor findings the severity ratchet released from blocking.
 Omit this heading entirely at rounds 1-2, where they appear under their own severity.>

## Filtered out (<count>)
<dropped findings with reasons — for auditability>

## Multi-round status
<for each finding in PRIOR_STATE: id, file, status, round_resolved/dismissed, dismissal_reason. Useful for "did I really ship M3 in round 5?" scanning.>
```

### Verdict and approval emoji mapping

**Senior engineer approval**: Yes → ✅ · No → ❌ · With changes → ⚠️
**Verdict**: approve → ✅ · comment → 💬 · request-changes → ❌
**Severity headers**: Critical → 🔴 · Serious → 🟠 · Moderate → 🟡 · Minor → 🔵

The Senior engineer approval line goes on top — single field a human wants to see first. Filtered out section is mandatory in terminal output — without it, you can't tell when the critic is over-filtering. Multi-round status is mandatory when `PRIOR_STATE.findings` is non-empty.

### Convergence trend line

Mandatory from round 2. One sentence, stating whether the PR is converging and why not:

```
Convergence: 4 new · 3 caused by earlier fixes · 1 regression reopened · 2 carried
Trend: 75% of this round's findings came from round 4's fixes. Not converging.
```

Pick the trend sentence from what the numbers say:
- `caused_by` share > 0.5 → `Not converging — the fixes are generating the findings.`
- New findings falling round over round, none caused_by → `Converging — tail is shrinking.`
- New count flat across 3+ rounds → `Stalled — same volume each round; scope may be growing.`

If a verdict REVERSES an earlier approval, say so explicitly in the Summary with the
reason and the two SHAs, e.g. *"I approved this at `dd142e0`. I'm reversing that,
because `e4f7432` made one thing worse than it was."* An unexplained reversal reads
as the tool moving the goalposts; a stated one reads as the review doing its job.

### Wall-time instrumentation (end)

Compute total elapsed + per-phase from `PHASE_START_*` timestamps. Append before Filtered Out:

```
## Timing
Phase 1: <s> (metadata + diff + intent + repo map + state load)
Phase 2: <s> wall / <sum> CPU (parallel: <N> subagents)
Phase 3: <s> (dedupe + verify + 3-prong + reusability audit + FP rules + prior-state + suppressions + gap + verdict)
Phase 4: <s>
Total:   <s>
```

### Self-review detection

Before asking whether to post:

```bash
VIEWER=$(gh api user -q .login)
AUTHOR=$(gh pr view <url> --json author -q .author.login)
[ "$VIEWER" = "$AUTHOR" ] && SELF_REVIEW=true
```

**GitHub silently coerces `--request-changes` to `--comment` when reviewer is the PR author.** GitHub quirk, not a skill bug.

If `SELF_REVIEW=true`:

If review has zero findings: print "No findings — nothing to fix." and exit. Otherwise:

```
header: "Self-review"
text: "Self-review detected — you're the PR author. Posting to GitHub is unnecessary. Fix these findings directly?"
options:
  - "Fix now (Recommended)" — Auto-invoke /fix-pr-review; no GitHub posting
  - "Keep local only" — Review stays in terminal
  - "Post anyway" — Post as COMMENT state (GitHub coerces self-reviews)
```

On "Fix now":
1. Write findings to `/tmp/review-pr-<num>-findings.md` with explicit field labels (NOT the summary table — `/fix-pr-review` parses these labels):
   ```
   ## Findings

   Severity: Serious
   File: src/auth.ts:47
   Category: Silent-failure
   Rule-class: silent-failure
   Enclosing-symbol: handleStdinError
   Issue: Unhandled stdin error can crash process
   Why it matters: Production crash on communication failure
   Suggested fix: Add error event handler
   ```
2. Invoke `/fix-pr-review /tmp/review-pr-<num>-findings.md`.
3. Skip post-review prompts — `/fix-pr-review` handles its own workflow.

### Verdict-body sync check (re-runs)

If `last_posted_review_id` exists in cache, compare last-posted body verdict against GitHub state:

```bash
LAST_POSTED_REVIEW_ID=$(jq -r '.last_posted_review_id // empty' "$CACHE_FILE")
if [ -n "$LAST_POSTED_REVIEW_ID" ]; then
  LAST_POSTED_STATE=$(gh api "repos/<owner>/<repo>/pulls/<num>/reviews/$LAST_POSTED_REVIEW_ID" --jq .state)
  LAST_POSTED_BODY_VERDICT=$(gh api "repos/<owner>/<repo>/pulls/<num>/reviews/$LAST_POSTED_REVIEW_ID" --jq .body | grep -oE '\*\*Verdict\*\*:\s*`?(approve|comment|request-changes)`?' | sed 's/.*\(approve\|comment\|request-changes\).*/\1/')
fi
```

If they drifted:

> **Previous review's body verdict (`<body>`) does NOT match GitHub state (`<state>`).** Likely cause: self-review coerced to `comment`, or manual edit in GitHub UI. The current run's output will not re-post over the previous review — add a NEW review via "Post now" if you want to update. (Rolling-review path will edit the body in place — see references/github-posting.md Step 0.)

### Select findings to post (multiSelect)

Never post findings unilaterally — the user picks what goes to GitHub. Skip this step only if:
- There are zero findings (verdict `approve` with no comments), or
- The user already chose "Fix now" / "Keep local only" from the self-review prompt.

AskUserQuestion:

```
header: "Findings"
text: "Select which findings to post as review comments. Unselected findings stay local."
options: [one option per finding: "<severity> <file:line> — <Issue, first ~60 chars>", ordered Critical → Minor]
multiSelect: true
```

- If findings exceed the option limit, split into multiple multiSelect questions grouped by severity (Critical/Serious first).
- Deselected findings: move to Filtered out with reason `user-deselected before posting`. They do NOT post, are excluded from the summary body's finding count, and are recorded in the state file as `dismissed` with `dismissal_reason: user-deselected` so later rounds don't re-raise them.
- If deselection removes every finding that drove the verdict, recompute the verdict (Phase 3 step 8) over the selected set before composing the summary body.
- If the user deselects everything, skip posting entirely — same outcome as "Keep local".

### Then ask

AskUserQuestion (cursor-selectable):

```
header: "Post review"
text: "Post this review to the PR? Verdict: <verdict>"
options:
  - "Post now" — Submit as <verdict> (uses rolling-review if prior /review-pr review exists)
  - "Keep local" — Don't post; stays in terminal
  - "Edit first" — Open body in $EDITOR before posting
```

### Re-review thread resolution (before posting)

If this is a re-review AND `posted_comments` cache exists:

1. **Identify resolved findings**: compare current findings against `posted_comments` via dedupe key. A cached finding NOT in current findings AND whose `id` is now `status: resolved` in `PRIOR_STATE` is "resolved this round."

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

### If yes — Post via references/github-posting.md

The full posting flow lives in `references/github-posting.md` — load it now. It handles:

- **Step 0**: detect prior `<!-- review-pr:run -->` tagged review on the PR. If found within 30 days, use the rolling-review path (edit body in place, attach only NEW threads); otherwise create a fresh review.
- **Steps 1-2**: compose summary body (with marker comment) + per-finding review comments.
- **Step 3**: pre-posting hunk validation (line vs file-level routing).
- **Step 4 / 4-rolling**: REST POST PENDING (or GraphQL `updatePullRequestReviewBody` for rolling).
- **Step 5 / 5-rolling**: GraphQL `addPullRequestReviewThread` for file-level (skip threads already in `posted_comments` on rolling path).
- **Step 6**: GraphQL `submitPullRequestReview` (skipped on rolling — prior review already submitted).
- **Step 7**: failure recovery with disclosed partial state.
- **Step 8**: cache write-back + state file update + thread resolution for fixed findings.

Pass into the reference: `<owner>`, `<repo>`, `<pr-num>`, `<head_sha>`, `CURRENT_ROUND`, summary body content, list of findings (line-level + file-level), `$CACHE_FILE` path, `$STATE_FILE` path.

### If edit first

Write summary body to `/tmp/review-pr-<num>.md`, open in `${EDITOR:-vi}`, then post after editor closes. Review comments (line-level + file-level) are NOT editable via this flow — only summary body. To remove a specific comment, edit the findings list before "Post now".

### Post-completion next actions (context-aware)

AskUserQuestion. Skip entirely if:
- Review had zero findings (verdict was `approve` with no comments)
- User chose "Fix now" or "Keep local only" from self-review prompt
- `/fix-pr-review` was already invoked

**For external PRs** (reviewer is NOT the author):

```
header: "Next"
text: "Review posted. What would you like to do next?"
options:
  - "Re-review later" — Re-run /review-pr after author pushes fixes
  - "Done" — Nothing more — end the session
```

On "Re-review later": print `Run /review-pr <url> again after fixes` and exit — do NOT immediately re-invoke (author hasn't pushed yet).

**The AskUserQuestion above is the final turn of this skill.** No freeform follow-up text question.

**For self-reviews** (user chose "Post anyway"):

```
header: "Next"
options:
  - "Fix findings" — Run /fix-pr-review on this PR
  - "Done" — End the session
```

On "Fix findings": invoke `/fix-pr-review <url>`. **Final turn of the skill.** No follow-up.

---

## Error handling

- **`gh` not installed/authed** → fail fast: `Run 'gh auth login' and retry.`
- **Invalid PR URL** → `Couldn't parse PR URL. Expected: https://github.com/owner/repo/pull/NUMBER`.
- **PR not accessible (404 / GraphQL error)** → `Couldn't access PR. Check repo access; try 'gh auth refresh -s repo'.`
- **PR is closed/merged** → warn but proceed (post-mortem review).
- **PR is a draft** → note in output header, proceed.
- **PR has no changes** → short-circuit (Phase 1).
- **Phase 2 subagent failure** → continue with remaining; abort only if ALL fail.
- **Network errors on `gh`** → surface, don't silently fall back.
- **Failed state-file write** → log warning, do not block posting. State file is best-effort persistence.

## Rules

- **NEVER** run the review twice in a single invocation.
- **NEVER** post to the PR without explicit user confirmation via "Post now" / "Edit first" (except self-review "Fix now" which skips posting).
- **NEVER** post a finding the user deselected in the "Select findings to post" checkpoint — log it as `user-deselected before posting`.
- **NEVER** stop mid-list in batch mode, and never let a batch subagent post or ask questions — all checkpoints defer to the single end-of-run prompt, asked only after the consolidated report is written.
- **NEVER** post the "Filtered out" section to GitHub — local audit only.
- **NEVER** fabricate file:line references; omit line if unsure (file-only routes to file-level).
- **NEVER** skip Phase 1's stop-and-ask — weak intent is the biggest slop source.
- **NEVER** skip the grounding pass in Subagent 1 — findings not tracing to mechanical grounding bullets are hallucinations.
- **NEVER** skip the critic pass — second-biggest anti-slop lever after the reviewer prompt.
- **NEVER** re-post review comments for findings already on the PR with active threads — duplicate noise.
- **NEVER** create a new top-level review when a prior `<!-- review-pr:run -->` tagged review exists within 30 days — use the rolling-review path (edit body in place, attach NEW threads only).
- **NEVER** use the word "deferred" — use `resolved` (with commit), `dismissed` (with reason), `wontfix` (with reason), `still-active`, or `regression`.
- **ALWAYS** use `gh api` for posting (hybrid: summary body + review comments). Fall back to `gh pr review --body` only if API call fails after Step 7 user-chosen path.
- **ALWAYS** resolve threads for findings now in `status: resolved` before posting new findings. Best-effort — failures don't block posting.
- **ALWAYS** write `.claude/review-state/<pr>.yml` after a successful run (or after "Keep local"). State file persistence is what makes round N+1 understand round N's outcomes.
