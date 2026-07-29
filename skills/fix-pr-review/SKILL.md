---
name: fix-pr-review
description: Triage and fix review findings that already exist on a GitHub PR, then reply and resolve the threads. Use on a CodeRabbit review URL, a PR whose review comments still need working through, or a local /review-pr findings file. When the PR has no findings yet, /review-pr produces them first.
---

# /fix-pr-review — Triage, Fix, and Resolve PR Review Comments

Consumes a PR review (CodeRabbit, `/review-pr`, or pasted), triages each finding, applies approved fixes, runs `/done`, and replies + resolves conversations on GitHub — all in one flow.

**Use AskUserQuestion for ALL user-facing decisions** — branch safety, stash confirmation, contested-item confirmation, plan approval, per-fix confirmations, type-check failure triage, and post-completion next actions. Every option is a concrete, considered answer, strongest first and marked "(Recommended)".

## Quick Reference

### Phase Overview

| Phase | What | Key Output |
|-------|------|------------|
| 1 | Prereqs, input detection, branch safety, baseline type-check | `BASE_SHA`, `repo_map`, `baseline_errors` |
| 2 | Fetch review data from GitHub or local file | Unified `Comment[]` array |
| 3 | Triage subagent: classify each finding via R-rubric | Triage plan (FIX/DISMISS/DEFER/DISAGREE/NEEDS-INPUT) |
| 4 | Plan approval gate: validate + user confirmation | Approved plan |
| 5 | Execute fixes: sequential edits + per-file narrow type-check | Modified files, `fix_status` per item |
| 5.5 | Convergence subagent: class completeness, inverse risk, new siblings | Per-fix verdicts; missing sites applied |
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
| R6 | FIX — bug/security/perf/correctness/reusability | `fix_plan` ≥30 chars, `change_class`, `test_scenario`, `inverse_risk`, `class_completeness` (with `verdict`) |
| R7 | DEFER — valid but out of scope | Tracking reference |
| R8 | DISAGREE — legitimate technical disagreement | `disagree_rationale` |
| R9 | NEEDS-INPUT — ambiguous/needs user knowledge | `why_unclear` |

*R4/R5 sit above R3 by design, not by accident. The full rubric and the reason for that order live in `references/triage-rubric.md`.*

### Key Cross-References

- **R-rubric definition**: `references/triage-rubric.md` — loaded by the triage subagent at Phase 3 STEP 4, not by main
- **Plan validation rules**: Phase 4 (validates fields required by R-rubric)
- **Fix execution routing**: Phase 5 (executes R6 FIX items)
- **Convergence**: Phase 5.5 (consumes `class_completeness` + `inverse_risk` from the plan; feeds `fix_status` and the per-fix `convergence:` report line)
- **Reply validator**: `references/github-reply-resolve.md` Step 7b (format rules for GitHub replies)
- **Report grouping**: Phase 8 (groups by R-classification)
- **Suppressions**: Phase 3 "Load review suppressions" (main agent reads, before dispatch) + `references/triage-prompt.md` (subagent applies them before classifying) + Phase 8 (write)

### Reference files

Each is loaded at exactly one point in the run; the firing condition is repeated in the pointer at that point.

- `references/fetch-review-data.md` — per-input-type GraphQL/REST fetch, CodeRabbit review-body anatomy, `Comment` schema. Loaded by main in Phase 2.
- `references/triage-prompt.md` — the whole Phase 3 subagent prompt (STEP 0 → STEP 6 + output format). Read by main in Phase 3, placeholder-substituted, passed verbatim.
- `references/triage-rubric.md` — R1–R9 detail, NEEDS-INPUT calibration, `change_class` worked examples, reply formats. Loaded by the triage SUBAGENT at STEP 4.
- `references/github-reply-resolve.md` — Steps 7a–7d posting/resolving mechanics. Loaded by main in Phase 7; never loaded for local-file input.
- `references/final-report.md` — the Phase 8 report template and its rendering rules. Loaded by main in Phase 8 before printing.

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

