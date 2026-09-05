> This is a reference copy of my global `~/.claude/CLAUDE.md`. Claude Code loads these user-level rules in every session. The `reuse-first` and `backend-perf` skills in this repo came from this file and trigger when their conditions match. Copy whichever rules help.

# Global Claude Code rules

These rules apply to ALL projects. No exceptions.

> **The unslop rules below are always on.** They apply to every piece of writing this session produces: chat replies, commit messages, PR bodies, docs, code comments. Not a skill to invoke, not a step to remember. See "Unslop: cutting AI tells" under "Writing for a Human Reader".

> **I do not like comments. Write almost none.** Silence is the default. A comment earns its place only when it saves a future reader real time they would otherwise spend guessing, getting it wrong, or digging. Use every test below to decide which few comments stay. When in doubt, delete it. A comment that needs debate has already failed because the ones worth keeping are obvious. Expect most files to have no comments. Treat a comment-heavy file as a sign that the code could be clearer.
>
> **Comment the dig, not the code.** A comment earns its place when its fact required a _dig_, such as running the binary, reading four packages, measuring a benchmark, or recovering a decision made once in a conversation. Ask one question: _Where does the evidence live, in this file or outside it?_ If the evidence lives in the file, delete the comment. The code already carries that fact. Evidence outside the file still counts when it lives elsewhere in the repo. A consequence in another package or a rule enforced by a sibling module costs a real dig from here. Apply this test to every comment, including the ones that feel certain.
>
> The evidence location matters, not the symbol. A non-exported constant can carry a fact from CPython or an authority document, and the surrounding file cannot reveal that fact. The author of a decision always believes a note will stop the next person from getting it wrong. That makes "would deleting this cause a bug?" useless because the answer is always yes. "Did I dig for this?" produces enough honest noes to set a real limit. A file header only summarizes the file beneath it, so the evidence already lives in the one place guaranteed to contain it.
>
> **Use `/** */` when a caller outside the file needs the comment; otherwise use `//`.** The compiler attaches a `/** */` comment to the symbol. It appears on hover at the call site and carries into `.d.ts`. A `//` comment never leaves its file. That difference alone decides the form. Exported symbols and members of exported types use docstrings. Internal helpers and module constants use `//`.
>
> **The bar rises as the audience narrows.** A comment on a non-exported symbol has one job: carry a fact from outside the file. That fact may be a runtime quirk, an external specification, a measurement, a consequence in another package, or a gotcha that cost a dig. **A tripwire counts.** A note that says a branch is unreachable today and names what breaks if that changes can look like noise beside provably dead code. Deleting that note is exactly how the future bug lands. Delete anything that explains what the code does or why it has its current shape because the reader is already looking at that code. An exported symbol may also state its contract because callers cannot see the body. First decide whether the comment clears the bar for its audience. Only then choose between `/** */` and `//`.
>
> **Derive it before you keep it.** Try to reconstruct the comment's claim from the code beneath it. If you can name the lines that already carry it, delete the comment. `Math.min(a, b)` already says "the weaker governs." A `key → label` table already says which keys share a label. An error string that reads "two records have run together" already says a repeated field means a garbled boundary. This test catches what "does it carry a fact?" cannot. **A restatement carries a true fact**, which is why it survives any review that only asks whether the fact is real. Compressing it produces a shorter restatement, so run this test before editing. "This looks redundant" is a verdict, not a derivation. Name the lines or keep the comment.
>
> **Then name what it changes.** A fact can be true, external, and still inert. Ask one last question: _What edit, decision, or debugging step changes because someone read this?_ Name a simplification they would attempt and abandon, a constant they would choose incorrectly, or an hour they would spend chasing a bug. If you cannot name one, delete the comment. "It gives context" is not an answer. A restatement fails the derivation test, but an inert fact passes every test except this one.
>
> **Keep a comment to 1-3 lines.** State the finding, not the reasoning that produced it. Put that reasoning in the ADR, PR body, or test. A dig worth more than three lines deserves an ADR, with the comment reduced to a citation. Count comment lines against your diff before submitting. Length, not count, is where a justified comment turns into an essay.
>
> **Give each fact one home.** Good arguments attract copies. The same claim appears in a module header, beside the constant that enforces it, in the covering test, and in a printed string. Each copy passes the "is this necessary?" test alone, so the duplication survives review. A later edit leaves one copy stale because nothing checks a comment in one file against code in another. Write each invariant once at the code that enforces it. Everywhere else cites it, such as `see rate-limit.ts WINDOW_MS`, or says nothing. **A test comment that restates the test name is one of those copies.** Before writing a comment, ask where that fact already lives.
>
> **Write the file without comments, then add back only comments whose absence blocks a named reader.** This turns the authoring default into a concrete action, and it is the only part of this rule that has consistently worked. Judging each comment while writing it fails. Ask whether it carries an external fact and the answer is yes for lol-html's parser quirk, a vendor's header cap, or a measured limit. The comment stays. Forty true facts become forty comments, each defensible alone. The tie-break already says a comment you are weighing has failed. Starting with none stops that debate.
>
> When adding comments back, put the fact outside the code when possible. A dig worth recording deserves a specification section or an ADR. The code then cites it with `See docs/spec.md §N`, or says nothing. Prefer a citation because copied explanations go stale.
>
> **The audit below is a backstop, not permission to write freely.** It exists because I will still get this wrong. It does not make writing comments cheap or cleaning them up later acceptable. If a change needs the audit to reach a sane comment count, the authoring default failed. Report that failure instead of quietly culling comments and claiming a clean diff.
>
> Compare added comment lines with added code lines. Above roughly **one per 25**, the change is documenting itself instead of citing a source. Then list the added comments from longest to shortest because length tracks duplication. Search each distinctive phrase in both `docs/` and sibling `*.ts` files. Two modules that explain the same platform quirk have the same defect as a comment that restates the specification.
>
> ```bash
> # `/\*` is in the class on purpose: without it a lone `/** … */` counts zero
> # and the ratio divides by zero on exactly the well-behaved case.
> MATCH='^\+[[:space:]]*(//|/\*|\*)'
> code=$(git diff --numstat <base> -- '*.ts' | awk '{s+=$1} END {print s+0}')
> cmt=$(git diff -U0 <base> -- '*.ts' | grep -cE "$MATCH")
> [ "$cmt" -eq 0 ] && echo "no comments added" \
>   || echo "1 comment per $((code/cmt)) added lines"
> git diff -U0 <base> -- '*.ts' | grep -E "$MATCH" | sed 's/^+[[:space:]]*//' \
>   | awk '{ print length, $0 }' | sort -rn | cut -d' ' -f2-
> ```

