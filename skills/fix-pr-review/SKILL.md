---
name: fix-pr-review
description: Triage and fix review findings that already exist on a GitHub PR, then reply and resolve the threads. Use on a CodeRabbit review URL, a PR whose review comments still need working through, or a local /review-pr findings file. When the PR has no findings yet, /review-pr produces them first.
---

# /fix-pr-review: Triage, Fix, and Resolve PR Review Comments

Consumes a PR review (CodeRabbit, `/review-pr`, or pasted), triages each finding, applies validated fixes, runs `/done`, and replies + resolves conversations on GitHub, all in one flow.

**Use AskUserQuestion only when the run still needs a user decision**: branch safety, stash confirmation, contested-item confirmation, `--interactive` per-fix confirmations, type-check failure triage, and post-completion next actions. Invoking `/fix-pr-review` or imperatively asking to fix review findings authorizes execution of the validated FIX plan; do not ask for separate plan approval. Every required option is a concrete, considered answer, strongest first and marked "(Recommended)".

## Quick Reference

### Phase Overview

| Phase | What | Key Output |
|-------|------|------------|
| 1 | Prereqs, input detection, branch safety, baseline type-check | `BASE_SHA`, `repo_map`, `baseline_errors` |
| 2 | Fetch review data from GitHub or local file | Unified `Comment[]` array |
| 3 | Triage subagent: classify each finding via R-rubric | Triage plan (FIX/DISMISS/DEFER/DISAGREE/NEEDS-INPUT) |
| 4 | Plan execution gate: validate + honor invocation intent | Executable plan |
| 5 | Execute fixes: sequential edits + per-file narrow type-check | Modified files, `fix_status` per item |
| 5.5 | Convergence subagent: class completeness, inverse risk, new siblings | Per-fix verdicts; missing sites applied |
| 6 | `/done` acceptance verification scoped to the fix diff, no commit or publish handoff | Verified fix diff, `done_verified_snapshot` |
| 7 | Reply + resolve on GitHub (skipped for local files) | Threads resolved |
| 8 | Finalize: settle NEEDS-INPUT, restore stash, report, suppressions write, next actions | Final report |

### R-Rubric Summary (Phase 3 STEP 4; first match wins)

| Rule | Classification | Requires |
|------|---------------|----------|
| R1 | DISMISS: self-contradictory/wrong | — |
| R2 | DISMISS: hallucinated file:line | Dead-link re-anchor failed |
| R4 | DISMISS: already fixed | `prior_commit_sha` |
| R5 | DISMISS: contradicts CLAUDE.md | `claude_md_quote` |
| R3 | DISMISS: pure style/naming | Not reusability-flagged |
| R6 | FIX: bug/security/perf/correctness/reusability | `fix_plan` ≥30 chars, `change_class`, `test_scenario`, `inverse_risk`, `class_completeness` (with `verdict`) |
| R7 | DEFER: valid but out of scope | Tracking reference |
| R8 | DISAGREE: legitimate technical disagreement | `disagree_rationale` |
| R9 | NEEDS-INPUT: ambiguous/needs user knowledge | `why_unclear` |

*R4/R5 sit above R3 by design, not by accident. The full rubric and the reason for that order live in `references/triage-rubric.md`.*

### Key Cross-References

- **R-rubric definition**: `references/triage-rubric.md`, loaded by the triage subagent at Phase 3 STEP 4, not by main
- **Plan validation rules**: Phase 4 (validates fields required by R-rubric)
- **Fix execution routing**: Phase 5 (executes R6 FIX items)
- **Convergence**: Phase 5.5 (consumes `class_completeness` + `inverse_risk` from the plan; feeds `fix_status` and the per-fix `convergence:` report line)
- **Reply validator**: `references/github-reply-resolve.md` Step 7b (format rules for GitHub replies)
- **Report grouping**: Phase 8 (groups by R-classification)
- **Suppressions**: Phase 3 "Load review suppressions" (main agent reads, before dispatch) + `references/triage-prompt.md` (subagent applies them before classifying) + Phase 8 (write)

### Reference files

Each carries its firing condition in the pointer at the point of use; load it there, not up front.

- `references/fetch-review-data.md`: per-input-type GraphQL/REST fetch, CodeRabbit review-body anatomy, `Comment` schema. Loaded by main in Phase 2, at the GitHub fetch step, and again at the `Comment`-schema normalisation step if the local-file path meant it was not read there.
- `references/triage-prompt.md`: the whole Phase 3 subagent prompt (STEP 0 → STEP 6 + output format). Read by main in Phase 3, placeholder-substituted, passed verbatim.
- `references/triage-rubric.md`: R1–R9 detail, NEEDS-INPUT calibration, `change_class` worked examples, reply formats. Loaded by the triage SUBAGENT at STEP 4.
- `references/github-reply-resolve.md`: Steps 7a–7d posting/resolving mechanics. Loaded by main in Phase 7; never loaded for local-file input.
- `references/final-report.md`: the Phase 8 report template and its rendering rules. Loaded by main in Phase 8 before printing.

One reference is not bundled here: `${CLAUDE_SKILL_DIR}/../review-pr/references/repo-map.md` holds the `repo_map_files` / `repo_map_exports` shell, the one copy this skill shares with `/review-pr` and `/harden-plan`. Loaded by main in Phase 1 when `packages/` or `apps/` exists.

## Usage

```
/fix-pr-review https://github.com/owner/repo/pull/123
/fix-pr-review https://github.com/owner/repo/pull/123#pullrequestreview-4089716169
/fix-pr-review https://github.com/owner/repo/pull/123#discussion_r3064352825
/fix-pr-review ./review.md            # local output from /review-pr
/fix-pr-review /tmp/review-pr-123-findings.md  # local review export
/fix-pr-review                         # no arg → ask user to paste
```

Optional flags:

- `--dry-run`: stop after plan display, don't execute
- `--interactive`: ask before applying each FIX item
- `--all-nitpicks`: full-triage nitpicks instead of default-dismiss

## Who gets triaged

Every reviewer's comments go through the same triage: CodeRabbit, humans, and other bots alike. The "CodeRabbit" framing throughout reflects the most common use case.

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

### Record execution authorization

Set `EXECUTION_AUTHORIZED=true` when the original request explicitly invokes `/fix-pr-review` or imperatively asks to fix, address, apply, handle, or resolve review findings. A bare URL or a read-only request to inspect, explain, review, or triage sets it to `false`. Preserve the matching request text as `execution_authorization_evidence`; Phase 4 may replace it with an explicit execution choice, and Phase 7 passes the final evidence to `preflight-mutations`.

