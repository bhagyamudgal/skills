---
name: parallel-review
description: Run code review and coderabbit review in parallel on changed code. Use when user says "review", "code review", "run review", "check my code", "review changes", or after completing a task/feature. Also trigger proactively after significant code changes.
---

# Parallel Code Review

Runs multiple code review tools simultaneously for comprehensive feedback.

## Workflow

### Step 1: Determine Scope

Figure out what to review:
- If user specifies files → review those files
- Otherwise → review all unstaged/staged changes via `git diff`

### Step 2: Launch Parallel Reviews

Run ALL of the following in parallel using the Agent tool:

1. **Code Review Agent** (`subagent_type: "pr-review-toolkit:code-reviewer"`)
   - Prompt: "Review the following changed files for bugs, logic errors, code quality, and adherence to project CLAUDE.md conventions: [list files or describe changes]"

2. **CodeRabbit Review Agent** (`subagent_type: "coderabbit:code-reviewer"`)
   - Prompt: "Review the code changes for bugs, security issues, and quality problems: [list files or describe changes]"

3. **Silent Failure Hunter** (`subagent_type: "pr-review-toolkit:silent-failure-hunter"`)
   - Only include this if the changes involve error handling, try-catch, or fallback logic
   - Prompt: "Check for silent failures and inadequate error handling in: [list files]"

### Step 3: Synthesize Results

After all agents complete:
1. Combine findings, deduplicating overlapping issues
2. Prioritize: Critical > Serious > Moderate > Minor
3. Present a unified summary with actionable fixes
4. If issues are found, offer to fix them

### Step 4: Fix (Optional)

If user agrees to fixes:
1. Apply fixes for critical and serious issues
2. Re-run `/fix-ts-errors` on changed files
3. Briefly confirm what was fixed

## For UI Changes

If the changes include frontend/UI code, also run in parallel:
- `/web-interface-guidelines` review
- `/ui-skills` review
- `/rams` accessibility review

## Quick Mode

If user says "quick review" — run only the code-reviewer agent (skip coderabbit and silent-failure-hunter).