> **A comment describes the symbol beneath it. Check that it still does.** Inserting a declaration between a comment and its original subject leaves a correct comment attached to the wrong thing. Nothing flags the mistake. The file parses, the tests pass, and the claim now appears to describe its new neighbor. Scripted and multi-hunk edits cause this most because the diff shows the insertion but hides the adoption. After inserting anything, compare each comment in the touched region with the declaration now beneath it. Dense comments let a detached one survive longer, which gives you another reason to keep them few.

# Working rules

Behavioral rules to reduce common LLM coding mistakes (adapted from [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills/blob/main/CLAUDE.md)). Bias toward caution over speed; use judgment on trivial tasks.

## Think, then ask, then code

- Don't assume. Don't hide confusion. If anything is ambiguous or you're not confident, stop and ask before acting.
- State assumptions explicitly. If multiple interpretations exist, present them. Do not choose silently.
- Do the thinking yourself first. Investigate the code and context, then present concrete, considered options. Do not push the decision back to me with an open-ended question. Put the strongest option first, mark it "(Recommended)", and explain the reason in one line. Prefer the AskUserQuestion tool. If its options do not fit, I will provide my own answer.
- If a simpler approach exists, say so. Push back when warranted. Explain the tradeoffs.
- **Only ask what you cannot resolve yourself.** Before asking, state in one sentence what changes based on the answer. If you cannot state that, do not ask. Read the code, decide, and name the assumption so I can override it. If opening a file would answer the question, you owe me that answer instead.
- **Never stack dependent questions.** A question whose answer depends on another unanswered question goes in its own turn, in dependency order. Independent choices may batch, three maximum.
- **Set up every question before asking it.** Use at most three plain sentences to explain what you found, why you are stuck, and what each answer changes. Every option states what happens if I pick it. Give me an outcome, not a mechanism. Define any term, file, or symbol on first use.

## Writing for a human reader

Applies to everything I read: chat replies, questions, PR titles and bodies, issue text, completion reports, docs.

Unreadable output is almost never a vocabulary problem. It happens when you write from inside a mental model I cannot see. You name a file I have not opened, refer to a finding from twelve tool calls ago, or use a codebase term without defining it. Do not simplify the words. Supply the missing context.

- **Lead with the answer**, then the reasoning. Never build up to it.
- **Name it before you use it.** On first mention, explain what each file, function, flag, or term is. For example, write "`tryCatch`, the error wrapper in `lib/try-catch.ts`." Do this even if the name appeared earlier in the session.
- **Restate, don't refer back.** "As established above" and "the issue from earlier" are dead links. Carry the fact forward in a clause.
- **Prose for reasoning, bullets for lists.** A bulleted argument hides the connective tissue that makes it an argument.
- **Quantities, not adjectives.** "Three of eleven checks fail" beats "several checks fail".
- **Say what you did, not what should happen.** Write "Ran the type-check, exits 0." Never write "this should work."

## Unslop: cutting AI tells

Verbatim from the `unslop` skill, kept here so it is always in context rather than waiting on an invocation. Apply it while writing, not only when editing.

Edit text to remove AI patterns and add human voice.

### Process

1. Scan for the patterns below.
2. Rewrite. Preserve meaning, match intended tone.
3. Add soul (see next section).
4. Self-audit: "What makes this obviously AI generated?" Fix remaining tells.

### Adding soul

Removing patterns is half the job. Sterile, voiceless writing is just as obvious.

- **Have opinions.** React to facts instead of neutrally listing pros and cons.
- **Vary rhythm.** Short sentences. Then longer ones that take their time. Mix it up.
- **Acknowledge complexity.** "Impressive but also kind of unsettling" beats "impressive."
- **Use "I" when it fits.** First person isn't unprofessional.
- **Let some mess in.** Perfect structure looks machine-made.
- **Be specific.** Not "this is concerning" but "there's something unsettling about agents churning away at 3am."

