# Finding output format

The single shape every reviewer and verifier emits a finding in, the single line shape a
lens-assigned reviewer emits a coverage-ledger cell verdict in, and the single field list
every surface renders a review header from. Loaded by **Subagent 1** (Phase 2 reviewer),
**Subagent 2** (Phase 2 silent-failure reviewer), **Subagent 3** (Phase 2 cross-cutting
reviewer), **V1** (Phase 3 class sweep) and **V3** (Phase 3 deep gap check) — all of them
produce output that Phase 3 dedupes, sweeps and persists, and without this file each
invents a shape that dedupe and step 4.55 cannot parse.
`q6-reusability-search.md` points here too, so a Q6a finding comes out in the same shape
as every other finding.

Loaded by **main** as well, which is easy to miss because main is the consumer of everyone
else's findings — but it authors findings of its own in Phase 3. The reusability audit at
step 4.5 raises one when a reviewer's `reusability_searches:` audit is missing or shallow,
and the gap check at step 6 raises one per gap it finds. Main writes `Severity:` on those,
so a main that never opens this file tiers them without the tier table, without the
Critical/Serious reversibility test, and without the detectability modifier this file says
is applied once at emission — which then never gets applied to them at all, since step 7
ranks on the emitted value and is explicitly forbidden from re-deriving it.

Everything downstream — the terminal block, the posted review, the batch report, the
`/fix-pr-review` handoff, V1's sweep report — is a **projection** of what is defined here:
a declared subset, never a second copy. "Projections of this schema" at the foot of this
file lists them and points at each one's spec.

Emit the fields verbatim, one per line, in the order below.

## Line number convention

`File: <path:line>` must use the **post-image line number** — the line as it appears in
the new version (the `+` side of the unified diff hunk, or unchanged context on the new
side). NOT old-side. NOT the diff hunk header offset. Omit `:line` for module-scope
findings; they route to file-level review comments.

## Per-finding block

```
Severity:    Critical | Serious | Moderate | Minor
Confidence:  high | medium | low
File:        <path:line> (or <path> alone for module-scope)
Category:    Intent | Unnecessary | DRY | Performance | Security |
             Reusability | Silent-failure | Breaking-change |
             Architecture | Prior-finding-correction
Rule-class:  <2-3 word slug — e.g., silent-failure, n+1-query, error-code-wrong-branch>
Lens:        <lens ids that raised this, comma-separated — e.g. L8, L12;
             "none — <the check that raised it>" when no lens did, e.g. "none — Q3",
             "none — cross-file sweep", "none — silent-failure pass">
Enclosing-symbol: <function/class/component containing the cited line, or "<module>">
Issue:       <one sentence>
Why it matters: <one sentence>
Suggested fix:  <one sentence, actionable>
Inverse risk:   <the failure mode this fix trades INTO if implemented literally,
                 or "none — pure addition">
Class-sites:    <A>/<N> — affected sites over the total entries in the
                class_completeness audit's sites: list, below
```

## Severity — what each tier means

Pick the tier by answering one question: **if this ships unchanged, what happens, to whom,
and how would anyone find out?** Not by category — a Security label does not make a finding
Critical. Not by how large or awkward the fix is. Not by how sure you are; `Confidence`
already carries that, and the two are ranked separately downstream.

| Tier | If it ships unchanged | Recovery | Typical shape |
|---|---|---|---|
| **Critical** | Someone outside the team takes a loss that outlives the bug: rows written wrong or destroyed, one tenant's data reachable by another, money/quantity/identity persisted incorrectly, or the change's own primary path broken for every user | Deploying the fix is NOT enough — needs a backfill, a migration, a revocation or a disclosure | a scoping predicate that spans tenants; an unguarded destructive write; a value persisted in the wrong unit or type |
| **Serious** | A reachable input produces a wrong result or a dead path for a real user, and you can name that input: the route, caller or data shape that reaches it in the code as merged | Deploying the fix ends it; nothing left behind to repair | a branch a live caller reaches and nobody handles; a contract change an existing caller breaks on; a guard added to one of two write paths |
| **Moderate** | Nothing is wrong for any user today; the cost is that the NEXT change here is likely to break — a duplicate that will diverge, an invariant enforced in one of two places, a query that is fine at present volume | Nothing to repair; fix when the area is next touched | a rule duplicated rather than shared; a missing index with no volume behind it yet; validation on one write and not its sibling |
| **Minor** | Nothing changes for a user under any input, now or later, absent a further decision | Nothing to recover | naming, dead code, redundant-but-correct code, a type that loses compile-time checking without changing runtime |

