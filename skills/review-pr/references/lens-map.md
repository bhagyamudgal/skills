# File-type → lens map

The data that decides which lenses from `lenses.md` apply to a given changed file.

Loaded by **main** in Phase 1, which evaluates the whole map once and writes `LENS_ASSIGNMENTS` — the ledger's cell set, fixed before any reviewing happens — by **Subagent 1** (Phase 2 reviewer) with `lenses.md`, which is handed its files' assignments and returns a verdict per cell, and by **V3**, which reads `lens_index` to build the gap check's lens axis. Main assembles the verdicts into the ledger in Phase 3; the object's shape and its counter partition are `finding-state-schema.md`'s.

**`q_map` is read by V3's gap check**, which builds its lens axis from the `new-ground` entries **plus** every `refines-Q<N>-inverted` one, less `META` (`verification-subagents.md`, "The lens axis"). The column is live, not documentation: a lens filed under a Q-number it does not really belong to is removed from the gap check, silently and with no other symptom.

It is a **separate file, and it is data rather than prose, so that adding a file type or a lens is a one-row edit here and not a change to any pipeline step.** The same reason `false-positive-rules.md` holds a YAML table instead of narrative: the iterator contract lives in `SKILL.md`, the rows live in the reference.

---

## Why this file exists at all

**So that `not-applicable` is a defensible verdict rather than a silent skip.**

A coverage ledger means something only if a reviewer who examined nothing can be told apart from a reviewer for whom there was nothing to examine. Without a declared map, those two collapse into the same blank cell, and a review that skipped the schema lens on a schema file is indistinguishable from a review that correctly skipped it on a stylesheet.

That collapse is not hypothetical — it is the most common defect shape in the study behind `lenses.md`: **a check that reports success while covering nothing.** A gap check that iterates a stale category list and returns "no gap" for every category is exactly the vacuous-verification pattern (L15). This map is what makes the lens axis falsifiable.

Three rules follow from that, and they are the whole contract:

1. **A lens the map assigns to a file must produce a verdict.** `clean` and `finding` are answers. So are `not-applicable` with a reason and `cannot-assess` naming the artifact. Silence is not — it is recorded as `not-examined`, and that blocks approval.
2. **A lens the map does not assign has no cell at all.** It is not `not-applicable`; it is absent, unbudgeted and uncounted. That is what this file buys — a reviewer owes an answer for the assigned set and owes nothing for the rest.
3. **A lens applied to a file the map did not assign it to is fine** — the map is a floor, not a ceiling. Record the cell it produced; it is evidence the map needs a row.

---

## How to evaluate

For each changed file, the applicable lens set is:

```
applicable(file) = always_on
                 ∪ ⋃ { ft.lenses  | ft ∈ file_types  where matches(ft.detect, file) }
                 ∪ ⋃ { sig.lenses | sig ∈ signals    where sig.pattern matches the file's changed lines }
```

- **`file_types` match on path**, against the file's repo-relative path. A file may match several types; take the union, never the first hit.
- **`signals` match on content**, evaluated against the **post-image of changed lines only** (the `+` side of the unified diff), not the whole file. Same convention as `File: <path:line>` in `finding-output-format.md`. A signal that only appears in untouched context does not fire — the change did not introduce it.
- **Signals are the precise half of this map and file types are the coarse half.** When they disagree, they do not: both contribute, and the union is the answer. A date bug in a stylesheet is still a date bug.
- **Deleted lines fire signals too.** Seven signal rows carry `side: both` — `guard-inserted-or-removed`, `predicate-fragment-changed`, `contract-surface-changed`, `destructive-write`, `version-or-toolchain`, `principal-set-changed`, `ui-hidden-not-removed` — and between them they fire nine lenses: `L7`, `L8`, `L9`, `L11`, `L12`, `L14`, `L16`, `L18`, `L19`. A predicate removed from a `WHERE` clause never appears on the `+` side. **Count and read the list off the rows below; do not restate it from memory.** An earlier revision of this line claimed four lenses and named `L10`, which no `side: both` row fires, while omitting `L8` — the lens the highest-yield signal in the set exists to trigger. A deletion-blind reviewer running that list would have skipped the removal half of the largest lens in the catalogue.
- **Unknown file type**, matching no `file_types` row: fall back to `always_on` plus whatever `signals` fire, and record the row as `file_type: [other]`. The path is in the row, so the extension is recoverable from it; an extension that shows up repeatedly with real findings is a missing row here.
- **Generated, vendored, or lockfile paths** short-circuit: see `skip_paths`, which is matched before `file_types`. A lockfile is not unreviewable — it routes to `L16`, which is a different thing from being reviewed line by line.