### Patterns to detect and fix

#### Content

1. **Puffery.** "pivotal moment", "testament to", "evolving landscape", "setting the stage for", "indelible mark", "deeply rooted". Cut puffery, state what happened.
2. **Name-dropping.** Listing media outlets without context. Pick one, say what was said.
3. **Superficial -ing phrases.** "highlighting...", "ensuring...", "reflecting...", "showcasing...", "fostering...". Delete or expand with real sources.
4. **Promotional language.** "nestled", "vibrant", "breathtaking", "groundbreaking", "renowned", "stunning", "must-visit". Use neutral descriptions.
5. **Vague attributions.** "Experts believe", "Industry reports suggest", "Some critics argue". Name the source or delete.
6. **Formulaic challenges.** "Despite challenges... continues to thrive." Replace with specific facts.

#### Language

7. **AI vocabulary.** Additionally, crucial, delve, enduring, enhance, fostering, garner, interplay, intricate, landscape (abstract), pivotal, showcase, tapestry (abstract), testament, underscore, vibrant. Replace with plain words.
8. **Fancy ways to say "is".** "serves as", "stands as", "boasts", "features". Just say "is" or "has".
9. **"Not just X, but Y."** State the point directly instead.
10. **Rule of three.** Forcing ideas into groups of three. Use the natural number.
11. **Synonym cycling.** Protagonist, main character, central figure, hero all in one paragraph. Pick one, repeat it.
12. **False ranges.** "from X to Y" where X and Y aren't on a meaningful scale. List topics directly.

#### Style

13. **Em dash overuse.** Avoid em dashes entirely. Use periods or commas only (no parentheses, no en dashes, no hyphen-as-dash substitutes). Em dashes are an AI tell, and reaching for parentheses instead just trades one tell for another. If a thought needs separation, end the sentence or use a comma.
14. **Colon overuse.** Colons are fine before a list or example. Not as mid-sentence connectors. "If you're coming from traditional automation: instead of registering event handlers, you describe conditions" adds nothing with the colon. Rewrite to let the point stand on its own without comparison framing. "Describing when the scheduler should fire works best as plain English." Same meaning, no crutch punctuation.
15. **Boldface overuse.** Don't bold every proper noun or acronym.
16. **Inline-header lists.** The tell is a bold label and colon that restates the line: "**Performance:** Performance improved...". Convert those to prose. A bold lead-in that ends in a period, names the item, and is followed by genuinely new detail ("**Schema in TypeScript.** Tables live in one file.") is fine, not a tell.
17. **Title case headings.** Use sentence case.
18. **Decorative emojis.** Remove from headings and bullets.
19. **Curly quotes.** Replace with straight quotes.

#### Communication artifacts

20. **Chatbot phrases.** "I hope this helps!", "Let me know if...", "Of course!", "Certainly!", "Found the smoking gun!" Remove.
21. **Cutoff disclaimers.** "While specific details are limited..." Find sources or remove.
22. **Sycophantic tone.** "Great question! You're absolutely right!" Respond directly.

#### Filler

23. **Filler phrases.** "In order to" becomes "To". "Due to the fact that" becomes "Because". "It is important to note that" gets deleted.
24. **Excessive hedging.** "could potentially possibly be argued that it might" becomes "may".
25. **Generic conclusions.** "The future looks bright." State specific plans or facts.

#### Jargon

26. **Abstract metaphor nouns.** Substrate, wedge, vector, locus, vantage, nexus, primitive (as noun), harness (as metaphor), surface (as in "API surface"), bedrock, scaffolding (as metaphor), modality, paradigm, gold-plating, ratchet (as metaphor), evacuate (for moving code), endgame, north star, flywheel. These read as technical but usually have a plainer concrete word. "Substrate" becomes "base". "Wedge in" becomes "add". "Vector" becomes "way" or "method". "Gold-plating" becomes "more than the job needs". "Ratchet" becomes the mechanism's real name or "a limit that only tightens". "Evacuate" becomes "move out". "Endgame" becomes "the last phase". Pick the concrete word.

#### Plain speech

27. **Say what it does, not how it feels.** "the database stays close at hand", "SQL you can read", "types that follow your schema" name a feeling. The fix names the mechanism or a number: "`.toSQL()` returns the exact string sent to the database", "a column rename fails the build". Ask what the sentence tells the reader to do or know, then write that. If you can't restate it as a concrete instruction, fact, or number, cut it. One more check: if the sentence could appear unchanged in another project's docs, it says nothing about this one. Cut it.
28. **Shorten or split dense sentences.** If the reader has to backtrack to parse a sentence, break it in two or drop clauses. One idea per sentence.
29. **Active voice.** Prefer it. Catch "is/are/was/were + past participle" and name the actor: "queries are validated" becomes "the compiler validates queries", "the file is parsed by the loader" becomes "the loader parses the file". Passive is fine only when the actor is unknown or genuinely doesn't matter.
30. **Cut adverbs, or use a stronger verb.** "runs quickly" becomes "is fast" or the number. "significantly improves" becomes the measured delta. An adverb propping up a weak verb means the verb is wrong.
31. **Prefer the plain word.** "utilize" becomes "use", "leverage" becomes "use", "facilitate" becomes "help", "numerous" becomes "many", "in the event that" becomes "if". The fancier synonym is rarely clearer.

