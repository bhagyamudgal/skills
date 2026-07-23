---
name: reuse-first
description: Search the codebase before writing any new utility, type, schema, component, hook, constant, or helper — 3-layer search (name, behavior, reference), reuse hierarchy, and duplicate smells. Use BEFORE creating any new function, type, zod schema, component, hook, or constant; when tempted to add a file to utils/ or lib/; when about to copy-paste similar code; or when reviewing a diff for duplication. Triggers on "new utility", "create a helper", "add a type", "new schema", "new component", "write a hook".
---

# Reuse First

Discipline for searching the codebase before creating any new utility, type, schema, component, hook, constant, or helper.

Before writing any new utility, type, schema, component, hook, or helper — **search the codebase first**. AI assistants reliably underperform here: writing a new function feels faster than finding the existing one, which silently creates duplication and tech debt. Every duplicate is a future divergence: a bug fixed in one copy stays broken in the other.

## 3-Layer Search

When looking for existing code, search in three passes — exact name often misses it:

1.  **Name layer**: `grep -r "functionName"` — exact + camelCase + snake_case variants
2.  **Behavior layer**: grep for what it _does_ — `format.*date`, `validate.*email`, `parse.*currency`
3.  **Reference layer**: find a feature that _uses_ the thing you're looking for — open it, follow its imports

If all 3 layers return nothing, then it's safe to write new. If only layer 1 returns nothing, keep looking.

## Required search before creating

When tempted to write any of the following, search first:

| Creating                       | Search for                                                                                                                                                                                                   |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Utility function               | `grep -r` in `lib/`, `utils/`, `shared/`, `packages/*/src/` by **behavior keyword** (`format`, `parse`, `validate`, `convert`, `normalize`) — not just by exact name                                         |
| Type / interface               | Check `types/`, `packages/*/types/`, `@*/types` package exports, and the same module's `*.types.ts` files. Prefer `z.infer<typeof schema>` over a hand-written duplicate                                     |
| Zod schema                     | Check `validators/`, `schemas/`, `packages/*/validators/`, and look for `z.object({...})` in adjacent files. Use `.extend()` / `.partial()` / `.pick()` / `.omit()` to derive new schemas from existing ones |
| React component                | Check `components/`, `components/ui/`, `packages/ui/`, and shared component packages. If a primitive exists, compose it — don't fork it                                                                      |
| Hook (TanStack Query, etc.)    | Check `hooks/`, `app/**/hooks/`, and look for existing `use<Resource>` hooks. One hook per endpoint — never duplicate query keys                                                                             |
| Constants                      | Check `constants/`, `packages/constants/`, and exported `const` declarations. No magic values inline if a named constant exists                                                                              |
| Error / try-catch wrapper      | If `tryCatch` exists, use it — never write a new try/catch wrapper                                                                                                                                           |
| Date/currency/weight formatter | Check `ui/utils/`, `packages/ui/src/utils/`, `lib/format*` — these almost always exist and are i18n-aware                                                                                                    |

## Reuse hierarchy (in order of preference)

1.  **Use as-is** if existing utility fits — even if the name isn't ideal
2.  **Compose** existing utilities to build the new behavior
3.  **Extend** by passing options/generics to the existing one
4.  **Generalize** the existing utility (move to a shared location, add a parameter, keep callers working)
5.  **Only as a last resort**: write a new one — and if it overlaps with an existing one, propose deprecating the older one in the same PR (don't leave both behind)

## Smells that indicate a duplicate is being created

- Naming with a suffix: `formatDate2`, `userServiceV2`, `validateInputNew`, `parseFooHelper`
- Variant naming for similar behavior: `formatPrice` + `formatCurrency` + `priceFormatter` coexisting
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

## When duplication IS acceptable

DRY is a sharp tool — don't over-apply it:

- **Two unrelated domains** that happen to look similar — DRY is about shared _knowledge_, not shared _appearance_. A `userId` validator and a `productId` validator can both be `z.string().uuid()` independently — coupling them creates fake polymorphism
- **Premature abstraction**: three similar lines is fine; abstract on the fourth occurrence, not the second
- **Tests**: explicit setup in each test often beats shared fixtures that hide what's being tested