Tier emoji, wherever a surface renders one: 🔴 Critical · 🟠 Serious · 🟡 Moderate · 🔵 Minor.

### The Critical/Serious boundary — reversibility

Ask: **once the fix is deployed, is anything still wrong?** If bad rows, leaked reads, sent
messages or corrupted totals survive the deploy, it is Critical; if the deploy ends the
incident, it is Serious. The mechanism's sophistication does not enter into it — a
one-character predicate that writes across tenants is Critical, and an entire mis-designed
module that only ever renders the wrong label is not.

A true observation about a convention deviation is not Critical by inheritance. Adjudication
of past runs found convention findings filed at the top tier whose real consequence was a
less specific error string, because a framework-level handler already caught the case the
finding assumed was fatal. Tier the consequence you can demonstrate, not the deviation.

### The Serious/Moderate boundary — reachability

The blocking bar sits here, so this boundary decides whether the change is held. **Name the
trigger**: the input, caller, route or data shape that reaches the bad path in the code as
merged. If you can name it, the finding is Serious. If the honest answer is "some future
caller", "if someone later passes null" or "once the table is larger", it is Moderate — and
that is not a low-confidence Serious, it is a correctly-tiered Moderate. A finding whose
`Why it matters` needs a second, hypothetical change before anyone is harmed belongs below
the bar.

### Detectability modifier — silence raises the tier

Apply this once, before writing `Severity:`. **If the wrong path executes right now, does
anything anywhere emit a signal?** A throw, a non-2xx, a log line, a failing assertion, a
visibly wrong value on screen. If nothing does — the wrong path returns a success-shaped
value — raise the tier by one. If it fails loudly on the first request, lower it by one.

This runs against the reviewer's instinct, which is why it is written down: attention drifts
to dense, clever code, and the bare `return 0` gets waved through. The escaped-defect study
behind this skill found the single commonest reason a shipped defect went unnoticed was that
there was no error signal at all — the wrong branch returned success, so no observation point
available to a reviewer or a user could distinguish it from the working one. A loud defect is
found in minutes by whoever runs it next; a silent one is found months later by a customer,
if ever. Scrutiny is owed in proportion to silence, not to complexity.

Two limits. The modifier moves the **tier only** — never relabel `Category` as
`Silent-failure` to pick up the escalation that category carries at verdict time. And it does
not reach Minor: a finding with no wrong behavior under any input has no wrong path to be
silent about.

## Required fields

`Inverse risk` and `Class-sites` are REQUIRED on every finding that proposes a code
change — one field per cascade feeder. `/fix-pr-review` seeds its own inverse-risk check
and class sweep from these two lines, so a finding printed without them costs the next
skill a full re-derivation.

`Rule-class` and `Enclosing-symbol` are required too — they let the critic compute a
stable finding ID (`sha1(file::enclosing_symbol::rule_class)`) that survives line shifts
and rewordings across review rounds. Load
`<SKILL_DIR>/references/finding-state-schema.md` for the exact ID derivation and the
`status` values a finding may carry. It specifies no normalization of the two fields before
they are hashed, so emit them already canonical: `Rule-class` lowercase and hyphen-joined,
`Enclosing-symbol` the symbol exactly as it is spelled in the source. Casing or spacing
drift between rounds produces a different hash for the same defect, which reads downstream
as a finding that was fixed and a new one that appeared.

`Lens` is required on every finding and is **not** part of the ID hash — the hash takes
`file`, `enclosing_symbol` and `rule_class`, and nothing else. It is what links a finding
to its coverage-ledger cell: `lens-map.md` defines the `finding` verdict as a cell some
finding's `Lens:` line names, and ledger assembly reads this line to set those cells and to
persist `lens_ids`. "Coverage-ledger cell verdicts" below defines the line the reviewer
emits for that same cell; the two must name each other, and this line is the authority
where they disagree. A blank line is not an answer — it is a finding the ledger silently
fails to account for, and a cell reading `finding` with nothing pointing back at it cannot
be audited.

Not every emitter works from a lens list, so the field has a second legal form. A reviewer
whose whole scope is a Q-number, a cross-file sweep, or a defect class with no lens writes
`none — <the check that raised it>` and names it. That parses to an empty `lens_ids`, names
no cell, and changes no counter — correctly, because the ledger measures lens coverage and
not the run's whole yield. What it must never be is silently blank, which is
indistinguishable from a lens finding whose emitter forgot the field.