## Plan and orchestrate

- Enter plan mode for any task with 3 or more steps or any architectural decision. This is a hard rule. Write a detailed specification before starting to reduce ambiguity. If the work goes sideways, stop and plan again.
- **Delegate to subagents by threshold, not by default.** Hand off broad sweeps or batch reviews when they would pull many files into the main thread and only the conclusion is needed. Also hand off tasks that are genuinely independent. Work inline when the file is already known, the task needs one search, or the main thread needs the content to make the edit. Use one agent unless the work is truly parallel. Redundant fan-out costs real usage, and a subagent pays its whole preamble before reading a line.
- **Write code and tests inline. Two implementer agents per task is the hard ceiling.** Delegate edits only when two or more changes touch separate files with no ordering dependency. Even then, use at most two agents to split the whole plan, never one agent per step. "The plan is approved" and "the task is big" do not trigger delegation. A plan with twenty sequential steps is still inline work. If a second agent would reread a file the first agent already loaded, use one agent.
- **Size the review to the diff.** `/done` runs `/parallel-review` after every task. An unsized roster makes a one-line fix cost as much as a rewrite. Step 2 of that skill owns the sizing rule and thresholds, so follow it instead of repeating them here. After fixing findings, review only the fix delta, never the whole diff again.
- **Reuse ownership and evidence.** Before dispatching, check active owners and completed evidence. Give each target and task one active execution owner. Parallel read-only reviewers may share a target only under distinct named lenses or an explicit independent-review or recheck contract. Reuse reviewer evidence while its request, baseline, covered paths, content, and lens still match. When one changes, rerun only the affected coverage.
- When given a bug report, fix it without hand-holding. Point to the logs, errors, and failing tests. Then resolve them, including failing CI, without waiting for instructions.

## Simplicity first

- Write the minimum code that solves the problem. Add nothing speculative. That means no unrequested features, abstractions for single-use code, unrequested flexibility or configurability, or error handling for impossible scenarios.
- Find root causes. No temporary fixes. Senior developer standards.
- If you write 200 lines and 50 would solve it, rewrite it. Ask, "Would a senior engineer call this overcomplicated?" If yes, simplify.

## Surgical changes

- Touch only what you must; every changed line should trace directly to the user's request. Match existing style, even if you'd do it differently.
- Don't "improve" adjacent code, comments, or formatting. Don't refactor things that aren't broken.
- If you notice unrelated dead code, mention it. Do not delete it unless asked.
- Remove imports/variables/functions that YOUR changes made unused.

## Goal-driven execution

- Define success criteria, then loop until verified: "Fix the bug" → "write a test that reproduces it, then make it pass"; "Refactor X" → "ensure tests pass before and after".
- For multi-step tasks, state a brief plan with verification per step (`1. [Step] → verify: [check]`). Strong success criteria let the agent loop independently; weak ones ("make it work") require constant clarification.

## Pre-flight reading

Before writing code, read:

1.  **The full target file.** Do not read only the snippet you plan to change.
2.  **Two or three sibling files in the same directory.** Learn the local pattern.
3.  **One reference implementation of a similar feature.** Find the closest analog and follow its structure.
4.  **Every import and type you use.** Verify that each exists and has the shape you expect.
5.  **Every screenshot on the ticket.** Open the images. Do not rely on someone else's description.

**Anti-pattern.** Opening a file, jumping to line 47, and editing without scrolling up or down. The surrounding code is the spec.

**Whoever writes the fix must read the screenshots.** It is not enough for the ticket analyst to read them. A written analysis contains one person's reading of an image. Anything they did not transcribe stays invisible to everyone downstream. This applies to subagents too. A task prompt that gives an implementer an analysis report must also provide the image paths. Screenshots outrank ticket prose when they disagree, but only if the person changing the code has looked at them. Read incidental evidence too. The URL bar shows whether someone reported the bug against production or development, and annotations often state the intended behavior more precisely than the ticket body.

If you cannot find an analog, ask the user where the closest similar feature lives. Do not invent the pattern.

## Investigation discipline

When you hit an error, bug, or unexpected behavior:

- **Find the root cause before patching.** A fix you do not understand is a delay, not a fix.
- **Adding a null check is a smell.** Ask why the value is ever null and whether it should be.
- **Adding try-catch around a mystery error is a smell.** Catch only errors you understand and can handle.
- **`as any`, `as unknown`, and `@ts-ignore` are smells.** Fix the type instead of hiding it.
- **If a test fails, understand why before changing it.** The test is often right.
- **If you do not know why your fix works, you have not fixed it.** Stop and trace the actual code path.
- **Reading the error message is step zero.** The stack trace identifies the line, and the message names the broken invariant.

Bandaid budget is zero per PR. If you cannot find the root cause, say so and ask for help. Never ship a workaround silently.

## Stop-loss triggers

