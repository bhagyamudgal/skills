# Schema design checks (Q7–Q9)

Loaded by Subagent 1 only when `INCLUDE_SCHEMA_CHECKS = true` (PR adds new database tables — detected in Phase 1 by grepping the diff for `pgTable\(`, `createTable\(`, `CREATE TABLE`, `knex.schema.createTable`, etc.).

The main SKILL.md keeps a 5-line conditional that loads this file. Inline-loading every run wastes context on non-schema PRs.

`SCHEMA_DIR` is set in Phase 1 — typically `db/schema/`, `drizzle/schema/`, `src/schema/`, or `migrations/`. If unset, defaults to `.` (repo root) and limits searches to files matching the detected table-definition pattern.

---

## Q7. Schema Overlap

**Question**: Does a new table duplicate an existing table's domain?

For each new `pgTable()` (or equivalent) definition in the diff:

a. Extract domain keywords from the table name (e.g., `app_OrderItems` → `order`, `item`).
b. Add FK target roots as additional keywords (e.g., FKs `recipeId`, `articleId` → keywords `recipe`, `article`).
c. Search `$SCHEMA_DIR` for tables with matching keywords:
   ```
   Grep("<keyword>", "$SCHEMA_DIR", type: "ts")
   ```
d. For each hit, read the file and compare FK targets and field names.
e. **Flag ONLY** if an existing table has **3+ matching FK targets** AND a similar domain purpose (both tables serve the same feature area — e.g., both handle ordering, both handle inventory).

Substring matches alone (e.g., `item` matching many unrelated tables) are NOT sufficient — verify by FK comparison AND domain overlap.

**Severity**: Moderate. **Category**: Architecture.

**Format**:
> Existing table `<existing>` in `<path>` has overlapping domain — shares FKs [list]. Is `<new table>` intentionally separate?

---

## Q8. Table Consolidation

**Question**: Could a simple 1:1 table be a column on an existing table?

For each new table definition in the diff, detect where:

a. The PK is also an FK to another table (pattern: `accountId` / `clientId` as both primary key and foreign key).
b. The table has fewer than **5 data columns** beyond the PK (exclude standard audit columns: `createdAt`, `updatedAt`, `createdBy`, `updatedBy`).

If both conditions are met:

c. Search for existing settings/config tables for the same parent entity:
   ```
   Grep("<parent>.*setting|<parent>.*config", "$SCHEMA_DIR", type: "ts")
   ```
d. **Flag ONLY** if a candidate settings/config table EXISTS. Do NOT suggest "create a settings table" — that is scope creep.

**Severity**: Moderate. **Category**: Architecture.

**Format**:
> 1:1 table `<new>` has only N data columns — could this be a column on existing `<settings table>` in `<path>`?

---

## Q9. Cross-Table Field Consistency

**Question**: Are entity reference columns complete?

When a new table has entity reference FKs (to `orderTable`, `productTable`, `invoiceTable`, `customerTable`, etc.):

a. Identify the "entity reference set" — which entity types does it reference?
b. Search for related tables in the same domain (tables sharing the same parent FK or domain name keywords).
c. Compare entity reference sets between the new table and related tables.
d. **Flag ONLY** when a related table in the SAME domain has MORE entity types. Do NOT flag cross-domain differences (e.g., billing items vs inventory items may intentionally support different entity types).

**Severity**: Moderate. **Category**: Architecture.

**Format**:
> New table references [order, product] but related `<table>` in `<path>` also references [invoice, customer] — are these intentionally omitted?

---

## When to skip these checks entirely

- The new table is in a **migrations file** rather than the schema source — schema-checks operate on the canonical schema definition (`pgTable()`-style), not migration DDL. If the schema file isn't touched, treat the migration as opaque.
- `SCHEMA_DIR` is empty AND no schema file is detectable from the diff or repo tree — write `Q7-Q9: SKIPPED — schema directory not found` and continue.
- The PR is a refactor of existing schema (renaming, splitting, FK adjustments) without genuinely-new table domains — Q7 is unlikely to apply.
