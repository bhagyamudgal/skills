#!/usr/bin/env python3
"""Score a /review-pr run against the frozen benchmark: precision, recall, match rate.

Precision is the number the skill is tuned on — Critical+Serious false-positive rate,
which has to stay at or under 5%. Recall is the number nobody has yet moved: escaped
defects that a diff would have shown, and how many the run names.

Match rate is reported as loudly as either, because it bounds both. Precision computed
over the 60% of findings a matcher could place, with the other 40% quietly discarded,
is a statement about the matcher. Every finding is accounted for here: matched,
ambiguous, or unmatched.

Usage:
    python3 tools/replay/score.py --benchmark ~/path/to/benchmark --self-check
    python3 tools/replay/score.py --benchmark ~/path/to/benchmark --findings run.json
    python3 tools/replay/score.py --benchmark ~/path/to/benchmark --findings run.json \\
        --source review-pr-skill --json out.json
    python3 tools/replay/score.py --benchmark ~/path/to/benchmark --show-holdout

Set REVIEW_PR_BENCHMARK to avoid passing --benchmark every time. There is no default:
the benchmark is private and must never be findable from this repo.
"""
import argparse
import hashlib
import json
import math
import os
import pathlib
import random
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import benchmark as bench
import match as matcher

# Fixed for the life of the benchmark. Changing it re-draws the held-out set and
# invalidates every recall number ever reported against the old one; if it ever has to
# change, the new seed goes in the report and the old results are retired, not compared.
HOLDOUT_SEED = 20260806
HOLDOUT_FRACTION = 0.20

# Recall claims are cheap to fake with vague wording, so the bar sits above the level
# where generic prose ("this query is unbounded") starts brushing real defects.
RECALL_THRESHOLD = 0.35

# Enough to resolve a p-value well below 0.05; the standard estimator bottoms out at
# 1/(permutations+1), so the 5 this used to run could not have supported one.
PERMUTATIONS = 200

# Below this, precision is a statement about the matcher rather than about the reviewer:
# the findings it fails to place are enriched for false positives, so the measured rate
# is optimistic by an amount that grows as the match rate falls.
MIN_MATCH_RATE = 0.60

EXIT_OK = 0
EXIT_REGRESSION = 1
EXIT_UNCERTIFIABLE = 2
EXIT_LABELS = {EXIT_OK: "within target, on evidence worth trusting",
               EXIT_REGRESSION: "REGRESSION",
               EXIT_UNCERTIFIABLE: "CANNOT CERTIFY"}

# `number` is deliberately NOT a PR alias. It is the commonest field name in the world;
# accepting it means any unrelated `number` on a row becomes a PR, and the PR check is a
# hard reject — one stray field silently rejects every record the row is compared to.
FIELD_ALIASES = {
    "path": ("path", "file", "file_path", "filename"),
    "claim": ("claim", "issue", "title", "finding", "description"),
    "severity_raw": ("severity", "severity_raw", "sev"),
    "pr": ("pr", "pr_number"),
    "source": ("source",),
    "id": ("id", "fid", "finding_id"),
}


def wilson95(k, n):
    """95% Wilson score interval — the benchmark's own files report intervals this way."""
    if n == 0:
        return [0.0, 0.0]
    z, p = 1.959964, k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, centre - half), 4), round(min(1.0, centre + half), 4)]


def _pick(row, key):
    for alias in FIELD_ALIASES[key]:
        if row.get(alias) not in (None, ""):
            return row[alias]
    return None


def load_findings(path):
    """Read a replay run's findings, tolerating the field names a skill run may emit."""
    doc = json.loads(pathlib.Path(path).read_text())
    rows = doc.get("findings", doc) if isinstance(doc, dict) else doc
    out = []
    for i, row in enumerate(rows):
        raw_path = _pick(row, "path")
        p, start, end, quality = bench._parse_free_anchor(raw_path)
        line = row.get("line") if row.get("line") is not None else row.get("line_start")
        if line is not None:
            start, _ = bench._split_lines(line)
        sev = bench._norm_severity(_pick(row, "severity_raw"))
        source = _pick(row, "source") or "review-pr-skill"
        out.append({
            "id": _pick(row, "id") or f"replay-{i}", "path": p, "line_start": start,
            "line_end": end, "anchor_quality": quality, "claim": _pick(row, "claim") or "",
            "severity": sev, "severity_raw": _pick(row, "severity_raw"),
            "tier": bench._tier(source, sev), "source": source,
            "pr": int(_pick(row, "pr")) if _pick(row, "pr") is not None else None,
        })
    return out


