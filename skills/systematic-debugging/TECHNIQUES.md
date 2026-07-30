# Supporting Techniques

Reached from `SKILL.md` at the point each one fires.

## Root-Cause Tracing

Bugs often manifest deep in the call stack (file created in the wrong directory, database opened with the wrong path). The instinct is to fix where the error appears — that's the symptom. Trace backward until you find the original trigger:

1. **Observe the symptom** — e.g., `git init` ran in the source directory.
2. **Find the immediate cause** — the line that directly did it.
3. **Ask what called it** — walk up the chain one caller at a time.
4. **Inspect the value passed at each level** — e.g., `projectDir` was `''`, and an empty `cwd` resolves to `process.cwd()`.
5. **Find the original trigger** — e.g., a test read a fixture value before setup populated it.

Fix at the source (in the example: a getter that throws if accessed before setup), then add defense-in-depth below.

When you can't trace by reading, instrument: log directory, cwd, relevant env, and `new Error().stack` immediately BEFORE the dangerous operation (not after it fails), run once, and grep the output. In tests use `console.error` — loggers may be suppressed.

**Tag every probe `[DEBUG-xxxx]` with a unique suffix so cleanup is one grep.** An untagged probe is a probe that ships.

For test pollution where you don't know which test is the culprit, bisect: run the suite one file at a time and stop at the first polluter.

## Defense in Depth

After fixing at the source, validate at EVERY layer the data passes through — a single check gets bypassed by other code paths, refactors, or mocks:

1. **Entry-point validation** — reject obviously invalid input at the API boundary (empty string, nonexistent path)
2. **Business-logic validation** — assert the data makes sense for this specific operation
3. **Environment guards** — refuse dangerous operations in the wrong context (e.g., refuse `git init` outside the temp dir when `NODE_ENV === "test"`)
4. **Debug instrumentation** — log context + stack before the dangerous operation for forensics when the other layers fail

Different layers catch different bypasses.

## Condition-Based Waiting

Flaky, timing-dependent test failures usually come from arbitrary sleeps — guesses that pass on a fast machine and fail under CI load. Wait for the actual condition instead:

```typescript
// Before: guessing at timing
await new Promise((r) => setTimeout(r, 50));
expect(getResult()).toBeDefined();

// After: waiting for the condition
await waitFor(() => getResult() !== undefined, "result available");
expect(getResult()).toBeDefined();
```

`waitFor` is a poll loop: check the condition every ~10ms, return when truthy, and throw a descriptive error after a timeout — every poll loop carries a timeout. Read fresh state inside the loop, not cached state from before it. Works for events, state machines, counts, file existence, compound conditions.

An arbitrary timeout is only correct when (1) you first waited for the triggering condition, (2) the duration comes from a known interval (e.g., 2 ticks of a 100ms poller), and (3) a comment explains why.
