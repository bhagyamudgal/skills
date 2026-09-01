# 11 category definitions: P1..P11

Loaded by **Subagent A** in Phase 2, before it answers any category. Each
category has a default severity that Subagent A can escalate with
`severity_reasoning`.

### P1. Intent coverage

Does the plan deliver the `stated_goal`? Trace each clause of the
goal to at least one step in `stated_steps`. Gaps are findings.

**Default severity**: Moderate (Serious if the gap is the stated
primary outcome of the PR).

**Worked example**:
- Goal: "Persist meal-level portion numbers in orders"
- Plan has steps for the write path but no step for the UI read path
- Finding: "Goal mentions persistence but plan has no step for
  reading the persisted values back into the UI. S3 persists 4
  fields; no step reads them on UI reload."
- Severity: Serious

### P2. Unnecessary complexity

Abstractions, config, or indirection not required by the goal.
Collapses scope-creep + overengineering into one bucket (same as
`/review-pr` Q2).

**Default severity**: Moderate.

**Worked example**:
- Plan creates a `PortionAggregationBuilder` class for a task that
  only needs one function call
- Finding: "Step S4 introduces a builder class for a one-shot
  aggregation. Goal doesn't require reusable aggregation; a function
  is simpler."
- Severity: Moderate

### P3. DRY (within-plan)

Duplicated logic across the plan's own steps. Not codebase-wide. P6
handles that.

**Default severity**: Moderate.

**Worked example**:
- Step S3 and Step S5 both describe validating `menuPlanId →
  accountId` with different wording
- Finding: "S3 and S5 duplicate the menu-plan ownership check.
  Extract to a shared helper referenced from both."

### P4. Performance

N+1 queries in plan steps, missing indexes for new WHERE clauses,
sequential awaits that should be `Promise.all`, unbounded
allocations.

**Default severity**: Serious if production-path, Moderate otherwise.

**Worked example**:
- Plan says "for each client, fetch their portions one at a time"
- Finding: "S6 loops over clients calling `getPortions` per client.
  Batch with an `IN` clause or a single JOIN."
- Severity: Serious

### P5. Security / multi-tenancy

**Default severity: Critical** for missing cross-FK validation on
write endpoints. Also covers: auth check coverage, input
sanitization, tenant isolation, secrets in code, unvalidated user
input reaching dangerous sinks.

**Required behavior**: for every new write endpoint, you MUST
address cross-FK validation. "No concerns" is invalid unless the
plan proves the endpoint is single-tenant-scoped or all FKs in the
request body are validated against the owned tenant root.