def holdout_split(escaped, seed=HOLDOUT_SEED, fraction=HOLDOUT_FRACTION):
    """Reserve a deterministic slice of the escaped-defect set, never scored in dev.

    Sorted before shuffling so the draw depends only on the seed and the set's contents,
    not on file order or dict iteration. The digest of the reserved ids goes in every
    report — that is what makes 'we did not tune on this' checkable rather than claimed.
    """
    ids = sorted(d["id"] for d in escaped)
    rng = random.Random(seed)
    rng.shuffle(ids)
    n = int(round(len(ids) * fraction))
    reserved = set(ids[:n])
    # sha1 of the empty string is a perfectly well-formed digest, so an empty holdout
    # would otherwise print as an audit trail proving nothing was held out at all.
    digest = hashlib.sha1("|".join(sorted(reserved)).encode()).hexdigest()[:12] \
        if reserved else "EMPTY-NOTHING-RESERVED"
    return reserved, {"seed": seed, "fraction": fraction, "n_total": len(ids),
                      "n_holdout": len(reserved), "holdout_digest": digest}


def grade(result):
    """Turn a match result into precision counts, keeping unmatched visible."""
    buckets = {}
    for m in result["matched"]:
        f = m["frozen"]
        key = (f["corpus"], f["source"], f["tier"])
        b = buckets.setdefault(key, {"n": 0, "false": 0, "true": 0, "ungraded": 0,
                                     "verdicts": {}})
        b["n"] += 1
        v = f.get("verdict") or "UNGRADED"
        b["verdicts"][v] = b["verdicts"].get(v, 0) + 1
        if v in bench.FALSE_VERDICTS:
            b["false"] += 1
        elif v in bench.TRUE_VERDICTS:
            b["true"] += 1
        else:
            b["ungraded"] += 1
    for b in buckets.values():
        graded = b["true"] + b["false"]
        b["graded"] = graded
        b["fp_rate"] = round(b["false"] / graded, 4) if graded else None
        b["wilson95"] = wilson95(b["false"], graded)
    return buckets


def headline_rates(buckets):
    """High-tier FP rate PER SOURCE.

    Pooling sources here would be the single most misleading thing this harness could
    print: the benchmark holds a 0-2.6% skill rate next to a 15-17% CodeRabbit rate, and
    one pooled number moves with the sampling mix rather than with either reviewer.
    """
    out = {}
    for (_, source, tier), b in buckets.items():
        if tier != "high":
            continue
        h = out.setdefault(source, {"graded": 0, "false": 0})
        h["graded"] += b["graded"]
        h["false"] += b["false"]
    for h in out.values():
        h["fp_rate"] = h["false"] / h["graded"] if h["graded"] else None
        h["wilson95"] = wilson95(h["false"], h["graded"])
        # Nothing graded is an absence of evidence, not a failed target. Calling it FAIL
        # buries a harness problem under the same label as a real regression.
        if h["fp_rate"] is None:
            h["verdict"] = "NO-DATA"
        else:
            h["verdict"] = "PASS" if h["fp_rate"] <= 0.05 else "FAIL"
    return out


def frozen_baseline(frozens):
    """The benchmark's own rates, recomputed under one definition.

    The benchmark's NORMALIZATION.md warns that the per-batch aggregates were computed
    under different definitions and are not comparable as reported. This recomputes them
    from the raw records so the harness can be checked against the published numbers.
    """
    out = {}
    for f in frozens:
        key = (f["corpus"], f["source"], f["tier"])
        b = out.setdefault(key, {"n": 0, "false": 0, "true": 0, "verdicts": {}})
        b["n"] += 1
        v = f.get("verdict") or "UNGRADED"
        b["verdicts"][v] = b["verdicts"].get(v, 0) + 1
        if v in bench.FALSE_VERDICTS:
            b["false"] += 1
        elif v in bench.TRUE_VERDICTS:
            b["true"] += 1
    for b in out.values():
        graded = b["true"] + b["false"]
        b["graded"] = graded
        b["fp_rate"] = round(b["false"] / graded, 4) if graded else None
        b["wilson95"] = wilson95(b["false"], graded)
    return out


