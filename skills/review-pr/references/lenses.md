# Lens catalogue

The question set a reviewer applies per changed file. Loaded by **Subagent 1** (Phase 2 reviewer) alongside `finding-output-format.md`, and by **V3** (Phase 3 deep gap check) for the lens axis of its gap check — the entries `lens-map.md` marks `q_map: new-ground`, which no Q-number reaches. `lens-map.md` decides *which* of these apply to a given file; this file defines what each one asks and what counts as an answer.

V3's lens axis is the newer of the two loaders and is only as live as its prompt: check `verification-subagents.md` for a "lens axis" section in V3's prompt before relying on it. A V3 that walks Q1–Q9 alone examines none of the `new-ground` lenses while reporting full coverage, and the per-file cells are then the only thing covering them.

It exists as a separate file because the Q1–Q9 list answers "what kind of problem is this?" and the lens list answers "what did the reviewer have to **do** to see it?" Those are different axes, and only the second one predicts whether a defect can be caught at all. A reviewer can answer all nine Q's honestly, from the diff, and still miss ~85% of what escapes.

---

## Where the numbers come from

Every lens below carries an evidence count from a study of **712 root-caused escaped defects** — bugs whose root cause was established during debugging, long after the introducing change merged. Four independently-mined slices: three partitioned by codebase (154 / 309 / 120, spanning eight codebases and four unrelated stacks) and one 129-record cross-cutting slice of incidental discoveries ("while I was in here I noticed…").

The number that bounds everything else. For each defect: **could a reviewer seeing only the introducing diff have caught it?**

| Slice | yes | partial | no |
|---|---|---|---|
| Bug-fix sessions | 26% | 36% | 38% |
| Feature / performance sessions | 14.6% | 35% | 50.5% |
| Other codebases | 18% | 47% | 35% |
| Incidental discoveries | **0%** | 22% | 78% |

**A perfect diff-only reviewer tops out at roughly 15–20% of what escapes.** The ceiling is set by where the reviewer looks, not by how hard it reads. That is the entire argument for Tier 2.

What the reviewer would have had to *do*, consistent across all three root-cause slices:

| Action | Share |
|---|---|
| **Open an untouched caller, or compare against the near-identical sibling** | **~30%** |
| Run a query against real data | 10% / 2% (stack-dependent) |
| Enumerate *all* paths of a rule class, not just the changed one | ~10% |
| Interrogate what the tests do **not** cover | ~10% |
| Run the app / drive the UI | ~7% |
| **Read the added lines more carefully** | **6%** |

Reading harder is the smallest lever in the table.

### How to read the counts

Counts are **hand-adjudicated records**, not grep hits: candidates were pulled by regex, then every candidate's root cause was read and near-misses were rejected. Three consequences for anyone re-deriving them:

- **They overlap.** One defect can instantiate two lenses; the sum across lenses exceeds 712 by design.
- **They count records, not distinct defects.** Roughly 20 defects appear twice under different slices. Where dedup materially changes a count it is stated inline.
- **`diff-visible` means the slice recorded `would_a_diff_show_it: yes`.** It is a lower bound on catchability, and it is the number to look at when deciding how much a lens is worth.

Every lens here clears the bar of **three independently-observed escaped defects**. Nothing was retained on plausibility.

---

## The meta-lens

The most transferable single rule the study produced. It subsumes much of Tier 1 and it applies to every file type, so `lens-map.md` marks it always-on.

> **If this code took the wrong branch right now, would anything anywhere emit a signal?**
> No throw, no log, no failing assertion, no visibly wrong value → this line needs scrutiny **proportional to its silence, not to its complexity.**

This inverts the normal allocation of review attention. Reviewers slow down at dense, clever code. The evidence says that is the wrong place to slow down.

Across the 129 incidental discoveries, the recorded reason nobody noticed:

| Share | Mechanism |
|---|---|
| **38.8%** | **No error signal** — the wrong path returns success. No throw, no log, no 4xx, no red test. |
| **36.4%** | **Reads as correct** — a guard exists, an index exists, the column *is* selected. Visual review passes. |
| 27.1% | Dormant precondition — needs a rare data shape or a second caller |
| 24.8% | Split across a seam — each half correct in isolation |
| 22.5% | Plausible wrong output — a number or a date that looks like data |
| 15.5% | Masked by coincidence — a null-fallback, a `.limit(1)`, a default that happens to match |

Mechanisms are non-exclusive; 103 of 129 (79.8%) carry at least one of the silent-by-construction tags. A hand re-read of all 129 found that **114 (88.4%) emitted no signal of any kind** on the defective path, and only about **7 (5.4%)** produced something normal CI or monitoring would have shown as red — **3 of those 7 were misattributed anyway** (a teardown warning read as runner noise; a red lint read as "my change broke the build"; a constraint violation read as a flaky local machine).

Note the second row separately from the first. "Reads as correct" is **independent** of "nothing screams": 36 records read as correct on visual review *without* being silent. A guard that exists and does nothing defeats a different reviewer instinct than a swallowed error does, and needs its own question.

### The failure-open asymmetry

Defects overwhelmingly failed **open**, not closed, and failing open is invisible by construction. A limiter that locks people out generates complaints within the hour; one that quietly stops limiting produces an absence of rejections, which reads as "nothing to fix". A filter builder with no branch for one operator returns HTTP 200 with the entire unfiltered collection — a superset, which reads as "nothing matched the exclusion" rather than "the filter did nothing". A cache invalidation aimed at a key nothing registers resolves successfully against zero matching queries and cannot report a miss.

**When a change alters a gate, a filter, a limiter, or an invalidation, ask which direction it fails in. If it fails open, no observation point in the system will tell you.**

### Silent but simple — the shapes to actually look for

The 38.8% were not hard to understand. They were one to three lines:

- A bare `continue` inside a copy loop with **no counter and no log** — the caller is told "32 of 40 copied" and cannot distinguish 8 legitimately absent from 8 silently dropped.
- `default: return 0` in a unit-conversion helper that handles one unit family. Two separately-reported user bugs, months apart, collapsed onto this one branch.
- `default: return undefined` in a filter builder with no case for one operator the UI offers — the condition vanishes from the `WHERE` and the endpoint answers 200 with everything.
- An update payload object populated across ~40 lines and then **not passed** to the write call four lines later. The endpoint returns success; the rename does nothing.
- `?? "0"` on a field that exists on **none** of the shapes feeding the function — always `undefined`, always writes zero, and the parameter was typed `any` so nothing flagged it.
- `.limit(1)` with no `ORDER BY` choosing the row that determines a price. Stable in practice until the plan or heap order changes.
- `expect(row?.field).toBeUndefined()` — passes for free when the row was never found. Fifteen of them in one suite; the forty sibling `toBeNull()` assertions did not have the problem, which is exactly why the suite read as uniformly rigorous.
- A column read by two tables, the API response and the UI, that a repo-wide grep shows **no code path writes**. Permanently empty, and an always-empty column reads as "nothing is due" rather than as a bug.
- `[...list.sort(fn)]` — the spread is applied *after* the sort, so the sort mutates the cached array in place. The line contains a spread, so it passes every visual "am I copying before sorting?" check.
- A mutation invalidating a cache key that no query registers, so the list never refreshed after **any** delete. Users read it as "the page needs a refresh".

---

## Tier 1 — diff-local

The evidence is already on screen. These are the ~15–20% that were visible and still missed, because nobody asked that specific question.

| ID | Trigger, one line | Evidence (diff-visible) | Q-map |
|---|---|---|---|
| L1 | A `catch`, `default:`, fallback, or early `return` on a failure path | 84 (16) | new ground |
| L2 | A validator, schema, regex, or allow-list change | 64 (13) | refines Q5 |
| L3 | A statement inside a transaction callback; check-then-write | 23 (7) | new ground |
| L4 | `LIMIT` / `.limit(n)` / pagination / `[0]` / first-wins dedup | 25 (3) | new ground |
| L5 | A numeric value crossing a write boundary | 46 (8) | refines Q5 |
| L6 | `toISOString()` / date arithmetic on a user-picked date | 22 (8) | new ground |
| L7 | A guard or early return added **above** existing code | 34 (7) | new ground |

---

### L1 — Success-shaped failure return

**Trigger.** A `catch` with no rethrow; a `default:` case; a `||` / `??` fallback on a value that came from a lookup, a parse, or a fetch; an early `return` on an error branch; a write with no row-count check; an upsert that absorbs conflicts.

