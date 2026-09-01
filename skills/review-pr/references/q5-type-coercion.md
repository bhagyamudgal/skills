# Q5: type-coercion at write sites

Loaded by **Subagent 1** while answering Q5, when the diff contains a DB insert/update or
an API payload construction. A diff with neither never reaches this file.

**Type-coercion at write sites** (subtle, test-only-caught bug):
Scan every DB insert/update / API payload construction in the diff for expressions like
`field: value?.toFixed(N)`, `field: String(value)`, or ``field: `${value.toFixed(N)}` ``
being written into NUMERIC fields. `.toFixed()` returns a string: silently stores "2.6"
in a numeric column.

Coercion methods to scan: `.toFixed`, `.toString`, `.toLocaleString`, `String(...)`,
template-literal `` `${...}` `` containing those.
Flag when NOT wrapped in `Number(...)` / `parseFloat(...)` / `parseInt(...)` / unary `+(...)`.

Determining "numeric field":

- **DB writes**: read schema at `$SCHEMA_DIR` OR grep the field name's column definition
  (`<fieldName>: numeric|integer|real|decimal|double|float|bigint`). If unset /
  undeterminable, SKIP. Do not guess.
- **API payloads / DTOs**: read the matching Zod schema (`z.number()`,
  `z.coerce.number()`) or TypeScript type. If unlocatable, SKIP.

Severity: Serious. Category: Breaking-change.