def _basenames(paths):
    return {p.rsplit("/", 1)[-1] for p in paths}


def _best_recall_hit(findings, defect, threshold):
    basenames = _basenames(defect["paths"])
    best, best_f = 0.0, None
    for f in findings:
        if basenames and f.get("path"):
            if f["path"].rsplit("/", 1)[-1] not in basenames:
                continue
        s = matcher.recall_score(f["claim"], defect["text"])
        if s > best:
            best, best_f = s, f
    return (best, best_f) if best >= threshold else (best, None)


def _null_can_move(findings, defect):
    """Whether permuting claims can change this defect's outcome at all.

    The hit test takes a MAX over the candidate set, and the permutation only moves claims
    between findings. So when the file gate excludes nobody, the candidate set is every
    finding, the same multiset of claims is maximised over before and after, and the null
    equals the observed statistic by arithmetic — not by measurement. Three reachable
    regimes land here: a defect whose hint carries no path, findings that carry no path,
    and every finding sharing one basename.
    """
    basenames = _basenames(defect["paths"])
    if not basenames:
        return False
    return any(f.get("path") and f["path"].rsplit("/", 1)[-1] not in basenames
               for f in findings)


def score_recall(findings, escaped, reserved, threshold=RECALL_THRESHOLD,
                 permutations=PERMUTATIONS):
    """Escaped defects a diff would have shown, and how many the run names.

    Reported against a permutation null. Text similarity between a one-line finding and
    a paragraph of root-cause prose produces hits by coincidence at a rate that is NOT
    negligible here — measured, not assumed — so a bare recall percentage would read as
    signal when much of it is chance. The null re-runs the same scorer with the claims
    shuffled onto other findings' file anchors: whatever it scores is what the file gate
    and generic engineering vocabulary buy you for free.

    The null is only alive where the file gate actually restricts the candidate set, so
    the count of defects it cannot move is reported next to it and a fully degenerate
    null yields no lift and no p-value rather than a decorative 1.0.
    """
    eligible = [d for d in escaped
                if d["diff_visible"] in ("yes", "partial") and d["id"] not in reserved]
    hits, named_gated, named_ungated = [], 0, 0
    for d in eligible:
        best, hit = _best_recall_hit(findings, d, threshold)
        if hit is None:
            continue
        # Gated means the file gate actually ran: the defect named a path AND the winning
        # finding carried one to test against it. A pathless finding skips the gate, and
        # labelling its hit "file-gated" claims evidence that was never checked.
        gated = bool(d["paths"]) and bool(hit.get("path"))
        named_gated += gated
        named_ungated += not gated
        hits.append({"defect": d["id"], "defect_class": d["defect_class"],
                     "diff_visible": d["diff_visible"], "gated": gated,
                     "score": round(best, 4), "finding": hit["id"]})

    live = [d for d in eligible if _null_can_move(findings, d)]
    nulls = []
    for s in range(permutations):
        rng = random.Random(HOLDOUT_SEED + s)
        claims = [f["claim"] for f in findings]
        rng.shuffle(claims)
        shuffled = [dict(f, claim=c) for f, c in zip(findings, claims)]
        nulls.append(sum(1 for d in eligible
                         if _best_recall_hit(shuffled, d, threshold)[1] is not None))
    null_mean = sum(nulls) / len(nulls) if nulls else None

    named = len(hits)
    if not live or not nulls:
        status, lift, p_value = "degenerate", None, None
    elif null_mean == 0:
        # A null that never fired is the best outcome the harness can produce, and the one
        # a bare `named / null_mean` renders as `None`. Both named explicitly, because
        # 0 named against a 0 null is the WEAKEST outcome and shares the same arithmetic.
        if named:
            status, lift, p_value = "null_never_fired", None, 1 / (len(nulls) + 1)
        else:
            status, lift, p_value = "nothing_named", None, None
    else:
        status = "ok"
        lift = round(named / null_mean, 2)
        p_value = round((1 + sum(1 for x in nulls if x >= named)) / (len(nulls) + 1), 4)

    by_vis, ungatable = {}, 0
    for d in eligible:
        by_vis[d["diff_visible"]] = by_vis.get(d["diff_visible"], 0) + 1
        ungatable += not d["paths"]
    return {"eligible": len(eligible), "named": named,
            "rate": round(named / len(eligible), 4) if eligible else None,
            "named_gated": named_gated, "named_ungated": named_ungated,
            "ungatable_defects": ungatable, "threshold": threshold,
            "null_mean": null_mean, "nulls": nulls, "permutations": len(nulls),
            "null_live_defects": len(live), "null_dead_defects": len(eligible) - len(live),
            "null_status": status, "lift": lift, "p_value": p_value,
            "eligible_by_visibility": by_vis, "hits": hits}


