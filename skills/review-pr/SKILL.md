---
name: review-pr
description: Review a GitHub PR, then automatically request changes for any findings or approve a clean review. Use on a PR URL when the ask is to produce and submit findings; when findings already exist and the ask is to act on them, use /fix-pr-review. Batch mode covers 2+ PRs or "review all open PRs". For local uncommitted changes, use /parallel-review.
---

# /review-pr: Deep GitHub PR Review

Reviews a remote GitHub PR with anti-slop filtering. Input: **PR URL only**.

Goal: produce an accurate, critical, actionable PR review, filter out noise (style nitpicks, hallucinated references, duplicates, generic advice), and submit the result to GitHub. Reviews of another author's PR use `REQUEST_CHANGES` or `APPROVE`; self-reviews use `COMMENT` because GitHub forbids authors from approving their own PRs.

**Cascade** is the failure this review is built to prevent: a fix shipped for round N's finding becomes round N+1's finding. Two things feed it: the suggested fix carries a defect of its own, and the fix lands on the cited site while identical sibling sites go untouched. So every finding proposing a code change carries an `Inverse risk:` and a `Class-sites:` count, one field per feeder. Phase 3 measures the result as `cascade_share` at step 7.5, the verdict at step 8 reads it to say whether the PR is converging, and Phase 4 prints it.

This skill assumes CodeRabbit is configured on the repo via `.coderabbit.yaml`. CodeRabbit catches style + convention findings before this skill runs; `/review-pr` focuses on what only deep semantic + codebase-wide review can do.

**Use AskUserQuestion for user-facing decisions that still require judgment**: stop-and-ask, large-PR confirmation, and post-failure recovery. Posting is not a decision point: invoking `/review-pr` authorizes submission of the complete review. Any sentence that offers the user 2+ labeled paths is an AskUserQuestion call. Options are cursor-selectable, concrete, and considered. Put the strongest first and mark it "(Recommended)".

## Reference files

Each one is loaded only on the branch that reaches it, some by main, some by a subagent. Loader and firing condition:

- `references/batch-mode.md`: orchestration rules, "don't stop" semantics, consolidated-report template, and automatic posting sequence. Loaded by **main** at Phase 1 when the user gives 2+ PR URLs or asks for all open PRs.
- `references/reviewer-prompt.md`: the whole Subagent 1 prompt, the anti-slop rules it works under, and the note on why the finding shape is not restated inside it. Loaded by **main** at the Phase 2 dispatch on every `SIZE_MODE` branch, `solo-main` included.
- `references/cross-cutting-prompt.md`: the whole Subagent 3 prompt. Loaded by **main** at the Phase 2 dispatch when `SIZE_MODE` is `parallel-chunked` or `parallel-chunked-confirm`; the unchunked modes never dispatch Subagent 3.
- `references/q5-type-coercion.md`: the Q5 type-coercion scan: coercion methods, how to decide a field is numeric, severity. Loaded by **Subagent 1** while answering Q5 when the diff contains a DB insert/update or an API payload construction.
- `references/class-sweep-and-inverse-risk.md`: reviewer-prompt steps 5 and 6: blast-radius search order, the `class_completeness:` and `Inverse risk:` field rules, the worked inverse-risk examples. Loaded by **Subagent 1** as soon as any finding proposes a code change.
- `references/repo-map.md`: the `repo_map_files` / `repo_map_exports` shell, local and cross-repo modes. The one copy in the repo; `/fix-pr-review` and `/harden-plan` load it from here too. Loaded by **main** in Phase 1 when `packages/` or `apps/` exists.
- `references/q6-reusability-search.md`: STEP A enumeration + STEP B search algorithm + Q6 control-flow gap. Loaded by **Subagent 1** when the diff has 1+ new top-level definitions.
- `references/finding-output-format.md`: the per-finding field block, the `class_completeness:` audit shape, and the run-level closing block. The one copy of the finding shape. Loaded by **Subagent 1**, **Subagent 3** and **V3** before they write any finding.
- `references/schema-design-checks.md`: Q7 (overlap), Q8 (1:1 consolidation), Q9 (cross-table FK) checks. Loaded by **Subagent 1** when `INCLUDE_SCHEMA_CHECKS = true`, and by **V3** when the gap check covers Q7–Q9.
- `references/verification-subagents.md`: V1/V2/V3 dispatch conditions + the exact prompt each is given. Loaded by **main** in Phase 3 at the first of steps 4.55 / 4.9 / 6 that fires.
- `references/false-positive-rules.md`: the four-rule YAML table (`wrapped-coercion`, `intent-alignment`, `library-behavior-citation`, `default-fallback`) each surviving finding is run through. Loaded by **main** at Phase 3 step 4.6 when any finding survives step 4.5.
- `references/finding-state-schema.md`: both persistence files: `.claude/review-state/<pr>.yml` (schema, finding-ID strategy, state machine, Phase 4 write-back) and the run-over-run cache (schema + the three replay branches). Loaded by **main** in Phase 1 before the review-state read and the cache check, and again in Phase 4 before the state write-back.
- `references/github-posting.md`: three-phase REST/GraphQL posting flow + rolling-review fix + re-run preflight (verdict-body sync, thread resolution) + failure recovery. Loaded by **main** in Phase 4 for every completed review.

