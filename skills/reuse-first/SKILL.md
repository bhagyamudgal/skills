---
name: reuse-first
description: Search before you write, and sweep before you finish — 3-layer search (name, behavior, reference), the reuse ladder, the duplication sweep, and the smells that mean you are about to fork. Use BEFORE creating any new utility, type, schema, component, hook, constant, module, or package; BEFORE hardcoding a literal that may already be an exported constant; when about to copy-paste similar code; and as a completion gate over every file the task touched, not just the diff.
---

# Reuse First

Every duplicate is a future **divergence**: a bug fixed in one copy stays broken in the other.

## 3-Layer Search

Exact name often misses it, so search in three passes:

1.  **Name layer**: `grep -r "functionName"`, exact + camelCase + snake_case variants
2.  **Behavior layer**: grep for what it _does_, `format.*date`, `validate.*email`, `parse.*currency`
3.  **Reference layer**: find a feature that _uses_ the thing you're looking for. Open it, follow its imports

**Done when you have printed what each layer returned**: three lines, before you write anything:

```
Name layer:      <variants grepped> -> <hits, or none>
Behavior layer:  <3+ keywords> -> <hits, or none>
Reference layer: <feature file opened> -> <imports followed>
```

Those three lines are the artifact. Creating the file without them is the
failure this skill exists to prevent, and it is invisible afterwards: the new
code compiles, passes review, and ships, because nothing downstream re-asks the
question. If you notice you have already written the artifact, run the search
anyway and delete what it finds a home for; do not rationalise the copy.

**One search per artifact, not per batch.** Creating six modules in one sitting
is six searches. Batching them into one glance is how a shared constant gets
missed: the search that would have found it was never phrased with its keywords.

If you cannot name three behavior keywords for the thing you are about to write, you do not understand it well enough to search for it. That is the finding, not the search.

## Where to search, by artifact

| Creating                       | Search for                                                                                                                                                                                                   |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Utility function               | `grep -r` in `lib/`, `utils/`, `shared/`, `packages/*/src/` by **behavior keyword** (`format`, `parse`, `validate`, `convert`, `normalize`)                                                                  |
| Type / interface               | Check `types/`, `packages/*/types/`, `@*/types` package exports, and the same module's `*.types.ts` files. Prefer `z.infer<typeof schema>` over a hand-written duplicate                                     |
| Zod schema                     | Check `validators/`, `schemas/`, `packages/*/validators/`, and look for `z.object({...})` in adjacent files. Use `.extend()` / `.partial()` / `.pick()` / `.omit()` to derive new schemas from existing ones |
| React component                | Check `components/`, `components/ui/`, `packages/ui/`, and shared component packages. If a primitive exists, compose it                                                                                      |
| Hook (TanStack Query, etc.)    | Check `hooks/`, `app/**/hooks/`, and look for existing `use<Resource>` hooks. One hook per endpoint; import the existing key from its query-keys module                                                      |
| Constants                      | Check `constants/`, `packages/constants/`, and exported `const` declarations. **Also grep the literal itself** (`grep -rn '"text/html"'`). A value already exported under a name no search for that name would ever reach                        |
| Module / route / package       | Grep for the concern, not the filename: `grep -rn "onError\|errorHandler"`, `grep -rn "app.use(" `. Two apps in one repo are the likeliest place a handler exists twice                                      |
| Test helper or fixture         | Read the sibling `*.test.ts` files first. Four near-identical `upload()` helpers is the normal outcome of never looking                                                                                       |
| Error / try-catch wrapper      | If `tryCatch` exists, use it                                                                                                                                                                                 |
| Date/currency/weight formatter | Check `ui/utils/`, `packages/ui/src/utils/`, `lib/format*`. These almost always exist and are i18n-aware                                                                                                    |

## Reuse hierarchy

**reuse > compose > extend > generalize > write new**

1.  **Reuse** as-is if the existing utility fits, even if the name isn't ideal
2.  **Compose** existing utilities to build the new behavior
3.  **Extend** by passing options/generics to the existing one
4.  **Generalize** the existing utility (move to a shared location, add a parameter, keep callers working)
5.  **Write new** as a last resort, and if it overlaps with an existing one, propose deprecating the older one in the same PR

### When duplication IS acceptable

Reach this section only after all three layers have returned.

- **Two unrelated domains** that happen to look similar: DRY is about shared _knowledge_, not shared _appearance_. A `userId` validator and a `productId` validator can both be `z.string().uuid()` independently; coupling them creates fake polymorphism
- **Premature abstraction**: three similar lines is fine; abstract on the fourth occurrence, not the second
- **Tests**: explicit setup in each test often beats shared fixtures that hide what's being tested