def _fmt_bucket(key, b):
    corpus, source, tier = key
    rate = "n/a" if b["fp_rate"] is None else f"{b['fp_rate'] * 100:5.1f}%"
    lo, hi = b["wilson95"]
    verdicts = ", ".join(f"{k}={v}" for k, v in sorted(b["verdicts"].items()))
    return (f"  {corpus:<22} {source:<16} {tier:<5} n={b['n']:<4} graded={b['graded']:<4} "
            f"FP+HALL={b['false']:<3} rate={rate}  95%[{lo * 100:.1f}-{hi * 100:.1f}]\n"
            f"      {verdicts}")


def match_rate(result, findings):
    return len(result["matched"]) / len(findings) if findings else 0.0


def gate(args, result, findings, headline):
    """Decide the exit status, and say why in words the caller can print.

    Three codes, because one bit cannot carry three outcomes: 0 the skill is within
    target on evidence worth trusting, 1 the skill regressed, 2 this run cannot certify
    anything either way. Collapsing 2 into 0 is the dangerous direction — it reports
    green when the matcher placed nothing and nothing was graded.
    """
    skill = headline.get("review-pr-skill")
    if args.gold:
        return EXIT_UNCERTIFIABLE, ["--gold findings carry no verdicts — this mode "
                                    "measures recall and cannot gate precision"]

    blockers = []
    if not findings:
        blockers.append("the run produced no findings at all")
    else:
        rate = match_rate(result, findings)
        if rate < args.min_match_rate:
            blockers.append(f"match rate {rate * 100:.1f}% is below the "
                            f"{args.min_match_rate * 100:.0f}% floor — the FP rate below "
                            f"it describes the matcher, not the reviewer")
    if skill is None or not skill["graded"]:
        blockers.append("no high-tier skill finding was graded — there is no precision "
                        "measurement here to pass")

    # A regression outranks an unusable run: if the rate cleared 5% on whatever WAS
    # graded, that is the more actionable of the two facts.
    if skill and skill["verdict"] == "FAIL":
        return EXIT_REGRESSION, blockers + [
            f"skill high-tier FP rate {skill['fp_rate'] * 100:.2f}% exceeds the 5.00% "
            f"target"]
    return (EXIT_UNCERTIFIABLE if blockers else EXIT_OK), blockers