```
catch { }   catch (e) { logger.warn(...) }  with no rethrow
default: return 0 | "" | null | undefined | false        default: break
|| 0   || 1   || ""   ?? 0   ?? []   ?? false            on a lookup/parse/fetch result
.filter(r => r.status === "fulfilled")                   after Promise.allSettled
await Promise.all(tasks)                                 where a task returns Promise<boolean|null>
onConflictDoNothing()  /  ON CONFLICT DO NOTHING         with no conflict target
insert/update/delete with no rowCount / affectedRows / .returning() check
isBlocked: false | allowed: true | totalHits: 0          inside a catch or fallback
status 200 / "COMPLETED" / "SUCCESS" / "skipped"         on a branch where a sub-step failed
bare `continue` / bare `return` in a loop                with no counter and no log
counter += 1                                             on the line after a call that can no-op
process.exitCode never assigned on the failure branch
|| true   || echo   continue-on-error: true   set +e     in CI
const { data } = useX()                                  with `error` present but never consumed
```

**Asks.** Does this return a value the caller cannot distinguish from success?

**Positive finding.** An abnormal runtime condition genuinely arises — a throw, an unresolvable lookup, an unhandled enum case, a constraint conflict, a zero-row write, an unavailable dependency, a quota rejection — **and** a branch answers it with a value, status, or exit code identical in shape to the normal outcome, **and** nothing throws, counts it at the aggregate level, or logs at error level. Warn-level or console-only counts as no signal.

**Not a finding.**
- *Truncation with no failure.* A hardcoded cap with no paging. Nothing failed; the code did what it was told. That is L4.
- *Wrong-but-loud.* A missing scoping predicate, a 500, an FK violation. The failure is signalled, often very loudly.
- *Hangs.* A floating promise whose `finally` never clears the loading flag. A permanent spinner reads as "still working", not as success.
- *Error flattening.* A `catch` that substitutes a static message for a specific one. A degraded signal is still a signal.
- *Code that was never wired.* A payload assembled and never passed to the write. Nothing failed and no handling branch exists — that is L10.
- *The inverse.* A benign empty run classified as a hard failure. Same family, opposite sign.

**Evidence.** 84 instances, 16 diff-visible (A 21 / B 33 / C 15 / I 15); ~71 after dedup. Largest Tier 1 lens.

**Q-map.** **New ground** with respect to Q1–Q9. Silent failures appear in `SKILL.md` step 7's "additionally flag" bullet, which carries no Q-number — so nothing on the Q axis reaches the single largest Tier 1 class. V3 covers it only on its lens axis, which is why that axis exists.

---

### L2 — Validation that does not validate

**Trigger.** Any change to a schema, refinement, regex, allow-list, deny-list, gating predicate, or database constraint.

```
.partial()  .omit(  .pick(  .deepPartial()   applied to a schema ending in .refine( / .superRefine(
.optional()  .nullish()  .nullable()          newly added on either side of a contract
.default(                                     on an env var, a mode/target flag, or a security-relevant field
z.object({...})  with no .strict() decision
.min(0) with no .max(   |   z.number() with no .int()   |   z.string() with no .max(
safeParse( / parse(     whose return value is not assigned or not read
as T   as unknown as   JSON.parse(x) as   : any        on an external payload
regex literals lacking ^ $ \b   |   trailing \d* .* .+  after a bounded group
if (!value)  if (value)                       on a field declared nonnegative / optional / nullable
if (a && b) { crossFieldCheck }               guarding a cross-field rule on a partial-update path
ALLOWED_* / allowedRoles / allowedTypes       array literal whose members equal the whole enum
uniqueIndex(  unique(  primaryKey(            edited without the matching application-side key
```

**Asks.** Does this accept what it reads as rejecting, or reject what it reads as accepting?

**Positive finding.** A construct whose *purpose* is to accept or reject behaves differently from what its text implies. Concretely: a value that should be rejected is accepted; a legal value is rejected; the rule is structurally unreachable; or two layers that both claim to enforce it disagree. Recurring shapes:

- An update schema derived from a create schema via `.partial()`, losing the create schema's object-level cross-field checks **and** inheriting every privilege field the create path gated by other means.
- A cross-field rule written `if (start && end) { ... }`, so a partial update supplying one bound is never checked against the stored other bound.
- `""` and `0` straddling "absent" and "a real value" — the schema permits the empty string, the UI renders an empty box, and the resolver treats blank as "unset" and substitutes a hardcoded default.
- Validator and storage constraint describing different domains: an unbounded `min(0)` against a fixed-width integer column, so the raw driver error reaches the user.
- An unanchored pattern, or a trailing unbounded group that makes a precision option a no-op.
- Validation running after the irreversible step — an outbound call already placed, then its response parsed with an assertion instead of a schema, so the success recorder never runs and the retry duplicates.
- An allow-list widened to cover its entire enum, degenerating the filter into a no-op.
- `.default(...)` on an env var, so `safeParse(undefined)` **succeeds** and the fail-soft branch is unreachable.
- No `.strict()`, so a misspelled key is stripped and the schema default is substituted — a typo'd config validates successfully.

**Not a finding.**
- *A rule that was never declared anywhere.* No unique constraint on a logical key. Nothing claims to validate. (A rule declared in the ORM model and absent from the live database **does** qualify — there a declaration exists and lies.)
- *Loud, correct rejections.* A migration whose new CHECK fails against pre-existing rows.
- *Contract drift with no checking construct.* A response type declaring a field the endpoint never produces. That is L9.
- *Mapping and normalization defects* where no accept/reject decision exists. Those are L5/L6.
- *Vacuous test assertions.* High-frequency and real, but that is L15.

**Evidence.** 64 instances, 13 diff-visible (A 10 / B 25 / C 18 / I 11); ~56 after dedup.

**Q-map.** **Refines Q5.** Q5 already names "unvalidated input reaching dangerous sinks", but scopes it to input arriving at a sink. L2's dominant shape is the opposite: validation that is present, passes review, and does not hold. The Q5 wording does not oblige a reviewer to check whether a validator's text matches its behaviour.

> **The L1∩L2 junction.** Five records sit in both sets, at one specific point: *a validator permits a value (`""`, `0`, absent) that a downstream resolver treats as "unset" and replaces with a hardcoded default — no rejection, no log, 200.* If only one rule can be written from these two lenses, write it against that junction.

---

### L3 — Transaction and atomicity boundary

**Trigger.** A transaction callback; a helper called from inside one; a check followed by a write; a compensating or cleanup sequence; a claim-then-act cursor advance.

```
db.transaction(async (tx) => { ... })   with the root handle referenced inside the body
helper signatures: (db: typeof rootDb) | (conn: DB | DBTr) | (tx?: Database)
const handle = transaction ? transaction : ownTx      |   tx ?? this.db
try { ... } catch { log; continue }     INSIDE a transaction callback, with no rethrow
a delete/update awaited immediately BEFORE a transaction that reinserts the same rows
any mutation after the closing brace of a transaction (recalc, denormalised refresh, cache write)
.returning() on an UPDATE that advances a cursor / watermark / claimedAt / generation
SELECT then INSERT on the same logical key with no FOR UPDATE, no ON CONFLICT, no unique index
existingRows.length + 1  |  MAX(col) + 1        used as a new key or position
enqueue / publish / sendEmail / scheduleNext    INSIDE a transaction callback
Promise.race( / AbortSignal                     wrapped around work that owns a connection
```

**Asks.** Can these two operations be separated at runtime — by a different connection, a commit in between, a skipped branch, an abandoned promise, or a second writer?

**Positive finding.** Name the interleaving or the crash point, and name the state left behind. If you cannot name both, it is not yet a finding. Recurring shapes:

- A helper called from inside the transaction that issues its queries on the injected root handle. Two distinct consequences, both observed: writes autocommit while the transaction commits empty; or the request checks out a **second** pooled connection while holding the first, so at pool saturation every slot holds a transaction waiting for a connection that will never be released.
- The "reuse the caller's transaction if given" idiom typed loosely enough to accept the pool. The pool is truthy, every write escapes, and it type-checks.
- A compensating `DELETE` that runs on the auto-committing root handle before a transaction re-inserts — a failure rolls back the re-insert and leaves the delete committed.
- A delete/write pair atomic on the main path and not on the skip path, so the key vanishes entirely.
- A derived-field recalculation relocated into the caller, executing after the service's transaction committed.
- Claim-then-act where the compensating revert is unconditional, so a concurrent edit landing between claim and failure is clobbered rather than preserved.
- A per-item `catch … continue` inside one transaction wrapping the whole loop: after the first failed statement the session is in failed-transaction state, every later statement is rejected, the driver converts `COMMIT` to `ROLLBACK`, and the in-memory counters incremented before the failure are reported as successes.
- A self-continuation scheduled from inside the transaction it depends on — a mid-batch throw rolls back the batch *and* the scheduled continuation, halting a migration silently.