Tier 3 lenses (`L13`–`L16`) are assigned by this map like any other, **but their execution policy is deliberately deferred and is not defined in `lenses.md` or here.** Until it is, an assigned Tier 3 lens resolves to a finding only where the diff itself carries the evidence, and otherwise to the `cannot-assess` verdict with the named check as its artifact. That is a complete answer and must not be recorded as `clean`. It is also why the ledger keeps `cannot-assess` as a value of its own rather than folding it into `clean`: a whole tier of this map cannot be answered by reading, and a vocabulary with nowhere to put that forces the reviewer to overstate what it examined — the exact dishonesty the ledger exists to prevent.

---

## Always-on L8 is hop 1

`L8` is Tier 2, and the ledger's rule is that a Tier 2 lens answered without opening anything is `not-examined`, not `clean`. `L8` is also `always_on`. Read together at full strength those two make every file in every PR owe the lens's whole hop sequence — siblings, a literal grep, the mirror operation, the shared helper — and one missed hop anywhere forbids approval. A rule that forbids every approval is not strict, it is noise: readers learn the coverage line is always red and stop reading it, which costs more than the lens ever returned.

So the always-on obligation is **hop 1 alone: re-read the full post-image of the changed file, top to bottom, for a second copy of the shape the diff just changed.** That is a real hop and not a formality — a reviewer working from hunks has not seen the rest of the file — and it is the one `lenses.md` measures at roughly 11% of L8's yield for near-zero cost. It is bounded by the file count, and the file is already open. `clean` on an always-on `L8` cell asserts exactly that read and nothing more.

**Hops 2–5 are owed where L8 is assigned by something other than `always_on`** — the `shared-package-export` file type, or the `predicate-fragment-changed` signal firing on the changed lines. There the lens is at full strength, and a cell answered without opening a file outside the diff is `not-examined`.

The alternative — dropping `L8` from `always_on` — was rejected: the yield being bought here is precisely the twin *inside the file the diff was already editing*, which no signal fires on, because the twin is in untouched context and signals only see changed lines. Narrowing the obligation keeps the reachable half of the lens; removing the row would lose it entirely.

---

## The map