## Who gets triaged

Every reviewer's comments go through the same triage — CodeRabbit, humans, and other bots alike. The "CodeRabbit" framing throughout reflects the most common use case.

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
2. `gh repo view --json nameWithOwner -q .nameWithOwner` — compare with URL's `owner/repo`. Mismatch → fail fast and tell the user to `cd` into the right clone; the fix is theirs to make, so leave cloning and directory changes to them.
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

### Pre-fix type-check baseline (what the narrow type-check compares against)

Run ONE baseline type-check before Phase 5, capture the set of files already failing:

```bash
bun turbo run check-types 2>&1 | tee /tmp/fix-pr-review-baseline-$$.log
```

Parse the output, build `baseline_errors[path] = <error count or error signatures>`. This is used in Phase 5 to distinguish **pre-existing** type errors from **fix-induced** ones. If type-check tooling is missing (no turbo, no tsc), skip the baseline and mark the narrow type-check as `skipped` for all fixes.

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

### Fetch from GitHub (PR URL / review URL / discussion URL)

Phase 1 detected exactly one of these three input types — load `references/fetch-review-data.md` now and run only that type's section. It holds the paginated GraphQL `reviewThreads` query and its `isResolved` filter, the `/pulls/<num>/reviews/<review_id>` and `/pulls/comments/<comment_id>` REST endpoints, the CodeRabbit review-body anatomy, and the parse for the `🤖 Prompt for all review comments with AI agents` block — the only place nitpicks appear, since they never get inline threads.

A fetch that errors — GraphQL rate limit, 404, private repo, or a per-page failure inside the pagination loop — surfaces the error and exits, so triage never runs on a partial comment set. For 404, print `Couldn't access PR — check repo access and run 'gh auth refresh -s repo'.`

### For local files (`./review.md`, `/tmp/review-pr-*-findings.md`, etc.)

Parse the `/review-pr` output format. Extract findings from the `## Findings` section, preserving `Severity / File / Category / Issue / Why it matters / Suggested fix` **plus `Rule-class` / `Enclosing-symbol` / `Inverse risk` / `Class-sites`** when present — `/review-pr` emits these per finding and dropping them forces this skill to re-derive work the reviewer already did.

**Seed, don't re-derive**: when `Inverse risk:` is present, seed STEP 5's `inverse_risk` from it and VERIFY it against the code (confirm the named failure mode is real and still applies) rather than deriving a new one from scratch. When `Class-sites: <H>/<N>` is present, seed STEP 1.5's `class_completeness` with those `N` sites and verify the count against your own search — re-run the search only to catch sites the reviewer missed, not to rebuild the list. `Rule-class` and `Enclosing-symbol` seed the class sweep's `signature`. If a seeded value contradicts what you read in the code, the code wins — record the discrepancy in the field.

**Severity mapping**: `/review-pr` uses `Critical | Serious | Moderate | Minor` while CodeRabbit uses `Critical | Major | Minor | Refactor | Nitpick`. Both are valid — normalize to the internal `Comment` schema which accepts either convention. Map for triage priority: `Critical` = highest, `Serious`/`Major` = high, `Moderate` = medium, `Minor`/`Refactor` = low, `Nitpick` = default-dismiss.

### Normalize to internal `Comment` list

Every input path ends here. The `Comment` schema — the exact field names Phases 3-8 read — is defined in `references/fetch-review-data.md`. Load that file now if you took the local-file path and have not read it yet.

### Short-circuit cases

- **Empty list** (all threads resolved, local file has no findings): print `Nothing to triage — no unresolved comments found.` → restore stash → exit 0.
- **Only nitpicks remain AND `--all-nitpicks` not set**: print `Only nitpicks found (N). Pass --all-nitpicks to triage them, or ignore.` → restore stash → exit 0.