**Not a finding.**
- *Client-side races.* A stale in-flight response overwriting newer state. A real race, no transactional boundary.
- *Clock-source mismatches.* A check constraint comparing an application timestamp against a database-defaulted column.
- *Non-idempotent loops with one actor.* A helper that zeroes siblings before setting the target, called once per row. No concurrency; a transaction would not help.
- *Ordering bugs inside one sequence.* A read placed after the delete whose rows it needed — sharing a transaction changes nothing.
- *Swallowed conflicts.* `ON CONFLICT DO NOTHING` with no target is L1: the transaction is intact, the conflict is silent.

**Evidence.** 23 instances, 7 diff-visible (A 4 / B 11 / C 4 / I 4); ~21 after dedup. The smallest Tier 1 lens, and the **most diff-visible (30%)** and most mechanically greppable — the best candidate in the whole set for an automated check rather than a review prompt.

**Q-map.** **New ground.** Q5 names "data integrity" but never atomicity; Q4 covers query shape, not concurrency. Nothing in Q1–Q9 obliges a reviewer to look at a transaction boundary.

---

### L4 — Bounded read over an unstable order

**Trigger.** Any bounded read or first-pick — in SQL or in memory.

```
.limit(  LIMIT  limit:  perPage  pageSize  offset  OFFSET  .skip(  .take(  .slice(0,  TOP
.orderBy(  ORDER BY  asc(  desc(  sortBy  .sort(
[0]   ?.[0]   const [row] =   .find(   .findFirst   rows[0]
new Map(xs.map(x => [x.id, x]))   ??=   if (!map.has(k))   dedupe   distinct   Set(
while (true)  do {...} while (rows.length === PAGE_SIZE)  BATCH_SIZE  CHUNK_SIZE  flushBatch
```
Highest-signal composite: **a `LIMIT`/`ORDER BY` in the same diff as an `UPDATE`/`DELETE` against that table.**

**Asks.** Can the source set contain more than one qualifying row — and if so, what determines which one comes back?

**Positive finding.** The set can hold more than one qualifying row and nothing in the query or the schema determines which. The strongest corroborating signal is a **sibling call site a few dozen lines away that does order correctly**, or a unique index that would have made it safe. Recurring shapes:

- `.limit(1)` with no `ORDER BY` selecting "the" row from a set with no uniqueness constraint enforcing one.
- `ORDER BY <timestamp>` with no tiebreaker where the timestamp ties in bulk-written data. One measured case: 99.3% of groups tie on one table, 0% on its interactively-written sibling — **the same code is correct against one table and nondeterministic against the other**.
- A paging loop that writes the table it pages. Under MVCC an update relocates the tuple, pushing processed rows past the offset and pulling unprocessed rows out of the window. Rows are skipped permanently and no counter notices.
- A hardcoded cap with no paging loop and no overflow signal; or truncation surfaced only to a server-side log while the client renders a partial view indistinguishable from a complete one.
- Dedupe applied **after** `LIMIT/OFFSET`, so a 20-row page renders one distinct entity — while the total, computed with `COUNT(DISTINCT …)`, looks right.
- A stale offset carried across a change to the result set (typing in a search box without resetting the page).
- The in-memory twin: `arr[0]` standing in for a missing discriminator while a neighbouring field in the same mapper uses `.find(isPrimary)` — and the producer sorts the array so index 0 is *not* the primary.
- First-wins map dedup on a key omitting a discriminator, collapsing rows that the table's partial unique index deliberately permits.

**Not a finding.**
- *Unbounded reads.* No `limit` at all. Nothing bounds it — a different problem.
- *Parameter-count blowups* from an oversized `IN (…)` list. Hard error, not silent order-dependence.
- *A page-size parameter dropped in transit.* Contents are correct and deterministic; only the size is wrong. That is L9.
- *`ORDER BY` on a semantically wrong column.* Deterministic and complete; no rows shift out of a window.
- *A test that fails to assert its pagination precondition.* That is L15, and it is the standard trap when writing an L4 regression test.

**Evidence.** 25 instances, 3 diff-visible (A 4 / B 12 / C 2 / I 7). Split 15 query-level / 10 in-memory first-pick. **3 of 25** is the headline: the rest turn on a fact the diff does not carry — a missing unique constraint, a tie distribution in real data, or a sibling that orders correctly.

**Q-map.** **New ground.** Pagination appears nowhere in Q1–Q9. Q4 covers query cost, not query determinism.

---

### L5 — Numeric value crossing a write boundary

**Trigger.** A number reaching a persisted destination — a column, an outbound message, a stored derived field.

```
Mg _mg Kg Grams PerUnit PerItem Per100 perKg Total unitsPer  1e3 1e6 * 100 / 100
CONVERSION_FACTOR  convertTo  normalizeUnit  formatWeight  ttl  timeout  Ms  Seconds
Number(  parseInt(  parseFloat(  +value  toFixed(  Math.round(  isNaN  || 0  || 1  ?? 0  if (!value)
numeric(  decimal(  smallint  integer(  real(  serial  CHECK (  z.number()  .min(0)  .int()  .max(
the SAME identifier appearing on two tables in one select({...})
as any / any[] / as unknown as   anywhere near a numeric write
```

**Asks.** What unit and domain is the destination declared in — and is this value in them?

**Positive finding.** The unit, scale, precision, or runtime type the value arrives with differs from what the destination is declared in. The load-bearing check is **opening the schema and reading the column's declared unit and domain**; if the diff does not tell you, that gap is itself the finding. Recurring shapes:

- Two same-named columns from different tables selected into one result under one name, and the wrong one is read — then rendered through the formatter for the other unit.
- Write path and read path disagreeing about which column holds the concept: the editable field writes one column, the calculation reads another with no editor, populated years earlier by a migration.
- A count multiplied by a unit-conversion factor and written into a unit-denominated column.
- A conversion helper with `default: return 0` for unfamiliar unit families — and a second copy of that helper one import away (this shape is simultaneously L8).
- A missing scale factor between a per-N rate and an absolute quantity, surviving because the value's only consumer was a sort key, where a uniform factor does not change the order.
- A unit that changed meaning across a dependency major (a TTL constant written when the library took seconds, read after it switched to milliseconds) — simultaneously L16.
- `Number("") === 0` passing an integer check; a discarded `safeParse` leaving a numeric config as a string so `Date.now() + "60"` concatenates.
- Falsy-zero: an honest `0` treated as absent and replaced by a fabricated magic number. **A reviewer requested one of these** — "check all falsy values" — against a field the schema declares non-negative.
- A rounding step turning a small positive quantity into zero, then into null, silently recreating the exact defect the change existed to fix.
- Two identifier spaces conflated because both are `number` — only the foreign key catches it, at runtime.

**Not a finding.**
- *Row multiplication from an under-correlated join wrapped in `SUM()`.* Spectacular magnitudes (135× on one row was measured), but the mechanism is join arity — that is L14.
- *Float comparison with no write boundary.* Genuine precision loss, nothing persisted.
- *Non-numeric coercions* — an object hitting `String()` and producing `"[object Object]"`.
- *Number formatting for the wrong locale.* Presentation, not a write boundary.
- *Two writers disagreeing about the source of truth.* Contract drift; the arithmetic is unit-correct in both. That is L9.

**Evidence.** 46 instances, 8 diff-visible (A 17 / B 21 / C 3 / I 5). Largest Tier 1 lens after L1. Five further records satisfy the "or date value" clause and are counted under L6 rather than double-counted.

**Q-map.** **Refines Q5.** Q5 already carries a type-coercion-at-write-sites block, scoped narrowly to `.toFixed()`/`String()` landing in numeric columns. L5 generalises the same instinct to unit, scale, precision and identifier-space, which is where 38 of the 46 instances actually live.

---

### L6 — Date serialization and timezone

**Trigger.** A temporal value crossing a form→wire, wire→column, or cache-key boundary; any date helper whose timezone parameter is optional.

```
toISOString  .split("T")[0]  .slice(0, 10)  JSON.stringify(<date>)  Date.parse  new Date(  Invalid Date
getUTCDate getUTCMonth getUTCFullYear   getFullYear getMonth getDate getDay setHours(0,0,0,0)
startOfDay endOfDay zonedTimeToUtc utcToZonedTime timeZone tz IANA Intl.DateTimeFormat
date(  timestamp(  timestamptz  time(  withTimezone  mode: "date"  mode: "string"
YYYY-MM-DD  ^\d{4}-\d{2}-\d{2}$  formatDate  dateKey  todayDate()
```

**Asks.** What frame is this value in on each side of the line, and does the destination store a **day** or an **instant**?