**Never fold a lens id into `Rule-class`.** That field is the third hash component, so a
lens id inside it changes the id of every finding carrying one: the same defect reads as
brand new in the next round, the regression sweep matches nothing it swept before, and
prior-state suppression re-raises what was already closed. The two fields answer different
questions and are not interchangeable — `Rule-class` is the defect's signature, which the
class sweep greps the repo for; `Lens` is which question found it.

## `class_completeness:` audit

Required on every finding that proposes a code change. Use this EXACT field name so
Phase 3 step 4.55 can parse it:

```
class_completeness:
  - finding: <the Issue, trimmed>
    rule_class: <slug>
    signature: <the literal/pattern actually searched>
    search: <tool>("<query>", "<path>") → <N> sites
    sites:
      - <file:line or symbol>: affected | not-affected — <one clause why>
    verdict: COMPLETE (all N sites reported) | INCOMPLETE (<M> unreported sites)
```

`affected` means the site exhibits this `rule_class`; `not-affected` means the sweep
looked and it does not. `Class-sites: <A>/<N>` is the count of `affected` entries over
the total number of entries in `sites:`.

`search:`'s own `→ <N> sites` is the raw hit count and is a **different** number — a grep
returns hits the sweep then discards as irrelevant, so it is legitimately larger. Never
render `Class-sites` from it. Two surfaces dividing by two denominators report two different
blast radii for one finding, with nothing on either surface to tell the reader which is which.

Do NOT write `handled` in this audit. `handled` belongs to a different, later layer:
`class_sites[].handled` in `<SKILL_DIR>/references/finding-state-schema.md` records
whether the PR has since COVERED an affected site, and only affected sites are carried
into that list. One word per layer — conflating them makes a merely-swept finding look
fixed.

If the finding proposes no code change, write exactly:
`class_completeness: N/A (no code change proposed)`.

## Finding IDs

`C1, C2…` Critical, `S1, S2…` Serious, `M1, M2…` Moderate, `m1, m2…` Minor — assigned by
main in Phase 3 after dedupe, sequentially within each tier, Critical tier first.

Reviewers never assign them. Numbering is a property of the deduped run-level set, and no
single reviewer sees that set.

**IDs are canonical, not presentational.** Every surface that lists more than one finding
prints them, and prints the same id for the same finding within a round: the terminal
block, the posted findings table, the posted per-finding comments, the ledger's `finding`
cells and the `/fix-pr-review` handoff all name a finding the same way. A surface that
drops them leaves the reader unable to carry a finding across to the next surface — the
author reading the terminal cannot tell which entry became the `S2` thread on the PR.

They are per-round labels. `M3` in round 2 need not be `M3` in round 3; cross-round
identity is the `sha1(file::enclosing_symbol::rule_class)` hash defined in
`finding-state-schema.md`.

## Coverage-ledger cell verdicts

The second shape defined here, and by volume the larger one. **Subagent 1 and its chunk
instances** owe a verdict on each `(file, lens)` pair in the `LENS_ASSIGNMENTS` block they
were handed, and on a real PR those cells outnumber the findings by an order of magnitude —
one per lens per file per chunk reviewer. Nobody else emits them: Subagent 2 and Subagent 3
receive no assignments and V3 is forbidden the cell vocabulary outright, so a cell block
from any of them is a shape they invented. Main parses the cells into `ledger.rows[].lenses[]`
(`finding-state-schema.md`, "Coverage ledger"), so the shape has to survive being emitted
dozens of times in a row under context pressure. The per-finding block's field-per-line
verbosity is the wrong instrument at that volume; a cell is one line.

Left to prose, each reviewer phrases its verdicts differently, main reads some of them, and
every cell it cannot read is `not-examined`. That direction is safe but not free: format
drift between chunk reviewers becomes a coverage line that is permanently red for reasons
that have nothing to do with coverage, and `lens-map.md` records what a permanently red line
teaches its readers.

Emit the cells after the findings, one line each, in the order the assignments were given:

```cells
<path> | <lens id> | <verdict> | <note>
```

- `<path>` — repo-relative, byte-identical to the assignments block. A cell keyed on a
  display name or a shortened path matches no row.
- `<lens id>` — `META`, `L1`…`L19`, exactly as spelled in `lens-map.md`'s `lens_index`.
- `<verdict>` — one of `clean`, `finding`, `not-applicable`, `cannot-assess`, spelled
  exactly. These tokens are copied verbatim into the ledger's enum, so a synonym
  (`n/a`, `ok`, `pass`, `N/A`) needs a mapping table that nobody has written. `not-examined`
  is main's alone: it means "this reviewer said nothing", which no reviewer can say of
  itself.
