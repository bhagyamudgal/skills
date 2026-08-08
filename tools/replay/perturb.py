#!/usr/bin/env python3
"""Measure what the matcher does once the two sides of a pair stop agreeing exactly.

`score.py --self-check` is an identity test: every signal agrees to the byte, so 100%
match proves only that a record can be recognised as itself. A real replay never gets
that — the line moved between the adjudicated commit and the replayed one, and the run
reworded its own claim. This perturbs the frozen records by known amounts and re-matches
them against the originals, which is the only way to say what the 0.60 accept threshold
buys under the drift a replay actually produces.

Two numbers, and the second is why the first is not enough on its own:

- **match rate** — how many perturbed copies were placed at all.
- **mis-assigned** — how many were placed on the WRONG record. A match rate that holds
  up while mis-assignment climbs is worse than one that falls, because a wrong pair
  grades a replay finding against somebody else's verdict and the report cannot tell.

Then the bias check: whether the copies the matcher fails to place are enriched for false
positives. If they are, every measured FP rate is optimistic whenever the match rate is
below 100% — a caveat precision has to carry, not a curiosity. The subgroup is small
enough that the answer is a direction and not a coefficient, which the report says out
loud rather than leaving to be inferred from a decimal.

The perturbation is synthetic. It says how the matcher degrades against a stated model of
drift; it does not say how much drift a live replay produces, which only a live replay
can establish.

Usage:
    python3 tools/replay/perturb.py --benchmark ~/path/to/benchmark
"""
import argparse
import os
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import benchmark as bench
import match as matcher

# Fixed so the published table is re-derivable. Sharing score.py's holdout seed would
# tie two unrelated draws together: re-seeding one to redraw the holdout would silently
# move every number here too.
PERTURB_SEED = 917
SEEDS = 5

# The bias check reads a subgroup of 18 false-positive records out of 241, where one
# record is 5.6 points. Five seeds put it anywhere from 88% to 93% — enough to flip the
# sign of the gap it is trying to measure — so it gets its own, much larger draw. Even
# then, 18 records is a weak estimate and the report says so.
BIAS_SEEDS = 100

# (label, line jitter in either direction — None drops the line, fraction of claim words
# dropped, whether the path survives). The labels are the published table's row headings.
SCENARIOS = (
    ("±5 lines, 20% of claim words dropped and shuffled", 5, 0.20, True),
    ("±15 lines, 40% dropped", 15, 0.40, True),
    ("±30 lines (past the window), 40% dropped", 30, 0.40, True),
    ("±15 lines, 60% dropped", 15, 0.60, True),
    ("no line numbers at all, 40% dropped", None, 0.40, True),
    ("no path at all, 40% dropped", 15, 0.40, False),
    ("±15 lines, 80% dropped", 15, 0.80, True),
)

# The row the bias check is measured on: enough drift to lose some records, not so much
# that what is left is noise. Named rather than indexed so reordering SCENARIOS cannot
# silently move the bias figure onto a different perturbation.
BIAS_SCENARIO = "±15 lines, 40% dropped"


def reword(claim, rng, drop):
    """Drop a fraction of the words and shuffle what survives.

    Shuffling is invisible to the current matcher, which compares token sets — it is here
    because a reworded claim genuinely arrives in a different order, and a future
    order-sensitive signal would have to survive it too.
    """
    kept = [w for w in claim.split() if rng.random() >= drop]
    rng.shuffle(kept)
    return " ".join(kept)


def perturb(record, rng, jitter, drop, keep_path):
    """One drifted copy of a frozen record, carrying the id it came from.

    `origin` is what makes mis-assignment measurable: without it a pair scored on path and
    claim alone looks identical whether the matcher landed on the right record or on a
    neighbour that happens to sit in the same file.
    """
    line = record["line_start"]
    if jitter is None:
        line = None
    elif line is not None:
        line = max(1, line + rng.randint(-jitter, jitter))
    return dict(record, id=f"perturbed-{record['id']}", origin=record["id"],
                line_start=line, line_end=None,
                path=record["path"] if keep_path else None,
                claim=reword(record["claim"], rng, drop))


def _verdict_group(record):
    if record.get("verdict") in bench.FALSE_VERDICTS:
        return "false"
    if record.get("verdict") in bench.TRUE_VERDICTS:
        return "true"
    return None