**Positive finding.** A temporal value's meaning changes as it crosses a boundary: the calendar day shifts, the day component is dropped, the type degrades to a string or to `null`, or two sides of a comparison are evaluated in different frames. Recurring shapes:

- The archetype, four records across three slices: a picker yields a `Date` at local midnight, the handler does `value.toISOString().split("T")[0]`, and for any positive UTC offset the stored calendar date is the previous day. In each case the single-row edit path carried the identical hazard a few hundred lines away, and the schema accepted the wrong day because it only validated the `YYYY-MM-DD` shape.
- Producer and consumer building the same day key in different frames — local accessors on one side, `toISOString().slice(0,10)` on the other — disagreeing between local midnight and the offset boundary, while a local weekday check in the same function disagrees with both.
- A key-derivation helper whose timezone argument is optional and omitted at one call site while its sibling six lines below passes one. The cache key has no subscriber, so the optimistic update silently no-ops.
- A date crossing a JSON boundary and returning as a string — and the inverse, where a raw templated projection bypasses the column decoder and the wire-format text reaches a caller expecting a date object.
- An invalid date serializing to something that silently means "no filter": `JSON.stringify(new Date(NaN))` is `null`, so a range bound comes back null and the query fires **unscoped**. Sibling: a formatter with no validity check returning the literal `"NaN-NaN-NaN"` to the API from six call sites.
- A date-only value resolved to a timestamp boundary inconsistently with its siblings, so an inclusive-looking range silently excludes its final day — with an existing test pinning the exclusive behaviour, making it read as deliberate.
- A lenient constructor accepting a semantically wrong day (Feb 30 rolling forward rather than failing).
- A timezone re-derived from the editor's browser and written over the persisted one, so editing a schedule created elsewhere silently moves when it fires.

**Not a finding.**
- *An unvalidated timezone identifier throwing at a formatting API.* Timezone-flavoured; the shape is missing input validation.
- *A global `Date` replacement in test setup breaking bare `Date()` calls.* A constructor/callable contract issue.
- *Application clock vs database clock skew.* Two timestamp sources, not a zone or serialization problem.

**Evidence.** 22 instances, 8 diff-visible (A 5 / B 5 / C 7 / I 5). **Best diff-visible ratio in Tier 1 (36%)**, because the offending token is usually literally in the diff — half the instances are one token applied to a user-picked calendar date.

**Q-map.** **New ground.** No Q covers temporal correctness.

---

### L7 — Code added above making code below unreachable

**Trigger.** Any new `return`, `throw`, `case`, guard, filter, or default introduced **earlier in execution order** than existing code — higher in the function, earlier in a chain, upstream in the data flow, or earlier in registration order.

```
a new return / throw / if (…) return in the FIRST 10 LINES of a changed function
guard assert invariant requireX @UseGuards middleware beforeLoad interceptor .use(
else if   switch (   case    default:   ??   ||   &&  as the FIRST operand   ?.   continue   break
a new member added to a const map / enum, next to any >= or <= against that map elsewhere
an allow-list array literal gaining an element   |   .includes( against a list whose size changed
tryCatch(fn(...)) vs tryCatch(() => fn(...))    |   captureException as the FIRST statement of a catch
a default value added to a prop or form field that a validator tests for ABSENCE
```

**Asks.** What below this just became unreachable, or just changed meaning?

**Positive finding.** An identifiable construct earlier in execution order is *why* the code below can never run or now means something different. The review action is concrete: after reading a new guard, early return, case, or default, **read what is below it and name which of those branches can still fire.** Recurring shapes:

- The canonical one, three times across three slices: `if (!user || !user.permissions) return false;` placed **above** `if (user.type === ADMIN) return true;`. Every admin is denied for the whole async load window, and permanently if the object legitimately lacks the optional field.
- An `if / else if / else throw` chain that throws before a later branch can be reached — the branch handling the third kind of input sits below the throw that rejects it.
- A fallback chain where an earlier alternative always wins: `a || b` collapsing two distinct concepts so the caller's own `field || otherField` fallback is dead code.
- A leading term short-circuiting every guard after it: `enabled && !!a && !!b` where `enabled?: boolean` has no default — `undefined && …` is `undefined`, which a query library treats as truthy, so the guards are bypassed and the request fires with undefined bounds.
- An upstream normalizer emptying a downstream comparison — added comparisons that can never match because a setter's `switch` already collapsed the vocabulary.
- `continue` scoped wider than intended, aborting the whole loop iteration rather than the one block it was meant to skip.
- Guard registration order in a middleware chain, so a diagnostic route answers identically whether the dependency it probes is up or down.
- Argument expressions evaluating before the wrapper meant to guard them — a helper taking an already-constructed promise runs its callee during argument evaluation, before the `try` is entered. The synchronous sibling takes a thunk and is immune, which is what makes the asymmetry invisible.
- A new member appended to what a distant file treats as an **ordered ladder**, making `4 >= 2` true two files away. *The dangerous consequence of an enum addition lives in the files you did not change.*
- A variable defined above for one purpose and reused below for another — a privilege boolean computed for one feature substituted into an unrelated guard.

The most quotable instance in the corpus: **a guard added on one date silently made a feature branch added fifteen days earlier into dead code — both changes correct in isolation.**

**Not a finding.**
- *Gates whose enabling input is never supplied* — an option no call site passes, a column read everywhere and written nowhere. Nothing *above* causes it. Those are L12(a) and L10.
- *Impossible predicates born unsatisfiable* — an `IS NULL` branch on a `NOT NULL` column.
- *Never-matching guards from a copy-paste wrong column.* Dead-guard-shaped, but the cause is a wrong identifier.
- *Eager evaluation replacing short-circuit.* It makes **more** code run, not less.
- *Operator precedence errors.* Ordering of operations, not reachability.
- *Observability written before the thing it reports*, where nothing becomes unreachable. (The error-path variant, where a throw in the earlier statement skips the recovery below, **does** qualify.)
- *Guards missing entirely* on some paths. That is L8 or L17.

**Evidence.** 34 instances, 7 diff-visible (A 7 / B 13 / C 8 / I 6). Widest spread across slices of any Tier 1 lens. Frequently invisible in the diff **by construction**, because the change and the code it kills are in different files or were made weeks apart by different people.

**Q-map.** **New ground.** Dead and unreachable code appears in no Q. Q2 covers unnecessary *additions*, not code the addition silently killed.

---

## Tier 2 — one hop out

**~30% of all escaped defects.** These are the single highest-value lenses in the set. What defines a Tier 2 lens is not the defect class but **the hop**: the file to open is finite, named, and reachable from the diff without running anything.

Across the 220 records instantiating L8–L10, **only 18 (8.2%) were catchable from the introducing diff.** Every one of the other 202 was catchable by opening a specific artifact: the rest of the changed file, the sibling file, the call-site list, the write site for a read field, the key registry.

| ID | Trigger, one line | The hop | Evidence (diff-visible) | Q-map |
|---|---|---|---|---|
| L8 | A fix to a predicate, pure function, or WHERE clause | The rest of this file, then siblings, then a literal grep of the fixed fragment | 132 (11) | refines Q3, inverted |
| L9 | A function's throwability, nullability, arity, or return shape changes | Every call site of the changed symbol | 49 (5) | new ground |
| L10 | A column added to a select; a new cache key; an object built for a write | The opposite direction: grep the identifier for its missing end | 39 (2) | new ground |
| L11 | A shared/exported symbol modified for one caller | Every importer the diff does not touch | 30 (4) | new ground |
| L12 | An optional parameter added, or a guard whose scope moved | Every call site that does **not** pass it | 36 (7) | new ground |

---

### L8 — The second copy

**Trigger.** Any fix to a predicate, a pure function, a WHERE clause, a formula, a key template, or a business rule. Also any file whose basename shares a stem with siblings (`bulk*` vs single, `create*`/`update*`/`remove*`, list vs detail), and any commit body containing "parity with", "same as", "mirrors", "also".

```
added predicate fragments: isNull(deletedAt)  IS NULL  AND tenantId =  archivedAt  .filter(
added determinism: ORDER BY next to LIMIT 1  |  .limit(1)  |  a tiebreaker
added guards: assert*  require*Permission  verify*  checkAccess*  a new middleware in a chain
map/bucket/row-id templates: `${a}-${b}`  .join(":")  new Map(x.map(i => [i.id, i]))
enum-case switch or allow-list array gaining a member  |  default: return undefined
serialization helpers: toISOString  getUTC*  unit conversion  currency/weight scaling
```

**Asks.** Does a second copy of this logic exist, and is it in this diff? Search by **behaviour**, not by name.

