---
name: reuse-first
description: Search before you write — 3-layer search (name, behavior, reference), the reuse ladder, and the smells that mean you are about to fork. Use BEFORE creating any new utility, type, schema, component, hook, or constant; when about to copy-paste similar code; or when reviewing a diff for duplication.
---

# Reuse First

Every duplicate is a future **divergence**: a bug fixed in one copy stays broken in the other.

## 3-Layer Search

Exact name often misses it, so search in three passes:

1.  **Name layer**: `grep -r "functionName"` — exact + camelCase + snake_case variants
2.  **Behavior layer**: grep for what it _does_ — `format.*date`, `validate.*email`, `parse.*currency`
3.  **Reference layer**: find a feature that _uses_ the thing you're looking for — open it, follow its imports

**Done when you can name what each layer returned:** the name variants you grepped, at least three behavior keywords and their hits, and the one existing feature you opened and followed imports from. If you cannot name three behavior keywords for the thing you are about to write, you do not understand it well enough to search for it — that is the finding, not the search.

## Where to search, by artifact

| Creating                       | Search for                                                                                                                                                                                                   |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Utility function               | `grep -r` in `lib/`, `utils/`, `shared/`, `packages/*/src/` by **behavior keyword** (`format`, `parse`, `validate`, `convert`, `normalize`)                                                                  |
| Type / interface               | Check `types/`, `packages/*/types/`, `@*/types` package exports, and the same module's `*.types.ts` files. Prefer `z.infer<typeof schema>` over a hand-written duplicate                                     |
| Zod schema                     | Check `validators/`, `schemas/`, `packages/*/validators/`, and look for `z.object({...})` in adjacent files. Use `.extend()` / `.partial()` / `.pick()` / `.omit()` to derive new schemas from existing ones |
| React component                | Check `components/`, `components/ui/`, `packages/ui/`, and shared component packages. If a primitive exists, compose it                                                                                      |
| Hook (TanStack Query, etc.)    | Check `hooks/`, `app/**/hooks/`, and look for existing `use<Resource>` hooks. One hook per endpoint; import the existing key from its query-keys module                                                      |
| Constants                      | Check `constants/`, `packages/constants/`, and exported `const` declarations                                                                                                                                 |
| Error / try-catch wrapper      | If `tryCatch` exists, use it                                                                                                                                                                                 |
| Date/currency/weight formatter | Check `ui/utils/`, `packages/ui/src/utils/`, `lib/format*` — these almost always exist and are i18n-aware                                                                                                    |

## Reuse hierarchy

**reuse > compose > extend > generalize > write new**

1.  **Reuse** as-is if the existing utility fits — even if the name isn't ideal
2.  **Compose** existing utilities to build the new behavior
3.  **Extend** by passing options/generics to the existing one
4.  **Generalize** the existing utility (move to a shared location, add a parameter, keep callers working)
5.  **Write new** as a last resort — and if it overlaps with an existing one, propose deprecating the older one in the same PR

### When duplication IS acceptable

Reach this section only after all three layers have returned.

- **Two unrelated domains** that happen to look similar — DRY is about shared _knowledge_, not shared _appearance_. A `userId` validator and a `productId` validator can both be `z.string().uuid()` independently; coupling them creates fake polymorphism
- **Premature abstraction**: three similar lines is fine; abstract on the fourth occurrence, not the second
- **Tests**: explicit setup in each test often beats shared fixtures that hide what's being tested

## Signs you are about to fork

- Naming with a suffix: `formatDate2`, `userServiceV2`, `validateInputNew`, `parseFooHelper`
- Variant naming for similar behavior: `formatPrice` + `formatCurrency` + `priceFormatter` coexisting — a divergence in progress
- Inline reimplementation of something that "feels like it should exist" — that feeling is usually correct
- A new file in `utils/` or `lib/` that's under 30 lines — likely belongs in an existing file
- A new type alias that mirrors a Zod schema's inferred type — use `z.infer` instead
- Copy-pasted boilerplate across files (auth checks, error mapping, response shaping) — extract to a shared helper
- Defining a new constant inline when a similarly-named one exists in `constants/`

## Verification step (before claiming the task done)

- Search for the new function/type's **behavior keywords**, not just its name — does anything similar exist under a different name?
- Check sibling files in the same directory — do they have helpers you missed?
- For monorepos: check shared packages even if it adds a dependency edge — duplicating across packages is worse than coupling them
- If you wrote a new utility, ask: "Could I delete this and import from somewhere else?" If yes, do that instead
