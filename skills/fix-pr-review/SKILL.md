---
name: fix-pr-review
description: Triage and fix CodeRabbit / review-pr findings on a GitHub PR, then reply + resolve conversations. Classifies each finding (FIX/DISMISS/DEFER/DISAGREE/NEEDS-INPUT), runs /done, posts specific replies. Use on CodeRabbit review URLs, PR URLs, or local review files. Pairs with /review-pr.
---

# /fix-pr-review — Triage, Fix, and Resolve PR Review Comments

Consumes a PR review (CodeRabbit, `/review-pr`, or pasted), triages each finding, applies approved fixes, runs `/done`, and replies + resolves conversations on GitHub — all in one flow.

**Goal**: stop re-typing the same "plan → classify → fix → reply → resolve" loop on every CodeRabbit review. One command, one approval, done.

**Use AskUserQuestion for ALL user-facing decisions** — branch safety, stash confirmation, plan approval, per-fix confirmations, type-check failure triage, and post-completion next actions. Always present options as cursor-selectable choices, not plain text questions.

## Quick Reference

### Phase Overview

| Phase | What | Key Output |
|-------|------|------------|
| 1 | Prereqs, input detection, branch safety, baseline type-check | `BASE_SHA`, `repo_map`, `baseline_errors` |
| 2 | Fetch review data from GitHub or local file | Unified `Comment[]` array |
| 3 | Triage subagent: classify each finding via R-rubric | Triage plan (FIX/DISMISS/DEFER/DISAGREE/NEEDS-INPUT) |
| 4 | Plan approval gate: validate + user confirmation | Approved plan |
| 5 | Execute fixes: sequential edits + per-file type-check (β) | Modified files, `fix_status` per item |
| 6 | /done pipeline: fix-ts-errors → parallel-review → simplify | Clean code |
| 7 | Reply + resolve on GitHub (skipped for local files) | Threads resolved |
| 8 | Finalize: restore stash, report, suppressions write, next actions | Final report |

### R-Rubric Summary (Phase 3 STEP 4 — first match wins)

| Rule | Classification | Requires |
|------|---------------|----------|
| R1 | DISMISS — self-contradictory/wrong | — |
| R2 | DISMISS — hallucinated file:line | Dead-link re-anchor failed |
| R4 | DISMISS — already fixed | `prior_commit_sha` |
| R5 | DISMISS — contradicts CLAUDE.md | `claude_md_quote` |
| R3 | DISMISS — pure style/naming | Not reusability-flagged |
| R6 | FIX — bug/security/perf/correctness/reusability | `fix_plan` ≥30 chars, `change_class`, `test_scenario` |
| R7 | DEFER — valid but out of scope | Tracking reference |
| R8 | DISAGREE — legitimate technical disagreement | `disagree_rationale` |
| R9 | NEEDS-INPUT — ambiguous/needs user knowledge | `why_unclear` |

*R4/R5 are evaluated before R3 by design — high-signal dismissals take priority over style. See Phase 3 STEP 4 for rationale.*

### Key Cross-References

- **R-rubric definition**: Phase 3 STEP 4
- **Plan validation rules**: Phase 4 (validates fields required by R-rubric)
- **Fix execution routing**: Phase 5 (executes R6 FIX items)
- **Reply validator**: Phase 7 (format rules for GitHub replies)
- **Report grouping**: Phase 8 (groups by R-classification)
- **Suppressions**: Phase 3 STEP 0.5 (read) + Phase 8 (write)

## Usage

```
/fix-pr-review https://github.com/owner/repo/pull/123
/fix-pr-review https://github.com/owner/repo/pull/123#pullrequestreview-4089716169
/fix-pr-review https://github.com/owner/repo/pull/123#discussion_r3064352825
/fix-pr-review ./review.md            # local output from /review-pr
/fix-pr-review /tmp/review-pr-123-findings.md  # temp file from /review-pr self-review
/fix-pr-review                         # no arg → ask user to paste
```

Optional flags:

- `--dry-run` — stop after plan display, don't execute
- `--interactive` — per-item approval instead of single gate
- `--all-nitpicks` — full-triage nitpicks instead of default-dismiss
- `--skip-nitpicks` — hide nitpicks entirely

## Real CodeRabbit structure (for reference)

A CodeRabbit PR review is a single `PullRequestReview` submission containing:

1. **Review `body`** (markdown) with collapsed sections:
   - `Actionable comments posted: N` header
   - `🧹 Nitpick comments (M)` — nitpicks live here as **text only**, NOT as inline comments. No thread to resolve.
   - **`🤖 Prompt for all review comments with AI agents`** — a pre-formatted plain-text block listing ALL findings in AI-consumable form. **This is the primary parsing target.**
   - `🪄 Autofix (Beta)` with task-list checkboxes
   - `ℹ️ Review info`

