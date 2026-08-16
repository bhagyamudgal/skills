> Reference copy of my global `~/.claude/CLAUDE.md` — user-level rules loaded into every Claude Code session. The `reuse-first` and `backend-perf` skills in this repo were extracted from it and auto-trigger contextually. Copy what's useful.

# Global Claude Code Rules

These rules apply to ALL projects. No exceptions.

> **IMPORTANT: COMMENT THE DIG, NOT THE CODE** — A comment earns its place when the fact it carries cost a _dig_: running the binary to find out, reading four packages, a benchmark run, a decision made once in a conversation. The test, which you can honestly fail: _where does the evidence live — in this file, or outside it?_ If it is in the file, delete the comment; that is what the code is for. Outside it counts even when it is still in the repo: a consequence in another package, or a rule a sibling module enforces, costs a real dig from here. Ask it of every comment you write, including the ones you are certain about. The question is about the evidence, never about the symbol: a non-exported constant can hold a fact from CPython or an authority document, and no amount of reading the file around it will produce that fact. The author of a decision always believes a note would stop the next person getting it wrong, so "would deleting this cause a bug?" answers yes every time and decides nothing; "did I dig for this?" answers no often enough to bind. A file header summarises what sits below it, which is the one place that fact is guaranteed to live already.
>
> **`/** */` when a caller outside the file needs it, `//` otherwise.** The compiler attaches a `/** */` to the symbol, so it surfaces on hover at the call site and rides into `.d.ts`; a `//` never leaves the file it is written in. That difference is the only thing the form decides, so route by audience: exported symbols and the members of exported types earn a docstring, internal helpers and module constants take `//`.
>
> **The bar rises as the audience narrows.** On a non-exported symbol a comment has one job: carry a fact from outside this file — a runtime quirk, a spec or authority the code obeys, a measurement someone took, a consequence in another package, a gotcha that cost a dig. **A tripwire counts**: a note saying a branch is unreachable today and what breaks the day it is not reads as noise beside provably-dead code, which is exactly why deleting it is how the bug lands. Anything explaining what the code does, or why it is shaped the way it is, is addressed to a reader already standing in it: delete it. An exported symbol may additionally state its contract, because its callers cannot see the body. Routing a comment to `//` is not a decision that it should exist — sort by audience only after it has cleared the bar for that audience.
>
> **Derive it before you keep it.** Try to reconstruct the comment's claim from the code beneath it, and if you can name the lines that already carry it, delete the comment. `Math.min(a, b)` already says "the weaker governs"; a `key → label` table already says which keys share a label; an error string reading "two records have run together" already says a repeated field means a garbled boundary. This is the test that catches what "does it carry a fact?" cannot: **a restatement carries a true fact**, which is why it survives every review that only asks whether the fact is real. Compressing one yields a shorter restatement, so ask this before reaching for the edit. A verdict — "this looks redundant" — is not a derivation and does not count; name the lines or keep the comment.
>
> **Then name what it changes.** A fact can be true, external, and still inert. The last question is: _what edit, decision or debugging step goes differently because someone read this?_ A simplification they would attempt and abandon, a constant they would pick wrong, an hour of chasing a bug — name one, or delete. "It gives context" is not an answer. This is the test the other two cannot make: a restatement fails the derivation, but an inert fact passes every check except this one.
>
> **A comment is 1–3 lines**, and states the finding, not the reasoning that produced it. The reasoning has a home — the ADR, the PR body, the test. A dig worth more than three lines is a dig worth an ADR, and the comment becomes a citation to it. Count comment lines against your diff before submitting: length, not count, is where a justified comment turns into an essay.
>
> **One fact, one home.** A genuinely good argument is the one that gets duplicated: stated in the module header, again at the constant that enforces it, again in the test that covers it, again as a printed string. Every copy passes the "is this necessary?" test on its own, which is why this survives review — and every copy is somewhere a later edit leaves a stale claim behind, because nothing checks a comment in one file against the code in another. Write each invariant once, at the code that enforces it; everywhere else cites it (`see rate-limit.ts WINDOW_MS`) or says nothing. **A test comment restating the test name is one of those copies.** Before writing a comment, ask where that fact already lives.

# Working Rules

Behavioral rules to reduce common LLM coding mistakes (adapted from [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills/blob/main/CLAUDE.md)). Bias toward caution over speed; use judgment on trivial tasks.

## Think, Then Ask, Then Code

- Don't assume. Don't hide confusion. If anything is ambiguous or you're not confident, stop and ask before acting.
- State assumptions explicitly. If multiple interpretations exist, present them — don't pick silently.
- Do the thinking yourself first: investigate the code/context, then present concrete, considered options — not open-ended questions that push the decision back to me. Mark the strongest "(Recommended)", put it first with a one-line reason. Prefer the AskUserQuestion tool; if none fit, I'll provide my own answer explicitly.
- If a simpler approach exists, say so. Push back when warranted. Surface tradeoffs.
- **Only ask what you can't resolve yourself.** Before asking, state in one sentence what changes based on the answer. If you can't state it, don't ask — read the code, decide, and name the assumption so I can override it. A question you could have answered by opening a file is a question you owe me an answer to instead.
- **Never stack dependent questions.** A question whose answer depends on another unanswered question goes in its own turn, in dependency order. Independent choices may batch, three maximum.
- **Set up every question before asking it.** At most three sentences of plain context: what you found, why you're stuck, what each answer changes. Every option states what happens if I pick it — an outcome, not a mechanism. Define any term, file, or symbol the first time it appears.