**What the reviewer must open**, in this order — each step is cheap and the first is nearly free. **Hop 1 is the always-on obligation: every changed file in every PR owes it, whatever the file's type and whether or not anything assigned L8.** Hops 2–5 are owed only where a `file_types` row or a signal assigns the lens; there it runs at full strength and a cell answered without opening a file outside the diff is `not-examined`. The reasoning, and what each shape costs the ledger, is in `lens-map.md`, "Always-on L8 is hop 1" — do not re-derive it here.

1. **The rest of the file you already changed** — the always-on hop. Scan the full post-image top to bottom for the same call, the same predicate, the same key template. A reviewer working from hunks has not seen it, and `clean` on an always-on L8 cell asserts this read and nothing more.
2. **The sibling files in the same directory.** List the directory and open every file whose name is the changed file's name with one word swapped.
3. **A literal grep of the fix's 3–8 token core** (`isNull(x.deletedAt)`, the key template, the conversion factor) — then grep for the **absence**: sites that have the surrounding shape but not the fixed fragment.
4. **The mirror operation.** Touched create → open update and delete. Touched bulk → open single. Touched the read → open the write.
5. **The canonical helper for whatever you just inlined**, in the shared packages.

> **The finding that should change how step 1 is weighted.** Of 132 instances, **at least 15 (11%) had the second copy inside a file the diff was already editing** — several within twenty lines of the changed hunk. Verbatim from the records: *"added error branches to three sibling hooks and missed the fourth — in the file it was already editing"*; *"omits all three guards that the subquery forty lines below carries"*; *"the adjacent update in the same block does carry the predicate, so the file reads as if scoping were handled"*; *"only 1 of 8 construction sites in the same file set the safe field"*. A further ~20 had the twin in a sibling file in the same directory. **Re-reading the whole file you just edited, looking for the same shape, would have caught roughly a quarter of this lens's yield at near-zero cost.**

> **The second finding, which explains why this class escapes.** The un-fixed copy is very often the one that produces the user-visible damage, because the *fixed* copy is the one someone already complained about. The fix appears to close the ticket.

**Positive finding.** Two or more places implement the same rule, predicate, or computation, and at least one lacks the correct version — whether the copies live in one file, two files, or a shared package and its fork. Recurring shapes: a corrected predicate with a byte-similar twin elsewhere; a new invariant applied at N of M sites of the same kind ("applied at 8 call sites, omitted from 3"; "five handlers add the guard, three do not"); two implementations of one computation drifting (a badge count and a list count); a copy-pasted block keeping the source block's column, comparing one id kind against a column holding another (same scalar type, so it compiles and the guard is a permanent false negative); two entry points to one operation where only one was hardened; a canonical helper that exists while one caller re-implements it; two predicates over the same data that must agree and do not (a display filter vs a dispatch filter); parallel pipelines with the rule wired into one; the same malformed predicate stamped across a family of sibling schemas.

**Not a finding.**
- *An application rule and a database constraint disagreeing.* The hop is the schema file, not a code twin.
- *An under-specified key with no second copy.* Nothing to sweep — that is L14.
- *A helper that existed and was not used*, with no divergence. That is a reuse miss (Q6).
- *Both copies identical and both wrong from birth*, with no fix on either. A shared design defect, not a second-copy defect.
- *Convention divergence* where no behaviour rule diverged.
- *"The same class probably exists somewhere"* stated without a named second site.

**Evidence.** 132 instances, 11 diff-visible (A 29 / B 47 / C 19 / I 37); ~117 after dedup. **18.5% of the entire corpus — the single highest-yield lens in the study.**

**Q-map.** **Refines Q3, with inverted polarity.** Q3 asks "did this diff duplicate logic that already exists?" L8 asks "does a duplicate already exist that this diff failed to fix?" Same search machinery, opposite direction, and only the second one is where the escaped defects are. A reviewer answering Q3 honestly can pass while the entire L8 class walks through.

---

### L9 — Contract change reaching only some consumers

**Trigger.** Any change to a function's throwability, nullability, arity, return shape, error vocabulary, a serialized field name, or the meaning of a sentinel or default.

```
throw / reject( ADDED inside a function that previously returned normally; return null → throw
signature edits: a new parameter, ? added/removed, | null, | undefined, .optional(), .partial()
return-type edits: T[] ↔ T, Promise<void> → Promise<boolean>, a destructure added inside a helper
renames of any SERIALIZED name: query/body keys, response fields, headers, enum string literals
call sites that IGNORE a result: await Promise.all( over status-returning calls, an unbound safeParse(,
   void fn(), .catch(() => {})
hand-built object literals feeding a write: .set({  .values({  return { a, b, c } inside a mapper
any change to a default: ?? 1, || 1, ?? "", ?? 0 — the "absent" encoding is what consumers branch on
```

**Asks.** Which consumers were not brought along?

**What the reviewer must open.**

1. **Every call site of the changed symbol**, found by grepping its exported name. This is the defining hop. The call graph is static and finite; sampling it is not an option.
2. **For a renamed or newly added serialized field**: grep the **string literal**, not the identifier, across both sides of the wire — the emitter, the reader, the response type, and any hand-written parser.
3. **For a schema or validator change**: the other consumer of that same schema. One schema repeatedly served as both the client resolver and the server validator, so changing it changed the client invisibly.
4. **For a throwability change**: every enclosing `try`, every error-classifying allow-list, and every fire-and-forget invocation. **A throw nobody awaits is not an error — it is a permanently stuck record.**
5. **For a changed return shape**: the destructuring pattern at each caller (`const [x] = …` vs `const x = …`). This single confusion produced multiple data-loss defects.
6. **For a widened constraint**: every `.find` / `.filter` / lookup still keyed on the old narrower key.

**Positive finding.** A contract is established or changed at one site and one or more *other* sites consuming it were not updated. Recurring shapes: a function gaining a throwing path whose consumers are fire-and-forget; a validation tightening on a shared schema that silently kills UI controls; a sentinel's meaning changing while two consumers still re-fabricate the old value; **producer and consumer disagreeing about which field holds the value** (the most repeated L9 shape, 7+ records — including three separate hooks each sending a page-size parameter under a name the shared helper never reads); a hand-built update payload that never mentions the newly added field; a return value that now carries meaning being discarded; a helper that destructures internally while the caller still indexes `[0]` and gets `undefined` forever; a builder invoked with 6 of 7 arguments while its sibling passes all 7; a guard's assumption invalidated by a new caller; an error-code extractor matching only one error class while other throw sites emit plain errors.

**Not a finding.**
- *A third-party contract changing under you on upgrade.* All consumers broke simultaneously; nobody was left behind. The hop is the dependency, which is L16.
- *Two statements in brand-new code disagreeing*, both inside the diff. That is careful diff reading, unless one is a pre-existing consumer.
- *A validator disagreeing with a column's domain.* That is L2.
- *A route returning the wrong entity* with no consumer that was ever updated. A plain defect, not a propagation failure.

**Evidence.** 49 instances, 5 diff-visible (A 11 / B 21 / C 10 / I 7).

**Q-map.** **New ground.** `SKILL.md` step 7 already requires a `consumers:` audit, but only for *new error values, sentinels and thrown exceptions* — it carries no Q-number, so no Q-axis pass reaches it, and it does not reach arity, return shape, nullability, or serialized field names, which is where 30+ of these 49 live. V3 reaches it on the lens axis only.

---

### L10 — Read/write asymmetry

**Trigger.** Anything consumed or produced whose counterpart is not in the diff.

```
a new column/field in a select({…}), a response type, or a type/interface
a new key string: queryKey:, invalidateQueries(, cache-prefix constants, event names, job names
.set( / .values( / .update( whose payload is a VARIABLE rather than an inline literal
mapper functions: return { … } inside a .map( following a select
cascade lists: an array of child tables iterated for a delete; deletedAt, archivedAt, tombstone
render-path filters: .filter(, hidden, excluded, isVisible
new optional args, feature flags, CLI flags
registration lists: DI provider arrays, prefix arrays, table lists in a copy routine, route registries
```

**Asks.** Does anything ever write / register / consume this?

**What the reviewer must open.**

1. **Grep the identifier in the opposite direction.** For every field the diff *reads*, grep for a writer; for every field it *writes*, grep for a reader. Two bounded greps. **Nine of these 39 instances die on this one step.**
2. **The key registry and the key invalidators, side by side.** Diff the set of registered key roots against the set of invalidated ones.
3. **The mirror handler** — specifically the *list of things each one touches*: child tables, derived counters, denormalized flags.
4. **The write path for every read filter you add, and the read path for every write filter.** If a row can be excluded on one side, ask what the other side does with it.
5. **The variable you built vs the variable you passed.** Trace the assembled payload to the call that consumes it — same function, but the two lines can be forty apart.
6. **The registration list the new thing must join.** These are enumerable and short: read the whole list, not the added line.

