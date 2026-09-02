---
name: systematic-debugging
description: Root-cause fix discipline for a debugging session already underway. Use when about to propose or apply a fix for a bug or test failure, when tempted to patch a symptom (add a null check, wrap in try-catch, bump a timeout, add a retry), and when a previous fix didn't work. /diagnosing-bugs builds the repro; this governs the fix.
---

# Systematic debugging

This is the discipline for the middle of a debugging session. Find the root cause, prove it, fix it once.

## The iron law

```text
NO FIXES WITHOUT ROOT-CAUSE INVESTIGATION FIRST
```

A fix you don't understand is not a fix. It's a delay. If you can't explain why your fix works, you haven't found the cause. Stop and trace the actual code path.

Bandaid budget is zero per PR. If you genuinely can't find the root cause, say so and ask for help.

## The four phases

Complete each phase before the next.

### Phase 1: Root-cause investigation

Before attempting ANY fix:

1. Read the error message. This is step zero. The stack trace tells you which line, and the message tells you what invariant broke. Read every error and warning in the output. They often contain the exact answer.
2. Reproduce consistently. `/diagnosing-bugs` Phase 2 is the playbook for building the repro loop.
3. Check recent changes. Look at the git diff, recent commits, new dependencies, config changes, and environment differences.
4. Instrument the boundaries. In a multi-component system, log what enters and exits each boundary and verify env and config propagation. Redact secrets, tokens, credentials, and personal data before anything lands in a log. Keep metadata like names and sizes, never values. Two examples are CI to build to signing, and API to service to database. Run once and read the evidence. It shows where the chain breaks. For example, the evidence may show secrets reaching the workflow but not the build. Then investigate that component. Full technique: [TECHNIQUES.md](${CLAUDE_SKILL_DIR}/TECHNIQUES.md#root-cause-tracing).
5. Trace the data flow backward. When the error is deep in the call stack, the crash site is a symptom. Where does the bad value originate? Keep tracing up until you find the source, and fix it there.

Phase 1 is done when you can name the line that produces the bad value and the input that made it bad. If you can only name where it crashed, you are not done.

Each of these smells means Phase 1 is not done:

- Adding a null check. Ask why this is ever null, and whether it should be.
- Wrapping a mystery error in try-catch. Catch only what you understand and can handle.
- `as any`, `as unknown`, or `@ts-ignore`. Fix the type, don't hide it.
- Bumping a timeout or adding a retry. Ask what is actually slow or racy. When the culprit is a flaky timing test, see [TECHNIQUES.md](${CLAUDE_SKILL_DIR}/TECHNIQUES.md#condition-based-waiting).
- Editing a failing test to pass. The test is often right, so understand WHY it fails before changing it. When it was right yesterday and your change broke it, your change is suspect.

### Phase 2: Pattern analysis

Find the pattern before fixing:

1. Find working examples. Locate similar working code in the same codebase.
2. Compare against references. When you implement a pattern, read the reference implementation completely, every line, not a skim. Partial understanding guarantees bugs.
3. List every difference between working and broken, however small. Treat every difference as a candidate until you rule it out.

Phase 2 is done when you can name the working example you compared against and account for every difference on the list, each one either ruled out by evidence or carried into Phase 3 as a hypothesis. When you found no working example, or a difference still sits there unexplained, you are not done.

### Phase 3: Hypothesis and testing

Scientific method:

1. Rank 3-5 falsifiable hypotheses, then test the top one. Each states its prediction. For example: "If X is the cause, changing Y makes the bug disappear." Write them down. A prediction can fail; an explanation cannot.
2. Test minimally. Make the smallest change that tests the hypothesis. Change one variable per run so the result isolates the cause.
3. Verify before continuing. A confirmed hypothesis moves to Phase 4. Otherwise revert the failed fix before testing the next hypothesis.
4. When you don't know, say so. "I don't understand X" beats pretending. Research more or ask for help.

### Phase 4: Implementation

Fix the root cause, not the symptom:

1. Write the regression test before the fix. Turn the reproduction into a failing test and watch it fail first. The ordering is the point. A test written after the fix proves nothing about the bug. `/diagnosing-bugs` Phase 5 owns the mechanics.
2. Single fix. Address the identified root cause. The diff contains only the root-cause fix.
3. Verify. The test passes, no other tests broke, and the issue is actually resolved. Then run `/done`.
4. Log each attempt as you make it, in the form "attempt N | hypothesis | result". After the third failure, stop fixing and open the architecture question with the user.
5. Treat 3 failed fixes as an architectural problem, not a failed hypothesis. The tells are that each fix reveals new shared state or coupling somewhere else, fixes require "massive refactoring", or each fix creates new symptoms elsewhere. Ask whether this pattern is fundamentally sound or you are sticking with it through inertia.

After fixing at the source, layer validation. The technique is [TECHNIQUES.md](${CLAUDE_SKILL_DIR}/TECHNIQUES.md#defense-in-depth).

## Red flags: stop and return to Phase 1

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

User signals that you are guessing, "Is that not happening?", "Will it show us...?", "Stop guessing", mean the same thing. Go back to Phase 1.

## When investigation reveals "no root cause"

When systematic investigation shows the issue is truly environmental, timing-dependent, or external, you completed the process. Document what you investigated, then implement handling such as a retry, timeout, or clear error and state:

1. the failure mode it handles
2. why it cannot be prevented upstream
3. what happens when the handling itself fails

Add monitoring for the next occurrence. Most "no root cause" cases are incomplete investigation. Check Phase 1's bar before you land here.
