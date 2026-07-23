---
name: fix-ts-errors
description: Fix TypeScript errors in changed or specified files. Use when user says "ts errors", "typescript errors", "fix types", "type errors", "this file has ts error", "still not working" (in TS context), or after writing code that may have type issues. Also use proactively after editing TypeScript files.
---

# Fix TypeScript Errors

Autonomous TypeScript error detection and fixing loop. Eliminates the manual "check → fix → still broken → fix again" cycle.

## Trigger Conditions

- User reports TS errors in a file
- User says "not working" after a TS change
- After writing/editing TypeScript files (proactive)
- User says "fix types", "ts errors", "type errors"

## Workflow

### Step 1: Identify Target Files

Determine which files to check:
- If user specifies files → use those
- If user says "changed files" → run `git diff --name-only` to get modified `.ts`/`.tsx` files
- If after a code edit → check the files just edited
- If unclear → ask which files

### Step 2: Get Diagnostics

Use the IDE integration to get TypeScript diagnostics:

```
Use the LSP tool (or mcp__ide__getDiagnostics) to get diagnostics for each target file.
```

If IDE integration is unavailable, fall back to reading the file and analyzing types manually based on imports and type definitions.

### Step 3: Fix Errors

For each error found:
1. Read the file around the error location
2. Understand the root cause (don't just suppress the error)
3. Fix with proper type-safe patterns

**Fix priority:**
- Missing imports → add the import
- Type mismatches → fix the type, not add `as` cast
- Missing properties → check the source type definition and align
- Null/undefined issues → add proper narrowing (no `!` assertions)
- Generic type issues → provide explicit type parameters

**Never do:**
- Add `// @ts-ignore` or `// @ts-expect-error`
- Use `as any` or `as unknown as X`
- Use non-null assertions (`!.`)
- Suppress errors without understanding them

### Step 4: Re-verify

After fixing, re-run diagnostics on the same files to confirm all errors are resolved.

If new errors appeared (cascade effect), go back to Step 3.

### Step 5: As-Cast Audit

Once diagnostics are clean, grep the changed lines for `as ` assertions (excluding `as const`):

```bash
git diff -U0 -- '*.ts' '*.tsx' | grep '^+' | grep -w 'as' | grep -v 'as const'
```

Skip import aliases (`import { x as y }`). For every remaining `as`:
1. Attempt to remove it with proper typing — inference, narrowing, type guards, generics, or schema-derived types (`z.infer`)
2. Re-run diagnostics after each removal; if errors appear, go back to Step 3
3. An `as` may survive only if genuinely unavoidable (e.g., a third-party library type gap) — and it must carry a comment explaining why

### Step 6: Report

Once clean, briefly report:
- How many errors were found
- What was fixed
- Surviving `as` casts: the count, with a one-line justification each (target: 0)
- Any remaining concerns

## Loop Breaker

If after 3 fix-verify cycles errors persist:
1. Stop and explain the root cause
2. Show the remaining errors
3. Suggest whether the issue is in the file itself or in a dependency
4. Ask the user how to proceed

## Important Rules

- Always understand the error before fixing — read surrounding code and type definitions
- Prefer fixing at the source over fixing at the symptom
- If a type is wrong in a shared package (@gsm3/types, @gsm3/validators), flag it — don't work around it
- Check if the error is in generated code (drizzle schema) vs authored code
- For Drizzle schema errors, check if `db:generate` needs to run