2. **N inline `PullRequestReviewComment`s** (actionables only; nitpicks don't get inline comments):
   - Attached to `path` + `line`
   - Wrapped in `PullRequestReviewThread` with `isResolved` state
   - Independently resolvable via GraphQL `resolveReviewThread(input:{threadId})`
   - Bodies tagged with severity: `_⚠️ Potential issue_ | _🔴 Critical_`, `_🛠️ Refactor suggestion_ | _🟠 Major_`, etc.

**Severity taxonomy**: `🔴 Critical`, `🟠 Major`, `🟡 Minor`, `🔵 Refactor`, `🧹 Nitpick`.

**Who gets triaged**: the skill triages comments from **all reviewers** (CodeRabbit + humans + other bots), not only CodeRabbit. The "CodeRabbit" framing reflects the most common use case — human review comments are handled identically.

---

## Phase 1: Prereqs + input detection + branch safety (main)

### Prereq checks

```bash
command -v gh >/dev/null 2>&1 || { echo "Install gh CLI: https://cli.github.com"; exit 1; }
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "Not inside a git repo — cd into your clone first."; exit 1; }
gh auth status 2>&1 | grep -q "Logged in" || { echo "Run 'gh auth login' first"; exit 1; }
```

### Detect input type from the argument

- Contains `#pullrequestreview-<id>` → **review URL**
- Contains `#discussion_r<id>` → **discussion URL** (single comment + thread)
- Starts with `./` / `/` / ends with `.md` → **local file**
- Matches `https://github.com/<owner>/<repo>/pull/<num>` with no fragment → **PR URL**
- Empty → ask user to paste content or provide URL

### Ensure correct repo + branch (GitHub inputs only)

1. Parse `owner`, `repo`, `num` from the URL.
2. `gh repo view --json nameWithOwner -q .nameWithOwner` — compare with URL's `owner/repo`. Mismatch → fail fast: tell the user to `cd` into the right clone.
3. `gh pr view <url> --json headRefName,baseRefName -q .` → PR branch name + base branch.
4. `git branch --show-current` → current branch (returns empty string on detached HEAD).
5. Branch state handling:
   - **Empty output (detached HEAD)**: Use AskUserQuestion:

     Question:
       header: "Branch"
       text: "Detached HEAD detected. 'gh pr checkout <num>' will move you to the PR branch. Any uncommitted detached work may be lost."
       options:
         - label: "Checkout PR branch"
           description: "Run 'gh pr checkout <num>' to switch to the PR's head branch"
         - label: "Abort"
           description: "Stop here — I'll sort out my branch state manually"

     On "Checkout PR branch": run `gh pr checkout <num>`. On failure (conflicts, missing refs), surface the error and abort. On "Abort": exit.

   - **Different branch in the same repo**: Use AskUserQuestion:

     Question:
       header: "Branch"
       text: "You're on branch '<current>' but the PR uses '<pr-branch>'. Switch to the PR branch?"
       options:
         - label: "Switch branch"
           description: "Run 'gh pr checkout <num>' to move to the PR branch"
         - label: "Abort"
           description: "Stop — I'll checkout the right branch manually"

     On "Switch branch": run `gh pr checkout <num>`. On gh failure (conflicts, missing refs), surface the error and abort. On "Abort": exit.

   - **On the PR branch**: continue.

### Auto-stash uncommitted work (branch safety)

```bash
git status --porcelain
```

If non-empty, use AskUserQuestion:

   Question:
     header: "Stash"
     text: "Uncommitted changes detected. Auto-stash before applying fixes? Contents will be restored via 'git stash pop' at the end."
     options:
       - label: "Auto-stash"
         description: "Stash changes now — they'll be restored when the run completes"
       - label: "Abort"
         description: "Stop — I'll commit or stash my work manually first"

On "Auto-stash": run `git stash push -u -m "fix-pr-review auto-stash $(date +%s)"` and set `STASH_PUSHED=true`. If the run aborts, the user can find their work in `git stash list` as `fix-pr-review auto-stash <timestamp>`.
On "Abort": print "Commit or stash your uncommitted work first." and exit.

### Compute the merge base (for already-fixed detection later)

```bash
BASE_SHA=$(git merge-base "origin/$(gh pr view <url> --json baseRefName -q .baseRefName)" HEAD)
```

Stash as `BASE_SHA` for use in Phase 3's already-fixed checks.

### Pre-fix type-check baseline (for β detection)

Run ONE baseline type-check before Phase 5, capture the set of files already failing:

```bash
bun turbo run check-types 2>&1 | tee /tmp/fix-pr-review-baseline-$$.log
```

Parse the output, build `baseline_errors[path] = <error count or error signatures>`. This is used in Phase 5 to distinguish **pre-existing** type errors from **fix-induced** ones. If type-check tooling is missing (no turbo, no tsc), skip the baseline and mark β as `skipped` for all fixes.

### Compute shared-package repo map (for reusability-aware classification)

Inventory shared packages AND apps so the Phase 3 classifier can cross-check comments about reuse/extraction against what already exists. Scan BOTH `packages/` and `apps/` — cross-app helper duplication (e.g., `apps/backend/src/modules/v1/feature-a/helpers.ts` vs `feature-b/helpers.ts`) is common in NestJS-style monorepos and is invisible to a packages-only scan.

**IMPORTANT**: wrap in `bash -c '...'` — raw `packages/*/src` globs abort under zsh with `zsh: no matches found` BEFORE `2>/dev/null` can catch it. Use `find` for layout robustness (`src/`, `lib/`, `source/`).

```bash
# Repo map files — inventory of TS/TSX in shared roots (capped 500 lines, truncation marked)
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

# Repo map exports — top-level exports across src/lib/source dirs (capped 500 lines, truncation marked)
bash -c '
if [ -d packages ] || [ -d apps ]; then
  find packages apps 2>/dev/null -type d \( -name src -o -name lib -o -name source \) \
    -not -path "*/node_modules/*" -not -path "*/dist/*" -not -path "*/build/*" \
    -not -path "*/.next/*" 2>/dev/null \
    | xargs -I{} grep -rhnE "^export (default (async )?function|function|const|class|type|interface|async function) \w+" {} 2>/dev/null \
    | awk "NR<=500{print} END{if(NR>500)print \"[truncated at 500 of \" NR \" lines — grep packages/ apps/ directly for more]\"}"
fi
'
```

Stash both outputs as `repo_map_files` and `repo_map_exports` for the Phase 3 subagent prompt. If neither `packages/` nor `apps/` exists (non-monorepo), set both to `N/A (not a monorepo)` and flag `IS_MONOREPO=false` — the classifier prompt uses this to reroute greps to `src/` and the repo root.

---

## Phase 2: Fetch review data (main)

### Dual-path input for /review-pr findings

`/review-pr` now posts findings as **individual inline comments** (one per finding, each on a specific code line). These create standard `PullRequestReviewThread`s on GitHub — identical to CodeRabbit threads. The existing GraphQL fetch below handles them with zero special parsing.

For self-review auto-fix (where `/review-pr` detects the user is the PR author and offers "Fix now"), findings are written to a temp file (e.g., `/tmp/review-pr-<number>-findings.md`) in the standard `## Findings` format. This uses the existing local file input path — Phase 7 automatically skips GitHub ops for local files.

### For PR URL (paginated unresolved threads)

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

**Also** fetch the latest CodeRabbit review's body to extract the "Prompt for AI agents" block (contains nitpicks that don't appear as threads):

```bash
gh api "repos/<owner>/<repo>/pulls/<num>/reviews" --paginate
```

Select the latest review where `user.login == coderabbitai[bot]` and `state ∈ {CHANGES_REQUESTED, COMMENTED}`.

### For review URL (`#pullrequestreview-<id>`)

```bash
gh api "repos/<owner>/<repo>/pulls/<num>/reviews/<review_id>"
gh api "repos/<owner>/<repo>/pulls/<num>/reviews/<review_id>/comments"
```

Then run the paginated GraphQL `reviewThreads` query (same as above) and match inline comments to their thread by `databaseId`.

### For discussion URL (`#discussion_r<id>`)

```bash
gh api "repos/<owner>/<repo>/pulls/comments/<comment_id>"
```

