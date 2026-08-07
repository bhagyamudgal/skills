# Replay benchmark harness for `/review-pr`

Measures two things about a `/review-pr` run against a frozen, adjudicated benchmark:

- **Precision** — Critical+Serious false-positive rate. Target: **≤ 5%**.
- **Recall** — escaped defects a diff would have shown, and how many the run names.

and one thing about itself:

- **Match rate** — how many replayed findings could be tied to a frozen verdict at all.

Match rate is printed first because it bounds the other two. Precision over the findings
a matcher happened to place, with the rest discarded, measures the matcher.

## The benchmark data is private and is never committed

The harness has **no default data path**. Pass `--benchmark <dir>` or set
`REVIEW_PR_BENCHMARK`. `tools/replay/data/` and `tools/replay/results/` are gitignored.
No fixture, repo name, file path, or finding text from the benchmark appears in this
directory — `test_replay.py` is built entirely from invented data.

The benchmark directory must contain:

```
verdicts/*.json                 adjudicated findings — any number of files, any schema
sessions/sessions_*.json        escaped defects, carrying would_a_diff_show_it
sessions/*goldstandard*.json    blind third-review findings (recall ground truth)
NORMALIZATION.md                the grading definitions this harness is bound by
```

`NORMALIZATION.md` lives in the **benchmark directory**, not in this repo — it describes
how the private corpora were graded, so it ships with the data. Code comments here that
cite it by section (`benchmark.py` on severity, `score.py` on the per-batch aggregates)
are pointing at that file, not at a missing file in this tree.

Nothing dispatches on a filename. Each file under `verdicts/` is sniffed for its shape
and read through one field-aliasing normaliser, so a new corpus with a new schema loads
without a code change. The corpus label in the report is the file's own stem. See
"Schema divergence" for what the normaliser has to reconcile.

## Commands

```bash
export REVIEW_PR_BENCHMARK=~/path/to/benchmark

# Sanity check: score the frozen verdicts as their own input.
# Must report ~100% match and reproduce the published FP rates. If it does not,
# the matcher is broken and nothing else it prints means anything.
python3 tools/replay/score.py --self-check

# Score a real run.
python3 tools/replay/run.py --pr https://github.com/o/r/pull/123 --out run.json
python3 tools/replay/score.py --findings run.json --json results.json

# Narrow the frozen set.
python3 tools/replay/score.py --findings run.json --source review-pr-skill
python3 tools/replay/score.py --findings run.json --corpus verdicts_skill

# Score against the blind third review instead of the adjudicated verdicts.
python3 tools/replay/score.py --findings run.json --gold

# Audit the held-out split without scoring anything.
python3 tools/replay/score.py --show-holdout

python3 tools/replay/test_replay.py
```

### Exit codes

One bit cannot carry three outcomes, so there are three codes:

| code | meaning |
| --- | --- |
| 0 | the skill's high-tier FP rate is within 5%, measured on evidence worth trusting |
| 1 | **regression** — the skill's high-tier FP rate exceeds 5% |
| 2 | **cannot certify** — the run does not support a precision claim either way |

CodeRabbit's rate never affects the exit code; it is a comparison point in this
benchmark, not something this repo can regress or fix.

Exit 2 fires when the match rate is below `--min-match-rate` (default 60%), when the run
produced no findings, when no high-tier skill finding was graded, or in `--gold` mode,
where the findings carry no verdicts at all. That last group used to exit 0 — reporting
green because nothing had been measured. The reasons are printed under `VERDICT` and
repeated in the `exit` block of `--json`.

The `--json` artifact is written *before* the report is printed, so a formatting failure
cannot also destroy the machine-readable output CI reads.

## Matcher

Exact `(file, line)` equality does not work: line numbers drift between the commit a
verdict was adjudicated against and the commit a replay reads, the skill rewords its own
claims run to run, and a finding can legitimately anchor a hunk off the construct it
describes. Three signals, weighted, renormalised over whichever are available:

| signal | weight | notes |
| --- | --- | --- |
| path | 0.30 | exact 1.0, same basename + parent 0.85, basename only 0.70, different basename **rejects outright**; scaled by 0.80 for a multi-site anchor and 0.60 for a glob |
| line | 0.20 | linear decay over a 25-line window (roughly one screen) |
| claim | 0.50 | 0.45 × word Jaccard + 0.55 × identifier Jaccard — `resolveTenantScope` matches through a full rewrite where prose does not |

Hard gates: different PR rejects, different basename rejects. Missing signals are
renormalised away rather than scored as disagreement — absent evidence is not contrary
evidence — **except the claim**, which keeps its weight in the denominator whether or not
it is comparable. It is the only signal carrying what a finding actually *says*, so
renormalising it away lets a row with no claim text at all ride path and line to a
perfect 1.0, win the greedy assignment, and push the genuine reworded finding into
`unmatched_replay`. A claimless row now tops out at 0.50 and lands in `ambiguous`.

