---
name: systematic-debugging
description: The disciplined root-cause loop to follow once you are already IN a debugging session — four phases (root-cause investigation, pattern analysis, hypothesis testing, implementation), no fix without an understood cause, evidence discipline at every component boundary, and a hard stop after repeated failed fixes. Use when about to propose or apply a fix for a bug or test failure, when a previous fix didn't work, when tempted to patch a symptom (add a null check, wrap in try-catch, bump a timeout, add a retry), or when you catch yourself guessing instead of tracing. Pairs with /diagnosing-bugs (repro + feedback-loop construction) — this skill governs fix discipline once the session is underway.
---

# Systematic Debugging

Random fixes waste time and create new bugs. Quick patches mask underlying issues. This is the discipline for the middle of a debugging session: find the root cause, prove it, fix it once.

**Pairs with `/diagnosing-bugs`, doesn't replace it** — that skill builds the repro and the tight feedback loop that makes a bug debuggable. This one governs what you do with that loop: how to investigate, when you've earned the right to propose a fix, and when to stop and question the architecture.

## The Iron Law

```
NO FIXES WITHOUT ROOT-CAUSE INVESTIGATION FIRST
```

A fix you don't understand is not a fix — it's a delay. If you can't explain why your fix works, you haven't found the cause; stop and trace the actual code path.

**Bandaid budget: zero per PR.** If you genuinely can't find the root cause, say so and ask for help — never ship a workaround silently.

## When to Use

Any technical issue: test failures, production bugs, unexpected behavior, performance problems, build failures, integration issues.

Use it ESPECIALLY when:

- Under time pressure — emergencies make guessing tempting, and systematic is faster than thrashing
- "Just one quick fix" seems obvious
- You've already tried one or more fixes and the bug is still there
- You don't fully understand the issue

Don't skip because the issue "seems simple" — simple bugs have root causes too, and the process is fast for them.

## The Four Phases

Complete each phase before the next.

### Phase 1 — Root-cause investigation

Before attempting ANY fix:

1. **Read the error message — this is step zero.** The stack trace tells you which line; the message tells you what invariant broke. Don't skip past errors or warnings; they often contain the exact answer. Read the whole trace. Note line numbers, file paths, error codes.
2. **Reproduce consistently.** Exact steps, reliable trigger. Not reproducible → gather more data, don't guess. `/diagnosing-bugs` is the playbook for building the repro loop.
3. **Check recent changes.** Git diff, recent commits, new dependencies, config changes, environment differences.
4. **Gather evidence at component boundaries.** In a multi-component system (CI → build → signing; API → service → database), don't theorize — instrument. For each boundary, log what enters and what exits, and verify env/config propagation. Run once, read the evidence, and it shows WHERE the chain breaks (secrets → workflow ✓, workflow → build ✗). Then investigate that component.
5. **Trace the data flow backward.** When the error is deep in the call stack, the crash site is a symptom. Where does the bad value originate? What called this with it? Keep tracing up until you find the source. Fix at the source, never at the crash site. Full technique under Root-Cause Tracing below.

**Symptom-patch smells** — each of these means Phase 1 isn't done:

- **Adding a null check** — ask: why is this ever null? Should it be?
- **Wrapping a mystery error in try-catch** — catch only what you understand and can handle
- **`as any` / `as unknown` / `@ts-ignore`** — fix the type, don't hide it
- **Bumping a timeout / adding a retry** — what is actually slow or racy?
- **Editing a failing test to pass** — the test is often right; understand WHY it fails before changing it. If it was right yesterday and your change broke it, your change is suspect, not the test.

### Phase 2 — Pattern analysis

Find the pattern before fixing:

1. **Find working examples.** Locate similar working code in the same codebase. What works that's similar to what's broken?
2. **Compare against references.** If implementing a pattern, read the reference implementation COMPLETELY — every line, not a skim. Partial understanding guarantees bugs.
3. **List every difference** between working and broken, however small. Don't assume "that can't matter".
4. **Understand dependencies.** What other components, settings, config, environment does this need? What assumptions does it make?

### Phase 3 — Hypothesis and testing

Scientific method:

1. **Form a single hypothesis.** State it: "I think X is the root cause because Y." Specific, not vague. Write it down.
2. **Test minimally.** The SMALLEST possible change that tests the hypothesis. One variable at a time — never multiple fixes at once, or you can't isolate what worked.
3. **Verify before continuing.** Confirmed → Phase 4. Not confirmed → form a NEW hypothesis. Do NOT stack more fixes on top of a failed one.
4. **When you don't know, say so.** "I don't understand X" beats pretending. Research more or ask for help.

### Phase 4 — Implementation

Fix the root cause, not the symptom:

1. **Failing test first.** Turn the simplest reproduction into a failing test before fixing — automated test if possible, one-off script if there's no framework. The test proves the bug existed and prevents regression.
2. **Single fix.** Address the identified root cause. ONE change at a time. No "while I'm here" improvements, no bundled refactoring.
3. **Verify.** Test passes, no other tests broken, issue actually resolved. Then run the standard verification pipeline (`/done`) before claiming the fix complete.
4. **If the fix doesn't work: STOP and count.** Fewer than 3 attempts → return to Phase 1 and re-analyze with the new information. 3+ failed attempts → do NOT attempt fix #4; question the architecture instead.
5. **3+ failed fixes = architectural problem, not a failed hypothesis.** The tells: each fix reveals new shared state or coupling somewhere else; fixes require "massive refactoring"; each fix creates new symptoms elsewhere. Stop and ask: is this pattern fundamentally sound, or are we sticking with it through inertia? Discuss with the user before attempting more fixes.

