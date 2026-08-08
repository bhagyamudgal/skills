# Replay benchmark harness for `/review-pr`

Measures three things about a `/review-pr` run against a frozen, adjudicated benchmark:

- **Precision** — Critical+Serious false-positive rate. Target: **≤ 5%**.
- **Recall** — escaped defects a diff would have shown, and how many the run names.
- **Severity drift** — where the run put a finding relative to where the benchmark put
  it. Reported, never gated.

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

# State which skill the run is meant to measure. Verified against the one the CLI will
# actually load, and the run refuses to start if they differ.
python3 tools/replay/run.py --pr <url> --skill-dir skills/review-pr --out run.json

# Narrow the frozen set.
python3 tools/replay/score.py --findings run.json --source review-pr-skill
python3 tools/replay/score.py --findings run.json --corpus verdicts_skill

# Score against the blind third review instead of the adjudicated verdicts.
python3 tools/replay/score.py --findings run.json --gold

# Audit the held-out split without scoring anything.
python3 tools/replay/score.py --show-holdout

# Reproduce the perturbation table and the matcher-bias figure under "Measured behaviour".
python3 tools/replay/perturb.py

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
benchmark, not something this repo can regress or fix. It is filled by findings whose
own `source` says `coderabbit`, not by skill findings that happen to match a CodeRabbit
record — see "Attribution".

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

Identity is the weakest test there is — every signal agrees to the byte. What the accept
threshold is worth under the drift a replay actually produces comes from
`python3 tools/replay/perturb.py`, which perturbs the same 241 records by known amounts
and re-matches them against the originals. The rows below are that command's table (5
seeds a row): match rate, and the mean number of pairs assigned to the *wrong* record.

| perturbation | match | mis-assigned |
| --- | --- | --- |
| ±5 lines, 20% of claim words dropped and shuffled | 99.4% | 0.4 (0.2% of accepted) |
| ±15 lines, 40% dropped | 91.1% | 0.4 (0.2% of accepted) |
| ±30 lines (past the window), 40% dropped | 78.2% | 0.4 (0.2% of accepted) |
| ±15 lines, 60% dropped | 68.6% | 0.4 (0.2% of accepted) |
| no line numbers at all, 40% dropped | 89.8% | 0.2 (0.1% of accepted) |
| no path at all, 40% dropped | 62.8% | 0.2 (0.1% of accepted) |
| ±15 lines, 80% dropped | 30.2% | 1.0 (1.4% of accepted) |

Mis-assignment is reported next to match rate because it is the worse failure: a pair on
the wrong record grades a replay finding against somebody else's verdict, and nothing
downstream can see that it did. It is given as a share as well as a count because heavy
drift shrinks the denominator — 1.0 wrong pair out of the 73 that survive at 80% is a
different statement from 0.4 out of 220. At zero perturbation it is 0.0, so what the
column measures is drift and not a pair of near-duplicate records in the corpus.

The perturbation is a **model of drift, not a measurement of it**. It says how the matcher
degrades as line and claim agreement are withdrawn; it does not say how much of either a
live replay withdraws, which only a live replay can establish.