`anchor_quality` is read at match time, so the loader's promise that a multi-site or
glob anchor is *weaker evidence* is enforced rather than merely recorded. The weaker of
the two anchors governs. **Known gap**: a multi-site anchor is still resolved to its
first path only, so a finding that correctly matches the anchor's *second* path is still
rejected as a different file.

Three outcomes, all reported: **matched** (≥ 0.60), **ambiguous** (≥ 0.42, excluded from
precision — might be the same finding, not confidently enough to grade a verdict on),
**unmatched**. Assignment is greedy one-to-one, so a run emitting five rewordings of one
finding cannot have all five absorbed by one CORRECT verdict.

### Measured behaviour

Identity (`--self-check`, 241 records): **100% match, 0 ambiguous, 0 unmatched**, and all
four published baseline FP rates and Wilson intervals reproduce exactly. Headline
high-tier FP rates on that run: skill **3.31%** (5/151, PASS), CodeRabbit **16.18%**
(11/68). Recall names **41 of 283** eligible defects (14.5%) against a null of 17.5 over
200 permutations — **lift ×2.35, p = 0.005**, with the null dead for 32 of the 283.

Under synthetic perturbation of the same 241 records (5 seeds each), match rate and the
number of pairs assigned to the *wrong* record:

| perturbation | match | mis-assigned |
| --- | --- | --- |
| ±5 lines, 20% of claim words dropped and shuffled | 99.6% | 0.0 |
| ±15 lines, 40% dropped | 91.5% | 0.0 |
| ±30 lines (past the window), 40% dropped | 81.0% | 0.2 |
| ±15 lines, 60% dropped | 72.1% | 0.8 |
| no line numbers at all, 40% dropped | 91.0% | 0.6 |
| no path at all, 40% dropped | 63.4% | 0.0 |
| ±15 lines, 80% dropped | 50.3% | 3.8 |

**Known bias**: findings the matcher fails to place are slightly enriched for false
positives — at ±15/40%, FP records match at 88.3% against 92.1% for true ones. Measured
FP rate is therefore optimistic by a few percent relative whenever match rate is below
100%. Read the FP rate next to the match rate, never alone — which the exit code now
enforces rather than merely advising: below `--min-match-rate` the run exits 2 instead of
reporting a rate it cannot stand behind.

## Recall

Eligible = escaped defects with `would_a_diff_show_it` in `yes` or `partial`, minus the
held-out split. A finding names a defect if its file basename appears in the defect's
`file_hint` and the claim text scores ≥ 0.35 by **containment** (not Jaccard: the
one-line finding is being compared to a paragraph of root-cause prose, and the union
term would swamp a correct hit).

Containment is measured **against the claim**, not against the shorter of the two sides,
and is scaled by how much vocabulary the claim staked (full weight at 5 tokens). Dividing
by the shorter side let a one-word claim score a perfect 1.000 against a long root-cause
write-up — comfortably over a threshold whose whole purpose is to sit above where generic
prose brushes real defects.

Defects whose `file_hint` names a symbol rather than a path (~13% of eligible) cannot be
file-gated and are matched on claim text alone. `ungated` counts the hits where the gate
did not actually run — which includes a finding that carries no path of its own, not just
a defect that carries no path.

**Recall deliberately does not PR-gate**, though precision hard-rejects on a PR mismatch.
An escaped defect's PR is parsed out of its `ticket` field, which mostly holds the
*issue* it was tracked under rather than the PR a reviewer would have seen: only 12 of
the 135 ticket numbers in the escaped set intersect the 50 PRs in the frozen verdicts.
Gating on it would discard most true hits. The field is loaded so the join key is
inspectable, and is not used as one.

### The permutation null, and where it is dead

Recall is printed beside a **permutation null**: the same scorer re-run with claims
shuffled onto other findings' file anchors. That number is what the file gate and generic
engineering vocabulary buy for free.

The null is only alive where the file gate actually restricts the candidate set. The hit
test takes a **max** over the candidates, and the permutation only moves claims between
findings — so when the gate excludes nobody, the same multiset of claims is maximised
over before and after and the null equals the observed statistic *by arithmetic*. Three
reachable regimes land there: a defect whose hint carries no path, findings that carry no
path (globs, unparsed anchors), and every finding sharing one basename.

The report therefore prints how many eligible defects the null **can** move. When that
count is zero it prints `NO LIFT REPORTED` instead of a lift of 1.0 dressed up as a
measurement. A `null_mean` of zero — the strongest outcome available — prints as
`lift: UNBOUNDED`, not as the `xNone` a bare `named / null_mean` produced.

A **p-value** accompanies the lift: the fraction of permutations naming at least as many
defects as the run, +1 smoothed. It cannot go below `1/(permutations+1)`, so the default
permutation count is 200 rather than the 5 that bottomed out at 0.167 and could not have
supported one. Tokenisation is memoised, so 200 draws cost about two seconds.

## Held-out split

A deterministically seeded 20% of the escaped-defect set, reserved and never scored.