**Positive finding.** One end of a produce/consume pair is missing. Recurring shapes: a column read by the list view, the detail response and an index built for it that **no code path writes** (a repo-wide grep finds no insert or update setting it); a response type declaring a field the endpoint never emits; a parser writing a value the next stage's field-by-field mapper never carries forward; a cache key **invalidated but never registered** (one key had 24–26 invalidation sites and zero registrations, after a commit replaced the server call with a local computation and deleted the registering query) and the inverse, **registered but never invalidated** (a key prefix missing from the shared invalidation list, so a list never refreshed after any delete); an update object populated across ~40 lines and never handed to the write; a column selected and then dropped in the row-to-DTO step; a soft-delete that never cascades to one child table; a filter applied on read but not on write, so parties hidden from the UI still receive the downstream action; a read filter over a field nothing writes, so new records silently vanish from any saved view; a registration site that was never added; a flag resolved onto a run object and consumed by nothing outside its own unit tests.

**Not a finding.**
- *Cache-key granularity bugs* — a key carrying an element the request never sends, or invalidation prefixes matching too broadly. Both ends exist; that is a key-design problem.
- *A cache key missing an input that changes the output.* "Enumerate the inputs", not "one end is missing".
- *Client-side-only enforcement.* Both ends exist, on different trust sides — that is L19.
- *An unexpected extra writer* on a read path. Nasty, but it is an extra producer, not a missing one.

**Evidence.** 39 instances, 2 diff-visible (A 11 / B 14 / C 3 / I 11). **The least diff-visible lens in the entire study (5%)**, and structurally so: a missing invalidation resolves successfully against zero matching queries and cannot report a miss.

**Q-map.** **New ground.** Nothing in Q1–Q9 asks whether the counterpart exists.

---

### L11 — Shared symbol changed for one caller

**Trigger.** Any modification to a symbol exported from a shared location, plus any module-level mutable state.

```
defaultOptions  defaultProps  defaults:      and call sites that override SOME options
an app-wide registered provider / interceptor / guard; middleware registered once for all routes
module-level mutable containers: export const … = new Map(  new Set(  = []  let cached
a lazy get*() with no dispose/close/end
a single hardcoded registry/instance name used as a map key across many decorated sites
in-place mutators on data you did not create: .sort(  .reverse(  .splice(  Object.assign(param
   — grep `[...x.sort()]` specifically; it passes every "am I copying before sorting?" eyeball check
.partial() .omit() .pick() .extend() on a shared validator that is ALSO a client form resolver
a new member of an exported constant map, next to any >= / <= against that map elsewhere
replacing globalThis.X / global.X in test setup
```

**Asks.** Who else consumes this, and what does each of them now do?

**What the reviewer must open.** For every symbol the diff modifies that is exported from a shared location: `grep -rn "<symbolName>"` across the repo, **enumerate the importers**, and open the ones the diff does not touch. If the count is greater than one, the PR must state what each other consumer now does.

**Positive finding.** Two arms, worth distinguishing because they need different reviewer actions.

*Arm A — a shared symbol changed for one consumer (19 records).* A shared unit-conversion helper's missing-unit branch rewritten to suit one importer while two others still depend on the old assumption; sixteen local copies of a "first row or throw" helper consolidated into one shared export whose predicate differs (falsy check vs strict-undefined), silently changing ~115 call sites — for arrays of primitives the old predicate throws on a leading zero where the new one returns it; a shared count-query builder corrected for one of four consumers, breaking the invariant that they sum to the total; a globally registered guard flipped from fail-open to fail-closed for one use case, taking an unenumerated health-probe route with it; a validation rule attached to a schema that is *also* the client form's resolver; a shared constant map gaining a member that an untouched consumer treats ordinally as a privilege ladder; a shared query gaining an exclusion filter that empties a second consumer's display.

*Arm B — shared mutable state (10 records).* A third-party module-level timer map keyed by an instance name that every call site leaves at the same default, so one unblock clears the shared array for the whole application; a test bootstrap replacing the global date constructor with a class, breaking third-party code that calls it without `new`; a merge helper mutating its caller's freshly-read arrays in place; `[...list.sort(fn)]` mutating a cached array before the copy is made; a lazily-built pool singleton with no dispose path; a global telemetry scope tag set per tenant and never cleared.

*The inverse variant, worth stating explicitly.* A permission helper denies during its own loading window; the author patched **one call site** inline rather than fixing the helper, leaving seven other consumers broken. Same blast-radius blindness, opposite direction.

**Not a finding.**
- *A bug inside a shared symbol with no modification event.* A defect, but nothing was changed *for* a caller.
- *A shared helper missing a predicate since day one.* Missing from birth is not a per-caller change.
- *The shared helper was **copied**, not modified.* That is L8.
- *State that was **not** shared* — in-process counters across worker processes multiplying an effective limit. The defect is the absence of sharing.
- *A caller sending one parameter name while the shared helper reads another.* Nothing shared was modified — that is L9.

**Evidence.** 30 instances, 4 diff-visible (A 3 / B 18 / C 6 / I 3); 29 distinct. Only 5 of 30 were reachable by careful reading of the diff alone.

**Q-map.** **New ground.** Q6 asks whether the diff *reimplements* something shared; the class sweep at `SKILL.md` step 5 computes blast radius for a *finding*. Neither asks for the blast radius of the PR's own edit to a shared export.

---

### L12 — Parameter and coverage drift

**Trigger.** Any new optional parameter, option, flag or field; any recursive call; any guard whose scope moved; any narrowed condition.

```
signature-side: ?:  options?: {  = {}  = false  = []  = "skip"  = 1   on an exported signature
a self-recursive function that REBUILDS its argument object instead of forwarding it (missing ...options)
tx / trx / transaction( — and inside a transaction callback, the root handle
cancellation plumbing: signal, abortSignal, AbortController — check sibling calls that omit it
a parameter present in a signature but ABSENT from the following where( / and( / eq( chain
guard-shape asymmetry: if (a && b) next to a sibling if (a); if (payload.start && payload.end)
numeric truthiness: if (!value), !count   on a field whose validator permits zero
a guard idiom (|| 1, ?? 0) sitting INSIDE one arm of an if/else
removal of an isNull( / or( branch from a predicate inside a diff labelled "fix"
new <ErrorClass>(  — count construction sites whenever a field is added to the class
```

**Asks.** Does any call site pass it — and which branch just lost coverage?

**What the reviewer must open.** Two hops, both mechanical:

1. **For every parameter, option, field or flag the diff adds:** grep its name repo-wide and **count the call sites that actually supply it.** Zero means the feature is inert. More than zero but fewer than the total means naming the ones that do not is the finding.
2. **For every function the diff fixes:** grep `<functionName>(` and sweep **all** call sites, not the cited line. Both of this lens's "1 of N sites updated" findings were caught exactly this way.

**Positive finding.** Five sub-arms:

- **(a) The inert option (11 records).** A documented CLI flag parsed, validated and resolved onto the run object that **nothing outside its own unit tests reads** — and the tests assert it was *resolved*, never that it changes output. A host-fingerprint verification option accepted by the verifier, with no storage column, never selected, never passed at the call site: verification has never run. A lead-time tier consulted only when an optional id is supplied, which **all six call sites omit** even though the row carries the id. An optional "safe message" field set at **1 of 8** construction sites, defaulting to the unsafe value everywhere else.
- **(b) The lost hop (9 records).** A recursion that does not carry the copy-mode flag into child calls, so every nested level reverts to reading live data; the same recursion omitting the error-policy option so children silently fall back to the permissive default; a scoping identifier forwarded to the *validation* call and dropped one hop later in the three destructive `DELETE` statements, which execute unscoped; a cancellation signal threaded through the read and export paths but **not** the destructive pass.
- **(c) The silent default (6 records).** A key-builder's fallback calling its date helper with no timezone argument, unlike its sibling six lines below; four call sites taking a default that skips the protective branch; an `enabled?: boolean` with no default, where `undefined` is treated as enabled by the query library.
- **(d) The guard that moved (5 records).** A divide-by-zero guard relocated so it covers only one of two branches, and the other writes `Infinity` to a numeric column; a filter applied only in the `else` arm; a fix for a swallowed error written as a top-level guard on the combined error state, so an auxiliary query's failure now blanks the entire view.
- **(e) The narrowed condition (5 records).** **A reviewer demanded `if (!value)` to "check all falsy values" against a field the validator declares non-negative — so a legal `0` is now silently discarded.** A soft-delete predicate bundled into an unrelated join rewrite, so previously-working records began 404ing. A detector scoping its candidate set via an `EXISTS` join onto the parent table, structurally blind to exactly the orphan population it exists to report.

