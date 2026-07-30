---
name: parallel-review
description: Run every code reviewer in parallel over a local diff and merge their findings into one ranked list. Use when the user asks for a review of uncommitted changes, says "quick review", or after significant code changes; and when another skill needs the local-diff review (`done` runs it as its review step).
---

# Parallel Code Review

## Workflow

### Step 1: Determine Scope

- If user specifies files → review those files
- Otherwise → review all unstaged and staged changes via `git diff HEAD`

### Step 2: Build the roster, then dispatch

Name the roster first, then launch every member in parallel with the Agent tool.

Always on the roster:

1. **Code Review Agent** (`subagent_type: "pr-review-toolkit:code-reviewer"`)
2. **CodeRabbit Review Agent** (`subagent_type: "coderabbit:code-reviewer"`)

Add to the roster when the condition holds:

3. **Silent Failure Hunter** (`subagent_type: "pr-review-toolkit:silent-failure-hunter"`) — the diff touches error handling, try-catch, or fallback logic
4. **`/web-interface-guidelines`, `/ui-skills`, `/rams`** — the diff touches frontend/UI code

Quick review: the roster is `pr-review-toolkit:code-reviewer` alone.

Shared prompt, plus the per-agent lens: "Review these changed files for bugs, logic errors, and adherence to project CLAUDE.md conventions: [files]."

**State the roster before dispatching.** It is the checklist Step 3 merges against.

### Step 3: Merge

The merge is not done while any reviewer on the roster is outstanding. Account for **every** member by name — reported, or failed and re-dispatched.

1. Merge all findings, collapsing duplicates across reviewers
2. Rank: Critical > Serious > Moderate > Minor
3. Present one list, every finding traceable to the reviewer that raised it
4. Hand the ranked list back to the caller