```yaml
# ---------------------------------------------------------------------------
# lens_index — the registry. tier drives sequencing; q_map lets the Phase 3
# gap check reconcile the lens axis against Q1-Q9 instead of iterating a stale
# category list and reporting full coverage. `new-ground` means NO Q-number
# covers it: a gap check that only walks Q1-Q9 will never examine it.
# ---------------------------------------------------------------------------
lens_index:
  META: { tier: 0, q_map: new-ground,  name: "would anything emit a signal?" }
  L1:   { tier: 1, q_map: new-ground,  name: "success-shaped failure return" }
  L2:   { tier: 1, q_map: refines-Q5,  name: "validation that does not validate" }
  L3:   { tier: 1, q_map: new-ground,  name: "transaction / atomicity boundary" }
  L4:   { tier: 1, q_map: new-ground,  name: "bounded read over an unstable order" }
  L5:   { tier: 1, q_map: refines-Q5,  name: "numeric value crossing a write boundary" }
  L6:   { tier: 1, q_map: new-ground,  name: "date serialization and timezone" }
  L7:   { tier: 1, q_map: new-ground,  name: "code above making code below unreachable" }
  L8:   { tier: 2, q_map: refines-Q3-inverted, name: "the second copy" }
  L9:   { tier: 2, q_map: new-ground,  name: "contract change reaching only some consumers" }
  L10:  { tier: 2, q_map: new-ground,  name: "read/write asymmetry" }
  L11:  { tier: 2, q_map: new-ground,  name: "shared symbol changed for one caller" }
  L12:  { tier: 2, q_map: new-ground,  name: "parameter and coverage drift" }
  L13:  { tier: 3, q_map: new-ground,  name: "claim depending on a data distribution" }
  L14:  { tier: 3, q_map: spans-Q4-Q5, name: "composite key predicate missing a component" }
  L15:  { tier: 3, q_map: new-ground,  name: "a check that cannot fail" }
  L16:  { tier: 3, q_map: new-ground,  name: "dependency / lockfile / toolchain change" }
  L17:  { tier: 4, q_map: refines-Q1,  name: "missing obligatory companion" }
  L18:  { tier: 4, q_map: refines-Q5,  name: "authorization scope widening" }
  L19:  { tier: 4, q_map: refines-Q5,  name: "hidden in the UI, still in the payload" }

# ---------------------------------------------------------------------------
# always_on — applied to every changed file regardless of type. Kept to two:
# an always-on list that grows stops being always-on in practice.
# ---------------------------------------------------------------------------
always_on:
  - META   # silence-proportional scrutiny; see lenses.md "The meta-lens"
  - L8     # the second copy — HOP 1 ONLY. See "Always-on L8 is hop 1" below.
           # Scoped, not full-strength: the always-on obligation is to re-read
           # the full post-image of the file you just edited, looking for the
           # same shape. Hops 2-5 are owed only where a file_types row or a
           # signal assigns L8.

# ---------------------------------------------------------------------------
# skip_paths — matched BEFORE file_types. `route_to` sends the file to a lens
# instead of reviewing it. `skip: true` assigns the file NO lenses; it still
# gets a ledger row, with `lenses: []` and a `skip_reason` naming the rule that
# skipped it. The row costs one line and keeps files_changed == len(rows), the
# ledger's own lost-a-file check; dropping the row instead trips that check on
# every PR that touches an image or a build artifact, and a false alarm that
# fires constantly is one nobody reads when it is real. A file recorded as
# skipped is also auditable — a reader can disagree with the rule. A file that
# vanished is not.
# ---------------------------------------------------------------------------
skip_paths:
  - id: lockfile
    detect:
      path: ["**/*.lock", "**/*-lock.json", "**/*-lock.yaml", "**/Cargo.lock", "**/go.sum", "**/Gemfile.lock"]
    route_to: [L16]
    note: "Unreviewable as a diff by construction — 0 of 12 corpus instances were diff-visible."
  - id: generated
    detect:
      path: ["**/dist/**", "**/build/**", "**/.next/**", "**/node_modules/**",
             "**/*.generated.*", "**/*.gen.ts", "**/__generated__/**", "**/*.snap"]
    skip: true
  - id: binary-and-assets
    detect:
      path: ["**/*.png", "**/*.jpg", "**/*.svg", "**/*.ico", "**/*.woff*", "**/*.pdf"]
    skip: true

# ---------------------------------------------------------------------------
# file_types — coarse, path-based. Union, not first-match.
# ---------------------------------------------------------------------------
file_types:

  - id: db-schema
    detect:
      path: ["**/schema/**", "**/schemas/**", "**/models/**", "**/entities/**"]
      content: ['pgTable\(', 'sqliteTable\(', 'mysqlTable\(', '@Entity\(', 'defineTable\(',
                'CREATE TABLE', 'createTable\(', 'Schema\.define']
    lenses: [L2, L5, L10, L13, L14, L17]
    note: "L17 first: a schema edit with no migration in the same change is the top-severity
           recurring class in this evidence base, and the missing file is by definition not
           in the diff. Q7-Q9 also apply when the change ADDS a table — that is a separate
           flag (INCLUDE_SCHEMA_CHECKS), not a lens."

  - id: migration
    detect:
      path: ["**/migrations/**", "**/migrate/**", "**/*_migration.*", "**/drizzle/**/*.sql"]
      content: ['ALTER TABLE', 'CREATE INDEX', 'DROP COLUMN', 'ADD CONSTRAINT']
    lenses: [L13, L14, L17]
    note: "L13 because a migration's correctness depends on the data it runs against, not on
           the DDL text: a CHECK added beside its own nullable column validates against
           pre-existing rows and rolls back the deploy."

  - id: query-or-repository
    detect:
      path: ["**/repositor*/**", "**/queries/**", "**/dao/**", "**/*.repository.*", "**/*.query.*"]
      content: ['\.select\(', '\.from\(', '\bSELECT\b.*\bFROM\b', '\.innerJoin\(', '\.leftJoin\(',
                'db\.query\.', '\.where\(', 'createQueryBuilder\(']
    lenses: [L1, L4, L5, L10, L13, L14, L18]

  - id: service-or-domain-logic
    detect:
      path: ["**/services/**", "**/*.service.*", "**/domain/**", "**/usecases/**", "**/handlers/**"]
    lenses: [L1, L3, L5, L7, L9, L10, L11, L12]

  - id: http-endpoint
    detect:
      path: ["**/controllers/**", "**/*.controller.*", "**/routes/**", "**/api/**",
             "**/app/**/route.ts", "**/pages/api/**"]
      content: ['@(Get|Post|Put|Patch|Delete)\(', '@Controller\(',
                'export async function (GET|POST|PUT|PATCH|DELETE)',
                'router\.(get|post|put|patch|delete)\(', 'app\.(get|post|put|patch|delete)\(']
    lenses: [L1, L2, L9, L12, L17, L18, L19]

  - id: validator-or-schema-definition
    detect:
      path: ["**/validators/**", "**/validation/**", "**/*.schema.ts", "**/dto/**", "**/*.dto.*"]
      content: ['z\.object\(', 'z\.string\(', 'yup\.', 'Joi\.', 'JSONSchema', 'class-validator']
    lenses: [L2, L5, L6, L9, L11, L12]

  - id: authz-guard-or-middleware
    detect:
      path: ["**/guards/**", "**/middleware*/**", "**/proxy.ts", "**/policies/**",
             "**/permissions/**", "**/*.guard.*", "**/auth/**"]
      content: ['@UseGuards\(', 'canActivate', 'authorize\(', 'hasPermission', 'requireRole',
                'allowedRoles', 'isAdmin', 'checkAccess']
    lenses: [L1, L7, L12, L18, L19]
    note: "L7 sits here because the single most-repeated authz shape in the corpus is an
           early bail placed ABOVE the privileged short-circuit it was meant to follow."

  - id: background-job-or-scheduler
    detect:
      path: ["**/jobs/**", "**/workers/**", "**/queue*/**", "**/cron/**", "**/tasks/**",
             "**/*.processor.*", "**/*.job.*"]
      content: ['@Cron\(', '@Process\(', 'queue\.add\(', 'scheduler\.', 'setInterval\(']
    lenses: [L1, L3, L4, L10, L12, L13]
    note: "L4 because a paging loop that writes the table it pages skips rows permanently and
           no counter notices — the defining background-job shape."

  - id: client-data-layer
    detect:
      path: ["**/hooks/**", "**/queries/**", "**/store*/**", "**/*.hook.*", "**/use*.ts", "**/use*.tsx"]
      content: ['useQuery\(', 'useMutation\(', 'queryKey', 'invalidateQueries\(',
                'useSWR\(', 'createSlice\(', 'atom\(']
    lenses: [L1, L6, L9, L10, L12]
    note: "L10 is the whole point of this row: a cache key invalidated but never registered
           resolves successfully against zero queries and cannot report a miss."

  - id: ui-component
    detect:
      path: ["**/components/**", "**/*.tsx", "**/*.jsx", "**/*.vue", "**/*.svelte"]
    lenses: [L1, L6, L7, L12, L19]

  - id: shared-package-export
    detect:
      path: ["packages/*/src/**", "libs/*/src/**", "**/shared/**", "**/common/**",
             "**/utils/**", "**/lib/**", "**/helpers/**"]
    lenses: [L8, L9, L11, L12]
    note: "The blast-radius row. Any modification here needs the importer enumeration in
           L11's hop before the change is judged at all."

  - id: test
    detect:
      path: ["**/*.test.*", "**/*.spec.*", "**/__tests__/**", "**/e2e/**", "**/fixtures/**",
             "**/factories/**", "**/*.fixture.*"]
    lenses: [L15]
    note: "L15 only. A test file is judged on whether its checks can fail, not on its own
           style. Reviewing test code with the production lens set is how budget is wasted."

  - id: ci-pipeline
    detect:
      path: [".github/workflows/**", "**/*.gitlab-ci.yml", "**/Jenkinsfile", "**/azure-pipelines*",
             "**/.circleci/**", "**/turbo.json", "**/nx.json", "**/Makefile"]
    lenses: [L15, L16, L17]

  - id: dependency-manifest
    detect:
      path: ["**/package.json", "**/Cargo.toml", "**/go.mod", "**/pyproject.toml",
             "**/requirements*.txt", "**/Gemfile", "**/Dockerfile*", "**/*.nix"]
    lenses: [L16, L17]

  - id: app-config-and-env
    detect:
      path: ["**/config/**", "**/*.config.*", "**/.env*", "**/*.toml", "**/*.ini"]
      content: ['process\.env\.', 'ConfigService', 'getEnv\(', 'dotenv']
    lenses: [L2, L11, L16, L17]

  - id: i18n-locale
    detect:
      path: ["**/locales/**", "**/i18n/**", "**/messages/**", "**/translations/**", "**/*.po"]
    lenses: [L17]

  - id: ops-script
    detect:
      path: ["**/scripts/**", "**/bin/**", "**/*.sh", "**/*.bash", "**/tools/**"]
    lenses: [L1, L4, L12, L13, L15, L17]
    note: "L1 dominates here: a script whose defining DELETE never checks its row count, and
           whose exit code is never set on the failure branch, reports SUCCESS for a no-op."

# ---------------------------------------------------------------------------
# signals — precise, content-based. Evaluated against CHANGED LINES ONLY
# (post-image), except where `side: both`, which is evaluated against removed
# lines as well. `both` is the only permitted value: a defect that shows up on
# the - side shows up on the + side too once someone re-adds the line wrong, so
# a deleted-only mode has never had a row and would only create a second way to
# miss the addition. Patterns are ECMAScript-flavoured regex, case-sensitive
# unless the pattern says otherwise. A signal fires a lens on any file type.
# ---------------------------------------------------------------------------
signals:

  - id: swallowed-failure
    pattern: 'catch\s*(\([^)]*\))?\s*\{\s*\}|catch\s*\([^)]*\)\s*\{[^}]*(console|logger)\.(warn|log|debug)|default:\s*(return|break)|onConflictDoNothing\(|ON CONFLICT DO NOTHING|continue-on-error|\|\|\s*true\b|set \+e'
    lenses: [L1]

  - id: neutral-fallback-on-lookup
    pattern: '(\|\||\?\?)\s*(0|1|""|''''|\[\]|\{\}|false|null)'
    lenses: [L1, L5]
    note: "High-volume, deliberately. The lens filters: it only counts when the left operand
           came from a lookup, a parse, or a fetch. Cheap to evaluate, cheap to dismiss."

  - id: validation-construct
    pattern: '\.partial\(|\.omit\(|\.pick\(|\.deepPartial\(|\.refine\(|\.superRefine\(|\.strict\(|\.default\(|z\.(string|number|boolean|enum|object)\(|safeParse\(|new RegExp\(|/\^|\$/'
    lenses: [L2]

  - id: transaction-boundary
    pattern: '\.transaction\(|BEGIN;|COMMIT;|ROLLBACK|FOR UPDATE|\btx\b|\btrx\b|SELECT .* FOR |advisory_?lock'
    lenses: [L3]

  - id: bounded-read
    pattern: '\.limit\(|\bLIMIT\b|\bOFFSET\b|\.offset\(|\.skip\(|\.take\(|pageSize|perPage|\.slice\(0|\.findFirst|\bTOP \d'
    lenses: [L4]

  - id: ordering
    pattern: '\.orderBy\(|\bORDER BY\b|\basc\(|\bdesc\(|\.sort\('
    lenses: [L4, L11]
    note: "L11 too: `[...x.sort(fn)]` spreads AFTER sorting, mutating the source in place, and
           passes every visual copy-before-sort check."

  - id: first-pick-or-key-collapse
    pattern: '\[0\]|const \[\w+\] =|new Map\(\s*\w+\.map\(|\.find\(|`\$\{[^}]+\}-\$\{'
    lenses: [L4, L14]

  - id: numeric-write
    pattern: '(?i)Number\(|parseInt\(|parseFloat\(|\.toFixed\(|Math\.round\(|numeric\(|decimal\(|smallint|integer\(|\bbigint\b|_mg|Kg\b|grams|per100|perUnit|perItem|ttl|timeoutMs'
    lenses: [L5]

  - id: temporal
    pattern: 'toISOString|getUTC(Date|Month|FullYear|Hours)|new Date\(|Date\.parse|setHours\(|startOfDay|endOfDay|timeZone|timestamptz|YYYY-MM-DD|\.slice\(0,\s*10\)|split\("T"\)'
    lenses: [L6]

  - id: guard-inserted-or-removed
    side: both
    pattern: '^\s*(if\s*\(.*\)\s*)?(return|throw)\b|@UseGuards\(|invariant\(|assert\w*\(|\bcontinue;|\bbreak;'
    lenses: [L7, L12]
    note: "Fires on deletions too. A guard whose scope moved shows up as a removal at the old
           site, and the branch that lost coverage appears nowhere on the + side."

  - id: predicate-fragment-changed
    side: both
    pattern: '(?i)isNull\(|IS NULL|deletedAt|archivedAt|tenantId|accountId|ownerId|\.filter\(|\bWHERE\b|\band\(|\bor\(|\beq\('
    lenses: [L8, L12, L14, L18]
    note: "The single highest-yield signal in the set. A changed predicate is the trigger for
           the largest lens (L8) and, when a component of it is removed, for the two
           most destructive ones (L14, L18)."

  - id: contract-surface-changed
    side: both
    pattern: '\bthrow new |\breject\(|\?:\s|\| null|\| undefined|\.optional\(|\.nullable\(|export (async )?function|export const \w+ = (async )?\(|interface |^type '
    lenses: [L9, L11, L12]

  - id: produce-consume-pair
    pattern: 'queryKey|invalidateQueries\(|\.set\(\s*\w+\s*\)|\.values\(\s*\w+\s*\)|select\(\{|providers:\s*\[|registerAsync|\.use\('
    lenses: [L10, L17]

  - id: shared-mutable-state
    pattern: '^export const \w+ = new (Map|Set|WeakMap)\(|^export const \w+: \w+\[\] = \[\]|^let \w+ =|globalThis\.|global\.\w+ =|defaultProps|defaultOptions'
    lenses: [L11]

  - id: optional-param-added
    pattern: '\w+\?:\s|=\s*\{\}\s*\)|=\s*(false|true|\[\]|""|null)\s*[,)]|options\?:'
    lenses: [L12]

  - id: distribution-claim
    pattern: '(?i)\bEXISTS\s*\(|NOT EXISTS|COUNT\(DISTINCT|GROUP BY|\bDISTINCT\b|/\s*\w+(Count|Total|Length)|\bnever happens\b|\balways (set|populated|present)\b'
    lenses: [L13]
    note: "Also fires on prose in the PR body and in comments — an unquantified 'this never
           happens' is exactly the claim the lens exists to make someone check."

  - id: destructive-write
    side: both
    pattern: '\.delete\(|\bDELETE FROM\b|\.update\(|\bUPDATE .* SET\b|truncate|hardDelete|\.destroy\('
    lenses: [L14, L18]
    note: "Escalate. A DELETE scoped by one column of a two-column key loses rows silently and
           unrecoverably; the adjacent statement in the same block often DOES carry the
           full predicate, which is what makes the file read as if scoping were handled."

  - id: assertion-or-check
    pattern: 'expect\(|assert\w*\(|\.toBe|\.toEqual|\.toBeUndefined\(|\.skip\b|skipIf\(|\.todo\b|\|\s*grep\b|test\.each'
    lenses: [L15]

  - id: version-or-toolchain
    side: both
    pattern: '"\w[\w@/-]*":\s*"[\^~]?\d|npm i(nstall)? -g|packageManager|engines|FROM \w+:|\.nvmrc|--frozen-lockfile|overrides|resolutions'
    lenses: [L16]

  - id: companion-obligation
    pattern: 'pgTable\(|CREATE TABLE|uniqueIndex\(|references\(|\bt\("|\bi18n\.|getMessage\(|@(Get|Post|Put|Patch|Delete)\(|"scripts":'
    lenses: [L17]

  - id: principal-set-changed
    side: both
    pattern: '(?i)allowedRoles|allowed\w*\s*=\s*\[|ROLES\s*=|\.includes\(|>=\s*[A-Z_]{3,}|role|isAdmin|scope|@Public\(|createSchema\.partial\('
    lenses: [L18]

  - id: ui-hidden-not-removed
    side: both
    pattern: '(?i)\{\s*\w+\s*&&\s*<|hidden|display:\s*none|visibility:|\.filter\(.*\)\s*\.map\(|redirect\('
    lenses: [L19]
    note: "Strongest when the diff DELETES markup and changes no response type, serializer, or
           projection — that combination is the archetype, and it is checkable mechanically."
```

---

## Ledger contract

One cell per `(changed file × applicable lens)` — applicable meaning assigned by the formula above. A lens this map did not assign has **no cell**: it is absent from the ledger, costs nothing, and is the budget this file buys. The five permitted values are what an *assigned* lens can resolve to, and nothing else:

| Verdict | Means |
|---|---|
| `clean` | The lens was applied and found nothing. A positive claim — it is falsifiable, and a later round may prove it wrong. |
| `finding` | Emitted in `finding-output-format.md` shape. That shape carries the lens ids on its own `Lens:` field, which is what links the finding back to this cell. **Not in `Rule-class`** — that field is a hash component of the finding's cross-round identity, so a lens id in it renames every finding and breaks the regression sweep's matching. |
| `not-applicable` | The lens was assigned, the reviewer looked, and the lens's trigger is not present in the file. **Must say why in one line.** This is a reviewer's verdict, not the map's: detection globs and signal regexes over-fire on purpose, so an assigned lens landing on a file it has nothing to ask about is expected and cheap to dismiss. |
| `cannot-assess` | The lens applies and answering needs an artifact not available (a Tier 3 execution, a cross-repo file). **Must name the artifact.** `SKILL.md` already permits this as a complete answer. |
| `not-examined` | Budget ran out. **Honest and permitted; silence dressed as `clean` is not.** |

`not-examined` on a Tier 2 lens is the costliest cell in the ledger — Tier 2 is where ~30% of escaped defects live, and it is the tier whose answer requires a hop the reviewer can still make. Name the tier in such a cell's `note` (`Tier 2 — the caller list was never opened`). The counters are tier-blind by design, so the tier only reaches a reader through that line.

The counter partition, its arithmetic, and which verdicts block an approval are fixed in `finding-state-schema.md` under "Coverage ledger". This file decides which cells exist; that one decides what they add up to.

---

## Extending the map

Adding a lens or a file type is a one-row edit. The bar for each:

- **A new `file_types` row** needs a path glob or content signature that an agent can evaluate without judgment, plus the lens list. If you cannot write the detection rule, the row is not ready.
- **A new `signals` row** needs a regex over changed lines, and a `side:` when the defect is a removal. Prefer a slightly over-firing pattern with a tight lens over a precise pattern that misses — the lens's "not a finding" section is the filter, and dismissing a signal is cheap while missing one is not.
- **A new lens** needs a `lens_index` entry with its tier and its `q_map`, and it must clear `lenses.md`'s evidence bar: **three independently-observed instances.** Record the count in `lenses.md`; a lens with no count is taste, and the catalogue is explicitly not that.
- **`q_map: new-ground` is load-bearing and is read.** It marks a lens with no Q-number, and V3's lens axis is built from exactly this set. Filing a lens under a Q it does not belong to removes it from the gap check — reinstating the silent-coverage failure this map exists to prevent, with no other symptom. Fill it correctly on every new lens.
