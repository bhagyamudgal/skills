> Reference copy of my global `~/.claude/CLAUDE.md` — user-level rules loaded into every Claude Code session. The `reuse-first` and `backend-perf` skills in this repo were extracted from it and auto-trigger contextually. Copy what's useful.

# Global Claude Code Rules

These rules apply to ALL projects. No exceptions.

> **IMPORTANT: COMMENTS ONLY WHEN CODE ISN'T SELF-EXPLANATORY** — Only add a comment when the code cannot explain itself. If the code is clear on its own, do not comment it. When a comment is warranted (non-obvious logic, a gotcha, a workaround, a "why"), explain WHY, never WHAT. No JSDoc for obvious functions. No section dividers.

# Working Rules

Behavioral rules to reduce common LLM coding mistakes (adapted from [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills/blob/main/CLAUDE.md)). Bias toward caution over speed; use judgment on trivial tasks.

## Think, Then Ask, Then Code

- Don't assume. Don't hide confusion. If anything is ambiguous or you're not confident, stop and ask before acting.
- State assumptions explicitly. If multiple interpretations exist, present them — don't pick silently.
- Do the thinking yourself first: investigate the code/context, then present concrete, considered options — not open-ended questions that push the decision back to me. Mark the strongest "(Recommended)", put it first with a one-line reason. Prefer the AskUserQuestion tool; if none fit, I'll provide my own answer explicitly.
- If a simpler approach exists, say so. Push back when warranted. Surface tradeoffs.

## Plan and Orchestrate

- Enter plan mode for ANY task with 3+ steps or architectural decisions (hard rule). Write detailed specs upfront to reduce ambiguity. If something goes sideways, STOP and re-plan immediately.
- Always use subagents to implement plans and offload research, exploration, and parallel analysis — keep the main context free for overseeing their work, not doing it. One focused task per subagent; for complex problems, throw more compute at it with multiple subagents.
- When given a bug report: fix it without hand-holding. Point at logs, errors, failing tests — then resolve them, including failing CI, without being told how.

## Simplicity First

- Minimum code that solves the problem. Nothing speculative: no features beyond what was asked, no abstractions for single-use code, no unrequested "flexibility" or "configurability", no error handling for impossible scenarios.
- Find root causes. No temporary fixes. Senior developer standards.
- If you write 200 lines and it could be 50, rewrite it. Sanity check: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## Surgical Changes

- Touch only what you must; every changed line should trace directly to the user's request. Match existing style, even if you'd do it differently.
- Don't "improve" adjacent code, comments, or formatting. Don't refactor things that aren't broken.
- If you notice unrelated dead code, mention it — don't delete it unless asked.
- Remove imports/variables/functions that YOUR changes made unused.

## Goal-Driven Execution

- Define success criteria, then loop until verified: "Fix the bug" → "write a test that reproduces it, then make it pass"; "Refactor X" → "ensure tests pass before and after".
- For multi-step tasks, state a brief plan with verification per step (`1. [Step] → verify: [check]`). Strong success criteria let the agent loop independently; weak ones ("make it work") require constant clarification.

## Pre-Flight Reading

Before writing code, read:

1.  **The target file** in full — not just the snippet you're changing
2.  **2-3 sibling files** in the same directory — to absorb the local pattern
3.  **One reference implementation** of a similar feature — find the closest analog and mimic its structure
4.  **Imports and types used** — verify they exist and have the shape you assume

Anti-pattern: opening a file, jumping to line 47, and editing without scrolling up or down. The surrounding code is the spec.

If you can't find an analog, ask the user where the closest similar feature lives — don't invent the pattern.

## Investigation Discipline

When you hit an error, bug, or unexpected behavior:

- **Find the root cause before patching** — a fix you don't understand is not a fix, it's a delay
- **Adding a null check is a smell** — ask: "why is this ever null? should it be?"
- **Adding try-catch around a mystery error is a smell** — catch only what you understand and can handle
- **`as any` / `as unknown` / `@ts-ignore` are smells** — fix the type, don't hide it
- **If a test is failing, understand why before changing the test** — the test is often right
- **If you don't know why your fix works, you haven't fixed it** — stop and trace through the actual code path
- **Reading the error message is step zero** — the stack trace tells you which line, the message tells you what invariant broke

