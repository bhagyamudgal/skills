#!/usr/bin/env python3
"""Token and wall-time accounting for a review-pr live run.

Reads the stream-json transcripts produced by `claude -p "/review-pr <url>"
--output-format stream-json --verbose` (one file per agent: the main run first,
then one file per dispatched subagent) and reports input/output/cache tokens
plus wall time, split by main and subagent. Built on harness.iter_events so a
truncated transcript reads as truncated, not clean.

Subagent tokens never appear inside the main transcript, which is why the run
procedure (docs/review_pr_fixture_runs.md) saves one file per agent instead of
relying on the main log alone. Wall times overlap: subagents run in parallel,
so the run wall time is the main duration while the summed durations are CPU.

Usage:
    python3 tools/eval/review_pr_tokens.py main.jsonl [sub1.jsonl ...] [--json]
"""
import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import harness

USAGE_KEYS = ("input_tokens", "output_tokens", "cache_creation_input_tokens",
              "cache_read_input_tokens")


def summarize(path):
    """Return token sums, wall time, cost, and truncation flag for one file."""
    text = pathlib.Path(path).read_text(encoding="utf-8")
    totals = {key: 0 for key in USAGE_KEYS}
    duration_ms, cost_usd, saw_result, turns = 0, 0.0, False, 0
    for event in harness.iter_events(text):
        if event.get("type") == "assistant":
            usage = (event.get("message") or {}).get("usage") or {}
            for key in USAGE_KEYS:
                totals[key] += usage.get(key, 0) or 0
        elif event.get("type") == "result":
            saw_result = True
            duration_ms = event.get("duration_ms", 0) or 0
            cost_usd = event.get("total_cost_usd", 0.0) or 0.0
            usage = event.get("usage") or {}
            for key in USAGE_KEYS:
                totals[key] = max(totals[key], usage.get(key, 0) or 0)
            turns = event.get("num_turns", 0) or 0
    _, _, error = harness.parse_transcript(text)
    return {"file": str(path), "truncated": not saw_result,
            "error": error, "turns": turns,
            "duration_ms": duration_ms, "cost_usd": round(cost_usd, 4),
            **totals}


def report(main_path, subagent_paths):
    agents = {"main": summarize(main_path)}
    agents["subagents"] = [summarize(path) for path in subagent_paths]
    total = {key: agents["main"][key] + sum(s[key] for s in agents["subagents"])
             for key in USAGE_KEYS}
    total["cost_usd"] = round(agents["main"]["cost_usd"]
                              + sum(s["cost_usd"] for s in agents["subagents"]), 4)
    agents["total"] = total
    return agents


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("main")
    parser.add_argument("subagents", nargs="*")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rep = report(args.main, args.subagents)
    if args.json:
        print(json.dumps(rep, indent=2))
        return
    rows = [("main", rep["main"])] + [(f"sub/{pathlib.Path(s['file']).stem}", s)
                                      for s in rep["subagents"]]
    print(f"{'agent':28} {'in':>9} {'out':>9} {'cache-new':>9} "
          f"{'cache-read':>10} {'wall-s':>7} {'usd':>7}")
    for name, s in rows:
        flag = " TRUNCATED" if s["truncated"] else ""
        print(f"{name:28} {s['input_tokens']:>9,} {s['output_tokens']:>9,} "
              f"{s['cache_creation_input_tokens']:>9,} {s['cache_read_input_tokens']:>10,} "
              f"{s['duration_ms'] / 1000:>7.0f} {s['cost_usd']:>7.2f}{flag}")
    t = rep["total"]
    print(f"{'TOTAL':28} {t['input_tokens']:>9,} {t['output_tokens']:>9,} "
          f"{t['cache_creation_input_tokens']:>9,} {t['cache_read_input_tokens']:>10,}")


if __name__ == "__main__":
    main()
