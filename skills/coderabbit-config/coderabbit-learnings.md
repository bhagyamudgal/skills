# CodeRabbit Learnings — copy-paste-ready

These are persistent, natural-language preferences that CodeRabbit applies across PR reviews.
They live in CodeRabbit's cloud (visible at https://app.coderabbit.ai/learnings) and persist
forever until you delete them. Two ways to add a learning:

1. **Web UI**: visit https://app.coderabbit.ai/learnings and paste each block as a new learning. Set scope to `local` (current repo only) or `global` (all repos in the org).
2. **PR comment**: reply on any PR with `@coderabbitai add learning: <text>`. CodeRabbit confirms and stores it.

Recommended scope: **global** for everything below — these are personal conventions that should apply to every project, not just one repo.

---

## Error handling

> We use `tryCatch` from `lib/try-catch.ts` instead of raw try/catch blocks. Variants: `tryCatchSync` for synchronous, `tryCatchRetry({ maxRetries })` for retryable calls, `tryCatchWithTimeout(promise, ms)` for bounded calls. Flag new `try { } catch { }` blocks except at framework boundaries (route handlers, top-level error boundaries). The pattern is `const { data, error } = await tryCatch(fetchUser(id))` — never throw inside business logic.

## TypeScript style

> Always use `type` instead of `interface`. Always use the `function` keyword for top-level function declarations (arrow functions OK only for inline callbacks). Never use non-null assertions (`!.`) — refactor to type-safe narrowing. Never use `any` — use `unknown` and narrow. Avoid `as` type assertions; only acceptable when working around third-party type gaps, and require an inline comment explaining why.

## Null vs undefined

> Use `null` for intentional absence ("not found" is expected), `undefined` for optional / not-set fields. A `nickname?: string` field is undefined when not provided; a `findUser` that didn't find anything returns `null`.

## Comments policy

> Default to writing no comments. Only add a comment when the WHY is non-obvious: a hidden constraint, a subtle invariant, a workaround for a specific bug, behavior that would surprise a reader. Never write multi-paragraph docstrings. Never use JSDoc that just restates the function name. Don't reference the current task / PR / fix in code comments — that belongs in the PR description.

## React patterns

> Avoid `useEffect` for state derivation — compute during render or use `useMemo`. Use the `key` prop to reset component state, not `useEffect`. Initialize state in `useState()`, not in `useEffect`. Only use `useMemo` for genuinely expensive computations. Only use `useCallback` when passing a callback to a memoized child component.

## Performance defaults

> If two or more async calls are independent, wrap them in `Promise.all` — never sequential awaits. Never run a database query inside a loop — batch with `IN` clauses or `JOIN` instead. For pagination, use `dbQueryWithPagination` which handles count + data in one pass; never run a separate `COUNT(*)` query. Every `WHERE` clause column used in production queries must have a matching index. In list endpoints, use `.select({ field1, field2 })` not `.select()` to project only needed columns.

## Surgical changes

> Only touch what the task requires. Don't "improve" adjacent code, comments, or formatting. Don't refactor things that aren't broken. Match existing style, even if you'd do it differently. When you notice unrelated dead code or issues, mention them in the review summary — don't fix them silently in the same PR.

## Conventional commits

> Commit messages use conventional-commits format: `feat: ...`, `fix: ...`, `refactor: ...`, `chore: ...`, `docs: ...`. The first line is under 70 characters. Body explains WHY, not WHAT (the diff already shows what).

## Branch naming

> Branch names follow these patterns: `bhagya/feat-<feature>` for new features, `bhagya/fix-<issue>` for bug fixes, `feature/<feature-name>` for shared collaborative branches. Don't suggest renaming branches; just verify PRs target sensible bases.

## Date / time handling

> Store all dates as UTC in the database. Use ISO strings for API transport. Convert to local timezone only in UI code. Use `date-fns` or `dayjs` for date manipulation, never native `Date` methods.

## File size

> Files over ~400 LOC are a soft warning. Don't suggest splitting unless the file has multiple unrelated concerns. A large service that does one cohesive thing is fine.

## Testing

> Prefer real databases / real fixtures over mocks in integration tests. We learned this the hard way: mocked tests pass while production migrations break. Mocks are OK only for external services (Stripe, Hubspot, S3) that you can't reasonably hit in CI.

## Don't suggest

> Do NOT suggest "consider adding tests" as a generic finding — only when tests were expected and omitted. Do NOT suggest extracting code to a shared package unless the code is fully generic (no domain types in signature OR body) AND a suitable shared package already exists. Do NOT flag `.toFixed()` / `.toString()` as type-coercion bugs when the call is wrapped in `Number(...)` / `parseFloat(...)` / `parseInt(...)` on the same line.