## Planning-doc grounding (optional pre-review context)

If `docs/superpowers/specs/` or `~/.claude/plans/*.md` reference this PR, check the diff against those documented design decisions and flag undocumented deviations under Q1 (Intent); if no such files exist, skip this check.

## Usage

```
/review-pr https://github.com/owner/repo/pull/123
```

If no URL is provided, ask the user for one. Bare `gh` commands infer a PR from the current branch. This skill reviews the URL it was given.

## Batch mode (multiple PRs)

Fires when the user provides **2+ PR URLs** or asks to review **all open PRs**. A single-PR run skips this entirely and drops straight into Phase 1. On that branch, load `${CLAUDE_SKILL_DIR}/references/batch-mode.md` before doing anything else: it holds the PR enumeration, the orchestration rules (one subagent per PR, main never reviews inline, subagents never post or ask), the "don't stop" semantics for review-only checkpoints, the consolidated-report template, and the automatic posting sequence.

---

## Phase 1: Gather context (main)

Run these as **two separate Bash tool calls in a single assistant message** (true parallelism requires separate tool_use blocks, not `&&` chained):

```bash
gh pr view <url> --json number,title,body,author,baseRefName,headRefName,additions,deletions,changedFiles,files,closingIssuesReferences,reviews,comments,state,isDraft
gh pr diff <url>
```

Phase 1 fetches the **full diff**. Stash it in main context, needed for the error-handling content scan AND Phase 3 critic's reference verification.

### Empty-diff short-circuit

If `changedFiles == 0` OR `additions + deletions == 0`:

> **Nothing to review.** This PR contains no reviewable file changes.

Stop immediately.

### Private-repo / access-error handling

If `gh pr view` returns a GraphQL resolution error or HTTP 404:

> **Couldn't access PR.** Check repo access. Try `gh auth refresh -s repo` and retry.

Fail fast.

### Detect self-review posting

After the metadata request succeeds, compare the authenticated viewer with the PR author:

```bash
VIEWER=$(gh api user -q .login)
AUTHOR=$(gh pr view <url> --json author -q .author.login)
```

GitHub documents that [pull request authors cannot approve their own pull requests](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/reviewing-changes-in-pull-requests/about-pull-request-reviews). Set `IS_SELF_REVIEW=true` when the accounts match and continue through the complete review. Phase 3 still decides the semantic verdict as `approve` or `request-changes`; Phase 4 submits the review with `COMMENT`, preserving its summary and per-finding threads without claiming an approval GitHub cannot record. Set `IS_SELF_REVIEW=false` otherwise.

### Extract linked issues