### Ensure correct repo + branch (GitHub inputs only)

1. Parse `owner`, `repo`, `num` from the URL.
2. `gh repo view --json nameWithOwner -q .nameWithOwner`: compare with URL's `owner/repo`. Mismatch → fail fast and tell the user to `cd` into the right clone; the fix is theirs to make, so leave cloning and directory changes to them.
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

Define one parser for the whole run. For each diagnostic, key its file and build the identity `<diagnostic code> + <normalized message>` after removing file position, line, and column data; retain duplicate identities as a multiset. Parse the Phase 1 output into `baseline_errors[path]` with this parser. Phase 5 and every Phase 8 baseline path must use the same parser and identity normalization. If type-check tooling is missing (no turbo, no tsc), skip the baseline and mark the narrow type-check as `skipped` for all fixes.

### Compute shared-package repo map (for reusability-aware classification)

Inventory shared packages AND apps so the Phase 3 classifier can cross-check comments about reuse/extraction against what already exists. Scan BOTH `packages/` and `apps/`. Cross-app helper duplication (e.g., `apps/backend/src/modules/v1/feature-a/helpers.ts` vs `feature-b/helpers.ts`) is common in NestJS-style monorepos and is invisible to a packages-only scan.

Load `${CLAUDE_SKILL_DIR}/../review-pr/references/repo-map.md` and run its **Local mode** block, the one copy of this shell, shared with `/review-pr` and `/harden-plan`. It carries the `bash -c` wrapping the globs need to survive zsh, and caps each half at 500 lines with the truncation marked. Load it when `packages/` or `apps/` exists; when neither does there is nothing to run and the fallback below applies.

Stash both outputs as `repo_map_files` and `repo_map_exports` for the Phase 3 subagent prompt. If neither `packages/` nor `apps/` exists (non-monorepo), set both to `N/A (not a monorepo)` and flag `IS_MONOREPO=false`. The classifier prompt uses this to reroute greps to `src/` and the repo root.

---

## Phase 2: Fetch review data (main)

### Dual-path input for /review-pr findings

`/review-pr` now posts findings as **individual inline comments** (one per finding, each on a specific code line). These create standard `PullRequestReviewThread`s on GitHub, identical to CodeRabbit threads. The existing GraphQL fetch below handles them with zero special parsing.

Manually exported or legacy `/review-pr` findings files use the existing local-file path. Phase 7 skips GitHub operations for those inputs.

### Fetch from GitHub (PR URL / review URL / discussion URL)

Phase 1 detected exactly one of these three input types. Load `${CLAUDE_SKILL_DIR}/references/fetch-review-data.md` now and run only that type's section. It holds the paginated GraphQL `reviewThreads` query and its `isResolved` filter, the `/pulls/<num>/reviews/<review_id>` and `/pulls/comments/<comment_id>` REST endpoints, the CodeRabbit review-body anatomy, and the parse for the `🤖 Prompt for all review comments with AI agents` block, the only place nitpicks appear, since they never get inline threads.

A fetch that errors — GraphQL rate limit, 404, private repo, or a per-page failure inside the pagination loop — surfaces the error and exits, so triage never runs on a partial comment set. For 404, print `Couldn't access PR — check repo access and run 'gh auth refresh -s repo'.`

### For local files (`./review.md`, `/tmp/review-pr-*-findings.md`, etc.)

Parse the `/review-pr` output format. Extract findings from the `## Findings` section, preserving `Severity / File / Category / Issue / Why it matters / Suggested fix` **plus `Rule-class` / `Enclosing-symbol` / `Inverse risk` / `Class-sites`** when present. `/review-pr` emits these per finding and dropping them forces this skill to re-derive work the reviewer already did.

**Seed, don't re-derive**: when `Inverse risk:` is present, seed STEP 5's `inverse_risk` from it and VERIFY it against the code (confirm the named failure mode is real and still applies) rather than deriving a new one from scratch. When `Class-sites: <A>/<N>` is present, seed STEP 1.5's `class_completeness` with those `N` sites and verify the count against your own search. Re-run the search only to catch sites the reviewer missed, not to rebuild the list. `Rule-class` and `Enclosing-symbol` seed the class sweep's `signature`. If a seeded value contradicts what you read in the code, the code wins. Record the discrepancy in the field.

**Severity mapping**: `/review-pr` uses `Critical | Serious | Moderate | Minor` while CodeRabbit uses `Critical | Major | Minor | Refactor | Nitpick`. Both are valid. Normalize to the internal `Comment` schema which accepts either convention. Map for triage priority: `Critical` = highest, `Serious`/`Major` = high, `Moderate` = medium, `Minor`/`Refactor` = low, `Nitpick` = default-dismiss.

### Normalize to internal `Comment` list

Every input path ends here. The `Comment` schema, the exact field names Phases 3-8 read, is defined in `references/fetch-review-data.md`. Load that file now if you took the local-file path and have not read it yet.

### Short-circuit cases

- **Empty list** (all threads resolved, local file has no findings): print `Nothing to triage — no unresolved comments found.` → restore stash → exit 0.
- **Only nitpicks remain AND `--all-nitpicks` not set**: print `Only nitpicks found (N). Pass --all-nitpicks to triage them, or ignore.` → restore stash → exit 0.

---

## Phase 3: Triage subagent (`general-purpose`)

### Load review suppressions (main agent, before dispatch)

Before dispatching the subagent, load `.claude/review-suppressions.yml` from the project root (if it exists). In cross-repo mode, fetch via `gh api repos/<owner>/<repo>/contents/.claude/review-suppressions.yml?ref=<head-sha>`. If not found, set `SUPPRESSIONS = ""`.

Pass loaded suppressions into the subagent prompt as a `## Review suppressions` section (same approach as CLAUDE.md content, PR diff, and repo maps; main agent fetches, subagent receives as context).

### Dispatch

Dispatch **one** `general-purpose` subagent with `Read`, `Grep`, and `Bash` tools. The triage plan comes from this subagent alone. If it fails outright, abort the run and say so; classifying inline skips the grounding and class-sweep passes the whole plan is built on.

**Important**: The Bash allowlist (`git log/diff/blame/show/merge-base/rev-parse`, `grep`, `rg`) is a **prompt-level instruction**. Claude Code's Agent tool doesn't sandbox Bash per-command. The subagent is trusted not to run other commands, not mechanically prevented from doing so.

### Prompt template

