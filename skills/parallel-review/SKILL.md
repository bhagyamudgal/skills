---
name: parallel-review
description: Run every code reviewer in parallel over a local diff and merge their findings into one ranked list. Use when the user asks for a review of uncommitted changes, says "quick review", or after significant code changes; and when another skill needs the local-diff review (`done` runs it as its review step).
---

# Parallel Code Review

## Workflow

### Step 1: Determine Scope

- If user specifies files → review those files
- Otherwise → review all unstaged and staged changes via `git diff HEAD`
- If a prior convergence artifact exists, invoke `converge-reviews` with the current baseline, diff hash, paths, request, and planned roster/lenses before dispatch. Reuse an unchanged result; when it returns `continue`, dispatch only the invalidated coverage it names. Apply any other result without starting another review round.

### Step 2: Build the roster, then dispatch

Name the roster first, then launch every member in parallel with the Agent tool.

Members 1-3 are `subagent_type` values, passed to the Agent tool as-is. Member 4 is a **skill-running agent**: `/web-interface-guidelines`, `/ui-skills`, and `/rams` are skills, not agent types, so they cannot be passed as `subagent_type` — dispatch a `general-purpose` agent that invokes them instead.

**Size the roster to the diff before naming it.** `done` runs this skill after every task, so an unsized roster charges a one-line fix what a rewrite costs. Measure the Step 1 scope with `git diff --shortstat HEAD`:

- One file and under roughly 50 changed lines, or the user asked for a quick review, then the roster is `pr-review-toolkit:code-reviewer` alone and the rest of this step does not apply.
- Anything larger builds the roster from the members below.

A re-review after fixing findings covers the fix delta, never the whole diff again, and is sized by that delta.

Always on the roster:

1. **Code Review Agent** (`subagent_type: "pr-review-toolkit:code-reviewer"`)
2. **CodeRabbit Review Agent** (`subagent_type: "coderabbit:code-reviewer"`)

Add to the roster when the condition holds:

3. **Silent Failure Hunter** (`subagent_type: "pr-review-toolkit:silent-failure-hunter"`) — the diff touches error handling, try-catch, or fallback logic
4. **UI Review Agent** (`subagent_type: "general-purpose"`) — the diff touches frontend/UI code. Prompt it to invoke `/web-interface-guidelines`, `/ui-skills`, and `/rams` against the diff and return their merged findings.

Shared prompt, plus the per-agent lens: "Review these changed files for bugs, logic errors, and adherence to project CLAUDE.md conventions: [files]."

**State the roster before dispatching.** It is the checklist Step 3 merges against.

### Step 3: Merge

The merge is not done while any reviewer on the roster is outstanding. Account for **every** member by name — reported, or failed and re-dispatched.

1. Merge all findings, collapsing duplicates across reviewers
2. Assign each merged finding a stable ID from its file, enclosing symbol, normalized defect class, and defect-instance fingerprint. Derive the fingerprint from the smallest stable semantic code anchor—such as a callee, accessed field, branch label, or data-flow endpoints—plus the violated invariant. If two defects still share an anchor, extend it with the nearest distinct semantic parent or operand. Normalize incidental formatting, literals, and reviewer wording; exclude raw line numbers. Merge only when all four parts match, and preserve every source reviewer. The caller owns these IDs and their dispositions; do not create a shared finding-ID authority.
3. Rank: Critical > Serious > Moderate > Minor, then present one traceable list
4. Invoke `converge-reviews` with the originating request, local baseline and current diff hash, reviewed paths, roster and lenses, merged findings, dispositions, and prior convergence artifact. Apply its result contract, then hand the ranked list and convergence result back to the caller.