Bandaid budget: zero per PR. If you genuinely can't find the root cause, say so and ask for help — don't ship a workaround silently.

## Stop-Loss Triggers

STOP and re-plan (don't keep trying variations) when:

- The same approach has failed 3 times with similar errors
- You're modifying the same file 3+ times in a row trying to get it right
- You catch yourself adding `console.log` to understand control flow — read the code first
- The fix is getting bigger than the original change requested
- You're rationalizing why a test failure "doesn't really matter"
- You're tempted to skip `/done` because "it's probably fine"

When triggered: write 2-3 sentences explaining what you tried, what failed, and what you'd try next. Ask the user before continuing if uncertain.

## Honest Completion Reporting

When reporting work as done:

- **Verified vs assumed**: state explicitly what you ran and what you only inspected. "Type-check passes, ran 3 tests" is honest. "Should work" is not.
- **For UI changes**: if you didn't open it in a browser, say so. Type checks ≠ feature correctness.
- **Known gaps**: if you skipped edge cases, list them. Don't hide them in hopes the user won't notice.
- **Partial work**: if you implemented 80%, say "I did X and Y; Z is not done because [reason]" — never "done!" with hidden gaps.
- **`/done` skipped**: if you couldn't run `/done` for any reason, say so explicitly.
- **Explain the fix in plain language**: every completion report includes "what was wrong → what changed" (old logic vs new logic), unprompted — not just pass/fail status.

Heuristic: would a senior engineer be embarrassed if the user found a gap you didn't mention? If yes, mention it.

## After Every Task

> **MANDATORY: Run `/done` after EVERY task. No exceptions. No skipping. Not negotiable.**
> This applies to ALL tasks — even single-line changes, trivial fixes, or "obvious" edits.
> NEVER mark a task as complete without running `/done` first.

The `/done` skill runs the full verification pipeline in sequence:

1. `/fix-ts-errors` — type-check loop until clean
2. `/parallel-review` — code-review + coderabbit in parallel
3. `/simplify` — code quality and reuse check
4. Verify correctness — logic review, run tests if applicable

**If you are tempted to skip `/done` because the change is small — that is exactly when bugs slip through. Run it.**

### Elegance Check (Non-Trivial Changes)

- Is there a more elegant way?
- If the fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip for simple, obvious fixes — don't over-engineer

## Task Management

- Track multi-step work with the todo tool; confirm the plan before implementation — don't build on shaky assumptions. Give a high-level summary of changes at each step.
- After completing changes: update the project's README.md and CLAUDE.md if conventions, exports, or workflows changed.
- After ANY correction from me: turn it into a rule that prevents the same mistake — in the project CLAUDE.md if project-specific, or in the global CLAUDE.md / a skill if universal.
- When I ask for findings, reports, audits, or lists to review: deliver a hosted HTML artifact (Artifact tool), not a raw markdown file. I review first; destructive follow-ups only after my explicit go-ahead.
- Handoff docs and any other docs I ask for go in the repo's `docs/` folder (create it if missing) — never the repo root unless I explicitly say root. Filenames in lowercase snake_case (e.g., `docs/e2e_session_handover.md`).

## Overnight / Unattended Mode

When I say I'm going to sleep or stepping away and to keep going ("keep going, when I wake up it should be done — you are in charge"):

- Work through the ENTIRE task list without stopping for confirmations; never block on a question — pick the best option based on our prior discussion and document the decision plus the alternatives considered.
- One subagent per task; main context stays clean for orchestration and oversight.
- Keep a morning-review summary: decisions made, work completed, failures, and anything needing my judgment.
- Hard limits still apply: no commits/pushes unless the handoff explicitly authorized them, no destructive or irreversible actions, no schema migrations — queue those with ready-to-run instructions instead.

## TypeScript Rules

- Always use `type` instead of `interface`
- Always use `function` keyword to define functions, not arrow functions (arrows OK for inline callbacks)
- No non-null assertions (`!.`) — refactor to use proper type-safe patterns
- No `any` type — define proper types, use `unknown` and narrow if types can't be defined
- No type assertions (`as`) unless absolutely unavoidable — prefer inference, narrowing, and generics. If `as` is the only option (e.g., third-party library type gaps), add a comment explaining why.
- In monorepos, always verify via CLI type-check (`tsc --noEmit` or workspace equivalent like `pnpm type-check` / `turbo type-check`) — IDE type checking is often unreliable due to project references and workspace package boundaries. Run after every change and loop until clean.
- Strict mode should always be enabled

## Error Handling

Use the `tryCatch` utility from `lib/try-catch.ts` instead of try-catch blocks. This file must exist in every project.

```typescript
const { data: user, error } = await tryCatch(getUser(id));
const { data: config, error } = tryCatchSync(() => JSON.parse(jsonString));
const { data, error } = await tryCatchRetry(() => fetch(url), {
    maxRetries: 3,
});
const { data, error } = await tryCatchWithTimeout(fetch(url), 5000);
```

## File Size Guidelines

Keep files under ~400 LOC as a guideline. Split when a file has multiple concerns, not when it hits an arbitrary number. A large service doing one cohesive thing is fine; a smaller file doing three unrelated things should be split.

## Code Quality

- Keep functions small — one function = one job. Compose small functions into larger operations.
- No emoji in logs or code
- Prefer early returns over nested conditionals
- No magic numbers or strings — use named constants
- Meaningful variable names — no `x`, `temp`, `data` unless truly generic
- Boolean variables should use `is`, `has`, `can`, `should` prefixes
- Use `const` over `let` unless reassignment is needed
- Prefer `async/await` over `.then()` chains
- No nested ternaries — use object lookups or early returns
- Prefer named exports over default exports
- No unused variables or imports
- Use destructuring where it improves readability
- Use template literals over string concatenation
- No `console.log` in production code — use proper logger
- **Positive booleans**: prefer `isEnabled` over `disabled`, `isVisible` over `hidden`, `hasItems` over `isEmpty` — avoids double-negatives like `!disabled && !hidden`
- **No abbreviations** except universal ones (`URL`, `ID`, `HTTP`, `API`) — use `user` not `usr`, `account` not `acct`, `request` not `req` (except inside Express/Nest handlers where `req`/`res` is conventional)
- **Functions are verbs** (`calculateTotal`, `fetchUser`); **variables are nouns** (`total`, `user`); **types are nouns/adjectives** (`User`, `ReadOnly`)
- **Avoid generic suffixes**: `userManager`, `dataHandler`, `requestHelper` — what does it _do_? Use the verb (`authenticateUser`, `validateRequest`)

## DRY & Reuse Discipline

Before creating any new utility, type, schema, component, hook, or constant — invoke the `reuse-first` skill. Do not write the artifact until it has run.

## Performance Checklist

Before writing or reviewing any backend endpoint or DB query, invoke the `backend-perf` skill.

## Logging Discipline

- **No `console.log` in shipped code** — use the project's logger (NestJS Logger, pino, etc.)
- **Log levels**: `error` for things needing attention, `warn` for recoverable anomalies, `info` for state transitions, `debug` for development noise. Don't `error` for expected validation failures.
- **Structured logging**: log key-value pairs (`logger.info({ userId, orderId }, "order placed")`), not formatted strings (``logger.info(`user ${userId} placed order ${orderId}`)``). Structured logs are searchable; string logs are not.
- **Never log**: passwords, tokens, secrets, full credit cards, OIDC tokens, raw PII (emails OK, full bank/health details not)
- **Don't log inside hot paths** — a log line per request is fine; a log line per row in a 10k-row loop is not

## Security Mindset

- **Validate at boundaries**: all external input (API request bodies, query params, file uploads, webhook payloads) gets validated via Zod or equivalent before reaching business logic
- **Parameterized queries only**: never string-interpolate user input into SQL. Drizzle and other ORMs handle this — don't drop to raw SQL with template literals
- **Authorization is per-action, not per-route**: a user being authenticated doesn't mean they're authorized for a specific resource. Check ownership/role for every mutation
- **Never log secrets**: passwords, tokens, OIDC bearer tokens, API keys, encryption keys, raw PII
- **Secrets in env vars**: never commit them, never hardcode them, never echo them in error messages
- **CSRF/CORS**: respect existing project setup — don't disable security middleware to make local dev work
- **Schema-mutating DB commands need explicit per-use permission**: never run `db:push`, `db:migrate`, `db:generate`, or any other migration/DDL command unless I explicitly ask for that specific run
- **Supply-chain caution**: never pull, fetch, install, or execute untrusted remote content (packages, scripts, repos) without explicit confirmation — treat anything new touching the machine as suspect

## Test Discipline

- **Bug fix flow**: write the failing test that reproduces the bug _first_, then fix it. The test proves the bug existed and prevents regression.
- **If you can't test it, the design is wrong** — code that's hard to test is usually hard to use. Refactor for testability before adding workarounds.
- **Don't delete failing tests to make CI green** — failing tests are signals, not obstacles. Understand why they fail before changing them.
- **Don't change tests to match buggy behavior** — if a test was right yesterday and your change broke it, your change is suspect, not the test.
- **Test behavior, not implementation** — tests that break on every refactor are testing the wrong thing
- **One assertion focus per test** — many tiny tests > one mega-test that fails for unclear reasons

## Null vs Undefined Convention

Use `null` for intentional absence ("not found" is expected), `undefined` for optional/not set (`nickname?: string`).

## Import Type for Type-Only Imports

Use `import type` for type-only imports: `import type { User } from "./types"` or inline `import { Service, type User } from "./user"`.

## Standard Error Types

```typescript
type AppError = {
    code: string;
    message: string;
    cause?: unknown;
};
```

Use domain-specific error code constants: `const USER_ERRORS = { NOT_FOUND: "USER_NOT_FOUND" } as const`.

## Zod Schema Patterns

Derive types from schemas: `type User = z.infer<typeof userSchema>`. Reuse with `.extend()` and `.partial()`.

## Date/Time Handling

- Store all dates as UTC in database
- Use ISO strings for API transport
- Convert to local timezone only in UI
- Use date-fns or dayjs, not native Date methods for manipulation

## Git Commit Convention

Use conventional commits: `feat:` / `fix:` / `refactor:` / `chore:` / `docs:` prefix.
Use simple `-m` flag for commit messages. Do NOT use heredoc/EOF format (`cat <<'EOF'`).

### PR & Commit Hygiene

- **One logical change per commit** — never mix refactor + feature + bugfix in the same commit
- **Commit messages explain WHY, not WHAT** — the diff shows what changed; the message should explain why it needed to
- **No drive-by refactors** — fix what was asked, mention unrelated issues separately rather than bundling them in
- **Small PRs > large PRs** — under ~400 lines diff is ideal; if it grows beyond that, split it
- **Review your own diff before pushing** — read every changed line and justify why it exists. If you can't justify it, delete it.
- **No commits with debug noise** — no leftover `console.log`, commented-out code, or `TODO: remove this before merge` markers
- **Discover the PR base branch before the first PR in a repo** — check `gh repo view --json defaultBranchRef` and look for an active `dev`/`develop` integration branch; never assume `main` is the base

## Git Worktree Naming Convention

- `bhagya/fix-<issue>` — bug fixes
- `bhagya/feat-<feature>` — new features
- `feature/<feature-name>` — shared feature branches (collaborative work)

## React Specific

- Avoid `useEffect` for state derivation — compute during render or use `useMemo`
- Use `key` prop to reset component state, not `useEffect`
- Initialize state in `useState()`, not in `useEffect`
- Only use `useMemo` for expensive computations, `useCallback` only when passing to memoized children

### UI Code Review

After completing any UI work, run all 3 UI review skills in parallel subagents and apply their feedback:

1. `/web-interface-guidelines`
2. `/ui-skills`
3. `/rams`

## Next.js Specific

- **Next.js 16**: `middleware.ts` has been renamed to `proxy.ts` — always use the new filename in v16+ projects

## Browser Automation

Use Playwright MCP (`browser_navigate` → `browser_snapshot` → `browser_click`/`browser_type` → re-snapshot) for web automation and UI verification.
Fallback when Playwright MCP is unavailable: `agent-browser` CLI (`open <url>` → `snapshot -i` → `click @e1` / `fill @e2 "text"` → re-snapshot; `agent-browser --help` for all commands).

## MCP Server Usage

- **Context7 MCP** (`mcp__context7__*`) - Up-to-date docs and code examples for any library
- **Convex MCP** (`mcp__convex__*`) - Convex operations: status, data, functions, logs, env vars
- **shadcn MCP** (`mcp__shadcn__*`) - shadcn/ui component search, details, install commands