## Signs you are about to fork

- Naming with a suffix: `formatDate2`, `userServiceV2`, `validateInputNew`, `parseFooHelper`
- Variant naming for similar behavior: `formatPrice` + `formatCurrency` + `priceFormatter` coexisting, a divergence in progress
- Inline reimplementation of something that "feels like it should exist": that feeling is usually correct
- A new file in `utils/` or `lib/` that's under 30 lines: likely belongs in an existing file
- A new type alias that mirrors a Zod schema's inferred type: use `z.infer` instead
- Copy-pasted boilerplate across files (auth checks, error mapping, response shaping): extract to a shared helper
- Defining a new constant inline when a similarly-named one exists in `constants/`

## Sweep mode: before claiming the task done

The pre-creation search only sees what you were about to write. It cannot see
what was **already** duplicated, and diff-scoped tools cannot either: `simplify`
inspects duplication *introduced by the change* and explicitly leaves
pre-existing code alone. So a handler copied into two apps last month is
invisible to every check in the pipeline, forever, unless this sweep runs.

Scope it to **every file the task touched plus their siblings**, not the diff.

**Prefer a real clone detector for copied blocks.** `jscpd` does Rabin-Karp
fingerprinting over token streams and finds cross-file copies in milliseconds,
without you guessing which files to compare, which is the part of a manual
sweep that fails silently. If the repo has it wired up, run it; if not, one
`npx jscpd@5 <paths> --reporters console` is usually worth it before hand-rolling
greps. Use the canonical `jscpd@5`, the official Rust rewrite, shipped as a
self-contained native binary through npm, cargo, brew or curl. Not the
third-party `jscpd-rs` port, which is a separate project and benchmarks slower.

It will not find the classes below, so still run them: a literal duplicating a
named constant, and a fact duplicated between docs and code, are both invisible
to token-level detection.

Derive the file set from git rather than typing paths: it respects
`.gitignore`, cannot name a directory that does not exist, and skips
`node_modules` without a flag.

```bash
BASE=<merge-base or the commit you branched from>
FILES=$(git ls-files 'apps' 'packages' 'src' 2>/dev/null | grep -vE '\.d\.ts$')

# 1. Literals repeated 3+ times — the ones worth naming, or already named
#    somewhere you never searched because a name search cannot find a value.
printf '%s\n' "$FILES" | xargs grep -hoE "['\"][A-Za-z][A-Za-z0-9:._/-]{5,}['\"]" \
  | tr -d "\"'" | sort | uniq -c | sort -rn | awk '$1 >= 3'

# 2. A specific literal you suspect is already an exported constant.
printf '%s\n' "$FILES" | xargs grep -n '"text/html"'

# 3. Facts stated in a comment that already live in the docs. This is the
#    class no clone detector sees, and the one that duplicates fastest when
#    the same change writes the spec section and the comment.
git diff -U0 "$BASE" -- 'apps' 'packages' \
  | grep -E '^\+\s*(//|\*)' | sed 's/^+[[:space:]]*//' \
  | grep -oE '[A-Za-z][A-Za-z ]{28,}' | sed 's/  */ /g; s/^ //; s/ $//' | sort -u \
  | while IFS= read -r phrase; do
      hit=$(grep -rlF "$phrase" docs/ ./*.md 2>/dev/null | head -1)
      [ -n "$hit" ] && printf '  %s -> %s\n' "$phrase" "$hit"
    done
```

**Do not hand-roll a check for near-identical function bodies.** A grep over
declaration lines dedupes on text that contains the name, so two helpers with
*different* names, the case worth finding, can never collide, and the check
quietly reports nothing while looking like it ran. Structural similarity needs a
clone detector; that is what `jscpd` above is for.

Commands here assume GNU-compatible `grep`. `ugrep`, `busybox` and BSD `grep`
differ on bracket classes and `--exclude` ordering, so if a check returns
suspiciously zero, verify it finds a planted duplicate before trusting it.

Then ask, per hit:

- Does this fact/behavior have **one** home, or several that can drift apart?
- If two copies exist and one is fixed, does the other silently stay broken?
  That is the whole test. A bug fixed in one copy staying broken in the other
  is the cost; everything else is style.
- For monorepos: check shared packages even if it adds a dependency edge.
  Duplicating across packages is worse than coupling them.
- If you wrote a new utility, ask: "Could I delete this and import from
  somewhere else?" If yes, do that instead.

**Report the sweep even when it finds nothing.** A silent sweep and a skipped
sweep are indistinguishable to the person reading your completion report, and
only one of them is honest.