def report(args, frozens, findings, result, buckets, headline, base, recall, split,
           notes, status, blockers):
    n = len(findings)
    matched = len(result["matched"])
    rate = matched / n if n else 0.0
    print("=" * 78)
    print("BENCHMARK LOAD")
    for note in notes:
        print(f"  {note}")
    print(f"\n  frozen records in scope: {len(frozens)}")

    print("\n" + "=" * 78)
    print("MATCH RATE  (bounds every number below it)")
    print(f"  replay findings:     {n}")
    print(f"  matched   >= {matcher.ACCEPT:.2f}:   {matched}  ({rate * 100:.1f}%)")
    print(f"  ambiguous >= {matcher.AMBIGUOUS:.2f}:   {len(result['ambiguous'])}"
          f"   (excluded from precision — not confidently the same finding)")
    print(f"  unmatched replay:    {len(result['unmatched_replay'])}"
          f"   (ungradable: no frozen verdict for them)")
    print(f"  unmatched frozen:    {len(result['unmatched_frozen'])}"
          f"   (benchmark findings this run did not reproduce)")

    print("\n" + "=" * 78)
    print("PRECISION — matched findings graded against their frozen verdict")
    if args.gold:
        print("  --gold: blind third-review findings carry no verdict. This section is")
        print("  empty by construction; read MATCH RATE and RECALL instead.")
    print("  Severity tiers are a STATED CROSSWALK, not an equivalence:")
    print("    review-pr-skill high = Critical|Serious;  coderabbit high = Critical|Major")
    if not buckets:
        print("  (nothing matched — no precision to report)")
    for key in sorted(buckets):
        print(_fmt_bucket(key, buckets[key]))
    print()
    if not headline:
        print("  HEADLINE  no high-tier findings graded")
    for source, h in sorted(headline.items()):
        r = "n/a" if h["fp_rate"] is None else f"{h['fp_rate'] * 100:.2f}%"
        print(f"  HEADLINE  {source:<16} high-tier FP+HALL = {h['false']}/{h['graded']}"
              f" = {r}   (target <= 5.00%)  {h['verdict']}")

    print("\n" + "=" * 78)
    print("FROZEN BASELINE — the benchmark's own rates, recomputed under one definition")
    for key in sorted(base):
        print(_fmt_bucket(key, base[key]))

    print("\n" + "=" * 78)
    print("RECALL — escaped defects a diff would have shown")
    print(f"  seed={split['seed']} fraction={split['fraction']}  "
          f"holdout={split['n_holdout']}/{split['n_total']} "
          f"digest={split['holdout_digest']}  (reserved, never scored)")
    if not split["n_holdout"]:
        print("  WARNING nothing was reserved — this run is not held out from anything")
    print(f"  eligible (yes|partial, dev split): {recall['eligible']}"
          f"   {recall['eligible_by_visibility']}"
          f"   ({recall['ungatable_defects']} have no path in file_hint — claim text only)")
    pct = "n/a" if recall["rate"] is None else f"{recall['rate'] * 100:.1f}%"
    print(f"  named by this run:                 {recall['named']}  ({pct})"
          f"   file-gated={recall['named_gated']} ungated={recall['named_ungated']}")
    _report_null(recall)
    for h in recall["hits"][:args.show_hits]:
        print(f"    {h['score']:.3f}  {h['diff_visible']:<8} {h['defect_class']}")

    print("\n" + "=" * 78)
    print(f"VERDICT  exit {status}  ({EXIT_LABELS[status]})")
    for reason in blockers:
        print(f"  - {reason}")
    print("=" * 78)