- Seed: **20260806**, fraction **0.20**, printed in every report with a digest of the
  reserved ids. An empty holdout prints `EMPTY-NOTHING-RESERVED` and a warning rather
  than the sha1 of the empty string, which is a well-formed digest attesting to nothing.
- Ids are content-addressed (`sha1` of the defect's own text), so the split survives a
  re-export that reorders rows.
- Ids are sorted before shuffling, so the draw depends only on the seed and the set's
  contents.

Changing the seed re-draws the split and retires every recall number measured against the
old one. It does not produce a comparable result.

## Schema divergence between the verdict files

The verdict corpora were produced by independent adjudication runs that never agreed a
schema. What `benchmark.py` reconciles:

- **Anchors** come four ways so far: `file` + `line`; `path` + `lines`/`lines_original`; a
  free-text `file` that may hold two paths, a glob, or a brace expansion; and `path` +
  `line` with some nulls. For CodeRabbit the harness prefers `lines_original` — `lines`
  is GitHub's line at *current* head, while the comment was posted against the original.
- **Claim text** is `claim` in some corpora and `title` in others.
- **Severity** has three vocabularies: `critical|serious`, `🔴 Critical|🟠 Major|🟡 Minor|🔵 Trivial`,
  and a `sev`/`severity_raw` pair with mixed casing. Per `NORMALIZATION.md` §3 these are
  never translated into each other. Each source gets its own high-tier predicate
  (skill: Critical|Serious; CodeRabbit: Critical|Major) and the report labels the pair a
  **stated crosswalk**, not an equivalence. Headline rates are per-source for the same
  reason — one pooled number moves with the sampling mix, not with either reviewer.
- **`coderabbit-body`** findings are CodeRabbit findings posted in a review body rather
  than a thread (`NORMALIZATION.md` §4). They share its severity vocabulary and belong in
  its denominator; only the channel differs.
- **Some corpora ship both a consolidated export and the per-PR files it was built from.**
  Loading both double-counts every finding in the overlap. The loader detects this by
  content, never by filename: findings are keyed on `(pr, idx)` where the export numbered
  them and on the anchor plus a claim prefix otherwise. Row **position is not part of the
  key** — a consolidated export numbers its rows differently from its parts, and a key
  that moves with row order cannot see one file covering another. The subsumption test is
  `⊆`, not `⊂`, so two byte-identical exports do not both load by each failing to be a
  proper subset of the other.

  Whole-file subsumption cannot catch a *partial* overlap, so the loader re-checks the
  partition arithmetic against what actually loaded and emits `WARNING partition check
  failed` naming the number of duplicates. This matters because nothing downstream can
  see them: ids are built from the corpus stem, so duplicates get distinct ids, inflate
  every denominator, falsely narrow the Wilson intervals, and surface in
  `unmatched_frozen` — reported as "benchmark findings this run did not reproduce", i.e.
  a fabricated recall miss.
- `CORRECT_TRIVIAL` is true-of-the-code and is **not** a false positive.
  `FALSE_POSITIVE` + `HALLUCINATION` form the numerator; `UNVERIFIABLE` leaves the
  denominator entirely.

## `run.py`

Invokes the skill through `claude -p --output-format stream-json --verbose` and parses
findings out of the labelled block defined in
`skills/review-pr/references/finding-output-format.md`. The skill emits text, not JSON,
and that format file is the single place the shape is defined — a second JSON emitter
inside the skill would be a second shape to keep in sync.

**Replay merged or closed PRs.** An open PR's head moves, so a run scores against a
commit the frozen verdicts were never adjudicated on. `--sha` is recorded in the output
so a scored run always states what it read; it is not enforced against the live head.

**It must never write to a real PR.** Two independent guards: `--disallowed-tools` denies
`gh pr review`, `gh pr comment`, `gh pr edit`, `gh api`, `gh issue create/comment` and
`git push`; and an appended system prompt forbids posting. Denying `gh api` wholesale
costs the skill a few GraphQL reads — the correct trade for a harness pointed at real
PRs. Exit code 1 on zero findings, because a real PR yielding nothing is nearly always a
budget cut-off or a format change rather than a clean PR.

The timeout is enforced by a watchdog that kills the child at the deadline, not by a
clock check inside the read loop: `for line in proc.stdout` blocks until a line arrives,
so a child that hangs **without printing** never reaches an in-loop check and is never
timed out at all. `stderr` is captured and surfaced in `error` — when the CLI dies before
emitting a single event, stderr holds the only statement of why, and discarding it
reports an auth failure as "this PR had no findings".

`unparsed` counts two things, because both are findings the run made and the harness
lost: `blocks` (a block with no severity, or with neither a file nor an issue) and
`orphan_fields` (field lines arriving before any `Severity:` opened a block — a finding
whose severity line the transcript dropped).

**Verification status**: `run.py`'s parsing, safety flags and output shape are unit
tested and the output is confirmed to load cleanly into `score.py`. It has **not** been
executed end-to-end against a live PR — that costs a full review run against a private
repo. Treat its per-run cost, timeout and budget defaults as untested estimates.
