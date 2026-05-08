# Q6a Reusability — search algorithm and audit format

Loaded by Subagent 1 when `Q6 inline check` finds 1+ new top-level definitions in the diff. The main SKILL.md keeps only the Q6a header + reporting format. This reference explains HOW to search.

---

## STEP A — Enumerate NEW definitions added in the diff

For each new definition of the kinds below, write one line:

```
added <kind> <name> in <file>
```

Kinds to enumerate (do NOT restrict to top-level exports):

- `function` (top-level: `function x()`, `const x = () =>`, `const x = function`)
- `class`
- `interface`, `type` alias
- exported `const` (including React components as arrow-function consts)
- React component (function or const form)
- React hook (name starts with `use`)
- **class method** — NestJS service methods like `async findOne(...)`, `private formatInvoice(...)`, `protected validate(...)`. These live inside existing classes but are still new code that can duplicate shared helpers.
- default-exported function or class (`export default function X`, `export default class X`)

**Skip ONLY when ALL three hold**:
- (a) the definition is < 5 lines of real logic, AND
- (b) its name does NOT match any symbol in `repo_map_exports` (case-insensitive root match), AND
- (c) it's purely a re-export, type alias trivially renaming another type, or a one-line wrapper.

If ANY of (a)/(b)/(c) fails, enumerate the item. This catches the "4-line private helper that duplicates a 4-line shared helper" case.

---

## STEP B — Search for each enumerated item

Run **all** of the following; do NOT stop at the first hit. Pay for thoroughness with tokens, not with missed findings.

### 1. Exact-name search

```
Grep("<name>", "packages/")
Grep("<name>", "apps/")     # for cross-app duplication
```

### 2. Semantic-root search

Extract the root by **dropping domain prefixes/suffixes** and searching the remaining verb/noun.

**Algorithm**:

a) Split name on CamelCase boundaries: `renderUserCard` → `[render, User, Card]`
b) Drop tokens that are DOMAIN nouns (Order, Invoice, Product, Customer, Account, User, Subscription — any business-entity noun specific to the project)
c) Keep tokens that are GENERIC verbs/nouns (format, parse, validate, build, sleep, chunk, retry, merge, group, sort, filter, map, find, compute, calculate, extract)
d) Grep each kept token against `packages/` and `apps/`

**Worked examples**:

| Name | Drop | Keep / search |
|------|------|---------------|
| `renderUserCard` | `User` | `Grep("render", ...)` + `Grep("Card", ...)` |
| `validateOrderInvoice` | `Order`, `Invoice` | `Grep("validate", ...)` |
| `UserBadge` (component) | `User` | `Grep("Badge", "packages/ui/src/components/")` |
| `sleep` | (none — no CamelCase) | `Grep("sleep", "packages/")` |
| `getMonthlyOrderSummary` | `Order` | `Grep("getSummary", ...)` + `Grep("summary", ...)` |

### 3. UI component search

For new React components added in `apps/*/src/components/` or `packages/*/src/components/`:

```
Grep("<ComponentName>", "packages/ui/src/components/")
Glob("packages/ui/src/components/**/<kebab-case-name>*.tsx")
Glob("packages/ui/src/components/**/<kebab-case-name>*.ts")
```

### 4. Verify each candidate hit

For each candidate match from steps 1-3, **Read the file** and confirm it is a REAL semantic match (not a substring collision — e.g., `formatter.ts` matching on `format` does NOT automatically mean the new code duplicates the existing one).

Record one of:
- `verified: yes — <what the existing impl does and whether it's a real match>`
- `verified: no — substring collision`
- `verified: no — different semantics`

---

## Audit field — REQUIRED

Use this **EXACT** field name `reusability_searches:` (not `reuse_searches` or any variant) so the Phase 3 critic can parse it:

```yaml
reusability_searches:
  - <tool>("<query>", "<path>") → <N> matches
    verified: <yes|no> — <if yes: what the existing impl does and whether it's a real match;
                          if no: substring collision or wrong semantic>
  - ...
```

**Rules**:

- **At least one entry per item enumerated in STEP A.**
- For each search where `N > 0`, `verified:` is MANDATORY. Critic rejects audits that claim "0 matches" for all searches as shallow / suspicious. If `N == 0`, write `verified: n/a`.
- If STEP A was empty, write EXACTLY:
  `reusability_searches: N/A (no new top-level definitions in diff)`

---

## Non-monorepo fallback

If the Phase 1 repo map is `N/A (not a monorepo)`, the project has no `packages/` or `apps/` directory. Reroute searches:

- `Grep("<name>", "src/")` — primary source root
- `Grep("<name>", ".")` — repo root (will include `node_modules` — filter mentally)
- Still run the verification step.

Don't claim "No issues" just because the default `packages/` search returns zero — search where the code actually lives.

---

## Q6a — reporting format

Default Severity: **SERIOUS** (escalate to **CRITICAL** if the existing thing lives in an auth / validation / crypto package).

```
Severity:    Serious
Confidence:  high | medium
File:        <path:line of the new duplicate>
Category:    Reusability
Issue:       <new symbol> at <new file:line> reimplements <existing symbol> at <existing file:line>
Why it matters: Divergent implementations drift over time, creating dual-fix burden and skill silos.
Suggested fix:  Import from <existing file> instead of redefining.
```

OR `No issues` (with a populated `reusability_searches:` field — empty audit invalidates this claim).

---

## Q6 known limitation — control-flow gaps

Q6's STEP A / STEP B enumerates NEW definitions and checks whether they duplicate EXISTING shared code. It does **not** catch the case where an existing helper is already called on SOME code paths in the same file but should ALSO be called on others — e.g., an early-return that hardcodes a synthetic response for a field that a helper computes on the happy path.

**Example bug class Q6 misses**:

```ts
async getUserInvoices(...) {
  const activeUsers = await this.getActiveUsers(...)
  if (activeUsers.length === 0) {
    return { summary: [], invoiceItems: [] }  // ← hardcoded []
  }
  // ... late path ...
  const invoiceItems =
    await this.invoiceItemsService
              .getByUserAndDateRange(...)
  return { summary, invoiceItems }
}
```

The early return silently drops stored `invoiceItems` because the helper is only invoked on the late path. Q6's `reusability_searches:` audit won't flag this — nothing was newly added, so STEP A enumerates nothing to search for. The gap exists in control flow, not in symbol duplication.

**When you see a NEW or MODIFIED early-return that builds a synthetic response object with empty fields** (`[]`, `null`, `{}`, `undefined`) — especially inside a function that imports or injects a service — check whether any of those empty fields are populated by a helper already used on another branch in the same function. If so, flag it under:

- **Q3 (DRY)** — when the duplication is within the current diff, OR
- **Prior-finding-correction** — when a prior reviewer raised it and the author did not address it, OR
- **Silent-failure** — when the synthetic empty value causes a user-visible behavior gap (e.g., stored values disappear from the UI in empty states).

**Do NOT flag this class under Q6** — the `reusability_searches:` audit has no field to record a control-flow finding, and the Phase 3 critic will drop Q6 findings that lack a matching audit entry.
