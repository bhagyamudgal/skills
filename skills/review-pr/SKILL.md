---
name: review-pr
description: Review a GitHub PR — deep, anti-slop, grounded in the linked issue's intent. Use on a PR URL when the ask is to produce findings; when findings already exist and the ask is to act on them, use /fix-pr-review. Batch mode covers 2+ PRs or "review all open PRs". For local uncommitted changes, use /parallel-review.
---

# /review-pr — Deep GitHub PR Review

Reviews a remote GitHub PR with anti-slop filtering. Input: **PR URL only**.

Goal: produce an accurate, critical, actionable PR review that surfaces what a human reviewer should double-check — and filters out noise (style nitpicks, hallucinated references, duplicates, generic advice).

**Cascade** is the failure this review is built to prevent: a fix shipped for round N's finding becomes round N+1's finding. Two things feed it — the suggested fix carries a defect of its own, and the fix lands on the cited site while identical sibling sites go untouched. So every finding proposing a code change carries an `Inverse risk:` and a `Class-sites:` count, one field per feeder. Phase 3 measures the result as `cascade_share` at step 7.5, the verdict at step 8 reads it to say whether the PR is converging, and Phase 4 prints it.

This skill assumes CodeRabbit is configured on the repo via `.coderabbit.yaml`. CodeRabbit catches style + convention findings before this skill runs; `/review-pr` focuses on what only deep semantic + codebase-wide review can do.

**Use AskUserQuestion for ALL user-facing decisions** — stop-and-ask, cache replay, large-PR confirmation, self-review, findings selection, post-review, post-failure, post-completion. Any sentence that offers the user 2+ labeled paths is an AskUserQuestion call, including the one that ends the run. Options are cursor-selectable, concrete, and considered — put the strongest first and mark it "(Recommended)".

## Reference files

Each one is loaded only on the branch that reaches it — some by main, some by a subagent. Loader and firing condition:

- `references/batch-mode.md` — orchestration rules, "don't stop" semantics, consolidated-report template, end-of-run decision prompt. Loaded by **main** at Phase 1 when the user gives 2+ PR URLs or asks for all open PRs.
- `references/q6-reusability-search.md` — Phase 1 repo-map shell + STEP A enumeration + STEP B search algorithm + Q6 control-flow gap. Loaded by **main** in Phase 1 when `packages/` or `apps/` exists, and by **Subagent 1** when the diff has 1+ new top-level definitions.
- `references/finding-output-format.md` — the per-finding field block, the `class_completeness:` audit shape, and the run-level closing block. The one copy of the finding shape, and the definitions of the severity tiers. Loaded by **Subagent 1**, **Subagent 2**, **Subagent 3**, **V1** and **V3** before they write any finding — and by **main**, which authors findings of its own in Phase 3 (the reusability audit at step 4.5, the gap check at step 6) and would otherwise assign severities without ever reading the tier definitions. This roster must list every loader, not only the ones worth mentioning: a loader missing here reads as an emitter working without the contract, which is what the roster exists to rule out.
- `references/schema-design-checks.md` — Q7 (overlap), Q8 (1:1 consolidation), Q9 (cross-table FK) checks. Loaded by **Subagent 1** when `INCLUDE_SCHEMA_CHECKS = true`, and by **V3** when the gap check covers Q7–Q9.
- `references/lens-map.md` — the file-type and signal detection rules that decide which lenses apply to which changed file, as data rather than prose. Loaded by **main** in Phase 1 to build the coverage ledger's cell set.
- `references/lenses.md` — the lens catalogue: per lens, its trigger, the question it asks, what does and does not qualify as a finding, and for Tier 2 the artifact to open. Loaded by **Subagent 1** for the lenses its files selected, and by **V3**, whose gap check iterates the `new-ground` lens set as its second axis. **Not** by Subagent 3: it is scoped to cross-file patterns, receives no `LENS_ASSIGNMENTS` and returns no lens verdicts — the per-file cells are Subagent 1's alone. Do not add a loader to this list without checking that the named prompt actually loads it; a manifest entry is prose, the prompt is what executes.
- `references/verification-subagents.md` — V1/V2/V3 dispatch conditions + the exact prompt each is given. Loaded by **main** in Phase 3 at the first of steps 4.55 / 4.9 / 6 that fires.
- `references/false-positive-rules.md` — the YAML rules table each surviving finding is run through, in the order the file lists them. Loaded by **main** at Phase 3 step 4.6 when any finding survives step 4.5. The file is the single source for the rule set, including which rules are `applies_to` and which are `trigger`, and which carry an `exempt_lenses` key. No roster here: the last one drifted, classifying two `trigger` rules as preconditions while the same sentence said not to restate it.
- `references/finding-state-schema.md` — both persistence files: `.claude/review-state/<pr>.yml` (schema, finding-ID strategy, state machine, Phase 4 write-back) and the run-over-run cache (schema + the three replay branches). Loaded by **main** in Phase 1 before the review-state read and the cache check, and again in Phase 4 before the state write-back.
- `references/github-posting.md` — three-phase REST/GraphQL posting flow + post-submit assertion + re-run preflight (verdict-body sync, thread dedupe, thread resolution) + failure recovery. Loaded by **main** in Phase 4 when the user chooses to post.

## Planning-doc grounding (optional pre-review context)

If `docs/superpowers/specs/` or `~/.claude/plans/*.md` reference this PR, check the diff against those documented design decisions and flag undocumented deviations under Q1 (Intent); if no such files exist, skip this check.

## Usage

```
/review-pr https://github.com/owner/repo/pull/123
```

If no URL is provided, ask the user for one. Bare `gh` commands infer a PR from the current branch — this skill reviews the URL it was given.

## Batch mode (multiple PRs)

Fires when the user provides **2+ PR URLs** or asks to review **all open PRs** — a single-PR run skips this entirely and drops straight into Phase 1. On that branch, load `${CLAUDE_SKILL_DIR}/references/batch-mode.md` before doing anything else: it holds the PR enumeration, the orchestration rules (one subagent per PR, main never reviews inline, subagents never post or ask), the "don't stop" semantics that turn every checkpoint into a pending decision, the consolidated-report template, and the single end-of-run decision prompt.

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

Load `${CLAUDE_SKILL_DIR}/references/finding-state-schema.md` before reading the state file — it defines the schema, the legal `status` values, and the finding-ID strategy every later phase writes against.

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
  PRIOR_STATE='{ pr: <num>, repo: "<owner>/<repo>", findings: [], last_round: 0,
                 ledger: { round: 0, rows: [], cells_total: 0, cells_examined: 0,
                           cells_cannot_assess: 0, cells_not_examined: 0 } }'
fi

