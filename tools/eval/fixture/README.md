# Trigger eval fixture

A deliberately small TypeScript repo the trigger eval runs against.

It is not meant to be correct. It carries planted defects so the utterances in
`../triggers.json` have something real to land on:

- `src/user.ts` dereferences an optional property — a genuine type error
- `loadUsers` awaits inside a `for` loop — the sequential-await shape

**The fixture matters more than it looks.** An early prototype ran against an empty
directory, and `"ts errors"` did *not* fire `fix-ts-errors` — the agent ran `Glob` to look
around instead, because there was no TypeScript to have errors in. That reads as a
description failure and is not one.

If you add a case to `triggers.json`, make sure the fixture can satisfy it. A case the
fixture cannot support measures the fixture, not the skill.