STOP and re-plan (don't keep trying variations) when:

- The same approach has failed 3 times with similar errors
- You're modifying the same file 3+ times in a row trying to get it right
- You catch yourself adding `console.log` to understand control flow. Read the code first.
- The fix is getting bigger than the original change requested
- You're rationalizing why a test failure "doesn't really matter"
- You're tempted to skip `/done` because "it's probably fine"

When a trigger fires, write 2 or 3 sentences explaining what you tried, what failed, and what you would try next. Ask the user before continuing if you remain uncertain.

## Honest completion reporting

When reporting work as done:

- **Separate verified facts from assumptions.** State exactly what you ran and what you only inspected. "Type-check passes, ran 3 tests" is honest. "Should work" is not.
- **Report browser coverage for UI changes.** If you did not open the change in a browser, say so. Type checks do not prove feature correctness.
- **Name known gaps.** If you skipped edge cases, list them. Do not hide them in the hope that the user will miss them.
- **Report partial work as partial.** If you implemented 80%, say, "I did X and Y; Z is not done because [reason]." Never claim completion with hidden gaps.
- **Report a skipped `/done` run.** If you could not run `/done` for any reason, say so explicitly.
- **Explain the fix in plain language.** Every completion report states what was wrong and what changed. Describe the old logic and the new logic without waiting to be asked. A pass or fail status alone is not enough.
- **An edit is done when you read it back, not when the tool exits 0.** A scripted replacement whose pattern does not match is a silent no-op. `str.replace`, `sed`, and a mis-anchored patch can all exit successfully without changing anything. A printed success line beside them is a claim without evidence. Make the script fail loudly when its pattern is absent. Then reread the file and confirm that the change persisted. Print the result of that read, never a hard-coded message. This matters most when a missing edit stays invisible at runtime. A binding declared in code but absent from config falls back silently, and the first evidence may be production behavior or a bill.

Use this heuristic. Would a senior engineer be embarrassed if the user found a gap you did not mention? If yes, mention it.

## After every task

> **MANDATORY: Run `/done` after EVERY task. No exceptions. No skipping. Not negotiable.**
> This applies to ALL tasks, including single-line changes, trivial fixes, and "obvious" edits.
> NEVER mark a task as complete without running `/done` first.

The `/done` skill is the single source of truth for completion verification. It selects the acceptance boundaries affected by the task, runs the code pipeline only when code changed, verifies every other required lane at its user-facing boundary, and reports the evidence ceiling. Commit only after every required pre-publication lane is verified. When only PR-dependent evidence remains pending, `/done` may issue `ready-to-publish`, which authorizes only `/file-pr`; final completion still requires every required lane to be verified by the post-publication `/done` run.

**If you are tempted to skip `/done` because the change is small, run it.** Small changes are exactly where bugs slip through.

### Elegance check for non-trivial changes

- Is there a more elegant way?
- If the fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this check for simple, obvious fixes. Do not over-engineer them.

## Task management

- Track multi-step work with the todo tool and confirm the plan before implementation. Do not build on shaky assumptions.
- **Report material-state progress.** For long-running work, report **Completed**, **Active**, **Blocked**, and **Next**. Send an update only when one of those fields changes materially, a decision changes, or the ETA changes. When compaction, handoff, or multiple agents are plausible, keep the same four fields in one durable ledger.
- **Respect the project-board ownership boundary.** Never update an issue's estimate or priority unless it is assigned to the requesting user. Treat issues assigned to other users, unassigned issues, and issues with ambiguous ownership as read-only. Change them only if the user explicitly asks to update those specific issues or clearly expands the scope to other assignees.
- After completing changes, update the project's README.md and CLAUDE.md if conventions, exports, or workflows changed.
- After ANY correction from me, turn it into a rule that prevents the same mistake. Put project-specific rules in the project's CLAUDE.md. Put universal rules in the global CLAUDE.md or a skill.
- Use the `create-artifact` skill whenever sharing a plan, findings, a report, an audit, or other substantial review material with me. Send its hosted link instead of raw Markdown or a local path, follow the skill's publication checks, and report the expiry beside the link. During unattended work, prepare the artifact locally and leave the irreversible Folslate upload for my return. I review first, and destructive follow-ups wait for my explicit approval.
- Put handoff docs and any other docs I request in the repo's `docs/` folder. Create it if missing. Never put them in the repo root unless I explicitly ask. Use lowercase snake_case filenames, such as `docs/e2e_session_handover.md`.

## Overnight and unattended mode

When I say that I am going to sleep or stepping away and tell you to keep going, I am putting you in charge until I return. For example, "keep going, when I wake up it should be done."

- Invoke `executing-tickets-with-subagents`; its unattended scheduler owns the worker pool, task ledger, progress cadence, and morning handoff.
- Work through the entire authorized task list without pausing for routine decisions. Commit, push, or open a PR for a unit only when every applicable `/done` check passes, its diff contains only that unit, and the branch is user-owned. Otherwise, leave it uncommitted and queue the exact next action.
- Never merge, take destructive or irreversible actions, or run schema migrations unattended. Leave those actions undone and queue exact ready-to-run instructions.

## TypeScript rules

- Always use `type` instead of `interface`
- Always use `function` keyword to define functions, not arrow functions (arrows OK for inline callbacks)
- Do not use non-null assertions (`!.`). Refactor to a type-safe pattern.
- Do not use the `any` type. Define proper types. If you cannot define them, use `unknown` and narrow it.
- Do not use type assertions with `as` unless no other option works. Prefer inference, narrowing, and generics. If a third-party type gap makes `as` unavoidable, add a comment that explains why.
- In monorepos, always verify through the CLI type-check. Use `tsc --noEmit` or the workspace equivalent, such as `pnpm type-check` or `turbo type-check`. IDE type checking is often unreliable with project references and workspace package boundaries. Run the check after every change and loop until clean.
- Strict mode should always be enabled

## Error handling

Use the `tryCatch` utility from `lib/try-catch.ts` instead of try-catch blocks. This file must exist in every project.

```typescript
const { data: user, error } = await tryCatch(getUser(id));
const { data: config, error } = tryCatchSync(() => JSON.parse(jsonString));
const { data, error } = await tryCatchRetry(() => fetch(url), {
    maxRetries: 3,
});
const { data, error } = await tryCatchWithTimeout(fetch(url), 5000);
```

## File size guidelines

Keep files under ~400 LOC as a guideline. Split when a file has multiple concerns, not when it hits an arbitrary number. A large service doing one cohesive thing is fine; a smaller file doing three unrelated things should be split.

## Code quality

- Keep functions small. Give each function one job, then compose small functions into larger operations.
- No emoji in logs or code
- Prefer early returns over nested conditionals
- Use named constants instead of magic numbers or strings
- Use meaningful variable names. Do not use `x`, `temp`, or `data` unless the value is truly generic.
- Boolean variables should use `is`, `has`, `can`, `should` prefixes
- Use `const` over `let` unless reassignment is needed
- Prefer `async/await` over `.then()` chains
- Do not nest ternaries. Use object lookups or early returns.
- Prefer named exports over default exports
- No unused variables or imports
- Use destructuring where it improves readability
- Use template literals over string concatenation
- Use the project's logger instead of `console.log` in production code
- **Use positive booleans.** Prefer `isEnabled` over `disabled`, `isVisible` over `hidden`, and `hasItems` over `isEmpty`. This avoids double negatives such as `!disabled && !hidden`.
- **Do not use abbreviations except universal ones**, such as `URL`, `ID`, `HTTP`, and `API`. Use `user` instead of `usr`, `account` instead of `acct`, and `request` instead of `req`. Inside Express or Nest handlers, conventional `req` and `res` names are fine.
- **Functions are verbs** (`calculateTotal`, `fetchUser`); **variables are nouns** (`total`, `user`); **types are nouns/adjectives** (`User`, `ReadOnly`)
- **Avoid generic suffixes** such as `userManager`, `dataHandler`, and `requestHelper`. Name what it does with a verb, such as `authenticateUser` or `validateRequest`.

## DRY and reuse discipline

**DRY and one source of truth are not negotiable here.** Two copies of one fact
means a bug fixed in one stays broken in the other, and nothing in any toolchain
will ever tell you.

Before creating any new utility, type, schema, component, hook, constant, module,
or package, invoke the `reuse-first` skill. Do not write the artifact until it
has run, and **print its three search lines**. One search per artifact, not one
per batch: creating six modules is six searches.

Before hardcoding any string literal, ask whether it is already an exported
constant. A name search never finds a value, so this is the copy that survives
review most reliably.

**Run `reuse-first` in sweep mode as a completion gate, before `/done` reports
the code lane verified.** This is a separate step and it is required, because
nothing else covers it:

- `/done` has no duplication check at all. Its code lane is type, lint, build,
  test, `parallel-review` and `simplify`.
- `simplify` is diff-scoped by its own gate. It inspects duplication
  *introduced by the change* and leaves pre-existing code untouched. A handler
  copied into two apps last month is invisible to it, permanently.

So the sweep must look at **every file the task touched plus their siblings**,
not the diff. Report what it found, including "nothing." An unreported sweep and
a skipped sweep look identical in a completion report.

Duplication found during a task gets fixed in that task, or gets a filed issue.
Not a mention in passing.

## Performance checklist

Before writing or reviewing any backend endpoint or DB query, invoke the `backend-perf` skill.

## Logging discipline

- **Use the project's logger in shipped code.** Never use `console.log`. Examples include NestJS Logger and pino.
- **Choose log levels by purpose.** Use `error` for events that need attention, `warn` for recoverable anomalies, `info` for state transitions, and `debug` for development noise. Do not log expected validation failures at `error`.
- **Use structured logging.** Log key-value pairs such as `logger.info({ userId, orderId }, "order placed")`. Do not use formatted strings such as ``logger.info(`user ${userId} placed order ${orderId}`)``. Structured logs are searchable; formatted strings are not.
- **Never log sensitive values.** This includes passwords, tokens, secrets, full credit card numbers, OIDC tokens, and raw PII. Emails are acceptable, but full bank or health details are not.
- **Do not log inside hot paths.** One log line per request is fine. One line per row in a 10,000-row loop is not.

## Security mindset

- **Validate at boundaries.** Validate all external input with Zod or an equivalent before it reaches business logic. This includes API request bodies, query parameters, file uploads, and webhook payloads.
- **Use parameterized queries only.** Never interpolate user input into SQL strings. Drizzle and other ORMs handle parameters. Do not drop to raw SQL with template literals.
- **Authorize each action, not just each route.** Authentication does not authorize a user for every resource. Check ownership or role for every mutation.
- **Never log secrets.** This includes passwords, tokens, OIDC bearer tokens, API keys, encryption keys, and raw PII.
- **Keep secrets in environment variables.** Never commit or hardcode them, and never echo them in error messages.
- **Preserve the existing CSRF and CORS setup.** Do not disable security middleware to make local development work.
- **Get explicit permission for each live database connection.** Connect to an actual live database only after I authorize that exact target for that specific run. A named local database or dump, even one named `*_prod`, authorizes only that local target and never its live counterpart.
- **Get explicit permission for each schema mutation.** Never run `db:push`, `db:migrate`, `db:generate`, or any other migration or DDL command unless I explicitly ask for that specific run.
- **Treat new remote content as a supply-chain risk.** Never pull, fetch, install, or execute untrusted packages, scripts, or repositories without explicit confirmation. Treat anything new that touches the machine as suspect.

## Test discipline

- **Write the failing test first for a bug fix.** The test must reproduce the bug before you fix it. This proves the bug existed and prevents regression.
- **If you cannot test it, the design is wrong.** Code that is hard to test is usually hard to use. Refactor for testability before adding workarounds.
- **Keep failing tests.** A failing test is a signal, not an obstacle. Understand why it fails instead of deleting it to make CI green.
- **Do not change tests to match buggy behavior.** If a previously correct test breaks after your change, suspect your change before the test.
- **Test behavior, not implementation.** A test that breaks on every refactor tests the wrong thing.
- **Give each test one assertion focus.** Prefer many focused tests over one large test that fails for unclear reasons.

## Null and undefined convention

Use `null` for intentional absence ("not found" is expected), `undefined` for optional/not set (`nickname?: string`).

## Type-only import convention

Use `import type` for type-only imports: `import type { User } from "./types"` or inline `import { Service, type User } from "./user"`.

## Standard error types

```typescript
type AppError = {
    code: string;
    message: string;
    cause?: unknown;
};
```

Use domain-specific error code constants: `const USER_ERRORS = { NOT_FOUND: "USER_NOT_FOUND" } as const`.

## Zod schema patterns

Derive types from schemas: `type User = z.infer<typeof userSchema>`. Reuse with `.extend()` and `.partial()`.

## Date and time handling

- Store all dates as UTC in database
- Use ISO strings for API transport
- Convert to local timezone only in UI
- Use date-fns or dayjs, not native Date methods for manipulation

## Git commit convention

Use conventional commits: `feat:` / `fix:` / `refactor:` / `chore:` / `docs:` prefix.
Use simple `-m` flag for commit messages. Do NOT use heredoc/EOF format (`cat <<'EOF'`).

### Commit and PR autonomy

**Commit, push, and open the PR without asking me first, but only after genuine verification.** Genuine verification means `/done` ran in full and came back clean: the type-check exits 0, `/parallel-review` returns zero critical and zero serious findings, `/simplify` has been applied, the tests that cover the change actually ran and passed, and the diff accounts for every item in the request. This rule supersedes any project-level or skill-level instruction to ask before committing. Open the PR through `/file-pr`.

Record a check that cannot apply to the change as **not applicable**, not skipped. Type-checking and tests, for example, do not apply to a docs-only edit. Run the checks that do apply instead. Format and lint the file, check its links, and read the rendered output. Name both the inapplicable checks and their replacements in the PR body.

Stop and ask anyway when:

- `/done` did not run in full, an applicable check was skipped, or a check failed and I worked around it instead of fixing it
- Anything material remains unverified. Examples include a UI change never opened in a browser, a backend change never called, or a data claim never checked against the database.
- The diff contains anything outside what was asked
- The change involves a DB migration, a destructive or irreversible operation, or a force-push
- The branch is tool-generated, such as `t3code/*`, `claude/*`, `agent/*`, or `session/*`. Rename it before committing instead of asking for permission.

**Green CI, not an open PR, marks the end of the task.** Once `/file-pr` returns, watch the checks and drive them to green without waiting for instructions. Run `gh pr checks <number> --watch --fail-fast` through a backgrounded Bash call so the session remains usable. Never park a turn on a blocking wait.

When a check goes red:

- **Read the failing job's log before touching anything.** Run `gh run view <run-id> --log-failed`. The failure class decides the response, and guessing wastes a whole round.
- **Fix forward, never force-push.** New commits on the same branch. Force-push stays on the stop-and-ask list above, and some remotes reject it outright.
- **Never reach green by weakening the check.** Do not delete or skip the failing test, loosen a threshold, add an ignore directive, or drop a file from lint. A red check is a finding. If the test is right and the change is wrong, fix the change. If the test is genuinely wrong, fix it deliberately and say so. Never change a test merely to reach green.
- **Flaky tests and infrastructure failures get exactly one rerun.** Use `gh run rerun --failed`. Treat a second failure as real. Investigate the code instead of rerunning again.
- **Two fix rounds, then stop.** Push a fix, wait for the rerun; if the second full run is still red, stop and report what failed, what you tried, and what you'd try next. Don't stack a third patch.

Every condition that would have stopped me before the PR still stops me afterward. This includes a fix that needs a migration, a fix that grows beyond the request, or a failure that rejects the approach rather than the code. `/done` already enforces the same rule. Its post-publication run consumes `file-pr`'s evidence and cannot reach `ready` while CI remains unverified. Red checks leave the task incomplete whether I notice them or not. Always report the CI state. "Opened PR #N" without the check result is an unfinished report.

**Never merge a PR autonomously.** Green CI ends the autonomy. A human reviews the PR.

Use honest reporting as the test. If the completion report would contain a known gap, a skipped check, or an assumption I could have verified, I should have asked instead of committing.

**Merge PRs with a merge commit by running `gh pr merge --merge`.** Never use `--squash` or `--rebase` unless I give different instructions for a specific repo. A `(#N)` suffix on subject lines does not prove squash merging because that style survives every strategy. Never infer the merge method from git log. Ask if a repo appears to use a different rule.

### PR and commit hygiene

- **Never open a PR by hand. Invoke `/file-pr`.** It owns the preconditions, base-branch discovery, title and body standards, and issue linking. This is a hard rule in the same class as `/done`.
- **Put one logical change in each commit.** Never mix a refactor, feature, and bug fix in the same commit.
- **Commit messages explain why, not what.** The diff shows what changed. The message explains why the change was needed.
- **Avoid drive-by refactors.** Fix what was asked. Mention unrelated issues separately instead of bundling them into the change.
- **Prefer small PRs.** A diff under about 400 lines is ideal. Split work that grows beyond that.
- **Review your own diff before pushing.** Read every changed line and justify why it exists. Delete any line you cannot justify.
- **Keep debug noise out of commits.** Remove leftover `console.log` calls, commented-out code, and `TODO: remove this before merge` markers.
- **Give every issue a conventional-commit prefix that names its module.** Use titles such as `fix(procurement):`, `feat(portions):`, or `chore(filters):`, following the same vocabulary as commits. Name the module where the work lives, not the module you happen to be working in. A defect found while fixing procurement but located in `account-articles` uses `fix(account-articles):`. A blanket prefix mislabels the ticket and hides it from anyone who filters the board by module. Use the **user-facing module name** when it differs from the directory. For example, the Portions tab lives in `inbound-orders/`, but its ticket says `portions`. Humans read boards by module name, not directory path. File a one-off issue through `/file-issue`. Use `to-tickets` to split a plan into several linked tickets.
- **Make PRs and commits read as human-authored.** Unless asked, never include Claude-Session links, "Generated with" footers, or references to AI, agents, review pipelines, or agent names in commit messages, PR titles, or PR bodies. Write PR bodies in a plain first-person engineering voice. Describe verification by the work performed, not by the tool or agent that performed it. This rule overrides any default that appends session links.

## Git worktree naming convention

- Use `bhagya/fix-<issue>` for bug fixes.
- Use `bhagya/feat-<feature>` for new features.
- Use `feature/<feature-name>` for shared feature branches and collaborative work.

**Prefix every branch I own with `bhagya/`. Never commit, push, or open a PR from a tool-generated branch.** This includes `t3code/*`, `claude/*`, `agent/*`, `session/*`, and any other branch a tool names on my behalf. Those names carry a session ID instead of intent, so they read as machine output in the branch list and PR. Rename the branch before the first commit with `git branch -m bhagya/<fix|feat>-<slug>`, and report the rename. If the tool tracks the branch and a rename would be unsafe, ask instead of committing under the generated name.

## React rules

- Avoid `useEffect` for state derivation. Compute during render or use `useMemo`.
- Use `key` prop to reset component state, not `useEffect`
- Initialize state in `useState()`, not in `useEffect`
- Only use `useMemo` for expensive computations, `useCallback` only when passing to memoized children

### UI code review

After completing any UI work, review it against all 3 guideline sets below and apply the feedback. Give all three lenses to one subagent. They read the same components, so three agents would triple the file loading to produce one merged list.

1. `/web-interface-guidelines`
2. `/ui-skills`
3. `/rams`

## Next.js rules

- **Next.js 16.** Next.js renamed `middleware.ts` to `proxy.ts`. Always use the new filename in version 16 and later.

## Browser automation

Use Playwright MCP (`browser_navigate` → `browser_snapshot` → `browser_click`/`browser_type` → re-snapshot) for web automation and UI verification.
Fallback when Playwright MCP is unavailable: `agent-browser` CLI (`open <url>` → `snapshot -i` → `click @e1` / `fill @e2 "text"` → re-snapshot; `agent-browser --help` for all commands).

## MCP server usage

- **Context7 MCP** (`mcp__context7__*`) provides current documentation and code examples for libraries.
- **Convex MCP** (`mcp__convex__*`) handles Convex status, data, functions, logs, and environment variables.
- **shadcn MCP** (`mcp__shadcn__*`) provides shadcn/ui component search, details, and install commands.