CURRENT_ROUND=$(( $(echo "$PRIOR_STATE" | yq '.last_round') + 1 ))
```

### Round-cap short-circuit (before any reviewing)

If `CURRENT_ROUND > 3`, stop here. Print the round number, the follow-up issue from
`PRIOR_STATE.followup_issue` (or that none was filed and why), and exit without dispatching
a single reviewer.

This check belongs at the point `CURRENT_ROUND` is computed, not at the verdict. The cap's
own wording is "do not silently re-review" — sited in Phase 3 that is unachievable, because
by then Phase 1 has run, every Phase 2 reviewer has been dispatched and every Phase 3
verifier has finished. The run would announce it should not have re-reviewed *after* paying
the entire cost of re-reviewing.

The exception is a `followup_issue.status` of `failed`, `incomplete` or `declined`: there
the backlog does not exist, so offer to file it (Phase 4's "File the follow-up issue" step)
against `PRIOR_STATE.findings` still `active`, then stop. Filing needs no new review.

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

On "I'll provide intent": wait for follow-up text, then build the intent model from it.

### Size warning

If `additions + deletions > 2000`:

> This PR touches **X lines across Y files**. Review may be noisy and slow. Proceeding.

### Wall-time instrumentation (start)

Capture one timestamp at the top of each phase, named so Phase 4 can find it:

```
PHASE_START_1=$(date +%s)     # here, top of Phase 1
PHASE_START_2=$(date +%s)     # top of Phase 2, before the first reviewer dispatch
PHASE_START_3=$(date +%s)     # top of Phase 3, before step 1 dedupe
PHASE_START_4=$(date +%s)     # top of Phase 4, before the terminal block
```

Phase 4 computes per-phase elapsed from consecutive pairs and the total from
`PHASE_START_1`. "Capture one at each later phase" is not a step — name each variable and
its site, or Phase 4 reads `PHASE_START_*` and finds only the first one, printing a
per-phase breakdown whose later rows have no source.

### Detect cwd-vs-PR-repo mismatch (cross-repo mode)

```bash
CWD_REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
PR_REPO="<owner>/<repo>"
[ -z "$CWD_REPO" ] || [ "$CWD_REPO" != "$PR_REPO" ] && CROSS_REPO_MODE=true || CROSS_REPO_MODE=false
```

Cross-repo mode changes:
1. Repo map computation falls back to remote `gh api` tree fetch.
2. Phase 3 already-fixed check uses `gh api` instead of local `git log`.

Set the `Mode` header field to `cross-repo (reviewed from outside the PR's repo)`. The field and its permitted values are defined in `references/finding-output-format.md`.

### CodeRabbit config check (one-time hint)

Once per `(owner, repo)` per session, check whether `.coderabbit.yaml` exists in the PR repo:

```bash
gh api "repos/<owner>/<repo>/contents/.coderabbit.yaml" >/dev/null 2>&1 \
  && CR_CONFIG_PRESENT=true \
  || CR_CONFIG_PRESENT=false
```

If `CR_CONFIG_PRESENT=false` AND this is the first run of `/review-pr` against this repo in the current session, print the hint once **inside the Phase 4 terminal block**, on its own line below `Coverage`:

> No `.coderabbit.yaml` in `<owner>/<repo>` — adding one pushes style + convention checks into CodeRabbit. The `coderabbit-config` skill carries a template (`npx skills add bhagyamudgal/skills@coderabbit-config`). Future `/review-pr` runs in this repo will be tighter.

The hint is informational — it never gates posting.

It goes inside the terminal block rather than after Phase 4 because Phase 4's last step
declares itself the final turn of this skill, so "after Phase 4 output" is a slot nothing
ever reaches. A hint scheduled after the end never prints.

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

Comparing `last_run_sha` to `CURRENT_HEAD` selects one of three branches: replay the cached run unchanged, re-review only the new commits, or invalidate and start fresh. The cache schema and the full body of each branch live in `references/finding-state-schema.md` under "Run-over-run cache" — already loaded above for the review-state read.

After successful run, write result to `$CACHE_FILE` at end of Phase 4 (cache is local, independent of GitHub state).

### Compute shared-package repo map (for Q6)

If `packages/` or `apps/` exists, load `${CLAUDE_SKILL_DIR}/references/q6-reusability-search.md` and run its "Phase 1 — compute the shared-package repo map" section: it holds both shell blocks (the cross-repo `gh api` tree fetch and the local `bash -c` find/grep pair, each truncating at 500 lines) and stashes `repo_map_files` + `repo_map_exports` for Subagent 1's prompt.

If neither directory exists, skip the shell: set both to `N/A (not a monorepo)` and flag `IS_MONOREPO=false` — Subagent 1 reroutes greps to `src/`.

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

### Select lenses and build the ledger cell set

Load `<SKILL_DIR>/references/lens-map.md`. For every file in the diff:

1. **Match `skip_paths` first.** A generated, vendored or binary path short-circuits: emit a
   row carrying its `skip_reason` and `lenses: []`, and move on. Honour `route_to` — a
   lockfile is not unreviewable, it routes to the lens that reviews it as a unit rather
   than line by line. Skipping this check first is what stops every image and build
   artifact from collecting a full lens set.
2. Otherwise classify against the map's `file_types` (path globs plus content signatures)
   and evaluate the `signals` regexes over its changed lines. The union of `always_on`,
   the file-type lenses and the signal lenses is that file's lens set.

`file_type` is a **list**, not one value — a path may match several rows, and the rule is
union, never first hit. A migration that is also a schema definition is both.

Write the result as `LENS_ASSIGNMENTS` — one entry per (file, lens). This is the ledger's
cell set, fixed before any reviewing happens, and it is what makes coverage countable:
`cells_total` is decided here, so a file that no reviewer ever opens still has rows, and
they read `not-examined` rather than vanishing.

Seven of the map's signals set `side: both`. Evaluate those against removed lines as well —
a predicate deleted from a `WHERE`, a guard dropped from a handler and a validation
stripped from a schema never appear on the `+` side, and a diff-only reviewer scanning
additions is structurally blind to them.

A file matching no `file_type` gets `other` and the `always_on` lenses. Never skip a file
for being unclassifiable; record it and let the ledger show what it got.

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

Launch in a **single message with multiple Agent tool calls** based on `SIZE_MODE`. One dispatch per invocation: the reviewer subagents go out once here, Phase 3's verifiers go out once there, and that is the whole review. If the PR needs a second look, that is a fresh `/review-pr` run — never a re-dispatch inside this one.

### Dispatch strategy

**`SIZE_MODE == "solo-main"`** (PR < 100 lines):
- Run Subagent 1 prompt inline in main context (no Agent tool call). Main reads stashed diff once, answers questions, populates `reusability_searches:`, outputs in same format as subagent.
- Still dispatch silent-failure hunter (if triggered) — fixed-cost subagent saves main context, runs in parallel.

**`SIZE_MODE == "parallel-standard"`** (100–500 lines, default):
- Dispatch Subagent 1 (Claude reviewer) + conditional Subagent 2 (silent-failure hunter) in parallel.

**`SIZE_MODE == "parallel-chunked"`** (500–2000 lines):
- Split diff by file into ~500-line chunks (don't split a file across chunks).
- Dispatch ONE Subagent 1 PER CHUNK with full intent model + prior review timeline + repo map + schema context, but only its chunk's files in scope. Prompt: "Your scope is the files listed above. Do not report findings in other files."
- Dispatch ONE silent-failure hunter at full PR scope.
- Dispatch ONE **cross-cutting reviewer** (Subagent 3) at full PR scope — see below. Chunk
  reviewers report within their own chunk only, so Subagent 3 is the one reviewer that can
  see a defect class spanning two chunks. Without it, that class is a straight path into
  the cascade.

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

**Note on CodeRabbit**: CodeRabbit's findings arrive through the prior-review timeline in Phase 1, pulled from the PR's existing comments (assuming `.coderabbit.yaml` is configured — see the one-time hint above), so no CodeRabbit subagent is dispatched. If the PR's latest commit has no CodeRabbit comment yet, Subagent 1 carries the load and the next round picks up CR's input.

### Subagent 1 — Claude reviewer (`general-purpose`)

Substitute `<SKILL_DIR>` throughout the prompt before it is used — before dispatching in
every mode, and equally before running it inline under `solo-main`, where main's own
working directory is the user's repo and a bare relative path misses in exactly the same
way.

`<SKILL_DIR>` is the absolute directory of the SKILL.md you are currently executing —
the `review-pr` directory this file sits in — resolved through any symlink. Derive it
from that location; never hardcode a path. The same skill installs at user scope
(`~/.claude/skills/review-pr`) and at project scope (`<repo>/.claude/skills/review-pr`),
so a hardcoded guess is wrong half the time and wrong silently.

Subagents inherit the user's repo as their working directory, so a bare `references/...`
path resolves against that repo and finds nothing — the load fails silently and the
subagent answers from memory instead. The same substitution applies to Subagent 3 and to
the Phase 3 verifiers.

Prompt:

```
You are reviewing a GitHub PR for a human reviewer who wants accurate, critical findings — every one traceable to a line of this diff and worth a second look.

## Where the reference files live
SKILL_DIR: <SKILL_DIR>
Your working directory is the user's repo, not the skill directory, so every
`<SKILL_DIR>/references/...` path below is absolute and must be used as written.
A bare `references/...` resolves against the repo and silently finds nothing.

## Output format — load this FIRST
Load `<SKILL_DIR>/references/finding-output-format.md` before you write anything. It
holds the per-finding field block, the `class_completeness:` audit shape, the
post-image line-number convention, and the closing block you end with. Emit every
finding in exactly that shape — a finding in any other shape is unparseable to the
Phase 3 critic and is dropped.

## Ground truth
Goal: <from Phase 1>
Expected touches: <from Phase 1>
Out of scope: <from Phase 1>
Prior findings already reported (raise one again only as a correction): <from Phase 1>

## Prior multi-round state — already closed
These findings were resolved or dismissed in earlier review rounds. They stay closed unless the diff shows the resolving code was reverted.
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
If true, ALSO load and follow `<SKILL_DIR>/references/schema-design-checks.md` for Q7-Q9.

## Lens assignments — one line per (file, lens) you owe a verdict on
<LENS_ASSIGNMENTS, filtered to the files in this chunk — the exact block main built in
 Phase 1. Format: `<path>  [<file_type ids>]  <lens ids>`, and for a skipped path
 `<path>  SKIPPED — <skip_reason>`. Mark each lens with where it came from — `*` for
 always_on, bare for a file-type or signal assignment. The L8 carve-out below turns on
 exactly that distinction, and without it the reviewer cannot tell a legitimate `clean`
 from a coverage gap. If this block is empty, say so in your output and
 do not invent assignments; an empty block means main failed to build them, and the
 ledger must record that rather than record clean cells.>

## Your task

1. Run `gh pr diff <url>` for the diff.
2. Run `gh pr view <url> --json files` for the file list.

3. **GROUNDING PASS — MANDATORY before answering any Q.**
   Write 3-5 bullets describing what this diff changes MECHANICALLY:
   - Which files are touched and how (added / modified / deleted / renamed)
   - Which functions / classes / schemas change
   - What the observable behavior change is
   Every subsequent finding MUST trace back to one of these bullets. If a finding doesn't trace, you are hallucinating it — drop before output.

3.5. Apply the lenses assigned to each file you were given. Your `LENS_ASSIGNMENTS` block
   lists them per file; load `<SKILL_DIR>/references/lenses.md` and apply each one named.

   Return an explicit verdict for **every** (file, lens) pair — `clean`, `finding`,
   `not-applicable` with a one-line reason, or `cannot-assess` naming the artifact that
   would answer it. Emit them in the cell-line shape defined in
   `<SKILL_DIR>/references/finding-output-format.md`, "Coverage-ledger cell verdicts" — one
   line per cell, after your findings, in the order the assignments were given. A verdict in
   any other shape is unparseable to ledger assembly and is recorded as `not-examined`,
   exactly as silence is. A pair you say nothing about is recorded as `not-examined`, which
   blocks approval, so silence costs more than an honest `not-applicable`. Never resolve a
   pair you did not actually examine to `clean`.

   Tier 2 lenses require opening a file that is **not in the diff** — the sibling, the
   caller, the consumer. That hop is the point: roughly 30% of defects that escape review
   are one hop out, and the file to open is always finite and named by the lens. A Tier 2
   lens answered without opening anything is `not-examined`, not `clean`.

   The one exception is `L8` where the map assigned it as `always_on`: there the obligation
   is hop 1 only — re-read the full post-image of the file you just edited. See
   `<SKILL_DIR>/references/lens-map.md`, "Always-on L8 is hop 1". Without that carve-out
   every file in every PR would owe the full hop sequence and approval would be
   unreachable, which teaches readers to ignore the coverage line entirely.

   Two of these invert a question you are also asked below, and the inverted form is where
   the defects are. Q3 asks whether this diff introduced duplication; L8 asks whether a
   duplicate already exists that this diff **failed to fix** — the largest single class in
   the study behind this skill, and in about one case in nine the unfixed twin was inside a
   file the diff was already editing. Answering Q3 honestly does not discharge L8.

4. Answer Q1–Q6 EXPLICITLY (plus Q7–Q9 if `INCLUDE_SCHEMA_CHECKS = true`). Each must be addressed, even if just "No issues".

   Emit the answers in the `Q<n>:` line shape defined in
   `<SKILL_DIR>/references/finding-output-format.md`, "Question answers", before your
   findings. Phase 3 step 4.5 **retracts** unfounded Q6 clearances, and it can only retract
   a claim it can locate — a "no issues" written in prose that main cannot find is a
   clearance that survives the check meant to withdraw it.

   Q1. Intent — Does this PR actually solve the stated goal? Where's the gap?
   Q2. Unnecessary changes — Files, abstractions, config, or indirection not required by the goal? (Collapses scope creep + overengineering — reporting separately produces dupes.)
       Q2a. Documentation necessity — For any `.md` file with > 200 added lines OR > 40% of PR's total additions: question whether the docs are needed. Check if `CLAUDE.md` or existing project docs already cover the domain. Frame as observation, not bug. Severity: Minor. Category: Unnecessary.
       Q2b. Premature complexity — Detect known patterns NOT mentioned in the linked issue:
            - Optimistic locking (`version` columns with default 1)
            - Soft-delete on append-only/audit tables
            - Denormalized aggregation columns
            - Polymorphic reference patterns
            - Self-referential FKs
            If `INCLUDE_SCHEMA_CHECKS = true` AND the project already uses the same pattern in existing tables (search `$SCHEMA_DIR`), treat it as an established convention.
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

       The full STEP A enumeration + STEP B search algorithm + Q6 control-flow gap notes live in `<SKILL_DIR>/references/q6-reusability-search.md`. Load it before answering Q6 if the diff has 1+ new top-level definitions.

       Q6a. Reimplements existing code (default Severity: SERIOUS; escalate to CRITICAL if existing thing lives in auth / validation / crypto package)
            <finding with concrete existing file:path to reuse>
            OR "No issues"

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

   Do this when the finding is FIRST RAISED, not when it is resolved — an unswept
   finding is a cascade waiting to happen.

   For each finding, derive a searchable signature from its `Rule-class` — the
   literal or structural pattern, not the prose — and search its **blast radius**:
   the touched files, then the enclosing module, then the package, plus every
   caller when `Rule-class` names a shared or exported symbol.

   REQUIRED audit field — use this EXACT name `class_completeness:`. Its exact shape,
   the `affected | not-affected` vocabulary, and the `N/A (no code change proposed)`
   sentinel are in `<SKILL_DIR>/references/finding-output-format.md` under
   "`class_completeness:` audit" — write it as specified there, not from memory.

   If the sweep finds sites the finding did not cover, fold them into the SAME
   finding (preferred — one finding, N sites) or raise them as siblings, so every
   site of the class is on the page.

6. **INVERSE-RISK PASS — MANDATORY, run after drafting every `Suggested fix`.**

   Treat your own remedy as code under review. Ask, for each suggested fix:
   *if a competent engineer implements this literally and nothing else, what breaks?*

   Answer concretely, naming the failure mode — not "could have issues". Worked
   examples:
     - "fail-closed decrypt" → placeholder value that can be re-encrypted over real ciphertext
     - "key={dataUpdatedAt} to re-seed the form" → silently discards unsaved edits on refetch
     - "treat missing reference as an empty run" → dead schedule now reports success forever
     - "widen the backend gate" → frontend mirror still restricts; inverts the bug

   Write it into the finding's `Inverse risk:` field. If the fix is a pure addition
   with no behavior traded away, say `none — pure addition`.

   A fix whose inverse risk is worse than the original finding is the cascade with
   extra steps. Rewrite the suggestion or downgrade the finding to an observation.

7. Additionally flag:
   - Silent failures (caught errors swallowed without logging)
   - Removed error handling
   - Breaking changes to public APIs not mentioned in PR description
   - Architectural issues (wrong layer / wrong package / wrong abstraction boundary)
   - **New error values / sentinels / thrown exceptions**: trace each to EVERY
     downstream consumer in this pass, including consumers the diff does not touch.
     Error chains are static and fully traceable, so one pass can cover every layer
     — a layer per round is a cascade.

     REQUIRED audit field on every such finding — use this EXACT name `consumers:`:

       consumers:
         - <file:line>: handles | does-not-handle — <one clause>

     Done when every new error value / sentinel / thrown exception in the diff has a
     `consumers:` list. Zero consumers is acceptable ONLY when the search that returned
     zero is named on the same line:
     `consumers: none — <tool>("<query>", "<path>") → 0 matches`.

8. **Schema-specific checks (Q7–Q9)** — only when `INCLUDE_SCHEMA_CHECKS = true`. Load `<SKILL_DIR>/references/schema-design-checks.md` and follow its Q7/Q8/Q9 instructions. Skip entirely if false.
```

#### Anti-slop rules (MANDATORY)

- Report semantic and codebase-wide defects; CodeRabbit owns style, formatting, and naming.
- Prior findings stay closed. **Exception**: if you believe a prior finding was wrong, report it with `Category: Prior-finding-correction` + concrete explanation.
- Findings in `PRIOR_STATE.findings` with `status in {resolved, dismissed, wontfix}` stay closed too. Re-raise one only when the diff shows the resolving code was reverted, and mark the new finding's `status` as `regression`.
- Raise a conditional issue ("this COULD become a problem if X") only when X is visible as a codebase signal in the diff.
- Point every finding at a `File: <path>`. Give the line when you can name it on the post-image side; leave it off for module-scope findings, which route to file-level review comments.
- Raise missing tests only where this PR was expected to add them — advice that would fit any PR belongs to no PR.
- If a question (Q1–Q9, except Q6) has nothing to report, write "No issues" — that is a complete answer.
- **Permission to abstain**: if answering needs code you haven't seen, fetch it via `gh api repos/<owner>/<repo>/contents/<path>?ref=<head-sha>` or write `Cannot assess — would need <file>`. Both are complete answers.
- Low-confidence findings at Moderate or Minor WILL be dropped by the critic. Only flag if a human should still take a second look.
- For Q6, populate `reusability_searches:` with actual tool calls or the N/A sentinel. Empty/missing audit = Q6 claims INVALID.
- Populate `class_completeness:` with actual tool calls or the N/A sentinel. Missing audit = the finding is treated as UNSWEPT and the critic runs the sweep itself.
- Every `Suggested fix:` ships with an `Inverse risk:` — `none — pure addition` when the fix trades nothing away.

#### Output format

`references/finding-output-format.md` is the one copy — the per-finding field block
(including `Rule-class`, `Enclosing-symbol`, `Inverse risk` and `Class-sites`), the
`class_completeness:` audit shape, the post-image line-number convention, and the
run-level closing block. The prompt above already tells Subagent 1 to load it from
`<SKILL_DIR>/references/finding-output-format.md`; do not restate any of it here, and do
not paste a second copy into any prompt.

### Subagent 2 (conditional) — Silent-failure hunter

Only dispatch if `INCLUDE_SILENT_FAILURE_HUNTER = true`.

- `subagent_type`: `pr-review-toolkit:silent-failure-hunter`

The context packet is PART OF THE PROMPT, not commentary around it — dispatch the whole
block below. Handed only a URL, this subagent has no idea what the PR is for or what
earlier rounds closed, so it re-finds settled issues and misses the rest.

Prompt:

```
Check for silent failures, swallowed errors, and inadequate error handling in the GitHub
PR at <url>. Fetch the diff yourself via `gh pr diff <url>`.

## Where the reference files live
SKILL_DIR: <SKILL_DIR>
Your working directory is the user's repo, not the skill directory, so the
`<SKILL_DIR>/references/...` paths below are absolute and must be used as written.
A bare `references/...` resolves against the repo and silently finds nothing.

## Output format — load this FIRST
Load `<SKILL_DIR>/references/finding-output-format.md` before you write anything and emit
every finding in exactly that shape, `Severity`, `Category`, `Rule-class`,
`Enclosing-symbol`, `Class-sites`, `Inverse risk` and the `class_completeness:` audit
included. A finding missing `Severity` is never ranked and never escalates to a verdict;
it does not appear in the Filtered Out list either, so it fails invisibly rather than
loudly. You report findings only — no run-level verdict.

That file defines the severity tiers, including the rule that a defect which fails
**silently** is tiered one step higher than the same defect failing loudly. That rule is
load-bearing for you specifically: silence is the whole class you are dispatched to find,
so without it you would systematically under-tier your own specialty. Apply it when you
write `Severity:` — and do not relabel `Category` to harvest an escalation the finding
has not earned.

## Ground truth
Goal: <from Phase 1>
Expected touches: <from Phase 1>
Out of scope: <from Phase 1>
Prior findings already reported (raise one again only as a correction): <from Phase 1>

## Already closed in earlier rounds — do not re-raise
<rule_class list from PRIOR_STATE.findings where status in {resolved, dismissed, wontfix}>
Re-raise one only when the diff shows the resolving code was reverted.
```

### Subagent 3 (conditional) — Cross-cutting reviewer

Dispatch when `SIZE_MODE` is `parallel-chunked` or `parallel-chunked-confirm`. Skip otherwise
— in unchunked modes Subagent 1 already sees every file.

- `subagent_type`: `general-purpose`
- Scope: the WHOLE PR. It is the only reviewer permitted to report across file boundaries.

```
You are reviewing a GitHub PR at <url> for CROSS-FILE patterns ONLY. Other reviewers cover
each file in isolation — do not duplicate them. Fetch the diff yourself.

## Where the reference files live
SKILL_DIR: <SKILL_DIR>
Your working directory is the user's repo, not the skill directory, so the
`<SKILL_DIR>/references/...` path below is absolute and must be used as written.
A bare `references/...` resolves against the repo and silently finds nothing.

## Output format — load this FIRST
Load `<SKILL_DIR>/references/finding-output-format.md` before you write anything and emit
every finding in exactly that shape, `Rule-class`, `Enclosing-symbol`, `Class-sites`,
`Inverse risk` and the `class_completeness:` audit included. A finding in any other shape
is unparseable to the Phase 3 critic and is dropped. You report findings only — no
run-level verdict.

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
definition not cross-cutting; drop it.

"No cross-file findings" is a complete answer.
```

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

Cap: **at most 4 verification subagents in total.** V2 and V3 are one each by nature — V2
reads a short prior-state list, V3 runs one gap check. Only V1 batches, so it gets at most
2, at 10 findings per subagent. Findings past V1's first 20 — ordered Critical → Minor —
are verified inline in main.
If a verifier errors or returns empty, run its step inline in main and note
`<verifier> unavailable — verified inline` in the `Reviewers` header field. That field's
spec in `references/finding-output-format.md` keeps this distinct from a reviewer that
actually cost coverage — this one is complete coverage under context pressure, and the
ledger must not record it as a gap.

The dispatch condition and the exact prompt for each of V1 (class-sweep), V2 (regression
sweep) and V3 (deep gap check) live in `references/verification-subagents.md`. Load it when
you reach the first of steps 4.55 / 4.9 / 6 whose condition holds, and keep it for the
others — the three dispatch in one message. If none holds, the file is never needed.

Substitute `<SKILL_DIR>` in every verifier prompt exactly as for Subagent 1 (see Phase 2)
— verifiers inherit the user's repo as their working directory too.

### 1. Dedupe

Merge findings describing the same issue across reviewers AND within a reviewer's output.

**Dedupe key**: `(file_path, post_image_line, normalized_symbol_name)` — NOT `Category`. For findings without a valid diff line, use `"file-level:<category>"` in place of `post_image_line` (e.g., `(config.ts, file-level:Architecture, missingvalidation)`). Two findings on the same `(file, line, symbol)` are duplicates regardless of category — merge, keep higher severity, concatenate reasoning.

Normalize symbol names: lowercase + strip CamelCase boundaries (`renderUserCard` → `renderusercard`).

Dedupe priority when merging:
1. Severity wins: `Critical > Serious > Moderate > Minor`.
2. Category precedence for ties: `Prior-finding-correction > Security > Reusability > Silent-failure > Breaking-change > Performance > DRY > Unnecessary > Intent > Architecture`. All ten values are ranked — step 6.5 reuses this ladder verbatim, so a category missing here has no tie-break there either. `Prior-finding-correction` ranks first because it asserts an earlier finding was wrong; losing it in a merge silently restores the finding it was filed to retract.
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

2. If `cited_line > max_valid_line`: drop and log `hallucinated reference (line <N> exceeds <M> available)`. Drop it as cited — a line that doesn't exist is not rescued by shifting it to one that does.

### 2. Verify `file:line`

The full diff is in main context (stashed in Phase 1) — main verifies references against it, independently of the subagent's now-discarded context.

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
`Class-sites: <A>/<N>` counts the audit's `affected` sites over the total entries in its
`sites:` list — see "`class_completeness:` audit" in `references/finding-output-format.md`
for the vocabulary. `handled` is the state file's separate question and never appears here.

Every finding that proposes a code change passes through this step, including findings the
step 6 gap check adds later — see the routing note there.

Batch every finding needing verification into **V1 — Class-sweep verifier** and dispatch it
alongside V2/V3. Main applies the rules below to what V1 returns.

1. **Field missing entirely** — the sweep was not run. Keep the finding and let V1 run the
   sweep. Derive the signature from `Rule-class`, and append V1's result to the finding. Log
   `class sweep run by verifier — reviewer omitted audit`.

2. **`verdict: INCOMPLETE`** — the reviewer found sites it did not report. Fold every
   unreported site into the finding's `Class-sites` count and list them in the finding
   body. A finding covering 1 of 4 sites, reported as if it covered the defect, is a
   cascade in waiting.

3. **`verdict: COMPLETE` with `search:` naming zero tool calls** — treat as missing (case 1).

4. **Shared-symbol escalation**: if the finding's file sits in a shared package (use the
   Phase 1 repo map) OR `Enclosing-symbol` is exported, its blast radius includes every
   caller. Where the sweep stopped at the defining file, run the caller search yourself
   and note the behavioral delta at each call site — enumerate them before the fix ships,
   not after.

Every finding that enters this step leaves it, widened. Log every widening.

Done when every finding proposing a code change exits this step with a non-empty
`Class-sites`.

### 4.56. Inverse-risk verification

Every finding carrying a `Suggested fix:` passes through this step, including findings the
step 6 gap check adds later — see the routing note there.

For each surviving finding with a `Suggested fix:`:

1. **`Inverse risk:` missing** — derive it yourself before printing. Ask what breaks if
   the suggestion is implemented literally and nothing else changes.

2. **Inverse risk is worse than the finding** — the suggestion is not a fix. Either
   rewrite it into one that doesn't trade the defect for a bigger one, or keep the
   finding and replace the suggestion with `no safe one-line fix — needs design`.

3. **Record it.** The `inverse_risk` string is persisted to `.claude/review-state/<pr>.yml`
   on the finding. Round N+1 checks it FIRST, before hunting anything new — see step 4.9.

`/fix-pr-review` implements these suggestions verbatim — an unvetted one-sentence
remedy becomes production code.

Done when every surviving finding carrying a `Suggested fix:` exits this step with a
non-empty `Inverse risk:`.

### 4.6. Apply false-positive rules table

A unified iterator over a rules table. Each rule has: `id`, either a `trigger` (regex matched against `Issue` or `Why`) or an `applies_to` (a finding class the rule runs on unconditionally, no text match), an optional `exempt_lenses` (a list of lens ids that switches that rule off for a finding), `evidence_check` (a callable that returns `evidence_present | evidence_absent | inapplicable`), and `action` (`drop` / `downgrade-1` / `downgrade-1-and-note` / `severity-conditional` / `re-anchor-or-drop` / `strip-fix`).

Apply each rule in order. **Check `exempt_lenses` first, before the selector**: if the rule carries the key and the finding's `Lens:` line names any lens in it, the rule is `inapplicable` for that finding — do not match its regex, do not run its `evidence_check`, do not apply its action — and log the skip to Filtered Out as `<rule-id> inapplicable — exempt lens <Lx>`. Otherwise: a `trigger` rule fires when (1) the regex matches AND (2) `evidence_check` returns the expected branch; an `applies_to` rule runs its `evidence_check` on every finding in its class.

Reading `Lens:` is part of this step. The exemption is data on the rule, not a judgement call — a carve-out only main remembers is a carve-out that does not run, which is how an authorization-widening finding came to be downgraded by the rule it was declared exempt from.

**At most one severity change per finding per pass.** When several rules fire, apply the strongest action once — `drop` beats `strip-fix` beats a downgrade — and log every rule `id` that fired. Without this cap the downgrades compound: an unverified distribution claim loses a tier for carrying no command, then loses another as "may be intentional", landing on exactly the softly-stated finding that the first rule exists to forbid. Two soft grounds, neither of which established the claim, should not add up to a verdict.

Log each fire to Filtered Out with the rule `id` + reason.

The rules themselves — the YAML table with every `trigger` / `applies_to` and `evidence_check` body — live in `references/false-positive-rules.md`. Load it here whenever at least one finding survives step 4.5; skip it when the finding list is empty. That table is the single source of truth for false-positive filtering: adding a new false-positive class is a one-row YAML edit there, not a new prose section here.

### 4.9. Proactive regression sweep (runs before prior-state suppression, 4.95)

Skip entirely when `CURRENT_ROUND == 1`.

Step 4.95 below only re-examines a resolved finding when a reviewer happens to re-raise
its exact ID — regressions caught by luck. This step catches them on purpose.

**Build the closed set from GitHub, not from `status` alone.** A finding is closed for
this sweep's purposes when *either*:

- its `PRIOR_STATE.status` is in `{resolved, dismissed, wontfix}`, **or**
- its `github_thread_id` resolves to a thread that GitHub reports as `isResolved: true`.

```
gh api graphql -f query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){
  pullRequest(number:$n){reviewThreads(first:100){pageInfo{hasNextPage endCursor}
  nodes{id isResolved comments(first:1){nodes{body}}}}}}}' -F o=<owner> -F r=<repo> -F n=<num>
```

Paginate past 100 — a truncated page reads as "not resolved" and silently shrinks the sweep.

Keying on `status` alone was leaving most of this step inert. `dismissed` gets written
automatically when the user deselects a finding, but **`resolved` has no automated writer**
— it is set by hand, and on any machine where nobody hand-edits the state YAML, nothing is
ever `resolved`. That is precisely the arm this sweep exists for: the regression case is a
finding that *was fixed* and came back. Thread state is the signal that actually moves,
because merging requires resolving threads.

For the same reason, treat GitHub's `isResolved` as evidence that a finding was **closed**,
never as evidence it was **correct**. Where a repository ruleset requires thread resolution
to merge, resolution is a merge precondition, not agreement — authors resolve findings they
dispute in order to ship.

Dispatch **V2 — Regression sweep verifier** over EVERY finding in that closed set,
regardless of whether any reviewer mentioned it this round. V2 gathers the evidence; main
applies the rules below to its verdicts:

1. **Re-verify by `rule_class`, not by ID hash.** The ID is
   `sha1(file::enclosing_symbol::rule_class)`, so the same defect resurfacing in a
   sibling symbol produces a DIFFERENT id and escapes matching entirely. Search the
   stored `class_sites` — plus any new sites the current diff added — for the class
   signature. A resolved finding whose class has an unhandled site is not resolved:
   reopen it with `status: regression` and cite the specific site.

2. **Check the stored `inverse_risk`.** If the fix that resolved this finding recorded
   an inverse risk, confirm that failure mode is absent at the current head. This is
   the cascade caught one round early.

3. **Re-validate dismissals against `depends_on`.** A `wontfix` records the code
   condition its rationale rests on. If a later commit invalidated that condition, the
   dismissal is void — reopen with `status: active` and note which commit voided it.

4. **Attribute the lineage — bounded to one hop.** Blame the finding's cited line
   (`git blame -L <line>,<line>` locally; `gh api repos/<owner>/<repo>/commits?path=<path>`
   in cross-repo mode). Set `caused_by: <prior finding id>` ONLY when blame lands on a
   commit recorded as some prior finding's `commit_sha_resolved`. Otherwise
   `caused_by: null` — stop there rather than walking back through parent commits.
   This covers the findings this step REOPENS. The findings this round raised fresh get
   the same treatment at step 4.96; both feed the count at step 7.5.

Done when every entry in the closed set built above — **both arms** — has a
recorded V2 verdict, and the verdict count equals the dispatched count. A missing verdict
means V2 dropped that entry — re-check it inline rather than reading silence as still-closed.

### 4.95. Apply prior-state suppression (multi-round dedup)

For each remaining finding:

1. Compute `id = sha1(<file>::<enclosing_symbol>::<rule_class>).hexdigest()[:10]`.
   - If subagent failed to emit `Rule-class:` or `Enclosing-symbol:`, synthesize: `enclosing_symbol = "<module>"`, `rule_class = first 3 words of Issue (lowercased, space-joined, stop-words filtered)`. Log a warning so the prompt can be tuned.

2. Look up `id` in `PRIOR_STATE.findings`. If a match exists with `status in {resolved, dismissed, wontfix}`:

   - **`status == resolved`**: verify the diff between `commit_sha_resolved..HEAD` doesn't reintroduce the issue.
     - Re-introduced (resolving change reverted) → set this finding's status to `regression`, keep it (will be flagged as a fresh active finding with regression history in Phase 4).
     - Not re-introduced → DROP, log `prior-state suppression — resolved in round <round_resolved> by commit <commit_sha_resolved>`.

   - **`status in {dismissed, wontfix}`** → DROP, log `prior-state suppression — <status> in round <round_resolved>: "<dismissal_reason>"`.

3. Report every finding's state as exactly one of: `active`, `resolved` (with commit), `dismissed` (with reason), `wontfix` (with reason), `regression`. The enum is closed, and it is the only status vocabulary that appears in output, logs, or comments.

### 4.96. Attribute lineage on this round's findings

Skip entirely when `CURRENT_ROUND == 1` — there is no earlier fix to attribute to, and
every finding gets `caused_by: null`.

Step 4.9 attributes lineage on findings it REOPENS from prior state. This step does it for
the findings this round raised fresh — which is the case the cascade check exists to
catch: a new finding sitting on a line the previous round's fix wrote. Skip this and
`cascade_share` is 0 by construction and the trend line always reads "Converging".

Run it over the findings that SURVIVED step 4.95, one hop, same bound as step 4.9:

1. Blame the finding's cited line — `git blame -L <line>,<line>` locally,
   `gh api repos/<owner>/<repo>/commits?path=<path>&sha=<head_sha>` in cross-repo mode.

2. Set the field:

   ```
   caused_by: <id of the prior finding whose commit_sha_resolved is that blame commit, or null>
   ```

   Set an id ONLY when the blame commit is recorded as some `PRIOR_STATE` finding's
   `commit_sha_resolved`. Otherwise `null` — do not walk back through parent commits, and
   do not guess from proximity or topic.

3. A finding with no cited line (module-scope) gets `caused_by: null`; there is no line to
   blame. Same for a finding whose blame commit predates round 1.

4. When several prior findings share the blame commit, take the single nearest cause — the
   cardinality rule in `references/finding-state-schema.md` decides which.

Done when every surviving finding carries a `caused_by` value, `null` included. Step 7.5
counts the non-null ones; Phase 4 write-back persists them.

### 5. Confidence-based drop

Drop all `Confidence: low` findings at Moderate or Minor. Log as `low-confidence filler`. **Keep** low-confidence Critical/Serious — humans want risky-but-uncertain flags.

### 5.5. Apply project-level suppressions

If `SUPPRESSIONS` was loaded in Phase 1, match each remaining finding:

1. Check if `Issue` text contains `pattern` (case-insensitive substring).
2. If `category` set, also check finding's `Category` matches exactly.
3. If `file` set, also check finding's `File` path contains the string.

If ALL specified conditions match: DROP, log `suppressed by .claude/review-suppressions.yml: "<reason>" (pattern: "<pattern>")`.

**Critical/Serious override**: suppressions drop findings at any severity — a team that explicitly decided a pattern is acceptable outranks the review, and `reason` keeps the drop auditable.

### 6. Gap check (Q1–Q6, Q7–Q9 if schema PR, plus the lens axis)

**Two axes, not one.** Besides the Q list, walk the lens axis: every entry in
`<SKILL_DIR>/references/lens-map.md`'s `lens_index` whose `q_map` is `new-ground` **or**
ends in `-inverted`, less `META`. Emit one `no gap` / `gap` entry per lens.

**Re-derive that set from the map; never hard-code a count here.** The selection rule is
"lenses no Q-number can discharge", and the two values qualify for opposite reasons —
`new-ground` because no question reaches the lens at all, `-inverted` because the question
that names it asks the mirror-image thing and can be answered honestly while the lens's
own class walks through. Skip `META`: it raises the tier of a silent finding rather than
producing findings of its own, so its entry could only ever read `no gap`, which is the
vacuous verdict this check exists to prevent.

Stating the rule rather than a list is deliberate: a lens filed `refines-Q<N>-inverted`
later is picked up without another edit here, and this check has already been fixed once
for iterating a stale enumeration.

This applies to the **inline** path as well as the dispatched one, and both must select
the same set. Main runs this check itself whenever it holds the full diff, so wiring the
lens axis into the verifier alone would fix it only for large PRs — and two paths through
one check that select differently is how the count and the set drifted apart before.

For any question category where Subagent 1 said nothing, briefly think about whether the diff has anything in that category. Add findings if you spot misses. Include Q7–Q9 only if `INCLUDE_SCHEMA_CHECKS = true`.

**Large-PR routing**: if `additions + deletions >= 500` AND main lacks the full diff,
route this check to **V3 — Deep gap check** and fold its findings in here. V3 has the
context budget to answer from the diff itself, where main would be guessing from a
file list. Pass V3 `INCLUDE_SCHEMA_CHECKS` and `SCHEMA_DIR` — it is dispatched precisely
on the large PRs where schema changes live, so dropping the flag drops Q7–Q9 exactly
where they are most likely to fire.

**Re-run the cascade gates on everything this step adds.** Findings created here — main's
own and V3's alike — arrive after steps 4.55, 4.56 and 4.96 have already run, so they
carry an empty `Class-sites`, an empty `Inverse risk`, and no `caused_by` unless routed
back. Route every finding this step adds back through:

1. **4.55** — class-completeness sweep, so `Class-sites: <A>/<N>` is non-empty. Where V1
   has already returned, run the sweep inline in main rather than dispatching a second V1;
   the 4-subagent cap still holds.
2. **4.56** — inverse-risk derivation, so every `Suggested fix:` carries an `Inverse risk:`.
3. **4.96** — lineage attribution, so `caused_by` is set or explicitly null.

`Inverse risk` and `Class-sites` are mandatory on any finding proposing a code change no
matter which step raised it; a gap-check finding that skips these writes nulls straight
into the state file and blinds the next round's regression sweep.

### 6.5. Cross-finding reconciliation

Step 1 dedupe reconciles **identity** — same defect, two reviewers. Nothing yet reconciles
**consistency**: two findings that are each defensible alone and cannot both be acted on.
This is the only window where the set is final and unranked, so it runs here.

This step adds no findings and changes no order. It only removes or merges.

**Bucket first.** For each finding, collect the `(file, enclosing_symbol)` pairs its
`Suggested fix:` would edit — the anchor site, plus any site the fix text names. Compare
only findings sharing at least one pair. Findings on disjoint symbols cannot contradict;
skipping them keeps this linear in practice rather than quadratic in the finding count.

**Three contradiction classes:**

1. **Opposite edits** — one fix adds what the other removes on the same symbol: add vs.
   remove a guard, `await` vs. drop the `await`, widen vs. narrow a type, memoize vs. inline.
2. **Order-dependent fixes** — each is correct alone; applied together they produce
   something neither intended, because A moves or rewrites the line B's fix assumes.
   Test: would applying A first change the code B's fix cites?
3. **Contradicting premises** — A's `Why` asserts X and B's `Why` asserts not-X about the
   same symbol ("value is always defined here" vs. "value can be null here"). Applies to
   findings with no fix too; a review that states both is wrong somewhere regardless of
   which is acted on.

**Resolution — deterministic, in this order:**

1. **Evidence beats assertion.** The finding whose claim is verifiable survives: it carries
   a re-runnable command (`publish-the-command-or-do-not-claim`), an opened implementation
   (`open-the-callee`, `declaration-is-not-implementation`), or a re-derived anchor
   (`re-derive-the-anchor`). Drop the other, log the basis.
2. **Severity, then Category precedence** — reuse step 1's dedupe ladder verbatim, so the
   two mechanisms never rank the same pair differently.
3. **Still tied → merge, never emit both fixes.** Keep one finding at the higher severity,
   concatenate both `Why` bodies, and replace both suggestions with
   `conflicting fixes — needs design`, naming the two directions. `/fix-pr-review` applies
   suggestions verbatim; two incompatible ones in the same review means it applies whichever
   it reaches first.

**Route merged findings back through 4.56** — a merged or rewritten fix invalidates the
`Inverse risk` derived for either original. Take `caused_by` from the surviving finding.

Log every reconciliation to Filtered Out as
`cross-finding contradiction — <id A> vs <id B>, kept <id>, basis <evidence|severity|merged>`.

Done when no two surviving findings propose incompatible edits to the same
`(file, enclosing_symbol)` pair, and every dropped or merged pair is logged.

### 6.9. Assemble the coverage ledger

Build this round's `ledger` from `LENS_ASSIGNMENTS` (Phase 1), the Phase 2 reviewer
verdicts and the final finding set, following
`<SKILL_DIR>/references/finding-state-schema.md`, "Phase 3 — assemble the ledger".

Step 9.5, the terminal block and the posted body all read the object built **here**. Phase
4 only writes it to disk. It has to be built at this point and not at write-back: the
verdict gate runs before posting, and a gate whose input does not exist yet reads as zero —
which passes. The failure would be silent and in the permissive direction.

A cell with no reviewer verdict is `not-examined` with the reason. A missing verdict is
never a `clean`.

### 7. Rank by severity

Critical > Serious > Moderate > Minor — tiers are defined in
`<SKILL_DIR>/references/finding-output-format.md` ("Severity — what each tier means").
Rank on the value the reviewer emitted; do not re-derive it here. The detectability
modifier is applied once at emission, and applying it a second time here would
double-raise every silent finding.

### 7.5. Compute `cascade_share`

The ONE place this ratio is computed. Ranking is done, the finding set is final, and every
finding carries a `caused_by` from step 4.9 or 4.96 — so this is the first point where the
number is both computable and stable.

At `CURRENT_ROUND == 1` there is no prior round to attribute to: set `cascade_share = 0`,
skip the trend sentence, and move on.

From round 2:

```
cascade_share: <count of active findings with a non-null caused_by> / <count of active findings>
```

Zero active findings → `cascade_share = 0`, not a division by zero.

Step 8 below reads this value for the verdict prefix, and Phase 4's **Cascade check**
prints it. Neither recomputes it — one number, one definition, one round.

#### Partition the active set (`new` / `carried` / `caused` / `reopened`)

Phase 4 prints `<N> new · <C> caused by earlier fixes · <R> regressions reopened ·
<F> carried`. Assign every active finding to **exactly one** bucket, testing in this
order and stopping at the first match:

1. **reopened** — the finding was closed in `PRIOR_STATE` and step 4.9's regression sweep
   reopened it this round.
2. **carried** — its id is in `PRIOR_STATE` with `status: active`. Raised before, still
   unfixed. Not new, however many rounds it survives.
3. **caused** — first raised this round and `caused_by` is non-null: the previous round's
   fix introduced it.
4. **new** — everything else.

The four counts must sum to the active total. If they do not, the ids are unstable and
the convergence line is fiction — say so rather than printing a sum that does not add up.

The ordering is what makes the line mean anything. Without a `carried` bucket, one
defect nobody has fixed yet is reported as a brand-new finding in every round, and five
rounds of the same unfixed thing reads as a review that keeps discovering problems. It
is the same problem, counted five times. `carried` is a backlog; `new` and `caused` are
the only two that indicate the round did work.

### 8. Decide verdict (category-aware)

**What blocks is Critical and Serious inside the change's blast radius.** Blast radius is
wider than the diff:

1. Every file in the diff.
2. **The companion artifacts the change obligates** — a migration for a schema edit, a
   locale key for a new user-facing string, a middleware mount for a new route, a task
   dependency for a new pipeline step, a raised process limit for a new runtime dependency.
3. **Callers and siblings of a changed exported symbol** — the one-hop set the Tier 2
   lenses open.

Points 2 and 3 are not decoration, and reading blast radius as "the diff" quietly disarms
the bar for the worst class the study found. A missing migration is *by definition* a file
that is not in the diff: the defect is the absence. Scope the bar to changed lines only and
the highest-severity recurring class becomes structurally unblockable — every instance of
it lives outside the diff.

A Critical or Serious finding **outside** the blast radius is real, and is reported and
filed; it does not hold this PR, because the PR did not cause it and its author is not
the right person to fix it.

- Any **Critical** → `request-changes`
- Any **Serious** in `Category = Security | Silent-failure | Breaking-change | Reusability` → `request-changes` (these are never "just a comment"; Reusability is escalated because reimplemented code is a correctness risk via divergent fixes)
- Any other Serious → `comment`
- Only Moderate/Minor → `approve` (with comments)
- No findings → `approve`

At any round, if `cascade_share > 0.5` — the single value computed at step 7.5 just above,
never recomputed here — prepend to the verdict reason:

> Over half of this round's findings were introduced by the previous round's fixes.
> Patching site-by-site is not converging — this module needs a design pass.

#### Severity ratchet (`CURRENT_ROUND >= 3`)

From round 3 onward, **only Critical and Serious may block.** Two concrete effects, both
on top of the rules above:

1. **Moderate and Minor stop holding the PR.** With no Critical and no `request-changes`
   Serious, the verdict is `approve` even when Moderate and Minor findings remain — where
   rounds 1–2 would have landed on `comment`.
2. **They report separately.** Print them in the Phase 4 body under the
   `Follow-ups (non-blocking)` heading instead of under their own severity headings. Only
   the heading changes — the per-finding block does not, and Phase 4 states it there.
   Phase 4's **File the follow-up issue** step then offers to file every finding still
   active — this released tail included — as one issue. That step is what makes "tracked
   instead of blocking" true, and it runs ahead of the post decision because the review
   body links to what it creates.

Rationale: a PR that has absorbed two rounds of fixes is being held by a long tail,
and each extra round of Moderate-chasing is another chance to feed the cascade. The
tail is worth less than the churn it costs.

Nothing else moves. No finding is dropped, no severity is rewritten, the verdict enum
stays `approve | comment | request-changes`, and Critical and Serious block exactly as
they do at rounds 1–2.

#### Round cap (`CURRENT_ROUND >= 3` is the last round)

Round 3 is terminal. There is no round 4: whatever survives it is filed, not re-reviewed.

**Enforced, not merely stated.** `CURRENT_ROUND` is computed from `last_round + 1` with no
ceiling, so a fourth invocation is reachable. Key the cap on `>= 3`, not `== 3` — otherwise
a run at round 4 gets the ratchet but neither the follow-up issue nor the terminal
behaviour, which is the worst of both.

- Every finding still active after the ratchet goes into **one** follow-up issue for this
  PR — not one issue per finding, and not a comment on an unrelated ticket.
- The issue is created **complete or not at all.** A partially-written issue that loses
  half the findings is worse than none, because the PR unblocks either way and the missing
  half leaves no trace.
- **Phase 4's "File the follow-up issue" step is what creates it** — asks first, composes
  the whole body, creates in one call, reads the issue back to confirm every finding
  landed, records the number only then. Nothing else in this skill creates it, and no step
  may assume it exists without reading `followup_issue` from the state file.
- Once it exists, link it from the review body and unblock the PR. When it does NOT exist
  — the user declined, or creation failed — the review body and the terminal say so in
  those words. An unblocked PR whose findings went nowhere is a fact the reader is owed,
  never something to paper over with a backlog nobody filed.

**`CURRENT_ROUND > 3` never reaches this step.** Phase 1's round-cap short-circuit stops
the run before any reviewer is dispatched, and owns the whole of that behaviour: reading
`followup_issue` from `$STATE_FILE`, printing a `filed` issue's URL, or filing once over
the uncovered findings when the entry is absent or reads `declined` / `failed` /
`incomplete`. Never file a second issue for one PR — the duplicate is the copy nobody
reads.

The rule lives at the point `CURRENT_ROUND` is computed because that is the only place it
can be honoured. Do not restate the branch here; two copies of one cap drift, and the copy
downstream of the work it is meant to prevent is the one that stops being true.

Either path still ends through the Phase 4 state write-back before stopping
(`references/finding-state-schema.md`, "Phase 4 — write back"). Stopping short of it drops
this round's `followup_issue` and leaves `last_round` unincremented, so round 5 arrives as
round 4 again and re-asks a question already answered.

Rationale: rounds 1–2 fix real defects; by round 3 the measured share of findings that
were themselves *introduced by the previous round's fixes* has collapsed to zero, which
means later rounds are no longer converging on the change — they are widening scope. The
cap converts an unbounded review loop into a bounded one plus a tracked backlog.

### 9. Decide Senior-engineer approval

A binary verdict (with middle option):

- **No** — verdict is `request-changes`, OR Q1 identified an intent gap, OR any Critical exists
- **With changes** — Serious findings exist in any category, OR 3+ Moderate findings
- **Yes** — otherwise

Write a one-sentence approval reason grounded in the most important finding (or absence — e.g., "Does what the issue asks, no Serious issues").

### 9.5. Coverage gate (runs last; overrides steps 8 and 9)

Read `ledger.cells_not_examined` from the ledger step 6.9 assembled.

**First: is there a ledger at all?** If step 6.9 produced none — no reviewer returned cell
verdicts, Phase 2 never dispatched, the assembly step did not run — then treat this as the
strongest possible gate, not the weakest:

- the verdict may not be `approve`, and Senior-engineer approval may not be `Yes`
- say so in these words: *"No coverage ledger was produced this round. This review states
  nothing about what it examined."*

Absent is not zero. An unset `cells_not_examined` reads as `0` under any ordinary
comparison, which passes the gate — so the one run that examined **nothing** would sail
through the check built to stop exactly that, while a run that honestly recorded a single
gap is blocked. This is not hypothetical: the first live run of this skill produced no
ledger at all, and only failed to approve because its verdict was `request-changes` on
unrelated grounds.

If a ledger exists and `cells_not_examined` is greater than zero:

- the verdict may not be `approve` — emit `comment` instead
- Senior-engineer approval may not be `Yes` — emit `With changes` instead
- the reason must state the gap in these terms, with both numbers filled in:

  > No findings in the `<cells_examined>` cells examined; `<cells_not_examined>` not
  > reviewed. This is not an approval of the unexamined code.

This gate exists because there are three independent routes to an approval — step 8, the
round-3 ratchet, and step 9 — and each computes its own. Gating them individually leaves
the next route someone adds ungated. Anything that produces an approval must run before
this step, so the invariant holds at one place instead of three.

`not-applicable` cells are examined; they carry a stated reason and do not count here.
`cannot-assess` cells do not gate either — an unrunnable check is a limit of the review,
not a defect the author can fix — but `cells_cannot_assess` prints regardless, because a
reader deciding whether to merge needs to know which questions nobody answered. Only
`not-examined` gates. Silence dressed as a clean verdict is the failure this whole
mechanism exists to make impossible — never resolve an unexamined cell to `clean` to
clear the gate.

---

## Phase 4: Output

### Print this block to terminal, always

```
# PR Review: <title> (#<number>)

**Senior engineer approval**: <emoji> <Yes | No | With changes> — <one-sentence reason>
**Verdict**: <emoji> <approve | comment | request-changes>
**Goal**: <intent goal>
**Size**: <additions>/<deletions> across <N> files
**Reviewers**: <list — "(unavailable)" for a failed Phase 2 reviewer, "<verifier> unavailable — verified inline" for a failed Phase 3 verifier>
**Round**: <CURRENT_ROUND> (<active>/<resolved>/<dismissed> findings carried across rounds)
**Convergence**: <N> new · <C> caused by earlier fixes · <R> regressions reopened · <F> carried
<trend line — omit at round 1>
**Mode**: <mode line — omit when no mode applies>
**Coverage**: <cells_examined>/<cells_total> cells examined across <files_changed> files changed. <cells_cannot_assess> cannot be assessed without <artifact>. **<cells_not_examined> cells NOT examined — this review does not cover them.**
<when step 6.9 produced no ledger, this line reads instead: **Coverage**: none recorded — no ledger was produced this round, so this review states nothing about what it examined. Never omit the line and never render zeros; an absent ledger and a fully-covered one must not look alike.>
<coderabbit hint — one line, only on the first run against this repo in a session when `CR_CONFIG_PRESENT=false`; omit entirely otherwise>

## Summary
<2-3 sentence summary>

## Findings (<count>)
<each entry is the full per-finding block from references/finding-output-format.md,
 headed by its canonical id — C1 / S1 / M1 / m1. The same id labels this finding in the
 posted review, the ledger and the handoff file; without it the author cannot tell which
 terminal entry became which thread on the PR.

 Emit the field labels EXACTLY as that file writes them: bare, at the start of the line,
 one field per line, `Label: value`. Not `**Issue**:`, not `` `Rule-class:` ``, and never
 folded into a heading — a run that renders `Severity` and `Confidence` inside a bold
 header line has not emitted those fields at all.

 This is a terminal block, so prettifying it is the natural instinct and it is wrong here.
 The block is read by `/fix-pr-review` and by the replay harness, both of which match a
 bare label at line start; markdown emphasis makes every field invisible to them at once.
 Three consecutive live runs were lost this way — the review was excellent each time and
 no consumer could read a single finding. Readability is what the severity headings and
 the summary table are for; these entries are the machine-readable copy.

 `<count>` is every finding this round emits, `Follow-ups (non-blocking)` included — the
 severity ratchet moves findings between headings and changes no total. From round 3, omit
 a severity sub-heading whose findings all moved; an empty `### Moderate` reads as a tier
 that came back clean.>

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
 Omit this heading entirely at rounds 1-2, where they appear under their own severity.

 Shape: identical to `## Findings` above — the full per-finding block per entry, headed by
 its canonical id, labels bare and at line start. The ratchet moves these findings out of
 the blocking set, not out of the machine-readable one: `/fix-pr-review`, the replay
 harness and the follow-up-issue body composed further down this phase all read the
 per-finding block, so a compact table here — the natural rendering for a heading of
 non-blocking items, and the one this spec previously left open — deletes every entry
 under it from all three consumers at once while the heading still looks populated.>
<plus the one tracking line from "File the follow-up issue" — the issue URL, or the
 statement that nothing tracks these findings. It is appended once that step has run: the
 answer does not exist when this block is first rendered, and a heading that lists
 released findings without saying where they went is the promise this skill is not
 allowed to leave open. The line names the whole filed set, not only this heading's
 entries — the issue carries every finding still active at the cap.>

## Filtered out (<count>)
<one line per dropped finding, NOT the per-finding block:
 `<id or path:line> · <Severity> · <Issue, trimmed> — <the drop reason logged by the step
 that dropped it, verbatim>`. `<count>` is the number of lines.

 A one-line subset is declared here rather than the full block because nothing downstream
 acts on a dropped finding: the handoff file carries only survivors, the posted body
 excludes this section outright, and the single question a reader brings — did the critic
 over-filter — is answered by the severity, the sentence and the reason. Keep the reason
 wording the dropping step logged; rephrasing it breaks the match back to the rule that
 fired.>

## Multi-round status
<one line per finding in PRIOR_STATE, NOT the per-finding block:
 `<id> · <last entry in label_history> · <file> · <status> · round <round_resolved, or "—"
 while still active> — <dismissal_reason, dropped when null>`. Useful for "did I really
 ship M3 in round 5?" scanning, which is what the label buys over the id hash.

 A one-line subset is declared here because every entry is a prior round's finding in a
 closed state: `references/finding-state-schema.md` is their authority and the only thing
 that reads them, and any of them still active this round already printed in full above.>
```

### Verdict and approval emoji mapping

**Senior engineer approval**: Yes → ✅ · No → ❌ · With changes → ⚠️
**Verdict**: approve → ✅ · comment → 💬 · request-changes → ❌
**Severity headers**: the tier emoji fixed in `references/finding-output-format.md`.

Filtered out is mandatory in terminal output — it is the only way to see when the critic is over-filtering. Multi-round status is mandatory when `PRIOR_STATE.findings` is non-empty.

### Cascade check

Mandatory from round 2. PRINT the value Phase 3 step 7.5 computed — do not recompute it
here. Step 8 already read that same number for the verdict prefix, and a second
computation on a different finding set is how the two disagree.

`cascade_share` = (active findings with `caused_by` set) / (total active findings)

Emit exactly one trend sentence, picked from what the numbers say:
- `cascade_share > 0.5` → `Not converging — the fixes are generating the findings.`
- New findings falling round over round and `cascade_share == 0` → `Converging — tail is shrinking.`
- New count flat across 3+ rounds → `Stalled — same volume each round; scope may be growing.`

```
Convergence: 4 new · 3 caused by earlier fixes · 1 regression reopened · 2 carried
Trend: cascade_share 0.75 — Not converging — the fixes are generating the findings.
```

If a verdict REVERSES an earlier approval, say so explicitly in the Summary with the
reason and the two SHAs, e.g. *"I approved this at `dd142e0`. I'm reversing that,
because `e4f7432` made one thing worse than it was."*

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

### File the follow-up issue (round >= 3)

Fires when `CURRENT_ROUND >= 3` AND at least one finding is still active after the
ratchet. Skip entirely otherwise: at rounds 1–2 the review is not terminal, every finding
is still owed another round, and there is no backlog to file.

Scope is **every** still-active finding, per the round cap — round 3 is the last look, so
an unfixed Critical needs filing as much as a released Minor. The Moderate and Minor the
ratchet released are why the guarantee is load-bearing: they stopped blocking on the
stated promise that this step tracks them.

**It runs here — first interactive step of Phase 4, ahead of the self-review branch, the
findings multiSelect and the post decision.** Two structural reasons. The issue number has
to exist before `references/github-posting.md` Step 1 composes the body, because the body
links to it and Step 1 is the one assembly point. And every other exit from Phase 4 —
self-review "Fix now", "Keep local only", "Keep local", deselecting every finding — leaves
without posting; an offer placed after any of them is an offer those paths never reach,
and the ratchet's promise would die exactly where nobody is watching for it.

**Creating an issue is an outward-facing write on the user's account: it happens only on
an explicit choice, never as a side effect of reaching round 3.** In batch mode nobody is
there to ask — the offer becomes a pending decision under `references/batch-mode.md`'s
"don't stop" semantics, like every other checkpoint, and the subagent files nothing.

The findings the multiSelect later deselects are not retracted from an issue already
filed. Say so on the terminal line and move on: a dismissed item inside a filed backlog is
visible and can be closed, an item that was never filed cannot.

#### 1. Look for an issue this PR already has

Read `followup_issue` from `$STATE_FILE` (`references/finding-state-schema.md`). If the
state file was lost, fall back to the body marker — the same fallback
`github-posting.md` Step 0 uses when the cache is gone:

```bash
gh issue list --repo "<owner>/<repo>" --state all --limit 5 \
  --search 'in:body "review-pr:followup pr=<pr-number>"' --json number,url,body
```

If either route returns an issue whose markers already carry every still-active finding, do
not ask and do not file: render it exactly as step 6's `filed` row, re-recording `number`,
`url` and `finding_ids` if the marker search is what found it, and stop here. One PR gets
one backlog; the second copy is the one nobody reads. If the issue carries only some of
them, run steps 2–6 over the uncovered findings alone and **append them to that issue**
rather than open a second one — step 4 carries both shapes.

#### 2. Ask

AskUserQuestion:

```
header: "Follow-ups"
text: "Round <N> is the last review round. <K> finding(s) are still open, <R> of them released from blocking this PR by the ratchet. File all <K> as one follow-up issue on <owner>/<repo>?"
options:
  - "File the issue (Recommended)" — One issue carrying all <K> findings, linked from the review body
  - "Don't file" — Nothing is created; these findings are tracked nowhere after this run
```

#### 3. Compose the WHOLE body before anything is created

Write it to `/tmp/review-pr-<pr-number>-followups.md` in full, every still-active finding
in it, ranked Critical → Minor. Nothing is sent until the file is complete — this is
where "complete or not at all" is actually enforceable, because a body that turns out
short is still just a local file.

Title (conventional-commit style, matching this skill's commit vocabulary):

```
chore(review): follow-ups from PR #<pr-number> review
```

Body:

````markdown
<!-- review-pr:followup pr=<pr-number> round=<round> -->
Non-blocking findings from the round-<round> review of <pr-url>. The severity ratchet
released them from holding that PR; they are recorded here instead.

Head reviewed: `<head_sha>`

### <id> · <severity-emoji> <Severity> — `<path:line>`
<!-- review-pr:followup id=<finding-id-hash> rule-class=<slug> symbol=<enclosing-symbol> -->
<Category><confidence-suffix>

**<Issue one-sentence>**

**Why it matters**: <one sentence>

**Suggested fix**: <one sentence, actionable>

**Inverse risk**: <the failure mode the fix trades into, or "none — pure addition">

**Class-sites**: <A>/<N> — affected sites over the entries in the sweep's site list

<one `###` block per still-active finding>
````

**What the issue projects from the per-finding block.** This is a projection of
`references/finding-output-format.md`, declared here the way every other surface declares
its subset. It carries `Severity` (emoji + word), the run's canonical id, `File`,
`Category`, `Issue`, `Why it matters`, `Suggested fix`, `Inverse risk` and `Class-sites` —
enough that whoever picks the issue up months later does not have to re-derive the review.
`Confidence` renders as ` · <medium|low> confidence` on the category line and is omitted
at `high`, as on a posted comment: an unhedged backlog item reads as certain. `Rule-class`
and `Enclosing-symbol` ride in the HTML marker rather than as visible lines — a reader has
no use for either, but they are two of the three id components, so step 1's marker search
can recompute ids from the issue body when the state file is gone. `Lens` is dropped: it
names the question that found the defect, and a backlog reader is acting on the defect.

#### 4. Create — one call, whole body

```bash
FOLLOWUP_URL=$(gh issue create --repo "<owner>/<repo>" \
  --title "chore(review): follow-ups from PR #<pr-number> review" \
  --body-file "/tmp/review-pr-<pr-number>-followups.md")
FOLLOWUP_NUMBER="${FOLLOWUP_URL##*/}"
```

When step 1 found this PR's issue and only some findings are uncovered, the same composed
file goes on that issue as one comment instead — one backlog per PR, however many rounds
add to it:

```bash
gh issue comment "$FOLLOWUP_NUMBER" --repo "<owner>/<repo>" \
  --body-file "/tmp/review-pr-<pr-number>-followups.md"
```

Either shape is **one call carrying every finding it owes**. Never create or comment and
then add the rest in a further call: a second write that fails leaves precisely the
half-written backlog the cap forbids, and the PR is already unblocked by then.

A `gh issue create` that errors or prints nothing is **not** proof that nothing was
created. Re-run step 1's marker search before any retry; a blind second attempt is how a
PR ends up with two partial backlogs.

#### 5. Read the issue back and verify every finding is present

```bash
FOLLOWUP_BODY=$(gh issue view "$FOLLOWUP_NUMBER" --repo "<owner>/<repo>" \
  --json body,comments -q '[.body] + [.comments[].body] | join("\n")')
MISSING=""
for id in <the still-active findings' id hashes>; do
  printf '%s' "$FOLLOWUP_BODY" | grep -q "review-pr:followup id=$id" || MISSING="$MISSING $id"
done
```

Read comments as well as the body — an appended round lives in a comment, and a check that
reads the body alone reports every appended finding missing.

Verify against what GitHub returned, never against the local file. The local file is what
this run meant to send; the guarantee is about what landed. Truncation, a rejected body
and a partial write all look identical from the sending side.

#### 6. Record the outcome and render it — four cases, no fifth

| Outcome | `followup_issue.status` | Terminal line under `Follow-ups (non-blocking)` | Review-body `Follow-ups` line |
|---|---|---|---|
| Read-back found every id | `filed` + `number`, `url`, `round_filed`, `finding_ids` | `<K> finding(s) filed as <url>.` | the URL |
| Read-back found the issue short | `incomplete` + `number`, `url`, `finding_ids`, `missing_ids` | `<url> is missing <ids> — treat as NOT filed. Full body kept at /tmp/review-pr-<n>-followups.md.` | names the issue AND the missing ids |
| The create or the append errored | `failed`, `number`/`url` null unless an earlier round's issue exists, `finding_ids` = the still-active set | `Filing failed: <error>. <K> finding(s) are tracked nowhere. Body kept at /tmp/review-pr-<n>-followups.md.` | states they are tracked nowhere |
| User chose "Don't file" | `declined`, `number`/`url` null, `finding_ids` = the still-active set | `<K> finding(s) are tracked nowhere — not filed, and the ratchet has already released <R> of them from holding this PR.` | states they are tracked nowhere |

`finding_ids` accumulates — a round that appends adds its ids to the list rather than
replacing it, and `round_filed` keeps the round that opened the issue. Replacing either
would report the earlier rounds' findings as never filed.

`incomplete` is treated as not filed on purpose: a partial issue is the one case where the
PR unblocks AND the missing half leaves no trace, so it is reported louder than a plain
failure, not quieter. Do not close or delete the partial issue — say what is missing and
keep the composed body on disk so it can be pasted in by hand.

`declined`, `failed` and `incomplete` never claim a backlog exists. The wording is the
point: "tracked nowhere" is what the reader needs to act, and any softer phrasing
re-tells the exact lie this step was built to end.

Whatever the outcome, `followup_issue` is persisted by the Phase 4 state write-back on
every path, "Keep local" included — see "Phase 4 — write back" in
`references/finding-state-schema.md`. It is what stops round 4 filing a duplicate, and
what lets round 4 tell a declined backlog from a lost state file.

### Self-review detection

Before asking whether to post:

```bash
VIEWER=$(gh api user -q .login)
AUTHOR=$(gh pr view <url> --json author -q .author.login)
[ "$VIEWER" = "$AUTHOR" ] && SELF_REVIEW=true
```

**GitHub silently coerces `--request-changes` to `--comment` when reviewer is the PR author.**

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

   ID: S1
   Severity: Serious
   Confidence: high
   File: src/stream.ts:47
   Category: Silent-failure
   Rule-class: silent-failure
   Lens: L1
   Enclosing-symbol: handleStreamError
   Issue: Unhandled stream error can crash the process
   Why it matters: crash on communication failure with no handler
   Suggested fix: attach an error event handler
   Inverse risk: a handler that only logs turns a crash into a silent hang
   Class-sites: 2/3
   class_completeness:
     - finding: Unhandled stream error can crash the process
       rule_class: silent-failure
       signature: .on("error"
       search: Grep("createStream\(", "src/") → 3 sites
       sites:
         - src/stream.ts:47: affected — no error listener
         - src/pipe.ts:12: affected — no error listener
         - src/sink.ts:88: not-affected — listener attached at construction
       verdict: COMPLETE (all 3 sites reported)
   ```

   This file is the FULL per-finding block from `references/finding-output-format.md` —
   every field, plus the `class_completeness:` audit. No field is optional here.
   `/fix-pr-review` keys its "seed, don't re-derive" path on these labels; drop any and it
   re-derives from scratch, discarding what steps 4.55 and 4.56 already did. Two that were
   being dropped and should not be: `Confidence`, which is how the next skill orders its
   triage, and the `class_completeness:` audit — `Class-sites: 2/3` says how many sibling
   sites are affected but not WHICH, so without the audit the class sweep is redone in full.
2. Invoke `/fix-pr-review /tmp/review-pr-<num>-findings.md`.
3. Skip post-review prompts — `/fix-pr-review` handles its own workflow.

### Select findings to post (multiSelect)

The user picks what goes to GitHub — posting waits for an explicit "Post now" or "Edit first"
(self-review "Fix now" is the one path that proceeds without posting at all). Skip this step only if:
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
- Deselected findings: move to Filtered out with reason `user-deselected before posting`. They stay local, are excluded from the summary body's finding count, and are recorded in the state file as `dismissed` with `dismissal_reason: user-deselected` so later rounds leave them closed.
- If deselection removes every finding that drove the verdict, recompute the verdict (Phase 3 step 8) over the selected set before composing the summary body — **then re-run step 9.5 over the recomputed verdict.** This is a fourth route to an approval, and the only one that runs after the coverage gate. Deselecting findings changes which findings hold the PR; it does not change which cells were examined, so an emptied finding list must still not produce an `approve` while `cells_not_examined > 0`.
- If the user deselects everything, skip posting entirely — same outcome as "Keep local".

### Then ask

AskUserQuestion (cursor-selectable):

```
header: "Post review"
text: "Post this review to the PR? Verdict: <verdict>"
options:
  - "Post now" — Submit as <verdict> (posts a new review; earlier rounds' reviews are left untouched)
  - "Keep local" — Don't post; stays in terminal
  - "Edit first" — Open body in $EDITOR before posting
```

Every option here ends with the state-file write-back — "Keep local" included. Follow
"Phase 4 — write back" in `references/finding-state-schema.md`; it is what lets round N+1
know what round N settled.

### If yes — Post via references/github-posting.md

The full posting flow lives in `references/github-posting.md` — load it now. It handles:

- **Step 0**: detect prior `<!-- review-pr:run -->` tagged reviews on the PR — read-only, for the round number, the dedupe of findings that already have threads, and the count of rounds already posted. Every round creates a fresh review; a submitted body is never edited.
- **Step 0b**: verdict-body sync check — on re-runs with a `last_posted_review_id` in cache, warn when the previously-posted body verdict drifted from its GitHub state.
- **Step 0c**: re-review thread resolution — resolve threads for findings closed since the last round (either arm: state status or GitHub thread state), record the "Resolved since last review" line, and skip re-posting findings that already have threads.
- **Steps 1-2**: compose summary body (with marker comment) + per-finding review comments.
- **Step 3**: pre-posting hunk validation (line vs file-level routing).
- **Step 3b / 4**: drop findings that already carry a thread from an earlier round, then REST POST PENDING.
- **Step 5**: GraphQL `addPullRequestReviewThread` for file-level threads.
- **Step 6**: GraphQL `submitPullRequestReview`.
- **Step 6b**: assert the review re-reads as SUBMITTED with the full thread count; failure routes to Step 7 and blocks the state write-back.
- **Step 7**: failure recovery with disclosed partial state.
- **Step 8**: cache write-back + state file update + thread resolution for fixed findings.

Pass into the reference: `<owner>`, `<repo>`, `<pr-num>`, `<head_sha>`, `CURRENT_ROUND`, summary body content, list of findings (line-level + file-level), `PRIOR_STATE` (Step 0c compares against it), **the `ledger` object step 6.9 assembled**, **the `followup_issue` outcome the follow-up step resolved** (its Step 1 has a slot for it, and an outcome that never arrives renders as no line at all — which reads as rounds 1–2), `$CACHE_FILE` path, `$STATE_FILE` path.

The ledger goes in memory, not by reading `$STATE_FILE`: Step 8c has not written it when Step 1 composes the body. Read from disk instead, round 1 renders the seed's zeros — which display as full coverage on the least-covered run of all — and round N renders round N−1's counters underneath round N's verdict.

### If edit first

Write summary body to `/tmp/review-pr-<num>.md`, open in `${EDITOR:-vi}`, then post after editor closes. This flow edits the summary body only; to change or remove a review comment (line-level or file-level), edit the findings list before "Post now".

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

On "Re-review later": print `Run /review-pr <url> again after fixes` and exit — the author hasn't pushed yet, so the re-run belongs to a later session.

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
