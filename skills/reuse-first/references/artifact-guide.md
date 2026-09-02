# Where to search, by artifact

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

1.  **Reuse** as-is if the existing utility fits, even when the name is not ideal
2.  **Compose** existing utilities to build the new behavior
3.  **Extend** by passing options or generics to the existing one
4.  **Generalize** the existing utility. Move it to a shared location, add a parameter, and keep callers working
5.  **Write new** as a last resort, and if it overlaps with an existing one, propose deprecating the older one in the same PR

### When duplication is acceptable

Reach this section only after all three layers have returned.

- **Two unrelated domains** that happen to look similar. DRY is about shared knowledge, not shared appearance. A `userId` validator and a `productId` validator can both be `z.string().uuid()` independently. Coupling them creates fake polymorphism
- **Premature abstraction.** Three similar lines are fine. Abstract on the fourth occurrence, not the second
- **Tests.** Explicit setup in each test often beats shared fixtures that hide what is being tested