**Known bias, weakly**: at ±15/40% over 100 draws, FP records match at **88.3%** (n=18)
against **90.9%** for true ones (n=223) — unplaced records lean slightly toward false
positives. Two separate limits sit on that number. The 100 draws (against the table's 5)
remove sampling noise in the perturbation itself: at 5 seeds the same figure lands
anywhere from 88% to 93%, far enough to flip the sign. What they cannot remove is the
corpus: 18 FP records means one record is 5.6 points, so a 2.6-point gap is well inside
one record's worth of resolution. Treat the direction as suggestive and the magnitude as
unestablished; a firm coefficient needs more adjudicated false positives, not more draws.

Taken as a direction, it means the measured FP rate is optimistic whenever match rate is
below 100%, so read the FP rate next to the match rate, never alone — which the exit code
enforces rather than merely advises: below `--min-match-rate` the run exits 2 instead of
reporting a rate it cannot stand behind.

## Attribution, and severity drift

A matched pair has two sides, and the two are not interchangeable. **Source and tier come
from the replay** — they describe what this run emitted. **The verdict comes from the
frozen record** — it is ground truth about whether the *claim* is true, which no replay
can restate. Corpus is the benchmark file's own label. A record with no replay side at
all — an unmatched frozen record, or the `FROZEN BASELINE` block — keeps frozen
attribution, because that is the only attribution it has.

Keying the tier off the frozen record made the harness blind to the one axis a severity
change moves: a run re-emitting identical claims a tier lower produced byte-identical
headline numbers. It also filed every skill finding that happened to match a CodeRabbit
record under CodeRabbit's rate — which never gates — so a run reasserting someone else's
false positives exited 0.

`SEVERITY DRIFT` counts matched pairs whose replay tier differs from the frozen tier:
escalated, de-escalated, unchanged, broken down by the verdict that moved, plus the count
of **cross-source pairs**, where the two tiers were set under two different crosswalks and
are not a like-for-like comparison. On `--self-check` every pair is unchanged by
construction, which is why self-check cannot exercise any of this on its own.

Drift never affects the exit code. The frozen tiers were adjudicated under the severity
semantics a change under test is entitled to move, so drift is what an intended change
looks like rather than a failure; the verdicts grade the truth of a claim and never the
appropriateness of its severity, so nothing here can say which direction was right. The
half of drift that does carry a consequence reaches the exit code through the headline
anyway, since a finding is now counted at the tier the run emitted it at — an escalated
false positive enters the gated denominator, a de-escalated one leaves it.

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

**It must be allowed to read one.** Phase 1's first two actions are `gh pr view` and
`gh pr diff`. Under `-p` there is no one to approve them, so without a grant they come
back `This command requires approval`, the review ends before it starts, and the run
reports zero findings — the exact silent failure this benchmark exists to catch. The run
therefore passes `--permission-mode dontAsk` with an explicit read-only `--allowedTools`
list: the two `gh pr` reads, the other `gh`/`git` read subcommands and the shell read
utilities (`jq`, `grep`, `find`, `head`, …) the skill reaches for, the file tools, and the
subagent dispatch tool under **both** names the CLI has given it — `Task` in older builds,
`Agent` in the installed one. Granting one name only would deny every subagent the skill
runs on, which is most of the review.

**No shell control flow is granted** — not `bash -c`, which the skill wraps its
reusability-search globs in, and not `for` / `while` / `if` either. Granting any of them
grants arbitrary shell, which is exactly the write access the rest of the list withholds.
Those reads degrade, loudly, and the run says so; the segment-splitting that makes a
read-only loop refusable is described under "A refusal is not an empty review" below.

`dontAsk` states the headless contract outright — never prompt, refuse whatever the
allowlist does not cover. `bypassPermissions` would also make the run work, and is the
wrong tool: it would hand the run write access to the checkout and to every `gh`
subcommand the deny list does not happen to name. Enumerating what a review may **read**
is bounded; enumerating everything it must not **write** is not.

**It must never write to a real PR.** Three guards, and deny outranks allow in all of
them: `--disallowed-tools` denies `gh pr review`, `gh pr comment`, `gh pr edit`, `gh api`,
`gh issue create/comment`, `git push` and the `Write`/`Edit`/`NotebookEdit` tools; the
allowlist grants no write path to begin with; and an appended system prompt forbids
posting. Denying `gh api` wholesale costs the skill a few GraphQL reads — the correct
trade for a harness pointed at real PRs. The edit tools are denied rather than merely
left out because an operator's own settings can widen an allowlist but cannot override a
deny.

`AskUserQuestion` is denied too, for a different reason: the skill offers checkpoints and
there is nobody to answer them. Denying it states that where the appended prompt only
asks, and keeps an unanswerable checkpoint out of the bucket that means "this harness is
misconfigured".

**A refusal is not an empty review.** The CLI reports refused tool calls in `result`
events — a subagent's in its own, which is why every result event is read and not just
the last — and the run splits them in two. A denial the deny list explains is the guard
working — the skill reached for its posting path and was stopped — and is recorded under
`permissions.blocked_by_policy` without failing the run. Any other denial means the run
was refused something it was meant to have, and lands in `permissions.refused`: printed as
a `PERMISSION REFUSED` line naming the first, and, **when the run also produced no
findings**, exit **3**. Without that split, a machine that grants nothing and a PR with
nothing wrong both print `findings=0` and exit 1. A refused run that still produced
findings is worth scoring with the warning attached, so it is not thrown away over one
denied command.

Rules are matched per shell segment, so `cd repo && gh pr comment …` is still recognised
as the posting path rather than reported as a refusal nobody asked for. The same splitting
is why **shell control flow stays refused**: a read-only batch such as
`for n in 12 40; do sed -n "${n}p" f; done` splits into segments whose first word is
`for`, which matches no prefix rule. Batching line reads is a natural thing for a reviewer
to reach for, so this will recur — and it stays refused, because a rule that admits a
read-only loop (`Bash(for:*)`) admits arbitrary shell, which is the write access the whole
allowlist exists to withhold. The cost is one command per read and a line in
`permissions.refused`.

`run.py`'s own exit codes — `score.py`'s three are listed further up:

| code | meaning |
| --- | --- |
| 0 | findings parsed |
| 1 | none parsed, and nothing suggests a review was lost — a clean PR or a budget cut-off |
| 2 | the CLI failed, timed out, or is misconfigured (`error` carries its stderr tail) |
| 3 | nothing parsed **and** a tool call the harness meant to allow was refused |
| 4 | **a review arrived and no part of it parsed** — see "A format failure is not a clean PR" |

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

### A format failure is not a clean PR

Both `unparsed` counters only catch output that **almost** parsed. A reviewer that emits
its findings in a wholly different shape — headings instead of `Severity:` lines, field
labels in bold so the `^\s*field\s*:` anchor misses them — trips neither. The run then
reports `findings=0 unparsed_blocks=0 orphan_fields=0`: every counter built to make silent
loss loud agreeing that nothing was lost.

`format.failure` separates that from a clean PR on two gates, **both** of which must trip:

- **Nothing parsed at all.** One recognised field line anywhere — even an orphan — means
  the grammar was understood, and this is an ordinary parse with drops.
- **A substantial output using the format's own vocabulary.** At least
  `MIN_REVIEW_CHARS` (2000) of text, and at least `MIN_FORMAT_MARKERS` (2) occurrences of
  words the finding format owns and clean prose does not: *suggested fix*, *inverse risk*,
  *rule-class*, *class-sites*, *why it matters*. `Severity`, `File` and `Issue` are
  deliberately **not** markers — they are ordinary English and would fire on a clean review
  that merely discusses severity.

**The gates under-report on purpose.** A reviewer that abandons the grammar *and* its
vocabulary — plain JSON, or `Fix:` for `Suggested fix:` — passes undetected and lands on
exit 1, where the operator reads a `raw_review` that is plainly a review. That is the
cheaper error. Calling a genuinely clean run a format failure teaches the operator to
disbelieve the signal, which is how the next real one gets waved through.

Exit 4 says outright not to score the run: an empty findings list there means the harness
failed, not that the PR was clean. `score.py` does not read `format.failure` — it would
report the same "the run produced no findings at all" it reports for a clean PR, so the
run's own exit code is the gate.

### The review survives the parser

`raw_review` holds the assistant text verbatim — `{chars, truncated, text}`, clipped at
`RAW_REVIEW_LIMIT` (400 000 characters, head kept: a review leads with its findings and
trails into process notes). `chars` is the length **before** truncation, so a clipped
review says so rather than looking short.

It is a sibling of `findings`, never merged into it. `score.py`'s `load_findings` reads
`findings` and nothing else, so prose cannot reach the matcher and be graded against
adjudicated verdicts — a measurement invented out of text nobody structured. Without this
key a run that hits a format bug leaves its review in a streamed transcript nobody
specified a shape for, where independent readings of the same text disagree on how many
findings it contained and neither is checkable.

### Dispatches are counted, not assumed

`subagent_dispatches` counts `Agent`/`Task` `tool_use` events across the stream. The skill
runs its reviewer phases inside subagents; a run that dispatched none did the whole review
single-pass in main, which is a **different experiment** — the output only a subagent
writes was never written, and the questions those phases exist to ask were never asked.
The count sits next to `findings` in the status line and a zero prints a `SINGLE-PASS`
warning, because the two runs are otherwise indistinguishable in the JSON. Granting the
tool under both names does not guarantee a build exposes it; this is the instrument that
says whether it did.

The final `result` event restates the last assistant message verbatim, so it is appended
only when the text is not already present. Appended blind it doubled the review — and with
it every finding parsed out of it, which the matcher can only report as unmatched
duplicates, dragging the measured match rate down and reading as a worse reviewer.

### Which skill produced the review

`--model` pins the model. The skill is the artifact actually under measurement and the CLI
gives no way to pin it: there is no skill-directory flag, and `--plugin-dir` takes plugins,
not skills. **So the run does not control which skill version runs.** It resolves and
records one instead, under `skill`:

```json
"skill": {"name": "review-pr", "requested": null,
          "resolved": "/…/.claude/skills/review-pr",
          "fingerprint": "ab12cd34ef56", "pinned": false}
```

Resolution mirrors the CLI's own order — project `.claude/skills/<name>` before user
`~/.claude/skills/<name>` — and the fingerprint is a sha256 over the tree's sorted paths
**and** bytes, so a renamed reference file moves it as surely as an edited one.

`--skill-dir` is a claim to verify, not an install. When it names a directory the CLI will
not load, the run prints `SKILL MISMATCH` and exits 2 **before launching the CLI**: the run
as configured would measure a different artifact than the one named, and finding that out
after the fact costs a full review's budget. To actually pin it, link the directory into
`<repo>/.claude/skills/<name>` yourself — the harness will not write to the checkout it is
measuring.

**Verification status**: `run.py`'s parsing, permission policy, denial classification,
exit codes and output shape are unit tested, and the output is confirmed to load cleanly
into `score.py`. The permission flags were additionally exercised against the installed
CLI on a throwaway fixture with a stub `gh` on `PATH` and settings pinned to a directory
holding none. Confirmed there: `gh pr view` and `gh pr diff` are refused without the
allowlist and run with it; a piped `gh pr view … | jq …` runs with both segments granted;
`gh pr comment` is refused either way and lands in `permission_denials`; a deny rule beats
an allow rule for the same command; `Write` is reported disabled "in subagents as well as
here"; the dispatch tool is `Agent` in this build; and a subagent's refusal surfaces in
its own `result` event rather than the parent's.

It has now been executed **once** end-to-end against a live PR. What that run settled:

- The read allowlist covers the review. One refusal in the whole run, and it was shell
  control flow (see above) — a batch of line reads the reviewer re-issued one at a time.
- The cost and timeout defaults are the right order of magnitude: roughly $5 and eleven
  minutes for one large PR, inside the $8 budget and well inside the hour.
- The three blind spots the run exposed are the four sections above. The review parsed to
  **zero** findings while all three "nothing was lost" counters read zero, the text existed
  only in a `--transcript` file with no specified shape, no subagent was dispatched at all,
  and the skill under measurement was whatever was last installed rather than the branch
  being tested. Every one of those is now instrumented; none was visible in the output JSON
  before.

Still untested end-to-end: everything downstream of a run that parses. A live run has not
yet produced a findings file that reached `score.py`, so the match rate, precision and
recall numbers a real replay would report remain unmeasured — the frozen self-check is the
only evidence those paths work.