---

## Phase 3: Triage subagent (`general-purpose`)

### Load review suppressions (main agent, before dispatch)

Before dispatching the subagent, load `.claude/review-suppressions.yml` from the project root (if it exists). In cross-repo mode, fetch via `gh api repos/<owner>/<repo>/contents/.claude/review-suppressions.yml?ref=<head-sha>`. If not found, set `SUPPRESSIONS = ""`.

Pass loaded suppressions into the subagent prompt as a `## Review suppressions` section (same approach as CLAUDE.md content, PR diff, and repo maps — main agent fetches, subagent receives as context).

### Dispatch

Dispatch **one** `general-purpose` subagent with `Read`, `Grep`, and `Bash` tools. The triage plan comes from this subagent alone — if it fails outright, abort the run and say so; classifying inline skips the grounding and class-sweep passes the whole plan is built on.

**Important**: The Bash allowlist (`git log/diff/blame/show/merge-base/rev-parse`, `grep`, `rg`) is a **prompt-level instruction** — Claude Code's Agent tool doesn't sandbox Bash per-command. The subagent is trusted not to run other commands, not mechanically prevented from doing so.

### Prompt template

The whole prompt is `references/triage-prompt.md` — read it now, substitute its `<...>` placeholders (`<SKILL_DIR>` = this skill's absolute directory, plus the Phase 1 context values, the `git diff <BASE_SHA>...HEAD` output, the repo maps, `SUPPRESSIONS`, and the Phase 2 `Comment[]` array), and pass the result to the subagent VERBATIM. It is the string the subagent runs, not instructions for you to follow, summarise, or restate inline.

Its STEP 4 sends the subagent to `references/triage-rubric.md` on its own — you do not read that file; the R-Rubric Summary table above is the main-agent view. What comes back is what Phase 4 validates: per FIX the prompt emits `fix_plan`, `change_class`, `test_scenario`, `inverse_risk:`, `class_completeness:` and `reusability_context:`.

---

## Phase 4: Plan approval gate (main)

*Validates against the R-rubric — summary table above, full detail in `references/triage-rubric.md`. Required fields per classification are defined there.*

### Plan validation (before display)

Before anything is shown to the user, mechanically validate the classifier's output:

- Every DISMISS with `rubric: R5` MUST have non-empty `claude_md_quote`.
- Every DISMISS with `rubric: R4` MUST have non-empty `prior_commit_sha`.
- Every DISAGREE MUST have non-empty `disagree_rationale` (and it MUST NOT be a pure style preference — check for keywords like "prefer", "cleaner", "nicer" without a concrete counter-argument).
- Every FIX MUST have `fix_plan` length >= 30 characters.
- Every FIX MUST have `change_class` set to exactly `hardening` or `logic-change` (the calibration the classifier applied is in `references/triage-rubric.md`; this check is purely the literal value).
- Every FIX MUST have non-empty `test_scenario`. For `change_class: hardening`, the value MUST be exactly `smoke test — happy path unchanged`. For `change_class: logic-change`, the value MUST be a 1-sentence concrete repro (not just "verify it works").
- Every FIX MUST have non-empty `inverse_risk` that either names a specific failure mode or is exactly `none — pure addition`. Hedges fail validation: an empty value, or anything of the shape "could have issues" / "minor risk" / "some risk" / "possible regression" / "none" on its own — a named failure mode says what breaks, where. Phase 5.5 consumes this field; an unnamed risk is unverifiable there.
- Every FIX MUST have a `class_completeness` block with a non-empty `verdict` starting with either `COMPLETE` or `INCOMPLETE`. `INCOMPLETE` MUST name the excluded sites and give a reason for each — an `INCOMPLETE` verdict with no per-site reason fails validation.
- Every item MUST have non-empty `grounding_a` and `grounding_b`.
- Every item — FIX, DISMISS, DEFER and DISAGREE alike — MUST carry a `reusability_context` field, even when it is just `{ flagged: false }`. Phase 7's reply validator branches on it, so a missing field silently disables the reusability gate on that reply.

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

### Contested-item confirmation (multiSelect)

Contested items are the ones that will post a reply and resolve a thread WITHOUT any code change: every DISMISS, DEFER, and DISAGREE. A wrong classification here silently closes a reviewer's conversation — confirm the triage before the approval prompt, and before Phase 5/7 can act on it.

Skip this step if there are zero contested items. Otherwise, use AskUserQuestion:

   Question:
     header: "Triage"
     text: "<C> item(s) will get a reply + thread resolution with no code change. Select any to RECLASSIFY — unselected items proceed as planned."
     options: [one option per DISMISS/DEFER/DISAGREE item: "[<id>] <file:line> — <classification> (<rubric>): <reason, first ~60 chars>"]
     multiSelect: true

If contested items exceed the option limit, split into multiple multiSelect questions — DISMISS first (the most costly to get wrong).

For each selected item, use a follow-up AskUserQuestion:

   Question:
     header: "Item <id>"
     text: "<file:line> — currently <classification>: <reason>. Reclassify as?"
     options:
       - label: "FIX (Recommended)"
         description: "Treat as a real issue — add to the FIX list with a fix plan"
       - label: "NEEDS-INPUT"
         description: "Park it — no reply, no resolution; surfaces in the final report"
       - label: "Keep as-is"
         description: "Selected by mistake — keep the original classification"

On "FIX": re-dispatch the classifier scoped to just this item to produce the full FIX field set — `fix_plan`, `change_class`, `test_scenario`, `inverse_risk`, and `class_completeness` (class sweep included; a reclassified item has never been swept) — then re-run plan validation on the changed item. Producing a partial field set here fails validation and burns the single retry. On "NEEDS-INPUT": move to NEEDS-INPUT with `why_unclear: "user contested the <classification> classification"`. On "Keep as-is": no change. On "Other": treat the freeform text as the reclassification instruction.

Nothing is posted or resolved during this step — Phase 7 remains the only place GitHub is touched, and it acts **only** on items that survived this confirmation. Resolving a thread is irreversible noise in the reviewer's conversation: a DISMISS, DEFER, or DISAGREE that skipped this gate stays open and unanswered until it has been through it.

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

*Executes R6 FIX items from the approved plan (see the R-Rubric Summary table for R6 criteria, Phase 4 for approval gate).*

### Dependency resolution

Build an execution order from `dependencies:` fields with a simple topological sort. On a **cycle** (A→B→A): abort with `Cyclic fix dependencies detected — edit the plan (rerun with 'e') to resolve.` Restore stash. Exit non-zero.

### Pre-edit snapshots (revert mechanism — Edit tool has no undo)

Before the first `Edit` touches any file in Phase 5, `Read` its full contents and cache them:

```
preedit_snapshot[path] = <full file content from Read>
```

Revert a single file = `Write(path, preedit_snapshot[path])`. Revert-all = iterate over every snapshotted path and Write back. Within Phase 5 that snapshot is an *exact* revert — one fix at a time, nothing else applied yet — so every `Edit` here runs against a file that was cached first.

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
4. **Narrow type-check (this file only)**:
   - Detect project type: if `turbo.json` exists → turborepo mode; else if `tsconfig.json` exists → plain TS mode; else → skip the check.
   - Turborepo: route through `turbo run` — `bun turbo run check-types --filter=<package>` (or `pnpm turbo run check-types --filter=<package>` if the repo uses pnpm), targeting the workspace package containing the edited file. The `turbo run` form is what carries `--filter` through; `bun` alone drops unknown flags instead of forwarding them to the underlying script.
   - Plain TS: `bunx tsc --noEmit` or `npx tsc --noEmit`.
   - No TS tooling: skip the check with a one-line note, and let `/done` in Phase 6 catch what it would have caught.
5. **Compare against Phase 1 baseline**: the narrow type-check is **failed ONLY if the error set on the edited file is a strict superset** of the baseline set for that file. Classifications:
   - **pass** — no errors on this file, or same error count as baseline.
   - **inconclusive — preexisting errors** — baseline already had errors on this file; we can't cleanly tell whether the fix added more. Continue.
   - **failed** — strict superset of baseline errors on this file (genuinely new errors).
6. On **pass** or **inconclusive**: mark `[<idx>] ✓ fixed` / `[<idx>] ~ inconclusive`, continue.
7. On **failed**:

   Print the error output (trimmed to ~30 lines), then use AskUserQuestion:

   Question:
     header: "Type-check"
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
                | reverted_inverse_risk | partial
```

`reverted_inverse_risk` and `partial` are written by Phase 5.5, not Phase 5. This feeds the final report in Phase 8.

---

## Phase 5.5: Convergence (subagent)

Run after all fixes are applied, BEFORE the `/done` pipeline. A run converges when every
fix is class-complete, carries no inverse risk, and spawned no new siblings; anything
short of that is what the next review round will find.

Dispatch ONE `general-purpose` subagent. It gets `git diff HEAD` plus, per fix, the
`class_completeness` site list and the `inverse_risk` string. It fetches whatever else it
needs. Keep it in a subagent: it re-reads files and greps the repo, and main only needs
verdicts.

```
For each fix below, verify against the working tree — not against the fix plan's claims.

1. CLASS COMPLETENESS — every site the class sweep marked `affected` in
   `class_completeness.sites` must actually be changed. A fix that landed on 3 of 4
   sites is INCOMPLETE, not done.
   (Sites the plan's `verdict` deliberately excluded are not counted as unfixed.)
2. INVERSE RISK — the named failure mode must NOT be present in the applied code.
3. NEW SIBLINGS — did the fix itself introduce a new instance of the pattern it fixes,
   or a new branch (error state, empty state, early return) that its siblings have but
   this one lacks?

Report per fix, nothing else:
  fix: <idx>
  class_complete: yes | no — <unfixed site if no>
  inverse_risk_present: no | yes — <file:line + one sentence>
  new_siblings: none | <file:line + one sentence>

Evidence rules differ per check — "I lack evidence" is not an answer for check 1:
  - Check 1 is decided MECHANICALLY by `git diff HEAD`. Each affected site either
    appears in the diff or it does not; there is no undecidable state. Report `no`
    with the unfixed site whenever a site is absent from the diff.
  - Checks 2 and 3 default to `no` / `none` unless you can cite a concrete file:line
    in the applied code. Do not speculate, do not re-review the PR, do not report
    style issues.
```

Handling:
- `class_complete: no` → apply the missing sites now, then re-verify ONCE. If the second
  pass still reports `no`, stop: mark `fix_status[idx] = partial`, record the still-unfixed
  sites, and surface them in Phase 8. Do not loop a third time — like the narrow
  type-check retry (max 2) and the self-heal loop (max 2), this loop is capped.
- `inverse_risk_present: yes` → the suggestion was wrong; applying it anyway ships a worse
  defect. Revert it — but **not** via `preedit_snapshot[path]` by default. Phase 5.5 runs
  after ALL fixes, and `preedit_snapshot[path]` holds the file's PRE-PHASE-5 content, so
  writing it back also erases every other fix that touched that file. Revert in this order:
    1. **Invert this fix's own hunks.** Take `git diff HEAD -- <file>`, isolate the hunks
       belonging to THIS fix (Phase 5 applied fixes one at a time, so the hunks are
       attributable), and apply their inverse. This is the default path.
    2. **Pre-edit snapshot** — only when no other fix touched any of this fix's files.
       Check the other FIX items' file lists before using it.
    3. **Neither is clean** → do NOT revert. Leave the working tree as-is, mark
       `fix_status[idx] = reverted_inverse_risk` with a `revert: not attempted` note,
       route the item to NEEDS-INPUT, and say plainly in the Phase 8 report that the
       risky fix is STILL APPLIED and why it could not be safely undone.
  On a successful revert (1 or 2), mark `fix_status[idx] = reverted_inverse_risk` and route
  to NEEDS-INPUT.
- `new_siblings` → treat as part of the same fix and handle it now.

Record the outcome per fix as `convergence[idx]`; Phase 8 renders it, plus one converged /
not-converged verdict for the run. If the subagent fails, run the three checks inline and
note `convergence checked inline`.

---

## Phase 6: /done pipeline (main)

After all fixes are applied, run the standard `/done` sequence on the pending fix diff (`git diff HEAD`):

1. `/fix-ts-errors` — loop until clean (catches the cross-file errors a per-file narrow check cannot see).
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

If `done_remaining` is non-empty after 2 iterations, record it for the final report and continue to Phase 7 — the user sees the remaining issues in Phase 8 and decides there.

**Moderate/Minor findings** are recorded in `done_remaining` without self-heal — user decides at commit time.

---

## Phase 7: Reply + resolve on GitHub (main)

*Reply format rules live in `references/github-reply-resolve.md` and are referenced by Phase 4 validation. This skill does NOT read or write `/review-pr`'s cache (`~/.claude/skills/review-pr/cache/`). Thread resolution happens on GitHub — `/review-pr`'s re-review picks up resolved threads via its GraphQL prior-review timeline fetch.*

Replying and resolving threads is this phase's entire GitHub footprint. The review's own `CHANGES_REQUESTED` state stays exactly as CodeRabbit left it — CodeRabbit clears it itself on its next auto-re-review, once the user pushes.

**Skip this entire phase if the input was `./review.md`** or any local file — there are no GitHub threads to operate on. Phase 8 still produces the local final report.

### Posting mechanics

Load `references/github-reply-resolve.md` now — it holds Step 7a (regenerate every FIX reply from the actual post-fix diff, never the Phase 3 `reply_placeholder`, and which `fix_status` values are barred from replying at all), Step 7b (the mechanical reply validator: forbidden prefixes, 40-char floor, must-contain patterns, and the `reusability_context`-gated rule), Step 7c (the `addPullRequestReviewThreadReply` + `resolveReviewThread` GraphQL calls), and Step 7d (promoted nitpicks have no thread to close).

### Per-item status tracking

```
gh_status[idx] = {
  reply_ok:    true | false | skipped,
  reply_err:   <error message if any>,
  resolve_ok:  true | false | skipped,
  resolve_err: <error message if any>
}
```

**Work through every item to the end of the batch.** An individual reply or resolve that fails is recorded in `gh_status[idx]` and the loop moves on; the failures surface together at the TOP of the final report.

---

## Phase 8: Finalize (main)

*Report groups by R-classification (see the R-Rubric Summary table). Includes suppressions write (learning loop).*

### 1. Restore WIP

If `STASH_PUSHED=true`:

```bash
git stash pop
```

On stash pop conflict: leave every conflict marker exactly as `git stash pop` left it — resolving the user's WIP is the user's call. The working tree will now contain:
- Phase 5 fixes (applied, uncommitted)
- Conflict markers from the popped stash
- Untracked files from the stash

Record `stash_restored: conflict` in the final report and print explicit guidance to the user.

### 2. Print the final report

Load `references/final-report.md` now and render the report from it. It holds the failure-first ordering, the full body template, and the rendering rules that decide which of the three fix subsections each `[F<n>]` lands in and how the `Test:` line is emitted.

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

Committing happens only on an explicit "Commit changes" or "Push to remote" choice in the post-completion prompt above. Otherwise leave the working tree as it stands — the report's suggested commit message is the hand-off.