The whole prompt is `references/triage-prompt.md`. Read it now, substitute its `<...>` placeholders (`<SKILL_DIR>` = this skill's absolute directory, plus the Phase 1 context values, the `git diff <BASE_SHA>...HEAD` output, the repo maps, `SUPPRESSIONS`, and the Phase 2 `Comment[]` array), and pass the result to the subagent VERBATIM. It is the string the subagent runs, not instructions for you to follow, summarise, or restate inline.

Its STEP 4 sends the subagent to `references/triage-rubric.md` on its own. You do not read that file; the R-Rubric Summary table above is the main-agent view. What comes back is what Phase 4 validates: per FIX the prompt emits `fix_plan`, `change_class`, `test_scenario`, `inverse_risk:` and `class_completeness:`; `reusability_context:` rides on every item, not just FIX.

---

## Phase 4: Plan execution gate (main)

*Validates against the R-rubric: summary table above, full detail in `references/triage-rubric.md`. Required fields per classification are defined there.*

### Plan validation (before display)

Before anything is shown to the user, mechanically validate the classifier's output:

- Every DISMISS with `rubric: R5` MUST have non-empty `claude_md_quote`.
- Every DISMISS with `rubric: R4` MUST have non-empty `prior_commit_sha`.
- Every DISAGREE MUST have non-empty `disagree_rationale` (and it MUST NOT be a pure style preference; check for keywords like "prefer", "cleaner", "nicer" without a concrete counter-argument).
- Every FIX MUST have `fix_plan` length >= 30 characters.
- Every FIX MUST have `change_class` set to exactly `hardening` or `logic-change` (the calibration the classifier applied is in `references/triage-rubric.md`; this check is purely the literal value).
- Every FIX MUST have non-empty `test_scenario`. For `change_class: hardening`, the value MUST be exactly `smoke test — happy path unchanged`. For `change_class: logic-change`, the value MUST be a 1-sentence concrete repro (not just "verify it works").
- Every FIX MUST have non-empty `inverse_risk` that either names a specific failure mode or is exactly `none — pure addition`. Hedges fail validation: an empty value, or anything of the shape "could have issues" / "minor risk" / "some risk" / "possible regression" / "none" on its own. A named failure mode says what breaks, where. Phase 5.5 consumes this field; an unnamed risk is unverifiable there.
- Every FIX MUST have a `class_completeness` block with a non-empty `verdict` starting with either `COMPLETE` or `INCOMPLETE`. `INCOMPLETE` MUST name the excluded sites and give a reason for each. An `INCOMPLETE` verdict with no per-site reason fails validation.
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
       If this rule has a legitimate exception in this case, select D<n>
       in the contested-item confirmation to change it to FIX or NEEDS-INPUT.
```

### Contested-item confirmation (multiSelect)

Contested items are the ones that will post a reply and resolve a thread WITHOUT any code change: every DISMISS, DEFER, and DISAGREE. A wrong classification here silently closes a reviewer's conversation. Confirm the triage before Phase 5/7 can act on it.

Skip this step if there are zero contested items. Otherwise, use AskUserQuestion:

   Question:
     header: "Triage"
     text: "<C> item(s) will get a reply + thread resolution with no code change. Select any to RECLASSIFY — unselected items proceed as planned."
     options: [one option per DISMISS/DEFER/DISAGREE item: "[<id>] <file:line> — <classification> (<rubric>): <reason, first ~60 chars>"]
     multiSelect: true

If contested items exceed the option limit, split into multiple multiSelect questions. DISMISS first (the most costly to get wrong).

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

On "FIX": re-dispatch the classifier scoped to just this item to produce the full FIX field set — `fix_plan`, `change_class`, `test_scenario`, `inverse_risk`, `class_completeness` (class sweep included; a reclassified item has never been swept), and `reusability_context` (carry the contested item's own value through unless the sweep changed it) — then re-run plan validation on the changed item. Producing a partial field set here fails validation and burns the single retry. On "NEEDS-INPUT": move to NEEDS-INPUT with `why_unclear: "user contested the <classification> classification"`. On "Keep as-is": no change. On "Other": treat the freeform text as the reclassification instruction.

Nothing is posted or resolved during this step. Phase 7 remains the only place GitHub is touched, and it acts **only** on items that survived this confirmation. Resolving a thread is irreversible noise in the reviewer's conversation: a DISMISS, DEFER, or DISAGREE that skipped this gate stays open and unanswered until it has been through it.

### Execution

If `--dry-run`: print the plan, print `dry run — not executing`, restore stash, exit 0.

If `EXECUTION_AUTHORIZED=true`, proceed directly to Phase 5. The invocation already authorizes execution of every validated FIX item. If `--interactive` was set, ask for per-item confirmation in Phase 5; it does not add a plan-level confirmation.

Otherwise, use AskUserQuestion:

   Question:
     header: "Execute"
     text: "The request did not explicitly authorize edits. Execute the validated plan? <F> fixes, <D> dismissals, <E> deferrals, <G> disagrees, <I> needs-input."
     options:
       - label: "Execute plan (Recommended)"
         description: "Apply all FIX items in dependency order"
       - label: "Cancel"
         description: "Leave the worktree unchanged and restore any stash"

On "Execute plan": set `EXECUTION_AUTHORIZED=true`, record the choice as `execution_authorization_evidence`, and proceed to Phase 5. On "Cancel": restore the stash if present, print `cancelled`, and exit 0.

---

## Phase 5: Execute fixes (main, sequential)

*Executes R6 FIX items from the validated plan (see the R-Rubric Summary table for R6 criteria and Phase 4 for validation).*

### Dependency resolution

Build an execution order from `dependencies:` fields with a simple topological sort. On a **cycle** (A→B→A): abort with `Cyclic fix dependencies detected — correct the dependency fields and rerun /fix-pr-review <original-input>.` Restore stash. Exit non-zero.

### Pre-edit snapshots (revert mechanism; Edit tool has no undo)

Bind Phase 5's state source before the first edit:

| Context | `active_snapshot` | `active_baseline_errors` | Abort scope |
|---------|-------------------|--------------------------|-------------|
| Ordinary Phase 5 | `perfix_snapshot[idx]` | Phase 1 `baseline_errors` | Current fix |
| Phase 8 item `<idx>` | `phase8_item_snapshot[idx]` | `phase8_item_baseline_errors[idx]` | Current item only |

In ordinary Phase 5, before the first `Edit` touches a file anywhere in the run, cache its full contents or authoritative absence in the run-level abort snapshot:

```
preedit_snapshot[path] = <full file content from Read>
```

Immediately before each ordinary fix, capture every declared path's then-current content or authoritative absence in `perfix_snapshot[idx]`; it includes all earlier landed fixes and becomes `active_snapshot` for Retry and Skip. After that fix's final successful attempt and before any later edit, derive its exact binary-safe forward patch, including additions and deletions, from `perfix_snapshot[idx]` to the current declared paths. Freeze that patch in `perfix_forward_patch[idx]`, freeze the exact current content or authoritative absence in `perfix_postimage[idx]`, and initialize `perfix_owned_components[idx]` with that patch and postimage. Never derive fix ownership later from the aggregate working-tree diff. `preedit_snapshot` is used only by Abort-all. In Phase 8 context, `active_snapshot` must already contain every declared path and no nested branch may read from or write to either ordinary snapshot. Restoring from an active snapshot writes back recorded content and removes paths recorded as authoritatively absent. Abort-all alone restores every run-level `preedit_snapshot` entry; a Phase 8 item restores only `phase8_item_files[idx]`, preserving earlier landed fixes.

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

   On "Apply fix": continue with steps 2-7. In ordinary Phase 5, "Skip" marks `fix_status[idx] = skipped` and advances to the next fix; "Skip remaining" marks every remaining fix `skipped` and jumps to Phase 6. In Phase 8 context, "Skip" restores every declared path from `active_snapshot` through the state-preserving restore rule with fallback `skipped`, sets `needs_input_status[idx]=skipped` and `convergence[idx]=not-run — user skipped before edit`, then sets paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `no landed fix — user skipped before edit` otherwise. Phase 8 "Skip remaining" performs that same restore and settlement for the current item; it marks each not-yet-run fix skipped unless its current status is `inverse_risk_applied`, which remains unchanged with its publication blocker. Earlier landed fixes remain untouched. Both choices clear `phase8_triage_context`, terminate the nested Phase 5 path immediately, bypass Phases 5.5–6, and rejoin Phase 8 at the next independent item. On "Other": treat as freeform instruction (e.g., "modify the fix plan for this item").

2. In ordinary context, first add any never-edited declared path to `preedit_snapshot`, then capture every declared path in `perfix_snapshot[idx]` and bind it as `active_snapshot` before editing. In Phase 8 context, require every declared path in `active_snapshot`; a missing entry violates the declared-path gate, so stop the item and use Phase 8's expansion rule to append that new path and baseline before editing while existing entries remain immutable.
3. Apply the change(s) via `Edit` tool.
4. **Narrow type-check (this file only)**:
   - Detect project type: if `turbo.json` exists → turborepo mode; else if `tsconfig.json` exists → plain TS mode; else → skip the check.
   - Turborepo: route through `turbo run` — `bun turbo run check-types --filter=<package>` (or `pnpm turbo run check-types --filter=<package>` if the repo uses pnpm), targeting the workspace package containing the edited file. The `turbo run` form is what carries `--filter` through; `bun` alone drops unknown flags instead of forwarding them to the underlying script.
   - Plain TS: `bunx tsc --noEmit` or `npx tsc --noEmit`.
   - No TS tooling: skip the check with a one-line note, and let `/done` in Phase 6 catch what it would have caught.
5. **Compare diagnostic-identity multisets**: parse the current output with Phase 1's parser, then subtract `active_baseline_errors[path]` from the current multiset by identity and count. Ordinary Phase 5 uses the Phase 1 run baseline; a Phase 8 item uses the baseline captured immediately before that item's edits. Classifications:
   - **pass**: the current multiset for every edited file is empty.
   - **failed**: `current - baseline` is non-empty for any edited file; report those remaining identities as genuinely new errors.
   - **inconclusive, preexisting errors**: current errors remain, but `current - baseline` is empty because every current identity and duplicate count is covered by the baseline. Continue.
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
       - label: "<Abort all | Abort item>"
         description: "Ordinary: revert all run-level edits and exit | Phase 8: restore only this item"

   On "Retry fix": restore the fix's declared paths from `active_snapshot`, re-dispatch the fix plan to a fresh `general-purpose` subagent with the new-errors context, loop (max 2 retries; on 3rd failure, auto-treat as "Skip this fix").
   In ordinary context, "Skip this fix" restores the current `perfix_snapshot[idx]`, marks `fix_status[idx]=skipped` and `[<idx>] NEEDS-INPUT`, skips its Phase 7 reply/resolve, and continues with the remaining fixes. In Phase 8 context, it restores every `phase8_item_files[idx]` path through the state-preserving restore rule with fallback `skipped`, sets `needs_input_status[idx]=skipped` and `convergence[idx]=not-run — user skipped after type-check failure`, then sets paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `no landed fix — user skipped after type-check failure` otherwise. Clear `phase8_triage_context`, terminate before Phases 5.5–6, and rejoin Phase 8 at the next independent item.
   Present "Abort all" only in ordinary context and "Abort item" only in Phase 8 context. On "Abort all", restore every run-level path, restore the stash, and exit non-zero. On "Abort item", restore only `phase8_item_files[idx]` through the state-preserving restore rule with fallback `aborted`, set `needs_input_status[idx]=failed` and `convergence[idx]=not-run — user aborted after type-check failure`, then set paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `no landed fix — user aborted after type-check failure` otherwise. Clear `phase8_triage_context`, terminate before Phases 5.5–6, and rejoin Phase 8 at the next independent item without touching the stash or earlier fixes.

### Fix execution tracking

```
fix_status[idx] = ok | retried_ok | inconclusive | skipped | aborted | type_check_skipped
                | reverted_inverse_risk | inverse_risk_applied | partial | restored_failed
landed_fix_statuses = {ok, retried_ok, inconclusive, type_check_skipped}
```

`landed_fix_statuses` is the authoritative landed-fix set for later phases and the final report. Phase 5.5 writes `reverted_inverse_risk` only after a successful restore and `inverse_risk_applied` when safe removal is unproven; both statuses and `partial` are non-landed. `restored_failed` means Phase 8 restored the item's snapshot after a failure and is always non-landed.

---

## Phase 5.5: Convergence (subagent)

Run after all fixes are applied, BEFORE the `/done` pipeline. A run converges when every
fix is class-complete, carries no inverse risk, and spawned no new siblings; anything
short of that is what the next review round will find.

Dispatch ONE `general-purpose` subagent. It gets `git diff HEAD` plus, per fix, the
`class_completeness` site list and the `inverse_risk` string. For a Phase 8 remediation
of `inverse_risk_applied`, also pass `phase8_remediation_kind`, the complete prior
owned-component ledger, and each component's planned removal or replacement evidence.
It fetches whatever else it needs. Keep it in a subagent: it re-reads files and greps
the repo, and main only needs verdicts.

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

For a Phase 8 `removal`, replace check 1 with mechanical remediation completeness:
every prior owned component must appear exactly once in the remediation ledger, and
the resulting content must prove that component absent. Do not require the original
affected site to remain in `git diff HEAD`, and never reapply the rejected fix to make
that site appear. For a Phase 8 `replacement`, require every prior owned component to
be removed or superseded by the recorded replacement bytes. In both branches, missing
component evidence is `class_complete: no`; the inverse-risk check requires affirmative
evidence across the complete component ledger rather than its ordinary default.

Handling:
- `class_complete: no` → apply the missing sites now, then re-verify ONCE. If the second
  pass still reports `no`, stop: mark `fix_status[idx] = partial`, record the still-unfixed
  sites, and surface them in Phase 8. Do not loop a third time; like the narrow
  type-check retry (max 2) and the self-heal loop (max 2), this loop is capped.
  For a Phase 8 remediation, correct only the missing removal or replacement evidence;
  do not apply an original affected site merely because it is absent from the diff.
- Treat each corrective class-completeness or new-sibling edit as part of the fix it completes.
  Capture its preimages, then append its exact patch and postimages to that fix's ordered
  `perfix_owned_components[idx]`; also register it as later-edit evidence for every other earlier fix.
- `inverse_risk_present: yes` → the suggestion was wrong; applying it anyway ships a worse
  defect. In Phase 8 context, restore every declared path from `active_snapshot`, including
  authoritative absence, and abort only the current item. In ordinary context,
  `preedit_snapshot` remains reserved for Abort-all. Use only
  `perfix_owned_components[idx]` and later-edit evidence to prove ownership; never reconstruct
  ownership from `git diff HEAD` or another aggregate diff. A candidate inverse removes every
  owned component in reverse order. Apply it only when the frozen evidence proves exclusive
  non-overlap and the temporary candidate preserves every other later edit. Restore the whole
  `perfix_snapshot[idx]` only when no other later fix or convergence edit touched any declared
  path and every current declared path equals the final owned component's postimage. Otherwise
  leave the fix applied, set `fix_status[idx] = inverse_risk_applied`, record
  `revert: not attempted — exclusive ownership unproven`, route it to NEEDS-INPUT, and state in
  Phase 8 that the risky fix remains applied.
  On an ordinary inverse/snapshot revert, mark `fix_status[idx] = reverted_inverse_risk` and
  route to NEEDS-INPUT. A Phase 8 active-snapshot restore uses its state-preserving restore rule
  with fallback `reverted_inverse_risk`.
- `new_siblings` → treat as part of the same fix and handle it now.

Record the outcome per fix as `convergence[idx]`; Phase 8 renders it, plus one converged /
not-converged verdict for the run. If the subagent fails, run the three checks inline and
note `convergence checked inline`.

---

## Phase 6: /done verification (main)

After all fixes are applied, run `/done` on the pending fix diff (`git diff HEAD`). `/done` is a four-section acceptance workflow, not a fixed three-command pipeline: §1 binds the run and selects the acceptance lanes, §2 verifies each required lane at its boundary, §3 assigns a state to every request item, lane, and evidence facet, and §4 builds the readiness card. Bind the originating request to the validated fix plan and scope every check to the fix diff, not the entire PR.

The Code lane always applies here. It runs `/fix-ts-errors` to green (catching the cross-file errors a per-file narrow check cannot see, and running the full workspace check at least once), runs `/parallel-review` over the fix diff and applies its `converge-reviews` result, runs `/simplify` including its blocking added-comment scan, and accounts for each fix against the diff. Select every other lane the fixes actually touched — UI, documentation, global configuration or skills, external metadata or data, publication or deployment — by the rule `/done` §1 states, and record the rest as `not-applicable` with their exclusion reason.

Do not take `/done` §4's handoffs. This skill owns publication: `git-commit` and `file-pr` are unavailable in Phase 6, and Phase 8's post-completion prompt is the only place a commit or push may start.

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

If `done_remaining` is non-empty after 2 iterations, record it for the final report and continue to Phase 7. The user sees the remaining issues in Phase 8 and decides there.

**Moderate/Minor findings** are recorded in `done_remaining` without self-heal. User decides at commit time.

When every required lane is verified, materialize the exact fix content as the `done_verified_snapshot` required by `git-commit`'s Verified content snapshot contract. Build it with `/done` §4's path-scoped snapshot procedure (`create_verified_snapshot`): read `HEAD` into an isolated `GIT_INDEX_FILE`, hash only the declared paths with `git hash-object -w`, stage each with `git update-index --add --cacheinfo <mode>,<blob>,<path>`, `--force-remove` each declared deletion, then `git write-tree`. The declared-path set here is the union of every landed fix's declared paths; the auto-stashed WIP and any other dirty path stays out of it and out of the object database. Record the snapshot tree and included path manifest while the run-level stash is still untouched. A Phase 8 fix may update only its declared paths in this snapshot after that item's verification lands cleanly; rebuild the tree by reading the prior snapshot instead of `HEAD` into the isolated index and applying only those verified bytes through the same `update-index --cacheinfo` mechanism, never by recapturing the live worktree. If no valid `done_verified_snapshot` exists, Commit and Push are unavailable.

---

## Phase 7: Reply + resolve on GitHub (main)

*Reply format rules live in `references/github-reply-resolve.md` and are referenced by Phase 4 validation. This skill does NOT read or write `/review-pr`'s cache (`~/.claude/skills/review-pr/cache/`). Thread resolution happens on GitHub. `/review-pr`'s re-review picks up resolved threads via its GraphQL prior-review timeline fetch.*

Replying and resolving threads is this phase's entire GitHub footprint. The review's own `CHANGES_REQUESTED` state stays exactly as CodeRabbit left it. CodeRabbit clears it itself on its next auto-re-review, once the user pushes.

Define `has_github_surface[idx] = thread_id != null AND (can_reply OR can_resolve)`. Initialize every item without that surface to paired `not-applicable` states, regardless of input source. For `./review.md` or any other local-file input, all items meet that condition; initialize them, then skip the rest of this phase. Phase 8 still requires deterministic per-item state for its final report.

### Posting mechanics

Load `${CLAUDE_SKILL_DIR}/references/github-reply-resolve.md` now. It holds Step 7a (regenerate every FIX reply from the actual post-fix diff, never the Phase 3 `reply_placeholder`, and which `fix_status` values are barred from replying at all), Step 7b (the mechanical reply validator: forbidden prefixes, 40-char floor, must-contain patterns, and the `reusability_context`-gated rule), Step 7c (the `addPullRequestReviewThreadReply` + `resolveReviewThread` GraphQL calls), and Step 7d (promoted nitpicks have no thread to close).

### Per-item status tracking

```
gh_status[idx] = {
  reply_state: landed | verified-existing | confirmed-absent | reconcile-required | skipped | not-applicable,
  reply_err:   <error message if any>,
  resolve_state: resolved | already-resolved | confirmed-open | reconcile-required | skipped | not-applicable,
  resolve_err: <error message if any>
}
```

Derive `reply_ok=true` from `reply_state ∈ {landed, verified-existing, not-applicable}` and `resolve_ok=true` from `resolve_state ∈ {resolved, already-resolved, not-applicable}` for the existing final-report renderer. Use `not-applicable` for every item where `has_github_surface=false`; omit those entries from GitHub failure and reply/resolve sections. Use `skipped` only when `has_github_surface=true` and an applicable GitHub mutation was not attempted. Render `verified-existing` as an authoritative existing reply and `already-resolved` as an authoritative resolution no-op. Resolution alone never proves the reply. **Work through every item to the end of the batch.** After any confirmed failure or `reconcile-required` result, skip dependent actions and retire the batch card. Continue independent pending items only after `preflight-mutations` returns a new `ready` card that excludes the unresolved target. All failures surface together at the TOP of the final report.

---

## Phase 8: Finalize (main)

*Report groups by R-classification (see the R-Rubric Summary table). Includes suppressions write (learning loop).*

### 1. Settle NEEDS-INPUT

Keep the run-level stash untouched throughout this step. Build `needs_input_items` from current workflow state: every item still classified `NEEDS-INPUT` and every item Phase 5 or 5.5 routed there. Initialize `needs_input_status[idx]=pending` for each entry. For any entry lacking `gh_status`, initialize paired `not-applicable` states when `has_github_surface=false`; otherwise initialize paired `skipped` states with `NEEDS-INPUT not yet authorized`. Do not derive this count from a rendered report. If the count is nonzero, use AskUserQuestion:

   Question:
     header: "NEEDS-INPUT"
     text: "<N> item(s) need your input. Would you like to triage them now?"
     options:
       - label: "Triage now"
         description: "Walk through each NEEDS-INPUT item and decide: fix, defer, or dismiss"
       - label: "Skip for now"
         description: "Leave them unresolved — handle manually later"

On "Triage now": for each `needs_input_items` entry, use AskUserQuestion:

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

For every automatic `Other` freeform path in the batch prompt or an item prompt, honor an instruction that unambiguously maps named items to `Fix it`, `Defer`, `Dismiss`, or `Skip for now`. Preserve the exact freeform text with the item. If the mapping is ambiguous, set each affected item's `needs_input_status=skipped` and carry the text into its manual-handling reason. Do not leave it pending.

On "Fix it": use a follow-up AskUserQuestion to collect guidance:

   Question:
     header: "Guidance"
     text: "What should the fix do for <file:line>? Describe the intended behavior or approach."
     options:
       - label: "Use reviewer's suggestion"
         description: "Apply the original review comment's recommended change as-is"
       - label: "I'll describe"
         description: "Let me type specific guidance for this fix"

   On "Use reviewer's suggestion": use the original comment's recommendation as the fix plan. On "I'll describe" or "Other", treat unambiguous fix guidance as the fix plan; honor an unambiguous defer, dismiss, or skip instruction through that action's branch. Preserve ambiguous text, set `needs_input_status=skipped`, and continue.

   Validate the complete FIX record through Phase 4 before editing. Record immutable `phase8_snapshot_fix_state[idx]` as the entry `fix_status` when it is `inverse_risk_applied` or `reverted_inverse_risk`; otherwise record `clear`. When the snapshot state is `inverse_risk_applied`, require the validated plan to record `phase8_remediation_kind[idx]=removal|replacement` and map every entry in the prior `perfix_owned_components[idx]` ledger exactly once to removal or replacement evidence. Reject an incomplete or duplicated map. Derive `phase8_item_files[idx]` from the union of every mapped owned-component path and every additional file declared by the validated plan, then capture each file's current content or authoritative absence in a dedicated `phase8_item_snapshot[idx]`. This snapshot includes all earlier landed fixes. Every later restore of this snapshot is state-preserving: restore the exact bytes, then restore `fix_status[idx]` from `phase8_snapshot_fix_state` when it is not `clear`, or use the branch's named fallback status when it is `clear`. Never change `phase8_snapshot_fix_state` without replacing the snapshot itself. Immediately after the snapshot and before any edit, run the affected Phase 5 narrow type-check against that state and parse `phase8_item_baseline_errors[idx]` with the Phase 1 diagnostic-identity multiset parser; when the applicable tooling is unavailable, record the baseline as unavailable and preserve the existing skipped-check behavior. Both item stores are append-only and separate from the run-level `preedit_snapshot` and `baseline_errors`: nested Phases 5–6 neither read nor overwrite the run-level stores. Set `phase8_triage_context=true` only after the snapshot, snapshot state, applicable remediation map, and item baseline are complete.

   In Phase 8 context, Phase 5 edits and retry agents may touch only `phase8_item_files[idx]`. When the plan expands, revalidate it and derive only the newly declared paths absent from `phase8_item_snapshot[idx]`; preserve every existing snapshot and baseline entry byte-for-byte. Before any new path is edited, append that path's current content or authoritative absence and its isolated per-path baseline, parsed with the Phase 1 diagnostic-identity multiset parser, to the item stores. Never recapture an existing path or rerun its baseline after an edit. If earlier item edits make a trustworthy per-path baseline for a new path impossible, fail closed: restore every path already present in the append-only item snapshot through the state-preserving restore rule with fallback `restored_failed`, leave the new path unedited, set `needs_input_status[idx]=failed` and `convergence[idx]=not-run — unsafe expansion baseline for <new-path>; snapshotted paths restored and new path left unedited`, then set paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `no landed fix — unsafe expansion baseline` otherwise. Clear `phase8_triage_context` and continue with the next independent item. Phase 5.5 may verify all sites but may apply a corrective edit only within declared, snapshotted files.

   Apply the Phase 5 per-fix loop. When it returns a settled `skipped` or `aborted` item, preserve its `fix_status`, `needs_input_status`, `convergence`, and `gh_status`, then rejoin Phase 8 immediately; Phase 5.5 and Phase 6 are barred from running or reapplying it. Otherwise run Phase 5.5 for that fix. After a successful active-snapshot restore yields `reverted_inverse_risk`, preserve that status without another restore, set `needs_input_status[idx]=failed`, set paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `no landed fix — inverse-risk fix reverted` otherwise, clear `phase8_triage_context`, and rejoin Phase 8. For any other status outside `landed_fix_statuses`, record it as `pre_restore_fix_status[idx]`, restore every declared path from `phase8_item_snapshot[idx]` through the state-preserving restore rule with fallback `restored_failed`, set `needs_input_status[idx]=failed`, and preserve the original convergence evidence with an appended `restored item snapshot after <pre_restore_fix_status>` disposition. Set paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `no landed fix — convergence rejected and item restored` otherwise. Clear `phase8_triage_context` and rejoin Phase 8 at the next independent item. Only a status in `landed_fix_statuses` proceeds to the affected Phase 6 type-check, review, and simplify assessments in verification-only mode; do not apply type-fix, self-heal, or simplify edits.

   A Critical or Serious blocker, validation abort, edit failure, exhausted retry, or Phase 6 failure aborts only this item. Before restoring, record the exact triggering error or blocker as `phase8_failure_reason[idx]`. Restore every declared path from `phase8_item_snapshot[idx]`, including removing a path whose snapshot recorded authoritative absence, through the state-preserving restore rule with fallback `restored_failed`; set `needs_input_status[idx]=failed`. Preserve existing convergence evidence and append `restored item snapshot after <phase8_failure_reason>`; when convergence never ran, set `convergence[idx]=not-run — <phase8_failure_reason>; item snapshot restored`. Set paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `no landed fix — <phase8_failure_reason>; item restored` otherwise. Clear the context and continue with the next independent item without restoring the run-level stash, exiting the skill, or bypassing the renderer. Ordinary Phase 5 and Phase 6 behavior remains unchanged when `phase8_triage_context` is false.

   When the fix and verification land cleanly, record current content risk as clear without changing the immutable snapshot state, then update `done_verified_snapshot` from the prior snapshot plus this item's verified declared-path bytes. If `phase8_snapshot_fix_state[idx]=inverse_risk_applied` and `phase8_remediation_kind[idx]=removal`, set `fix_status[idx]=reverted_inverse_risk`, set `needs_input_status[idx]=failed`, set paired `gh_status` states to `not-applicable` when `has_github_surface=false` or to `skipped` with `original finding not accepted — risky fix removed` otherwise, clear `phase8_triage_context`, and rejoin Phase 8 without GitHub reply or resolution. A verified replacement retains its applicable landed status and may proceed to the Phase 7 reply/resolve mechanics. Set `needs_input_status=fixed` only when `fix_status ∈ landed_fix_statuses` and both GitHub operations are successful or not applicable; set it to `reconcile-required` if either operation has that state, otherwise set it to `failed`. Preserve the final classification, `fix_status`, convergence, current-content risk, and `gh_status` before continuing.

Immediately before any chosen Fix, Defer, or Dismiss reply mutates GitHub, invoke `preflight-mutations` for that item's reply/resolve batch with the exact PR and current head SHA, target thread ID, final reply text, classification, and the per-item choice above. Apply its result contract before continuing. Record a blocked or confirmed failure as `needs_input_status=failed`, an indeterminate operation as `reconcile-required`, and the exact Phase 7 `gh_status`; then continue to the next independent item. Every branch rejoins report rendering.

On "Defer": set the classification to `DEFER` and run the Phase 7 reply/resolve mechanics. On "Dismiss": do the same with classification `DISMISS`. When `has_github_surface=false`, set both GitHub states to `not-applicable` without entering any GitHub report section. Map the final result for either branch: both required operations successful or not applicable → `needs_input_status` "deferred" or "dismissed"; either operation `reconcile-required` → `reconcile-required`; every other non-success or confirmed failure → `failed`. Preserve every authoritative outcome in `gh_status`, then continue.

On "Skip for now": mark each untouched entry `needs_input_status=skipped` and preserve its current classification, `gh_status`, and any freeform guidance for later handling.

Treat `inverse_risk_applied` as a content-state blocker, not a triage disposition. Fix, Skip, Defer, Dismiss, or freeform reclassification preserves that status and its publication block until the risky owned components are removed or replaced, Phase 5.5 and Phase 6 pass on the resulting content, and `done_verified_snapshot` is rebuilt. A verified removal may set `reverted_inverse_risk`; a verified replacement may set an applicable landed status.

Skip the questions if the NEEDS-INPUT count is 0. Before leaving this step, require every `needs_input_items` entry to have a non-pending status. Convert an unexpected remaining `pending` entry to `skipped`, preserving its recorded choice and guidance as the manual-handling reason.

### 2. Restore WIP

Only after every NEEDS-INPUT item has settled, if `STASH_PUSHED=true`:

```bash
git stash pop
```

On stash pop conflict, leave every conflict marker exactly as `git stash pop` left it. Resolving the user's WIP is the user's call. Record `stash_restored: conflict` for the final report. No edit, type-check, convergence check, Phase 6 check, commit, or push may run after this restoration. Expose conflict resolution as the only dependency-ready next action.

### 3. Print the final report once

Recompute every count from the final classification, `fix_status`, `convergence`, `needs_input_status`, and `gh_status` state. Load `${CLAUDE_SKILL_DIR}/references/final-report.md` now and render it exactly once. Render `inverse_risk_applied` under **Skipped / not landed clean**, count it as not converged, and state `risky fix remains applied`. Its dependency-ready action is `Remove the risky owned components or apply a replacement, then rerun Phase 5.5 and Phase 6 to rebuild done_verified_snapshot.` Interpret any legacy no-safe-revert rule for `reverted_inverse_risk` as `inverse_risk_applied`; the reverted status always means the fix was removed. The report's failure-first ordering includes every Phase 7 and Phase 8 GitHub outcome; its rendering rules decide which fix subsection each `[F<n>]` occupies and how the `Test:` line is emitted.

### 4. Offer to write suppressions (learning loop)

After the final report, collect all current DISMISS and DISAGREE items. If any exist, offer to persist them as suppressions for future reviews.

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
- `stash_restored=conflict` (the conflicted worktree remains read-only)

### 5. Post-completion next actions

After printing the final report and completing the suppression step when applicable, compute `inverse_risk_blockers` from every item whose current `fix_status` is `inverse_risk_applied`, independent of final classification or `needs_input_status`. When `stash_restored=conflict`, suppress the prompt and report `Resolve stash conflicts` as the sole dependency-ready next action; Commit and Push remain unavailable. Otherwise, if `inverse_risk_blockers` is non-empty, suppress the prompt and report the dependency-ready removal/replacement action from Step 3; Commit and Push remain unavailable even when `done_verified_snapshot` exists. Skip the prompt if all fixes were aborted (nothing was applied); otherwise use AskUserQuestion.

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

On "Commit changes" or "Push to remote", require `inverse_risk_blockers` to be empty, `stash_restored != conflict`, and a valid `done_verified_snapshot`. Recompute the blocker set instead of trusting the rendered report; a non-empty set stops the action. Invoke `git-commit` in Verified content snapshot sealed-index mode with that snapshot; never stage or restage the live worktree. Require the created commit tree to equal the snapshot tree. Ordinary restored WIP remains in the worktree and outside the candidate commit.

On "Push to remote", commit first, then require the commit tree to still equal the snapshot before freezing the publication branch and push-attempt SHA. For GitHub PR input, re-read the current PR's `headRefName` plus `headRepository.id` and `nameWithOwner`; freeze those authoritative values, require the Phase 1 expected PR branch and active branch to equal the frozen head name, and set `<exact-ref>` to `refs/heads/<frozen-headRefName>`. That head repository identity is the intended publication target and remains independent of the input/base repository. For local-file or other no-current-PR input, freeze the active branch and derive `<exact-ref>` as `refs/heads/<active-branch>`. Freeze the push-attempt SHA only when the active symbolic ref equals `<exact-ref>` and that branch ref and `HEAD` resolve to the same SHA. Resolve the intended publication target before binding `<preflighted-remote>`. For GitHub PR input, enumerate configured remotes and validate every endpoint in each ordered complete fetch/push set. Auto-select the only remote whose every endpoint matches the PR head identity; when multiple match, immediately use AskUserQuestion with concrete `<remote> — <nameWithOwner> (<id>)` options and pagination when needed; when none match, stop with `Configure a remote whose complete endpoint sets resolve to the current PR head repository, then choose Push to remote again.` The selected match becomes `<preflighted-remote>`.

For local-file or other no-current-PR input, immediately follow the "Push to remote" choice with AskUserQuestion. Inventory every configured remote; capture without printing its ordered complete fetch and push endpoint sets, normalize and resolve every endpoint independently through authenticated `gh repo view ... --json id,nameWithOwner`, and retain a remote only when every endpoint resolves to the same repository ID and `nameWithOwner`. Show each retained remote as a concrete option labelled `<remote> — <nameWithOwner> (<id>)`; list rejected remotes with the failing endpoint or set mismatch but never make them selectable. If the option limit cannot hold every retained remote, paginate disjoint sets of concrete options with a `Show next remotes` choice until the user selects one. That selection freezes both complete sets, sets `<preflighted-remote>` and the explicit intended publication target, and joins the preflight authorization and guards. If no remote is valid, stop with: `Configure a remote whose complete fetch and push endpoint sets resolve to one authenticated GitHub repository, then choose Push to remote again.`

Capture without printing the ordered complete sets from `git remote get-url --all <preflighted-remote>` and `git remote get-url --push --all <preflighted-remote>`, then normalize every endpoint to a credential-free URL identity. Preserve transport class, host, port, and owner/repository while treating equivalent spellings such as scp-like versus `ssh://`, default ports, trailing slash, and `.git` suffix alike. Independently resolve every normalized endpoint through authenticated `gh repo view ... --json id,nameWithOwner`; require every endpoint ID and `nameWithOwner` to equal the intended publication target. Retain only the ordered normalized sets or their digests and resolved IDs, never credentials. Record the remote name, both complete endpoint sets, and intended target; any addition, removal, reorder, resolution failure, or repository mismatch is `reconcile-required`. The named-remote push may target its configured complete push set only while that frozen set still matches.

Query `<exact-ref>` and record its remote SHA or authoritative absence; when present, require it to be an ancestor of the frozen SHA. Immediately before `git push`, invoke `preflight-mutations` with the exact remote, both ordered complete endpoint sets and repository IDs, intended publication target, `<exact-ref>`, frozen local SHA, expected remote SHA or absence, upstream state, commit range, dependent refs, and the user's choice. Include the PR base, frozen `headRefName`, `<exact-ref>`, and head repository ID in its guards and invalidators when a PR exists. Include the active symbolic ref, branch-ref SHA, `HEAD`, frozen publication branch and exact ref, and complete selected-remote identity in those guards and invalidators, then re-enumerate and compare both endpoint sets before running the exact push:

```bash
git push --force-with-lease="<exact-ref>:<expected-sha-or-empty>" "<preflighted-remote>" "<frozen-local-sha>:<exact-ref>"
git ls-remote --heads "<preflighted-remote>" "<exact-ref>"
```

After every attempted push, including a nonzero or ambiguous exit, establish remote state first: re-enumerate both complete endpoint sets and run the exact `git ls-remote` read-back for `<exact-ref>` once. Record the push as landed only when the authoritative remote SHA equals the frozen SHA, the ordered sets are unchanged, and every endpoint still equals the intended publication target. An old or unexpected SHA, unavailable read-back, added, removed, reordered, unresolved, or mismatched endpoint is `reconcile-required`; stop and never retry from the command result alone.

After preserving the remote result, re-read the active symbolic ref, frozen publication branch-ref SHA, and `HEAD`. Continue only when the symbolic ref equals `<exact-ref>` and both local SHAs equal the frozen SHA. When the remote landed but any local value moved, record `remote landed / local publication moved`, set overall publication to `reconcile-required`, and stop without retrying the push. When the remote did not land, preserve its observed state and stop as `reconcile-required` regardless of local state. Only after both remote and local state pass may a GitHub PR input read `headRefName`, `headRefOid`, and `headRepository.id`; require them to equal the frozen head name, frozen SHA, and intended publication target ID. On "Re-run on remaining": if the original input was a local file, invoke `/fix-pr-review <original-file-path>` scoped to skipped/needs-input items; otherwise invoke `/fix-pr-review <url>` scoped to remaining items. On "Done": exit.

### 6. Exit

Committing happens only on an explicit "Commit changes" or "Push to remote" choice in the post-completion prompt above. Otherwise leave the working tree as it stands. The report's suggested commit message is the hand-off.