def run_scenario(frozens, jitter, drop, keep_path, seeds=SEEDS):
    """Match `seeds` independently perturbed copies of the corpus against the originals.

    Mis-assignment is returned as a share of the pairs the matcher accepted as well as a
    count: heavy drift shrinks the denominator, so a rising count next to a collapsing
    match rate understates how much of what survived is wrong.
    """
    groups = {"false": [], "true": []}
    for record in frozens:
        group = _verdict_group(record)
        if group:
            groups[group].append(record["id"])

    rates, misassigned, wrong_shares, group_rates = [], [], [], {"false": [], "true": []}
    for s in range(seeds):
        rng = random.Random(PERTURB_SEED + s)
        replays = [perturb(f, rng, jitter, drop, keep_path) for f in frozens]
        result = matcher.match(replays, frozens)
        accepted = result["matched"]
        rates.append(len(accepted) / len(replays) if replays else 0.0)
        wrong = sum(1 for m in accepted if m["frozen"]["id"] != m["replay"]["origin"])
        misassigned.append(wrong)
        wrong_shares.append(wrong / len(accepted) if accepted else 0.0)

        placed = {m["replay"]["origin"] for m in accepted}
        for group, ids in groups.items():
            if ids:
                group_rates[group].append(
                    sum(1 for i in ids if i in placed) / len(ids))
    return {"match_rate": _mean(rates), "misassigned": _mean(misassigned),
            "misassigned_share": _mean(wrong_shares),
            "false_match_rate": _mean(group_rates["false"]),
            "true_match_rate": _mean(group_rates["true"]),
            "n_false": len(groups["false"]), "n_true": len(groups["true"])}


def _mean(values):
    return sum(values) / len(values) if values else None


def _pct(value):
    return "n/a" if value is None else f"{value * 100:.1f}%"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", default=os.environ.get("REVIEW_PR_BENCHMARK"),
                    help="root of the private benchmark dir (or REVIEW_PR_BENCHMARK). "
                         "No default — the data must never be locatable from this repo.")
    ap.add_argument("--seeds", type=int, default=SEEDS,
                    help="independent perturbations averaged per row")
    ap.add_argument("--bias-seeds", type=int, default=BIAS_SEEDS,
                    help="draws for the false-positive bias check, which reads a subgroup "
                         "far too small for the row count to resolve")
    args = ap.parse_args()

    if not args.benchmark:
        ap.error("--benchmark or REVIEW_PR_BENCHMARK is required")
    if args.seeds < 1 or args.bias_seeds < 1:
        ap.error("seed counts must be at least 1")
    root = pathlib.Path(args.benchmark).expanduser()
    if not root.is_dir():
        ap.error(f"benchmark dir not found: {root}")

    frozens, notes = bench.load_verdicts(root)
    # The loader's own warnings — a subsumed re-export, a partial overlap inflating the
    # corpus — decide whether these rows describe 241 findings or 241 rows holding fewer.
    # On stderr so the table stays pipeable into the README.
    for note in notes:
        print(note, file=sys.stderr)

    rows = [run_scenario(frozens, *scenario[1:], seeds=args.seeds)
            for scenario in SCENARIOS]

    print(f"Perturbation of {len(frozens)} frozen records, {args.seeds} seeds each, "
          f"seed base {PERTURB_SEED}.\n")
    print("| perturbation | match | mis-assigned |")
    print("| --- | --- | --- |")
    for (label, _, _, _), row in zip(SCENARIOS, rows):
        print(f"| {label} | {_pct(row['match_rate'])} | {row['misassigned']:.1f} "
              f"({_pct(row['misassigned_share'])} of accepted) |")

    label, jitter, drop, keep_path = next(s for s in SCENARIOS if s[0] == BIAS_SCENARIO)
    bias = run_scenario(frozens, jitter, drop, keep_path, seeds=args.bias_seeds)
    print(f"\nMatcher bias at \"{label}\", {args.bias_seeds} seeds:")
    if not bias["n_false"] or not bias["n_true"]:
        # A corpus graded all one way has no two groups to compare, and printing one
        # group's rate next to a 0.0% that means "nobody was in this group" is how a
        # missing measurement gets read as a strong one.
        print(f"  NOT MEASURED — the corpus in scope holds {bias['n_false']} false and "
              f"{bias['n_true']} true records; a bias needs both.")
        return 0
    print(f"  FP records (n={bias['n_false']}) match at {_pct(bias['false_match_rate'])} "
          f"against {_pct(bias['true_match_rate'])} for true ones (n={bias['n_true']}).")
    print("  Read as a direction, not a coefficient: one FP record is "
          f"{100 / bias['n_false']:.1f} points.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