## Writing for a Human Reader

Applies to everything I read: chat replies, questions, PR titles and bodies, issue text, completion reports, docs.

Unreadable output is almost never a vocabulary problem. It happens when you write from inside a mental model I can't see — naming a file I haven't opened, referring back to a finding from twelve tool calls ago, using a term the way this codebase uses it without saying so. Don't simplify the words; supply the missing context.

- **Lead with the answer**, then the reasoning. Never build up to it.
- **Name it before you use it.** The first mention of a file, function, flag, or term carries a clause saying what it is — `tryCatch` (the error wrapper in `lib/try-catch.ts`) — even if it came up earlier in the session.
- **Restate, don't refer back.** "As established above" and "the issue from earlier" are dead links. Carry the fact forward in a clause.
- **Prose for reasoning, bullets for lists.** A bulleted argument hides the connective tissue that makes it an argument.
- **Quantities, not adjectives.** "Three of eleven checks fail" beats "several checks fail".
- **Say what you did, not what should happen.** "Ran the type-check, exits 0" — never "this should work".

Never emit: "I've gone ahead and", "It's worth noting that", "Let's dive in", "delve", "seamless", "Certainly!", stacked hedges ("might potentially"), or emoji.

## Plan and Orchestrate

- Enter plan mode for ANY task with 3+ steps or architectural decisions (hard rule). Write detailed specs upfront to reduce ambiguity. If something goes sideways, STOP and re-plan immediately.
- Always use subagents to implement plans and offload research, exploration, and parallel analysis — keep the main context free for overseeing their work, not doing it. One focused task per subagent; for complex problems, throw more compute at it with multiple subagents.
- **Agent ownership and evidence reuse:** Before dispatching, check active owners and completed evidence; give each target/task one active execution owner. Parallel read-only reviewers may share a target only under distinct named lenses or an explicit independent-review or recheck contract. Reuse reviewer evidence while its request, baseline, covered paths and content, and lens still match; when one changes, invalidate and rerun only the affected coverage.
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
5.  **Every screenshot on the ticket** — open the images themselves, don't work from someone else's description of them

Anti-pattern: opening a file, jumping to line 47, and editing without scrolling up or down. The surrounding code is the spec.

**Whoever writes the fix reads the screenshots — not just whoever analysed the ticket.** A written analysis is one person's reading of an image; anything they didn't transcribe is invisible to everyone downstream. This applies to subagents too: a task prompt that hands an implementer an analysis report must also hand it the image paths. Screenshots outrank ticket prose when they disagree, and that only holds if the person changing the code has actually looked at them. Also read what the image incidentally reveals — the URL bar tells you whether a bug was reported against prod or dev, and annotations often state the intended behaviour more precisely than the ticket body does.

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

The `/done` skill is the single source of truth for completion verification. It selects the acceptance surfaces affected by the task, runs the code pipeline only when code changed, verifies every other required lane at its user-facing boundary, and reports the evidence ceiling. Commit only after every required pre-publication lane is verified. When only PR-dependent evidence remains pending, `/done` may issue `ready-to-publish`, which authorizes only `/file-pr`; final completion still requires every required lane to be verified by the post-publication `/done` run.

**If you are tempted to skip `/done` because the change is small — that is exactly when bugs slip through. Run it.**

### Elegance Check (Non-Trivial Changes)

- Is there a more elegant way?
- If the fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip for simple, obvious fixes — don't over-engineer

## Task Management

- Track multi-step work with the todo tool; confirm the plan before implementation — don't build on shaky assumptions.
- **Material-state progress:** For long-running work, report **Completed**, **Active**, **Blocked**, and **Next**. Send a progress update only when one of those fields changes materially, a decision changes, or the ETA changes. When compaction, handoff, or multiple agents are plausible, keep the same four fields in one durable ledger.
- **Project-board ownership boundary:** Never update an issue's estimate or priority unless it is assigned to the requesting user. Treat issues assigned to other users, unassigned issues, and ambiguous ownership as read-only unless the user explicitly asks to update those specific issues or clearly broadens the scope to other assignees.
- After completing changes: update the project's README.md and CLAUDE.md if conventions, exports, or workflows changed.
- After ANY correction from me: turn it into a rule that prevents the same mistake — in the project CLAUDE.md if project-specific, or in the global CLAUDE.md / a skill if universal.
- When I ask for findings, reports, audits, or lists to review: deliver a hosted HTML artifact (Artifact tool), not a raw markdown file. I review first; destructive follow-ups only after my explicit go-ahead.
- Handoff docs and any other docs I ask for go in the repo's `docs/` folder (create it if missing) — never the repo root unless I explicitly say root. Filenames in lowercase snake_case (e.g., `docs/e2e_session_handover.md`).