**Not a finding.**
- *A wrong argument rather than a drifted one* — an optional transaction parameter handed a connection pool. A wrong value at a call site, plus a type that is too wide. That is L3.
- *The check was never written on that path.* No narrowing or scope-move event — that is L8 or L17.
- *A hardcoded literal rather than an unpassed option.* That is L4.
- *A default whose meaning changed via a dependency upgrade*, with no first-party default touched. That is L16.
- *The flag is passed and simply does not gate the second callback.* Insufficient scope, not un-passed.

**Evidence.** 36 instances, 7 diff-visible (A 6 / B 15 / C 10 / I 5). Notably, the largest single detection bucket for this lens is *"open the schema / migration / index definition"* — several of these options were inert because the storage side was never built.

**Q-map.** **New ground.**

---

## Tier 3 — requires executing something

Cannot be answered by reading. This is where the largest-blast-radius defects hid: three of these four lenses have a **diff-visible count of zero across all 712 records**.

> **Execution policy for Tier 3 is deliberately deferred and is NOT defined here.** Whether the reviewer runs a query, mutates a line to watch a test fail, or installs under a changed lockfile — and under what permission, sandbox and cost budget — is a separate decision. This section defines only the trigger, the question, and the evidence. **Do not invent an execution policy from this file.** Until one exists, a Tier 3 lens produces at most an explicit *"cannot assess — would need &lt;the named check&gt;"*. That is the ledger's `cannot-assess` verdict, written on the cell with the named check as the artifact its `note` is required to carry. It is a complete answer, it does not block approval, and it is never recorded as `clean` — a whole tier that cannot be answered by reading is exactly why the vocabulary keeps a value of its own for it.

| ID | Trigger | The lens asks | Evidence (diff-visible) | Q-map |
|---|---|---|---|---|
| **L13** | A claim depending on a data distribution — nullability, cardinality, "this never happens", "that table is empty" | **Run the query and publish it.** Published-query claims verified 19/19 and 11/11 in the earlier review audit; bare assertions 0/2. | 35 (**0**) | new ground |
| **L14** | A query, join, DELETE, UPDATE, map key, or cache key over a multi-column identity | Does the predicate include **every** component of the key? | ~40 (2) | spans Q4, Q5 |
| **L15** | A new test, CI task, guard script, or type-level constraint | **Have you watched this fail?** Mutate the line it claims to defend and confirm it goes red. | ~30 (4) | new ground |
| **L16** | A lockfile-only or dependency-version change | Unreviewable as a diff. What behaviour changed for which consumers? | 12 (**0**) | new ground |

**L13 shapes.** A field that exists in the schema but that no row populates, so a feature gated on it never fires; a key assumed unique that is not; a predicate correct only on a non-empty set (a positive filter compiled as `EXISTS(child …)` silently drops every parent with zero children, while its negated form is trivially true and keeps them); a divisor legitimately zero for a known subpopulation; a junction table assumed populated that is 77.7% empty; a volume assumption that only bites at real cardinality. **Positive finding:** a statement with a count attached. *"This predicate assumes every parent has ≥1 child; 3 of 6 live parents have none."* **Not a finding:** a wrong-shape assumption settled by reading the producer rather than by querying — route that to L9.

**L14 shapes.** A join correlated on a prefix of the target's key, where the consequence depends entirely on what sits above it: under a plain `SELECT` a downstream map discards the duplicates (slow but correct); under `SUM()` every duplicate is counted (135× measured on one row, median 1,515× across one tenant); under `COUNT(*) OVER()` it inflates pagination and the dedupe runs after `LIMIT/OFFSET`. **A DELETE or UPDATE scoped by one column of a two-column key** — one hard delete keyed on the parent id alone removed that child from every other generation's snapshot; the adjacent statement in the same block *does* carry the predicate. A unique index coarser than the table's real identity, so a per-owner insert loop can never reach its second iteration and the extra rows are dropped with no error — and the table then *looks healthy*. A map or cache key built by concatenation that omits the discriminating component. **Positive finding:** name the key arity, name the bound components, and name which consequence applies — fan-out (cost), wrong aggregate (wrong number), or delete (row loss, unrecoverable). **Not a finding:** an *over*-specified key. Real defect, opposite direction.

**L15 shapes.** `expect(row?.field).toBeUndefined()` passing for free when the row was never found — and the sibling `toBeNull()` assertions not having the problem, which is why the suite reads as uniformly rigorous. A fixture that cannot exercise the branch: one entity seeded so a cross product degenerates to the diagonal; a raised page size that makes the whole dataset fit in one page, so a broken offset loop passes — **the precondition, not the assertion, carried the signal**. `cmd | grep <forbidden>` where `cmd` failed and printed nothing: grep matched zero lines over empty input and reported clean, unable to distinguish "nothing found" from "nothing examined". A suite gated on a dependency the CI image never installs. A build task whose input glob names a directory that does not exist, so no source change ever invalidates the cached pass. **Positive finding:** name the mutation. *"Delete this predicate / return `undefined` from this builder — the suite stays green."* **Not a finding:** a thin test that merely omits a case. L15 requires the assertion be *incapable* of failing, not merely incomplete.

**L16 shapes.** An unpinned global tool install in a container build resolving the `latest` tag at build time, so an upstream major release broke every image with no commit — and layer caching delayed the symptom by hours, decoupling it from any change. A major that silently stops reading a config surface, dropping the security pins carried there — where regenerating the lockfile to "fix the build" would have shipped unpinned images **and turned CI green**. A patch release adding a module-evaluation throw, so the symptom is connection-refused rather than a 500, and the introducing diff contains only a manifest and a lockfile. The same upgrade revealing the *old* version had been failing open (a derived partial schema silently dropping every refinement, measured 1 check → 0). A workspace-pruning container build failing on an import that resolves locally through hoisting — which neither local dev nor a full-workspace type-check can see. **Positive finding:** name the behaviour and the consumer set. **Not a finding:** a library default that surprises you with no version change involved — that is reading the dependency, not a version delta.

---

## Tier 4 — absence-shaped

Invisible because there is nothing to read. The defining tell for L17 is a **sibling declaration in the same file that has the companion**.

| ID | Trigger | The lens asks | Evidence (diff-visible) | Q-map |
|---|---|---|---|---|
| **L17** | Any construct with an obligatory companion | **What must also be present?** | ~24 (3) | refines Q1 |
| **L18** | An authorization guard, role check, or scope predicate changes | **Who else does this now admit?** | ~27 (2) | refines Q5 |
| **L19** | A UI element removed or hidden to fix a disclosure or visibility problem | Was the data removed from the **response**, or only from the render? | 8 records / 7 distinct (**0**) | refines Q5 |

**L17 shapes.** A schema edit whose branch contains zero generated SQL and zero journal entries — type-check and lint pass, because a schema file is a declaration of desired state and the ORM happily builds the query. A nullable column and a CHECK requiring it non-null added in the same transaction, so the CHECK validates against pre-existing rows and the whole deploy rolls back. A hot new predicate with no matching index — and its mirror image, an index whose leading column the same commit removed from the `WHERE`. A cascade covering six child tables and not the seventh; a query-key prefix list the new hook's key is missing from. A new user-facing string with no locale key. A package declaring a lint script and the shared config dependency while shipping no config file. A config key defined in one environment only.
**Positive finding:** point at the sibling that has the companion. *"Six entries in this cascade list, seven child tables exist"; "five handlers carry the guard, these three do not."*
**Not a finding:** two existing declarations that merely drifted — that is L9.

