---
name: fix-ts-errors
description: Fix TypeScript errors and loop the type-check until green. Use when the user says "ts errors" or "fix types", when a change "still isn't working" in a TS context, after editing any TypeScript file, and when another skill needs the type-check loop (/done, /parallel-review, /fix-pr-review).
---

# Fix TypeScript Errors

## Workflow

### Step 1: Identify Target Files

- If user specifies files → use those
- If user says "changed files" → run `git diff --name-only` to get modified `.ts`/`.tsx` files
- If unclear → ask which files

### Step 2: Go red

Run the workspace type-check — `pnpm type-check` / `turbo type-check`, or `bunx tsc --noEmit` for a plain TS project. **That output is the loop's ground truth.**

Use IDE diagnostics (the LSP tool, or `mcp__ide__getDiagnostics`) only to localise an error the check already reported. IDE diagnostics are per-file and unreliable across workspace package boundaries, so they narrow — they never decide.

### Step 3: Fix Errors

For each error found:

1. Read the file around the error location
2. Understand the root cause, then fix at the source
3. Fix with proper type-safe patterns

**Fix priority:**

- Missing imports → add the import
- Type mismatches → correct the declaration at its source
- Missing properties → check the source type definition and align
- Null/undefined → narrow with a type guard or an early return
- Generic type issues → provide explicit type parameters

**Every error exits through a real type:** add the missing import, narrow the union, widen the signature at its source, or derive it from the schema (`z.infer`). An `as` survives only with a comment naming the third-party gap.

### Step 4: Re-verify

Re-run the same workspace check. **Green means it exits 0.**

A file whose squiggles cleared is not green — a type change breaks its importers, so chase the cascade to the workspace edge before reporting. If new errors appeared, go back to Step 3.

### Step 5: As-Cast Audit

Once green, grep the changed lines for `as ` assertions (excluding `as const`):

```bash
git diff -U0 -- '*.ts' '*.tsx' | grep '^+' | grep -w 'as' | grep -v 'as const'
```

Skip import aliases (`import { x as y }`). For every remaining `as`:

1. Attempt to remove it with proper typing — inference, narrowing, type guards, generics, or schema-derived types (`z.infer`)
2. Re-run the check after each removal; if errors appear, go back to Step 3
3. An `as` may survive only if genuinely unavoidable (e.g., a third-party library type gap) — and it must carry a comment explaining why

### Step 6: Report

Once green, briefly report:

- How many errors were found
- What was fixed
- Surviving `as` casts: the count, with a one-line justification each (target: 0)

## Loop Breaker

If after 3 fix-verify cycles errors persist:

1. Stop and explain the root cause
2. Show the remaining errors
3. Suggest whether the issue is in the file itself or in a dependency
4. Ask the user how to proceed

## Important Rules

- A wrong type in a shared workspace package is fixed in that package: report it and stop
- Check whether the error is in generated code or authored code — if a codegen step is stale, suggest the command, do not run it