## Red Flags — Stop and Return to Phase 1

If you catch yourself thinking any of these:

- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- Changing multiple things, then running the tests
- "It's probably X, let me fix that" — without evidence
- "I don't fully understand this, but it might work"
- Listing fixes before tracing the data flow
- Rationalizing why a test failure "doesn't really matter"
- "One more fix attempt" when 2+ have already failed
- Each fix reveals a new problem in a different place

ALL of these mean: STOP. Return to Phase 1.

User signals that you're guessing — "Is that not happening?", "Will it show us...?", "Stop guessing" — mean the same thing: back to Phase 1.

## Common Rationalizations

| Excuse                                        | Reality                                                              |
| --------------------------------------------- | -------------------------------------------------------------------- |
| "Issue is simple, don't need process"         | Simple issues have root causes too. The process is fast for them.    |
| "Emergency, no time for process"              | Systematic debugging is FASTER than guess-and-check thrashing.       |
| "Just try this first, then investigate"       | The first fix sets the pattern. Do it right from the start.          |
| "I'll write the test after confirming it"     | Untested fixes don't stick. The failing test proves the bug existed. |
| "Multiple fixes at once saves time"           | Can't isolate what worked. Causes new bugs.                          |
| "Reference too long, I'll adapt the pattern"  | Partial understanding guarantees bugs. Read it completely.           |
| "I see the problem, let me fix it"            | Seeing symptoms ≠ understanding the root cause.                      |
| "One more fix attempt" (after 2+ failures)    | 3+ failures = architectural problem. Question the pattern.           |

## Quick Reference

| Phase                 | Key activities                                        | Success criteria            |
| --------------------- | ----------------------------------------------------- | --------------------------- |
| **1. Root cause**     | Read errors, reproduce, check changes, gather evidence | Understand WHAT and WHY     |
| **2. Pattern**        | Find working examples, compare completely             | Every difference identified |
| **3. Hypothesis**     | Single theory, minimal test                           | Confirmed or new hypothesis |
| **4. Implementation** | Failing test, single fix, verify                      | Bug resolved, tests pass    |

## When Investigation Reveals "No Root Cause"

If systematic investigation shows the issue is truly environmental, timing-dependent, or external: you've completed the process. Document what you investigated, implement appropriate handling (retry, timeout, clear error message) as a deliberate design decision — not a bandaid — and add monitoring/logging for the next occurrence.

But: 95% of "no root cause" cases are incomplete investigation.

## Supporting Techniques

### Root-Cause Tracing

Bugs often manifest deep in the call stack (file created in the wrong directory, database opened with the wrong path). The instinct is to fix where the error appears — that's the symptom. Trace backward until you find the original trigger:

1. **Observe the symptom** — e.g., `git init` ran in the source directory.
2. **Find the immediate cause** — the line that directly did it.
3. **Ask what called it** — walk up the chain one caller at a time.
4. **Inspect the value passed at each level** — e.g., `projectDir` was `''`, and an empty `cwd` resolves to `process.cwd()`.
5. **Find the original trigger** — e.g., a test read a fixture value before setup populated it.

Fix at the source (in the example: a getter that throws if accessed before setup), then add defense-in-depth below.

When you can't trace by reading, instrument: log directory, cwd, relevant env, and `new Error().stack` immediately BEFORE the dangerous operation (not after it fails), run once, and grep the output. In tests use `console.error` — loggers may be suppressed. For test pollution where you don't know which test is the culprit, bisect: run the suite one file at a time and stop at the first polluter.

### Defense in Depth

After fixing at the source, validate at EVERY layer the data passes through — a single check gets bypassed by other code paths, refactors, or mocks:

1. **Entry-point validation** — reject obviously invalid input at the API boundary (empty string, nonexistent path)
2. **Business-logic validation** — assert the data makes sense for this specific operation
3. **Environment guards** — refuse dangerous operations in the wrong context (e.g., refuse `git init` outside the temp dir when `NODE_ENV === "test"`)
4. **Debug instrumentation** — log context + stack before the dangerous operation for forensics when the other layers fail

Different layers catch different bypasses. One validation says "we fixed the bug"; layered validation says "we made the bug structurally impossible".

### Condition-Based Waiting

Flaky, timing-dependent test failures usually come from arbitrary sleeps — guesses that pass on a fast machine and fail under CI load. Wait for the actual condition instead:

```typescript
// Before: guessing at timing
await new Promise((r) => setTimeout(r, 50));
expect(getResult()).toBeDefined();

// After: waiting for the condition
await waitFor(() => getResult() !== undefined, "result available");
expect(getResult()).toBeDefined();
```

`waitFor` is a poll loop: check the condition every ~10ms, return when truthy, throw a descriptive error after a timeout (always include one — never loop forever). Read fresh state inside the loop, not cached state from before it. Works for events, state machines, counts, file existence, compound conditions.

An arbitrary timeout is only correct when (1) you first waited for the triggering condition, (2) the duration comes from a known interval (e.g., 2 ticks of a 100ms poller), and (3) a comment explains why.