- `<note>` — everything after the third `|`, one line, no pipes needed inside it since the
  parse takes the remainder. **Required** for `not-applicable` (why the assigned lens's
  trigger is absent here) and for `cannot-assess` (which artifact would answer it). For
  `finding`, the `Rule-class` slug of the finding raised on this cell. A `clean` line ends
  after the verdict, with no trailing pipe.

The fence's `cells` info string is an aid, not the contract: each line stands alone and is
recognised by its own shape, so one mangled line costs one cell. That is why this is a flat
list and not a per-file grouping — grouping is cheaper in tokens and orphans an entire
file's cells when its one header line garbles, which converts a formatting slip into a
whole file of `not-examined`.

`finding` carries a `Rule-class` slug rather than a finding id because reviewers never
assign ids (see "Finding IDs"), and because the authoritative link runs the other way: main
sets `finding` cells from the surviving findings' `Lens:` lines during ledger assembly, not
from this block. The slug makes the reviewer's claim checkable against its own findings — a
`finding` cell with no finding pointing back at it is a dropped `Lens:` line, and it should
read as that rather than as a cell that quietly set itself. A reviewer `finding` cell whose
finding did not survive dedupe or filtering resolves to `clean`: the lens ran and nothing
stands. It is never `not-examined` — the reviewer did the work.

These are the cells behind the ledger example in `finding-state-schema.md`, so the two can
be read against each other. One finding covering two cells writes its slug on both; main
resolves them to one `finding_id`.

```cells
src/handlers/import-pdf.ts | L1 | finding | silent-failure
src/handlers/import-pdf.ts | L8 | finding | silent-failure
src/services/upsert-bundle.helper.ts | L7 | clean
drizzle/0042_bundle_index.sql | L17 | not-applicable | index-only DDL — no table gains a column needing a companion
drizzle/0042_bundle_index.sql | L13 | cannot-assess | needs a row-count and null-share query against the target table
```

### What main does with a malformed cell

A line main cannot parse — an unknown verdict token, a missing or unrecognised lens id, a
path outside the assignments, or a `not-applicable` / `cannot-assess` carrying no note — is
treated as **absent**. The cell it was meant to fill is `not-examined`, with the reason
recorded as an unparseable verdict. This is deliberately the same outcome as silence: a
verdict main cannot read is a verdict main does not have, and the ledger has exactly one
safe direction of failure. Never repair a malformed line by inferring what the reviewer
probably meant, and never let one settle to `clean`.

A cell block whose closing fence never arrives was truncated rather than withheld. Cells
before the break stand; the rest are `not-examined` with truncation as their reason, which
is a distinct and more actionable note than "the reviewer said nothing about the pair".

A cell naming a `(file, lens)` pair the assignments do not contain is recorded, not dropped —
the map is a floor and not a ceiling — and flagged as a map row that is missing.

## Run-level header — canonical field list

One header, rendered by several surfaces. This list is the source: a surface carries a
declared subset of these fields and invents none of its own.

| Field | Filled by | Content |
|---|---|---|
| `Title` | PR metadata | the PR title |
| `Number` | PR metadata | the PR number |
| `Senior engineer approval` | reviewer | `Yes` \| `No` \| `With changes`, plus a one-sentence reason. The reason is part of the field, not an optional extra — an approval verdict with no stated reason is unreviewable. |
| `Verdict` | main, Phase 3 step 8 | `approve` \| `comment` \| `request-changes` |
| `Severity counts` | main | per-tier counts, tiers with zero findings omitted |
| `Goal` | Phase 1 intent | one sentence — what the PR set out to do |
| `Summary` | reviewer | 2-3 sentences — what the PR does, biggest concern, overall verdict |
| `Size` | PR metadata | additions/deletions across N files |
| `Reviewers` | main | which reviewers and verifiers ran, each degraded one marked with why (see `Reviewers` below) |
| `Round` | main | `CURRENT_ROUND`, plus active/resolved/dismissed counts carried across rounds |
| `Convergence` | main, Phase 3 step 7.5 | new / caused-by-earlier-fixes / regressions-reopened / carried, plus the one trend sentence. Printed, never recomputed per surface. |
| `Mode` | main | the run's non-default modes (see `Mode` below); omitted when the run is a plain in-repo full review |
| `Follow-ups` | Phase 4's "File the follow-up issue" step | the round-cap backlog's fate — the issue URL when `filed`, and otherwise the stated reason there is none (`incomplete` / `failed` / `declined`). Omitted below round 3 and whenever no finding is still active. The wording of the three non-`filed` renderings is fixed in `github-posting.md` and must not be softened: the round cap releases findings from blocking on the promise that they are tracked, so a surface that implies a backlog which does not exist re-tells exactly the lie the step exists to prevent |
| `Coverage` | the ledger Phase 3 step 6.9 assembled — **not** the state file, which Step 8c has not written when the body is composed; in batch mode, the ledger the per-PR subagent transported back | `cells_examined` / `cells_total` across `files_changed`, plus `cells_cannot_assess` and `cells_not_examined` each when non-zero. `cells_examined` covers `{clean, finding, not-applicable}`; the three counters partition `cells_total`, so a surface renders them and never derives one by subtracting the others. The five-value verdict vocabulary and the partition are fixed in `finding-state-schema.md` |