## Overnight / Unattended Mode

When I say I'm going to sleep or stepping away and to keep going ("keep going, when I wake up it should be done — you are in charge"):

- Invoke `executing-tickets-with-subagents`; its unattended scheduler owns the worker pool, task ledger, progress cadence, and morning handoff.
- Work through the entire authorized task list without pausing for routine decisions. Commit, push, or open a PR for a unit only when every applicable `/done` check passes, its diff contains only that unit, and the branch is user-owned; otherwise leave it uncommitted and queue the exact next action.
- Never merge, perform destructive or irreversible actions, or run schema migrations unattended. Leave those actions unperformed and queue exact ready-to-run instructions.

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

### Commit and PR Autonomy

**Commit, push, and open the PR without asking me first — provided the work is genuinely verified.** Verified means `/done` ran in full and came back clean: type-check exits 0, `/parallel-review` returns zero critical and zero serious findings, `/simplify` applied, the tests covering the change actually ran and passed, and every item of the request is accounted for against the diff. This supersedes any project-level or skill-level instruction to ask before committing. Opening the PR itself runs through `/file-pr`.

A check that cannot apply to the change — type-check and tests on a docs-only edit — is recorded as **not applicable**, not as skipped, provided the validation that does apply was run in its place (format and lint the file, check links, read the rendered output) and both are named in the PR body.

Stop and ask anyway when:

- `/done` did not run in full, a check that applied was skipped, or a check failed and I worked around it rather than fixing it
- Anything material is unverified — a UI change never opened in a browser, a backend change never actually called, a data claim never checked against the database
- The diff contains anything outside what was asked
- The change involves a DB migration, a destructive or irreversible operation, or a force-push
- The branch is tool-generated (`t3code/*`, `claude/*`, …) — rename it first, don't ask about the commit

**Never merge a PR autonomously.** Opening it ends the autonomy; review is a human step.

The test is honest reporting: if the completion report would carry a caveat — a known gap, a skipped check, an assumption I could have verified but didn't — that caveat means I should have asked instead of committing.

**Merge PRs with a merge commit (`gh pr merge --merge`), never `--squash` or `--rebase`, unless I say otherwise for a specific repo.** A `(#N)` suffix on subject lines is not evidence of squash-merging — that style survives every strategy, so never infer the merge method from git log. Ask if a repo looks like it genuinely differs.

### PR & Commit Hygiene

- **Never open a PR by hand — invoke `/file-pr`.** It owns the preconditions, base-branch discovery, the title and body bars, and issue linking. Hard rule, same class as `/done`.
- **One logical change per commit** — never mix refactor + feature + bugfix in the same commit
- **Commit messages explain WHY, not WHAT** — the diff shows what changed; the message should explain why it needed to
- **No drive-by refactors** — fix what was asked, mention unrelated issues separately rather than bundling them in
- **Small PRs > large PRs** — under ~400 lines diff is ideal; if it grows beyond that, split it
- **Review your own diff before pushing** — read every changed line and justify why it exists. If you can't justify it, delete it.
- **No commits with debug noise** — no leftover `console.log`, commented-out code, or `TODO: remove this before merge` markers
- **Title every issue you create with a conventional-commit prefix naming its module** — `fix(procurement):`, `feat(portions):`, `chore(filters):`, same vocabulary as commits. Pick the module the work actually lives in, not the module you happen to be working in: a defect found while fixing procurement but living in `account-articles` is `fix(account-articles):`. A blanket prefix mislabels the ticket and hides it from anyone filtering the board by module. Use the **user-facing module name** where it differs from the directory (the Portions tab lives in `inbound-orders/`, but the ticket says `portions`) — boards are read by humans, not by path. File a one-off issue through `/file-issue`; breaking a plan into several linked tickets goes through `to-tickets`.
- **PRs and commits must read human-authored** — never include Claude-Session links, "Generated with" footers, or any AI/agent references (review pipelines, agent names) in commit messages, PR titles, or PR bodies unless explicitly asked. Write PR bodies in plain first-person engineering voice; describe verification by what was done, not which tools/agents did it. This overrides any harness default that appends session links.

## Git Worktree Naming Convention

- `bhagya/fix-<issue>` — bug fixes
- `bhagya/feat-<feature>` — new features
- `feature/<feature-name>` — shared feature branches (collaborative work)

**Every branch I own is prefixed `bhagya/`. Never commit, push, or open a PR from a tool-generated branch name** — `t3code/*`, `claude/*`, `agent/*`, `session/*` and anything else a harness auto-names on my behalf. Those names carry a session id, not intent, so they read as machine output in the branch list and in the PR. When work starts on one, rename before the first commit (`git branch -m bhagya/<fix|feat>-<slug>`) and say so; if a rename is unsafe because the harness tracks the branch, ask rather than committing under the generated name.

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