def _report_null(recall):
    """The null is the harness's central statistical claim, so a dead one has to say so."""
    mean = "n/a" if recall["null_mean"] is None else f"{recall['null_mean']:.1f}"
    sample = recall["nulls"][:8]
    tail = ", ..." if len(recall["nulls"]) > len(sample) else ""
    print(f"  permutation null (thr={recall['threshold']}, n={recall['permutations']}): "
          f"      {mean}  [{', '.join(str(x) for x in sample)}{tail}]")
    print(f"  defects the null can move:         {recall['null_live_defects']}"
          f"   (dead for {recall['null_dead_defects']}: no path on the defect or on the "
          f"findings, so the file gate excludes nobody)")
    if recall["null_status"] == "degenerate":
        print("  NO LIFT REPORTED — the null is arithmetically identical to the observed")
        print("  statistic across every eligible defect. Permuting claims between findings")
        print("  cannot change a maximum taken over all of them. This is not a result.")
        return
    if recall["null_status"] == "nothing_named":
        print("  NO LIFT REPORTED — the run named no defects and neither did the null.")
        print("  This is the weakest outcome, not an unbounded one.")
        return
    if recall["null_status"] == "null_never_fired":
        print(f"  lift: UNBOUNDED — the null named 0 defects in all "
              f"{recall['permutations']} permutations, so there is no ratio to take. "
              f"This is the strongest outcome, not a missing number.")
    else:
        print(f"  lift x{recall['lift']}")
    print(f"  p = {recall['p_value']}   (permutations naming at least as many as the run,"
          f" +1 smoothed)")
    print("  A recall number near the null is chance, not detection. Read them together.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--benchmark", default=os.environ.get("REVIEW_PR_BENCHMARK"),
                    help="root of the private benchmark dir (or REVIEW_PR_BENCHMARK). "
                         "No default — the data must never be locatable from this repo.")
    ap.add_argument("--findings", help="JSON findings produced by a skill run")
    ap.add_argument("--self-check", action="store_true",
                    help="score the frozen verdicts as their own input. Near-100%% match "
                         "and near-0%% FP is the only proof the matcher works at all.")
    ap.add_argument("--corpus", action="append",
                    help="restrict the frozen set by corpus label (the verdict file stem)")
    ap.add_argument("--source", action="append",
                    help="restrict the frozen set by source (review-pr-skill, coderabbit)")
    ap.add_argument("--gold", action="store_true",
                    help="score against the blind third-review findings instead of the "
                         "adjudicated verdicts — recall ground truth with real anchors")
    ap.add_argument("--window", type=int, default=matcher.LINE_WINDOW,
                    help="line-proximity window in lines")
    ap.add_argument("--recall-threshold", type=float, default=RECALL_THRESHOLD)
    ap.add_argument("--permutations", type=int, default=PERMUTATIONS,
                    help="permutation null draws; the p-value cannot go below "
                         "1/(n+1), so a handful of draws cannot support one")
    ap.add_argument("--min-match-rate", type=float, default=MIN_MATCH_RATE,
                    help="below this the run exits 2 (cannot certify): precision over a "
                         "minority of findings measures the matcher, not the reviewer")
    ap.add_argument("--seed", type=int, default=HOLDOUT_SEED)
    ap.add_argument("--show-holdout", action="store_true",
                    help="print the reserved ids and exit — for auditing the split only")
    ap.add_argument("--show-hits", type=int, default=10)
    ap.add_argument("--json", help="write the full result, including every unmatched item")
    args = ap.parse_args()

    if not args.benchmark:
        ap.error("--benchmark or REVIEW_PR_BENCHMARK is required")
    root = pathlib.Path(args.benchmark).expanduser()
    if not root.is_dir():
        ap.error(f"benchmark dir not found: {root}")

    escaped, enotes = bench.load_escaped(root)
    reserved, split = holdout_split(escaped, args.seed)
    if args.show_holdout:
        print(json.dumps({"split": split, "ids": sorted(reserved)}, indent=2))
        return 0

    if args.gold:
        frozens, notes = bench.load_gold(root)
    else:
        frozens, notes = bench.load_verdicts(root)
    notes = notes + enotes
    if args.corpus:
        frozens = [f for f in frozens if f["corpus"] in set(args.corpus)]
    if args.source:
        frozens = [f for f in frozens if f["source"] in set(args.source)]

    if args.self_check:
        findings = [dict(f) for f in frozens]
        notes.append("SELF-CHECK: frozen records replayed as their own input")
    elif args.findings:
        findings = load_findings(args.findings)
    else:
        ap.error("--findings or --self-check is required")

    result = matcher.match(findings, frozens, window=args.window)
    buckets = grade(result)
    headline = headline_rates(buckets)
    base = frozen_baseline(frozens)
    recall = score_recall(findings, escaped, reserved, args.recall_threshold,
                          args.permutations)
    status, blockers = gate(args, result, findings, headline)

    # Written before the report, not after: the machine-readable artifact is what CI
    # reads, and it must not be hostage to a formatting error in the human-readable one.
    if args.json:
        payload = {
            "notes": notes, "split": split,
            "exit": {"status": status, "label": EXIT_LABELS[status],
                     "blockers": blockers,
                     "match_rate": round(match_rate(result, findings), 4)},
            "match": {
                "n_findings": len(findings), "matched": len(result["matched"]),
                "ambiguous": len(result["ambiguous"]),
                "unmatched_replay": [r["id"] for r in result["unmatched_replay"]],
                "unmatched_frozen": [f["id"] for f in result["unmatched_frozen"]],
                "pairs": [{"replay": m["replay"]["id"], "frozen": m["frozen"]["id"],
                           "score": m["score"], "signals": m["signals"],
                           "verdict": m["frozen"].get("verdict")}
                          for m in result["matched"]],
                "ambiguous_pairs": [{"replay": m["replay"]["id"],
                                     "frozen": m["frozen"]["id"], "score": m["score"]}
                                    for m in result["ambiguous"]],
            },
            "precision": {"|".join(k): v for k, v in buckets.items()},
            "headline": headline,
            "frozen_baseline": {"|".join(k): v for k, v in base.items()},
            "recall": recall,
        }
        pathlib.Path(args.json).write_text(json.dumps(payload, indent=2))
        print(f"wrote {args.json}\n")

    report(args, frozens, findings, result, buckets, headline, base, recall, split,
           notes, status, blockers)
    # Only the skill's own rate can fail this — CodeRabbit's is a comparison point in
    # this benchmark, not something this repo can regress or fix.
    return status


if __name__ == "__main__":
    sys.exit(main())