**L18 shapes.** An allow-list literal growing to cover its whole domain (`[ADMIN]` → `[ADMIN, USER]` where the enum has exactly two members: the filter now matches every row and the middleware is a no-op — **whenever an allow-list grows, count the enum's members**). A privilege variable computed for one purpose and reused for another, widening an unrelated right to every holder of a broad grant. Per-route instead of per-field authorization: an ownership-checked update route whose schema is `createSchema.partial()` and therefore inherits privilege fields as they accumulate — **the dangerous line was never in any diff; only its reachability changed**. An enum member appended to what a distant file treats as an ordered ladder. Asymmetric predicates between two halves of one feature — a filter's correlated `EXISTS` omitting the tenant and soft-delete guards its sort subquery carries ten lines away. Resource-level membership never checked, so the gate is an *absence* and appears in no diff. Authenticated encryption called without associated data, so ciphertext is not bound to its row and can be relocated across tenants and still decrypt.
**Positive finding:** enumerate the delta. *"Before: org admins. After: org admins ∪ every holder of grant X."* Best evidence is a count of the set the predicate now matches.
**Not a finding:** the inverse — a guard that got *narrower* and now wrongly denies. Real defect, wrong lens (that is L7 or L12).
**Note:** L18 is **exempt from the `intent-alignment` downgrade** in `false-positive-rules.md`. "The PR intended to change the guard" is precisely the case where the admitted set must still be enumerated. The exemption is **enforced by the rules table**: `intent-alignment` carries `exempt_lenses: [L2, L18]`, which the step 4.6 iterator evaluates against this finding's `Lens:` line before the rule's regex runs. Nothing is applied by hand.

What the exemption demands in return: **state the delta** — the set admitted before and after, or a name or count of what is newly reachable. A finding that only observes the guard changed and the description does not mention it *is* the scope-creep claim, carries no delta, and stays subject to the rule. Otherwise a `Lens:` line becomes a way to buy immunity from a rule that is usually right.

**L19 shapes.** The archetype: a disclosure ticket fixed by deleting a credential block from the component markup, leaving the response type and the endpoint untouched — the secrets still ship to the browser, sit in the network tab and in the client cache, now with no UI consuming them. **The fields were deleted from the markup, not from the payload**, and a reviewer checking the reported symptom sees it resolved. Hidden by a render filter but still acted upon: parties excluded from the sidebar still receive the downstream dispatch on confirm. Client-side-only enforcement: a limit clamped in three browser checks with zero server-side enforcement. A client-side route guard with no server counterpart, so a crawler receives HTTP 200 with the real authenticated HTML before the redirect fires. Over-shipping relative to the declared response type. Adjacent family: **redaction applied at one surface only** — a scrubber stripping a value from one field while the same value travels in a parallel field of the same payload.
**Positive finding:** the element is gone from the markup and the field is still in the response type, the projection, or the serializer — name where it still leaves the server, and name the second surface (network tab, client cache, server-rendered HTML, client bundle).
**Not a finding:** an element hidden for cosmetic or layout reasons. L19 needs the hide to be **load-bearing** — fixing a leak, enforcing a limit, or expressing a rule the server also has to uphold.
**Thinnest lens in the set.** 7 distinct defects clears the three-instance bar, but only just; treat a low-confidence L19 finding accordingly.

---

## Lens ↔ Q-number map

The coverage ledger and V3's gap check both need this, because a gap check that iterates only Q1–Q9 will report full coverage while every lens marked *new ground* goes unexamined — which is exactly the L15 failure shape the study found most often.

**V3 iterates `lens-map.md`'s `q_map` column, not this table.** That column is the machine-readable copy and the one to change first; this table is the reasoning behind each value, and it is here to be argued with rather than parsed. Two copies of one mapping drift, and the drift shows up as a lens quietly filed under a heading that does not cover it — so a `q_map` edit that this table does not justify is the edit to distrust.

| Lens | Relationship | Note |
|---|---|---|
| Meta | **new ground** | An attention-allocation rule, not a category. Always-on. |
| L1 | **new ground** | Lives in `SKILL.md` step 7, which has no Q-number and is therefore outside V3's Q axis — reachable only on its lens axis. |
| L2 | refines Q5 | Q5 covers input reaching a sink; L2 covers validators that pass review and do not hold. |
| L3 | **new ground** | Q5 names data integrity but never atomicity. |
| L4 | **new ground** | Determinism, not cost — Q4 does not reach it. |
| L5 | refines Q5 | Generalises Q5's `.toFixed()`-into-numeric block to unit, scale, precision, identifier-space. |
| L6 | **new ground** | — |
| L7 | **new ground** | Q2 covers unnecessary additions, not code an addition killed. |
| L8 | refines Q3, **inverted** | Q3: "did this diff duplicate?" L8: "does a duplicate exist that this diff failed to fix?" |
| L9 | **new ground** | Step 7's `consumers:` audit covers only new error values; no Q-number, and it stops short of arity/shape/nullability. |
| L10 | **new ground** | — |
| L11 | **new ground** | Q6 asks about reimplementation; step 5 sweeps a *finding's* blast radius, not the PR's own edit to a shared export. |
| L12 | **new ground** | — |
| L13 | **new ground** | — |
| L14 | spans Q4, Q5 | Fan-out is a Q4 finding; a key-short DELETE is a Q5 one. Neither Q names key arity. |
| L15 | **new ground** | Q1–Q9 never examine tests. `SKILL.md` has one suppression rule about tests and no check. |
| L16 | **new ground** | — |
| L17 | refines Q1 | A missing obligatory companion **is** an intent gap: the PR does not fully solve the stated goal. |
| L18 | refines Q5 | Q5 names "missing authorization"; L18 supplies the question that finds it. |
| L19 | refines Q5 | Q5's disclosure half, applied to the payload rather than the render. |

**Q-numbers with no lens.** Real gaps in the other direction, and worth stating plainly rather than leaving implied:

- **Q2 (unnecessary changes, scope creep, premature complexity)** — no lens. Expected: the corpus is root-caused *escaped defects*, and over-engineering does not produce a runtime defect, so it cannot appear in this evidence base. Absence here is a property of the corpus, **not** evidence that Q2 is worthless. Keep Q2; do not expect a lens to arrive for it.
- **Q6 (reusability / reimplements existing code)** — no lens asks Q6's question. L8 and L11 use the same search machinery pointed the other way. Keep Q6 as its own check.
- **Q7 (table overlap) and Q8 (1:1 consolidation)** — no lens. The corpus contains schema defects, but they are constraint-declaration drift and missing migrations, not domain-overlap or consolidation problems. Those are design-review questions the escaped-defect corpus cannot speak to.
- **Q9 (cross-table field consistency)** — no lens directly; L14 is adjacent (key arity) but asks a different question.

---

## Candidates — recurring classes with no lens, not adopted

The evidence surfaced these classes at or above the three-instance bar, and none of L1–L19 covers them. Recorded here so the next revision has a shortlist rather than a fresh mining run. **They are not part of the catalogue and no reviewer should apply them yet** — adopting a lens costs reviewer budget, and the tiering decision for these has not been made.

| Candidate | Instances | Why the existing set misses it |
|---|---|---|
| Cache / derived-state / invalidation-key desync | ~25 | L10 covers only the *missing end*. These have both ends and mismatched key shapes: a prefix that can never match, a read key fully parameterised while writers invalidate on a 3-element prefix, a key omitting an input that changes the output. All invisible by construction. |
| Framework / library semantics misuse | ~28 | Code correct against the library's *name* and wrong against its behaviour. Detection hop: open the installed library source, not your memory of it. |
| Config / tooling default matching nothing real | ~25 | Distinct from L16 (no version change). A host pattern written with the wrong separator; a cache input glob naming a nonexistent directory; a connection string matching neither environment. Syntactically valid, semantically empty. |
| React render / effect lifecycle and identity churn | ~15 | Memoized callbacks reading state omitted from dependency arrays; an effect declared before the state it depends on; a sub-component declared inside another's body remounting its subtree every render. |
| Sentinel / edge-value conflation | ~12 | One value meaning two things, permissive meaning wins. Distinct from L5: the value is legal and in range; only its *meaning* is overloaded. |
| Unbounded work sized by real data volume | ~12 | Correctness cliffs, not perf tuning — a synchronous commit of millions of nodes, a client-storage write exceeding quota whose exception the library swallows. Partly Q4, but Q4 stops at query shape. |
| Loading / partial state rendered as authoritative | ~10 | For every async read, what does the *third* state render as — in-flight, and refetch-error? A guard written `isError && !data` catches only the load error and misses the refetch error that a polling interval makes the common one. |
| Sensitive-data exposure surfaces | ~10 | L18 covers scope widening, L19 covers UI-vs-payload. Neither covers a raw driver error interpolated into a client message, or a sanitizer covering only some of the parallel channels carrying the same value (3 instances of that sub-shape alone). |
| Never-terminating async lifecycle | ~7 | A call that never settles when its backing store is down — it does not reject, it hangs. Only reconnection is bounded, not a hung command on a live socket. |
| Schema-constraint declaration drift (model vs live database) | ~7 | Distinct from L14 (a *predicate* missing a component) and L17 (a *companion* never created): here the constraint exists in the model and is wrong or absent in the database. |
| Error classification by matching human-readable message strings | ~5 | Two handlers classifying the *same* error from the *same* shared function into 400 on one route and 500 on the other, because their allow-lists carry different English substrings. |
| Input normalization — equivalent spellings compared as strings | ~5 | Two textual spellings of one address or path compared raw, collapsing distinct entities or failing to recognise identity. |
