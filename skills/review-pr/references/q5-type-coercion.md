# Q5: type-coercion at write sites

**Subagent 1** loads this while answering Q5, when the diff contains a DB insert/update or
an API payload construction. A diff with neither never reaches this file.

**Type-coercion at write sites**. Only tests catch this subtle bug:
Scan every DB insert/update and API payload construction in the diff for expressions like
`field: value?.toFixed(N)`, `field: String(value)`, or ``field: `${value.toFixed(N)}` ``
being written into NUMERIC fields. `.toFixed()` returns a string: silently stores "2.6"
in a numeric column.

Coercion methods to scan: `.toFixed`, `.toString`, `.toLocaleString`, `String(...)`,
template-literal `` `${...}` `` containing those.
Flag when NOT wrapped in `Number(...)` / `parseFloat(...)` / unary `+(...)`.
`parseInt(...)` counts as a safe wrap ONLY for a verified-integer field
(DB `integer`/`bigint`, Zod `z.number().int()` per the rules below) whose source
is verified integer-formatted (no fractions, separators, or unit suffixes) and
within `Number.MAX_SAFE_INTEGER`, or where explicit truncation intent is
documented at the write site. Otherwise it IS the bug: `parseInt("1.9")` and
`parseInt("1,234")` both yield `1`, and values past the safe range lose precision.

How to tell a field is numeric:

- **DB writes**: read schema at `$SCHEMA_DIR` OR grep the field name's column definition
  (`<fieldName>: numeric|integer|real|decimal|double|float|bigint`). If unset /
  undeterminable, SKIP. Never guess.
- **API payloads / DTOs**: read the matching Zod schema (`z.number()`,
  `z.coerce.number()`) or TypeScript type. If unlocatable, SKIP.

Severity: Serious. Category: Breaking-change.