### `Reviewers` — degraded runs

This field is where a run admits it ran short-handed. It carries every Phase 2 reviewer and
every Phase 3 verifier that was dispatched, each degraded one annotated:

- `<reviewer> (unavailable)` — the subagent errored or returned empty and its share of the
  diff went unreviewed. Its cells are `not-examined` in the ledger.
- `<verifier> unavailable — verified inline` — the verifier errored and main ran its step
  itself. The check happened; only its executor changed.

The two are not interchangeable. The first is missing coverage and the ledger must agree;
the second is complete coverage under context pressure.

### `Mode` — non-default runs

One line, listing every mode that applies; omitted entirely when none does:

- `partial re-review (<N> new commits since cached run at <sha>)` — Phase 2 saw only the
  new-commits diff, so findings on untouched code come from the cache rather than this
  round's reading.
- `cross-repo (reviewed from outside the PR's repo)` — the repo map came from remote
  fetches instead of the local tree, so reusability answers rest on a thinner index.
- `intent not grounded — findings may be generic` — the intent gap was never resolved, so
  Q1 was answered against the diff alone. Batch mode raises this one by design, having no
  one to ask.

All three qualify how much of the PR this run actually read, which is why they sit in the
header next to `Coverage` rather than in a footnote. A surface may suppress an individual
value — but it must name the value and say where a reader can otherwise see the same cost.

## Reviewer emission of the header fields

A reviewer whose scope is the WHOLE PR (Subagent 1 in unchunked modes) ends its output with
the header fields a reviewer can know — the rest are main's:

```
Senior engineer approval: Yes | No | With changes
Approval reason: <one sentence>
Summary: <3 sentences — what the PR does, biggest concern, overall verdict>
Verdict: approve | comment | request-changes
```

`Approval reason` is a separate line here only because a reviewer emits fields one per line;
it is the reason half of the `Senior engineer approval` field, and rendering surfaces join
the two.

Chunk reviewers, Subagent 3 and V3 emit no header fields — their scope is partial, so main
composes the run-level verdict in Phase 3. A chunk reviewer still owes its cell block; that
is coverage over the files it held, not a claim about the run.

## Projections of this schema

Each surface below renders a declared SUBSET of the per-finding block, the header field
list, the cell-verdict line, or the `class_completeness:` audit. Each one's own spec names
what it carries and why what it drops is safe to drop there.

**A projection that restates the schema is the defect.** Two copies of one shape drift, and
the drift is invisible until a downstream parser meets the older copy. A projection cites
this file and names its subset.

| Surface | Spec | Projects |
|---|---|---|
| Terminal block | SKILL.md, Phase 4 | header + per-finding block |
| Posted review body | `github-posting.md` Step 1 | header |
| Posted per-finding comment | `github-posting.md` Step 2 | per-finding block |
| Batch consolidated report | `batch-mode.md` | header, one row per PR |
| `/fix-pr-review` handoff file | SKILL.md, Phase 4 | per-finding block |
| Follow-up issue body | SKILL.md, Phase 4 | per-finding block, minus `Lens` (the issue outlives the ledger cell it answered); `Rule-class` and `Enclosing-symbol` ride in the HTML marker that the read-back greps and a later round's lookup reads |
| V1 class-sweep report | `verification-subagents.md` | `class_completeness:` audit |
| Coverage ledger (`ledger.rows[].lenses[]`) | `finding-state-schema.md`, "Coverage ledger" | the cell-verdict line — verdict and note per cell, with `finding_id` resolved by main from the finding's `Lens:` line rather than carried on the line itself |

When a surface needs a field this file does not define, the field is added HERE first and
the surface then projects it. Adding it to the surface alone recreates the drift.
