---
name: done
description: MANDATORY post-task verification. Run after EVERY task — no exceptions, no skipping, regardless of task size. Executes type-check, parallel code review, and code simplification in sequence.
---

# Post-Task Verification (/done)

**This skill is MANDATORY after every task. No exceptions. Not optional. Not "nice to have". REQUIRED.**

Even for single-line changes, one-file edits, or "trivial" fixes — you MUST run `/done` before marking any task as complete.

## Workflow

### Step 1: Type Check

Run `/fix-ts-errors` — this runs `pnpm type-check` across all packages and loops until zero errors.

If the task only touched a specific app, you may scope the first pass (`--filter=frontend` or `--filter=backend`), but always run the full check at least once.

**Do not proceed to Step 2 until type-check passes clean.**

### Step 2: Parallel Code Review

Run `/parallel-review` — this launches code-reviewer + coderabbit review agents in parallel on the changed code.

If issues are found:
1. Fix critical and serious issues
2. Re-run `/fix-ts-errors` after fixes
3. Report what was fixed

### Step 3: Simplify

Run `/simplify` — this reviews changed code for reuse, quality, and efficiency.

If improvements are suggested:
1. Apply the improvements
2. Re-run `/fix-ts-errors` after changes

### Step 4: Verify Correctness

1. Review the final code logic to verify it does what was intended
2. If tests exist for the changed code, run them
3. Ask yourself: "Would a staff engineer approve this?"

### Step 5: Report

Briefly report:
- What was checked
- Any issues found and fixed during review
- Final status: clean or remaining concerns

### Step 6: Suggest Commit Messages

After everything passes, suggest two ready-to-paste `git commit` commands. **Do NOT run them — only print them for the user to choose.**

Use conventional commit format (`feat:`, `fix:`, `refactor:`, `chore:`, `docs:`).

**Option A — Detailed:**
```
git commit -m "feat: add user role validation to auth middleware

- Add role-based guard to /api/admin routes
- Update UserRole type with new 'manager' variant
- Add validation tests for all role combinations"
```

**Option B — One-liner:**
```
git commit -m "feat: add user role validation to auth middleware"
```

Rules for commit message suggestions:
- Analyze the actual `git diff` to understand what changed
- The subject line should explain WHY, not WHAT (the diff shows what)
- Detailed version uses `-` bullet points for key changes (3-5 bullets max)
- Use the correct prefix: `feat:` for new features, `fix:` for bugs, `refactor:` for restructuring, `chore:` for tooling/config, `docs:` for documentation
- Keep subject line under 72 characters
- **Never commit automatically — only suggest**

## Rules

- **NEVER skip this skill** — it runs after every task, period
- **NEVER mark a task as complete without running /done first**
- **NEVER say "the changes are small so I'll skip review"** — small changes cause big bugs
- If a step finds issues, fix them before proceeding to the next step
- If you already ran `/fix-ts-errors` during implementation, run it again — new issues may have been introduced
