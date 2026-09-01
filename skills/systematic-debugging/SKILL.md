---
name: systematic-debugging
description: Root-cause fix discipline for a debugging session already underway. Use when about to propose or apply a fix for a bug or test failure, when tempted to patch a symptom (add a null check, wrap in try-catch, bump a timeout, add a retry), and when a previous fix didn't work. /diagnosing-bugs builds the repro; this governs the fix.
---

# Systematic Debugging

This is the discipline for the middle of a debugging session: find the root cause, prove it, fix it once.

## The Iron Law

```
NO FIXES WITHOUT ROOT-CAUSE INVESTIGATION FIRST
```

A fix you don't understand is not a fix. It's a delay. If you can't explain why your fix works, you haven't found the cause; stop and trace the actual code path.

**Bandaid budget: zero per PR.** If you genuinely can't find the root cause, say so and ask for help.

## The Four Phases

Complete each phase before the next.

### Phase 1: Root-cause investigation

Before attempting ANY fix:

1. **Read the error message: this is step zero.** The stack trace tells you which line; the message tells you what invariant broke. Read every error and warning in the output. They often contain the exact answer.
2. **Reproduce consistently.** `/diagnosing-bugs` Phase 2 is the playbook for building the repro loop.
3. **Check recent changes.** Git diff, recent commits, new dependencies, config changes, environment differences.
4. **Instrument the boundaries.** In a multi-component system (CI → build → signing; API → service → database), log what enters and exits each boundary and verify env/config propagation. Run once, read the evidence, and it shows WHERE the chain breaks (secrets → workflow ✓, workflow → build ✗). Then investigate that component. Full technique: [TECHNIQUES.md](${CLAUDE_SKILL_DIR}/TECHNIQUES.md#root-cause-tracing).
5. **Trace the data flow backward.** When the error is deep in the call stack, the crash site is a symptom. Where does the bad value originate? Keep tracing up until you find the source. Fix at the source, where the bad value originates.

**Phase 1 is done when you can name the line that produces the bad value and the input that made it bad.** If you can only name where it crashed, you are not done.

**Symptom-patch smells**: each of these means Phase 1 isn't done:

- **Adding a null check**. Ask: why is this ever null? Should it be?
- **Wrapping a mystery error in try-catch**: catch only what you understand and can handle
- **`as any` / `as unknown` / `@ts-ignore`**: fix the type, don't hide it
- **Bumping a timeout / adding a retry**: what is actually slow or racy? If it's a flaky timing test, see [TECHNIQUES.md](${CLAUDE_SKILL_DIR}/TECHNIQUES.md#condition-based-waiting).
- **Editing a failing test to pass**: the test is often right; understand WHY it fails before changing it. If it was right yesterday and your change broke it, your change is suspect.

### Phase 2: Pattern analysis

Find the pattern before fixing:

1. **Find working examples.** Locate similar working code in the same codebase.
2. **Compare against references.** If implementing a pattern, read the reference implementation COMPLETELY, every line, not a skim. Partial understanding guarantees bugs.
3. **List every difference** between working and broken, however small. Treat every difference as a candidate until you rule it out.

**Phase 2 is done when you can name the working example you compared against and account for every difference on the list, each one either ruled out by evidence or carried into Phase 3 as a hypothesis.** If you found no working example, or a difference is still sitting there unexplained, you are not done.

### Phase 3: Hypothesis and testing

Scientific method:

1. **Rank 3-5 falsifiable hypotheses, then test the top one.** Each states its prediction: "If X is the cause, changing Y makes the bug disappear." Write them down. A prediction can fail; an explanation cannot.
2. **Test minimally.** The SMALLEST possible change that tests the hypothesis. Change one variable per run so the result isolates the cause.
3. **Verify before continuing.** Confirmed → Phase 4. Not confirmed → revert the failed fix before testing the next hypothesis.
4. **When you don't know, say so.** "I don't understand X" beats pretending. Research more or ask for help.

### Phase 4: Implementation

Fix the root cause, not the symptom:

1. **Regression test, before the fix.** Turn the reproduction into a failing test and watch it fail *first*. The ordering is the point, since a test written after the fix proves nothing about the bug. `/diagnosing-bugs` Phase 5 owns the mechanics.
2. **Single fix.** Address the identified root cause. The diff contains only the root-cause fix.
3. **Verify.** Test passes, no other tests broken, issue actually resolved. Then run `/done`.
4. **Log each attempt as you make it**, "attempt N | hypothesis | result". After the third failure, stop fixing and open the architecture question with the user.
5. **3 failed fixes = architectural problem, not a failed hypothesis.** The tells: each fix reveals new shared state or coupling somewhere else; fixes require "massive refactoring"; each fix creates new symptoms elsewhere. Ask: is this pattern fundamentally sound, or are we sticking with it through inertia?

After fixing at the source, layer validation: [TECHNIQUES.md](${CLAUDE_SKILL_DIR}/TECHNIQUES.md#defense-in-depth).

## Red Flags: Stop and Return to Phase 1

If you catch yourself thinking any of these:

- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- Changing multiple things, then running the tests
- "It's probably X, let me fix that", without evidence
- "I don't fully understand this, but it might work"
- Listing fixes before tracing the data flow
- Rationalizing why a test failure "doesn't really matter"
- "One more fix attempt" when 2+ have already failed
- Each fix reveals a new problem in a different place

User signals that you're guessing, "Is that not happening?", "Will it show us...?", "Stop guessing", mean the same thing: back to Phase 1.

## When Investigation Reveals "No Root Cause"

If systematic investigation shows the issue is truly environmental, timing-dependent, or external: you've completed the process. Document what you investigated, then implement handling (retry, timeout, clear error) and state:

1. the failure mode it handles
2. why it cannot be prevented upstream
3. what happens when the handling itself fails

Add monitoring for the next occurrence. Most "no root cause" cases are incomplete investigation. Check Phase 1's bar before you land here.