**Worked example (PR #4587 F1)**:
- Plan creates an upsert endpoint accepting `menuPlanId`,
  `menuPlanSheetId`, `accountMealId`, `menuPlanMealMenuId`
- Plan's auth step only validates `menuPlanId → accountId`
- Finding: "Upsert endpoint at S2 accepts 4 foreign keys but only
  validates ownership on `menuPlanId`. An authenticated attacker
  sends their own menuPlanId + a victim's sheetId/mealId: the row
  lands because FKs accept it, and the partial unique index prevents
  the victim's next legitimate save."
- Severity: Critical
- Recommended: "Add a step to validateMenuPlanOwnership that joins
  menuPlanSheetTable, menuPlanMealTable, and menuPlanMealMenuTable
  and asserts each belongs to the owned menuPlanId. One Promise.all
  of 3 SELECT 1 queries."

### P6. Reusability (codebase-wide)

Plan-declared symbols (functions, classes, components, hooks) that
already exist in shared packages. Uses the `/review-pr` Q6 STEP A /
STEP B algorithm, scoped to the plan's stated new symbols.

**Default severity**: Serious. Escalate to Critical if the existing
thing is in an auth / validation / crypto package.

**STEP A. Enumerate new symbols**: for every function / class /
interface / type / component / hook / method the plan proposes to
create, write one line `added <kind> <name> in <file>`.

**STEP B. Search aggressively**: for each enumerated item, run
exact-name `Grep` in `packages/` + `apps/`, plus semantic-root
`Grep` (drop domain prefixes/suffixes and search the remaining
verb/noun). Read candidate matches to verify they're real matches,
not substring collisions.

**Required audit field**. Include `reusability_searches:` listing
the Grep/Glob calls you ran for STEP B. Empty = invalid.

**Worked example**:
- Plan says "create `tryCatch` helper at S7"
- Grep finds `packages/try-catch/src/index.ts` exports `tryCatch`
- Finding: "S7 creates `tryCatch`, but `@fileseye/try-catch` already
  exports it. Reuse instead."
- Severity: Serious

**Known limitation**. Same as documented in `/review-pr` Q6:
P6 does NOT catch the case where an existing helper is called on
SOME code paths but should also be called on others. Flag those
under P9 Control-flow hazards instead.

### P7. Concurrency / atomicity

**Default severity: Serious**. Escalate to **Critical** if the write
is user-triggered on a concurrent cascade path (e.g., a single user
action fires 2+ parallel writes to the same row).

Every new write endpoint must be atomic or explicitly transaction-
wrapped. Flag:
- `findExisting + branch to create/update` patterns
- Sequential `SELECT → INSERT` without a transaction
- Race-prone duplicate detection via application logic
- Missing `ON CONFLICT DO UPDATE` / upsert primitives
- `setState → dispatch → setState` chains that could race on the
  frontend

**Required behavior**: for every new write step, you MUST address
atomicity. "No concerns" is invalid unless the plan explicitly uses
`onConflictDoUpdate`, `db.transaction(...)`, or a CAS primitive.

**Worked example (PR #4587 F2)**:
- Plan says "check if row exists via findExisting; if yes, update;
  if no, create"
- Finding: "S3 specifies `findExisting + branch` for the upsert.
  Two concurrent callers both miss in findExisting and both call
  create, hitting a unique-constraint violation (23505). Use
  `db.insert(...).onConflictDoUpdate(...)` with the partial-index
  targetWhere clause instead."
- Severity: Critical (UI has a cascade path firing concurrent
  writes on a single user gesture)
- Recommended: "Replace findExisting+branch in S3 with
  `onConflictDoUpdate` targeting the natural key. Inside a
  `db.transaction` so the history record write is atomic too."

### P8. Intent round-trip

**Default severity: Serious**.

For every new persisted field, the plan must specify the read path
that surfaces it. Flag fields that appear in a write step but have
no matching read-path step.

**Required behavior**: enumerate every new persisted field from the
plan's schema changes. For each, find the step that reads it.
Missing read-path is a finding.

**Worked example (PR #4587 F3)**:
- Plan schema step S1 adds 4 columns: `portionsPlanned`,
  `portionsOrdered`, `portionsProduced`, `portionsSold`
- Plan read step S6 only reads `portionsPlanned`
- Finding: "S1 persists 4 portion fields but S6 read aggregation
  only reads `portionsPlanned`. The other 3 fields will be write-
  only. Their stored values won't surface on reload."
- Severity: Serious
- Recommended: "Update S6 to thread all 4 portion fields through
  the aggregation helper so all persisted values round-trip."

### P9. Control-flow hazards

**Default severity: Serious**.

Early returns that build synthetic empty responses (`return { x: [],
y: null, z: {} }`). Check `stated_files` imports vs the function's
injected services: if an early return hardcodes empty state for a
field that another branch populates via an injected helper, flag.

**This is the Q6-known-limitation gap** from `/review-pr`: P9
specifically catches what P6 misses.

**Worked example (PR #4587 F4)**:
- Plan says: "if rawClients.length === 0, early-return with
  `{ components: [], mealMenuPortions: [] }`"
- Plan also says: "inject mealMenuPortionsService and use
  `getByMenuPlanAndDateRange` on the happy path"
- Finding: "S4 early-returns with hardcoded `mealMenuPortions: []`,
  but S5's happy path fetches this from `mealMenuPortionsService`.
  The early-return silently drops stored meal-level portions in
  the empty-client state, exactly the state where stored
  aggregates should still surface."
- Severity: Serious
- Recommended: "Hoist the `mealMenuPortionsService` fetch above the
  early return (ideally in parallel with `getClientsWithOffers`
  via `Promise.all`) and return its result in both the early-exit
  and happy-path branches."

### P10. Error handling

**Default severity: Moderate**. Escalate to **Serious** if the error
path leaks user data, drops a write silently, or fires an empty
user-visible toast.

Flag:
- Silent failures (caught errors swallowed without logging)
- Bare `catch { }` blocks
- Empty error toasts (`message: undefined` fallthrough)
- `Promise.all` for independent mutations (recommend
  `Promise.allSettled` + per-rejection logging)
- Removed error handling in modified code
- Swallowed errors in mutation hooks (`onError: () => {}`)
- Raw DB errors leaking to user via general exception filter

**Worked example (PR #4587 F6)**:
- Plan says "wrap cascade batch + upsert in `Promise.all` with bare
  catch that just refetches"
- Finding: "S7 wraps two independent mutations (cascade batch +
  aggregate upsert) in `Promise.all` and catches errors silently
  with a bare refetch. Use `Promise.allSettled` + `console.error`
  per rejection so a failed upsert doesn't get lost when the
  cascade batch succeeds."
- Severity: Serious (a dropped write is user-visible on the next
  save attempt)

### P11. Pattern consistency

**Default severity: Moderate**. Escalate to **Serious** if the
missing pattern is security-relevant (e.g., sibling services use an
auth middleware this plan skips).

New files must match conventions of sibling files. Grounded by
Phase 2 Subagent B's `patterns` map. If sibling services all have
a history table via `writeHistoryRecord` and the new service plan
doesn't mention one, flag.

**Worked example (PR #4587 E2)**:
- Plan creates `MealMenuPortionsService`
- Subagent B finds 3 sibling services, all using `writeHistoryRecord`
  to persist audit rows on mutation
- Plan has no history-table step
- Finding: "S1 creates `MealMenuPortionsService` without a history
  table. 3 sibling services (`ClientPortionsService`,
  `OrderItemsService`, `MealPlansService`) all write to `gs_*History`
  tables via `writeHistoryRecord`. Missing parity means audits will
  have a gap at this endpoint."
- Severity: Moderate
- Recommended: "Add a step for `gs_MealMenuPortionsHistory` schema
  (matching `client-component-portions-history.ts` structure) +
  `writeMealMenuPortionHistoryRecord` helper matching sibling
  pattern. Wire it into the upsert transaction."