1. Prefer `closingIssuesReferences` (each carries its own `repository.nameWithOwner`; use that, not the PR's repo).
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
text: "Intent is unclear. No linked issue and the description lacks grounding signals. How should I proceed?"
options:
  - "Proceed anyway": Review with just the diff; findings will be generic without grounding
  - "Skip this PR": Abort the review
  - "I'll provide intent": Wait for user to type intent text
```

On "I'll provide intent": wait for follow-up text, then build the intent model from it.

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

> No `.coderabbit.yaml` in `<owner>/<repo>`. Adding one pushes style + convention checks into CodeRabbit. The `coderabbit-config` skill carries a template (`npx skills add bhagyamudgal/skills@coderabbit-config`). Future `/review-pr` runs in this repo will be tighter.

The hint is informational. It never gates posting.

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

Use `REVIEW_CACHE_CONTRACT_VERSION` from `references/finding-state-schema.md`, already loaded for the review-state read. Validate `contract_version` before reading any cache field. A missing or mismatched version invalidates the complete cache and starts a full fresh review. For a current cache, comparing `last_run_sha` to `CURRENT_HEAD` selects one of three branches: replay the cached run unchanged, re-review only the new commits, or invalidate and start fresh. The cache schema and the full body of each branch live in that reference under "Run-over-run cache".

After a successful run, write `contract_version: REVIEW_CACHE_CONTRACT_VERSION` with the result in `$CACHE_FILE` at the end of Phase 4. The cache is local and independent of GitHub state.

If `PRIOR_STATE.convergence` exists, invoke `converge-reviews` with the current request, base/head, diff hash, paths, and planned roster/lenses before Phase 2. Reuse a matching result without dispatch. When it returns `closure_check: available`, dispatch the one targeted check over only the named blocker IDs and changed sites. Keep the recorded round unchanged and reject any new finding or widened coverage from that check. Feed its evidence and updated blocker dispositions back through `converge-reviews`, persist the new result plus `closure_check: passed | failed`, then apply that result: a passing check may return `converged`; a failed check remains `blocked-at-cap` at the current round. When the initial result is `continue`, review only the invalidated coverage it names; apply any other result without starting another round.

### Compute shared-package repo map (for Q6)

If `packages/` or `apps/` exists, load `${CLAUDE_SKILL_DIR}/references/repo-map.md` and run the block for the mode you are in: it holds both shell blocks (the cross-repo `gh api` tree fetch and the local `bash -c` find/grep pair, each truncating at 500 lines) and stashes `repo_map_files` + `repo_map_exports` for Subagent 1's prompt. It is the one copy of that shell, shared with `/fix-pr-review` and `/harden-plan`.

If neither directory exists, skip the shell: set both to `N/A (not a monorepo)` and flag `IS_MONOREPO=false`. Subagent 1 reroutes greps to `src/`.

### Check for error-handling touches (flag for Phase 2)

Grep the diff content for error-handling patterns in **added or modified lines**:

```
try \{ | catch \( | catch \{ | throw new | throw \s | \.catch\( | Result< | rescue | err := | raise
```

If any pattern appears OR user mentions error handling, set `INCLUDE_SILENT_FAILURE_HUNTER = true`.

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

If file exists, pass into Subagent 1 prompt as "Review suppressions — patterns this project has already accepted; skip them". Phase 3 step 5.5 also applies as safety net.

Cross-repo: fetch via `gh api repos/<owner>/<repo>/contents/.claude/review-suppressions.yml?ref=<head-sha>`. Skip on 404.

---

## Phase 2: Reviewer subagents

Launch in a **single message with multiple Agent tool calls** based on `SIZE_MODE`. One dispatch per invocation: the reviewer subagents go out once here, Phase 3's verifiers go out once there, and that is the whole review. If the PR needs a second look, that is a fresh `/review-pr` run. Never a re-dispatch inside this one.

### Dispatch strategy

**`SIZE_MODE == "solo-main"`** (PR < 100 lines):
- Run Subagent 1 prompt inline in main context (no Agent tool call). Main reads stashed diff once, answers questions, populates `reusability_searches:`, outputs in same format as subagent.
- Still dispatch silent-failure hunter (if triggered): fixed-cost subagent saves main context, runs in parallel.

**`SIZE_MODE == "parallel-standard"`** (100–500 lines, default):
- Dispatch Subagent 1 (Claude reviewer) + conditional Subagent 2 (silent-failure hunter) in parallel.

**`SIZE_MODE == "parallel-chunked"`** (500–2000 lines):
- Split diff by file into ~500-line chunks (don't split a file across chunks).
- Dispatch ONE Subagent 1 PER CHUNK with full intent model + prior review timeline + repo map + schema context, but only its chunk's files in scope. Prompt: "Your scope is the files listed above. Do not report findings in other files."
- Dispatch ONE silent-failure hunter at full PR scope.
- Dispatch ONE **cross-cutting reviewer** (Subagent 3) at full PR scope; see below. Chunk
  reviewers report within their own chunk only, so Subagent 3 is the one reviewer that can
  see a defect class spanning two chunks. Without it, that class is a straight path into
  the cascade.

**`SIZE_MODE == "parallel-chunked-confirm"`** (> 2000 lines):

```
header: "Large PR"
text: "This PR is <N> lines. Chunked review will dispatch <M> reviewer subagents (one per ~500-line chunk) plus silent-failure hunter. Expected wall: 2-4 minutes."
options:
  - "Continue": Proceed with chunked parallel review
  - "Cancel": Abort; consider breaking into smaller PRs
```

### Degraded-mode rule

If any subagent errors out or returns empty, continue with the remaining and note `<reviewer> unavailable` in Phase 4 output header. Abort only if ALL fail.

**Note on CodeRabbit**: CodeRabbit's findings arrive through the prior-review timeline in Phase 1, pulled from the PR's existing comments (assuming `.coderabbit.yaml` is configured; see the one-time hint above), so no CodeRabbit subagent is dispatched. If the PR's latest commit has no CodeRabbit comment yet, Subagent 1 carries the load and the next round picks up CR's input.

### Subagent 1: Claude reviewer (`general-purpose`)

Substitute `<SKILL_DIR>` throughout the prompt before it is used, before dispatching in
every mode, and equally before running it inline under `solo-main`, where main's own
working directory is the user's repo and a bare relative path misses in exactly the same
way.

`<SKILL_DIR>` is the absolute directory of the SKILL.md you are currently executing,
the `review-pr` directory this file sits in, resolved through any symlink. Derive it
from that location; never hardcode a path. The same skill installs at user scope
(`~/.claude/skills/review-pr`) and at project scope (`<repo>/.claude/skills/review-pr`),
so a hardcoded guess is wrong half the time and wrong silently.

Subagents inherit the user's repo as their working directory, so a bare `references/...`
path resolves against that repo and finds nothing. The load fails silently and the
subagent answers from memory instead. The same substitution applies to Subagent 3 and to
the Phase 3 verifiers.

#### Prompt substitutions

`<PROMPT_PREAMBLE>` and `<GROUND_TRUTH>` are each substituted into more than one prompt, so
this is their one definition. Every prompt that carries them names them by these tokens.
Substitute the block as written, with `<SKILL_DIR>` already resolved.

**`<PROMPT_PREAMBLE>`**: opens Subagent 1, Subagent 3 and V3, the three prompts that emit
findings. Each of them follows it with its own one-line statement of whether it closes on a
run-level verdict:

```text
## Where the reference files live
SKILL_DIR: <SKILL_DIR>
Your working directory is the user's repo, not the skill directory, so every
`<SKILL_DIR>/references/...` path in this prompt is absolute and must be used as written.
A bare `references/...` resolves against the repo and silently finds nothing.

## Output format, load this FIRST
Load `<SKILL_DIR>/references/finding-output-format.md` before you write anything. It holds
the per-finding field block, meaning `Rule-class`, `Enclosing-symbol`, `Class-sites`,
`Inverse risk` and the `class_completeness:` audit, plus the post-image line-number
convention and the run-level closing block. Emit every finding in exactly that shape; a finding in any other
shape is unparseable to the Phase 3 critic and is dropped.
```

**`<GROUND_TRUTH>`**. Opens Subagent 1 and Subagent 2:

```text
## Ground truth
Goal: <from Phase 1>
Expected touches: <from Phase 1>
Out of scope: <from Phase 1>
Prior findings already reported (raise one again only as a correction): <from Phase 1>
```

#### The prompt

Load `${CLAUDE_SKILL_DIR}/references/reviewer-prompt.md` at this dispatch. Every mode
reaches it, `solo-main` included, since that mode runs the same prompt body inline. It
holds the prompt, the anti-slop rules the reviewer works under, and the note on why the
finding shape is never restated inside it.

### Subagent 2 (conditional): Silent-failure hunter

Only dispatch if `INCLUDE_SILENT_FAILURE_HUNTER = true`.

- `subagent_type`: `pr-review-toolkit:silent-failure-hunter`

The context packet is PART OF THE PROMPT, not commentary around it. Dispatch the whole
block below. Handed only a URL, this subagent has no idea what the PR is for or what
earlier rounds closed, so it re-finds settled issues and misses the rest.

Prompt:

```
Check for silent failures, swallowed errors, and inadequate error handling in the GitHub
PR at <url>. Fetch the diff yourself via `gh pr diff <url>`.

<GROUND_TRUTH>

## Already closed in earlier rounds, do not re-raise
<rule_class list from PRIOR_STATE.findings where status in {resolved, dismissed, wontfix}>
Re-raise one only when the diff shows the resolving code was reverted.
```

### Subagent 3 (conditional): Cross-cutting reviewer

Dispatch when `SIZE_MODE` is `parallel-chunked` or `parallel-chunked-confirm`. Skip otherwise.
In unchunked modes Subagent 1 already sees every file.

- `subagent_type`: `general-purpose`
- Scope: the WHOLE PR. It is the only reviewer permitted to report across file boundaries.

The prompt lives in `${CLAUDE_SKILL_DIR}/references/cross-cutting-prompt.md`. Load it at
this dispatch.

---

## Phase 3: Critic pass (main context)

The critic pass always runs. It is the second-biggest anti-slop lever after the reviewer
prompt, and no branch of this skill prints, posts, or persists findings that have not been
through it.

After ALL subagents return, main Claude runs the critic pass, splitting the work on one line:

- **Judgment stays in main.** Dedupe, the 3-prong test, false-positive rules, suppressions,
  ranking, verdict. These need the intent model and the prior-review timeline, which main
  already holds. Shipping them to a subagent would mean re-sending all of it.
- **Evidence-gathering goes to subagents.** Anything that means grepping the repo,
  enumerating callers, or re-reading files at HEAD. These burn context proportional to the
  codebase and return a few lines of verdict. Main should hold the verdict, not the search.

Steps 4.55, 4.9 and 6 dispatch subagents (see **Phase 3 verification subagents** below).
Everything else runs inline. A verification subagent reports evidence in a compact
structured verdict; main rules on severity, on drops, and on the state file.

Execute in order:

### Phase 3 verification subagents

Cap: **at most 4 verification subagents in total.** V2 and V3 are one each by nature: V2
reads a short prior-state list, V3 runs one gap check. Only V1 batches, so it gets at most
2, at 10 findings per subagent. Findings past V1's first 20, ordered Critical → Minor,
are verified inline in main.
If a verifier errors or returns empty, run its step inline in main and note
`<verifier> unavailable — verified inline` in the Phase 4 header.

The dispatch condition and the exact prompt for each of V1 (class-sweep), V2 (regression
sweep) and V3 (deep gap check) live in `references/verification-subagents.md`. Load it when
you reach the first of steps 4.55 / 4.9 / 6 whose condition holds, and keep it for the
others. The three dispatch in one message. If none holds, the file is never needed.

Substitute `<SKILL_DIR>` in every verifier prompt exactly as for Subagent 1 (see Phase 2).
Verifiers inherit the user's repo as their working directory too.

### 1. Dedupe

Merge findings describing the same issue across reviewers AND within a reviewer's output.

**Dedupe key**: `(file_path, post_image_line, normalized_symbol_name)`, NOT `Category`. For findings without a valid diff line, use `"file-level:<category>"` in place of `post_image_line` (e.g., `(config.ts, file-level:Architecture, missingvalidation)`). Two findings on the same `(file, line, symbol)` are duplicates regardless of category: merge, keep higher severity, concatenate reasoning.

Normalize symbol names: lowercase + strip CamelCase boundaries (`renderUserCard` → `renderusercard`).

Dedupe priority when merging:
1. Severity wins: `Critical > Serious > Moderate > Minor`.
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

2. If `cited_line > max_valid_line`: drop and log `hallucinated reference (line <N> exceeds <M> available)`. Drop it as cited. A line that doesn't exist is not rescued by shifting it to one that does.

### 2. Verify `file:line`

The full diff is in main context (stashed in Phase 1). Main verifies references against it, independently of the subagent's now-discarded context.

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

Keep if **ANY one** fails. Log drops as `noise / 3-prong test`.

### 4.5. Reusability audit verification

For each reviewer's "Q6 No issues" response, verify the audit. Catches: missing audit field, insufficient search count, class-method definitions not counted.

#### 4.5a: Count new definitions in the diff

Match added lines (starting with `+`) against:

```
+\s*(export\s+(default\s+)?)?(async\s+)?(function|class|interface|type)\s+\w+
+\s*(export\s+)?const\s+\w+\s*(:\s*[^=]+)?=\s*(async\s+)?(\([^)]*\)|[a-zA-Z_$][\w$]*)\s*=>
+\s*(export\s+default\s+function|export\s+default\s+class|export\s+default\s+async\s+function)\s+\w+
+\s+(private|protected|public|async|static)(\s+(private|protected|public|async|static))*\s+\w+\s*\(
```

Patterns cover: standard function/class/interface/type, arrow-function consts, default exports, **class methods inside class bodies** (NestJS-style services). Track `{`/`}` nesting from the nearest `class X {` to count only methods inside class blocks.

Combine into `new_definitions_count`.

#### 4.5b: Count and parse the audit

Match `(?:reusability|reuse)_searches?:` (canonical: `reusability_searches:`).

Three outcomes:

1. **Field entirely missing**: PROMPT NON-COMPLIANCE. Drop ALL Q6 "No issues" claims AND add a Serious finding "Reviewer did not include `reusability_searches:` audit — Q6 was not performed."

2. **Field present with sentinel `N/A (no new top-level definitions in diff)`**: verify `new_definitions_count == 0`. If holds, audit is valid. If not, treat as shallow per outcome 3.

3. **Field present with entries**: count entries. If `searches_count < new_definitions_count`, drop "Q6 No issues" claims AND add a Moderate finding "Reusability check was shallow (<S> searches for <N> new definitions) — manual scan recommended before merging."

   Additionally: for each entry where `N > 0` but `verified:` is missing or says `no`, mark the corresponding Q6a claim (if any) as low-confidence and log `search returned hits but reviewer did not verify semantic match`.

#### 4.5c: Log all drops to Filtered Out for auditability.

### 4.55. Class-completeness verification

For each surviving finding that proposes a code change, check its `class_completeness:` audit.
`Class-sites: <A>/<N>` counts the audit's `affected` sites over the total entries in its
`sites:` list. See "`class_completeness:` audit" in `references/finding-output-format.md`
for the vocabulary. `handled` is the state file's separate question and never appears here.

Steps 4.55 and 4.56 both run over the findings the step 6 gap check adds later, not only
over the ones the reviewers raised. See the routing note there. Every finding that
proposes a code change passes through this step; every finding carrying a `Suggested fix:`
passes through 4.56.

Batch every finding needing verification into **V1: Class-sweep verifier** and dispatch it
alongside V2/V3. Main applies the rules below to what V1 returns.

1. **Field missing entirely**: the sweep was not run. Keep the finding and let V1 run the
   sweep. Derive the signature from `Rule-class`, and append V1's result to the finding. Log
   `class sweep run by verifier — reviewer omitted audit`.

2. **`verdict: INCOMPLETE`**: the reviewer found sites it did not report. Fold every
   unreported site into the finding's `Class-sites` count and list them in the finding
   body. A finding covering 1 of 4 sites, reported as if it covered the defect, is a
   cascade in waiting.

3. **`verdict: COMPLETE` with `search:` naming zero tool calls**: treat as missing (case 1).

4. **Shared-symbol escalation**: if the finding's file sits in a shared package (use the
   Phase 1 repo map) OR `Enclosing-symbol` is exported, its blast radius includes every
   caller. Where the sweep stopped at the defining file, run the caller search yourself
   and note the behavioral delta at each call site. Enumerate them before the fix ships,
   not after.

Every finding that enters this step leaves it, widened. Log every widening.

Done when every finding proposing a code change exits this step with a non-empty
`Class-sites`.

### 4.56. Inverse-risk verification

For each surviving finding with a `Suggested fix:`:

1. **`Inverse risk:` missing**: derive it yourself before printing. Ask what breaks if
   the suggestion is implemented literally and nothing else changes.

2. **Inverse risk is worse than the finding**: the suggestion is not a fix. Either
   rewrite it into one that doesn't trade the defect for a bigger one, or keep the
   finding and replace the suggestion with `no safe one-line fix — needs design`.

3. **Record it.** The `inverse_risk` string is persisted to `.claude/review-state/<pr>.yml`
   on the finding. Round N+1 checks it FIRST, before hunting anything new. See step 4.9.

`/fix-pr-review` implements these suggestions verbatim. An unvetted one-sentence
remedy becomes production code.

Done when every surviving finding carrying a `Suggested fix:` exits this step with a
non-empty `Inverse risk:`.

### 4.6. Apply false-positive rules table

A unified iterator over a rules table. Each rule has: `id`, `trigger` (regex matched against `Issue` or `Why`), `evidence_check` (a callable that returns `evidence_present | evidence_absent | inapplicable`), `action` (`drop` / `downgrade-1` / `downgrade-1-and-note`).

Apply each rule in order. A rule fires when (1) `trigger` regex matches AND (2) `evidence_check` returns the expected branch. Log each fire to Filtered Out with the rule `id` + reason.

The rules themselves, the four-rule YAML table with every `trigger` regex and `evidence_check` body, live in `references/false-positive-rules.md`. Load it here whenever at least one finding survives step 4.5; skip it when the finding list is empty. That table is the single source of truth for false-positive filtering: adding a new false-positive class is a one-row YAML edit there, not a new prose section here.

### 4.9. Proactive regression sweep (runs before prior-state suppression, 4.95)

Skip entirely when `CURRENT_ROUND == 1`.

Step 4.95 below only re-examines a resolved finding when a reviewer happens to re-raise
its exact ID: regressions caught by luck. This step catches them on purpose.

Dispatch **V2: Regression sweep verifier** over EVERY finding in `PRIOR_STATE` with
`status in {resolved, dismissed, wontfix}`, regardless of whether any reviewer mentioned it
this round. V2 gathers the evidence; main applies the rules below to its verdicts:

1. **Re-verify by `rule_class`, not by ID hash.** The ID is
   `sha1(file::enclosing_symbol::rule_class)`, so the same defect resurfacing in a
   sibling symbol produces a DIFFERENT id and escapes matching entirely. Search the
   stored `class_sites`, plus any new sites the current diff added, for the class
   signature. A resolved finding whose class has an unhandled site is not resolved:
   reopen it with `status: regression` and cite the specific site.

2. **Check the stored `inverse_risk`.** If the fix that resolved this finding recorded
   an inverse risk, confirm that failure mode is absent at the current head. This is
   the cascade caught one round early.

3. **Re-validate dismissals against `depends_on`.** A `wontfix` records the code
   condition its rationale rests on. If a later commit invalidated that condition, the
   dismissal is void. Reopen with `status: active` and note which commit voided it.

4. **Attribute the lineage: bounded to one hop.** Blame the finding's cited line
   (`git blame -L <line>,<line>` locally; `gh api repos/<owner>/<repo>/commits?path=<path>`
   in cross-repo mode). Set `caused_by: <prior finding id>` ONLY when blame lands on a
   commit recorded as some prior finding's `commit_sha_resolved`. Otherwise
   `caused_by: null`. Stop there rather than walking back through parent commits.
   This covers the findings this step REOPENS. The findings this round raised fresh get
   the same treatment at step 4.96; both feed the count at step 7.5.

Done when every `PRIOR_STATE` entry with `status in {resolved, dismissed, wontfix}` has a
recorded V2 verdict, and the verdict count equals the dispatched count. A missing verdict
means V2 dropped that entry. Re-check it inline rather than reading silence as still-closed.

### 4.95. Apply prior-state suppression (multi-round dedup)

For each remaining finding:

1. Compute `id = sha1(<file>::<enclosing_symbol>::<rule_class>).hexdigest()[:10]`.
   - If subagent failed to emit `Rule-class:` or `Enclosing-symbol:`, synthesize: `enclosing_symbol = "<module>"`, `rule_class = first 3 words of Issue (lowercased, space-joined, stop-words filtered)`. Log a warning so the prompt can be tuned.

2. Look up `id` in `PRIOR_STATE.findings`. If a match exists with `status in {resolved, dismissed, wontfix}`:

   - **`status == resolved`**: verify the diff between `commit_sha_resolved..HEAD` doesn't reintroduce the issue.
     - Re-introduced (resolving change reverted) → set this finding's status to `regression`, keep it (will be flagged as a fresh active finding with regression history in Phase 4).
     - Not re-introduced → DROP, log `prior-state suppression, resolved in round <round_resolved> by commit <commit_sha_resolved>`.

   - **`status in {dismissed, wontfix}`** → DROP, log `prior-state suppression, <status> in round <round_resolved>: "<dismissal_reason>"`.

3. Report every finding's state as exactly one of: `active`, `resolved` (with commit), `dismissed` (with reason), `wontfix` (with reason), `regression`. The enum is closed, and it is the only status vocabulary that appears in output, logs, or comments.

### 4.96. Attribute lineage on this round's findings

Skip entirely when `CURRENT_ROUND == 1`. There is no earlier fix to attribute to, and
every finding gets `caused_by: null`.

Step 4.9 attributes lineage on findings it REOPENS from prior state. This step does it for
the findings this round raised fresh, which is the case the cascade check exists to
catch: a new finding sitting on a line the previous round's fix wrote. Skip this and
`cascade_share` is 0 by construction and the trend line always reads "Converging".

Run it over the findings that SURVIVED step 4.95, one hop, same bound as step 4.9:

1. Blame the finding's cited line: `git blame -L <line>,<line>` locally,
   `gh api repos/<owner>/<repo>/commits?path=<path>&sha=<head_sha>` in cross-repo mode.

2. Set the field:

   ```
   caused_by: <id of the prior finding whose commit_sha_resolved is that blame commit, or null>
   ```

   Set an id ONLY when the blame commit is recorded as some `PRIOR_STATE` finding's
   `commit_sha_resolved`. Otherwise `null`. Do not walk back through parent commits, and
   do not guess from proximity or topic.

3. A finding with no cited line (module-scope) gets `caused_by: null`; there is no line to
   blame. Same for a finding whose blame commit predates round 1.

4. When several prior findings share the blame commit, take the single nearest cause. The
   cardinality rule in `references/finding-state-schema.md` decides which.

Done when every surviving finding carries a `caused_by` value, `null` included. Step 7.5
counts the non-null ones; Phase 4 write-back persists them.

### 5. Confidence-based drop

Drop all `Confidence: low` findings at Moderate or Minor. Log as `low-confidence filler`. **Keep** low-confidence Critical/Serious. Humans want risky-but-uncertain flags.

### 5.5. Apply project-level suppressions

If `SUPPRESSIONS` was loaded in Phase 1, match each remaining finding:

1. Check if `Issue` text contains `pattern` (case-insensitive substring).
2. If `category` set, also check finding's `Category` matches exactly.
3. If `file` set, also check finding's `File` path contains the string.

If ALL specified conditions match: DROP, log `suppressed by .claude/review-suppressions.yml: "<reason>" (pattern: "<pattern>")`.

**Critical/Serious override**: suppressions drop findings at any severity. A team that explicitly decided a pattern is acceptable outranks the review, and `reason` keeps the drop auditable.

### 6. Gap check (Q1–Q6, Q7–Q9 if schema PR)

For any question category where Subagent 1 said nothing, briefly think about whether the diff has anything in that category. Add findings if you spot misses. Include Q7–Q9 only if `INCLUDE_SCHEMA_CHECKS = true`.

**Large-PR routing**: if `additions + deletions >= 500` AND main lacks the full diff,
route this check to **V3: Deep gap check** and fold its findings in here. V3 has the
context budget to answer from the diff itself, where main would be guessing from a
file list. Pass V3 `INCLUDE_SCHEMA_CHECKS` and `SCHEMA_DIR`. It is dispatched precisely
on the large PRs where schema changes live, so dropping the flag drops Q7–Q9 exactly
where they are most likely to fire.

**Re-run the cascade gates on everything this step adds.** Findings created here, main's
own and V3's alike, arrive after steps 4.55, 4.56 and 4.96 have already run, so they
carry an empty `Class-sites`, an empty `Inverse risk`, and no `caused_by` unless routed
back. Route every finding this step adds back through:

1. **4.55**: class-completeness sweep, so `Class-sites: <A>/<N>` is non-empty. Where V1
   has already returned, run the sweep inline in main rather than dispatching a second V1;
   the 4-subagent cap still holds.
2. **4.56**: inverse-risk derivation, so every `Suggested fix:` carries an `Inverse risk:`.
3. **4.96**: lineage attribution, so `caused_by` is set or explicitly null.

`Inverse risk` and `Class-sites` are mandatory on any finding proposing a code change no
matter which step raised it; a gap-check finding that skips these writes nulls straight
into the state file and blinds the next round's regression sweep.

### 7. Rank by severity

Critical > Serious > Moderate > Minor.

### 7.5. Compute `cascade_share`

The ONE place this ratio is computed. Ranking is done, the finding set is final, and every
finding carries a `caused_by` from step 4.9 or 4.96, so this is the first point where the
number is both computable and stable.

At `CURRENT_ROUND == 1` there is no prior round to attribute to: set `cascade_share = 0`,
skip the trend sentence, and move on.

From round 2:

```
cascade_share: <count of active findings with a non-null caused_by> / <count of active findings>
```

Zero active findings → `cascade_share = 0`, not a division by zero.

Step 8 below reads this value for the verdict prefix, and Phase 4's **Cascade check**
prints it. Neither recomputes it: one number, one definition, one round.

### 8. Decide verdict

- One or more surviving findings → `request-changes`
- No findings → `approve`

At any round, if `cascade_share > 0.5` — the single value computed at step 7.5 just above,
never recomputed here — prepend to the verdict reason:

> Over half of this round's findings were introduced by the previous round's fixes.
> Patching site-by-site is not converging. This module needs a design pass.

### 9. Decide Senior-engineer approval

A binary assessment:

- **No**: one or more findings survived the critic pass, OR Q1 identified an intent gap
- **Yes**: otherwise

Write a one-sentence approval reason grounded in the most important finding or the absence of findings. Nothing you compose for this review carries an em or en dash, this reason and the `Goal`, Summary and one-line issue cells alike. Text quoted from the issue or the diff stays as you found it.

---

## Phase 4: Output

Every Phase 4 path reaches **Convergence handoff** after the GitHub review is authoritatively submitted and local state is written back.

### Print this block to terminal, always

```
# PR Review: <title> (#<number>)

**Senior engineer approval**: <emoji> <Yes | No>, <one-sentence reason>
**Verdict**: <emoji> <approve | request-changes>
**GitHub event**: <APPROVE | REQUEST_CHANGES | COMMENT; use COMMENT when IS_SELF_REVIEW=true>
**Goal**: <intent goal>
**Size**: <additions>/<deletions> across <N> files
**Reviewers**: <list, with "(unavailable)" marker for any failed subagent>
**Round**: <CURRENT_ROUND> (<active>/<resolved>/<dismissed> findings carried across rounds)
**Convergence**: <N> new · <C> caused by earlier fixes · <R> regressions reopened · <F> carried
<trend line, omit at round 1>

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
<dropped findings with reasons, for auditability>

## Multi-round status
<for each finding in PRIOR_STATE: id, file, status, round_resolved/dismissed, dismissal_reason. Useful for "did I really ship M3 in round 5?" scanning.>
```

### Verdict and approval emoji mapping

**Senior engineer approval**: Yes → ✅ · No → ❌
**Verdict**: approve → ✅ · request-changes → ❌
**Severity headers**: Critical → 🔴 · Serious → 🟠 · Moderate → 🟡 · Minor → 🔵

Filtered out is mandatory in terminal output. It is the only way to see when the critic is over-filtering. Multi-round status is mandatory when `PRIOR_STATE.findings` is non-empty.

### Cascade check

Mandatory from round 2. PRINT the value Phase 3 step 7.5 computed. Do not recompute it
here. Step 8 already read that same number for the verdict prefix, and a second
computation on a different finding set is how the two disagree.

`cascade_share` = (active findings with `caused_by` set) / (total active findings)

Emit exactly one trend sentence, picked from what the numbers say:
- `cascade_share > 0.5` → `Not converging, because the fixes are generating the findings.`
- New findings falling round over round and `cascade_share == 0` → `Converging, with the tail shrinking.`
- New count flat across 3+ rounds → `Stalled at the same volume each round; scope may be growing.`

```
Convergence: 4 new · 3 caused by earlier fixes · 1 regression reopened · 2 carried
Trend: cascade_share 0.75. Not converging, because the fixes are generating the findings.
```

If a verdict reverses an earlier `approve` assessment, say so explicitly in the Summary
with the reason and the two SHAs. For another author's PR, write *"I approved this at `dd142e0`.
I'm reversing that, because `e4f7432` made one thing worse than it was."* For a self-review,
write *"I assessed this as approve at `dd142e0`. I'm reversing that, because `e4f7432`
made one thing worse than it was."*

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

### Post to GitHub

An explicit `/review-pr <PR URL>` invocation is fresh authorization to submit the complete review to that exact PR. The authorization remains valid only while the target PR, head SHA, semantic verdict, GitHub event, and frozen payload match the later mutation card. Apply `preflight-mutations` normally and block on any non-ready verdict; do not bypass it or ask the user to select findings, confirm posting, keep the review local, edit the body, or choose a next action.

- When `IS_SELF_REVIEW=false`, submit every surviving finding as an individual review comment with `REQUEST_CHANGES`; submit a clean review with `APPROVE` and no review comments.
- When `IS_SELF_REVIEW=true`, submit the same complete finding set or clean summary with `COMMENT`. Keep the semantic verdict in the body and terminal output.
- Preserve every item in `Filtered out` as terminal-only audit output. Filtered items never enter the GitHub payload.

Load `${CLAUDE_SKILL_DIR}/references/github-posting.md` now. The full posting flow handles:

- **Step 0**: detect the latest prior `<!-- review-pr:run -->` tagged review. Reuse it only when it is under 30 days old, its GitHub state matches the required event, its semantic verdict still matches on self-reviews, it was threaded, and that exact review owns a thread for every current file-referenced finding. Any failed condition creates a fresh pending review with the complete finding set.
- **Step 0b**: verdict-body sync check. On re-runs with a `last_posted_review_id` in cache, map the body verdict through `IS_SELF_REVIEW` and warn when the implied event drifted from its GitHub state.
- **Step 0c**: re-review thread resolution. Resolve threads for findings now `resolved`, record the "Resolved since last review" line, and preserve existing threads during an eligible body-only rolling update.
- **Steps 1-2**: compose summary body (with marker comment) + per-finding review comments.
- **Step 3**: pre-posting hunk validation (line vs file-level routing).
- **Step 4 / 4-rolling**: REST POST PENDING, or update the submitted review body only when rolling eligibility proves no new threads are needed.
- **Step 5**: GraphQL `addPullRequestReviewThread` for file-level findings on a fresh pending review.
- **Step 6**: GraphQL `submitPullRequestReview` with `REQUEST_CHANGES`, `APPROVE`, or the self-review `COMMENT`; skip only after a body-only rolling update whose review already has the required state and complete thread ownership.
- **Step 7**: failure recovery with disclosed partial state.
- **Step 8**: cache write-back + state file update + thread resolution for fixed findings.

Pass into the reference: `<owner>`, `<repo>`, `<pr-num>`, `<head_sha>`, `CURRENT_ROUND`, `IS_SELF_REVIEW`, summary body content, the complete surviving finding list (line-level + file-level), `PRIOR_STATE` (Step 0c compares against it), `$CACHE_FILE` path, `$STATE_FILE` path, and the `/review-pr` invocation as the posting authorization source.

### Convergence handoff

After authoritative posting and write-back, invoke `converge-reviews` with the PR request, base/current head and diff hash, reviewed paths, reviewer roster and lenses, current findings and dispositions, and `$STATE_FILE`. Store the resulting `convergence` block in that existing state file without replacing `review-pr`'s finding state. Apply its result contract before recommending another review round or declaring the review converged.

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
- **Review event permission denied** → surface the GitHub error and stop. Use `COMMENT` only when Phase 1 established `IS_SELF_REVIEW=true`; never downgrade another author's review after a permission failure.
- **Failed state-file write** → log warning, do not block posting. State file is best-effort persistence.