(Note: endpoint has NO pull-number — it's `/pulls/comments/<id>`, not `/pulls/<num>/comments/<id>`.)

Then run the paginated GraphQL `reviewThreads` query and match the comment's `databaseId` inside `reviewThreads.nodes[].comments.nodes[].databaseId`. Scope the rest of the flow to just that one thread.

### Parse CodeRabbit body's AI prompt block when present

If any fetched review's body contains `🤖 Prompt for all review comments with AI agents`, extract that section. It's a pre-formatted plain-text block with ALL findings in AI-consumable form — more reliable than HTML-unwrapping collapsibles. The block contains:

- `Inline comments:` section → maps to actionable items (match to inline comments by file:line)
- `Nitpick comments:` section → body-only nitpicks with file + line

### For local files (`./review.md`, `/tmp/review-pr-*-findings.md`, etc.)

Parse the `/review-pr` output format. Extract findings from the `## Findings` section, preserving `Severity / File / Category / Issue / Why it matters / Suggested fix`.

**Severity mapping**: `/review-pr` uses `Critical | Serious | Moderate | Minor` while CodeRabbit uses `Critical | Major | Minor | Refactor | Nitpick`. Both are valid — normalize to the internal `Comment` schema which accepts either convention. Map for triage priority: `Critical` = highest, `Serious`/`Major` = high, `Moderate` = medium, `Minor`/`Refactor` = low, `Nitpick` = default-dismiss.

### Normalize to internal `Comment` list

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

### Short-circuit cases

- **Empty list** (all threads resolved, local file has no findings): print `Nothing to triage — no unresolved comments found.` → restore stash → exit 0.
- **Only nitpicks remain AND `--all-nitpicks` not set**: print `Only nitpicks found (N). Pass --all-nitpicks to triage them, or ignore.` → restore stash → exit 0. No reason to run a full triage subagent on items that will all auto-dismiss.

---

## Phase 3: Triage subagent (`general-purpose`)

### Load review suppressions (main agent, before dispatch)

Before dispatching the subagent, load `.claude/review-suppressions.yml` from the project root (if it exists). In cross-repo mode, fetch via `gh api repos/<owner>/<repo>/contents/.claude/review-suppressions.yml?ref=<head-sha>`. If not found, set `SUPPRESSIONS = ""`.

Pass loaded suppressions into the subagent prompt as a `## Review suppressions` section (same approach as CLAUDE.md content, PR diff, and repo maps — main agent fetches, subagent receives as context).

### Dispatch

Dispatch **one** `general-purpose` subagent with `Read`, `Grep`, and `Bash` tools.

**Important**: The Bash allowlist (`git log/diff/blame/show/merge-base/rev-parse`, `grep`, `rg`) is a **prompt-level instruction** — Claude Code's Agent tool doesn't sandbox Bash per-command. The subagent is trusted not to run other commands, not mechanically prevented from doing so.

### Prompt template

```
You are triaging PR review comments. For each comment, decide one of:
  FIX | DISMISS | DEFER | DISAGREE | NEEDS-INPUT

## Context
PR: <url>
PR title: <title>
Branch: <branch name>
Base branch: <baseRefName>
Base commit (merge-base): <BASE_SHA from Phase 1>
Repo: <owner/repo>
PR goal (from description + linked issue if available): <one sentence>

## PR diff (for grounding)
<output of `git diff <BASE_SHA>...HEAD`, truncated at ~2000 lines with a "[truncated — use git diff yourself for full context]" marker if longer>

## Shared package repo map (for reusability classification)
### Files
<repo_map_files from Phase 1, or "N/A (not a monorepo)">

### Exported symbols
<repo_map_exports from Phase 1, or "N/A">

This map is truncated at 500 lines per section — grep packages/ directly
for anything not listed here.

## Review suppressions (from .claude/review-suppressions.yml)
<If SUPPRESSIONS loaded by main agent, include suppressions content here.
If no suppressions file exists, include: "None">

## Comments to triage
<JSON array of Comment objects from Phase 2>

## Your tools
- Read (any file in the repo — you are on the PR branch)
- Grep (verify claims, find duplicates, locate missing patterns)
- Bash: INSTRUCTED (not enforced) to only run `git log`, `git diff`, `git blame`,
  `git show`, `git merge-base`, `git rev-parse`, `grep`, `rg`.

## Workflow

STEP 0 (MANDATORY, do once): Read the project's CLAUDE.md file(s) from the repo
root and any nested CLAUDE.md in the affected subdirectories. Identify rules
that could override CodeRabbit findings — e.g., "use type not interface",
"use function keyword not arrow", forbidden patterns, testing rules, style
conventions. These override CodeRabbit preferences.

STEP 0.5 — APPLY REVIEW SUPPRESSIONS (do once, after STEP 0):
Review suppressions are loaded by the MAIN AGENT before subagent dispatch
(see below) and passed into this prompt as context. If suppressions were
provided, they appear in the "## Review suppressions" section above.

Expected format:
  suppressions:
    - pattern: "factory pattern"
      category: Architecture
      reason: "YAGNI - single provider by design"
      added: 2026-04-13  # informational, not used for matching
    - pattern: "missing timeout"
      file: "claude-code.ts"
      reason: "Timeout handled at caller level"
      added: 2026-04-13

Before applying the R1-R9 rubric in STEP 4, check each finding against
suppressions. For each suppression entry:
  1. Match `pattern` (case-insensitive substring) against the comment body
  2. If `category` is set, also match against the finding's category
  3. If `file` is set, also match against the finding's file path
If ALL specified conditions match: auto-classify as DISMISS with reason
  "suppressed by .claude/review-suppressions.yml: <reason>"
Skip the R1-R9 rubric for suppressed findings — they go straight to
DISMISS in the triage plan.

STEP 1 — DEDUPE PASS: Group comments that describe the same pattern at
different callsites (same rule + same symbol, OR same rule + same file).
Treat each group as a single meta-finding with a shared fix plan and a
shared reply template. Apply the fix once per callsite but mark every
member thread for resolution in Phase 7.

STEP 2 — MECHANICAL GROUNDING (MANDATORY, for each comment or meta-finding
BEFORE classifying): In one line each, state:
  (a) What code does this comment point at? (file path, symbol, line range,
      restated in your own words after reading the file)
  (b) What change is the comment actually asking for? (restated in your own
      words, one sentence)
Every subsequent finding MUST trace back to this grounding. If you can't
answer (a) or (b) confidently, route to NEEDS-INPUT — do not guess.

STEP 2.5 — REUSABILITY KEYWORD SCAN (for each comment):

Check whether the comment contains any of these reusability keywords /
phrases (case-insensitive substring match):

  Direct:   "already exists", "already have", "already implemented",
            "we have this", "we already have", "we do this elsewhere",
            "isn't there already", "there's a helper", "existing",
            "use X instead", "why not use", "should be in",
            "util for this", "common"
  Refactor: "reuse", "shared package", "helper file", "into helpers",
            "move to", "move into", "move these", "put in shared",
            "extract", "factor out", "pull out", "refactor to use",
            "DRY", "duplicate", "this is the same"

OR the comment is placed on a NEW definition added in this PR. "New
definition" is BROAD and INCLUDES:
  - top-level function / class / type / exported const / React component / hook
  - **class methods** (NestJS-style `private formatX(...)`, `async findOne(...)`,
    `public validate(...)` inside a class body). Class methods are the
    most common real-world case — do NOT restrict to top-level exports.
  - default-exported functions or classes (`export default function`,
    `export default class`)

If reusability-flagged, run these searches using the repo map + your tools
**aggressively** (run ALL of them — we pay for thoroughness with tokens):

  Monorepo mode (`packages/` and/or `apps/` exists):
    - Grep("<new-symbol-name>", "packages/") — exact name match
    - Grep("<new-symbol-name>", "apps/") — cross-app duplication check
    - Grep("<semantic-root>", "packages/") — drop domain prefixes
      (User/Order/Meal/Portion/etc.), keep verb/noun
    - Grep + Glob "packages/ui/src/components/" for new UI components
      (use kebab-case filename pattern: `<kebab-name>*.tsx`)
    - Read any candidate match to CONFIRM it's a real semantic match
      (not just a substring collision — a hit on `formatter.ts` when
      searching for `format` does not automatically mean duplication)

  Non-monorepo mode (`repo_map_files == "N/A (not a monorepo)"`):
    - Grep("<new-symbol-name>", "src/") — primary source root
    - Grep("<new-symbol-name>", ".") — repo root fallback
    - Read candidate matches to confirm

Store the findings as `reusability_context:` on the comment. Use
`reusability_context: { flagged: true, matches: [...], verified: <yes|no> }`
so the field is guaranteed to round-trip to Phase 4/7 even when no
matches are found. If no keywords OR new definitions, set
`reusability_context: { flagged: false }`.

Concrete targets (existing file:path to reuse, or destination package
for extraction) strengthen the FIX decision in STEP 4.

STEP 3 (for each comment or meta-finding):
  a) Read the file:line. If the exact line doesn't contain what the comment
     describes, DEAD-LINK CHECK: grep for the symbol or pattern mentioned in
     the comment body. If found at a different location → re-anchor to the
     new location and continue classification. If not found anywhere →
     DISMISS with "code removed/refactored in <commit>" (scan
     `git log <BASE_SHA>..HEAD --name-only` to find the commit that touched
     the file).
  b) Verify the current code matches CodeRabbit's claim.
  c) ALREADY-FIXED CHECK (scoped, two layers):
     • Same-file: `git log -p <BASE_SHA>..HEAD -- <file>` (diverge-from-base
       commits only, NOT full file history).
     • Cross-file: `git log <BASE_SHA>..HEAD --name-only` to list every file
       touched on this branch. If a caller or related file may have rendered
       the comment moot (e.g., caller was hardened to guarantee non-null),
       read that file's diff to confirm.
     If already addressed → DISMISS with R4 (you MUST populate
     `prior_commit_sha` in the output).
  d) CLAUDE.md CHECK: does this contradict a project rule? If yes → DISMISS
     with R5 (you MUST populate `claude_md_quote` with the verbatim rule text).
  e) NITPICK SANITY SCAN (only if source_type=nitpick): apply the 3-PRONG
     TEST — answer three yes/no questions:
        (1) Could this cause a runtime failure, wrong output, or security hole?
        (2) Does it block a real user task?
        (3) Would a senior reviewer insist on it in a paid review?
     If ALL three are No → stock DISMISS (source_type=nitpick, auto-dismiss).
     If ANY one is Yes → PROMOTE to full triage (continue with Step 4) and
     mark `promoted_from_nitpick: true`.

STEP 4 — CLASSIFY using the rubric (apply in order, first match wins):

  R1. Self-contradictory or technically wrong → DISMISS
  R2. Hallucinated file:line (after dead-link re-anchor attempt failed) → DISMISS
  R4. Already fixed in current branch state (same-file or cross-file) →
      DISMISS — REQUIRES `prior_commit_sha`
  R5. Contradicts CLAUDE.md → DISMISS — REQUIRES `claude_md_quote`
  R3. Pure style/naming with no correctness implication → DISMISS (only
      reaches this rule if R1/R2/R4/R5 didn't fire; nitpicks reach this
      rule only after promotion in Step 3e)
  Note: If STEP 2.5 flagged reusability_context.flagged == true
  AND a concrete existing target was found, SKIP R3 (pure style)
  when considering the comment — a reuse-directed comment that could
  look "stylistic" (e.g., "rename to match helper X") is actually a
  R6 reusability FIX, not style.

  R6. Real bug / security / perf / correctness / REUSABILITY issue → FIX

      Reusability is correctness-adjacent — duplicated or reimplemented
      code is a correctness risk (divergent fixes, missed updates, skill
      drift). Default to FIX when ANY of these hold:

        (a) A concrete existing target is known (STEP 2.5 found a match
            in `repo_map_exports` or via direct grep). The FIX is just
            "delete new code + import existing" — this NEVER goes to
            DEFER, even if the existing target lives in an "untouched"
            file, because replacing 10 lines with a 1-line import only
            touches files the PR already has open.

        (b) The extraction is feasible in-scope (< 50 LOC of refactor
            within files already touched by this PR).

        (c) Small-but-duplicated: even a <5-line private helper that
            duplicates a shared helper is a FIX — never dismiss as
            "too small to matter".

  R7. Real issue but out of scope for THIS PR's stated goal → DEFER

      SPECIAL RULE — REUSABILITY CONCERNS:
      For comments about reuse / DRY / extraction / sharing / helpers,
      DO NOT route to R7 (DEFER) unless BOTH hold:
        (a) the refactoring genuinely requires changes to files NOT
            touched by this PR AND scope exceeds ~50 LOC of changes
            (strictly — small cross-file refactors stay in R6)
        (b) there is a concrete "tracked separately" reference
            (ticket, backlog, follow-up PR)

      **Gap handler**: If (a) is TRUE but (b) is MISSING (no tracking
      reference), do NOT fall through to R6 — this is an honest
      out-of-scope refactor that needs a ticket. Route to R9
      (NEEDS-INPUT) with:
        why_unclear: "out-of-scope reuse refactor (<LOC estimate>
                      LOC across untouched files) — needs a tracking
                      ticket reference before this can be either FIXed
                      or DEFERred"
      This surfaces to the user at the end of the run for manual
      decision.

      **Delete-new-import-existing carve-out**: if the fix action is
      "delete the new duplicate + add an `import` to the existing
      target", that ALWAYS goes to R6 (FIX) regardless of where the
      existing target lives. Deleting and importing only touches files
      already in the PR's diff — it is always in-scope.

      "I didn't feel like doing it", "this is a small cleanup", or
      "can be done later" are NOT valid DEFER reasons for reusability.
      Default to R6 (FIX) when feasible in-scope.
  R8. Valid concern but the reviewer's recommendation is wrong for this
      codebase (legitimate technical disagreement, not style preference) →
      DISAGREE — REQUIRES `disagree_rationale` with concrete counter-argument
  R9. Ambiguous / needs user domain knowledge / needs code execution to
      verify → NEEDS-INPUT

Rubric ordering rationale: R1/R2 are objective fact-checks (first). R4/R5 are
HIGH-SIGNAL dismissals — evaluated before R3 so a style nit on already-
refactored code dismisses with the stronger "already fixed in abc123" reason
instead of the weaker "pure style" reason. R3 comes after. R6-R9 are action
buckets.

STEP 5 — For each FIX, write a concrete fix plan:
  - Which file(s) to edit
  - What change to make (1–3 sentences, >= 30 chars)
  - Any dependencies on other fixes ("depends on F1" if F1 renames a symbol
    this fix calls)

STEP 6 — Write replies:
  - For DISMISS / DEFER / DISAGREE: write SPECIFIC reply text following the
    format rules below.
  - For FIX: write `reply_placeholder` — this is a placeholder only and will
    be REGENERATED in Phase 7 from the actual post-fix diff. Do not rely on
    it being the final reply.

## NEEDS-INPUT calibration

Use NEEDS-INPUT when you cannot verify WITHOUT running code or without user
domain knowledge. Concrete examples:
  - "This query is slow" → needs a benchmark run → NEEDS-INPUT
  - "This breaks test suite X" → needs test execution → NEEDS-INPUT
  - "Should we use strategy A or B here?" → needs user domain knowledge → NEEDS-INPUT

Anti-examples (these are NOT NEEDS-INPUT):
  - "Rename variable for clarity" → R3 style (or R6 if genuinely confusing)
  - "Missing null check" → you CAN verify by reading the file → R6 or R1
  - "Consider extracting helper" → R3 or R6 based on readability impact

Err toward FIX for mechanical low-risk changes you can verify. Err toward
NEEDS-INPUT when the comment hinges on domain knowledge or runtime behavior.

### Presenting NEEDS-INPUT options to the user

If you elaborate on a NEEDS-INPUT item with branching options (e.g.,
"Option A / Option B / Option C"), every unselected branch MUST be phrased
as a conditional. The user cannot tell "what I already did" from "what I'm
proposing" unless the sentence structure makes it unmistakable.

- PROHIBITED (reads as already-done work):

    Option A — Aggregate as independent intent, no cascade
    - Delete the cascade batch from the meal-level edit path
    - Meal-level edits only write to gs_MealMenuPortions

- REQUIRED (reads as hypothetical future):

    Option A — Aggregate as independent intent, no cascade
    IF CHOSEN, we would:
    - Delete the cascade batch from the meal-level edit path
    - Make meal-level edits write only to gs_MealMenuPortions

Rules:
  - Every option block must open with `IF CHOSEN, we would:` before its
    action list, OR every bullet inside must start with `would <verb>` /
    `would not <verb>`.
  - Current state must be labeled separately under `What's in the code now:`
    so the user has an unambiguous baseline.
  - Never mix imperative and conditional mood inside one option block.

This rule exists because the skill was previously observed to describe
hypothetical futures in present-tense imperative, leading a user to think
the option had already been applied. Do not repeat.

## change_class calibration

Every FIX item must commit to one of:

- `hardening`: A user running their normal workflow would NOT notice
  anything different. The change affects edge cases only — adversarial
  inputs, concurrent races, malformed payloads, currently-unreachable
  branches, type-safety, defensive depth. Happy path is unchanged.
  Examples:
    - adding cross-FK validation that only fires on malformed requests
    - replacing `findExisting + branch` with atomic `onConflictDoUpdate`
      (single-user behavior identical; only matters under concurrency)
    - adding `.strict()` to a Zod schema (normal UI never sends extras)
    - narrowing a type from `string` to a union (compile-time only)
    - `Promise.all` → `Promise.allSettled` + `console.error` (happy path
      identical; only changes failure observability)

- `logic-change`: A user MIGHT observe a difference in a realistic
  scenario. Any fix that changes what the UI renders, what the API
  returns on a non-error path, what data reaches the database, or how
  errors surface to the user.
  Examples:
    - hoisting a fetch above an early-return (data now appears in an
      empty state where it was previously hidden)
    - making stored values round-trip on reload (previously dropped)
    - fixing an empty error toast to show a real message
    - adding a visual drift indicator (new UI signal)

Burden of proof is on the `hardening` claim. When in doubt, label it
`logic-change` and write a specific test scenario. A fix that is BOTH
hardening and logic-change is `logic-change`.

### test_scenario format

- For `hardening`: write exactly `smoke test — happy path unchanged`.
  (No repro steps; the intent is "confirm nothing regressed".)
- For `logic-change`: write a 1-sentence concrete repro that can be
  executed in the UI, API, or DB. Must include:
    - the trigger (what the user does)
    - the observation (what they should see differently from before)
  Example: "Set a meal-level portion, navigate to a week with no
  components scheduled; stored value should still render in the cell
  (was blank before)."

This split is rendered verbatim in the Phase 8 final report so the user
can triage testing effort — smoke-test the hardening bucket, deliberately
exercise the logic-change bucket.

## Anti-slop reply format

- FIX (placeholder only): "Fixed — <what will be changed, specific>"
- DISMISS R4: "Already fixed in <short_sha>: <what that commit did>"
- DISMISS R5: "Contradicts CLAUDE.md rule: '<verbatim quote>'. Keeping project convention."
- DISMISS R1/R2/R3: "Not changing — <specific 1-sentence rationale with concrete evidence>"
- DEFER: "Valid but out of scope for this PR (<PR focus>); <optional tracking ref>"
- DISAGREE: "Disagree — <concrete counter-argument naming the trade-off>. Keeping current approach."
- FORBIDDEN: "thanks", "noted", "good point", "fair", "will do", "addressed",
  "done", "ok", "sure", "got it". These are mechanically rejected in Phase 7.
- Every non-placeholder reply must cite specific evidence: file:line, CLAUDE.md
  rule quote, prior commit SHA, or a concrete verb (changed/added/removed/
  renamed/refactored/scoped).

## Output format (required — Phase 4 validates)

Return the plan in this EXACT format. Missing required fields cause rejection.

```
# Triage plan

## FIX (<count>)
[F1] <file:line> — <comment ask, truncated ~80 chars>
     thread_id: <id>               # NULL for promoted nitpicks
     promoted_from_nitpick: <bool>
     grounding_a: <what code this points at>
     grounding_b: <what change is asked>
     fix_plan: <1-3 sentences, >= 30 chars>
     change_class: hardening | logic-change     # see calibration above
     test_scenario: <for hardening: "smoke test — happy path unchanged";
                     for logic-change: 1-sentence concrete user-visible repro>
     reply_placeholder: "Fixed — <specific>"
     dependencies: []
     member_threads: []            # for dedup'd groups

## DISMISS (<count>)
[D1] <file:line> — <comment ask>
     thread_id: <id>               # or "nitpick — no thread"
     rubric: R1|R2|R3|R4|R5
     prior_commit_sha: <short sha> # REQUIRED if rubric == R4
     claude_md_quote: "<rule>"     # REQUIRED if rubric == R5
     grounding_a: <what code>
     grounding_b: <what ask>
     reason: <concrete 1 sentence>
     reply: "<specific reply per rubric format>"

## DEFER (<count>)
[E1] <file:line> — <comment ask>
     thread_id: <id>
     grounding_a: <what code>
     grounding_b: <what ask>
     reason: <why out of scope>
     reply: "Valid but out of scope — <specific>"

## DISAGREE (<count>)
[G1] <file:line> — <comment ask>
     thread_id: <id>
     grounding_a: <what code>
     grounding_b: <what ask>
     disagree_rationale: <concrete counter-argument>
     reply: "Disagree — <specific>. Keeping current approach."

## NEEDS-INPUT (<count>)
[N1] <file:line> — <comment ask>
     html_url: <direct URL>
     grounding_a: <what code>
     grounding_b: <what ask>
     why_unclear: <1 sentence>

## Nitpicks auto-dismissed (<count>)
[n1] <file:line> — <comment ask>
     reply_local_only: "<stock dismissal with specific rationale>"
     sanity_scan: passed             # or "escalated — see [F<n>]"
```
```

---

## Phase 4: Plan approval gate (main)

*Validates against R-rubric (see Phase 3 STEP 4). Required fields per classification are defined there.*

### Plan validation (before display)

Before anything is shown to the user, mechanically validate the classifier's output:

- Every DISMISS with `rubric: R5` MUST have non-empty `claude_md_quote`.
- Every DISMISS with `rubric: R4` MUST have non-empty `prior_commit_sha`.
- Every DISAGREE MUST have non-empty `disagree_rationale` (and it MUST NOT be a pure style preference — check for keywords like "prefer", "cleaner", "nicer" without a concrete counter-argument).
- Every FIX MUST have `fix_plan` length >= 30 characters.
- Every FIX MUST have `change_class` set to exactly `hardening` or `logic-change` (see `## change_class calibration` above).
- Every FIX MUST have non-empty `test_scenario`. For `change_class: hardening`, the value MUST be exactly `smoke test — happy path unchanged`. For `change_class: logic-change`, the value MUST be a 1-sentence concrete repro (not just "verify it works").
- Every item MUST have non-empty `grounding_a` and `grounding_b`.

On validation failure: re-dispatch the classifier with the specific missing fields listed. Max 1 retry. Second failure → abort with the validation errors printed.

### Plan display

Print the plan with a header:

```
# Fix Plan — PR #<num>: <title>
# <N> findings triaged: <F> fix, <D> dismiss, <E> defer, <G> disagree, <I> needs-input, <n> nitpicks
```

### Highlight DISMISS-by-CLAUDE.md prominently

If any DISMISS has `rubric: R5`, print a **separate highlighted section BEFORE** the main plan:

```
## ⚠ Dismissed because they contradict CLAUDE.md — review and override if any are exceptions

[D<n>] <file:line>: <comment ask>
       CLAUDE.md rule: "<verbatim quote>"
       Reply will be: "<reply>"
       If this rule has a legitimate exception in this case, choose "Edit plan first"
       in the approval prompt to change D<n> to FIX or NEEDS-INPUT.
```

This is the safety net for the case where a project convention has a legitimate exception.

### Interactive TTY detection

```bash
[ -t 0 ] && EDIT_AVAILABLE=true
```

### Approval prompt

If `--dry-run`: print the plan, print `dry run — not executing`, restore stash, exit 0.

Otherwise, use AskUserQuestion with conditional options based on `EDIT_AVAILABLE`:

   Question:
     header: "Approve"
     text: "Approve the fix plan above? <F> fixes, <D> dismissals, <E> deferrals, <G> disagrees, <I> needs-input."
     options:
       - label: "Execute plan"
         description: "Apply all FIX items in dependency order"
       - label: "Cancel"
         description: "No changes made — restore stash and exit"
       - label: "Edit plan first"
         description: "Open the plan in $EDITOR for manual tweaks before executing"
         [only include this option if EDIT_AVAILABLE=true]

On "Execute plan": proceed to Phase 5. If `--interactive` flag was set, switch to per-item confirmation mode in Phase 5.
On "Cancel": restore stash (if any), print "cancelled", exit 0.
On "Edit plan first": write plan to `/tmp/fix-pr-review-<num>.md`, open in `${EDITOR:-vi}`, read back after close. Re-run the plan validation step, then use AskUserQuestion again:

   Question:
     header: "Confirm"
     text: "Plan modified — <N> changes detected. Execute the edited plan?"
     options:
       - label: "Execute"
         description: "Apply the edited plan"
       - label: "Cancel"
         description: "Discard edits and exit"

   On "Execute": proceed to Phase 5. On "Cancel": restore stash, exit 0.

When `EDIT_AVAILABLE=false`, present only "Execute plan" and "Cancel" (2 options). When `EDIT_AVAILABLE=true`, present all 3. The user can always type a freeform response via the automatic "Other" option.

---

## Phase 5: Execute fixes (main, sequential)

*Executes R6 FIX items from the approved plan (see Phase 3 STEP 4 for R6 criteria, Phase 4 for approval gate).*

### Dependency resolution

Build an execution order from `dependencies:` fields with a simple topological sort. On a **cycle** (A→B→A): abort with `Cyclic fix dependencies detected — edit the plan (rerun with 'e') to resolve.` Restore stash. Exit non-zero.

### Pre-edit snapshots (revert mechanism — Edit tool has no undo)

Before the first `Edit` touches any file in Phase 5, `Read` its full contents and cache them:

```
preedit_snapshot[path] = <full file content from Read>
```

Revert a single file = `Write(path, preedit_snapshot[path])`. Revert-all = iterate over every snapshotted path and Write back.

### Per-fix loop

For each FIX item in topological order:

1. Print `[<idx>/<total>] Fixing: <file:line>`.

   If `--interactive` flag is set, use AskUserQuestion before applying each fix:

   Question:
     header: "Fix <idx>"
     text: "[<idx>/<total>] <file:line> — <fix_plan summary, first 80 chars>"
     options:
       - label: "Apply fix"
         description: "Execute this fix and continue to the next"
       - label: "Skip"
         description: "Skip this fix — mark as NEEDS-INPUT in the final report"
       - label: "Skip remaining"
         description: "Stop here — skip all remaining fixes"

   On "Apply fix": continue with steps 2-7. On "Skip": mark `fix_status[idx] = skipped`, skip to next item. On "Skip remaining": mark all remaining items as `skipped`, jump to Phase 6. On "Other": treat as freeform instruction (e.g., "modify the fix plan for this item").

2. For every file listed in `fix_plan`: if not already in `preedit_snapshot`, `Read` and cache.
3. Apply the change(s) via `Edit` tool.
4. **Per-file narrow type-check (β)**:
   - Detect project type: if `turbo.json` exists → turborepo mode; else if `tsconfig.json` exists → plain TS mode; else → skip β.
   - Turborepo: `bun turbo run check-types --filter=<package>` (or `pnpm turbo run check-types --filter=<package>` if the repo uses pnpm). Target the workspace package containing the edited file. **Do NOT use `bun check-types --filter=<package>`** — `bun` doesn't forward unknown flags to the underlying script.
   - Plain TS: `bunx tsc --noEmit` or `npx tsc --noEmit`.
   - No TS tooling: skip β with a one-line note.
5. **Compare against Phase 1 baseline**: β is considered **failed ONLY if the error set on the edited file is a strict superset** of the baseline set for that file. Classifications:
   - **pass** — no errors on this file, or same error count as baseline.
   - **inconclusive — preexisting errors** — baseline already had errors on this file; we can't cleanly tell whether the fix added more. Continue.
   - **failed** — strict superset of baseline errors on this file (genuinely new errors).
6. On **pass** or **inconclusive**: mark `[<idx>] ✓ fixed` / `[<idx>] ~ inconclusive`, continue.
7. On **failed**:

   Print the error output (trimmed to ~30 lines), then use AskUserQuestion:

   Question:
     header: "Beta fail"
     text: "[<idx>] Fix applied but type-check has NEW errors vs baseline. <error count> new error(s) in <file>."
     options:
       - label: "Retry fix"
         description: "Revert and re-dispatch to a fresh subagent with error context (max 2 retries)"
       - label: "Skip this fix"
         description: "Revert this fix, mark as NEEDS-INPUT, continue with remaining fixes"
       - label: "Abort all"
         description: "Revert ALL Phase 5 edits, restore stash, and exit"

   On "Retry fix": `Write` the pre-edit snapshot back (revert), re-dispatch the fix plan to a fresh `general-purpose` subagent with the new-errors context, loop (max 2 retries; on 3rd failure, auto-treat as "Skip this fix").
   On "Skip this fix": revert via snapshot `Write`, mark `fix_status[idx] = skipped`, mark `[<idx>] NEEDS-INPUT`, skip reply + resolve for this item in Phase 7.
   On "Abort all": revert ALL Phase 5 edits via pre-edit snapshots, restore stash, exit non-zero.

### Fix execution tracking

```
fix_status[idx] = ok | retried_ok | inconclusive | skipped | aborted | type_check_skipped
```

This feeds the final report in Phase 8.

---

## Phase 6: /done pipeline (main)

After all fixes are applied, run the standard `/done` sequence on the pending fix diff (`git diff HEAD`):

1. `/fix-ts-errors` — loop until clean (catches cross-file errors per-file β missed).
2. `/parallel-review` — review only the fix diff, not the entire PR.
3. `/simplify` — apply cleanup improvements.

### Self-heal loop (explicit iteration tracking)

```
self_heal_iter = 0
done_remaining = []
while self_heal_iter < 2:
    findings = run_parallel_review(diff="git diff HEAD")
    blockers = [f for f in findings if f.severity in ("Critical", "Serious")]
    if not blockers:
        break
    # Dispatch fresh subagent per blocker with the finding + the diff
    for f in blockers:
        apply_subagent_corrective_edits(f)
    run_fix_ts_errors()
    self_heal_iter += 1

# After loop: record whatever blockers remain (if any)
done_remaining = blockers
```

If `done_remaining` is non-empty after 2 iterations, record it for the final report and continue to Phase 7. Do not block progression — the user will see the remaining issues in Phase 8 and decide.

**Moderate/Minor findings** are recorded in `done_remaining` without self-heal — user decides at commit time.

---

## Phase 7: Reply + resolve on GitHub (main)

*Reply format rules are defined here and referenced by Phase 4 validation. This skill does NOT read or write `/review-pr`'s cache (`~/.claude/skills/review-pr/cache/`). Thread resolution happens on GitHub — `/review-pr`'s re-review picks up resolved threads via its GraphQL prior-review timeline fetch.*

**Skip this entire phase if the input was `./review.md`** or any local file — there are no GitHub threads to operate on. Phase 8 still produces the local final report.

### Step 7a — Regenerate FIX replies from actual diff

The classifier wrote `reply_placeholder` during Phase 3 BEFORE fixes existed. Between Phase 3 and now, fixes were applied (Phase 5) and possibly modified by self-heal (Phase 6). The placeholder may no longer match reality.

For each FIX item with `fix_status ∈ {ok, retried_ok, inconclusive}`:

1. Compute the diff for its target file(s): `git diff HEAD -- <file1> <file2>` (nothing is committed yet, so HEAD = pre-Phase-5 state; the diff IS the applied fix).
2. Extract the relevant hunk(s) for the referenced file:line.
3. Synthesize `reply_final[idx]` from the actual diff, in the form:

   ```
   Fixed — <1-sentence description of what the diff actually changed, 
   citing the new post-image line number and a concrete verb>
   ```

4. Store as `reply_final[idx]`.

Skipped/aborted FIX items get no reply (they land in NEEDS-INPUT for the final report instead).

### Step 7b — Reply validator (pre-post mechanical check)

Before posting any reply, validate it against forbidden-phrase / must-contain rules:

```
forbidden_prefixes = [
    "Thanks", "Noted", "Good point", "Fair", "Will do",
    "Addressed", "Done", "Ok", "OK", "Sure", "Got it"
]
min_length = 40 characters
must_contain_any_of = [
    a file path  (e.g., /\w+\.\w{1,4}/)
    a line reference (e.g., /:\d+/ or /\bline \d+/)
    a quoted string (e.g., /"[^"]+"/ or /'[^']+'/ — for CLAUDE.md quotes)
    a short commit SHA (/\b[a-f0-9]{7,}\b/)
    a concrete verb ("changed", "added", "removed", "renamed", "refactored",
                     "fixed", "scoped", "extracted", "inlined")
]
```

A reply passes if: starts with none of the forbidden prefixes, length ≥ 40, AND matches at least ONE of the `must_contain_any_of` patterns.

**Reusability-specific rule** (mechanically enforced via `reusability_context`):

The validator reads the `reusability_context:` field stored on each comment during Phase 3 STEP 2.5. If `reusability_context.flagged == true`, the reusability-specific rule activates and is AND-combined with the generic rule above.

```
if comment.reusability_context?.flagged:
    reusability_rule_passes =
        (classification == "FIX" AND reply contains a destination file path
            that points at an existing module — one of:
              - a `@fileseye/...` or `@<scope>/...` package reference
              - a `packages/.../<file>.ts` path
              - an `apps/.../<file>.ts` path
              - a relative import path pattern `from './...'` or `from '../...'`)
        OR
        (classification == "DEFER" AND reply contains a concrete
            out-of-scope reason: ticket ref, file path outside the PR diff,
            OR the phrase "tracked in <ref>")
        OR
        (classification == "DISMISS" AND reply cites a specific reason:
            CLAUDE.md quote, prior commit sha, or factual refutation)

    if NOT reusability_rule_passes:
        reject reply; dispatch rewriter subagent with failing rule cited
```

Concretely this catches:
- `"Fixed — now importing from @fileseye/utils/format.ts:45 instead of reimplementing"` → PASSES (FIX with destination)
- `"Fixed — refactored to a helper"` → FAILS (no destination)
- `"Moved to helpers"` → FAILS (no concrete target)
- `"Valid but requires packages/shared refactor; tracking in #4321"` → PASSES (DEFER with scope reason)
- `"Will do later"` → FAILS (no reason, no target)

**Missing `reusability_context` field**: if the classifier omitted the field entirely (Phase 3 non-compliance), default to `reusability_context = { flagged: false }` and fall through to the generic validator. But log a `reusability_context missing — Phase 3 schema gap` warning in the final report so the user knows the reusability check didn't gate this reply.

**Phase 4 plan validation note**: the Phase 4 plan validator should ALSO check that every comment in the plan has a `reusability_context` field (even if `{flagged: false}`). Missing-field → one retry, then hard failure. This guarantees the field round-trips from Phase 3 to Phase 7 and the validator's branching logic is always reachable.

On failure: dispatch a 1-off `general-purpose` subagent with the original comment + failing reply + which rule failed, ask for a compliant rewrite. Max 1 rewrite. If the rewrite still fails, log as `reply_invalid` and SKIP posting for this item (thread stays unresolved; surfaced in the top of the final report).

### Step 7c — Post loop

For each item with a non-null `thread_id` (actionables only — NOT nitpicks, NOT NEEDS-INPUT, NOT skipped in Phase 5, NOT `reply_invalid`):

```bash
# 1. Post reply — use -f (raw string) for IDs, not -F (type-coercing)
gh api graphql \
  -f threadId="<thread_id>" \
  -f body="<reply text>" \
  -f query='mutation($threadId: ID!, $body: String!) {
    addPullRequestReviewThreadReply(input: {
      pullRequestReviewThreadId: $threadId,
      body: $body
    }) {
      comment { id url }
    }
  }'

# 2. Resolve (only if reply succeeded)
gh api graphql \
  -f threadId="<thread_id>" \
  -f query='mutation($threadId: ID!) {
    resolveReviewThread(input: { threadId: $threadId }) {
      thread { id isResolved }
    }
  }'
```

### Step 7d — Promoted nitpicks handling

Promoted nitpicks (sanity-flagged in Phase 3e) have `thread_id = null` because they live only in the review body. Phase 5 applies the fix for them; Phase 7 has **nothing to post**. They are tracked separately for the final report so the user sees: "fix applied, no thread to resolve — mention in commit message; CodeRabbit's next review will regenerate the body and the old nitpick disappears."

### Per-item status tracking

```
gh_status[idx] = {
  reply_ok:    true | false | skipped,
  reply_err:   <error message if any>,
  resolve_ok:  true | false | skipped,
  resolve_err: <error message if any>
}
```

**Do NOT abort the batch on individual failures.** Continue to the next item. Failures are surfaced at the TOP of the final report.

---

## Phase 8: Finalize (main)

*Report groups by R-classification (see Phase 3 STEP 4). Includes suppressions write (learning loop).*

### 1. Restore WIP

If `STASH_PUSHED=true`:

```bash
git stash pop
```

On stash pop conflict: do NOT auto-resolve. The working tree will now contain:
- Phase 5 fixes (applied, uncommitted)
- Conflict markers from the popped stash
- Untracked files from the stash

Record `stash_restored: conflict` in the final report and print explicit guidance to the user.

### 2. Print the final report

#### Failure section (TOP — only if any Phase 7 op failed)

If any `gh_status[idx]` has `reply_ok == false` OR `resolve_ok == false`, print this section at the **top** of the report:

```
## ⚠ GitHub operations that FAILED (<count>)

  [<idx>] <file:line>
    reply:   <err>
    resolve: <err>
    thread:  <html_url>

These threads are still open on GitHub. Retry manually, or re-run the skill
scoped to the specific comment:
  /fix-pr-review <html_url>
```

#### Main body

```
# Fix PR Review — PR #<num>: <title>

## Fixes applied (<count>)

### Hardening-only fixes (<H count>) — no user-visible change expected, smoke-test the happy path
  [1] ✓ src/modules/.../meal-menu-portions.service.ts:26 — atomic onConflictDoUpdate replaces findExisting+branch
      β type-check: pass
      Test: smoke test — happy path unchanged
  [2] ✓ src/modules/.../meal-menu-portions-validation-helper.ts:9 — cross-FK ownership validation added
      β type-check: pass
      Test: smoke test — happy path unchanged

### Logic-changing fixes (<L count>) — user-visible behavior differs, exercise each scenario below
  [3] ✓ src/modules/.../client-portions.service.ts:100 — hoist mealMenuPortions fetch above early exits
      β type-check: pass
      Test: Set a meal-level portion, navigate to a week where no components are scheduled;
            stored value should still render in the cell (was blank before).
  [4] ✓ src/.../planned-aggregation.ts:94 — round-trip stored ordered/produced/sold fields
      β type-check: pass
      Test: Edit a meal-row ordered value, reload the page; the value should persist
            in the cell (was resetting to child-sum before).

### Skipped (<S count>)
  [5] ⚠ src/utils/parser.ts:88 — β failed twice, needs manual attention

# Rendering rules for this section:
#   - Every [F<n>] item in the classifier plan MUST appear in exactly one of
#     the three subsections above. Partition by (change_class, β-status):
#       change_class=hardening   AND β pass → Hardening-only
#       change_class=logic-change AND β pass → Logic-changing
#       β failed twice (either class)        → Skipped
#   - For each fix, render the `Test:` line using the `test_scenario` field
#     from the classifier plan verbatim. Do NOT paraphrase — the user needs
#     the exact repro they approved.
#   - If a subsection's count is 0, omit the subsection entirely (do not
#     print an empty header).

## Dismissed (<count>)
  [D1] src/db/schema/index.ts:41 (nitpick) — export ordering matches alphabetical pattern
       Original (first 80 chars): "Consider maintaining consistent schema export ordering..."
  [D2] src/auth/util.ts:12 — contradicts CLAUDE.md: "use type not interface"
       Original: "Consider using interface for User type..."

## Deferred (<count>)
  [E1] src/legacy/parser.ts:210 — streaming refactor out of scope for this PR

## Disagree (<count>)
  [G1] src/api/routes.ts:55 — inlining is clearer here than extraction

## /done results
  /fix-ts-errors:   clean
  /parallel-review: 1 Moderate finding — consider extracting helper (see output above)
  /simplify:        no changes suggested
  Remaining after self-heal: <list or "none">

## GitHub reply/resolve (<count>)
  [1]  posted ✓  resolved ✓  — src/db/schema/meal-menu-portions.ts:53
  [2]  posted ✓  resolved ✓  — src/modules/.../meal-menu-portions.service.ts:143
  [D1] (nitpick — no GitHub op)
  [D2] posted ✓  resolved ✓  — src/auth/util.ts:12
  [E1] posted ✓  resolved ✓  — src/legacy/parser.ts:210

## Promoted nitpicks — no GitHub thread (<count>)
  [F4] src/foo.ts:22 — promoted from nitpick (sanity scan caught a real issue)
       Fix applied. No inline thread to resolve. Mention in commit message;
       CodeRabbit's next review will regenerate the body.

## NEEDS INPUT — handle manually (<count>)
  [N1] https://github.com/owner/repo/pull/123#discussion_r<id>
       CodeRabbit: <short description>
       Why unclear: <reason from classifier>
       Re-triage: /fix-pr-review https://github.com/owner/repo/pull/123#discussion_r<id>

## Suggested commit message

Detailed:
  git commit -m "fix: address CodeRabbit review on PR #<num>

  - <fix 1 description>
  - <fix 2 description>
  - <fix N description>"

One-liner:
  git commit -m "fix: address CodeRabbit review on PR #<num>"

## Stashed work

Stashed: <yes | no>
Restored: <yes | no | conflict>

<If conflict:>
  Your working tree now contains:
    • Phase 5 fixes (applied, not committed)
    • Conflict markers from your stashed WIP
    • Any untracked files from the stash
  Resolve conflicts, then `git add` your intended set before committing.
  Your original stash is still available as `git stash list` entry
  `fix-pr-review auto-stash <timestamp>`.
```

### 3. Interactive NEEDS-INPUT triage

If any NEEDS-INPUT items exist in the final report, use AskUserQuestion:

   Question:
     header: "NEEDS-INPUT"
     text: "<N> item(s) need your input. Would you like to triage them now?"
     options:
       - label: "Triage now"
         description: "Walk through each NEEDS-INPUT item and decide: fix, defer, or dismiss"
       - label: "Skip for now"
         description: "Leave them unresolved — handle manually later"

On "Triage now": for each NEEDS-INPUT item, use AskUserQuestion:

   Question:
     header: "Item N<idx>"
     text: "<file:line> — <why_unclear>"
     options:
       - label: "Fix it"
         description: "Provide guidance and have the agent apply a fix"
       - label: "Defer"
         description: "Mark as out-of-scope, post a DEFER reply on GitHub"
       - label: "Dismiss"
         description: "Not a real issue — post a DISMISS reply on GitHub"

On "Fix it": use a follow-up AskUserQuestion to collect guidance:

   Question:
     header: "Guidance"
     text: "What should the fix do for <file:line>? Describe the intended behavior or approach."
     options:
       - label: "Use reviewer's suggestion"
         description: "Apply the original review comment's recommended change as-is"
       - label: "I'll describe"
         description: "Let me type specific guidance for this fix"

   On "Use reviewer's suggestion": apply the fix using the original comment's recommendation (same as Phase 5 per-fix loop) and post a FIX reply. On "I'll describe" or "Other": use the user's freeform text as the fix plan, apply inline, and post a FIX reply.

On "Defer": post a DEFER reply and resolve (skip GitHub ops for local file inputs — record classification in report only). On "Dismiss": post a DISMISS reply and resolve (same local file guard).

On "Skip for now": continue to next actions.

Skip this step entirely if the NEEDS-INPUT count is 0.

### 3.5. Offer to write suppressions (learning loop)

After the final report and NEEDS-INPUT triage, collect all DISMISS and DISAGREE items from the triage plan. If any exist, offer to persist them as suppressions for future reviews.

Use AskUserQuestion:

   Question:
     header: "Learn"
     text: "Save these dismissed/disagreed patterns to .claude/review-suppressions.yml so they're auto-dismissed in future reviews?"
     options: [one option per DISMISS/DISAGREE item, showing the pattern + reason]
     multiSelect: true

For each selected item, append to `.claude/review-suppressions.yml`:
```yaml
  - pattern: "<normalized pattern from finding — key phrase, not full text>"
    category: "<finding category if available>"
    file: "<finding's file path — include only if the rationale is specific to one file, omit for generic patterns>"
    reason: "<dismiss/disagree rationale from triage>"
    added: <today's date YYYY-MM-DD>
```

If the file doesn't exist, create it with:
```yaml
suppressions:
  - pattern: ...
```

If no items are selected, or the user chooses "Other" to skip, do not write anything.

Skip this step entirely if:
- There are no DISMISS or DISAGREE items
- The input was a local file from outside a git repo (no project root to write suppressions into)

### 4. Post-completion next actions

After printing the final report (and optional NEEDS-INPUT triage), use AskUserQuestion. Skip this prompt if all fixes were aborted (nothing was applied).

   Question:
     header: "Next"
     text: "Fix run complete. <F> fixes applied, <S> skipped, <N> needs-input. What next?"
     options:
       - label: "Commit changes"
         description: "Stage and commit using the suggested commit message"
       - label: "Push to remote"
         description: "Commit and push to update the PR"
       - label: "Re-run on remaining"
         description: "Run /fix-pr-review again for skipped/needs-input items"
       - label: "Done"
         description: "Exit — I'll handle the rest manually"

On "Commit changes": stage relevant files and commit with the suggested detailed commit message. On "Push to remote": commit first (same as above), then `git push`. On "Re-run on remaining": if the original input was a local file, invoke `/fix-pr-review <original-file-path>` scoped to skipped/needs-input items; otherwise invoke `/fix-pr-review <url>` scoped to remaining items. On "Done": exit.

### 5. Exit

Do not auto-commit unless the user chose "Commit changes" or "Push to remote" in the post-completion prompt above.

---

## Error handling

- **`gh` / git / auth prereqs** → Phase 1 prereq block catches these with actionable messages.
- **Wrong repo** → fail fast: `cd` into the right clone and retry. Do not auto-clone.
- **Wrong branch / detached HEAD** → offer `gh pr checkout <num>` via AskUserQuestion with explicit warning on detached state. On "Abort", exit.
- **Uncommitted WIP, user declines stash** → `Commit or stash your uncommitted work first.`
- **Phase 2 GraphQL error (rate limit, 404, private repo)** → surface error, exit. For 404: `Couldn't access PR — check repo access and run 'gh auth refresh -s repo'.`
- **Phase 2 pagination loop hangs** → surface per-page error, exit.
- **Phase 3 subagent fails entirely** → abort. Do NOT attempt to triage without the subagent.
- **Phase 4 plan validation fails** → one retry with specific missing-field message. Second failure → abort.
- **Phase 5 type-check tooling missing** → skip β with a one-line warning; proceed (cross-file errors caught by `/done` in Phase 6).
- **Phase 5 cyclic fix dependencies** → abort, tell user to edit plan.
- **Phase 5 full abort by user** → revert all edits via pre-edit snapshots, restore stash, exit non-zero.
- **Phase 7 reply validator failure** → mini-rewrite pass; on second failure, log as `reply_invalid` and skip posting for that item.
- **Phase 7 GraphQL errors** → log per-item, continue batch, surface at TOP of final report.
- **Phase 8 stash pop conflict** → surface conflict, tell user to resolve manually. Do NOT auto-resolve. Document the mixed working-tree state in the final report.

## Rules

- **NEVER** auto-commit. Only suggest commit messages at the end.
- **NEVER** skip the Phase 3 CLAUDE.md read — project conventions override CodeRabbit preferences. This is the single highest-ROI anti-slop lever.
- **NEVER** skip the Phase 3 mechanical grounding step (STEP 2) — findings that don't trace back to `grounding_a` and `grounding_b` are hallucinations.
- **NEVER** post generic replies. The Phase 7 reply validator mechanically rejects them — do not bypass it.
- **NEVER** post a FIX reply generated in Phase 3 — always regenerate from the actual post-fix diff in Phase 7 Step 7a.
- **NEVER** dismiss the CodeRabbit review's `CHANGES_REQUESTED` state — let CodeRabbit auto-re-review when the user pushes.
- **NEVER** post replies for body-only nitpicks (no thread to reply to). Promoted nitpicks with `thread_id=null` get fixes but no GitHub ack — surfaced in the final report instead.
- **NEVER** touch GitHub (Phase 7) for any local file input (`./review.md`, `/tmp/review-pr-*-findings.md`, etc.).
- **NEVER** proceed past Phase 4 without explicit "Execute plan" or edited-plan confirmation via AskUserQuestion.
- **NEVER** proceed past Phase 4 if plan validation is missing required fields: `claude_md_quote` for R5, `prior_commit_sha` for R4, `disagree_rationale` for DISAGREE, `grounding_a` + `grounding_b` for every item, `fix_plan` ≥ 30 chars for every FIX.
- **NEVER** corrupt user WIP — always auto-stash before Phase 5 edits, restore in Phase 8, error loudly on stash conflicts.
- **NEVER** retry a β-failed fix more than twice — treat the 3rd failure as `skip` and route to NEEDS-INPUT.
- **NEVER** self-heal `/done` more than 2 iterations — report remaining issues and let the user decide.
- **NEVER** revert an Edit without writing the pre-edit snapshot back — the Edit tool has no undo.
- **NEVER** use `bun check-types --filter=<pkg>` — use `bun turbo run check-types --filter=<pkg>` (or pnpm equivalent). `bun` doesn't forward unknown flags to npm scripts.
- **NEVER** use `-F` for GraphQL ID variables — `-F` does JSON type coercion that can break all-numeric IDs. Use `-f` (raw string) for IDs.
